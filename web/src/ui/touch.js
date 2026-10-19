// Touch controls (brief §10). Designed for simultaneous movement and camera
// control with two thumbs, inside the safe area, with every action customisable.
//
// Multi-touch is tracked by pointerId, so the look drag never steals the move
// stick's finger and vice versa — the single most common failure in a ported
// desktop control scheme.

export const ACTIONS = ['fire', 'aim', 'reload', 'interact', 'crouch', 'sprint', 'traverse', 'journal', 'pause'];

export class TouchControls {
  constructor(root, settings, i18n) {
    this.root = root;
    this.s = settings;
    this.i18n = i18n;
    this.move = { x: 0, y: 0, active: false, id: null, origin: [0, 0], cur: [0, 0] };
    this.look = { dx: 0, dy: 0, active: false, id: null, last: [0, 0] };
    this.held = new Set();
    this.toggled = new Set();
    this.pressed = new Set();      // one-shot presses drained each frame
    this.available = new Set(['fire', 'aim', 'reload', 'crouch', 'sprint', 'journal', 'pause']);
    this.gyro = { dx: 0, dy: 0, enabled: false };
    this.el = {};
    this.build();
    this.bind();
    this.applyLayout();
    settings.subscribe((id) => { if (['left_handed', 'stick_size', 'stick_mode', 'hud_scale'].includes(id)) this.applyLayout(); });
  }

  build() {
    const t = (k) => this.i18n.t(k);
    this.root.innerHTML = `
      <div class="tc-stick" data-el="stick" aria-hidden="true">
        <div class="tc-stick-ring"></div><div class="tc-stick-knob" data-el="knob"></div>
      </div>
      <div class="tc-look" data-el="look" aria-hidden="true"></div>
      <div class="tc-right">
        <button class="tc-btn tc-btn-fire"   data-act="fire"     aria-label="${t('hud.fire')}"><span>${t('hud.fire')}</span></button>
        <button class="tc-btn tc-btn-aim"    data-act="aim"      aria-label="${t('hud.aim')}"><span>${t('hud.aim')}</span></button>
        <button class="tc-btn tc-btn-reload" data-act="reload"   aria-label="${t('hud.reload')}"><span>${t('hud.reload')}</span><i class="tc-prog" data-el="reloadprog"></i></button>
        <button class="tc-btn tc-btn-ctx"    data-act="interact" aria-label="${t('hud.interact')}" hidden><span data-el="ctxlabel">${t('hud.interact')}</span><i class="tc-prog" data-el="ctxprog"></i></button>
        <button class="tc-btn tc-btn-trav"   data-act="traverse" aria-label="climb" hidden><span>↑</span></button>
      </div>
      <div class="tc-left">
        <button class="tc-btn tc-btn-sm" data-act="crouch" aria-label="${t('hud.crouch')}"><span>${t('hud.crouch')}</span></button>
        <button class="tc-btn tc-btn-sm" data-act="sprint" aria-label="${t('hud.sprint')}"><span>${t('hud.sprint')}</span></button>
      </div>
      <div class="tc-corner">
        <button class="tc-chip" data-act="journal" aria-label="${t('menu.journal')}">${t('menu.journal')}</button>
        <button class="tc-chip" data-act="pause"   aria-label="${t('hud.pause')}">II</button>
      </div>`;
    for (const el of this.root.querySelectorAll('[data-el]')) this.el[el.dataset.el] = el;
    this.buttons = [...this.root.querySelectorAll('[data-act]')];
  }

  applyLayout() {
    const lh = this.s.get('left_handed');
    this.root.setAttribute('data-hand', lh ? 'left' : 'right');
    this.root.style.setProperty('--stick-scale', this.s.get('stick_size'));
    this.root.setAttribute('data-stick', this.s.get('stick_mode'));
  }

  haptic(ms = 8) { if (this.s.get('haptics') && navigator.vibrate) { try { navigator.vibrate(ms); } catch {} } }

