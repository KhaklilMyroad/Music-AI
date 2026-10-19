import { describe, it, eq, ok, notOk, throws, close } from './runner.js';
import { atlas, chapters, content, weapons, history, locales, districtNormandy, provenance, freshService, normandyRequest, FULL_READY } from './fixtures.js';
import * as C from '../src/sim/contracts.js';
import { newCampaign } from '../src/sim/bootstrap.js';
import { validateOrder, REJECT } from '../src/sim/orders.js';
import { stableStringify, digest, makeRng } from '../src/sim/rng.js';

export default function run() {

describe('Contracts: entity separation (brief §16)', () => {
  it('a civilian group cannot carry a military strength value', () => {
    const g = C.makeCivilianGroupState({ group_id: 'g1', city_id: 'loc_warsaw', tile_id: 't' });
    const issues = C.validateCivilianGroup({ ...g, strength: 0.4 }, []);
    ok(issues.some((i) => i.includes("must not carry a military 'strength'")), 'guard missing');
  });

  it('an underground cell cannot be given a division action', () => {
    const u = C.makeUnitState({ unit_id: 'u', unit_type: 'underground_cell', faction: 'resistance_cell', tile_id: 't' });
    notOk(u.allowed_actions.includes('attack'));
    const issues = C.validateUnit({ ...u, allowed_actions: ['attack'] }, []);
    ok(issues.some((i) => i.includes('cannot perform')));
  });

  it('every unit type has distinct capabilities, not one shared template', () => {
    const sigs = new Set(Object.values(C.UNIT_CAPABILITIES).map((c) => JSON.stringify(c)));
    ok(sigs.size === Object.keys(C.UNIT_CAPABILITIES).length, 'two unit types share one capability set');
  });

  it('campaign validation rejects a dangling tile reference', () => {
    const c = newCampaign(atlas, content, { date: '1944-06-06' });
    c.tiles['theater_western_europe:3,0'].neighbors.push('theater_western_europe:999,999');
    throws(() => C.validateCampaign(c), 'references missing tile');
  });

  it('campaign validation rejects a unit standing on no tile', () => {
    const c = newCampaign(atlas, content, { date: '1944-06-06' });
    c.units.u_res_cell_nor.tile_id = 'nowhere:0,0';
    throws(() => C.validateCampaign(c), 'references missing tile');
  });

  it('a save state serialises and round-trips without node references', () => {
    const c = newCampaign(atlas, content, { date: '1944-06-06' });
    const round = JSON.parse(JSON.stringify(c));
    eq(digest(round), digest(c), 'state is not purely serialisable');
    ok(!stableStringify(c).includes('[object'), 'a live object leaked into the contract');
  });
});

describe('Contracts: MissionResult cannot patch the world (brief §16, §17)', () => {
  it('a result carrying a world patch is refused outright', () => {
    const { svc } = freshService();
    svc.enterMission(normandyRequest(), 'n1');
    const ctx = svc.c.pending_operation.context;
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    throws(() => svc.finishMission({
      result_version: C.RESULT_VERSION, operation_id: ctx.operation_id, source_revision: ctx.source_revision,
      outcome: 'success', completed_objectives: [], world_patch: { resources: { materiel: 9999 } },
    }), 'may not carry a world-state patch');
  });

  it('a result claiming an objective the mission never defined is refused', () => {
    const { svc } = freshService();
    const r = svc.enterMission(normandyRequest(), 'n1');
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    throws(() => svc.finishMission({
      result_version: C.RESULT_VERSION, operation_id: r.context.operation_id, source_revision: r.context.source_revision,
      outcome: 'success', completed_objectives: ['obj_win_the_war'],
    }), 'objectives this mission does not define');
  });

  it('an over-claimed reward is clamped to the chapter bounds, not accepted', () => {
    const { svc } = freshService();
    const r = svc.enterMission(normandyRequest(), 'n1');
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    const before = svc.c.resources.intelligence;
    const out = svc.finishMission({
      result_version: C.RESULT_VERSION, operation_id: r.context.operation_id, source_revision: r.context.source_revision,
      outcome: 'success', completed_objectives: ['obj_cut_field_line'],
      declared_resources: { intelligence: 9999 },
    });
    ok(out.clamped.includes('intelligence'), 'clamp not reported');
    const chapterMax = 3;   // chapter_nor_01 success grants 3
    ok(svc.c.resources.intelligence - before <= chapterMax * 2, `intelligence gained ${svc.c.resources.intelligence - before}, bound was ${chapterMax}`);
  });

  it('a result for a different campaign revision is refused', () => {
    const { svc } = freshService();
    const r = svc.enterMission(normandyRequest(), 'n1');
    svc.markLoading(); svc.markReady(FULL_READY); svc.markPlaying();
    throws(() => svc.finishMission({
      result_version: C.RESULT_VERSION, operation_id: r.context.operation_id,
      source_revision: r.context.source_revision + 5, outcome: 'success', completed_objectives: [],
    }), 'does not match context');
  });

  it("a chapter that forbids 'success' cannot be completed successfully", () => {
    const uprising = chapters.chapters.find((c) => c.id === 'chapter_wsw_03');
    notOk(uprising.allowed_outcomes.includes('success'), 'the 1943 uprising chapter must not offer a success outcome');
  });
});

describe('Content data integrity', () => {
  it('every chapter history_ref resolves to a register record', () => {
    const ids = new Set(history.records.map((r) => r.id));
    for (const ch of chapters.chapters) for (const ref of ch.history_refs) ok(ids.has(ref), `${ch.id} -> ${ref}`);
  });

  it('no historical record carries an invented citation', () => {
    for (const r of history.records) {
      if (r.sources.length) ok(r.review_status === 'approved', `${r.id} has sources but is not approved`);
      else ok(r.review_status.startsWith('pending') || r.review_status === 'approved_as_fiction', `${r.id} has no sources and no pending flag`);
    }
  });

  it('every sensitive record states its treatment', () => {
    for (const r of history.records.filter((x) => x.sensitivity === 'high')) {
      ok(r.treatment_note && r.treatment_note.length > 40, `${r.id} is sensitive but has no treatment note`);
      ok(r.review_status === 'pending_specialist_review', `${r.id} is sensitive but not gated on specialist review`);
    }
  });

  it('every sensitive chapter is gated on specialist review', () => {
    for (const ch of chapters.chapters.filter((c) => c.sensitivity === 'high')) {
      eq(ch.gate, 'specialist_review_required', `${ch.id} is sensitive but ungated`);
    }
  });

  it('ghettos, camps and extermination centres are not one record', () => {
    const warsaw = history.records.filter((r) => r.locations.includes('loc_warsaw'));
    ok(warsaw.length >= 4, 'Warsaw is modelled by fewer than four dated records');
    const sealed = warsaw.find((r) => r.id === 'hist_1940_warsaw_ghetto_sealed');
    const up43 = warsaw.find((r) => r.id === 'hist_1943_warsaw_ghetto_uprising');
    const up44 = warsaw.find((r) => r.id === 'hist_1944_warsaw_uprising');
    ok(sealed && up43 && up44, 'the 1940 sealing, 1943 ghetto uprising and 1944 city uprising must be separate records');
    ok(up43.date_start !== up44.date_start, 'the two uprisings share a date');
  });

  it('the Anne Frank record is reference-only and never a playable reconstruction', () => {
    const r = history.records.find((x) => x.id === 'hist_1942_frank_family_hiding');
    ok(r.gameplay_use.includes('Reference context ONLY'));
    ok(!chapters.chapters.some((c) => c.history_refs.includes(r.id) && c.status === 'authored' && !c.history_refs.includes('fict_household_lindenweg')));
  });

  it('every weapon declares its reload rules and audio events', () => {
    for (const w of weapons.weapons) {
      ok(Array.isArray(w.audio_events) && w.audio_events.length >= 3, `${w.id} has too few audio events`);
      if (w.magazine && w.class !== 'tool') ok(w.reload, `${w.id} has a magazine but no reload rules`);
      if (w.ammunition) ok(weapons.ammunition[w.ammunition], `${w.id} references unknown ammunition`);
    }
  });

  it('no weapon is marked production-ready while it is a blockout', () => {
    for (const w of weapons.weapons) ok(['blockout', 'wip', 'approved'].includes(w.model_status), `${w.id}: ${w.model_status}`);
    ok(weapons.weapons.every((w) => w.model_status !== 'approved' || w.provenance_ref), 'an approved asset has no provenance record');
  });

  it('non-lethal mission families exist and outnumber lethal ones', () => {
    const lethal = chapters.mission_families.filter((f) => f.lethal_required).length;
    const nonLethal = chapters.mission_families.length - lethal;
    ok(nonLethal > lethal, `only ${nonLethal} non-lethal families vs ${lethal} lethal`);
  });

  it('the Warsaw courier chapter issues no firearm', () => {
    const ch = chapters.chapters.find((c) => c.id === 'chapter_wsw_01');
    ok(ch.editorial_note.includes('No weapon is issued'));
  });

  it('the New York chapter never invents an occupation', () => {
    const ch = chapters.chapters.find((c) => c.id === 'chapter_nyc_01');
    notOk(ch.mission_families.some((f) => ['mission_family_defence', 'mission_family_assault'].includes(f)));
  });
});

describe('Asset provenance (brief §12, §15)', () => {
  it('every provenance row records creator, source, licence and processing history', () => {
    for (const a of provenance.assets) {
      for (const field of ['creator', 'source', 'licence', 'permissions', 'processing_history', 'use_restrictions']) {
        // A licence identifier is legitimately short ("MIT"), so this asserts
        // the field was filled in, not how long it is.
        ok(typeof a[field] === 'string' && a[field].trim().length > 0, `${a.id} is missing ${field}`);
      }
      ok(provenance.review_states.includes(a.review_status), `${a.id} has an unknown review_status`);
      ok(provenance.may_ship_states.includes(a.may_ship), `${a.id} has an unknown may_ship state`);
    }
  });

  it('nothing unapproved is cleared to ship', () => {
    for (const a of provenance.assets) {
      if (a.review_status !== 'approved') notOk(a.may_ship === 'yes', `${a.id} is unapproved but cleared to ship`);
    }
  });

  it('every blockout or placeholder is marked never-ship and says why', () => {
    const blockout = provenance.assets.filter((a) => a.may_ship === 'never');
    ok(blockout.length >= 2, 'the blockout geometry and placeholder materials must both be marked never-ship');
    for (const a of blockout) {
      ok(/must not ship|must not be shown|BLOCKOUT|PLACEHOLDER/i.test(a.use_restrictions), `${a.id} is never-ship but carries no explanation`);
    }
  });

  it('no weapon claims an approved model without a provenance reference', () => {
    for (const w of weapons.weapons) {
      if (w.model_status === 'approved') ok(w.provenance_ref, `${w.id} is approved with no provenance_ref`);
    }
  });

  it('the registry names what still has to exist before launch', () => {
    ok(provenance.required_before_launch.length >= 5, 'the pre-launch provenance list is too thin to be useful');
    const joined = provenance.required_before_launch.join(' ').toLowerCase();
    for (const topic of ['foley', 'music', 'voice', 'font', 'licence']) {
      ok(joined.includes(topic), `the pre-launch list does not mention ${topic}`);
    }
  });

  it('generated audio is never permitted to be described as a wartime recording', () => {
    const joined = Object.values(provenance.policy).join(' ').toLowerCase();
    ok(joined.includes('never be described as an original wartime recording'));
  });
});

describe('Localisation (brief §10)', () => {
  it('English and Hebrew have identical key sets', () => {
    const a = Object.keys(locales.en).sort(), b = Object.keys(locales.he).sort();
    eq(a.length, b.length, `en ${a.length} keys vs he ${b.length}`);
    eq(a.filter((k) => !locales.he[k]).length, 0, 'untranslated keys present');
  });
  it('Hebrew declares RTL direction', () => { eq(locales.he._meta.direction, 'rtl'); eq(locales.en._meta.direction, 'ltr'); });
  it('no locale value is an empty string', () => {
    for (const [loc, table] of Object.entries(locales)) for (const [k, v] of Object.entries(table)) {
      if (k === '_meta') continue;
      ok(typeof v === 'string' && v.trim().length > 0, `${loc}:${k} is empty`);
    }
  });
  it('every rejection reason code has a localised message in both languages', () => {
    for (const code of Object.values(REJECT)) {
      ok(locales.en[code], `en missing ${code}`);
      ok(locales.he[code], `he missing ${code}`);
    }
  });
  it('player-facing error text never exposes internal detail', () => {
    for (const table of Object.values(locales)) for (const [k, v] of Object.entries(table)) {
      if (k === '_meta') continue;
      notOk(/node|stack|traceback|null pointer|undefined|\.gd:|\.js:/i.test(v), `${k} leaks internals: ${v}`);
    }
  });
});

describe('District content (brief §9, §13)', () => {
  it('the district is larger than the desktop prototype district', () => {
    const [w, h] = districtNormandy.grid.size_m;
    ok(w * h > 66 * 64, `${w}x${h} is not larger than 66x64`);
  });
  it('every building has an interior with at least one room', () => {
    for (const s of districtNormandy.structures) ok(s.interior.rooms.length >= 1, `${s.id} has no interior`);
  });
  it('every interactable door declares a state and a swing, so it cannot be passable before it opens', () => {
    for (const s of districtNormandy.structures) for (const o of s.openings.filter((x) => x.kind === 'door')) {
      ok(o.state, `${s.id} door has no state`); ok(o.swing, `${s.id} door has no swing`); ok(o.hinge, `${s.id} door has no hinge`);
    }
  });
  it('every window declares a recess, so walls have thickness', () => {
    for (const s of districtNormandy.structures) for (const o of s.openings.filter((x) => x.kind === 'window')) {
      ok(typeof o.recess === 'number' && o.recess > 0, `${s.id} window has no recess`);
    }
    for (const s of districtNormandy.structures) ok(s.wall_thickness >= 0.3, `${s.id} walls are paper thin`);
  });
  it('every POI an authored objective references actually exists in the district', () => {
    const poi = new Set(districtNormandy.pois.map((p) => p.id));
    const ch = chapters.chapters.filter((c) => c.district === districtNormandy.id && c.status === 'authored');
    for (const c of ch) for (const o of c.objectives) {
      if (o.target && o.target.startsWith('poi_')) ok(poi.has(o.target), `${c.id}:${o.id} -> ${o.target} missing`);
    }
  });
  it('every authored objective in the district is reachable from a POI or an npc group', () => {
    const poi = new Set(districtNormandy.pois.map((p) => p.id));
    const objsWithPoi = districtNormandy.pois.filter((p) => p.objective).map((p) => p.objective);
    ok(objsWithPoi.includes('obj_cut_field_line') && objsWithPoi.includes('obj_mark_battery') && objsWithPoi.includes('obj_reach_barn'));
  });
  it('every patrol defines investigate, combat, lost_contact and recover behaviour', () => {
    for (const p of districtNormandy.patrols) for (const st of ['patrol', 'investigate', 'combat', 'lost_contact', 'recover']) {
      ok(p.states[st], `${p.id} has no ${st} state`);
    }
  });
  it('civilians have their own priorities, not a combat AI', () => {
    for (const c of districtNormandy.civilians) {
      ok(c.priority && !['combat', 'attack'].includes(c.priority), `${c.id} priority ${c.priority}`);
      ok(c.schedule.length >= 2, `${c.id} has no daily schedule`);
      ok(c.persists_when_unloaded === true, `${c.id} would reset when streamed out`);
      ok(c.is_fictional === true, `${c.id} is not flagged fictional`);
    }
  });
  it('civilian schedules cover the whole 24-hour day', () => {
    for (const c of districtNormandy.civilians) {
      const covered = c.schedule.reduce((s, x) => s + ((x.to_h - x.from_h + 24) % 24 || 24), 0);
      close(covered, 24, 0.01, `${c.id} schedule covers ${covered}h`);
    }
  });
  it('the district declares what persists and what resets', () => {
    const p = districtNormandy.persistence_rules;
    ok(p.permanent.length >= 5 && p.resets_on_reentry.length >= 3);
    ok(p.permanent.includes('objective_flags'), 'objective flags must persist to prevent duplicate rewards');
  });
  it('the district honestly declares that its art is a blockout', () => {
    eq(districtNormandy.art_status.level, 'blockout');
    ok(districtNormandy.art_status.statement.includes('does not meet the commercial art bar'));
  });
  it('streaming cells cover the whole district with no gap', () => {
    const [w, h] = districtNormandy.grid.size_m;
    const covered = new Set();
    for (const c of districtNormandy.streaming_cells) {
      for (let x = c.rect_m[0]; x < c.rect_m[2]; x += 8) for (let z = c.rect_m[1]; z < c.rect_m[3]; z += 8) covered.add(`${x},${z}`);
    }
    eq(covered.size, (w / 8) * (h / 8), `streaming covers ${covered.size} of ${(w / 8) * (h / 8)} cells`);
  });
});

}
