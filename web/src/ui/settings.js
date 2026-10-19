// Player settings for the PC edition.
//
// Two rules from the brief are still structural: only categories that actually
// work are exposed, and a visible slider must control its intended output.
// Every entry names the subsystem it drives, and a test asserts each `drives`
// target is consumed somewhere.
//
// What changed from the mobile build: device tiers became GPU presets, the
// touch layout group became an input group with rebinding and mouse
// sensitivity, and each expensive renderer feature is exposed individually
// because the floor GPU has to hold 60 FPS with them off.

const KEY = 'wbtm.settings';

export const PRESETS = ['low', 'medium', 'high', 'ultra', 'custom'];

export const SCHEMA = [
  { group: 'display', id: 'display_mode',  label: 'settings.display_mode',  type: 'enum',  values: ['windowed', 'fullscreen'], def: 'windowed', drives: 'window' },
  { group: 'display', id: 'fps_cap',       label: 'settings.fps_cap',       type: 'enum',  values: ['off', '60', '120', '144'], def: 'off', drives: 'window' },
  { group: 'display', id: 'fov',           label: 'settings.fov',           type: 'range', min: 70, max: 110, step: 1, def: 90, drives: 'player' },

  { group: 'graphics', id: 'preset',         label: 'settings.preset',         type: 'enum',  values: PRESETS, def: 'high', drives: 'renderer' },
  { group: 'graphics', id: 'render_scale',   label: 'settings.render_scale',   type: 'range', min: 0.5, max: 2.0, step: 0.05, def: 1.0, drives: 'renderer' },
  { group: 'graphics', id: 'anti_aliasing',  label: 'settings.anti_aliasing',  type: 'enum',  values: ['off', 'msaa_2x', 'msaa_4x'], def: 'msaa_2x', drives: 'renderer' },
  { group: 'graphics', id: 'shadow_quality', label: 'settings.shadow_quality', type: 'enum',  values: ['off', 'low', 'medium', 'high', 'ultra'], def: 'high', drives: 'renderer' },
  { group: 'graphics', id: 'draw_distance',  label: 'settings.draw_distance',  type: 'range', min: 120, max: 600, step: 20, def: 400, drives: 'renderer' },
  { group: 'graphics', id: 'vegetation',     label: 'settings.vegetation',     type: 'range', min: 0.3, max: 1.0, step: 0.05, def: 1.0, drives: 'renderer' },
  { group: 'graphics', id: 'max_characters', label: 'settings.max_characters', type: 'range', min: 8, max: 48, step: 2, def: 28, drives: 'renderer' },
  { group: 'graphics', id: 'bloom',          label: 'settings.bloom',          type: 'range', min: 0, max: 0.6, step: 0.05, def: 0.15, drives: 'renderer' },

  { group: 'input', id: 'mouse_sensitivity',    label: 'settings.mouse_sensitivity',    type: 'range', min: 0.05, max: 1.5, step: 0.01, def: 0.25, drives: 'player' },
  { group: 'input', id: 'aim_sensitivity_mult', label: 'settings.aim_sensitivity_mult', type: 'range', min: 0.2, max: 1.5, step: 0.05, def: 0.65, drives: 'player' },
  { group: 'input', id: 'invert_y',             label: 'settings.invert_y',             type: 'bool',  def: false, drives: 'player' },
  { group: 'input', id: 'gamepad_look_speed',   label: 'settings.gamepad_look_speed',   type: 'range', min: 0.5, max: 4.0, step: 0.1, def: 2.0, drives: 'player' },
  { group: 'input', id: 'aim_toggle',           label: 'settings.hold_or_toggle',       type: 'enum',  values: ['hold', 'toggle'], def: 'hold', drives: 'input' },
  { group: 'input', id: 'crouch_toggle',        label: 'settings.hold_or_toggle',       type: 'enum',  values: ['toggle', 'hold'], def: 'toggle', drives: 'input' },
  { group: 'input', id: 'prone_toggle',         label: 'settings.hold_or_toggle',       type: 'enum',  values: ['toggle', 'hold'], def: 'toggle', drives: 'input' },
  // Rumble replaces the phone's haptics: it only reaches a connected gamepad,
  // and zero means a player who finds it unpleasant can switch it off.
  { group: 'input', id: 'rumble',               label: 'settings.rumble',               type: 'range', min: 0, max: 1, step: 0.1, def: 0.6, drives: 'player' },

  { group: 'accessibility', id: 'ui_scale',           label: 'settings.ui_scale',            type: 'range', min: 0.8, max: 1.6, step: 0.05, def: 1, drives: 'theme' },
  { group: 'accessibility', id: 'text_scale',         label: 'settings.text_scale',          type: 'range', min: 0.85, max: 1.6, step: 0.05, def: 1, drives: 'theme' },
  { group: 'accessibility', id: 'hud_scale',          label: 'settings.hud_scale',           type: 'range', min: 0.8, max: 1.5, step: 0.05, def: 1, drives: 'theme' },
  { group: 'accessibility', id: 'language',           label: 'settings.language',            type: 'enum',  values: ['en', 'he'], def: 'en', drives: 'i18n' },
  { group: 'accessibility', id: 'high_contrast',      label: 'settings.high_contrast',       type: 'bool', def: false, drives: 'theme' },
  { group: 'accessibility', id: 'colour_independent', label: 'settings.colour_independent',  type: 'bool', def: true, drives: 'hud' },
  { group: 'accessibility', id: 'motion_reduction',   label: 'settings.motion_reduction',    type: 'bool', def: false, drives: 'theme' },
  { group: 'accessibility', id: 'head_bob',           label: 'settings.head_bob',            type: 'range', min: 0, max: 1, step: 0.1, def: 0.7, drives: 'player' },
  { group: 'accessibility', id: 'camera_shake',       label: 'settings.camera_shake',        type: 'range', min: 0, max: 1, step: 0.1, def: 0.6, drives: 'player' },
  { group: 'accessibility', id: 'recoil_presentation',label: 'settings.recoil_presentation', type: 'range', min: 0.2, max: 1, step: 0.1, def: 1, drives: 'player' },
  { group: 'accessibility', id: 'subtitles',          label: 'settings.subtitles',           type: 'bool', def: true, drives: 'hud' },
  { group: 'accessibility', id: 'speaker_names',      label: 'settings.speaker_names',       type: 'bool', def: true, drives: 'hud' },
  { group: 'accessibility', id: 'sound_captions',     label: 'settings.sound_captions',      type: 'bool', def: false, drives: 'audio' },

  { group: 'audio', id: 'vol_master',   label: 'settings.vol_master',   type: 'range', min: 0, max: 1, step: 0.05, def: 0.9, drives: 'audio' },
  { group: 'audio', id: 'vol_effects',  label: 'settings.vol_effects',  type: 'range', min: 0, max: 1, step: 0.05, def: 1, drives: 'audio' },
  { group: 'audio', id: 'vol_ambience', label: 'settings.vol_ambience', type: 'range', min: 0, max: 1, step: 0.05, def: 0.85, drives: 'audio' },
  { group: 'audio', id: 'vol_dialogue', label: 'settings.vol_dialogue', type: 'range', min: 0, max: 1, step: 0.05, def: 1, drives: 'audio' },
  { group: 'audio', id: 'vol_music',    label: 'settings.vol_music',    type: 'range', min: 0, max: 1, step: 0.05, def: 0.6, drives: 'audio' },
  { group: 'audio', id: 'output_mode',  label: 'settings.output_mode',  type: 'enum',  values: ['stereo', 'mono', 'headphones'], def: 'stereo', drives: 'audio' },

  { group: 'content', id: 'intensity', label: 'content.intensity', type: 'enum', values: ['full', 'reduced'], def: 'full', drives: 'content' },
];