  bind() {
    const stickZone = () => {
      const lh = this.s.get('left_handed');
      const r = this.root.getBoundingClientRect();
      return lh ? { x0: r.width * 0.55, x1: r.width } : { x0: 0, x1: r.width * 0.45 };
    };

    const onDown = (e) => {
      if (e.target.closest('[data-act]')) return;         // buttons handle themselves
      const z = stickZone();
      const inStick = e.clientX >= z.x0 && e.clientX <= z.x1;
      if (inStick && !this.move.active) {
        this.move.active = true; this.move.id = e.pointerId;
        const fixed = this.s.get('stick_mode') === 'fixed';
        const base = fixed ? this.fixedStickCentre() : [e.clientX, e.clientY];
        this.move.origin = base; this.move.cur = [e.clientX, e.clientY];
        this.el.stick.style.setProperty('--sx', `${base[0]}px`);
        this.el.stick.style.setProperty('--sy', `${base[1]}px`);
        this.el.stick.classList.add('is-active');
        this.updateStick();
      } else if (!this.look.active) {
        this.look.active = true; this.look.id = e.pointerId; this.look.last = [e.clientX, e.clientY];
      }
      this.root.setPointerCapture?.(e.pointerId);
    };

    const onMove = (e) => {
      if (this.move.active && e.pointerId === this.move.id) {
        this.move.cur = [e.clientX, e.clientY];
        this.updateStick();
      } else if (this.look.active && e.pointerId === this.look.id) {
        const inv = this.s.get('invert_y') ? -1 : 1;
        this.look.dx += (e.clientX - this.look.last[0]);
        this.look.dy += (e.clientY - this.look.last[1]) * inv;
        this.look.last = [e.clientX, e.clientY];
      }
    };

    const onUp = (e) => {
      if (this.move.active && e.pointerId === this.move.id) {
        this.move = { x: 0, y: 0, active: false, id: null, origin: [0, 0], cur: [0, 0] };
        this.el.stick.classList.remove('is-active');
        this.el.knob.style.transform = 'translate(-50%,-50%)';
      }
      if (this.look.active && e.pointerId === this.look.id) this.look.active = false, this.look.id = null;
    };

    this.root.addEventListener('pointerdown', onDown);
    this.root.addEventListener('pointermove', onMove);
    this.root.addEventListener('pointerup', onUp);
    this.root.addEventListener('pointercancel', onUp);
    this.root.addEventListener('contextmenu', (e) => e.preventDefault());

    for (const b of this.buttons) {
      const act = b.dataset.act;
      const toggleMode = (act === 'aim' && this.s.get('aim_toggle') === 'toggle')
                      || (act === 'crouch' && this.s.get('crouch_toggle') === 'toggle');
      b.addEventListener('pointerdown', (e) => {
        e.stopPropagation();
        b.classList.add('is-down');
        this.haptic(act === 'fire' ? 12 : 8);
        if (toggleMode) { this.toggled.has(act) ? this.toggled.delete(act) : this.toggled.add(act); b.classList.toggle('is-on', this.toggled.has(act)); }
        else this.held.add(act);
        this.pressed.add(act);
      });
      const release = (e) => { e?.stopPropagation(); b.classList.remove('is-down'); if (!toggleMode) this.held.delete(act); };
      b.addEventListener('pointerup', release);
      b.addEventListener('pointercancel', release);
      b.addEventListener('pointerleave', release);
    }

    // Optional keyboard, for development on a desktop browser. The shipped
    // mobile build must not require it — nothing here is the only way to act.
    this.keys = new Set();
    addEventListener('keydown', (e) => { this.keys.add(e.code); if (e.code === 'Space') e.preventDefault(); });
    addEventListener('keyup', (e) => this.keys.delete(e.code));
  }

