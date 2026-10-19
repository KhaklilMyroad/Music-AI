// Stealth: visibility and noise (brief §8).
//
// Deliberate design choices, each one a line in the acceptance matrix:
//  * The model reads ONLY gameplay inputs. Render scale, shadow quality and
//    post-processing are not parameters, so a lower quality tier cannot change
//    whether the player is concealed or illuminated.
//  * Light exposure is a calibrated gameplay number in 0..1. It is not a
//    photometric measurement and the HUD never claims it is one.
//  * A footstep requires ground contact AND horizontal displacement, so pushing
//    into a wall or moving through the air produces no footsteps.

export const POSTURE = {
  stand:  { profile: 1.00, noise_scale: 1.00, speed: 1.00 },
  crouch: { profile: 0.58, noise_scale: 0.45, speed: 0.55 },
  prone:  { profile: 0.30, noise_scale: 0.18, speed: 0.22 },
};

export const SURFACE_NOISE = {
  surf_grass: 0.55, surf_crop: 0.70, surf_dirt_track: 0.75, surf_cobble: 1.00,
  surf_packed_earth: 0.80, surf_board_floor: 0.95, surf_stone_floor: 1.00,
  surf_hedge_base: 0.85, surf_gravel: 1.15, surf_water_shallow: 1.25, surf_rubble: 1.20,
};

/** Equipment adds a floor to movement noise: a loaded pack cannot be silent. */
export function carriedNoise(loadKg) { return Math.min(0.5, loadKg * 0.012); }

/**
 * Light exposure at a point, 0 (dark) to 1 (fully lit). Inputs are the
 * gameplay light list, not the renderer's.
 * @param {{sun_intensity:number, indoors:boolean}} ambient
 * @param {Array<{pos:[number,number], radius:number, intensity:number, occluded:boolean}>} lights
 */
export function lightExposure(point, ambient, lights) {
  let e = ambient.indoors ? ambient.sun_intensity * 0.25 : ambient.sun_intensity;
  for (const l of lights) {
    if (l.occluded) continue;
    const dx = point[0] - l.pos[0], dz = point[1] - l.pos[1];
    const d = Math.hypot(dx, dz);
    if (d >= l.radius) continue;
    const falloff = 1 - d / l.radius;
    e += l.intensity * falloff * falloff;
  }
  return Math.max(0, Math.min(1, e));
}

/**
 * Chance-per-second that an observer notices the player, before accumulation.
 * Returns the rate and the breakdown, so the HUD indicator and the debug view
 * can both explain WHY risk is high rather than showing a bare bar.
 */
export function detectionRate(observer, player, world) {
  const dx = player.pos[0] - observer.pos[0], dz = player.pos[1] - observer.pos[1];
  const dist = Math.hypot(dx, dz);
  const post = POSTURE[player.posture] || POSTURE.stand;

  if (dist > observer.sight_range) return { rate: 0, blocked_by: 'range', dist, factors: {} };
  if (world.hasLineOfSight && !world.hasLineOfSight(observer.pos, player.pos, player.posture)) {
    return { rate: 0, blocked_by: 'occlusion', dist, factors: {} };
  }

  // Angle from the observer's facing. Attention falls off outside the cone
  // instead of snapping to zero, so peripheral movement still matters.
  const toPlayer = Math.atan2(dz, dx);
  let delta = Math.abs(normaliseAngle(toPlayer - observer.facing));
  const half = observer.fov_rad / 2;
  const angleFactor = delta <= half ? 1 : Math.max(0, 1 - (delta - half) / (Math.PI - half)) * 0.35;
  if (angleFactor <= 0) return { rate: 0, blocked_by: 'facing', dist, factors: {} };

  const distanceFactor = Math.max(0.05, 1 - (dist / observer.sight_range) ** 1.4);
  const lightFactor = 0.18 + 0.82 * player.light_exposure;     // never fully invisible in the open
  const coverFactor = 1 - Math.min(0.9, player.cover);          // 0..1, from the tile/prop the player is behind
  const motionFactor = 0.45 + 0.55 * Math.min(1, player.speed / 3.2);
  const profileFactor = post.profile;
  const alert = 0.6 + 1.4 * observer.alertness;                 // 0..1 alertness -> 0.6..2.0

  const rate = observer.base_acuity * alert * angleFactor * distanceFactor * lightFactor * coverFactor * motionFactor * profileFactor;
  return {
    rate: Math.max(0, rate),
    blocked_by: null, dist,
    factors: { angleFactor, distanceFactor, lightFactor, coverFactor, motionFactor, profileFactor, alert },
  };
}

