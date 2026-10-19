// Patrols and civilians.
//
// Hostiles run the state machine the district data declares: patrol →
// investigate → combat → lost_contact → recover. Detection goes through the
// shared stealth model, so what the HUD shows and what the AI uses are the same
// numbers. Civilians run a separate priority system: they are not a combat AI
// with a different hat.

import { material } from './materials.js';
import { detectionRate, stepAwareness, awarenessBand, noiseHeard, movementNoise } from '../sim/detection.js';
import { damageAt } from '../sim/weapons.js';

let THREE;
export function initAgents(three) { THREE = three; }

function makeFigure(uniformMat, scale = 1) {
  const g = new THREE.Group();
  const skin = material('mat_skin');
  const uni = material(uniformMat);
  const torso = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.56, 0.24), uni);
  torso.position.y = 1.18;
  const hips = new THREE.Mesh(new THREE.BoxGeometry(0.36, 0.2, 0.24), uni);
  hips.position.y = 0.88;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.115, 10, 8), skin);
  head.position.y = 1.56;
  const helmet = new THREE.Mesh(new THREE.SphereGeometry(0.135, 10, 7, 0, Math.PI * 2, 0, Math.PI * 0.62), material('mat_metal_dull'));
  helmet.position.y = 1.59;
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.052, 0.058, 0.08, 7), skin);
  neck.position.y = 1.47;
  const limbs = {};
  for (const [name, x] of [['legL', -0.1], ['legR', 0.1]]) {
    const hip = new THREE.Group(); hip.position.set(x, 0.86, 0);
    const thigh = new THREE.Mesh(new THREE.CylinderGeometry(0.066, 0.06, 0.42, 7), uni);
    thigh.position.y = -0.21;
    const knee = new THREE.Group(); knee.position.y = -0.42;
    const shin = new THREE.Mesh(new THREE.CylinderGeometry(0.056, 0.05, 0.4, 7), uni);
    shin.position.y = -0.2;
    const boot = new THREE.Mesh(new THREE.BoxGeometry(0.11, 0.08, 0.2), material('mat_wood_dark'));
    boot.position.set(0, -0.42, 0.03);
    knee.add(shin, boot); hip.add(thigh, knee);
    limbs[name] = { hip, knee };
    g.add(hip);
  }
  for (const [name, x] of [['armL', -0.25], ['armR', 0.25]]) {
    const sh = new THREE.Group(); sh.position.set(x, 1.4, 0);
    const upper = new THREE.Mesh(new THREE.CylinderGeometry(0.052, 0.046, 0.3, 7), uni);
    upper.position.y = -0.15;
    const el = new THREE.Group(); el.position.y = -0.3;
    const lower = new THREE.Mesh(new THREE.CylinderGeometry(0.044, 0.04, 0.28, 7), uni);
    lower.position.y = -0.14;
    const hand = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.09, 0.05), skin);
    hand.position.y = -0.3;
    el.add(lower, hand); sh.add(upper, el);
    limbs[name] = { hip: sh, knee: el };
    g.add(sh);
  }
  g.add(torso, hips, head, neck, helmet);
  g.userData.limbs = limbs;
  g.userData.head = head;
  g.scale.setScalar(scale);
  g.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  return g;
}

function makeCarriedWeapon(cls) {
  const g = new THREE.Group();
  const metal = material('mat_metal_dull'), wood = material('mat_wood_dark');
  if (cls === 'pistol') {
    const f = new THREE.Mesh(new THREE.BoxGeometry(0.035, 0.09, 0.17), metal);
    g.add(f);
  } else {
    const stock = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.08, 0.36), wood);
    stock.position.z = 0.2;
    const rec = new THREE.Mesh(new THREE.BoxGeometry(0.044, 0.06, 0.24), metal);
    const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, 0.62, 8), metal);
    barrel.rotation.x = Math.PI / 2; barrel.position.z = -0.44;
    g.add(stock, rec, barrel);
  }
  g.userData.muzzle = [0, 0, cls === 'pistol' ? -0.1 : -0.75];
  return g;
}