// What each preset sets. Touching any individual graphics option moves the
// preset to "custom", so the UI never claims a preset it is not running.
export const PRESET_VALUES = {
  low:    { render_scale: 0.7, anti_aliasing: 'off', shadow_quality: 'low', draw_distance: 160, vegetation: 0.3, max_characters: 10, bloom: 0 },
  medium: { render_scale: 0.85, anti_aliasing: 'msaa_2x', shadow_quality: 'medium', draw_distance: 260, vegetation: 0.6, max_characters: 18, bloom: 0.1 },
  high:   { render_scale: 1.0, anti_aliasing: 'msaa_2x', shadow_quality: 'high', draw_distance: 400, vegetation: 1.0, max_characters: 28, bloom: 0.15 },
  ultra:  { render_scale: 1.0, anti_aliasing: 'msaa_4x', shadow_quality: 'ultra', draw_distance: 600, vegetation: 1.0, max_characters: 40, bloom: 0.2 },
};

export class Settings {
  constructor() {
    this.values = Object.fromEntries(SCHEMA.map((s) => [s.id, s.def]));
    try { Object.assign(this.values, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch { /* defaults */ }
    this.listeners = new Set();
    this._applyingPreset = false;
  }

  get(id) { return this.values[id]; }
  has(id) { return SCHEMA.some((s) => s.id === id); }

  set(id, v) {
    const spec = SCHEMA.find((s) => s.id === id);
    if (!spec) throw new Error(`unknown setting ${id}`);
    if (spec.type === 'range') v = Math.max(spec.min, Math.min(spec.max, Number(v)));
    if (spec.type === 'bool') v = !!v;
    if (spec.type === 'enum' && !spec.values.includes(String(v))) return;
    if (this.values[id] === v) return;
    this.values[id] = v;

    if (spec.group === 'graphics' && id !== 'preset' && !this._applyingPreset) {
      this.values.preset = 'custom';
      for (const fn of this.listeners) fn('preset', 'custom', SCHEMA.find((s) => s.id === 'preset'));
    }
    if (id === 'preset' && v !== 'custom') this.applyPreset(String(v));

    try { localStorage.setItem(KEY, JSON.stringify(this.values)); } catch { /* private mode */ }
    for (const fn of this.listeners) fn(id, v, spec);
  }

  applyPreset(name) {
    const vals = PRESET_VALUES[name];
    if (!vals) return;
    this._applyingPreset = true;
    for (const [k, v] of Object.entries(vals)) {
      this.values[k] = v;
      for (const fn of this.listeners) fn(k, v, SCHEMA.find((s) => s.id === k));
    }
    this._applyingPreset = false;
    try { localStorage.setItem(KEY, JSON.stringify(this.values)); } catch {}
  }

  subscribe(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  groups() { return [...new Set(SCHEMA.map((s) => s.group))]; }
  inGroup(g) { return SCHEMA.filter((s) => s.group === g); }

  applyTheme() {
    const r = document.documentElement;
    r.style.setProperty('--ts', this.get('text_scale') * this.get('ui_scale'));
    r.style.setProperty('--hud', this.get('hud_scale'));
    r.setAttribute('data-contrast', this.get('high_contrast') ? 'high' : 'normal');
    r.setAttribute('data-motion', this.get('motion_reduction') ? 'reduced' : 'full');
    r.setAttribute('data-colour-independent', this.get('colour_independent') ? 'on' : 'off');
  }

  audioOptions() {
    const mode = this.get('output_mode');
    return {
      busVolumes: {
        master: this.get('vol_master'), effects: this.get('vol_effects'),
        ambience: this.get('vol_ambience'), dialogue: this.get('vol_dialogue'), music: this.get('vol_music'),
      },
      mono: mode === 'mono',
      headphones: mode === 'headphones',
      soundCaptions: this.get('sound_captions'),
      maxVoices: { low: 32, medium: 48, high: 64, ultra: 96 }[this.get('preset')] ?? 64,
    };
  }

  rendererOptions() {
    const shadow = this.get('shadow_quality');
    return {
      preset: this.get('preset'),
      // On PC the device pixel ratio is not a budget: the player's render scale is.
      pixelRatioCap: 2.0,
      renderScale: this.get('render_scale'),
      msaa: this.get('anti_aliasing'),
      shadows: shadow !== 'off',
      shadowMapSize: { off: 0, low: 1024, medium: 2048, high: 4096, ultra: 8192 }[shadow] ?? 4096,
      fogDensity: 0.004,
      drawDistance: this.get('draw_distance'),
      vegetationDensity: this.get('vegetation'),
      maxActiveCharacters: this.get('max_characters'),
      bloom: this.get('bloom'),
      fov: this.get('fov'),
      frameTarget: this.get('fps_cap') === 'off' ? 0 : Number(this.get('fps_cap')),
    };
  }
}
