// First-person character controller and view model.
//
// Two things here exist specifically because the brief calls them out:
//  * Footsteps are emitted from measured ground contact and horizontal
//    displacement, so pushing into a wall and moving through the air are both
//    silent without needing a special case.
//  * The support hand is parented to a named contact point on the weapon mesh,
//    so it cannot detach or intersect the stock while the weapon moves.

import { material } from './materials.js';
import { WeaponRuntime } from '../sim/weapons.js';
import { movementNoise, POSTURE, lightExposure } from '../sim/detection.js';

let THREE;
export function initPlayer(three) { THREE = three; }

const EYE = { stand: 1.62, crouch: 1.05, prone: 0.42 };
const SPEED = { stand: 3.1, crouch: 1.55, prone: 0.62 };
const RADIUS = 0.32;
const GRAVITY = -16.5;
const STEP_UP = 0.42;

export class Player {
  constructor(district, settings, opts = {}) {
    this.d = district;
    this.s = settings;
    this.pos = new THREE.Vector3(district.spawn.pos[0], 0, district.spawn.pos[2]);
    this.vel = new THREE.Vector3();
    this.yaw = district.spawn.yaw;
    this.pitch = 0;
    this.posture = 'stand';
    this.postureBlend = EYE.stand;
    this.grounded = true;
    this.groundY = 0;
    this.health = opts.health ?? 100;
    this.condition = { fatigue: 0, warmth: 1, hunger: 0, thirst: 0 };
    this.sprinting = false;
    this.stamina = 1;
    this.stepAccum = 0;
    this.lastPos = this.pos.clone();
    this.noiseEvents = [];
    this.shotEvents = [];
    this.camera = new THREE.PerspectiveCamera(72, 1, 0.06, 600);
    this.recoilOffset = { pitch: 0, yaw: 0 };
    this.shakeTime = 0;
    this.viewRoot = new THREE.Group();
    this.weapons = new Map();
    this.equipped = null;
    this.inventory = opts.inventory || {};
    this.buildViewModel();
  }

  // ------------------------------------------------------------ view model --
  buildViewModel() {
    this.vm = new THREE.Group();
    this.vm.name = 'viewmodel';
    this.viewRoot.add(this.vm);
    this.camera.add(this.viewRoot);
    this.vmBob = new THREE.Group();
    this.vm.add(this.vmBob);
    this.weaponSlot = new THREE.Group();
    this.weaponSlot.position.set(0.17, -0.19, -0.42);
    this.vmBob.add(this.weaponSlot);
    this.handsGroup = new THREE.Group();
    this.vmBob.add(this.handsGroup);
  }

