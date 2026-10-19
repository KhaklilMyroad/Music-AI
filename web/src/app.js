// Application shell. Owns the screen state machine and wires the UI to the
// CampaignService; it never writes campaign state itself.

import { atlas, chapters, weapons, history, districts, content, CONTENT_VERSIONS } from './data.generated.js';
import { newCampaign } from './sim/bootstrap.js';
import { CampaignService } from './sim/campaign.js';
import { SaveService } from './sim/save.js';
import { validateCampaign } from './sim/contracts.js';
import { UNIT_CAPABILITIES } from './sim/contracts.js';
import { i18n } from './ui/i18n.js';
import { Settings, SCHEMA } from './ui/settings.js';
import { TouchControls } from './ui/touch.js';
import { DesktopInput, DEFAULT_BINDINGS } from './ui/desktop-input.js';
import { MapView } from './strategic/map-view.js';
import { MissionScene } from './fps/mission.js';

const THREE_URL = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.module.min.js';

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

/** localStorage-backed store for SaveService. Fails soft in private mode. */
function browserStore() {
  const mem = new Map();
  const safe = (fn, fb) => { try { return fn(); } catch { return fb; } };
  return {
    read: (k) => safe(() => localStorage.getItem(k), mem.get(k) ?? null) ?? mem.get(k) ?? null,
    write: (k, v) => {
      mem.set(k, v);
      try { localStorage.setItem(k, v); }
      catch (e) {
        // A full quota is a player-facing condition, not a crash.
        if (String(e.name).includes('Quota')) { const err = new Error('save.no_space'); err.code = 'save.no_space'; throw err; }
      }
    },
    remove: (k) => { mem.delete(k); safe(() => localStorage.removeItem(k)); },
    keys: () => safe(() => Object.keys(localStorage), [...mem.keys()]),
  };
}

class App {
  constructor() {
    this.settings = new Settings();
    this.settings.set('language', i18n.locale);
    this.settings.applyTheme();
    this.saves = new SaveService(browserStore(), { engine_build: 'proto-0.1.0', contentVersions: CONTENT_VERSIONS });
    this.screen = null;
    this.three = null;
    this.mission = null;
    this.toasts = [];
    this.settings.subscribe((id, v) => this.onSetting(id, v));
  }

  // ------------------------------------------------------------------ boot --
  async boot() {
    this.bindChrome();
    const steps = [
      { id: 'content', label: i18n.locale === 'he' ? 'מאמת תוכן' : 'Verifying content' },
      { id: 'contracts', label: i18n.locale === 'he' ? 'בודק חוזי נתונים' : 'Checking data contracts' },
      { id: 'engine', label: i18n.locale === 'he' ? 'מאתחל רינדור' : 'Starting the renderer' },
      { id: 'saves', label: i18n.locale === 'he' ? 'קורא שמירות' : 'Reading saves' },
    ];
    const box = $('#boot-steps');
    box.innerHTML = '';
    const nodes = {};
    for (const s of steps) {
      const n = el('div', 'boot-step');
      n.append(el('span', 'dot'), el('span', null, s.label));
      box.append(n); nodes[s.id] = n;
    }
    const mark = (id, ok, extra) => {
      nodes[id].classList.add(ok ? 'ok' : 'fail');
      if (extra) nodes[id].append(el('span', 'note', ` — ${extra}`));
      $('#boot-bar > i').style.width = `${(Object.values(nodes).filter((n) => n.classList.contains('ok')).length / steps.length) * 100}%`;
    };

    // content verification: the launch screen the brief asks for
    const missing = [];
    for (const ch of chapters.chapters) if (ch.district && !districts[ch.district]) missing.push(ch.district);
    const uniqueMissing = [...new Set(missing)];
    mark('content', true, uniqueMissing.length
      ? (i18n.locale === 'he' ? `${Object.keys(districts).length} מותקן, ${uniqueMissing.length} לא מותקן` : `${Object.keys(districts).length} installed, ${uniqueMissing.length} not installed`)
      : `${Object.keys(districts).length} installed`);
    this.notInstalled = new Set(uniqueMissing);

    try {
      const probe = newCampaign(atlas, content, { date: '1944-06-06' });
      validateCampaign(probe);
      mark('contracts', true, `${Object.keys(probe.tiles).length} tiles`);
    } catch (e) { mark('contracts', false, e.message.split('\n')[0]); }

    try {
      this.three = await import(/* @vite-ignore */ THREE_URL);
      mark('engine', true, `three ${this.three.REVISION}`);
    } catch (e) {
      mark('engine', false, i18n.locale === 'he' ? 'אין רינדור תלת-ממד' : 'no 3D renderer available');
      this.engineFailed = true;
    }

    let resume = null;
    try { resume = this.saves.load('auto'); } catch { resume = null; }
    this.resumeState = resume;
    mark('saves', true, resume ? (i18n.locale === 'he' ? `נמצאה שמירה · שבוע ${resume.campaign.turn}` : `save found · week ${resume.campaign.turn}`) : (i18n.locale === 'he' ? 'אין שמירה' : 'no save'));
    if (resume?.recovered_from) this.toast(i18n.t('error.save_corrupt'), true);

    await new Promise((r) => setTimeout(r, 420));
    this.renderMenu();
    this.show('menu');
  }

