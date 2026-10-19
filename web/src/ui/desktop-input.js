// PC input: pointer-locked mouse look, keyboard movement, rebindable actions,
// and gamepad as an alternative. Produces the same per-frame snapshot shape the
// touch layer did, so the mission scene did not change when the platform did.
//
// Pointer lock is requested on a deliberate click rather than automatically:
// browsers refuse it outside a user gesture, and a game that grabs the cursor
// without being asked is a game people cannot leave.

const STORE = 'wbtm.bindings';

// Default bindings. `context` groups them for the rebinding screen and lets the
// conflict check allow the same key in two contexts never active at once.
export const DEFAULT_BINDINGS = {
  move_forward: { context: 'fps', codes: ['KeyW', 'ArrowUp'], label: 'input.move_forward' },
  move_back:    { context: 'fps', codes: ['KeyS', 'ArrowDown'], label: 'input.move_back' },
  move_left:    { context: 'fps', codes: ['KeyA', 'ArrowLeft'], label: 'input.move_left' },
  move_right:   { context: 'fps', codes: ['KeyD', 'ArrowRight'], label: 'input.move_right' },
  sprint:       { context: 'fps', codes: ['ShiftLeft', 'ShiftRight'], label: 'input.sprint' },
  crouch:       { context: 'fps', codes: ['ControlLeft', 'KeyC'], label: 'input.crouch' },
  prone:        { context: 'fps', codes: ['KeyZ'], label: 'input.prone' },
  traverse:     { context: 'fps', codes: ['Space'], label: 'input.traverse' },
  lean_left:    { context: 'fps', codes: ['KeyQ'], label: 'input.lean_left' },
  lean_right:   { context: 'fps', codes: ['KeyX'], label: 'input.lean_right' },
  fire:         { context: 'fps', mouse: [0], label: 'input.fire' },
  aim:          { context: 'fps', mouse: [2], label: 'input.aim' },
  reload:       { context: 'fps', codes: ['KeyR'], label: 'input.reload' },
  interact:     { context: 'fps', codes: ['KeyE', 'KeyF'], label: 'input.interact' },
  hold_breath:  { context: 'fps', codes: ['AltLeft'], label: 'input.hold_breath' },
  weapon_next:  { context: 'fps', codes: ['Digit2'], wheel: 1, label: 'input.weapon_next' },
  weapon_prev:  { context: 'fps', codes: ['Digit1'], wheel: -1, label: 'input.weapon_prev' },
  journal:      { context: 'shared', codes: ['KeyJ'], label: 'input.journal' },
  map:          { context: 'shared', codes: ['KeyM', 'Tab'], label: 'input.map' },
  pause:        { context: 'shared', codes: ['Escape'], label: 'input.pause' },
  quick_save:   { context: 'shared', codes: ['F5'], label: 'input.quick_save' },
  end_turn:     { context: 'map', codes: ['Space'], label: 'input.end_turn' },
};

export class DesktopInput {
  constructor(settings, i18n, { surface = document.body } = {}) {
    this.s = settings;
    this.i18n = i18n;
    this.surface = surface;
    this.bindings = structuredClone(DEFAULT_BINDINGS);
    this.loadOverrides();

    this.down = new Set();        // currently held codes
    this.mouseDown = new Set();
    this.pressedCodes = new Set();// one-shot, drained per frame
    this.look = { dx: 0, dy: 0 };
    this.wheel = 0;
    this.locked = false;
    this.toggled = new Set();
    this.gamepadIndex = null;
    this.onPointerLockChange = () => {};
    this.bind();
  }

