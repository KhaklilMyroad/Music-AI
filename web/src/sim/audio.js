// Audio routing rules (brief §14). This module holds the decisions that must be
// testable without a listening test: voice budget, source priority, reverb and
// obstruction per source, distance behaviour, and the mono fallback.
//
// It does NOT replace human listening. Audio acceptance in the matrix requires
// a person on a phone speaker, ordinary headphones and Bluetooth.

export const BUSES = ['master', 'effects', 'ambience', 'dialogue', 'music'];

/** Priority classes. A prop must never cut off a reload cue or a spoken line. */
export const PRIORITY = {
  dialogue: 100,
  weapon_mechanism: 90,     // reload stages, bolt, magazine
  weapon_shot: 85,
  player_feedback: 80,      // hit, damage, objective
  threat: 70,               // enemy fire, footsteps nearby
  interaction: 60,
  character_foley: 50,
  ambience_zone: 30,
  prop: 10,
};

export const REVERB = {
  rv_open:           { decay: 0.6, wet: 0.08, hf_damp: 0.2 },
  rv_open_hedged:    { decay: 0.9, wet: 0.14, hf_damp: 0.35 },
  rv_dense_foliage:  { decay: 0.5, wet: 0.10, hf_damp: 0.6 },
  rv_room_small:     { decay: 0.7, wet: 0.22, hf_damp: 0.3 },
  rv_room_stone:     { decay: 1.8, wet: 0.34, hf_damp: 0.15 },
  rv_barn:           { decay: 1.4, wet: 0.28, hf_damp: 0.25 },
  rv_chapel:         { decay: 3.2, wet: 0.42, hf_damp: 0.1 },
  rv_bunker:         { decay: 1.1, wet: 0.38, hf_damp: 0.45 },
  rv_attic:          { decay: 0.55, wet: 0.18, hf_damp: 0.5 },
};

/** Distance behaviour per family. A rifle shot has a tail; a footstep does not. */
export const DISTANCE_MODEL = {
  weapon_shot:       { ref_m: 1, max_m: 900, rolloff: 1.1, tail_from_m: 60, distant_layer: true },
  weapon_mechanism:  { ref_m: 1, max_m: 22,  rolloff: 1.6, tail_from_m: null, distant_layer: false },
  explosion:         { ref_m: 1, max_m: 1600, rolloff: 1.0, tail_from_m: 80, distant_layer: true },
  character_foley:   { ref_m: 1, max_m: 28,  rolloff: 1.8, tail_from_m: null, distant_layer: false },
  dialogue:          { ref_m: 1, max_m: 35,  rolloff: 1.3, tail_from_m: null, distant_layer: false },
  prop:              { ref_m: 1, max_m: 18,  rolloff: 2.0, tail_from_m: null, distant_layer: false },
  ambience_zone:     { ref_m: 0, max_m: 0,   rolloff: 0,   tail_from_m: null, distant_layer: false },
};

export class AudioDirector {
  /**
   * @param {object} opts
   * @param {number} opts.maxVoices          hard voice budget for the device tier
   * @param {object} opts.busVolumes         0..1 per bus
   * @param {boolean} opts.mono              collapse to one channel
   * @param {boolean} opts.soundCaptions     emit directional captions for accessibility
   */
  constructor({ maxVoices = 32, busVolumes = {}, mono = false, soundCaptions = false } = {}) {
    this.maxVoices = maxVoices;
    this.busVolumes = { master: 1, effects: 1, ambience: 1, dialogue: 1, music: 1, ...busVolumes };
    this.mono = mono;
    this.soundCaptions = soundCaptions;
    this.active = [];          // { id, family, priority, bus, dist, startedAt }
    this.captions = [];
    this.rejected = [];
  }

  gainFor(family, bus, dist, occlusion = 0) {
    const m = DISTANCE_MODEL[family] || DISTANCE_MODEL.prop;
    let g = 1;
    if (m.max_m > 0) {
      if (dist >= m.max_m) g = 0;
      else g = Math.pow(1 - dist / m.max_m, m.rolloff);
    }
    g *= 1 - Math.min(0.92, occlusion * 0.85);
    g *= (this.busVolumes[bus] ?? 1) * this.busVolumes.master;
    return Math.max(0, Math.min(1, g));
  }

