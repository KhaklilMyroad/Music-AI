// Player settings. Two rules from the brief are structural here:
//  * only categories that actually work are exposed
//  * a visible slider must control its intended output
// Every setting therefore names the subsystem it drives, and the shell asserts
// at startup that each one is consumed somewhere.

const KEY = 'wbtm.settings';

export const SCHEMA = [
  { group: 'graphics', id: 'quality',        label: 'settings.quality',          type: 'enum', values: ['low', 'balanced', 'high'], def: 'balanced', drives: 'renderer' },
  { group: 'graphics', id: 'frame_target',   label: 'settings.frame_target',     type: 'enum', values: ['30', '60'], def: '60', drives: 'renderer' },
  { group: 'graphics', id: 'render_scale',   label: 'settings.render_scale',     type: 'range', min: 0.6, max: 1.0, step: 0.05, def: 0.9, drives: 'renderer' },
  { group: 'graphics', id: 'high_contrast',  label: 'settings.high_contrast',    type: 'bool', def: false, drives: 'theme' },

  { group: 'display',  id: 'text_scale',     label: 'settings.text_scale',       type: 'range', min: 0.85, max: 1.6, step: 0.05, def: 1, drives: 'theme' },
  { group: 'display',  id: 'hud_scale',      label: 'settings.hud_scale',        type: 'range', min: 0.8, max: 1.5, step: 0.05, def: 1, drives: 'theme' },
  { group: 'display',  id: 'language',       label: 'settings.language',         type: 'enum', values: ['en', 'he'], def: 'en', drives: 'i18n' },
  { group: 'display',  id: 'colour_independent', label: 'settings.colour_independent', type: 'bool', def: true, drives: 'hud' },

  { group: 'camera',   id: 'sensitivity',    label: 'settings.sensitivity',      type: 'range', min: 0.3, max: 3.0, step: 0.1, def: 1.2, drives: 'player' },
  { group: 'camera',   id: 'aim_sensitivity', label: 'settings.aim_sensitivity', type: 'range', min: 0.2, max: 2.0, step: 0.1, def: 0.7, drives: 'player' },
  { group: 'camera',   id: 'invert_y',       label: 'settings.invert_y',         type: 'bool', def: false, drives: 'player' },
  { group: 'camera',   id: 'gyro',           label: 'settings.gyro',             type: 'bool', def: false, drives: 'player' },
  { group: 'camera',   id: 'aim_assist',     label: 'settings.aim_assist',       type: 'enum', values: ['off', 'light', 'strong'], def: 'light', drives: 'player' },
  { group: 'camera',   id: 'camera_shake',   label: 'settings.camera_shake',     type: 'range', min: 0, max: 1, step: 0.1, def: 0.6, drives: 'player' },
  { group: 'camera',   id: 'recoil_presentation', label: 'settings.recoil_presentation', type: 'range', min: 0.2, max: 1, step: 0.1, def: 1, drives: 'player' },
  { group: 'camera',   id: 'motion_reduction', label: 'settings.motion_reduction', type: 'bool', def: false, drives: 'theme' },

  { group: 'controls', id: 'left_handed',    label: 'settings.left_handed',      type: 'bool', def: false, drives: 'touch' },
  { group: 'controls', id: 'stick_size',     label: 'settings.stick_size',       type: 'range', min: 0.8, max: 1.5, step: 0.05, def: 1, drives: 'touch' },
  { group: 'controls', id: 'stick_mode',     label: 'settings.stick_mode',       type: 'enum', values: ['floating', 'fixed'], def: 'floating', drives: 'touch' },
  { group: 'controls', id: 'aim_toggle',     label: 'settings.hold_or_toggle',   type: 'enum', values: ['hold', 'toggle'], def: 'hold', drives: 'touch' },
  { group: 'controls', id: 'crouch_toggle',  label: 'settings.hold_or_toggle',   type: 'enum', values: ['toggle', 'hold'], def: 'toggle', drives: 'touch' },
  { group: 'controls', id: 'haptics',        label: 'settings.haptics',          type: 'bool', def: true, drives: 'touch' },

  { group: 'audio',    id: 'vol_master',     label: 'settings.vol_master',       type: 'range', min: 0, max: 1, step: 0.05, def: 0.9, drives: 'audio' },
  { group: 'audio',    id: 'vol_effects',    label: 'settings.vol_effects',      type: 'range', min: 0, max: 1, step: 0.05, def: 1, drives: 'audio' },
  { group: 'audio',    id: 'vol_ambience',   label: 'settings.vol_ambience',     type: 'range', min: 0, max: 1, step: 0.05, def: 0.85, drives: 'audio' },
  { group: 'audio',    id: 'vol_dialogue',   label: 'settings.vol_dialogue',     type: 'range', min: 0, max: 1, step: 0.05, def: 1, drives: 'audio' },
  { group: 'audio',    id: 'vol_music',      label: 'settings.vol_music',        type: 'range', min: 0, max: 1, step: 0.05, def: 0.6, drives: 'audio' },
  { group: 'audio',    id: 'mono',           label: 'settings.mono',             type: 'bool', def: false, drives: 'audio' },
  { group: 'audio',    id: 'subtitles',      label: 'settings.subtitles',        type: 'bool', def: true, drives: 'hud' },
  { group: 'audio',    id: 'speaker_names',  label: 'settings.speaker_names',    type: 'bool', def: true, drives: 'hud' },
  { group: 'audio',    id: 'sound_captions', label: 'settings.sound_captions',   type: 'bool', def: false, drives: 'audio' },

  { group: 'content',  id: 'intensity',      label: 'content.intensity',         type: 'enum', values: ['full', 'reduced'], def: 'full', drives: 'content' },
];

