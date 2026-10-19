// Weapon runtime: a state machine over the data-driven profile in
// shared-data/weapons.json. The brief's rules that this enforces:
//  * ammunition changes only at the profile's declared insert point
//  * single-round, partial and empty reloads follow the weapon's own rules
//  * interruption (death, mission resolution, weapon switch) follows the
//    declared cancel_policy and never leaves duplicated rounds
//  * availability is checked against date and faction

import { inWindow } from './dates.js';

export const W = { IDLE: 'idle', FIRING: 'firing', CYCLING: 'cycling', RELOADING: 'reloading', EMPTY: 'empty', INTERACTING: 'interacting' };

export function isAvailable(profile, date, faction) {
  return inWindow(date, profile.available_from, profile.available_until) && profile.factions.includes(faction);
}

export class WeaponRuntime {
  constructor(profile, { loaded = null, reserve = 0 } = {}) {
    this.p = profile;
    const cap = profile.magazine?.capacity ?? 0;
    this.capacity = cap;
    this.chamberExtra = !!profile.magazine?.chamber_extra;
    this.loaded = loaded == null ? cap : Math.min(cap + (this.chamberExtra ? 1 : 0), loaded);
    this.reserve = reserve;
    this.state = this.loaded > 0 ? W.IDLE : W.EMPTY;
    this.t = 0;                       // seconds remaining in the current state
    this.reload = null;               // { total, elapsed, inserted, target, kind, pre_count }
    this.events = [];                 // audio/animation events emitted this step
    this.recoil = { pitch: 0, yaw: 0 };
    this.ads = 0;                     // 0..1 aim-down-sight blend
  }

  get maxLoaded() { return this.capacity + (this.chamberExtra ? 1 : 0); }
  get canFire() { return (this.state === W.IDLE || this.state === W.FIRING) && this.loaded > 0; }

  emit(id, data) { this.events.push({ id, ...data }); }
  drainEvents() { const e = this.events; this.events = []; return e; }

  tryFire(rngNext) {
    if (this.state === W.RELOADING) {
      // Firing during a reload cancels it first, per the profile's policy.
      this.cancelReload('fire_input');
    }
    if (this.loaded <= 0) {
      this.state = W.EMPTY;
      this.emit('dry');                 // a trigger pull on an empty weapon always clicks
      return { fired: false, reason: 'empty' };
    }
    if (this.state === W.CYCLING) return { fired: false, reason: 'cycling' };

    this.loaded -= 1;
    this.emit('fire', { remaining: this.loaded });
    const h = this.p.handling;
    const spread = h.rpm_cyclic > 0 ? 1 - 0.6 * this.ads : 1 - 0.75 * this.ads;
    this.recoil.pitch += h.recoil_vertical * (0.85 + 0.3 * rngNext());
    this.recoil.yaw += h.recoil_horizontal * (rngNext() * 2 - 1);
    if (h.rpm_cyclic > 0) { this.state = W.CYCLING; this.t = 60 / h.rpm_cyclic; }
    else { this.state = W.CYCLING; this.t = h.cycle_seconds; this.emit(this.p.class === 'bolt_action_rifle' ? 'bolt_open' : 'slide_cycle'); }
    if (this.loaded === 0) this.emit('last_round');
    return { fired: true, spread, remaining: this.loaded };
  }

  /** kind: 'auto' picks charger vs single based on what the profile supports and how empty it is. */
  startReload(kind = 'auto') {
    if (this.state === W.RELOADING) return { started: false, reason: 'already_reloading' };
    if (!this.p.reload) return { started: false, reason: 'no_reload' };
    if (this.reserve <= 0) return { started: false, reason: 'no_reserve' };
    if (this.loaded >= this.maxLoaded) return { started: false, reason: 'full' };
    const r = this.p.reload;
    const wasEmpty = this.loaded === 0;
    if (!r.supports_partial && !wasEmpty && kind !== 'force') return { started: false, reason: 'partial_not_supported' };

    let chosen = kind;
    if (kind === 'auto') chosen = r.supports_single_round && this.loaded > 0 ? 'single' : 'charger';
    const total = chosen === 'single'
      ? r.single_round_seconds
      : r.charger_seconds + (wasEmpty ? r.empty_penalty_seconds : 0);

    this.reload = { kind: chosen, total, elapsed: 0, inserted: false, pre_count: this.loaded, was_empty: wasEmpty };
    this.state = W.RELOADING;
    this.emit(chosen === 'single' ? 'single_insert_start' : (this.p.magazine.feed === 'detachable_box' ? 'mag_release' : 'bolt_open'));
    return { started: true, kind: chosen, total };
  }