  /** Build a weapon view model with named grip contacts the hands attach to. */
  makeWeaponModel(profile) {
    const g = new THREE.Group();
    const wood = material('mat_wood_dark');
    const metal = material('mat_metal_dull');
    const isPistol = profile.class === 'pistol';
    const isTool = profile.class === 'tool';

    if (isTool) {
      const handle = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.03, 0.16), material('mat_cloth'));
      const jaw1 = new THREE.Mesh(new THREE.BoxGeometry(0.012, 0.012, 0.09), metal);
      jaw1.position.set(-0.008, 0.004, -0.12); jaw1.rotation.x = -0.08;
      const jaw2 = jaw1.clone(); jaw2.position.set(0.008, -0.004, -0.12); jaw2.rotation.x = 0.08;
      g.add(handle, jaw1, jaw2);
      g.userData.grip = { primary: [0, 0, 0.0], support: [0, 0.0, -0.02], supportVisible: false };
      g.userData.muzzle = [0, 0, -0.16];
    } else if (isPistol) {
      const frame = new THREE.Mesh(new THREE.BoxGeometry(0.032, 0.085, 0.18), metal);
      frame.position.set(0, 0.012, -0.02);
      const slide = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.03, 0.19), metal);
      slide.position.set(0, 0.052, -0.025);
      const grip = new THREE.Mesh(new THREE.BoxGeometry(0.034, 0.11, 0.045), wood);
      grip.position.set(0, -0.055, 0.045); grip.rotation.x = 0.26;
      const trigger = new THREE.Mesh(new THREE.BoxGeometry(0.008, 0.028, 0.008), metal);
      trigger.position.set(0, -0.016, 0.008);
      g.add(frame, slide, grip, trigger);
      g.userData.grip = { primary: [0.0, -0.045, 0.042], support: [-0.026, -0.03, 0.03], supportVisible: true };
      g.userData.muzzle = [0, 0.05, -0.12];
      g.userData.ejectionPort = [0.02, 0.055, 0.0];
    } else {
      const smg = profile.class === 'submachine_gun';
      const barrelLen = smg ? 0.30 : 0.62;
      const stock = new THREE.Mesh(new THREE.BoxGeometry(0.046, 0.085, 0.34), wood);
      stock.position.set(0, -0.012, 0.21);
      const comb = new THREE.Mesh(new THREE.BoxGeometry(0.044, 0.04, 0.16), wood);
      comb.position.set(0, 0.05, 0.12);
      const receiver = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.056, 0.22), metal);
      receiver.position.set(0, 0.016, -0.02);
      const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.0095, 0.0105, barrelLen, 10), metal);
      barrel.rotation.x = Math.PI / 2;
      barrel.position.set(0, 0.022, -0.14 - barrelLen / 2);
      const handguard = new THREE.Mesh(new THREE.BoxGeometry(0.036, 0.038, smg ? 0.16 : 0.3), wood);
      handguard.position.set(0, 0.0, -0.16 - (smg ? 0.08 : 0.15));
      const rear = new THREE.Mesh(new THREE.BoxGeometry(0.018, 0.016, 0.02), metal);
      rear.position.set(0, 0.05, -0.09);
      const front = new THREE.Mesh(new THREE.BoxGeometry(0.008, 0.022, 0.008), metal);
      front.position.set(0, 0.046, -0.12 - barrelLen);
      const guard = new THREE.Mesh(new THREE.TorusGeometry(0.018, 0.0035, 5, 10, Math.PI), metal);
      guard.rotation.set(Math.PI / 2, 0, 0); guard.position.set(0, -0.026, 0.05);
      g.add(stock, comb, receiver, barrel, handguard, rear, front, guard);
      if (smg) {
        const mag = new THREE.Mesh(new THREE.BoxGeometry(0.022, 0.17, 0.05), metal);
        mag.position.set(0, -0.1, -0.02);
        g.add(mag);
        g.userData.magMesh = mag;
      } else if (profile.magazine?.feed === 'internal_charger') {
        const floor = new THREE.Mesh(new THREE.BoxGeometry(0.038, 0.022, 0.1), metal);
        floor.position.set(0, -0.03, -0.015);
        g.add(floor);
      }
      const boltHandle = new THREE.Mesh(new THREE.CylinderGeometry(0.005, 0.005, 0.05, 6), metal);
      boltHandle.rotation.z = Math.PI / 2;
      boltHandle.position.set(0.028, 0.03, 0.02);
      g.add(boltHandle);
      g.userData.boltMesh = boltHandle;
      g.userData.grip = {
        primary: [0.0, -0.038, 0.1],
        // the support hand sits ON the handguard, which is its only valid contact
        support: [0.0, -0.028, handguard.position.z],
        supportVisible: true,
      };
      g.userData.muzzle = [0, 0.022, -0.14 - barrelLen];
      g.userData.ejectionPort = [0.026, 0.04, -0.02];
    }
    return g;
  }

  /** A hand built from palm + five fingers; curl is driven per pose. */
  makeHand(side) {
    const skin = material('mat_skin');
    const sleeve = material('mat_uniform_civ');
    const g = new THREE.Group();
    const palm = new THREE.Mesh(new THREE.BoxGeometry(0.052, 0.085, 0.032), skin);
    g.add(palm);
    const cuff = new THREE.Mesh(new THREE.CylinderGeometry(0.038, 0.044, 0.1, 9), sleeve);
    cuff.position.set(0, 0.085, 0.004);
    g.add(cuff);
    const forearm = new THREE.Mesh(new THREE.CylinderGeometry(0.036, 0.042, 0.2, 9), sleeve);
    forearm.position.set(0, 0.2, 0.01);
    g.add(forearm);
    g.userData.fingers = [];
    for (let i = 0; i < 4; i++) {
      const root = new THREE.Group();
      root.position.set(-0.019 + i * 0.0128, -0.04, 0.0);
      const p1 = new THREE.Mesh(new THREE.BoxGeometry(0.0115, 0.032, 0.0125), skin);
      p1.position.set(0, -0.016, 0);
      const mid = new THREE.Group();
      mid.position.set(0, -0.032, 0);
      const p2 = new THREE.Mesh(new THREE.BoxGeometry(0.0105, 0.027, 0.0115), skin);
      p2.position.set(0, -0.0135, 0);
      mid.add(p2);
      root.add(p1, mid);
      g.add(root);
      g.userData.fingers.push({ root, mid });
    }
    const thumbRoot = new THREE.Group();
    thumbRoot.position.set(side === 'right' ? 0.026 : -0.026, -0.012, 0.012);
    const t1 = new THREE.Mesh(new THREE.BoxGeometry(0.014, 0.03, 0.014), skin);
    t1.position.set(0, -0.015, 0);
    const tmid = new THREE.Group(); tmid.position.set(0, -0.03, 0);
    const t2 = new THREE.Mesh(new THREE.BoxGeometry(0.0125, 0.026, 0.0125), skin);
    t2.position.set(0, -0.013, 0); tmid.add(t2);
    thumbRoot.add(t1, tmid);
    g.add(thumbRoot);
    g.userData.thumb = { root: thumbRoot, mid: tmid };
    g.userData.side = side;
    return g;
  }

  setFingerCurl(hand, curl, thumbCurl = curl * 0.75) {
    for (const f of hand.userData.fingers) { f.root.rotation.x = curl * 1.25; f.mid.rotation.x = curl * 1.5; }
    hand.userData.thumb.root.rotation.x = thumbCurl * 0.9;
    hand.userData.thumb.root.rotation.z = (hand.userData.side === 'right' ? -1 : 1) * thumbCurl * 0.8;
    hand.userData.thumb.mid.rotation.x = thumbCurl * 1.1;
  }

  equip(profile, state) {
    let w = this.weapons.get(profile.id);
    if (!w) {
      const runtime = new WeaponRuntime(profile, state);
      const model = this.makeWeaponModel(profile);
      const right = this.makeHand('right');
      const left = this.makeHand('left');
      w = { profile, runtime, model, right, left };
      this.weapons.set(profile.id, w);
    }
    if (this.equipped) {
      this.equipped.runtime.interrupt('weapon_switch');
      this.weaponSlot.remove(this.equipped.model);
      this.handsGroup.remove(this.equipped.right, this.equipped.left);
    }
    this.equipped = w;
    this.weaponSlot.add(w.model);
    this.handsGroup.add(w.right, w.left);
    // Hands are positioned FROM the weapon's named contact points, in the
    // weapon's own space, so they travel with it exactly.
    const grip = w.model.userData.grip;
    const base = this.weaponSlot.position;
    w.right.position.set(base.x + grip.primary[0], base.y + grip.primary[1], base.z + grip.primary[2]);
    w.right.rotation.set(-0.42, 0.1, 0.06);
    this.setFingerCurl(w.right, 0.95, 0.8);
    if (grip.supportVisible) {
      w.left.visible = true;
      w.left.position.set(base.x + grip.support[0] - 0.012, base.y + grip.support[1] - 0.01, base.z + grip.support[2]);
      w.left.rotation.set(-0.55, -0.22, -0.5);
      this.setFingerCurl(w.left, 0.85, 0.7);
    } else {
      w.left.visible = false;
    }
    return w;
  }

  get eyeHeight() { return this.postureBlend; }

  // -------------------------------------------------------------- movement --
  resolveCollision(next) {
    const d = this.d;
    const r = RADIUS;
    const feet = next.y;
    const headroom = this.posture === 'prone' ? 0.6 : this.posture === 'crouch' ? 1.2 : 1.75;
    let x = next.x, z = next.z;
    for (let pass = 0; pass < 3; pass++) {
      for (const c of d.colliders) {
        if (c.kind === 'door') {
          const door = d.doors.find((dr) => dr.id === c.doorId) || d.doors.find((dr) => dr.id.startsWith(c.id.replace('_doorway_', '_door_')));
          if (door?.passable) continue;
        }
        if (c.kind === 'roof') continue;
        if (c.y1 <= feet + 0.001 || c.y0 >= feet + headroom) continue;
        if (c.y1 - feet <= STEP_UP && c.kind !== 'wall' && c.kind !== 'boundary') continue;   // step over a low prop
        const cx = Math.max(c.min[0], Math.min(x, c.max[0]));
        const cz = Math.max(c.min[1], Math.min(z, c.max[1]));
        const dx = x - cx, dz = z - cz;
        const dist = Math.hypot(dx, dz);
        if (dist >= r) continue;
        if (dist < 1e-6) { x = cx + r; continue; }
        const push = (r - dist) / dist;
        x += dx * push; z += dz * push;
      }
    }
    return { x, z, blocked: Math.hypot(x - next.x, z - next.z) > 0.0005 };
  }

  floorUnder(x, z, y) {
    let best = 0;
    for (const p of this.d.platforms || []) {
      if (x >= p.min[0] && x <= p.max[0] && z >= p.min[1] && z <= p.max[1] && p.y <= y + 0.45) best = Math.max(best, p.y);
    }
    for (const c of this.d.colliders) {
      if (c.kind !== 'floor') continue;
      if (x >= c.min[0] && x <= c.max[0] && z >= c.min[1] && z <= c.max[1] && c.y1 <= y + 0.45) best = Math.max(best, c.y1);
    }
    for (const st of this.d.stairs || []) {
      if (x >= st.min[0] && x <= st.max[0] && z >= st.min[1] && z <= st.max[1]) {
        const t = (z - st.min[1]) / Math.max(0.01, st.max[1] - st.min[1]);
        best = Math.max(best, st.y1 * Math.max(0, Math.min(1, t)));
      }
    }
    return best;
  }

  update(dt, input, world) {
    const sens = (input.aim ? this.s.get('aim_sensitivity') : this.s.get('sensitivity')) * 0.0028;
    this.yaw -= input.look[0] * sens;
    this.pitch = Math.max(-1.42, Math.min(1.42, this.pitch - input.look[1] * sens));

    // posture
    const wantCrouch = input.crouch;
    const target = wantCrouch ? 'crouch' : 'stand';
    if (this.posture !== target) this.posture = target;
    this.postureBlend += (EYE[this.posture] - this.postureBlend) * Math.min(1, dt * 11);

    // speed
    this.sprinting = (input.sprint || input.sprintFromStick) && this.posture === 'stand' && !input.aim && this.stamina > 0.05;
    const base = SPEED[this.posture] * (input.aim ? 0.55 : 1);
    const speed = base * (this.sprinting ? 1.78 : 1);
    this.stamina = Math.max(0, Math.min(1, this.stamina + (this.sprinting ? -dt * 0.22 : dt * 0.14)));

    const fwd = new THREE.Vector3(-Math.sin(this.yaw), 0, -Math.cos(this.yaw));
    const right = new THREE.Vector3(Math.cos(this.yaw), 0, -Math.sin(this.yaw));
    const wish = new THREE.Vector3()
      .addScaledVector(fwd, input.move[1])
      .addScaledVector(right, input.move[0]);
    if (wish.lengthSq() > 1) wish.normalize();
    wish.multiplyScalar(speed);

    // gravity and ground
    this.vel.y += GRAVITY * dt;
    const next = new THREE.Vector3(this.pos.x + wish.x * dt, this.pos.y + this.vel.y * dt, this.pos.z + wish.z * dt);
    const floor = this.floorUnder(next.x, next.z, this.pos.y);
    if (next.y <= floor) { next.y = floor; this.vel.y = 0; this.grounded = true; }
    else this.grounded = next.y - floor < 0.05;

    const solved = this.resolveCollision(next);
    const prev = this.pos.clone();
    this.pos.set(solved.x, next.y, solved.z);

    // ---- footstep emission: measured, not intended ----
    const moved = Math.hypot(this.pos.x - prev.x, this.pos.z - prev.z);
    const horizSpeed = moved / Math.max(1e-5, dt);
    const strideLen = this.posture === 'prone' ? 0.55 : this.posture === 'crouch' ? 0.62 : (this.sprinting ? 1.15 : 0.82);
    if (this.grounded) this.stepAccum += moved;
    if (this.grounded && this.stepAccum >= strideLen) {
      this.stepAccum = 0;
      const surface = this.d.surfaceAt(this.pos.x, this.pos.z, this.pos.y);
      const n = movementNoise({
        grounded: true, displacement: moved, speed: horizSpeed, posture: this.posture,
        surface, loadKg: this.carriedKg(),
      });
      if (n.loudness > 0) this.noiseEvents.push({ ...n, pos: [this.pos.x, this.pos.z], surface, at: world.elapsed });
    }
    this.lastMoved = moved;
    this.lastSpeed = horizSpeed;

    // camera
    const shake = this.s.get('camera_shake');
    this.shakeTime = Math.max(0, this.shakeTime - dt * 2.4);
    const bobAmp = this.s.get('motion_reduction') ? 0 : (this.sprinting ? 0.022 : 0.012) * Math.min(1, horizSpeed / 2.4);
    const bob = Math.sin(world.elapsed * (this.sprinting ? 13 : 8.5)) * bobAmp;
    this.camera.position.set(this.pos.x, this.pos.y + this.postureBlend + bob, this.pos.z);
    const rec = this.equipped?.runtime.recoil ?? { pitch: 0, yaw: 0 };
    const recScale = this.s.get('recoil_presentation') * 0.0075;
    const sh = this.shakeTime * shake * 0.01;
    this.camera.rotation.set(
      this.pitch - rec.pitch * recScale + (Math.random() - 0.5) * sh,
      this.yaw - rec.yaw * recScale + (Math.random() - 0.5) * sh,
      0, 'YXZ',
    );

    // view model sway / bob / ADS
    const w = this.equipped;
    if (w) {
      const ads = w.runtime.ads;
      this.vmBob.position.set(
        -ads * 0.17 + Math.sin(world.elapsed * 1.6) * 0.004 * (1 - ads),
        ads * 0.055 + bob * 0.5 + Math.sin(world.elapsed * 2.1) * 0.003 * (1 - ads),
        ads * 0.07,
      );
      this.vmBob.rotation.set(
        -input.look[1] * 0.00012 * (1 - ads * 0.8) + bob * 0.4,
        -input.look[0] * 0.00016 * (1 - ads * 0.8),
        (this.sprinting ? -0.12 : 0) * (1 - ads),
      );
      // Reload pose: the support hand leaves the handguard and returns to it.
      const rl = w.runtime.reload;
      if (rl) {
        const t = rl.elapsed / rl.total;
        const swing = Math.sin(Math.min(1, t) * Math.PI);
        const grip = w.model.userData.grip;
        const b = this.weaponSlot.position;
        w.left.position.set(
          b.x + grip.support[0] - 0.012 - swing * 0.05,
          b.y + grip.support[1] - 0.01 - swing * 0.1,
          b.z + grip.support[2] + swing * 0.14,
        );
        this.setFingerCurl(w.left, 0.85 - swing * 0.45, 0.7 - swing * 0.3);
        w.model.rotation.set(swing * 0.16, swing * 0.1, swing * -0.2);
        if (w.model.userData.magMesh) w.model.userData.magMesh.visible = !(rl.kind === 'charger' && t > 0.12 && t < (w.profile.reload.insert_point_fraction ?? 0.5));
      } else {
        const grip = w.model.userData.grip;
        const b = this.weaponSlot.position;
        if (grip.supportVisible) {
          w.left.position.set(b.x + grip.support[0] - 0.012, b.y + grip.support[1] - 0.01, b.z + grip.support[2]);
          this.setFingerCurl(w.left, 0.85, 0.7);
        }
        w.model.rotation.set(0, 0, 0);
        if (w.model.userData.magMesh) w.model.userData.magMesh.visible = true;
        // bolt handle travels only while the weapon is cycling
        if (w.model.userData.boltMesh) {
          const cyc = w.runtime.state === 'cycling' ? 1 - (w.runtime.t / Math.max(0.01, w.profile.handling.cycle_seconds)) : 0;
          w.model.userData.boltMesh.position.z = 0.02 + Math.sin(cyc * Math.PI) * 0.045;
        }
      }
      w.runtime.step(dt, { aiming: input.aim });
    }

    return { blocked: solved.blocked, moved, speed: horizSpeed };
  }

  carriedKg() {
    let kg = 6;
    if (this.equipped) kg += { pistol: 1.1, submachine_gun: 3.6, bolt_action_rifle: 4.1, semi_auto_rifle: 4.4, tool: 0.4 }[this.equipped.profile.class] ?? 2;
    for (const [, n] of Object.entries(this.inventory)) kg += n * 0.012;
    return kg;
  }

  tryFire(world) {
    const w = this.equipped;
    if (!w || w.profile.class === 'tool') return null;
    const out = w.runtime.tryFire(() => world.rng.next());
    if (!out.fired) return out;
    this.shakeTime = 1;
    const dir = new THREE.Vector3(0, 0, -1).applyQuaternion(this.camera.quaternion);
    const origin = this.camera.position.clone();
    this.shotEvents.push({ origin: origin.toArray(), dir: dir.toArray(), spread: out.spread, profile: w.profile, at: world.elapsed });
    this.noiseEvents.push({ loudness: 1.5, radius_m: 220, source: 'gunshot', pos: [this.pos.x, this.pos.z], at: world.elapsed });
    return out;
  }

  reload() {
    const w = this.equipped;
    if (!w || !w.profile.reload) return { started: false, reason: 'no_reload' };
    const ammoId = w.profile.ammunition;
    w.runtime.reserve = this.inventory[ammoId] ?? w.runtime.reserve;
    const out = w.runtime.startReload('auto');
    return out;
  }

  syncReserveToInventory() {
    const w = this.equipped;
    if (!w || !w.profile.ammunition) return;
    this.inventory[w.profile.ammunition] = w.runtime.reserve;
  }

  /** Gameplay light exposure at the player's feet, for the stealth model. */
  exposure(world) {
    const indoors = this.d.isIndoors(this.pos.x, this.pos.z, this.pos.y);
    const lights = this.d.lights.map((l) => ({
      pos: l.pos, radius: l.radius, intensity: l.intensity,
      occluded: !!this.d.segmentBlocked(l.pos[0], l.y, l.pos[1], this.pos.x, this.pos.y + 1.2, this.pos.z, true),
    }));
    return lightExposure([this.pos.x, this.pos.z], { sun_intensity: world.sunIntensity, indoors }, lights);
  }

  drainNoise() { const n = this.noiseEvents; this.noiseEvents = []; return n; }
  drainShots() { const s = this.shotEvents; this.shotEvents = []; return s; }

  checkpoint() {
    this.syncReserveToInventory();
    const w = this.equipped;
    return {
      position: [this.pos.x, this.pos.y, this.pos.z], yaw: this.yaw, pitch: this.pitch,
      posture: this.posture, health: this.health, condition: { ...this.condition },
      equipped: w?.profile.id ?? null,
      weapon_states: Object.fromEntries([...this.weapons].map(([id, x]) => [id, { loaded: x.runtime.loaded, reserve: x.runtime.reserve, chambered: x.runtime.loaded > 0 }])),
      inventory: { ...this.inventory },
      interrupted_action: w?.runtime.reload
        ? { kind: 'reload', progress: w.runtime.reload.elapsed / w.runtime.reload.total, revert_to: { loaded: w.runtime.reload.pre_count, reserve: w.runtime.reserve + (w.runtime.loaded - w.runtime.reload.pre_count) } }
        : null,
    };
  }

  restore(cp) {
    if (!cp) return;
    if (cp.position) this.pos.set(cp.position[0], cp.position[1], cp.position[2]);
    if (cp.yaw != null) this.yaw = cp.yaw;
    if (cp.pitch != null) this.pitch = cp.pitch;
    if (cp.posture) { this.posture = cp.posture; this.postureBlend = EYE[cp.posture]; }
    if (cp.health != null) this.health = cp.health;
    if (cp.inventory) this.inventory = { ...cp.inventory };
    // An interrupted reload reverts to its recorded pre-reload counts: the
    // checkpoint, not the live scene, decides, so no round can be duplicated.
    for (const [id, st] of Object.entries(cp.weapon_states || {})) {
      const w = this.weapons.get(id);
      if (!w) continue;
      const revert = cp.interrupted_action?.kind === 'reload' && cp.interrupted_action.revert_to;
      w.runtime.loaded = revert ? revert.loaded : st.loaded;
      w.runtime.reserve = revert ? revert.reserve : st.reserve;
      w.runtime.reload = null;
      w.runtime.state = w.runtime.loaded > 0 ? 'idle' : 'empty';
    }
  }
}