export class Hostile {
  constructor(spec, index, district, world) {
    this.spec = spec;
    this.id = `${spec.id}_${index}`;
    this.d = district;
    this.faction = spec.faction;
    this.weaponProfile = world.weaponById(spec.weapon);
    this.route = spec.route_m;
    this.leg = index % Math.max(1, this.route.length);
    this.pos = [this.route[this.leg][0], this.route[this.leg][1]];
    this.y = 0;
    this.facing = 0;
    this.state = 'patrol';
    this.awareness = 0;
    this.alertness = spec.alertness;
    this.health = 100;
    this.alive = true;
    this.pauseLeft = 0;
    this.stateTimer = 0;
    this.lastKnown = null;
    this.fireCooldown = 0;
    this.gait = 0;
    this.repositionIn = 0;
    this.sight_range = 58;
    this.fov_rad = Math.PI * 0.6;
    this.base_acuity = 0.85;
    this.model = makeFigure('mat_uniform_axis');
    const w = makeCarriedWeapon(this.weaponProfile?.class ?? 'bolt_action_rifle');
    this.model.userData.limbs.armR.knee.add(w);
    w.position.set(0, -0.26, -0.12);
    w.rotation.set(1.35, 0, 0);
    this.weaponMesh = w;
    this.model.position.set(this.pos[0], 0, this.pos[1]);
    this.noise = [];
  }

  get observerRecord() {
    return {
      pos: this.pos, facing: this.facing, fov_rad: this.fov_rad,
      sight_range: this.sight_range, alertness: Math.min(1, this.alertness + (this.state === 'patrol' ? 0 : 0.4)),
      base_acuity: this.base_acuity,
    };
  }

  hear(noiseEvents) {
    for (const n of noiseEvents) {
      const h = noiseHeard(n, { pos: this.pos, alertness: this.alertness }, this.d);
      if (!h.heard) continue;
      this.lastKnown = [n.pos[0], n.pos[1]];
      this.awareness = Math.min(1, this.awareness + (n.source === 'gunshot' ? 0.9 : 0.3));
      if (this.state === 'patrol') this.enter('investigate');
    }
  }

  enter(state) {
    this.state = state;
    this.stateTimer = 0;
    if (state === 'combat') this.repositionIn = this.rand(this.spec.states.combat.reposition_s);
  }

  rand(range) { return Array.isArray(range) ? range[0] + Math.random() * (range[1] - range[0]) : range; }

  moveToward(target, speed, dt) {
    const dx = target[0] - this.pos[0], dz = target[1] - this.pos[1];
    const dist = Math.hypot(dx, dz);
    if (dist < 0.25) return true;
    const step = Math.min(dist, speed * dt);
    let nx = this.pos[0] + dx / dist * step, nz = this.pos[1] + dz / dist * step;
    // slide along blockers rather than stopping dead
    for (const c of this.d.colliders) {
      if (c.kind === 'roof' || c.kind === 'floor') continue;
      if (c.y1 < 0.6) continue;
      if (c.kind === 'door') {
        const door = this.d.doors.find((dr) => dr.id === c.doorId);
        if (door?.passable) continue;
      }
      const cx = Math.max(c.min[0], Math.min(nx, c.max[0]));
      const cz = Math.max(c.min[1], Math.min(nz, c.max[1]));
      const ox = nx - cx, oz = nz - cz, od = Math.hypot(ox, oz);
      if (od < 0.36 && od > 1e-6) { const push = (0.36 - od) / od; nx += ox * push; nz += oz * push; }
    }
    const moved = Math.hypot(nx - this.pos[0], nz - this.pos[1]);
    this.pos[0] = nx; this.pos[1] = nz;
    this.facing = Math.atan2(dz, dx);
    if (moved > 0.002) {
      this.gait += moved;
      if (this.gait > 0.78) {
        this.gait = 0;
        const surf = this.d.surfaceAt(nx, nz);
        const n = movementNoise({ grounded: true, displacement: moved, speed, posture: 'stand', surface: surf, loadKg: 18 });
        if (n.loudness > 0) this.noise.push({ ...n, pos: [nx, nz] });
      }
    }
    return false;
  }