  /** The cancel policy from the profile. Default reverts to the pre-reload count. */
  cancelReload(cause) {
    if (this.state !== W.RELOADING || !this.reload) return { cancelled: false };
    const rl = this.reload;
    const policy = this.p.reload.cancel_policy || 'revert_to_pre_reload_count';
    if (!rl.inserted && policy === 'revert_to_pre_reload_count') {
      this.loaded = rl.pre_count;                 // nothing entered the weapon yet
    }
    // If ammunition was already inserted, it stays inserted and the reserve was
    // already debited; cancelling cannot duplicate or vanish a round.
    this.reload = null;
    this.state = this.loaded > 0 ? W.IDLE : W.EMPTY;
    this.emit('reload_cancelled', { cause, policy, loaded: this.loaded });
    return { cancelled: true, cause, loaded: this.loaded };
  }

  /** Called when the mission ends or the player dies mid-action. */
  interrupt(cause) {
    const out = { cause, cancelled_reload: false };
    if (this.state === W.RELOADING) { this.cancelReload(cause); out.cancelled_reload = true; }
    this.state = this.loaded > 0 ? W.IDLE : W.EMPTY;
    this.t = 0;
    // Any mechanism sound still in flight is stopped: an interrupted action must
    // not keep producing unrelated mechanism audio.
    this.emit('mechanism_audio_stop', { cause });
    return out;
  }

  step(dt, { aiming = false } = {}) {
    const h = this.p.handling;
    this.ads = Math.max(0, Math.min(1, this.ads + (aiming ? dt / Math.max(0.01, h.ads_time) : -dt / Math.max(0.01, h.ads_time))));
    this.recoil.pitch *= Math.max(0, 1 - dt / Math.max(0.01, h.recoil_recovery));
    this.recoil.yaw *= Math.max(0, 1 - dt / Math.max(0.01, h.recoil_recovery));

    if (this.state === W.CYCLING) {
      this.t -= dt;
      if (this.t <= 0) {
        this.t = 0;
        if (this.p.class === 'bolt_action_rifle') this.emit('bolt_close');
        this.state = this.loaded > 0 ? W.IDLE : W.EMPTY;
      }
      return;
    }

    if (this.state === W.RELOADING && this.reload) {
      const rl = this.reload;
      rl.elapsed += dt;
      const frac = rl.elapsed / rl.total;
      // The ammunition count changes exactly at the insert point, never before.
      if (!rl.inserted && frac >= (this.p.reload.insert_point_fraction ?? 0.5)) {
        rl.inserted = true;
        if (rl.kind === 'single') {
          const take = Math.min(1, this.reserve, this.maxLoaded - this.loaded);
          this.loaded += take; this.reserve -= take;
          this.emit('single_insert', { loaded: this.loaded, reserve: this.reserve });
        } else {
          const want = this.maxLoaded - (this.p.magazine.feed === 'detachable_box' ? 0 : this.loaded);
          const target = this.p.magazine.feed === 'detachable_box' ? this.maxLoaded : this.maxLoaded;
          const take = Math.min(Math.max(0, target - this.loaded), this.reserve);
          this.loaded += take; this.reserve -= take;
          this.emit(this.p.magazine.feed === 'detachable_box' ? 'mag_insert' : 'charger_strip', { loaded: this.loaded, reserve: this.reserve });
        }
      }
      if (rl.elapsed >= rl.total) {
        const wasSingle = rl.kind === 'single';
        this.reload = null;
        this.state = this.loaded > 0 ? W.IDLE : W.EMPTY;
        this.emit('reload_complete', { loaded: this.loaded, reserve: this.reserve });
        // A single-round weapon keeps topping up while the player holds reload.
        if (wasSingle && this.loaded < this.maxLoaded && this.reserve > 0) return { chain_single: true };
      }
    }
  }
}

/** Damage with distance falloff. Returns an integer so results are reproducible. */
export function damageAt(profile, distance_m, hitZone = 'torso') {
  const d = profile.damage;
  if (!d) return 0;
  let f = 1;
  if (distance_m > d.falloff_start_m) {
    const t = Math.min(1, (distance_m - d.falloff_start_m) / Math.max(1, d.falloff_end_m - d.falloff_start_m));
    f = 1 - t * (1 - d.falloff_min_factor);
  }
  const zone = { head: 2.6, torso: 1.0, limb: 0.6 }[hitZone] ?? 1.0;
  return Math.round(d.base * f * zone);
}
