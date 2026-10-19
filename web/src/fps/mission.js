// The mission scene: renderer, lighting, agents, objectives and the result.
//
// The result this produces is deliberately narrow — an outcome, the objectives
// that were completed, metrics, and bounded effect requests. It cannot write
// campaign state; the CampaignService validates and applies it.

import { District, initBuilder } from './build-district.js';
import { Player, initPlayer } from './player.js';
import { Hostile, Civilian, initAgents } from './agents.js';
import { initMaterials, material } from './materials.js';
import { makeRng } from '../sim/rng.js';
import { damageAt } from '../sim/weapons.js';
import { stealthReadout, awarenessBand } from '../sim/detection.js';
import { AudioDirector, reverbForRoom } from '../sim/audio.js';
import { RESULT_VERSION } from '../sim/contracts.js';

let THREE;

const WEATHER = {
  clear_morning: { sun: 1.0, sunColour: 0xffe9c4, sky: 0x8fb0c6, ground: 0x5c5a40, fog: 0xa9bccb, fogMul: 1.0, elev: 0.55, azim: 1.1 },
  overcast:      { sun: 0.45, sunColour: 0xd8dce0, sky: 0x8b929a, ground: 0x4e5244, fog: 0x9aa3ab, fogMul: 2.2, elev: 0.9, azim: 1.6 },
  light_rain:    { sun: 0.3, sunColour: 0xc8ced4, sky: 0x6f777e, ground: 0x454a40, fog: 0x7f888f, fogMul: 3.4, elev: 1.0, azim: 2.0 },
  night_clear:   { sun: 0.08, sunColour: 0x7f93b8, sky: 0x1b2634, ground: 0x171c22, fog: 0x1d2530, fogMul: 1.6, elev: 0.35, azim: 4.2 },
};