  update(dt, player, world) {
    if (!this.alive) return;
    this.stateTimer += dt;
    this.fireCooldown = Math.max(0, this.fireCooldown - dt);

    // perception through the shared model
    const det = detectionRate(this.observerRecord, {
      pos: [player.pos.x, player.pos.z], posture: player.posture,
      light_exposure: world.playerExposure, cover: world.playerCover, speed: player.lastSpeed ?? 0,
    }, this.d);
    this.awareness = stepAwareness(this.awareness, det.rate, dt, this.state === 'combat' ? 0.03 : 0.22);
    if (det.rate > 0) this.lastKnown = [player.pos.x, player.pos.z];
    const band = awarenessBand(this.awareness);

    switch (this.state) {
      case 'patrol': {
        if (band === 'detected') { this.enter('combat'); break; }
        if (band === 'suspicious') { this.enter('investigate'); break; }
        if (this.pauseLeft > 0) { this.pauseLeft -= dt; this.facing += dt * 0.5; break; }
        const target = this.route[this.leg];
        if (this.moveToward(target, 1.25, dt)) {
          this.leg = (this.leg + 1) % this.route.length;
          this.pauseLeft = this.rand(this.spec.pause_s);
        }
        break;
      }
      case 'investigate': {
        if (band === 'detected') { this.enter('combat'); break; }
        const cfg = this.spec.states.investigate;
        const target = this.lastKnown || this.route[this.leg];
        const speed = cfg.sprint_to_last_known ? 2.6 : 1.4;
        const arrived = this.moveToward(target, speed, dt);
        if (arrived) this.facing += dt * 1.6;      // sweep the area
        if (this.stateTimer > cfg.search_seconds) this.enter('lost_contact');
        break;
      }
      case 'combat': {
        const cfg = this.spec.states.combat;
        if (band !== 'detected' && this.stateTimer > 3) { this.enter('lost_contact'); break; }
        const target = this.lastKnown || [player.pos.x, player.pos.z];
        const dist = Math.hypot(target[0] - this.pos[0], target[1] - this.pos[1]);
        this.facing = Math.atan2(target[1] - this.pos[1], target[0] - this.pos[0]);
        this.repositionIn -= dt;
        if (cfg.use_cover && this.repositionIn <= 0) {
          this.repositionIn = this.rand(cfg.reposition_s);
          this.coverTarget = this.findCover(target);
        }
        if (this.coverTarget) { if (this.moveToward(this.coverTarget, 2.2, dt)) this.coverTarget = null; }
        else if (dist > 22) this.moveToward(target, 1.9, dt);
        if (this.fireCooldown <= 0 && det.rate > 0 && dist < 70) {
          this.fireCooldown = this.weaponProfile?.handling.rpm_cyclic ? 0.55 : 1.7;
          world.hostileFire(this, [player.pos.x, player.pos.y + player.eyeHeight * 0.75, player.pos.z], dist);
        }
        break;
      }
      case 'lost_contact': {
        const cfg = this.spec.states.lost_contact;
        if (band === 'detected') { this.enter('combat'); break; }
        this.facing += dt * 0.9;
        if (this.stateTimer > cfg.hold_seconds) this.enter(cfg.then === 'sweep' ? 'investigate' : 'recover');
        break;
      }
      case 'recover': {
        const cfg = this.spec.states.recover;
        if (band === 'detected') { this.enter('combat'); break; }
        if (this.moveToward(this.route[this.leg], 1.2, dt) || this.stateTimer > cfg.decay_seconds) {
          this.awareness = Math.min(this.awareness, 0.2);
          this.enter('patrol');
        }
        break;
      }
    }

    // pose: the gait drives the limbs, so feet do not slide
    const walking = this.state !== 'patrol' || this.pauseLeft <= 0;
    const phase = world.elapsed * (this.state === 'combat' ? 7 : 4.4);
    const amp = walking ? (this.state === 'combat' ? 0.5 : 0.34) : 0.02;
    const L = this.model.userData.limbs;
    L.legL.hip.rotation.x = Math.sin(phase) * amp;
    L.legR.hip.rotation.x = -Math.sin(phase) * amp;
    L.legL.knee.rotation.x = Math.max(0, -Math.sin(phase) * amp * 1.2);
    L.legR.knee.rotation.x = Math.max(0, Math.sin(phase) * amp * 1.2);
    const aiming = this.state === 'combat';
    L.armR.hip.rotation.x = aiming ? -1.25 : -0.3 + Math.sin(phase) * amp * 0.5;
    L.armR.knee.rotation.x = aiming ? -0.45 : -0.35;
    L.armL.hip.rotation.x = aiming ? -1.1 : -0.3 - Math.sin(phase) * amp * 0.5;
    L.armL.knee.rotation.x = aiming ? -0.9 : -0.3;
    L.armL.hip.rotation.z = aiming ? 0.35 : 0;
    this.model.userData.head.rotation.y = 0;
    this.model.position.set(this.pos[0], this.y, this.pos[1]);
    this.model.rotation.y = -this.facing + Math.PI / 2;
  }

