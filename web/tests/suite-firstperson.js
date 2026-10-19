import { describe, it, eq, ok, notOk, close, throws } from './runner.js';
import { weapons } from './fixtures.js';
import { WeaponRuntime, isAvailable, damageAt, W } from '../src/sim/weapons.js';
import * as D from '../src/sim/detection.js';
import { makeRng } from '../src/sim/rng.js';

const profile = (id) => weapons.weapons.find((w) => w.id === id);
const r = makeRng(1);
const step = (w, seconds, dt = 1 / 60, opts) => { for (let i = 0; i < Math.round(seconds / dt); i++) w.step(dt, opts); };

export default function run() {

describe('Weapons: availability follows date and faction (brief §7)', () => {
  it('a 1941 weapon is not available in 1939', () => {
    const p = profile('wpn_semi_rifle_us');
    notOk(isAvailable(p, '1939-09-01', 'allied_us_army'));
    ok(isAvailable(p, '1944-06-06', 'allied_us_army'));
  });
  it('a weapon is not available to a faction that never carried it', () => {
    notOk(isAvailable(profile('wpn_semi_rifle_us'), '1944-06-06', 'axis_army'));
    notOk(isAvailable(profile('wpn_bolt_rifle_de'), '1944-06-06', 'french_resistance'));
  });
  it('each weapon class has its own handling, not one shared rifle', () => {
    const sigs = new Set(weapons.weapons.filter((w) => w.class !== 'tool').map((w) => JSON.stringify(w.handling)));
    eq(sigs.size, weapons.weapons.filter((w) => w.class !== 'tool').length, 'two weapons share a handling profile');
  });
  it('each weapon has its own audio event set', () => {
    const sigs = new Set(weapons.weapons.map((w) => JSON.stringify(w.audio_events.sort())));
    eq(sigs.size, weapons.weapons.length, 'two weapons share an audio event set');
  });
});

describe('Weapons: ammunition changes only at the declared insert point (brief §13)', () => {
  it('a magazine reload does not add rounds before the insert point', () => {
    const p = profile('wpn_pistol_civ');
    const w = new WeaponRuntime(p, { loaded: 2, reserve: 20 });
    w.startReload('charger');
    const half = p.reload.insert_point_fraction * p.reload.charger_seconds;
    step(w, half * 0.8);
    eq(w.loaded, 2, 'rounds appeared before the insert point');
    step(w, p.reload.charger_seconds);
    eq(w.loaded, w.maxLoaded, 'the reload did not complete');
    eq(w.loaded + w.reserve, 2 + 20, 'rounds were created or destroyed');
  });

  it('an empty reload takes longer than a partial one', () => {
    const p = profile('wpn_pistol_civ');
    const partial = new WeaponRuntime(p, { loaded: 3, reserve: 20 }).startReload('charger');
    const empty = new WeaponRuntime(p, { loaded: 0, reserve: 20 }).startReload('charger');
    ok(empty.total > partial.total, `${empty.total} should exceed ${partial.total}`);
    close(empty.total - partial.total, p.reload.empty_penalty_seconds, 1e-9);
  });

  it('a clip-fed rifle refuses a partial reload, as its profile declares', () => {
    const p = profile('wpn_semi_rifle_us');
    notOk(p.reload.supports_partial);
    const w = new WeaponRuntime(p, { loaded: 4, reserve: 16 });
    const out = w.startReload('auto');
    notOk(out.started);
    eq(out.reason, 'partial_not_supported');
  });

  it('a bolt-action rifle loads single rounds and chains while reserve lasts', () => {
    const p = profile('wpn_bolt_rifle_de');
    ok(p.reload.supports_single_round);
    const w = new WeaponRuntime(p, { loaded: 2, reserve: 10 });
    w.startReload('auto');
    step(w, p.reload.single_round_seconds + 0.02);
    eq(w.loaded, 3, 'a single round was not inserted');
    eq(w.reserve, 9);
    eq(w.loaded + w.reserve, 12, 'the round count is not conserved');
  });

  it('total rounds are conserved across many random reload interruptions', () => {
    const p = profile('wpn_pistol_civ');
    const rng = makeRng(77);
    const w = new WeaponRuntime(p, { loaded: 8, reserve: 40 });
    const total = w.loaded + w.reserve;
    for (let i = 0; i < 400; i++) {
      const a = rng.int(0, 3);
      if (a === 0) w.tryFire(rng.next);
      else if (a === 1) w.startReload('auto');
      else if (a === 2) w.cancelReload('random');
      else step(w, rng.float(0.01, 0.4));
      const fired = total - (w.loaded + w.reserve);
      ok(fired >= 0, `rounds were created (total now ${w.loaded + w.reserve}, started ${total})`);
    }
    ok(w.loaded + w.reserve <= total, 'rounds were created over a long random session');
  });
});

describe('Weapons: interruption (brief §7, §13, §20)', () => {
  it('death during a reload cancels it and leaves the count correct', () => {
    const p = profile('wpn_pistol_civ');
    const w = new WeaponRuntime(p, { loaded: 3, reserve: 12 });
    const total = w.loaded + w.reserve;
    w.startReload('charger');
    step(w, p.reload.charger_seconds * 0.3);                 // before the insert point
    const out = w.interrupt('player_death');
    ok(out.cancelled_reload);
    eq(w.loaded, 3, 'the cancel policy was not applied');
    eq(w.loaded + w.reserve, total, 'the interruption duplicated or lost rounds');
    eq(w.state, W.IDLE);
  });

  it('an interrupted action stops producing mechanism audio', () => {
    const w = new WeaponRuntime(profile('wpn_bolt_rifle_de'), { loaded: 1, reserve: 5 });
    w.startReload('auto'); w.drainEvents();
    w.interrupt('mission_resolved');
    const ev = w.drainEvents().map((e) => e.id);
    ok(ev.includes('mechanism_audio_stop'), 'no audio stop was issued on interruption');
  });

  it('firing during a reload cancels the reload rather than doing both', () => {
    const p = profile('wpn_smg_resistance');
    const w = new WeaponRuntime(p, { loaded: 5, reserve: 60 });
    w.startReload('charger');
    step(w, 0.2);
    const out = w.tryFire(r.next);
    ok(out.fired);
    eq(w.state, W.CYCLING);
    notOk(w.reload, 'the reload survived a fire input');
  });

  it('an empty weapon reports dry rather than firing', () => {
    const w = new WeaponRuntime(profile('wpn_pistol_civ'), { loaded: 0, reserve: 0 });
    const out = w.tryFire(r.next);
    notOk(out.fired);
    eq(out.reason, 'empty');
    ok(w.drainEvents().some((e) => e.id === 'dry'));
  });

  it('a bolt-action rifle cannot fire again until the bolt has cycled', () => {
    const p = profile('wpn_bolt_rifle_de');
    const w = new WeaponRuntime(p, { loaded: 5, reserve: 10 });
    ok(w.tryFire(r.next).fired);
    notOk(w.tryFire(r.next).fired, 'the bolt rifle fired twice without cycling');
    step(w, p.handling.cycle_seconds + 0.02);
    ok(w.tryFire(r.next).fired);
  });

  it('damage falls off with distance and never rises with it', () => {
    const p = profile('wpn_bolt_rifle_de');
    let last = Infinity;
    for (let d = 0; d <= 500; d += 25) { const v = damageAt(p, d); ok(v <= last, `damage rose at ${d} m`); last = v; }
    ok(damageAt(p, 500) >= Math.round(p.damage.base * p.damage.falloff_min_factor) - 1);
  });

  it('a tool has no damage profile at all', () => {
    for (const t of weapons.weapons.filter((w) => w.class === 'tool')) eq(t.damage, null, `${t.id} can hurt someone`);
  });
});

describe('Stealth: noise comes from real movement (brief §8, §20)', () => {
  it('pushing into a wall makes no footstep', () => {
    const n = D.movementNoise({ grounded: true, displacement: 0.0, speed: 3.2, posture: 'stand', surface: 'surf_cobble', loadKg: 14 });
    eq(n.loudness, 0);
    eq(n.source, 'no_displacement');
  });

  it('moving through the air makes no footstep', () => {
    const n = D.movementNoise({ grounded: false, displacement: 1.2, speed: 4.0, posture: 'stand', surface: 'surf_cobble', loadKg: 14 });
    eq(n.loudness, 0);
    eq(n.source, 'airborne');
  });

  it('surface, posture, speed and load each change the noise', () => {
    const base = { grounded: true, displacement: 0.8, speed: 2.0, posture: 'stand', surface: 'surf_grass', loadKg: 5 };
    const a = D.movementNoise(base).loudness;
    ok(D.movementNoise({ ...base, surface: 'surf_cobble' }).loudness > a, 'surface has no effect');
    ok(D.movementNoise({ ...base, posture: 'crouch' }).loudness < a, 'posture has no effect');
    ok(D.movementNoise({ ...base, speed: 4.5 }).loudness > a, 'speed has no effect');
    ok(D.movementNoise({ ...base, loadKg: 30 }).loudness > a, 'carried load has no effect');
    ok(D.movementNoise({ ...base, posture: 'prone' }).loudness < D.movementNoise({ ...base, posture: 'crouch' }).loudness);
  });

  it('a stationary character generates no continuous equipment rustle', () => {
    const n = D.movementNoise({ grounded: true, displacement: 0, speed: 0, posture: 'stand', surface: 'surf_board_floor', loadKg: 25 });
    eq(n.loudness, 0);
  });

  it('a wall between a noise and a listener attenuates it', () => {
    const noise = { pos: [0, 0], loudness: 0.9, radius_m: 23 };
    const listener = { pos: [8, 0], alertness: 0.4 };
    const open = D.noiseHeard(noise, listener, { acousticOcclusion: () => 0 });
    const walled = D.noiseHeard(noise, listener, { acousticOcclusion: () => 0.9 });
    ok(open.attenuated > walled.attenuated, 'occlusion had no effect');
    ok(open.heard);
  });

  it('a noise beyond its radius is not heard at all', () => {
    const out = D.noiseHeard({ pos: [0, 0], loudness: 0.5, radius_m: 10 }, { pos: [40, 0], alertness: 1 }, {});
    notOk(out.heard);
  });
});

describe('Stealth: detection is not omniscient and not quality-dependent (brief §8, §18)', () => {
  const observer = { pos: [0, 0], facing: 0, fov_rad: Math.PI * 0.55, sight_range: 60, alertness: 0.4, base_acuity: 1.1 };
  const player = (over = {}) => ({ pos: [20, 0], posture: 'stand', light_exposure: 0.8, cover: 0, speed: 1.5, ...over });

  it('an occluded player is not detected regardless of distance', () => {
    const out = D.detectionRate(observer, player(), { hasLineOfSight: () => false });
    eq(out.rate, 0);
    eq(out.blocked_by, 'occlusion');
  });

  it('a player behind the observer is far harder to notice than one in front', () => {
    const front = D.detectionRate(observer, player({ pos: [20, 0] }), {});
    const behind = D.detectionRate(observer, player({ pos: [-20, 0] }), {});
    ok(behind.rate < front.rate * 0.4, `behind ${behind.rate} vs front ${front.rate}`);
  });

  it('darkness, cover and posture each reduce the rate', () => {
    const base = D.detectionRate(observer, player(), {}).rate;
    ok(D.detectionRate(observer, player({ light_exposure: 0.05 }), {}).rate < base, 'light has no effect');
    ok(D.detectionRate(observer, player({ cover: 0.8 }), {}).rate < base, 'cover has no effect');
    ok(D.detectionRate(observer, player({ posture: 'prone' }), {}).rate < base, 'posture has no effect');
    ok(D.detectionRate(observer, player({ speed: 0.1 }), {}).rate < base, 'movement has no effect');
  });

  it('detection accumulates over time instead of triggering instantly', () => {
    const rate = D.detectionRate(observer, player(), {}).rate;
    let a = 0;
    a = D.stepAwareness(a, rate, 1 / 60);
    eq(D.awarenessBand(a), 'unaware', 'one frame of exposure caused detection');
    for (let i = 0; i < 600; i++) a = D.stepAwareness(a, rate, 1 / 60);
    eq(D.awarenessBand(a), 'detected', 'sustained exposure never led to detection');
  });

  it('awareness decays when the player breaks contact', () => {
    let a = 0.7;
    for (let i = 0; i < 300; i++) a = D.stepAwareness(a, 0, 1 / 60);
    eq(D.awarenessBand(a), 'unaware');
  });

  it('there is a suspicious band between unaware and detected, so patrols can investigate', () => {
    eq(D.awarenessBand(0.5), 'suspicious');
    eq(D.awarenessBand(0.2), 'unaware');
    eq(D.awarenessBand(0.9), 'detected');
  });

  it('the detection model takes no rendering parameter, so a quality tier cannot change it', () => {
    const src = D.detectionRate.toString() + D.lightExposure.toString() + D.movementNoise.toString();
    for (const word of ['shadow_quality', 'render_scale', 'quality', 'preset', 'msaa', 'lod_bias', 'ssao']) {
      notOk(src.includes(word), `the stealth model reads a rendering setting: ${word}`);
    }
    const args = D.detectionRate.length;
    eq(args, 3, 'detectionRate signature changed; re-check that no render setting was added');
  });

  it('light exposure is bounded and indoors is darker than open sun', () => {
    const out = D.lightExposure([0, 0], { sun_intensity: 1, indoors: false }, []);
    const inn = D.lightExposure([0, 0], { sun_intensity: 1, indoors: true }, []);
    ok(out > inn);
    ok(D.lightExposure([0, 0], { sun_intensity: 1, indoors: false }, [{ pos: [0, 0], radius: 5, intensity: 9, occluded: false }]) <= 1);
  });

  it('an occluded lamp does not light the player', () => {
    const lit = D.lightExposure([1, 0], { sun_intensity: 0, indoors: true }, [{ pos: [0, 0], radius: 6, intensity: 1, occluded: false }]);
    const dark = D.lightExposure([1, 0], { sun_intensity: 0, indoors: true }, [{ pos: [0, 0], radius: 6, intensity: 1, occluded: true }]);
    ok(lit > dark);
    eq(dark, 0);
  });

  it('the stealth readout is colour-independent and labelled as a model', () => {
    const out = D.stealthReadout(0.8, 0.1, 0.9, 0.5);
    ok(out.visibility.label_key && out.noise.label_key && out.awareness.label_key, 'bands have no text label');
    eq(out.disclaimer_key, 'stealth.model_is_gameplay');
  });
});

}