  // ------------------------------------------------------------ bindings --
  loadOverrides() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORE) || '{}');
      for (const [action, b] of Object.entries(saved)) {
        // A binding for an action this build dropped is ignored, not applied.
        if (this.bindings[action]) Object.assign(this.bindings[action], b);
      }
    } catch { /* defaults */ }
  }

  saveOverrides() {
    const out = {};
    for (const [action, b] of Object.entries(this.bindings)) {
      const d = DEFAULT_BINDINGS[action];
      if (JSON.stringify(b.codes ?? []) !== JSON.stringify(d.codes ?? []) || JSON.stringify(b.mouse ?? []) !== JSON.stringify(d.mouse ?? [])) {
        out[action] = { codes: b.codes, mouse: b.mouse };
      }
    }
    try { localStorage.setItem(STORE, JSON.stringify(out)); } catch { /* private mode */ }
  }

  /** Actions that would clash. Different non-shared contexts never clash. */
  conflictsFor(action, code) {
    const ctx = this.bindings[action]?.context ?? 'shared';
    return Object.entries(this.bindings)
      .filter(([other, b]) => {
        if (other === action) return false;
        const oc = b.context ?? 'shared';
        if (oc !== ctx && oc !== 'shared' && ctx !== 'shared') return false;
        return (b.codes ?? []).includes(code);
      })
      .map(([other]) => other);
  }

  /** Rebind to a single key. Taking a key from another action removes it there. */
  rebind(action, code, { allowConflict = false } = {}) {
    if (!this.bindings[action]) return { ok: false, reason: 'unknown_action' };
    const clashes = this.conflictsFor(action, code);
    if (clashes.length && !allowConflict) return { ok: false, reason: 'conflict', conflicts: clashes };
    for (const other of clashes) {
      this.bindings[other].codes = (this.bindings[other].codes ?? []).filter((c) => c !== code);
    }
    this.bindings[action].codes = [code];
    this.saveOverrides();
    return { ok: true, conflicts: clashes };
  }

  resetBindings() {
    this.bindings = structuredClone(DEFAULT_BINDINGS);
    try { localStorage.removeItem(STORE); } catch {}
  }

  /** Readable binding text for the rebinding screen and the control hints. */
  bindingText(action) {
    const b = this.bindings[action] ?? {};
    const parts = [...(b.codes ?? []).map((c) => prettyCode(c)), ...(b.mouse ?? []).map((m) => ['Mouse 1', 'Mouse 3', 'Mouse 2'][m] ?? `Mouse ${m + 1}`)];
    if (b.wheel) parts.push(b.wheel > 0 ? 'Wheel down' : 'Wheel up');
    return parts.length ? parts.join(' / ') : this.i18n.t('input.unbound');
  }

  held(action) {
    const b = this.bindings[action] ?? {};
    if ((b.codes ?? []).some((c) => this.down.has(c))) return true;
    if ((b.mouse ?? []).some((m) => this.mouseDown.has(m))) return true;
    return false;
  }

  justPressed(action) {
    const b = this.bindings[action] ?? {};
    return (b.codes ?? []).some((c) => this.pressedCodes.has(c));
  }

  // --------------------------------------------------------------- events --
  bind() {
    addEventListener('keydown', (e) => {
      // Never swallow the browser's own shortcuts while the cursor is free.
      if (e.code === 'Tab' || (this.locked && e.code === 'F5')) e.preventDefault();
      if (this.down.has(e.code)) return;      // ignore auto-repeat
      this.down.add(e.code);
      this.pressedCodes.add(e.code);
    });
    addEventListener('keyup', (e) => this.down.delete(e.code));
    addEventListener('blur', () => { this.down.clear(); this.mouseDown.clear(); });

    this.surface.addEventListener('mousedown', (e) => {
      if (!this.locked) return;
      e.preventDefault();
      this.mouseDown.add(e.button);
    });
    addEventListener('mouseup', (e) => this.mouseDown.delete(e.button));
    this.surface.addEventListener('contextmenu', (e) => { if (this.locked) e.preventDefault(); });

    addEventListener('mousemove', (e) => {
      if (!this.locked) return;
      // Relative motion only. No acceleration, no smoothing: 1:1 aiming.
      this.look.dx += e.movementX ?? 0;
      this.look.dy += e.movementY ?? 0;
    });

    this.surface.addEventListener('wheel', (e) => {
      if (!this.locked) return;
      e.preventDefault();
      this.wheel += Math.sign(e.deltaY);
    }, { passive: false });

    document.addEventListener('pointerlockchange', () => {
      this.locked = document.pointerLockElement === this.surface;
      if (!this.locked) { this.down.clear(); this.mouseDown.clear(); }
      this.onPointerLockChange(this.locked);
    });
    document.addEventListener('pointerlockerror', () => {
      this.locked = false;
      this.onPointerLockChange(false);
    });

    addEventListener('gamepadconnected', (e) => { this.gamepadIndex = e.gamepad.index; });
    addEventListener('gamepaddisconnected', () => { this.gamepadIndex = null; });
  }

  /** Must be called from a user gesture, or the browser refuses. */
  async capture() {
    if (this.locked) return true;
    try {
      // unadjustedMovement asks the browser to skip OS pointer acceleration.
      await this.surface.requestPointerLock?.({ unadjustedMovement: true });
      return true;
    } catch {
      try { this.surface.requestPointerLock?.(); return true; } catch { return false; }
    }
  }

  release() { if (this.locked) document.exitPointerLock?.(); }

  // -------------------------------------------------------------- sampling --
  pad() {
    if (this.gamepadIndex == null) return null;
    const gp = navigator.getGamepads?.()[this.gamepadIndex];
    return gp && gp.connected ? gp : null;
  }

  sample(dt = 1 / 60) {
    const dz = 0.2;
    const gp = this.pad();
    const ax = (i) => { const v = gp?.axes?.[i] ?? 0; return Math.abs(v) < dz ? 0 : v; };
    const btn = (i) => !!gp?.buttons?.[i]?.pressed;

    let mx = (this.held('move_right') ? 1 : 0) - (this.held('move_left') ? 1 : 0) + ax(0);
    let my = (this.held('move_forward') ? 1 : 0) - (this.held('move_back') ? 1 : 0) - ax(1);
    const len = Math.hypot(mx, my);
    if (len > 1) { mx /= len; my /= len; }

    const sens = this.s.get('mouse_sensitivity');
    const look = [this.look.dx * sens, this.look.dy * sens];
    // Gamepad look is a rate, so it is scaled by dt and reported separately:
    // touching both devices in one frame must not double the sensitivity.
    const lookRate = [ax(2) * this.s.get('gamepad_look_speed') * 220 * dt, ax(3) * this.s.get('gamepad_look_speed') * 220 * dt];
    this.look.dx = 0; this.look.dy = 0;

    const toggleMode = (action) => this.s.get(`${action}_toggle`) === 'toggle';
    const posture = (action, padBtn) => {
      const raw = this.held(action) || btn(padBtn);
      if (!toggleMode(action)) return raw;
      if (this.justPressed(action) || (padBtn != null && btn(padBtn) && !this._padPrev?.[padBtn])) {
        this.toggled.has(action) ? this.toggled.delete(action) : this.toggled.add(action);
      }
      return this.toggled.has(action);
    };

    const pressed = new Set();
    for (const action of Object.keys(this.bindings)) {
      if (this.justPressed(action)) pressed.add(action);
    }
    const wheelDir = this.wheel; this.wheel = 0;
    if (wheelDir > 0) pressed.add('weapon_next');
    if (wheelDir < 0) pressed.add('weapon_prev');
    if (btn(2)) pressed.add('reload');
    if (btn(3)) pressed.add('interact');

    const out = {
      move: [mx, my],
      look,
      lookRate,
      fire: this.held('fire') || btn(7),
      aim: this.held('aim') || btn(6),
      crouch: posture('crouch', 1),
      prone: posture('prone', 11),
      sprint: this.held('sprint') || btn(10),
      holdBreath: this.held('hold_breath'),
      lean: (this.held('lean_right') ? 1 : 0) - (this.held('lean_left') ? 1 : 0),
      interactHeld: this.held('interact') || btn(3),
      pressed,
      sprintFromStick: Math.hypot(ax(0), ax(1)) > 0.92,
      locked: this.locked,
    };
    this._padPrev = gp ? gp.buttons.map((b) => b.pressed) : null;
    this.pressedCodes.clear();
    return out;
  }

  /** Control hints for the HUD: the keys that actually do something now. */
  hints(actions) {
    return actions
      .filter((a) => this.bindings[a])
      .map((a) => ({ action: a, key: this.bindingText(a), label: this.i18n.t(this.bindings[a].label) }));
  }
}