  findCover(threat) {
    let best = null, bestScore = -Infinity;
    for (const c of this.d.colliders) {
      if (!c.cover || c.cover < 0.4) continue;
      const cx = (c.min[0] + c.max[0]) / 2, cz = (c.min[1] + c.max[1]) / 2;
      const dToThreat = Math.hypot(cx - threat[0], cz - threat[1]);
      const dToSelf = Math.hypot(cx - this.pos[0], cz - this.pos[1]);
      if (dToSelf > 26 || dToThreat < 6) continue;
      const away = Math.atan2(cz - threat[1], cx - threat[0]);
      const spot = [cx + Math.cos(away) * 1.1, cz + Math.sin(away) * 1.1];
      const score = c.cover * 10 - dToSelf * 0.35 + Math.min(dToThreat, 30) * 0.1;
      if (score > bestScore) { bestScore = score; best = spot; }
    }
    return best;
  }

  takeHit(damage, world) {
    this.health -= damage;
    if (this.health <= 0 && this.alive) {
      this.alive = false;
      this.model.rotation.z = Math.PI / 2.1;
      this.model.position.y = 0.26;
      for (const k of Object.keys(this.model.userData.limbs)) {
        this.model.userData.limbs[k].hip.rotation.x = (Math.random() - 0.5) * 0.9;
        this.model.userData.limbs[k].knee.rotation.x = -Math.random() * 0.7;
      }
      world.onHostileDown(this);
    } else {
      this.awareness = 1;
      this.lastKnown = [world.player.pos.x, world.player.pos.z];
      if (this.state !== 'combat') this.enter('combat');
    }
  }

  drainNoise() { const n = this.noise; this.noise = []; return n; }
}

export class Civilian {
  constructor(spec, district, world) {
    this.spec = spec;
    this.id = spec.id;
    this.d = district;
    this.pos = [spec.home_m[0], spec.home_m[1]];
    this.facing = 0;
    this.state = 'routine';
    this.fear = 0;
    this.model = makeFigure('mat_uniform_civ', spec.id === 'civ_boy_runner' ? 0.78 : 1);
    // civilians are not soldiers: no helmet, no weapon
    const helmet = this.model.children.find((c) => c.geometry?.type === 'SphereGeometry' && c.position.y > 1.5 && c.material === material('mat_metal_dull'));
    if (helmet) this.model.remove(helmet);
    this.model.position.set(this.pos[0], 0, this.pos[1]);
    this.narrativeFlags = new Set(spec.narrative_flags || []);
    this.noise = [];
  }

  scheduledTarget(hour) {
    const h = ((hour % 24) + 24) % 24;
    for (const s of this.spec.schedule) {
      const from = s.from_h, to = s.to_h;
      const inside = from <= to ? (h >= from && h < to) : (h >= from || h < to);
      if (inside) return s;
    }
    return this.spec.schedule[0];
  }