  bindChrome() {
    addEventListener('resize', () => { this.map?.resize(); this.mission?.resize(); });
    // Interruption: pause safely and checkpoint. On PC the causes are alt-tab,
    // the pause key, sleep and a crash, and the durable-write order in docs/04
    // is what makes any of them safe. A final shutdown callback is never
    // relied on, because a crash does not send one.
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) this.onInterrupted('focus_lost');
    });
    addEventListener('pagehide', () => this.onInterrupted('page_hide'));
    addEventListener('blur', () => { if (this.screen === 'mission') this.onInterrupted('blur'); });
    $('#rotate-continue').addEventListener('click', () => { $('#rotate-hint').style.display = 'none'; });
    $('#menu-art') && this.paintMenuArt();
  }

  onInterrupted(kind) {
    if (this.screen === 'mission' && this.mission && !this.mission.finished) {
      if (this.mission.paused) return;
      this.mission.paused = true;
      this.input?.release();
      this.mission.audio.onInterruption(kind === 'focus_lost' ? 'focus_lost' : 'paused');
      try { this.svc.checkpointDistrict(this.mission.checkpoint()); } catch (e) { /* already resolved */ }
      this.openPause();
    } else if (this.svc) {
      try { this.svc.persist(`interrupted_${kind}`); } catch (e) { this.onSaveError(e); }
    }
  }

  onSaveError(e) {
    this.toast(i18n.t(e?.code === 'save.no_space' ? 'error.save_no_space' : 'error.save_corrupt'), true);
  }

  show(name) {
    this.screen = name;
    for (const s of $$('.screen')) s.classList.toggle('is-active', s.id === `screen-${name}`);
    $('#touch').hidden = name !== 'mission';
  }

  toast(text, bad = false) {
    const n = el('div', bad ? 'bad' : null, text);
    $('#toast').append(n);
    setTimeout(() => n.remove(), 4200);
  }

  onSetting(id, v) {
    if (id === 'language') { i18n.set(v); try { localStorage.setItem('wbtm.locale', v); } catch {} location.reload(); return; }
    this.settings.applyTheme();
    if (['preset', 'render_scale', 'draw_distance', 'anti_aliasing'].includes(id) && this.mission) {
      const o = this.settings.rendererOptions();
      this.mission.renderer.setPixelRatio(Math.min(devicePixelRatio || 1, o.pixelRatioCap) * o.renderScale);
      this.mission.resize();
    }
    if (id === 'output_mode' || id.startsWith('vol_') || id === 'sound_captions') {
      if (this.mission) Object.assign(this.mission.audio, this.settings.audioOptions());
    }
    if (this.map) this.map.draw();
  }

  // ------------------------------------------------------------------ menu --
  renderMenu() {
    const t = (k) => i18n.t(k);
    $('#menu-title').textContent = t('app.title');
    const box = $('#menu-actions');
    box.innerHTML = '';
    const add = (labelKey, hint, fn, primary) => {
      const b = el('button', `btn${primary ? ' btn-primary' : ''}`);
      b.append(el('span', null, t(labelKey)));
      if (hint) b.append(el('span', 'hint', hint));
      b.addEventListener('click', fn);
      box.append(b);
      return b;
    };
    if (this.resumeState) {
      add('menu.continue', `${t('map.turn')} ${this.resumeState.campaign.turn} · ${i18n.date(this.resumeState.campaign.date)}`, () => this.startCampaign(this.resumeState.campaign, this.resumeState.district_checkpoint), true);
    }
    add('menu.new_campaign', '1944-06-06 · Normandy', () => this.startCampaign(null), !this.resumeState);
    add('menu.sandbox', i18n.locale === 'he' ? 'חקירה חופשית' : 'free exploration', () => this.startCampaign(null, null, 'sandbox'));
    add('menu.history', `${history.records.length} ${i18n.locale === 'he' ? 'רשומות' : 'records'}`, () => this.openHistory());
    add('menu.settings', null, () => this.openSettings());
    $('#menu-note').textContent = i18n.locale === 'he'
      ? 'אב טיפוס עיצובי למשחק PC. מקלדת ועכבר. הגאומטריה, הדמויות והצליל הם בלוקאאוט — לא הרף האמנותי המסחרי. הלולאה, החוזים והשמירות הם אמיתיים.'
      : 'PC design prototype. Keyboard and mouse. Geometry, characters and sound are blockout — not the commercial art bar. The loop, the data contracts and the saves are real.';
  }

  paintMenuArt() {
    const cv = $('#menu-art');
    const resize = () => {
      const r = cv.parentElement.getBoundingClientRect();
      const dpr = Math.min(devicePixelRatio || 1, 2);
      cv.width = r.width * dpr; cv.height = r.height * dpr;
      const c = cv.getContext('2d');
      c.scale(dpr, dpr);
      const W = r.width, H = r.height;
      const sky = c.createLinearGradient(0, 0, 0, H);
      sky.addColorStop(0, '#2a3238'); sky.addColorStop(0.55, '#1a2024'); sky.addColorStop(1, '#0d1113');
      c.fillStyle = sky; c.fillRect(0, 0, W, H);
      // layered hedgerow silhouettes: near, middle, distant
      const layers = [[0.52, '#141a16', 26], [0.64, '#0f1512', 18], [0.78, '#0a0e0c', 12]];
      for (const [y, col, amp] of layers) {
        c.beginPath(); c.moveTo(0, H);
        for (let x = 0; x <= W; x += 6) {
          const h = H * y - Math.sin(x / 48 + y * 9) * amp - Math.sin(x / 13 + y * 3) * amp * 0.3;
          c.lineTo(x, h);
        }
        c.lineTo(W, H); c.closePath();
        c.fillStyle = col; c.fill();
      }
      // a thin light line on the horizon, and the grid overlay that hints at the map
      c.strokeStyle = 'rgba(201,143,54,.22)'; c.lineWidth = 1;
      for (let i = 0; i < 9; i++) {
        c.beginPath();
        const yy = H * 0.5 + i * 18;
        c.moveTo(0, yy); c.lineTo(W, yy + 8); c.stroke();
      }
      c.fillStyle = 'rgba(201,143,54,.08)';
      c.fillRect(0, H * 0.5, W, H * 0.5);
    };
    resize();
    addEventListener('resize', resize);
  }

  // -------------------------------------------------------------- campaign --
  startCampaign(existing, districtCheckpoint, mode = 'campaign') {
    const campaign = existing || newCampaign(atlas, content, {
      date: '1944-06-06', seed: (Date.now() & 0x7fffffff) || 7, mode,
      campaign_id: mode === 'sandbox' ? 'cmp_sandbox' : 'cmp_main',
    });
    this.svc = new CampaignService(campaign, atlas, content, this.saves);
    this.svc.subscribe((kind, data) => this.onCampaignEvent(kind, data));

    const rec = this.svc.recover();
    if (rec.action === 'cancelled_entry') this.toast(i18n.t('error.transition_failed'));
    if (rec.action === 'resume_mission' || rec.action === 'restart_mission') {
      this.pendingResume = { context: rec.context, checkpoint: rec.checkpoint };
    }
    if (rec.action === 'resumed_commit' || rec.action === 'already_committed' || rec.action === 'acknowledged') {
      if (rec.applied) this.showResultScreen(rec.applied, null, true);
    }

    this.map = new MapView($('#map-canvas'), this.svc, i18n, this.settings);
    this.map.onSelect = (sel) => this.openSelectionSheet(sel);
    this.map.onTapEmpty = () => this.closeSheet();
    this.map.onMoveTarget = (unit_id, tile_id) => {
      const u = this.svc.c.units[unit_id];
      if (!u) return;
      const kind = u.allowed_actions.includes('move') ? 'move' : 'move_covert';
      this.confirmOrder({ kind, unit_id, tile_id });
    };
    this.map.setTheater(this.theaterForDate());
    this.renderTopbar();
    this.renderMapbar();
    this.show('map');

    if (this.pendingResume) {
      const r = this.pendingResume; this.pendingResume = null;
      this.toast(i18n.locale === 'he' ? 'ממשיך מבצע שנקטע' : 'Resuming an interrupted operation');
      this.enterMissionScene(r.context, r.checkpoint);
    }
  }

  theaterForDate() {
    const open = this.svc.atlas.theaters.filter((t) => t.opens_on <= this.svc.c.date);
    return (open.find((t) => t.id === 'theater_western_europe') || open[0]).id;
  }

  onCampaignEvent(kind, data) {
    if (kind === 'order_rejected') this.toast(i18n.t(data.reason), true);
    if (kind === 'turn_resolved') this.openTurnReport(data);
    if (kind === 'mission_entry_rejected') this.toast(i18n.t('error.transition_failed'), true);
    this.renderTopbar();
    this.renderMapbar();
    this.map?.draw();
  }

  renderTopbar() {
    // Campaign events can fire before the map view exists (recover() runs on
    // adopt, ahead of the first render), so the chrome renderers are guarded.
    if (!this.map) return;
    const c = this.svc.c;
    $('#tb-date').textContent = i18n.date(c.date);
    $('#tb-turn').textContent = `${i18n.t('map.turn')} ${i18n.num(c.turn)}${c.mode === 'sandbox' ? ' · ' + i18n.t('menu.sandbox') : ''}`;
    const res = $('#tb-res');
    res.innerHTML = '';
    for (const [key, labelKey] of [['materiel', 'map.materiel'], ['personnel', 'map.personnel'], ['intelligence', 'map.intelligence']]) {
      const n = el('div', 'res-item');
      n.append(el('i', null, i18n.t(labelKey)), el('b', null, i18n.num(c.resources[key] ?? 0)));
      res.append(n);
    }
    const tabs = $('#tb-theaters');
    tabs.innerHTML = '';
    for (const th of this.map.theatersOpen()) {
      const b = el('button', null, i18n.t(th.label_key));
      b.setAttribute('aria-pressed', String(th.id === this.map.theater));
      b.addEventListener('click', () => { this.map.setTheater(th.id); this.renderTopbar(); });
      tabs.append(b);
    }
  }

  renderMapbar() {
    if (!this.svc) return;
    const bar = $('#mapbar');
    bar.innerHTML = '';
    const queued = this.svc.c.order_queue.length;
    const chaptersAvailable = this.svc.availableChapters().filter((ch) => ch.status === 'authored' && districts[ch.district]);

    const ops = el('button', 'btn');
    ops.append(el('span', null, i18n.locale === 'he' ? 'מבצעים' : 'Operations'), el('span', 'hint', String(chaptersAvailable.length)));
    ops.disabled = chaptersAvailable.length === 0;
    ops.addEventListener('click', () => this.openOperations());
    bar.append(ops);

    const journal = el('button', 'btn btn-ghost', i18n.t('menu.history'));
    journal.addEventListener('click', () => this.openHistory());
    bar.append(journal);

    const set = el('button', 'btn btn-ghost', i18n.t('menu.settings'));
    set.addEventListener('click', () => this.openSettings());
    bar.append(set);

    bar.append(el('div', 'spacer'));

    if (queued) {
      const q = el('button', 'btn btn-ghost');
      q.append(el('span', null, i18n.locale === 'he' ? 'פקודות בתור' : 'Queued orders'), el('span', 'hint', String(queued)));
      q.addEventListener('click', () => this.openQueue());
      bar.append(q);
    }
    const end = el('button', 'btn btn-primary', i18n.t('map.end_turn'));
    end.addEventListener('click', () => {
      const out = this.svc.endTurn();
      if (!out.ok) this.toast(i18n.t(out.reason), true);
    });
    bar.append(end);
  }

  // ----------------------------------------------------------------- sheet --
  closeSheet() { $('#sheet').classList.remove('is-open'); this.map?.previewPath(null); }

  openSheet(kicker, title, bodyFn, footFn) {
    const sh = $('#sheet');
    $('#sheet-kicker').textContent = kicker || '';
    $('#sheet-title').textContent = title || '';
    const body = $('#sheet-body'); body.innerHTML = '';
    const foot = $('#sheet-foot'); foot.innerHTML = '';
    bodyFn?.(body);
    footFn?.(foot);
    sh.classList.add('is-open');
  }

  openSelectionSheet(sel) {
    if (!sel) return this.closeSheet();
    if (sel.kind === 'unit') return this.openUnitSheet(sel.id);
    if (sel.kind === 'city') return this.openCitySheet(sel.id);
    return this.openTileSheet(sel.id);
  }

  openUnitSheet(unit_id) {
    const c = this.svc.c;
    const u = c.units[unit_id];
    if (!u) return;
    const cap = UNIT_CAPABILITIES[u.unit_type];
    const explain = this.svc.explainUnit(unit_id);
    const mine = u.faction === c.player_faction;
    const tile = c.tiles[u.tile_id];

    this.openSheet(i18n.t(`unit.${u.unit_type}`), i18n.t(u.label_key), (body) => {
      const dl = el('dl', 'kv');
      const add = (k, v) => { dl.append(el('dt', null, k), el('dd', null, v)); };
      add(i18n.locale === 'he' ? 'עוצמה' : 'Strength', `${Math.round(u.strength * 100)}%`);
      add(i18n.t('map.supply'), `${Math.round(u.supply * 100)}%`);
      add(i18n.locale === 'he' ? 'תנועה' : 'Movement', `${i18n.num(u.move_budget)} / ${i18n.num(u.move_budget_max)}`);
      add(i18n.locale === 'he' ? 'שטח' : 'Terrain', tile.terrain);
      add(i18n.locale === 'he' ? 'אספקה בשטח' : 'Tile supply', i18n.num(tile.supply, 1));
      body.append(dl);

      const chips = el('div', 'chips');
      for (const r of explain.reasons) {
        const bad = ['explain.isolated', 'explain.routed', 'explain.weakened'].includes(r.key);
        chips.append(el('span', `chip${bad ? ' bad' : r.key === 'explain.short_supply' ? ' warn' : ''}`, i18n.t(r.key)));
      }
      body.append(chips);

      if (mine) {
        body.append(el('div', 'note', i18n.locale === 'he'
          ? `פעולות אפשריות: ${u.allowed_actions.map((a) => a).join(', ')}`
          : `Actions this group can perform: ${u.allowed_actions.join(', ')}`));
        if (this.map.range) {
          const n = this.map.range.tiles.length;
          body.append(el('div', 'note', i18n.locale === 'he'
            ? `${n} אריחים בטווח. הקש על אריח מודגש כדי לראות מסלול ועלות.`
            : `${n} tiles in range. Tap a highlighted tile to preview its route and cost.`));
        }
      }
    }, (foot) => {
      if (!mine) { foot.append(el('div', 'note', i18n.locale === 'he' ? 'כוח של הצד השני.' : 'An opposing formation.')); return; }
      const actions = [];
      if (u.allowed_actions.includes('entrench')) actions.push(['entrench', i18n.locale === 'he' ? 'להתבצר' : 'Entrench']);
      if (u.allowed_actions.includes('defend')) actions.push(['defend', i18n.locale === 'he' ? 'להתגונן' : 'Defend']);
      if (u.allowed_actions.includes('hide')) actions.push(['hide', i18n.locale === 'he' ? 'להסתתר' : 'Lie low']);
      if (u.allowed_actions.includes('reconnoitre')) actions.push(['reconnoitre', i18n.t('mf.recon')]);
      if (u.allowed_actions.includes('sabotage')) actions.push(['sabotage', i18n.t('mf.sabotage')]);
      if (u.allowed_actions.includes('courier')) actions.push(['courier', i18n.t('mf.courier')]);
      const row = el('div', 'btn-row');
      for (const [kind, label] of actions) {
        const b = el('button', 'btn btn-ghost', label);
        b.addEventListener('click', () => this.confirmOrder({ kind, unit_id, tile_id: u.tile_id }));
        row.append(b);
      }
      foot.append(row);
      if (this.map.range?.tiles.length) {
        const pick = el('button', 'btn btn-primary', i18n.t('map.move_here'));
        pick.append(el('span', 'hint', i18n.locale === 'he' ? 'בחר אריח במפה' : 'pick a tile on the map'));
        pick.addEventListener('click', () => { this.closeSheet(); this.toast(i18n.locale === 'he' ? 'הקש על אריח מודגש' : 'Tap a highlighted tile'); });
        foot.append(pick);
      }
    });

  }

  openCitySheet(city_id) {
    const c = this.svc.c;
    const city = c.cities[city_id];
    const tile = c.tiles[city.tile_id];
    this.openSheet(i18n.t(`theater.${city.theater.replace('theater_', '')}`), i18n.t(city.label_key), (body) => {
      const dl = el('dl', 'kv');
      const add = (k, v) => { dl.append(el('dt', null, k), el('dd', null, v)); };
      add(i18n.locale === 'he' ? 'שליטה' : 'Control', city.control);
      add(i18n.t('map.supply'), i18n.num(city.supply_access, 1));
      add(i18n.locale === 'he' ? 'מתקנים' : 'Facilities', `${city.facilities.length} / ${city.facilities_max}`);
      if (city.restriction_level) add(i18n.locale === 'he' ? 'מגבלות' : 'Restrictions', `${city.restriction_level} / 5`);
      body.append(dl);

      for (const gid of city.civilian_group_ids) {
        const g = c.civilian_groups[gid];
        if (!g) continue;
        const wrap = el('div');
        const head = el('div', 'row');
        head.append(el('span', 't', i18n.t(g.label_key)));
        wrap.append(head);
        const needs = el('div');
        for (const [k, v] of Object.entries(g.needs)) {
          const f = el('div', 'field');
          f.append(el('label', null, k), el('span', 'val', `${Math.round(v * 100)}%`));
          const m = el('div', 'meter' + (v < 0.3 ? ' bad' : v > 0.7 ? ' good' : ''));
          const i = el('i'); i.style.width = `${v * 100}%`; m.append(i);
          f.append(m); f.style.gridTemplateColumns = '1fr auto'; m.style.gridColumn = '1 / -1';
          needs.append(f);
        }
        wrap.append(needs);
        wrap.append(el('div', 'note', `${i18n.locale === 'he' ? 'מצב' : 'Status'}: ${g.displacement} · ${g.headcount} ${i18n.locale === 'he' ? 'אנשים' : 'people'}`));
        body.append(wrap);
      }

      for (const nid of city.network_ids) {
        const n = c.networks[nid];
        if (!n) continue;
        const dl2 = el('dl', 'kv');
        dl2.append(el('dt', null, i18n.t(n.label_key)), el('dd', null, ''));
        dl2.append(el('dt', null, i18n.locale === 'he' ? 'גישה' : 'Access'), el('dd', null, `${n.access} / 5`));
        dl2.append(el('dt', null, i18n.locale === 'he' ? 'חשיפה' : 'Exposure'), el('dd', null, `${Math.round(n.exposure * 100)}%`));
        dl2.append(el('dt', null, i18n.locale === 'he' ? 'תאים' : 'Cells'), el('dd', null, `${n.cells.filter((x) => !x.compromised).length} / ${n.cells.length}`));
        body.append(dl2);
      }

      if (city.facilities.length) {
        const list = el('div', 'list');
        for (const f of city.facilities) {
          const r = el('div', 'row');
          r.append(el('span', 't', i18n.t(`facility.${f.facility_id.replace('fac_', '')}`)));
          r.append(el('span', 'badge' + (f.disabled || f.damaged ? '' : ' on'), f.disabled ? (i18n.locale === 'he' ? 'מושבת' : 'disabled') : f.damaged ? (i18n.locale === 'he' ? 'ניזוק' : 'damaged') : (i18n.locale === 'he' ? 'פעיל' : 'working')));
          list.append(r);
        }
        body.append(list);
      }
      if (city.construction_queue.length) {
        const list = el('div', 'list');
        for (const q of city.construction_queue) {
          const r = el('div', 'row');
          r.append(el('span', 't', i18n.t(`facility.${q.facility_id.replace('fac_', '')}`)));
          r.append(el('span', 'badge', `${q.turns_remaining} ${i18n.locale === 'he' ? 'שבועות' : 'weeks'}`));
          list.append(r);
        }
        body.append(list);
      }
    }, (foot) => {
      const b = el('button', 'btn btn-primary', i18n.t('map.build'));
      b.addEventListener('click', () => this.openBuild(city_id));
      foot.append(b);
    });
  }

  openTileSheet(tile_id) {
    const t = this.svc.c.tiles[tile_id];
    this.openSheet(t.terrain, `${t.q}, ${t.r}`, (body) => {
      const dl = el('dl', 'kv');
      const add = (k, v) => { dl.append(el('dt', null, k), el('dd', null, v)); };
      add(i18n.locale === 'he' ? 'שליטה' : 'Control', t.control);
      add(i18n.t('map.supply'), i18n.num(t.supply, 1));
      if (t.supply_penalty) add(i18n.locale === 'he' ? 'נזק לאספקה' : 'Supply damage', `-${t.supply_penalty}`);
      add(i18n.locale === 'he' ? 'עביר' : 'Passable', t.passable ? '✓' : i18n.t('map.impassable_border'));
      const rule = atlas.terrain_rules[t.terrain] || {};
      add(i18n.locale === 'he' ? 'עלות תנועה' : 'Move cost', String(rule.move_cost ?? '—'));
      add(i18n.locale === 'he' ? 'מחסה' : 'Cover', `${Math.round((rule.cover ?? 0) * 100)}%`);
      body.append(dl);
      if (!t.passable) body.append(el('div', 'reason', i18n.t('map.impassable_border')));
    });
  }

  openBuild(city_id) {
    const city = this.svc.c.cities[city_id];
    this.openSheet(i18n.t(city.label_key), i18n.t('map.build'), (body) => {
      const list = el('div', 'list');
      for (const spec of atlas.facility_catalog) {
        const probe = this.svc.previewOrder({ order_id: `probe_${spec.id}`, kind: 'construct', city_id, facility_id: spec.id });
        const r = el('button', `row${probe.ok ? '' : ' is-locked'}`);
        r.append(el('span', 't', i18n.t(spec.label_key)));
        r.append(el('span', 'badge', `${spec.build_turns} ${i18n.locale === 'he' ? 'שב׳' : 'wk'}`));
        const cost = Object.entries(spec.cost).filter(([, v]) => v).map(([k, v]) => `${i18n.t(`map.${k}`)} ${v}`).join(' · ');
        const benefit = Object.entries(spec.benefit).filter(([k]) => !k.startsWith('mission_')).map(([k, v]) => `${k.replace(/_/g, ' ')} ${typeof v === 'number' ? v : ''}`).join(' · ');
        r.append(el('span', 'd', `${cost}${probe.ok ? '' : ` — ${i18n.t(probe.reason)}`}`));
        if (probe.ok) r.append(el('span', 'd', benefit));
        if (probe.ok) r.addEventListener('click', () => this.confirmOrder({ kind: 'construct', city_id, facility_id: spec.id }));
        list.append(r);
      }
      body.append(list);
      body.append(el('div', 'note', i18n.locale === 'he'
        ? 'כל פרויקט דורש תנאים מוקדמים, עלות, זמן ויש לו תועלת גלויה ותגובה לשינוי שליטה או נזק.'
        : 'Every project has prerequisites, a cost, a build time, a visible benefit, and defined behaviour when control changes or it is damaged.'));
    });
  }

  /** The confirmation step with the cost preview the brief requires. */
  confirmOrder(order) {
    const order_id = `ord_${this.svc.c.revision}_${Math.random().toString(36).slice(2, 8)}`;
    const full = { ...order, order_id };
    const preview = this.svc.previewOrder(full);
    this.openSheet(i18n.t('map.confirm_order'), orderTitle(order), (body) => {
      if (!preview.ok) { body.append(el('div', 'reason', `${i18n.t(preview.reason)}${preview.detail ? ` (${preview.detail})` : ''}`)); return; }
      const cost = el('div', 'cost');
      const entries = Object.entries(preview.cost).filter(([, v]) => v);
      if (!entries.length) cost.append(el('span', null, i18n.locale === 'he' ? 'אין עלות במשאבים' : 'No resource cost'));
      for (const [k, v] of entries) cost.append(el('span', 'neg', `${i18n.t(`map.${k}`)} −${v}`));
      body.append(el('div', 'note', i18n.t('map.cost')), cost);
      if (preview.plan.path) {
        body.append(el('div', 'note', `${i18n.t('map.route')}: ${preview.plan.path.length - 1} ${i18n.locale === 'he' ? 'צעדים' : 'steps'} · ${i18n.locale === 'he' ? 'עלות תנועה' : 'move cost'} ${preview.plan.move_cost}`));
        this.map.previewPath(order.tile_id);
      }
      const after = el('dl', 'kv');
      for (const [k, v] of Object.entries(preview.resources_after)) {
        if (!['materiel', 'personnel', 'intelligence'].includes(k)) continue;
        after.append(el('dt', null, i18n.t(`map.${k}`)), el('dd', null, i18n.num(v)));
      }
      body.append(el('div', 'note', i18n.locale === 'he' ? 'אחרי הפקודה' : 'After this order'), after);
    }, (foot) => {
      const row = el('div', 'btn-row');
      const cancel = el('button', 'btn btn-ghost', i18n.t('map.cancel'));
      cancel.addEventListener('click', () => this.closeSheet());
      row.append(cancel);
      if (preview.ok) {
        const go = el('button', 'btn btn-primary', i18n.t('map.confirm_order'));
        go.addEventListener('click', () => {
          const out = this.svc.submitOrder(full);
          if (out.ok) { this.toast(i18n.locale === 'he' ? 'הפקודה נכנסה לתור' : 'Order queued'); this.closeSheet(); this.map.clearSelection(); }
        });
        row.append(go);
      }
      foot.append(row);
    });
  }

  openQueue() {
    this.openSheet(i18n.t('map.turn'), i18n.locale === 'he' ? 'פקודות בתור' : 'Queued orders', (body) => {
      const list = el('div', 'list');
      for (const q of this.svc.c.order_queue) {
        const r = el('div', 'row');
        r.append(el('span', 't', orderTitle(q.order)));
        const x = el('button', 'badge', i18n.t('map.cancel'));
        x.addEventListener('click', () => { this.svc.cancelOrder(q.order_id); this.openQueue(); });
        r.append(x);
        const cost = Object.entries(q.cost).filter(([, v]) => v).map(([k, v]) => `${i18n.t(`map.${k}`)} −${v}`).join(' · ');
        if (cost) r.append(el('span', 'd', cost));
        list.append(r);
      }
      body.append(list.children.length ? list : el('div', 'note', i18n.t('map.no_orders')));
    });
  }

  openTurnReport(report) {
    const t = (k) => i18n.t(k);
    this.openModal(t('map.turn_report'), (body) => {
      body.append(el('div', 'note', `${t('map.turn')} ${report.turn} → ${report.turn + 1} · ${i18n.date(this.svc.c.date)}`));
      const section = (titleText, rows) => {
        if (!rows.length) return;
        body.append(el('div', 'note', titleText));
        const list = el('div', 'list');
        for (const r of rows) { const n = el('div', 'row'); n.append(el('span', 't', r)); list.append(n); }
        body.append(list);
      };
      section(i18n.locale === 'he' ? 'פקודות שנדחו' : 'Rejected orders',
        report.rejected_orders.map((r) => `${t(r.reason)} · ${i18n.locale === 'he' ? 'הוחזר' : 'refunded'} ${Object.entries(r.refunded).filter(([, v]) => v).map(([k, v]) => `${t(`map.${k}`)} ${v}`).join(' ') || '—'}`));
      section(i18n.locale === 'he' ? 'תנועות' : 'Movements',
        report.movements.map((m) => `${t(this.svc.c.units[m.unit_id]?.label_key || 'unit.underground_cell')} → ${m.to.split(':')[1]}`));
      section(i18n.locale === 'he' ? 'קרבות' : 'Engagements',
        report.engagements.map((e) => `${e.tile_id.split(':')[1]} · ${e.kind}${e.ratio ? ` (${e.ratio})` : ''}`));
      section(i18n.locale === 'he' ? 'הצד השני' : 'Opposition',
        report.opposition.map((o) => `${t(this.svc.c.units[o.unit_id]?.label_key || 'unit.infantry_division')} · ${o.decision}${o.reason ? ` (${o.reason})` : ''}`));
      section(i18n.t('map.supply'), report.supply_changes.slice(0, 8).map((s) => `${s.tile_id.split(':')[1]}: ${i18n.num(s.from, 1)} → ${i18n.num(s.to, 1)}`));
      section(i18n.locale === 'he' ? 'בנייה' : 'Construction',
        report.construction.map((c) => `${t(`facility.${c.facility_id.replace('fac_', '')}`)} · ${c.completed ? (i18n.locale === 'he' ? 'הושלם' : 'completed') : c.started ? (i18n.locale === 'he' ? 'החל' : 'started') : c.repaired ? (i18n.locale === 'he' ? 'תוקן' : 'repaired') : c.control_change || ''}`));
      section(i18n.locale === 'he' ? 'אזרחים' : 'Civilians',
        report.civilian.map((c) => `${t(this.svc.c.civilian_groups[c.group_id]?.label_key || 'civgroup.loc_warsaw')} · ${c.change}${c.cause ? ` (${c.cause})` : ''}`));
      section(i18n.locale === 'he' ? 'מחתרת' : 'Network',
        report.network.map((n) => n.event ? `${n.event} · ${n.cell_id ?? ''}` : `${n.action} · ${n.succeeded ? '✓' : '✗'}`));
      section(i18n.locale === 'he' ? 'אירועים' : 'Events',
        report.events.map((e) => `${t(e.label_key)}${e.sensitivity === 'high' ? ' ⚑' : ''}${e.kind === 'chapter_available' ? ` — ${i18n.locale === 'he' ? 'מבצע חדש זמין' : 'new operation available'}` : ''}`));
      if (report.events.some((e) => e.sensitivity === 'high')) body.append(el('div', 'note', `⚑ ${i18n.t('content.sensitive_notice')}`));
    });
  }

  // ------------------------------------------------------------ operations --
  openOperations() {
    const avail = this.svc.availableChapters();
    this.openSheet(i18n.t('mission.briefing'), i18n.locale === 'he' ? 'מבצעים זמינים' : 'Available operations', (body) => {
      const list = el('div', 'list');
      for (const ch of avail) {
        const installed = !!districts[ch.district];
        const playable = ch.status === 'authored' && installed;
        const r = el('button', `row${playable ? '' : ' is-locked'}`);
        r.append(el('span', 't', i18n.t(ch.label_key)));
        r.append(el('span', 'badge' + (playable ? ' on' : ''), playable ? i18n.t('mission.begin') : ch.status));
        r.append(el('span', 'd', `${i18n.t(`district.${ch.district.replace('district_', '')}`)} · ${ch.date_window.from} → ${ch.date_window.to}`));
        if (!installed) r.append(el('span', 'd', i18n.t('error.content_missing')));
        else if (ch.status !== 'authored') r.append(el('span', 'd', i18n.locale === 'he' ? 'התוכן עדיין לא נכתב במלואו' : 'content not fully authored yet'));
        if (playable) r.addEventListener('click', () => this.openBriefing(ch));
        list.append(r);
      }
      body.append(list);
      if (this.notInstalled.size) {
        body.append(el('div', 'note', `${i18n.t('error.content_missing')} — ${[...this.notInstalled].join(', ')}`));
      }
    });
  }

  openBriefing(chapter) {
    this.closeSheet();
    const d = districts[chapter.district];
    const histRefs = chapter.history_refs.map((id) => history.records.find((r) => r.id === id)).filter(Boolean);
    const b = $('#brief-content');
    b.innerHTML = '';
    b.append(el('div', 'kicker', `${i18n.t(`district.${chapter.district.replace('district_', '')}`)} · ${i18n.date(this.svc.c.date)}`));
    b.append(el('h2', null, i18n.t(chapter.label_key)));
    const meta = el('div', 'meta');
    meta.append(el('span', null, `${i18n.locale === 'he' ? 'תפקיד' : 'Role'}: ${chapter.perspective.role.replace(/_/g, ' ')}`));
    meta.append(el('span', null, chapter.mission_families.map((f) => i18n.t(`mf.${f.replace('mission_family_', '')}`)).join(' · ')));
    meta.append(el('span', null, `${d.grid.size_m[0]} × ${d.grid.size_m[1]} m`));
    b.append(meta);

    b.append(el('div', 'note', i18n.t('mission.objectives')));
    const ol = el('div', 'obj-list');
    for (const o of chapter.objectives) {
      const n = el('div', 'obj');
      n.append(el('span', 'mark'), el('span', null, i18n.t(o.label_key)));
      n.append(el('span', 'opt', o.required ? '' : i18n.t('mission.optional')));
      ol.append(n);
    }
    b.append(ol);

    const outcomes = el('div', 'note', `${i18n.locale === 'he' ? 'תוצאות אפשריות' : 'Possible outcomes'}: ${chapter.allowed_outcomes.map((o) => i18n.t(`mission.outcome.${o}`)).join(' · ')}`);
    b.append(outcomes);

    if (histRefs.length) {
      const h = el('div', 'hist');
      for (const r of histRefs) {
        const item = el('div', 'hist-item');
        const top = el('div', 'top');
        top.append(el('span', `k ${r.kind}`, i18n.t(`history.kind.${r.kind}`)));
        top.append(el('span', 'dates', `${r.date_start} → ${r.date_end}`));
        item.append(top);
        item.append(el('h4', null, r.title_key.replace(/^(hist|fict)\./, '').replace(/\.title$/, '').replace(/_/g, ' ')));
        item.append(el('p', null, r.gameplay_use));
        if (r.treatment_note) item.append(el('p', null, r.treatment_note));
        item.append(el('p', null, `${i18n.t('history.confidence')}: ${r.confidence} · ${r.sources.length ? r.sources.join('; ') : i18n.t('history.sources_pending')}`));
        h.append(item);
      }
      b.append(h);
    }
    b.append(el('div', 'fiction', `${i18n.t('mission.fiction_notice')} ${chapter.editorial_note || ''}`));

    const foot = $('#brief-actions');
    foot.innerHTML = '';
    const back = el('button', 'btn btn-ghost', i18n.t('map.cancel'));
    back.addEventListener('click', () => this.show('map'));
    const go = el('button', 'btn btn-primary', i18n.t('mission.begin'));
    go.addEventListener('click', () => this.beginOperation(chapter));
    foot.append(back, go);
    this.show('brief');
  }

  async beginOperation(chapter) {
    if (this.engineFailed) { this.toast(i18n.locale === 'he' ? 'אין רינדור תלת-ממד בדפדפן הזה' : 'No 3D renderer available in this browser', true); return; }
    const unit = Object.values(this.svc.c.units).find((u) => u.faction === this.svc.c.player_faction && this.svc.c.tiles[u.tile_id]?.city_id === chapter.location)
      || Object.values(this.svc.c.units).find((u) => u.faction === this.svc.c.player_faction);
    const tile_id = this.svc.c.cities[chapter.location]?.tile_id || unit?.tile_id;
    const nonce = `${Date.now()}`;
    const loadout = chapter.mission_families.includes('mission_family_sabotage')
      ? ['tool_wire_cutters', 'wpn_pistol_civ']
      : ['wpn_pistol_civ', 'tool_medical_kit'];
    const out = this.svc.enterMission({ chapter_id: chapter.id, district_id: chapter.district, tile_id, unit_id: unit?.unit_id ?? null, loadout }, nonce);
    if (!out.ok) { this.toast(`${i18n.t('error.transition_failed')} (${out.code})`, true); this.show('map'); return; }
    await this.enterMissionScene(out.context, null, chapter);
  }

  async enterMissionScene(context, checkpoint, chapterIn) {
    const chapter = chapterIn || chapters.chapters.find((c) => c.id === context.chapter_id);
    const d = districts[context.district_id];
    this.show('load');
    const bar = $('#load-bar > i');
    const what = $('#load-what');
    $('#load-title').textContent = i18n.t(chapter?.label_key || 'mission.loading');
    const stage = (p, text) => { bar.style.width = `${Math.round(p * 100)}%`; what.textContent = text; };
    // Visible feedback within half a second, as the performance table requires.
    stage(0.05, i18n.t('mission.loading'));
    await frame(); await frame();

    if (!d) { this.svc.abortMission('content_missing', context.district_id); this.toast(i18n.t('error.content_missing'), true); this.show('map'); return; }
    this.svc.markLoading();

    try {
      stage(0.2, i18n.locale === 'he' ? 'בונה את השטח' : 'Building the ground');
      await frame();
      this.mission = new MissionScene(this.three, {
        canvas: $('#mission-canvas'), district: d, context, chapter, weapons,
        settings: this.settings, i18n, onStateChange: (k, v) => this.onMissionEvent(k, v),
      });
      stage(0.65, i18n.locale === 'he' ? 'מציב סיורים ותושבים' : 'Placing patrols and residents');
      await frame();
      if (!this.input) {
        this.input = new DesktopInput(this.settings, i18n, { surface: $('#mission-canvas') });
        this.input.onPointerLockChange = (locked) => {
          $('#capture-hint').hidden = locked;
          if (!locked && this.mission && !this.mission.finished && !this.mission.paused) {
            // Losing the cursor is the PC equivalent of losing focus: pause and
            // checkpoint rather than letting the player's hands leave the game.
            this.onInterrupted('pointer_unlock');
          }
        };
      }
      // Touch still works through the same snapshot shape, for a touchscreen
      // laptop or a Steam Deck, but nothing requires it.
      if (!this.touch && matchMedia('(pointer: coarse)').matches) {
        this.touch = new TouchControls($('#touch'), this.settings, i18n);
      }
      this.mission.markUiReady();
      stage(0.9, i18n.locale === 'he' ? 'מאמת מוכנות' : 'Verifying readiness');
      await frame();
      const ready = this.svc.markReady(this.mission.ready);
      if (!ready.ok) {
        this.toast(`${i18n.t('error.transition_failed')} — ${ready.detail}`, true);
        this.svc.abortMission(ready.code, ready.detail);
        this.mission.dispose(); this.mission = null;
        this.show('map'); return;
      }
      if (checkpoint) this.mission.restore(checkpoint);
      stage(1, i18n.t('mission.ready'));
      await frame();
      this.svc.markPlaying();
      this.show('mission');
      this.mission.resize();
      this.startLoop();
      this.checkpointTimer = setInterval(() => {
        if (this.mission && !this.mission.finished && !this.mission.paused) {
          try { this.svc.checkpointDistrict(this.mission.checkpoint()); } catch (e) { this.onSaveError(e); }
        }
      }, 20000);
    } catch (e) {
      console.error(e);
      this.svc.abortMission('load_exception', String(e.message).slice(0, 120));
      this.toast(i18n.t('error.transition_failed'), true);
      this.show('map');
    }
  }

  onMissionEvent(kind, data) {
    if (kind === 'objective') this.toast(`✓ ${data.label}`);
    if (kind === 'hit_marker') { const m = $('#hitmark'); m.classList.remove('show'); void m.offsetWidth; m.classList.add('show'); }
    if (kind === 'player_hit') {
      const v = $('#vignette'); v.classList.add('hit'); setTimeout(() => v.classList.remove('hit'), 260);
      // Gamepad rumble, not phone vibration. `vibrationActuator` is not
      // universally supported, so a missing one is simply no rumble.
      const strength = this.settings.get('rumble');
      const pad = this.input?.pad?.();
      if (strength > 0 && pad?.vibrationActuator) {
        try {
          pad.vibrationActuator.playEffect('dual-rumble', {
            duration: 180, weakMagnitude: 0.35 * strength, strongMagnitude: 0.7 * strength,
          });
        } catch { /* unsupported actuator type */ }
      }
    }
    if (kind === 'resolved') this.finishMission(data);
  }

  startLoop() {
    cancelAnimationFrame(this.raf);
    let last = performance.now();
    const target = this.settings.rendererOptions().frameTarget;
    const minDt = 1 / (target + 6);
    let acc = 0;
    const tick = (now) => {
      this.raf = requestAnimationFrame(tick);
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      if (!this.mission) return;
      acc += dt;
      if (target === 30 && acc < minDt) return;
      const step = acc; acc = 0;
      const input = this.input.sample(step);
      // A mission only advances while the mouse is captured. Otherwise the
      // player is looking at the pause screen or has alt-tabbed away.
      if (input.locked || this.mission.paused) {
        this.mission.update(step, input);
      }
      this.mission.render();
      this.renderHud(input);
      if (input.pressed.has('pause')) this.onInterrupted('pause');
      if (input.pressed.has('quick_save') && this.mission && !this.mission.finished) {
        try { this.svc.checkpointDistrict(this.mission.checkpoint()); this.toast(i18n.t('input.quick_save')); }
        catch (e) { this.onSaveError(e); }
      }
    };
    this.raf = requestAnimationFrame(tick);
  }

  renderHud(input) {
    const h = this.mission.hudState();
    const t = (k) => i18n.t(k);

    const oc = $('#hud-objectives');
    oc.innerHTML = '';
    oc.append(el('div', 'h', t('hud.objective')));
    for (const o of h.objectives) {
      const n = el('div', `o${o.done ? ' done' : o.failed ? ' failed' : ''}`);
      n.append(el('span', 'm'), el('span', null, `${o.label}${o.required ? '' : ` (${t('mission.optional')})`}`));
      oc.append(n);
    }

    const st = $('#hud-stealth');
    st.innerHTML = '';
    for (const key of ['visibility', 'noise', 'awareness']) {
      const s = h.stealth[key];
      const n = el('div', 's');
      n.dataset.band = s.band;
      n.append(el('span', null, t(s.label_key)));
      const bar = el('div', 'bar2'); const i = el('i'); i.style.width = `${s.value * 100}%`; bar.append(i);
      n.append(bar);
      st.append(n);
    }

    const am = $('#hud-ammo');
    am.innerHTML = '';
    if (h.weapon) {
      if (h.weapon.isTool) { am.append(el('b', null, '—')); am.append(el('span', 'w', t(h.weapon.label_key))); }
      else {
        am.append(el('b', null, String(h.weapon.loaded)));
        am.append(el('span', null, ` / ${h.weapon.reserve}`));
        am.append(el('span', 'w', t(h.weapon.label_key)));
      }
    } else am.append(el('span', 'w', t('hud.no_weapon')));

    $('#hud-cond-bar').style.width = `${h.health}%`;
    $('#hud-cond-bar').parentElement.className = `meter${h.health < 35 ? ' bad' : h.health > 70 ? ' good' : ''}`;
    $('#hud-stam-bar').style.width = `${h.stamina * 100}%`;

    // The touch layer is optional on PC, so every call into it is guarded.
    if (this.touch) {
      this.touch.setReloadProgress(h.weapon?.reloading ? h.weapon.reloadProgress : 0);
      this.touch.setContext(h.interact?.label_key ?? null, h.interact?.progress ?? 0);
      this.touch.setAvailable({ fire: !!h.weapon && !h.weapon.isTool, aim: !!h.weapon && !h.weapon.isTool, reload: !!h.weapon && !h.weapon.isTool, interact: !!h.interact, traverse: false });
    }

    // Posture, lean and breath: PC verbs the touch build had no room for.
    const stateRow = $('#hud-state');
    stateRow.innerHTML = '';
    if (h.posture !== 'stand') stateRow.append(el('span', 'tag', t(h.posture === 'prone' ? 'hud.prone' : 'hud.crouch')));
    if (Math.abs(h.lean ?? 0) > 0.1) stateRow.append(el('span', 'tag', `${t('hud.lean')} ${h.lean < 0 ? '◀' : '▶'}`));
    if ((h.breath ?? 1) < 0.999) {
      const b = el('span', `tag${h.holdingBreath ? ' on' : ''}`);
      b.append(document.createTextNode(`${t('hud.breath')} `));
      const bar = el('span', 'tagbar');
      const i = el('i'); i.style.width = `${(h.breath ?? 1) * 100}%`; bar.append(i);
      b.append(bar);
      stateRow.append(b);
    }

    // The interaction prompt names the actual key, read from the live bindings,
    // so it stays correct after the player rebinds.
    const ip = $('#hud-interact');
    if (h.interact) {
      ip.hidden = false;
      ip.innerHTML = '';
      ip.append(el('kbd', null, this.input.bindingText('interact')), el('span', null, t(h.interact.label_key)));
      const prog = el('i', 'ip-prog');
      prog.style.width = `${(h.interact.progress ?? 0) * 100}%`;
      ip.append(prog);
    } else ip.hidden = true;

    const sub = $('#hud-sub');
    sub.innerHTML = '';
    for (const s of h.subtitles) {
      const n = el('div');
      const line = el('span', 'subline');
      if (s.speaker) line.append(el('b', null, s.speaker));
      line.append(document.createTextNode(s.text));
      n.append(line);
      sub.append(n);
    }
    for (const c of h.captions) sub.append(el('div', 'caption', `⟨ ${c.direction} · ${Math.round(c.dist)} m ⟩`));

    const prompt = $('#hud-prompt');
    prompt.textContent = h.observeProgress > 0.02 && h.observeProgress < 1
      ? `${t('obj.mark_battery')} — ${Math.round(h.observeProgress * 100)}%`
      : h.extractionBlocked ? (i18n.locale === 'he' ? 'עוד יש מטרות חובה' : 'Required objectives are not complete') : '';
    $('#reticle').style.opacity = h.weapon && !h.weapon.isTool ? String(0.35 + (h.weapon.ads ?? 0) * 0.6) : '0';
  }

  openPause() {
    this.openModal(i18n.t('hud.pause'), (body) => {
      body.append(el('div', 'note', i18n.locale === 'he' ? 'המבצע מושהה. ההתקדמות נשמרה בגבול פעולה בטוח.' : 'The operation is paused. Progress was saved at a safe action boundary.'));
      const list = el('div', 'list');
      const resume = el('button', 'row'); resume.append(el('span', 't', i18n.t('menu.continue')));
      resume.addEventListener('click', async () => {
        this.closeModal();
        // Pointer lock needs a user gesture, so it is requested from the click
        // that resumes rather than silently on a timer.
        const ok = await this.input?.capture();
        if (!ok) this.toast(i18n.t('error.pointer_lock'), true);
        if (this.mission) this.mission.paused = false;
      });
      const settings = el('button', 'row'); settings.append(el('span', 't', i18n.t('menu.settings')));
      settings.addEventListener('click', () => this.openSettings());
      const withdraw = el('button', 'row'); withdraw.append(el('span', 't', i18n.t('mission.withdraw')));
      withdraw.addEventListener('click', () => { this.closeModal(); this.mission?.withdraw(); });
      list.append(resume, settings, withdraw);
      body.append(list);
    });
  }

  finishMission(result) {
    clearInterval(this.checkpointTimer);
    cancelAnimationFrame(this.raf);
    const out = this.svc.finishMission(result);
    const applied = out.applied;
    if (this.mission) { this.mission.dispose(); this.mission = null; }
    this.showResultScreen(applied, result, out.duplicate);
    this.renderTopbar(); this.renderMapbar(); this.map?.draw();
  }

  showResultScreen(applied, result, duplicate) {
    const b = $('#result-content');
    b.innerHTML = '';
    const outcome = applied?.outcome || result?.outcome || 'failure';
    b.append(el('div', 'kicker', i18n.t('mission.result')));
    const h = el('div', 'outcome', i18n.t(`mission.outcome.${outcome}`));
    h.dataset.o = outcome;
    b.append(h);
    if (duplicate) b.append(el('div', 'ok-box', i18n.locale === 'he' ? 'התוצאה הזאת כבר יושמה. לא שולם פעמיים.' : 'This result was already applied. Nothing was paid twice.'));

    if (result) {
      const objs = el('div', 'obj-list');
      for (const id of result.completed_objectives) { const n = el('div', 'obj done'); n.append(el('span', 'mark'), el('span', null, i18n.t(`obj.${id.replace('obj_', '')}`))); objs.append(n); }
      for (const id of result.failed_objectives) { const n = el('div', 'obj failed'); n.append(el('span', 'mark'), el('span', null, i18n.t(`obj.${id.replace('obj_', '')}`))); objs.append(n); }
      b.append(objs);
      const m = result.metrics;
      b.append(el('div', 'metrics',
        `${Math.floor(m.elapsed_mission_seconds / 60)}m ${m.elapsed_mission_seconds % 60}s · ` +
        `${i18n.locale === 'he' ? 'יריות' : 'shots'} ${m.shots_fired} · ` +
        `${i18n.locale === 'he' ? 'זוהית' : 'detected'} ${m.times_detected} · ` +
        `${i18n.locale === 'he' ? 'אזעקה' : 'alarm'} ${m.alarm_raised ? '✓' : '—'}`));
    }

    b.append(el('div', 'note', i18n.t('mission.what_changed')));
    const ch = el('div', 'changes');
    for (const c of applied?.changes || []) {
      const n = el('div', 'change');
      n.append(el('span', null, changeIcon(c.what)));
      n.append(el('span', null, describeChange(c)));
      const v = c.delta != null ? i18n.delta(c.delta) : (c.value != null ? String(c.value) : '');
      const vn = el('span', `v${c.delta > 0 ? ' pos' : c.delta < 0 ? ' neg' : ''}`, v);
      n.append(vn);
      ch.append(n);
    }
    if (!(applied?.changes || []).length) ch.append(el('div', 'note', i18n.locale === 'he' ? 'שום דבר במערכה לא השתנה.' : 'Nothing in the campaign changed.'));
    b.append(ch);

    const foot = $('#result-actions');
    foot.innerHTML = '';
    const back = el('button', 'btn btn-primary', i18n.locale === 'he' ? 'חזרה למפה' : 'Return to the map');
    back.addEventListener('click', () => { this.show('map'); this.renderTopbar(); this.renderMapbar(); this.map?.draw(); });
    foot.append(back);
    this.show('result');
  }

  // ---------------------------------------------------------------- modals --
  openModal(title, bodyFn, footFn) {
    $('#modal-title').textContent = title;
    const body = $('#modal-body'); body.innerHTML = '';
    const foot = $('#modal-foot'); foot.innerHTML = '';
    bodyFn?.(body);
    if (footFn) footFn(foot);
    else { const b = el('button', 'btn', i18n.locale === 'he' ? 'סגור' : 'Close'); b.addEventListener('click', () => this.closeModal()); foot.append(b); }
    $('#modal').classList.add('is-open');
  }
  closeModal() { $('#modal').classList.remove('is-open'); }

  openSettings() {
    this.openModal(i18n.t('menu.settings'), (body) => {
      const tabs = el('div', 'tabs');
      const pane = el('div');
      const groups = this.settings.groups();
      const paint = (g) => {
        pane.innerHTML = '';
        for (const spec of this.settings.inGroup(g)) {
          const f = el('div', 'field');
          f.append(el('label', null, i18n.t(spec.label)));
          const v = this.settings.get(spec.id);
          if (spec.type === 'bool') {
            const sw = el('button', 'switch');
            sw.setAttribute('aria-pressed', String(!!v));
            sw.addEventListener('click', () => { this.settings.set(spec.id, !this.settings.get(spec.id)); sw.setAttribute('aria-pressed', String(!!this.settings.get(spec.id))); });
            f.append(sw);
          } else if (spec.type === 'enum') {
            const seg = el('div', 'seg');
            for (const opt of spec.values) {
              const b = el('button', null, spec.id === 'language' ? (i18n.available.find((a) => a.code === opt)?.name ?? opt) : opt);
              b.setAttribute('aria-pressed', String(String(v) === String(opt)));
              b.addEventListener('click', () => { this.settings.set(spec.id, opt); paint(g); });
              seg.append(b);
            }
            f.append(seg);
          } else {
            const val = el('span', 'val', Number(v).toFixed(2));
            const r = el('input');
            r.type = 'range'; r.min = spec.min; r.max = spec.max; r.step = spec.step; r.value = v;
            r.addEventListener('input', () => { this.settings.set(spec.id, r.value); val.textContent = Number(this.settings.get(spec.id)).toFixed(2); });
            f.append(val, r);
          }
          pane.append(f);
        }
        if (g === 'content') pane.append(el('div', 'note', i18n.t('content.sensitive_notice')));
        if (g === 'audio') pane.append(el('div', 'note', i18n.locale === 'he'
          ? 'כל פס קול משפיע רק על עצמו. במצב מונו, רמזים חיוניים מוצגים ככתובית כיוון.'
          : 'Each bus affects only its own output. In mono, essential directional cues appear as a caption instead.'));
      };
      // A synthetic tab: rebinding is not a list of settings, it is a list of
      // actions, so it renders itself rather than going through the schema.
      const allTabs = [...groups, 'controls'];
      for (const g of allTabs) {
        const b = el('button', null, g === 'controls' ? i18n.t('settings.rebind') : g);
        b.setAttribute('aria-selected', String(g === allTabs[0]));
        b.addEventListener('click', () => {
          for (const x of $$('button', tabs)) x.setAttribute('aria-selected', 'false');
          b.setAttribute('aria-selected', 'true');
          if (g === 'controls') this.paintBindings(pane); else paint(g);
        });
        tabs.append(b);
      }
      body.append(tabs, pane);
      paint(allTabs[0]);
    });
  }

  /** The rebinding screen. Grouped by context, with conflicts surfaced. */
  paintBindings(pane) {
    pane.innerHTML = '';
    if (!this.input) {
      pane.append(el('div', 'note', i18n.locale === 'he'
        ? 'המקשים נטענים כשמתחיל מבצע.'
        : 'Controls load when an operation starts.'));
      return;
    }
    const byContext = {};
    for (const [action, b] of Object.entries(this.input.bindings)) {
      (byContext[b.context] ??= []).push(action);
    }
    for (const [context, actions] of Object.entries(byContext)) {
      pane.append(el('div', 'note', context));
      for (const action of actions) {
        const row = el('div', 'bind-row');
        row.append(el('span', 'name', i18n.t(this.input.bindings[action].label)));
        const key = el('button', 'key', this.input.bindingText(action));
        let pending = null;
        key.addEventListener('click', () => {
          key.classList.add('is-listening');
          key.textContent = i18n.t('settings.press_a_key');
          const onKey = (e) => {
            e.preventDefault();
            e.stopPropagation();
            cleanup();
            // A clash is shown, not silently resolved. Pressing the same key
            // again confirms taking it from the other action.
            const out = this.input.rebind(action, e.code, { allowConflict: pending === e.code });
            if (!out.ok && out.reason === 'conflict') {
              pending = e.code;
              key.classList.add('is-conflict');
              key.textContent = i18n.t('settings.binding_conflict', {
                other: i18n.t(this.input.bindings[out.conflicts[0]].label),
              });
              return;
            }
            pending = null;
            this.paintBindings(pane);
          };
          const cleanup = () => {
            key.classList.remove('is-listening');
            removeEventListener('keydown', onKey, true);
          };
          addEventListener('keydown', onKey, true);
        });
        row.append(key);
        const reset = el('button', 'reset', '↺');
        reset.title = i18n.t('settings.reset_bindings');
        reset.addEventListener('click', () => {
          this.input.bindings[action] = structuredClone(DEFAULT_BINDINGS[action]);
          this.input.saveOverrides();
          this.paintBindings(pane);
        });
        row.append(reset);
        pane.append(row);
      }
    }
    const resetAll = el('button', 'btn btn-ghost', i18n.t('settings.reset_bindings'));
    resetAll.addEventListener('click', () => { this.input.resetBindings(); this.paintBindings(pane); });
    pane.append(resetAll);
  }

  openHistory() {
    this.openModal(i18n.t('history.panel_title'), (body) => {
      body.append(el('div', 'note', i18n.locale === 'he'
        ? 'מתועד, שחזור מנומק ובדיה מופרדים. ציטוטים ממתינים לבדיקת מומחה — אין כאן מקור מומצא.'
        : 'Documented fact, reasoned reconstruction and fiction are kept apart. Citations are pending specialist review; no source here is invented.'));
      const h = el('div', 'hist');
      for (const r of history.records) {
        const item = el('div', 'hist-item');
        const top = el('div', 'top');
        top.append(el('span', `k ${r.kind}`, i18n.t(`history.kind.${r.kind}`)));
        top.append(el('span', 'dates', `${r.date_start} → ${r.date_end}`));
        if (r.sensitivity === 'high') top.append(el('span', 'chip warn', i18n.locale === 'he' ? 'רגיש' : 'sensitive'));
        item.append(top);
        item.append(el('h4', null, r.title_key.replace(/^(hist|fict)\./, '').replace(/\.title$/, '').replace(/_/g, ' ')));
        item.append(el('p', null, r.gameplay_use));
        if (r.treatment_note) item.append(el('p', null, r.treatment_note));
        item.append(el('p', null, `${i18n.t('history.confidence')}: ${r.confidence} · ${r.sources.length ? r.sources.join('; ') : i18n.t('history.sources_pending')}`));
        h.append(item);
      }
      body.append(h);
    });
  }
}