/**
 * Accumulating awareness. Detection is never instant and never omniscient:
 * awareness rises while the player is observable and decays when not.
 * 0..0.4 unaware, 0.4..0.75 suspicious (investigate), >=0.75 detected.
 */
export function stepAwareness(current, rate, dt, decayPerSecond = 0.22) {
  const next = rate > 0 ? current + rate * dt : current - decayPerSecond * dt;
  return Math.max(0, Math.min(1, next));
}
export function awarenessBand(a) { return a >= 0.75 ? 'detected' : a >= 0.4 ? 'suspicious' : 'unaware'; }

/**
 * Noise emitted by a movement step. `grounded` and `displacement` come from the
 * character controller, which is why wall-pushing and airborne movement are
 * silent by construction rather than by a special case.
 */
export function movementNoise({ grounded, displacement, speed, posture, surface, loadKg, interaction }) {
  if (interaction) {
    return { loudness: interaction.loudness, radius_m: interaction.loudness * 26, source: interaction.id };
  }
  if (!grounded) return { loudness: 0, radius_m: 0, source: 'airborne' };
  if (displacement < 0.06) return { loudness: 0, radius_m: 0, source: 'no_displacement' };
  const post = POSTURE[posture] || POSTURE.stand;
  const surf = SURFACE_NOISE[surface] ?? 0.8;
  const speedTerm = Math.min(1.25, 0.35 + speed / 3.6);
  const loudness = Math.max(0, Math.min(1.5, surf * post.noise_scale * speedTerm + carriedNoise(loadKg)));
  return { loudness: Math.round(loudness * 1000) / 1000, radius_m: Math.round(loudness * 26 * 10) / 10, source: 'footstep' };
}

/** Does a noise reach an observer? Walls dampen; a doorway transmits. */
export function noiseHeard(noise, listener, world) {
  if (noise.loudness <= 0) return { heard: false, attenuated: 0 };
  const d = Math.hypot(listener.pos[0] - noise.pos[0], listener.pos[1] - noise.pos[1]);
  if (d > noise.radius_m) return { heard: false, attenuated: 0 };
  const occl = world.acousticOcclusion ? world.acousticOcclusion(noise.pos, listener.pos) : 0;
  const level = noise.loudness * (1 - d / noise.radius_m) * (1 - occl * 0.75);
  const threshold = 0.08 + 0.12 * (1 - listener.alertness);
  return { heard: level >= threshold, attenuated: Math.round(level * 1000) / 1000, occlusion: occl };
}

/** Player-facing stealth readout. Colour-independent: bands are words plus a bar. */
export function stealthReadout(lightExposureValue, cover, noise, awareness) {
  const vis = Math.max(0, Math.min(1, lightExposureValue * (1 - Math.min(0.9, cover))));
  const band = (v) => (v < 0.25 ? 'low' : v < 0.6 ? 'medium' : 'high');
  return {
    visibility: { value: Math.round(vis * 100) / 100, band: band(vis), label_key: `stealth.visibility.${band(vis)}` },
    noise: { value: Math.round(Math.min(1, noise / 1.2) * 100) / 100, band: band(Math.min(1, noise / 1.2)), label_key: `stealth.noise.${band(Math.min(1, noise / 1.2))}` },
    awareness: { value: Math.round(awareness * 100) / 100, band: awarenessBand(awareness), label_key: `stealth.awareness.${awarenessBand(awareness)}` },
    // Explicit: this is a gameplay model, not a measurement.
    disclaimer_key: 'stealth.model_is_gameplay',
  };
}

function normaliseAngle(a) { while (a > Math.PI) a -= 2 * Math.PI; while (a < -Math.PI) a += 2 * Math.PI; return a; }