  update(dt, player, world) {
    const slot = this.scheduledTarget(world.localHour);
    const threatNear = world.hostilesInCombat > 0 || world.shotsFired > 0;
    const dPlayer = Math.hypot(player.pos.x - this.pos[0], player.pos.z - this.pos[1]);

    // Civilian priorities are their own: self-preservation, flee, shelter others.
    if (threatNear && this.spec.priority !== 'shelter_others') {
      this.fear = Math.min(1, this.fear + dt * 0.6);
      this.state = this.spec.priority === 'flee_from_danger' ? 'flee' : 'take_cover';
    } else {
      this.fear = Math.max(0, this.fear - dt * 0.12);
      if (this.fear < 0.2) this.state = 'routine';
    }

    if (this.state === 'flee') {
      const away = Math.atan2(this.pos[1] - player.pos.z, this.pos[0] - player.pos.x);
      this.step([this.pos[0] + Math.cos(away) * 8, this.pos[1] + Math.sin(away) * 8], 3.0, dt);
    } else if (this.state === 'take_cover') {
      this.step(this.spec.home_m, 2.1, dt);
    } else {
      const arrived = this.step(slot.at_m, 0.95, dt);
      if (arrived) this.facing += dt * 0.3;
    }

    const phase = world.elapsed * (this.state === 'flee' ? 7.5 : 3.4);
    const amp = this.moving ? (this.state === 'flee' ? 0.55 : 0.26) : 0.015;
    const L = this.model.userData.limbs;
    L.legL.hip.rotation.x = Math.sin(phase) * amp;
    L.legR.hip.rotation.x = -Math.sin(phase) * amp;
    L.legL.knee.rotation.x = Math.max(0, -Math.sin(phase) * amp * 1.2);
    L.legR.knee.rotation.x = Math.max(0, Math.sin(phase) * amp * 1.2);
    L.armL.hip.rotation.x = -Math.sin(phase) * amp * 0.8;
    L.armR.hip.rotation.x = Math.sin(phase) * amp * 0.8;
    this.model.position.set(this.pos[0], 0, this.pos[1]);
    this.model.rotation.y = -this.facing + Math.PI / 2;
    this.canSpeak = dPlayer < 3.2 && this.state === 'routine';
  }

  step(target, speed, dt) {
    const dx = target[0] - this.pos[0], dz = target[1] - this.pos[1];
    const dist = Math.hypot(dx, dz);
    this.moving = dist > 0.4;
    if (!this.moving) return true;
    const s = Math.min(dist, speed * dt);
    let nx = this.pos[0] + dx / dist * s, nz = this.pos[1] + dz / dist * s;
    for (const c of this.d.colliders) {
      if (c.kind === 'roof' || c.kind === 'floor' || c.y1 < 0.6) continue;
      if (c.kind === 'door') { const door = this.d.doors.find((dr) => dr.id === c.doorId); if (door?.passable) continue; }
      const cx = Math.max(c.min[0], Math.min(nx, c.max[0])), cz = Math.max(c.min[1], Math.min(nz, c.max[1]));
      const ox = nx - cx, oz = nz - cz, od = Math.hypot(ox, oz);
      if (od < 0.34 && od > 1e-6) { const p = (0.34 - od) / od; nx += ox * p; nz += oz * p; }
    }
    const moved = Math.hypot(nx - this.pos[0], nz - this.pos[1]);
    this.pos[0] = nx; this.pos[1] = nz;
    this.facing = Math.atan2(dz, dx);
    if (moved > 0.002) {
      this.gait = (this.gait || 0) + moved;
      if (this.gait > 0.7) {
        this.gait = 0;
        const n = movementNoise({ grounded: true, displacement: moved, speed, posture: 'stand', surface: this.d.surfaceAt(nx, nz), loadKg: 4 });
        if (n.loudness > 0) this.noise.push({ ...n, pos: [nx, nz] });
      }
    }
    return false;
  }

  drainNoise() { const n = this.noise; this.noise = []; return n; }
}