  /**
   * Request a voice. Within budget it plays; over budget it only plays if it can
   * displace a strictly lower-priority voice. Returns what happened and why, so
   * a QA log can show which cue lost and to what.
   */
  play(req, now = 0) {
    const family = req.family;
    const priority = req.priority ?? PRIORITY[family] ?? PRIORITY.prop;
    const bus = req.bus ?? (family === 'dialogue' ? 'dialogue' : family === 'ambience_zone' ? 'ambience' : 'effects');
    const gain = this.gainFor(family, bus, req.dist ?? 0, req.occlusion ?? 0);
    if (gain <= 0.001 && family !== 'ambience_zone') {
      this.rejected.push({ id: req.id, reason: 'inaudible' });
      return { played: false, reason: 'inaudible' };
    }

    if (this.active.length >= this.maxVoices) {
      // Evict the lowest-priority voice; tie-break on the quieter, then the older.
      const sorted = this.active.slice().sort((a, b) => (a.priority - b.priority) || (a.gain - b.gain) || (a.startedAt - b.startedAt));
      const victim = sorted[0];
      if (!victim || victim.priority >= priority) {
        this.rejected.push({ id: req.id, reason: 'voice_budget', blocked_by: victim?.id ?? null });
        return { played: false, reason: 'voice_budget', blocked_by: victim?.id ?? null };
      }
      this.active = this.active.filter((v) => v !== victim);
      this.rejected.push({ id: victim.id, reason: 'evicted_by', by: req.id });
    }

    const voice = {
      id: req.id, family, priority, bus, gain, startedAt: now,
      dist: req.dist ?? 0,
      reverb: REVERB[req.reverb] ?? REVERB.rv_open,
      pan: this.mono ? 0 : (req.pan ?? 0),
      distant_layer: !!(DISTANCE_MODEL[family]?.distant_layer && (req.dist ?? 0) >= (DISTANCE_MODEL[family]?.tail_from_m ?? Infinity)),
    };
    this.active.push(voice);

    // In mono, direction is gone, so an essential cue is captioned instead of lost.
    if (this.mono && req.essential) this.captions.push({ id: req.id, direction: directionWord(req.pan ?? 0), dist: req.dist ?? 0, forced_by: 'mono' });
    else if (this.soundCaptions && req.essential) this.captions.push({ id: req.id, direction: directionWord(req.pan ?? 0), dist: req.dist ?? 0 });

    return { played: true, voice };
  }

  stop(id) { this.active = this.active.filter((v) => v.id !== id); }

  /** Interrupt handling: a phone call or focus loss must leave no orphan voices. */
  onInterruption(kind) {
    const stopped = this.active.map((v) => v.id);
    this.active = [];
    return { kind, stopped, resume_policy: kind === 'phone_call' ? 'resume_ambience_and_music_only' : 'resume_all_positional' };
  }

  /** Repetition guard: the same clip must not fire twice inside its window. */
  static repetitionGuard(windowSeconds = 0.18) {
    const last = new Map();
    return (clipId, now) => {
      const t = last.get(clipId);
      if (t != null && now - t < windowSeconds) return false;
      last.set(clipId, now);
      return true;
    };
  }

  /** Simple peak check so a mix test can fail on clipping without a listening pass. */
  static mixPeak(voices) {
    const sum = voices.reduce((s, v) => s + v.gain * v.gain, 0);
    return Math.sqrt(sum);
  }
}

export function directionWord(pan) {
  if (pan <= -0.6) return 'left';
  if (pan >= 0.6) return 'right';
  if (pan <= -0.2) return 'front_left';
  if (pan >= 0.2) return 'front_right';
  return 'ahead';
}

/** Reverb for a position: which zone the listener is in, not where the source is. */
export function reverbForRoom(roomAmbience) {
  return {
    amb_interior_kitchen: 'rv_room_small', amb_interior_quiet: 'rv_room_small',
    amb_interior_attic: 'rv_attic', amb_interior_barn: 'rv_barn', amb_interior_chapel: 'rv_chapel',
    amb_bocage_field: 'rv_open', amb_bocage_lane: 'rv_open_hedged', amb_bocage_hedge: 'rv_dense_foliage',
    amb_bunker: 'rv_bunker',
  }[roomAmbience] ?? 'rv_open';
}