function prettyCode(code) {
  if (code.startsWith('Key')) return code.slice(3);
  if (code.startsWith('Digit')) return code.slice(5);
  if (code.startsWith('Arrow')) return { ArrowUp: '↑', ArrowDown: '↓', ArrowLeft: '←', ArrowRight: '→' }[code];
  return {
    ShiftLeft: 'Shift', ShiftRight: 'R Shift', ControlLeft: 'Ctrl', ControlRight: 'R Ctrl',
    AltLeft: 'Alt', AltRight: 'R Alt', Space: 'Space', Escape: 'Esc', Tab: 'Tab',
  }[code] ?? code;
}

/** Undeclared clashes in the default table, so a binding bug fails a test. */
export function undeclaredClashes(table = DEFAULT_BINDINGS) {
  const seen = new Map();
  const out = [];
  // Escape pauses a mission and backs out of a menu; declared, not discovered.
  const shares = (a, b) => (a === 'pause' && b === 'cancel') || (a === 'cancel' && b === 'pause');
  for (const [action, b] of Object.entries(table)) {
    for (const code of b.codes ?? []) {
      for (const other of seen.get(code) ?? []) {
        const oc = table[other].context ?? 'shared';
        const c = b.context ?? 'shared';
        if ((oc === c || oc === 'shared' || c === 'shared') && !shares(action, other)) {
          out.push({ a: action, b: other, code, contexts: [c, oc] });
        }
      }
      seen.set(code, [...(seen.get(code) ?? []), action]);
    }
  }
  return out;
}