export class Settings {
  constructor() {
    this.values = Object.fromEntries(SCHEMA.map((s) => [s.id, s.def]));
    try { Object.assign(this.values, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch { /* defaults */ }
    this.listeners = new Set();
  }
  get(id) { return this.values[id]; }
  set(id, v) {
    const spec = SCHEMA.find((s) => s.id === id);
    if (!spec) throw new Error(`unknown setting ${id}`);
    if (spec.type === 'range') v = Math.max(spec.min, Math.min(spec.max, Number(v)));
    if (spec.type === 'bool') v = !!v;
    if (spec.type === 'enum' && !spec.values.includes(String(v))) return;
    this.values[id] = v;
    try { localStorage.setItem(KEY, JSON.stringify(this.values)); } catch { /* private mode */ }
    for (const fn of this.listeners) fn(id, v, spec);
  }
  subscribe(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  groups() { return [...new Set(SCHEMA.map((s) => s.group))]; }
  inGroup(g) { return SCHEMA.filter((s) => s.group === g); }

  /** Apply the settings that drive the document theme. */
  applyTheme() {
    const r = document.documentElement;
    r.style.setProperty('--ts', this.get('text_scale'));
    r.style.setProperty('--hud', this.get('hud_scale'));
    r.setAttribute('data-contrast', this.get('high_contrast') ? 'high' : 'normal');
    r.setAttribute('data-motion', this.get('motion_reduction') ? 'reduced' : 'full');
    r.setAttribute('data-colour-independent', this.get('colour_independent') ? 'on' : 'off');
  }

  audioOptions() {
    return {
      busVolumes: { master: this.get('vol_master'), effects: this.get('vol_effects'), ambience: this.get('vol_ambience'), dialogue: this.get('vol_dialogue'), music: this.get('vol_music') },
      mono: this.get('mono'), soundCaptions: this.get('sound_captions'),
      maxVoices: { low: 16, balanced: 24, high: 32 }[this.get('quality')] ?? 24,
    };
  }

  rendererOptions() {
    const q = this.get('quality');
    return {
      quality: q,
      pixelRatioCap: { low: 1.0, balanced: 1.5, high: 2.0 }[q],
      renderScale: this.get('render_scale'),
      shadows: q !== 'low',
      shadowMapSize: { low: 0, balanced: 1024, high: 2048 }[q],
      fogDensity: { low: 0.012, balanced: 0.008, high: 0.006 }[q],
      vegetationDensity: { low: 0.4, balanced: 0.75, high: 1.0 }[q],
      frameTarget: Number(this.get('frame_target')),
      maxActiveCharacters: { low: 6, balanced: 10, high: 14 }[q],
    };
  }
}
