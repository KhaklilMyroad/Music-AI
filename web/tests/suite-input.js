import { describe, it, eq, ok, notOk, close } from './runner.js';
import { DEFAULT_BINDINGS, undeclaredClashes } from '../src/ui/desktop-input.js';
import { SCHEMA, PRESET_VALUES, PRESETS, Settings } from '../src/ui/settings.js';
import fs from 'node:fs';

const readSource = (rel) => fs.readFileSync(new URL(`../${rel}`, import.meta.url), 'utf8');

/** Minimal localStorage stand-in, so Settings can be exercised under node. */
function withStorage(fn) {
  const store = new Map();
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
  };
  try { return fn(); } finally { delete globalThis.localStorage; }
}

export default function run() {

describe('PC input: the default binding table (brief §10, restated for PC)', () => {
  it('has no undeclared clash within a context', () => {
    const clashes = undeclaredClashes();
    eq(clashes, [], `clashing bindings: ${clashes.map((c) => `${c.a}+${c.b} on ${c.code}`).join(', ')}`);
  });

  it('gives every action at least one binding', () => {
    for (const [action, b] of Object.entries(DEFAULT_BINDINGS)) {
      const n = (b.codes ?? []).length + (b.mouse ?? []).length + (b.wheel ? 1 : 0);
      ok(n > 0, `${action} has no binding at all`);
    }
  });

  it('reuses a key across contexts only where the contexts cannot both be live', () => {
    // Space is traverse in a mission and end-turn on the map; that is the
    // point of contexts, and it must stay allowed.
    eq(DEFAULT_BINDINGS.traverse.context, 'fps');
    eq(DEFAULT_BINDINGS.end_turn.context, 'map');
    ok(DEFAULT_BINDINGS.traverse.codes.includes('Space'));
    ok(DEFAULT_BINDINGS.end_turn.codes.includes('Space'));
  });

  it('keeps movement on the left hand and the camera on the mouse', () => {
    for (const a of ['move_forward', 'move_back', 'move_left', 'move_right']) {
      ok((DEFAULT_BINDINGS[a].codes ?? []).some((c) => c.startsWith('Key')), `${a} has no letter key`);
    }
    eq(DEFAULT_BINDINGS.fire.mouse, [0]);
    eq(DEFAULT_BINDINGS.aim.mouse, [2]);
  });

  it('every bound action names a localisation key for the rebinding screen', () => {
    for (const [action, b] of Object.entries(DEFAULT_BINDINGS)) {
      ok(typeof b.label === 'string' && b.label.startsWith('input.'), `${action} has no input.* label`);
    }
  });

  it('exposes the PC verbs the touch build could not: prone, lean and hold breath', () => {
    for (const a of ['prone', 'lean_left', 'lean_right', 'hold_breath']) {
      ok(DEFAULT_BINDINGS[a], `${a} is not bound`);
    }
  });
});

describe('PC settings: presets and schema (brief §11, restated for PC)', () => {
  it('every preset fully describes the graphics state', () => {
    const gfx = SCHEMA.filter((s) => s.group === 'graphics' && s.id !== 'preset').map((s) => s.id);
    for (const [name, vals] of Object.entries(PRESET_VALUES)) {
      const missing = gfx.filter((id) => !(id in vals));
      eq(missing, [], `the ${name} preset does not set ${missing}`);
    }
  });

  it('presets are ordered by cost, so "low" is never heavier than "ultra"', () => {
    const order = ['low', 'medium', 'high', 'ultra'];
    for (let i = 1; i < order.length; i++) {
      const a = PRESET_VALUES[order[i - 1]], b = PRESET_VALUES[order[i]];
      ok(a.draw_distance <= b.draw_distance, `${order[i - 1]} draws further than ${order[i]}`);
      ok(a.max_characters <= b.max_characters, `${order[i - 1]} allows more characters than ${order[i]}`);
      ok(a.vegetation <= b.vegetation, `${order[i - 1]} has denser vegetation than ${order[i]}`);
    }
  });

  it('changing one graphics option moves the preset to custom rather than lying', () => withStorage(() => {
    const s = new Settings();
    eq(s.get('preset'), 'high');
    s.set('shadow_quality', 'low');
    eq(s.get('preset'), 'custom', 'the preset still claimed to be "high"');
  }));

  it('choosing a preset applies all of its values at once', () => withStorage(() => {
    const s = new Settings();
    s.set('preset', 'low');
    for (const [k, v] of Object.entries(PRESET_VALUES.low)) eq(s.get(k), v, `preset did not apply ${k}`);
    eq(s.get('preset'), 'low', 'applying a preset marked itself custom');
  }));

  it('changing a non-graphics setting leaves the preset alone', () => withStorage(() => {
    const s = new Settings();
    s.set('mouse_sensitivity', 0.5);
    eq(s.get('preset'), 'high', 'an input setting invalidated the graphics preset');
  }));

  it('"custom" is offered but is not a preset anyone can apply', () => {
    ok(PRESETS.includes('custom'));
    notOk('custom' in PRESET_VALUES, 'custom has preset values, which makes it a real preset');
  });

  it('render scale can exceed 1, because supersampling is a PC option', () => {
    const spec = SCHEMA.find((s) => s.id === 'render_scale');
    ok(spec.max > 1, `render scale caps at ${spec.max}, so PC players cannot supersample`);
  });

  it('every setting names the subsystem it drives, and every target is real', () => {
    const known = ['renderer', 'window', 'player', 'input', 'theme', 'hud', 'audio', 'i18n', 'content'];
    for (const s of SCHEMA) ok(known.includes(s.drives), `${s.id} drives unknown target "${s.drives}"`);
  });

  it('no module reads a setting the schema does not define', () => {
    // This caught `haptics`: the PC schema dropped it, but the touch layer and
    // the damage feedback still read it, so both were silently dead.
    const ids = new Set(SCHEMA.map((s) => s.id));
    const files = [
      'src/app.js', 'src/fps/player.js', 'src/fps/mission.js',
      'src/ui/touch.js', 'src/ui/desktop-input.js', 'src/strategic/map-view.js',
    ];
    const unknown = [];
    for (const rel of files) {
      const src = readSource(rel);
      // \b matters: without it `this.pois.get('poi_x')` reads as a settings call.
      for (const m of src.matchAll(/(?:\bsettings|\bthis\.s|\bthis\.settings)\.get\(['"]([a-z_]+)['"]\)/g)) {
        if (!ids.has(m[1])) unknown.push(`${rel}: ${m[1]}`);
      }
    }
    eq(unknown, [], `settings read but never defined: ${unknown.join(', ')}`);
  });

  it('the accessibility group kept everything the mobile build had', () => {
    const ids = SCHEMA.filter((s) => s.group === 'accessibility').map((s) => s.id);
    for (const required of ['text_scale', 'hud_scale', 'high_contrast', 'colour_independent',
      'motion_reduction', 'camera_shake', 'recoil_presentation', 'subtitles', 'speaker_names', 'sound_captions']) {
      ok(ids.includes(required), `accessibility lost ${required} in the move to PC`);
    }
  });

  it('mono output survived the platform change, and gained a headphone mode', () => withStorage(() => {
    const s = new Settings();
    s.set('output_mode', 'mono');
    ok(s.audioOptions().mono, 'mono no longer reaches the audio director');
    s.set('output_mode', 'headphones');
    ok(s.audioOptions().headphones);
    notOk(s.audioOptions().mono);
  }));

  it('the audio voice budget rises with the preset, as PC headroom allows', () => withStorage(() => {
    const s = new Settings();
    s.set('preset', 'low');
    const low = s.audioOptions().maxVoices;
    s.set('preset', 'ultra');
    ok(s.audioOptions().maxVoices > low, `voice budget did not rise: ${low}`);
    ok(low >= 32, `a PC floor of ${low} voices is below the mobile ceiling`);
  }));
});

}