export class MissionScene {
  constructor(three, { canvas, district, context, chapter, weapons, settings, i18n, onStateChange }) {
    THREE = three;
    initMaterials(three); initBuilder(three); initPlayer(three); initAgents(three);
    this.ctx = context;
    this.chapter = chapter;
    this.weaponsReg = weapons;
    this.s = settings;
    this.i18n = i18n;
    this.onStateChange = onStateChange || (() => {});
    this.rng = makeRng(context.seed);
    this.elapsed = 0;
    this.missionSeconds = 0;
    this.localHour = 8.2;
    this.ready = { player: false, collision: false, navigation: false, objectives: false, ui: false, audio: false };
    this.metrics = { elapsed_mission_seconds: 0, shots_fired: 0, times_detected: 0, alarm_raised: false, civilians_assisted: 0, hostiles_neutralised: 0 };
    this.objectiveState = {};
    this.events = [];
    this.subtitles = [];
    this.finished = null;
    this.paused = false;
    this.interactTarget = null;
    this.interactProgress = 0;

    const opts = this.s.rendererOptions();
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: opts.quality !== 'low', powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, opts.pixelRatioCap) * opts.renderScale);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    this.renderer.shadowMap.enabled = opts.shadows;
    if (opts.shadows) this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    this.scene = new THREE.Scene();
    this.weather = district.default_weather;
    this.applyWeather(this.weather, opts);

    this.district = new District(district, { shadows: opts.shadows, ambientMotion: !this.s.get('motion_reduction') });
    this.scene.add(this.district.group);
    this.ready.collision = this.district.colliders.length > 0;
    this.ready.navigation = this.district.interiorRooms.length > 0 && this.district.doors.length > 0;

    this.player = new Player(this.district, this.s, { inventory: { amm_9x19: 48, tool_medical_kit: 2 } });
    this.scene.add(this.player.camera);
    const loadout = (context.loadout || []).map((id) => this.weaponById(id)).filter(Boolean);
    this.loadout = loadout.length ? loadout : [this.weaponById('tool_wire_cutters')].filter(Boolean);
    this.loadoutIndex = 0;
    if (this.loadout.length) this.player.equip(this.loadout[0]);
    this.ready.player = true;

    this.hostiles = [];
    for (const spec of district.patrols) for (let i = 0; i < spec.count; i++) {
      const h = new Hostile(spec, i, this.district, this);
      this.hostiles.push(h);
      this.scene.add(h.model);
    }
    this.civilians = district.civilians.map((spec) => {
      const c = new Civilian(spec, this.district, this);
      this.scene.add(c.model);
      return c;
    });

    this.audio = new AudioDirector(this.s.audioOptions());
    this.repGuard = AudioDirector.repetitionGuard(0.18);
    this.ready.audio = true;

    this.buildObjectives();
    this.ready.objectives = Object.keys(this.objectiveState).length > 0;

    this.tracers = new THREE.Group();
    this.scene.add(this.tracers);
    this.resize();
  }

  weaponById(id) { return this.weaponsReg.weapons.find((w) => w.id === id) || null; }

  applyWeather(name, opts) {
    const w = WEATHER[name] || WEATHER.clear_morning;
    this.weatherSpec = w;
    this.sunIntensity = w.sun;
    this.scene.background = new THREE.Color(w.sky);
    this.scene.fog = new THREE.FogExp2(w.fog, opts.fogDensity * w.fogMul);
    const hemi = new THREE.HemisphereLight(w.sky, w.ground, 0.55 + w.sun * 0.35);
    this.scene.add(hemi);
    const sun = new THREE.DirectionalLight(w.sunColour, 1.5 * w.sun + 0.15);
    const dist = 90;
    sun.position.set(Math.cos(w.azim) * dist * Math.cos(w.elev), Math.sin(w.elev) * dist, Math.sin(w.azim) * dist * Math.cos(w.elev));
    sun.target.position.set(64, 0, 56);
    this.scene.add(sun.target);
    if (opts.shadows) {
      sun.castShadow = true;
      sun.shadow.mapSize.set(opts.shadowMapSize, opts.shadowMapSize);
      const c = sun.shadow.camera;
      c.left = -70; c.right = 70; c.top = 70; c.bottom = -70; c.near = 1; c.far = 260;
      sun.shadow.bias = -0.0008;
      sun.shadow.normalBias = 0.03;
    }
    this.scene.add(sun);
    this.sun = sun;
  }

  buildObjectives() {
    for (const o of this.chapter?.objectives || []) {
      this.objectiveState[o.id] = {
        spec: o, done: false, failed: false, progress: 0,
        label: this.i18n.t(o.label_key), required: o.required,
      };
    }
    this.pois = new Map(this.district.data.pois.map((p) => [p.id, { ...p, state: {} }]));
  }

  resize() {
    const el = this.renderer.domElement;
    const w = el.clientWidth || window.innerWidth, h = el.clientHeight || window.innerHeight;
    this.renderer.setSize(w, h, false);
    this.player.camera.aspect = w / h;
    this.player.camera.updateProjectionMatrix();
  }

  markUiReady() { this.ready.ui = true; }
  get readyAll() { return Object.values(this.ready).every(Boolean); }

  // -------------------------------------------------------------- gameplay --
  nearestInteraction() {
    const p = this.player.pos;
    let best = null, bd = 2.4;
    for (const [id, poi] of this.pois) {
      if (!poi.p) continue;
      if (poi.kind === 'observation_target' || poi.kind === 'zone' || poi.kind === 'landmark') continue;
      if (poi.hidden_until_intel && !this.cacheRevealed) continue;
      if (poi.state.complete) continue;
      const d = Math.hypot(poi.p[0] - p.x, poi.p[1] - p.z);
      if (d < bd) { bd = d; best = { kind: 'poi', id, poi, label_key: poi.label_key }; }
    }
    const door = this.district.nearestDoor(p.x, p.z, 1.9);
    if (door && !best) best = { kind: 'door', id: door.id, door, label_key: door.frac > 0.5 ? 'hud.interact' : 'hud.interact' };
    for (const c of this.civilians) {
      if (!c.canSpeak) continue;
      const d = Math.hypot(c.pos[0] - p.x, c.pos[1] - p.z);
      if (d < bd) { bd = d; best = { kind: 'civilian', id: c.id, civ: c, label_key: c.spec.label_key }; }
    }
    for (const l of this.district.ladders) {
      const d = Math.hypot(l.pos[0] - p.x, l.pos[1] - p.z);
      if (d < 1.6 && !best) best = { kind: 'ladder', id: l.id, ladder: l, label_key: 'hud.interact' };
    }
    return best;
  }

  interact(target, dt, held) {
    if (!target) { this.interactProgress = 0; return; }
    if (target.kind === 'door') {
      if (!this.doorCooldown) {
        this.district.openDoor(target.id, target.door.target < 0.5);
        this.doorCooldown = 0.45;
        this.playSound({ id: 'door_move', family: 'interaction', dist: 1, essential: false });
        this.player.noiseEvents.push({ loudness: 0.5, radius_m: 13, source: 'door', pos: [this.player.pos.x, this.player.pos.z], at: this.elapsed });
      }
      return;
    }
    if (target.kind === 'ladder') {
      this.player.pos.y = target.ladder.top + 0.02;
      this.player.vel.y = 0;
      return;
    }
    if (target.kind === 'civilian') {
      if (!this.dialogueCooldown) {
        this.dialogueCooldown = 4;
        const c = target.civ;
        const lines = {
          civ_farm_woman: c.narrativeFlags.has('knows_cache_location') && !this.cacheRevealed
            ? { key: 'dlg.farm_woman.cache', text: this.i18n.locale === 'he' ? 'מתחת לקש, מאחורי האסם. אל תדליק אור.' : 'Under the straw, behind the barn. Do not strike a light.' }
            : { key: 'dlg.farm_woman.warn', text: this.i18n.locale === 'he' ? 'הם עוברים בדרך כל חצי שעה. חכה.' : 'They pass on the lane every half hour. Wait.' },
          civ_boy_runner: { key: 'dlg.boy.line', text: this.i18n.locale === 'he' ? 'ראיתי תותח בשדה המזרחי.' : 'There is a gun in the east field. I saw it.' },
          civ_priest: { key: 'dlg.priest.line', text: this.i18n.locale === 'he' ? 'הדלת פתוחה. אל תביא אותם לכאן.' : 'The door is open. Do not bring them here.' },
        }[c.id] || { key: 'dlg.generic', text: '…' };
        if (c.id === 'civ_farm_woman' && c.narrativeFlags.has('knows_cache_location')) this.cacheRevealed = true;
        this.say(this.i18n.t(c.spec.label_key), lines.text);
        this.playSound({ id: 'dialogue_line', family: 'dialogue', dist: 1.5, essential: true });
        this.metrics.civilians_assisted = Math.max(this.metrics.civilians_assisted, 0);
      }
      return;
    }
    // staged POI interaction, e.g. cutting a line in three stages
    const poi = target.poi;
    if (!held) { this.interactProgress = 0; return; }
    if (poi.tool && this.player.equipped?.profile.id !== poi.tool) {
      const t = this.loadout.findIndex((w) => w.id === poi.tool);
      if (t >= 0) { this.loadoutIndex = t; this.player.equip(this.loadout[t]); }
      else { this.say(null, this.i18n.t('hud.no_weapon')); return; }
    }
    const total = (poi.stages ?? 1) * (poi.stage_seconds ?? 1.2);
    this.interactProgress = Math.min(1, this.interactProgress + dt / total);
    const stage = Math.floor(this.interactProgress * (poi.stages ?? 1));
    if (stage !== poi.state.lastStage) {
      poi.state.lastStage = stage;
      if (this.repGuard(`cut_stage_${stage}`, this.elapsed)) {
        this.playSound({ id: `cut_stage_${stage}`, family: 'interaction', dist: 0.6, essential: false });
        this.player.noiseEvents.push({ loudness: 0.35, radius_m: poi.noise_radius_m ?? 8, source: 'tool', pos: [this.player.pos.x, this.player.pos.z], at: this.elapsed });
      }
    }
    if (this.interactProgress >= 1) {
      poi.state.complete = true;
      this.interactProgress = 0;
      if (poi.id === 'poi_arms_cache') {
        for (const c of poi.contents || []) this.player.inventory[c.item] = (this.player.inventory[c.item] ?? 0) + c.count;
      }
      this.completeObjective(poi.objective, 'interaction');
      this.playSound({ id: 'objective_complete', family: 'player_feedback', dist: 0, essential: true });
    }
  }

  completeObjective(id, how) {
    const o = this.objectiveState[id];
    if (!o || o.done) return;
    o.done = true;
    o.how = how;
    this.events.push({ kind: 'objective_complete', id, at: Math.round(this.missionSeconds) });
    this.onStateChange('objective', { id, label: o.label });
  }

  say(speaker, text) {
    if (!this.s.get('subtitles')) return;
    const name = this.s.get('speaker_names') ? speaker : null;
    this.subtitles.push({ speaker: name, text, until: this.elapsed + 4.2 });
    this.onStateChange('subtitle', { speaker: name, text });
  }

  playSound(req) {
    const room = this.district.roomAt(this.player.pos.x, this.player.pos.z, this.player.pos.y);
    const out = this.audio.play({ ...req, reverb: reverbForRoom(room?.ambience ?? this.district.data.ambience_default) }, this.elapsed);
    // the director holds the voice; the prototype has no sample bank, so the
    // decision is what is recorded, not an audible result
    if (out.played) setTimeout(() => this.audio.stop(req.id), 120);
    return out;
  }

  hostileFire(hostile, targetPos, dist) {
    this.playSound({ id: `hostile_fire_${hostile.id}`, family: 'weapon_shot', dist, essential: true, pan: 0 });
    const spreadDeg = 1.4 + dist * 0.035 + (hostile.state === 'combat' ? 0.6 : 0);
    const hit = this.rng.next() < Math.max(0.05, 0.55 - dist * 0.006) && !this.district.segmentBlocked(hostile.pos[0], 1.4, hostile.pos[1], targetPos[0], targetPos[1], targetPos[2], true);
    this.addTracer([hostile.pos[0], 1.42, hostile.pos[1]], targetPos, spreadDeg);
    if (hit) {
      const dmg = Math.max(4, Math.round(damageAt(hostile.weaponProfile, dist, 'torso') * 0.42));
      this.player.health = Math.max(0, this.player.health - dmg);
      this.player.shakeTime = 1.4;
      this.onStateChange('player_hit', { damage: dmg, from: hostile.id, dir: Math.atan2(hostile.pos[1] - this.player.pos.z, hostile.pos[0] - this.player.pos.x) });
      this.playSound({ id: 'player_hit', family: 'player_feedback', dist: 0, essential: true });
      if (this.player.health <= 0) this.resolve('failure', 'player_down');
    }
  }

  onHostileDown(h) {
    this.metrics.hostiles_neutralised += 1;
    this.events.push({ kind: 'hostile_down', id: h.id, at: Math.round(this.missionSeconds) });
    this.playSound({ id: `down_${h.id}`, family: 'threat', dist: 6, essential: false });
  }

  addTracer(from, to, spreadDeg = 0) {
    const g = new THREE.BufferGeometry();
    const jitter = (spreadDeg * Math.PI / 180);
    const dir = new THREE.Vector3(to[0] - from[0], to[1] - from[1], to[2] - from[2]).normalize();
    dir.x += (this.rng.next() - 0.5) * jitter; dir.z += (this.rng.next() - 0.5) * jitter; dir.y += (this.rng.next() - 0.5) * jitter * 0.6;
    const end = new THREE.Vector3(from[0], from[1], from[2]).addScaledVector(dir, 60);
    g.setFromPoints([new THREE.Vector3(from[0], from[1], from[2]), end]);
    const line = new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0xffd9a0, transparent: true, opacity: 0.85 }));
    line.userData.life = 0.07;
    this.tracers.add(line);
  }

  playerShoot() {
    const out = this.player.tryFire(this);
    if (!out?.fired) {
      if (out?.reason === 'empty') this.playSound({ id: 'dry', family: 'weapon_mechanism', dist: 0, essential: true });
      return out;
    }
    this.metrics.shots_fired += 1;
    const w = this.player.equipped;
    this.playSound({ id: `shot_${this.metrics.shots_fired}`, family: 'weapon_shot', dist: 0, essential: true });
    const cam = this.player.camera;
    const origin = cam.position.clone();
    const dir = new THREE.Vector3(0, 0, -1).applyQuaternion(cam.quaternion);
    const spreadRad = (0.3 + out.spread * 1.6) * Math.PI / 180;
    dir.x += (this.rng.next() - 0.5) * spreadRad;
    dir.y += (this.rng.next() - 0.5) * spreadRad;
    dir.normalize();
    this.addTracer(origin.toArray(), origin.clone().addScaledVector(dir, 50).toArray());

    // hit resolution against hostiles, respecting geometry
    let best = null, bestT = Infinity;
    for (const h of this.hostiles) {
      if (!h.alive) continue;
      const to = new THREE.Vector3(h.pos[0], 1.2, h.pos[1]);
      const rel = to.clone().sub(origin);
      const t = rel.dot(dir);
      if (t < 0.4 || t > 180) continue;
      const closest = origin.clone().addScaledVector(dir, t);
      const miss = closest.distanceTo(to);
      const zone = miss < 0.2 ? 'torso' : miss < 0.55 ? 'limb' : null;
      const headTo = new THREE.Vector3(h.pos[0], 1.56, h.pos[1]);
      const headMiss = origin.clone().addScaledVector(dir, t).distanceTo(headTo);
      if (!zone && headMiss > 0.16) continue;
      if (this.district.segmentBlocked(origin.x, origin.y, origin.z, to.x, to.y, to.z, true)) continue;
      if (t < bestT) { bestT = t; best = { h, zone: headMiss < 0.16 ? 'head' : zone, dist: t }; }
    }
    if (best) {
      const dmg = damageAt(w.profile, best.dist, best.zone);
      best.h.takeHit(dmg, this);
      this.onStateChange('hit_marker', { zone: best.zone });
      this.playSound({ id: `impact_${this.metrics.shots_fired}`, family: 'player_feedback', dist: 0, essential: false });
    }
    // every hostile who can hear a gunshot reacts
    for (const h of this.hostiles) if (h.alive) h.hear([{ pos: [this.player.pos.x, this.player.pos.z], loudness: 1.5, radius_m: 220, source: 'gunshot' }]);
    this.metrics.alarm_raised = true;
    this.player.syncReserveToInventory();
    return out;
  }

  // ----------------------------------------------------------------- frame --
  update(dt, input) {
    if (this.finished || this.paused) return;
    this.elapsed += dt;
    this.missionSeconds += dt;
    this.localHour += dt / 3600 * 6;      // a mission hour passes in ten minutes
    this.doorCooldown = Math.max(0, (this.doorCooldown ?? 0) - dt);
    this.dialogueCooldown = Math.max(0, (this.dialogueCooldown ?? 0) - dt);

    const move = this.player.update(dt, input, this);

    // stealth inputs, shared with the AI
    this.playerExposure = this.player.exposure(this);
    this.playerCover = this.district.coverAt(this.player.pos.x, this.player.pos.z, this.player.pos.y);

    // Interactions. A staged interaction (cutting a line) continues while the
    // button is held; a one-shot interaction (a door) fires on press. Both
    // routes exist, so no action is reachable only by a long press.
    this.interactTarget = this.nearestInteraction();
    const held = input.interactHeld === true;
    const tapped = input.pressed.has('interact');
    if (this.interactTarget?.kind === 'poi') this.interact(this.interactTarget, dt, held || tapped);
    else if (tapped) this.interact(this.interactTarget, dt, true);
    else this.interactProgress = 0;

    if (input.pressed.has('reload')) this.player.reload();
    if (input.fire) this.playerShoot();

    // observation objective: look at the target from far enough, with sight
    const obs = this.pois.get('poi_gun_position');
    if (obs && !this.objectiveState[obs.objective]?.done) {
      const d = Math.hypot(obs.p[0] - this.player.pos.x, obs.p[1] - this.player.pos.z);
      const toTarget = new THREE.Vector3(obs.p[0] - this.player.pos.x, 1.2, obs.p[1] - this.player.pos.z).normalize();
      const look = new THREE.Vector3(0, 0, -1).applyQuaternion(this.player.camera.quaternion);
      const aligned = look.dot(toTarget) > 0.985;
      const sight = !this.district.segmentBlocked(this.player.pos.x, this.player.pos.y + 1.5, this.player.pos.z, obs.p[0], 1.4, obs.p[1], true);
      const far = d <= (obs.required_distance_m ?? 60) && d > 6;
      if (aligned && sight && far && this.player.equipped?.runtime.ads > 0.6) {
        obs.state.observed = (obs.state.observed ?? 0) + dt;
        this.observeProgress = Math.min(1, obs.state.observed / (obs.required_seconds ?? 3));
        if (obs.state.observed >= (obs.required_seconds ?? 3)) this.completeObjective(obs.objective, 'observation');
      } else {
        obs.state.observed = Math.max(0, (obs.state.observed ?? 0) - dt * 0.6);
        this.observeProgress = (obs.state.observed ?? 0) / (obs.required_seconds ?? 3);
      }
    }

    // zone objectives
    for (const [, poi] of this.pois) {
      if (poi.kind !== 'zone' || !poi.objective) continue;
      const st = this.objectiveState[poi.objective];
      if (!st || st.done) continue;
      const d = Math.hypot(poi.p[0] - this.player.pos.x, poi.p[1] - this.player.pos.z);
      if (poi.interaction === 'reach' && d < (poi.radius_m ?? 5)) {
        // the extraction zone only counts once the required objectives are met
        const req = Object.values(this.objectiveState).filter((o) => o.required && o.spec.id !== poi.objective);
        if (req.every((o) => o.done)) { this.completeObjective(poi.objective, 'reached'); this.resolve(this.deriveOutcome(), 'extracted'); }
        else this.extractionBlocked = true;
      } else if (poi.interaction === 'hold') {
        if (d < (poi.radius_m ?? 8)) { poi.state.held = (poi.state.held ?? 0) + dt; st.progress = Math.min(1, poi.state.held / (poi.spec?.duration_s ?? 180)); }
        if ((poi.state.held ?? 0) >= 180) this.completeObjective(poi.objective, 'held');
      }
    }

    // agents
    const playerNoise = this.player.drainNoise();
    this.hostilesInCombat = 0;
    for (const h of this.hostiles) {
      if (!h.alive) continue;
      h.hear(playerNoise);
      h.update(dt, this.player, this);
      if (h.state === 'combat') this.hostilesInCombat += 1;
    }
    this.shotsFired = this.metrics.shots_fired;
    for (const c of this.civilians) c.update(dt, this.player, this);

    // detection metric and optional constraints
    const maxAware = Math.max(0, ...this.hostiles.filter((h) => h.alive).map((h) => h.awareness));
    const band = awarenessBand(maxAware);
    if (band === 'detected' && !this.wasDetected) { this.metrics.times_detected += 1; this.wasDetected = true; }
    if (band !== 'detected') this.wasDetected = false;
    this.maxAwareness = maxAware;
    for (const o of Object.values(this.objectiveState)) {
      if (o.spec.type !== 'constraint' || o.failed) continue;
      if (o.spec.constraint === 'alarm_never_raised' && this.metrics.alarm_raised) o.failed = true;
      if (o.spec.constraint === 'never_detected' && this.metrics.times_detected > 0) o.failed = true;
    }

    this.district.step(dt, this.elapsed);

    // tracers decay
    for (const t of [...this.tracers.children]) {
      t.userData.life -= dt;
      t.material.opacity = Math.max(0, t.userData.life / 0.07) * 0.85;
      if (t.userData.life <= 0) { this.tracers.remove(t); t.geometry.dispose(); t.material.dispose(); }
    }
    this.subtitles = this.subtitles.filter((s) => s.until > this.elapsed);
    this.metrics.elapsed_mission_seconds = Math.round(this.missionSeconds);
  }

  render() { this.renderer.render(this.scene, this.player.camera); }

  hudState() {
    const w = this.player.equipped;
    const read = stealthReadout(this.playerExposure ?? 0, this.playerCover ?? 0, (this.player.noiseEvents[0]?.loudness ?? 0), this.maxAwareness ?? 0);
    return {
      health: this.player.health,
      stamina: this.player.stamina,
      weapon: w ? { label_key: w.profile.label_key, loaded: w.runtime.loaded, reserve: w.runtime.reserve, isTool: w.profile.class === 'tool', reloading: !!w.runtime.reload, reloadProgress: w.runtime.reload ? w.runtime.reload.elapsed / w.runtime.reload.total : 0, ads: w.runtime.ads } : null,
      stealth: read,
      objectives: Object.values(this.objectiveState).map((o) => ({ id: o.spec.id, label: o.label, done: o.done, failed: o.failed, required: o.required, progress: o.progress ?? 0 })),
      interact: this.interactTarget ? { label_key: this.interactTarget.label_key, progress: this.interactProgress } : null,
      observeProgress: this.observeProgress ?? 0,
      subtitles: this.subtitles,
      posture: this.player.posture,
      captions: this.audio.captions.slice(-3),
      hour: this.localHour,
      extractionBlocked: this.extractionBlocked,
    };
  }

  deriveOutcome() {
    const req = Object.values(this.objectiveState).filter((o) => o.required);
    const done = req.filter((o) => o.done).length;
    if (done === req.length) return 'success';
    if (done > 0) return 'partial_success';
    return 'failure';
  }

  /** Build the MissionResult. Bounded: an outcome, objectives, metrics, requests. */
  resolve(outcome, reason) {
    if (this.finished) return this.finished;
    const allowed = this.ctx.allowed_outcomes;
    let final = outcome;
    if (!allowed.includes(final)) final = allowed.includes('partial_success') ? 'partial_success' : allowed[0];
    const completed = Object.values(this.objectiveState).filter((o) => o.done && !o.failed).map((o) => o.spec.id);
    const failed = Object.values(this.objectiveState).filter((o) => o.failed || (!o.done && o.required)).map((o) => o.spec.id);
    const eff = this.chapter?.strategic_effects?.[final] || {};
    this.finished = {
      result_version: RESULT_VERSION,
      operation_id: this.ctx.operation_id,
      source_revision: this.ctx.source_revision,
      outcome: final,
      completed_objectives: completed,
      failed_objectives: failed,
      metrics: { ...this.metrics },
      declared_losses: { personnel: final === 'failure' ? Math.abs(eff.personnel ?? 0) : 0 },
      declared_resources: {
        intelligence: eff.intelligence ?? 0,
        materiel: eff.materiel ?? 0,
        documents: 0,
      },
      requests: {
        remove_attacking_formation: !!eff.removes_attacking_formation,
        supply_penalty: (eff.tile_effects || []).reduce((m, e) => Math.max(m, e.set_supply_penalty ?? 0), 0),
        network_exposure_delta: eff.network_exposure ?? 0,
        network_access_delta: eff.network_access ?? 0,
        civilian_health_delta: eff.civilian_health_delta ?? 0,
      },
      reason,
    };
    this.onStateChange('resolved', this.finished);
    return this.finished;
  }

  withdraw() { return this.resolve('withdrawal', 'player_withdrew'); }

  checkpoint() {
    const p = this.player.checkpoint();
    return {
      checkpoint_version: 2,
      district_id: this.district.data.id,
      district_content_version: this.district.data.content_version,
      saved_at_boundary: 'safe_action_boundary',
      player: { position: p.position, yaw: p.yaw, pitch: p.pitch, posture: p.posture, health: p.health, condition: p.condition, equipped: p.equipped },
      inventory: p.inventory,
      weapon_states: p.weapon_states,
      mission_flags: Object.fromEntries(Object.values(this.objectiveState).filter((o) => o.done).map((o) => [o.spec.id, true])),
      poi_states: Object.fromEntries([...this.pois].map(([id, p2]) => [id, { complete: !!p2.state.complete, observed: p2.state.observed ?? 0 }])),
      door_states: Object.fromEntries(this.district.doors.map((d) => [d.id, d.frac > 0.5])),
      container_states: { poi_arms_cache: !!this.pois.get('poi_arms_cache')?.state.complete },
      local_entities: this.hostiles.map((h) => ({ id: h.id, alive: h.alive, pos: h.pos, state: h.state })),
      local_time_hours: this.localHour,
      weather: this.weather,
      interrupted_action: p.interrupted_action,
    };
  }

  restore(cp) {
    if (!cp) return;
    this.player.restore(cp.player ? { ...cp.player, weapon_states: cp.weapon_states, inventory: cp.inventory, interrupted_action: cp.interrupted_action } : null);
    for (const [id, done] of Object.entries(cp.mission_flags || {})) if (this.objectiveState[id] && done) this.objectiveState[id].done = true;
    for (const [id, st] of Object.entries(cp.poi_states || {})) { const p = this.pois.get(id); if (p) p.state = { ...st }; }
    for (const [id, open] of Object.entries(cp.door_states || {})) this.district.openDoor(id, open);
    for (const e of cp.local_entities || []) {
      const h = this.hostiles.find((x) => x.id === e.id);
      if (!h) continue;
      h.alive = e.alive; h.pos = [...e.pos]; h.state = e.state;
      if (!h.alive) { h.model.rotation.z = Math.PI / 2.1; h.model.position.y = 0.26; }
    }
    this.localHour = cp.local_time_hours ?? this.localHour;
  }

  dispose() {
    this.district.dispose();
    this.renderer.dispose();
    this.scene.traverse((o) => { if (o.isMesh) { o.geometry?.dispose?.(); } });
  }
}