  fixedStickCentre() {
    const r = this.root.getBoundingClientRect();
    const lh = this.s.get('left_handed');
    const pad = 110 * this.s.get('stick_size');
    return [lh ? r.width - pad : pad, r.height - pad * 0.85];
  }

  updateStick() {
    const radius = 62 * this.s.get('stick_size');
    let dx = this.move.cur[0] - this.move.origin[0];
    let dy = this.move.cur[1] - this.move.origin[1];
    const len = Math.hypot(dx, dy);
    if (len > radius) { dx = dx / len * radius; dy = dy / len * radius; }
    this.move.x = dx / radius; this.move.y = -dy / radius;
    this.el.knob.style.transform = `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;
  }

  /** Per-frame input snapshot. Drains one-shot presses. */
  sample() {
    const k = this.keys;
    let mx = this.move.x, my = this.move.y;
    if (k.has('KeyW')) my += 1; if (k.has('KeyS')) my -= 1;
    if (k.has('KeyD')) mx += 1; if (k.has('KeyA')) mx -= 1;
    const len = Math.hypot(mx, my); if (len > 1) { mx /= len; my /= len; }

    const down = (a) => this.held.has(a) || this.toggled.has(a);
    const out = {
      move: [mx, my],
      look: [this.look.dx, this.look.dy + (this.gyro.enabled ? this.gyro.dy : 0)],
      lookGyro: this.gyro.enabled ? [this.gyro.dx, this.gyro.dy] : [0, 0],
      fire: down('fire') || k.has('Space'),
      aim: down('aim') || k.has('ShiftLeft') === false && k.has('KeyQ'),
      crouch: down('crouch') || k.has('KeyC'),
      sprint: down('sprint') || k.has('ShiftLeft'),
      // Held separately from the one-shot press, so a staged interaction can
      // run while the button stays down.
      interactHeld: this.held.has('interact') || k.has('KeyE'),
      pressed: new Set(this.pressed),
      sprintFromStick: len > 0.92,
    };
    if (k.has('KeyR')) out.pressed.add('reload');
    if (k.has('KeyE')) out.pressed.add('interact');
    this.look.dx = 0; this.look.dy = 0;
    this.gyro.dx = 0; this.gyro.dy = 0;
    this.pressed.clear();
    return out;
  }

  /** Show only actions the controller actually supports right now. */
  setAvailable(map) {
    for (const b of this.buttons) {
      const act = b.dataset.act;
      if (!ACTIONS.includes(act)) continue;
      const on = map[act] !== false && (map[act] !== undefined || this.available.has(act));
      b.hidden = !on;
    }
  }

  setContext(labelKey, progress) {
    const btn = this.root.querySelector('[data-act="interact"]');
    if (!labelKey) { btn.hidden = true; return; }
    btn.hidden = false;
    this.el.ctxlabel.textContent = this.i18n.t(labelKey);
    this.el.ctxprog.style.setProperty('--p', progress ?? 0);
  }

  setReloadProgress(p) { this.el.reloadprog.style.setProperty('--p', p ?? 0); }
  setTraverse(on) { this.root.querySelector('[data-act="traverse"]').hidden = !on; }

  async enableGyro(on) {
    this.gyro.enabled = on;
    if (!on) return true;
    try {
      if (typeof DeviceOrientationEvent !== 'undefined' && DeviceOrientationEvent.requestPermission) {
        const p = await DeviceOrientationEvent.requestPermission();
        if (p !== 'granted') { this.gyro.enabled = false; return false; }
      }
      let last = null;
      addEventListener('deviceorientation', (e) => {
        if (!this.gyro.enabled) return;
        if (last) { this.gyro.dx += (e.alpha - last.alpha) * 2.2; this.gyro.dy += (e.beta - last.beta) * -2.2; }
        last = { alpha: e.alpha ?? 0, beta: e.beta ?? 0 };
      });
      return true;
    } catch { this.gyro.enabled = false; return false; }
  }
}