function orderTitle(order) {
  const map = {
    move: 'map.move_here', move_covert: 'map.move_here', attack: 'map.attack_here',
    construct: 'map.build', repair: 'map.build', entrench: 'explain.entrenched',
    reconnoitre: 'mf.recon', sabotage: 'mf.sabotage', courier: 'mf.courier',
    defend: 'mf.defence', hide: 'mf.concealment', relieve: 'mf.medical', evacuate: 'mf.evacuation',
  };
  return i18n.t(map[order.kind] || 'map.inspect');
}
function changeIcon(what) {
  return { resource: '◆', tile_control: '▣', formation_removed: '✕', enemy_readiness: '▾',
    chapter_completed: '✓', chapter_unlocked: '＋', network_exposure: '◉', network_access: '◎',
    civilian_needs: '♁', campaign_time: '⏱', tile_supply_penalty: '⚡' }[what] || '·';
}
function describeChange(c) {
  const L = i18n.locale === 'he';
  switch (c.what) {
    case 'resource': return i18n.t(`map.${c.key}`) + (c.from === 'chapter_effect' ? (L ? ' (מהמבצע)' : ' (from the operation)') : '');
    case 'tile_control': return (L ? 'שליטה באריח' : 'Tile control') + ` → ${c.to}`;
    case 'formation_removed': return (L ? 'כוח הוסר מהמפה' : 'Formation removed from the map') + `: ${i18n.t(c.label_key || 'unit.infantry_division')}`;
    case 'enemy_readiness': return L ? 'כשירות האויב' : 'Enemy readiness';
    case 'chapter_completed': return (L ? 'פרק הושלם' : 'Chapter completed') + `: ${i18n.t(`chapter.${c.chapter_id.replace('chapter_', '')}.title`)}`;
    case 'chapter_unlocked': return (L ? 'פרק נפתח' : 'Chapter unlocked') + `: ${i18n.t(`chapter.${c.chapter_id.replace('chapter_', '')}.title`)}`;
    case 'network_exposure': return L ? 'חשיפת הרשת' : 'Network exposure';
    case 'network_access': return L ? 'גישת הרשת' : 'Network access';
    case 'civilian_needs': return L ? 'צרכים של הקהילה' : 'Community needs';
    case 'campaign_time': return (L ? 'זמן המערכה' : 'Campaign time') + ` → ${c.date}`;
    case 'tile_supply_penalty': return L ? 'אספקה באריח נפגעה' : 'Tile supply damaged';
    default: return c.what;
  }
}
const frame = () => new Promise((r) => requestAnimationFrame(() => r()));

const app = new App();
window.__wbtm = app;
app.boot();
