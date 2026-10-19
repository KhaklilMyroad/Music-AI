# 05 — Input and interface (PC)

Keyboard and mouse are the primary scheme. A gamepad is a first-class
alternative. Touch still works and nothing requires it.

This replaces the mobile touch specification. The platform changed; the
accessibility commitments did not.

## Control map

| Action | Keyboard / mouse | Gamepad | Context |
|---|---|---|---|
| Move | `W` `A` `S` `D`, arrows | left stick | fps |
| Look | mouse (relative, pointer-locked) | right stick | fps |
| Run | `Shift` | left stick click | fps |
| Crouch | `Ctrl` / `C` | B | fps |
| Prone | `Z` | right stick click | fps |
| Climb or step over | `Space` | A | fps |
| Lean left / right | `Q` / `X` | — | fps |
| Fire | left mouse | right shoulder | fps |
| Aim | right mouse | left shoulder | fps |
| Reload | `R` | X | fps |
| Interact | `E` / `F` (tap or hold) | Y | fps |
| Hold breath | `Alt` | — | fps |
| Next / previous item | wheel, `1` `2` | — | fps |
| Pan the map | middle mouse drag | — | map |
| Zoom | wheel, `+` `−` | — | map |
| End week | `Space` | right shoulder | map |
| Next formation | `Tab` | — | map |
| Journal | `J` | Back | shared |
| Map | `M` | — | shared |
| Pause | `Esc` | Start | shared |
| Quick save / load | `F5` / `F9` | — | shared |

Every action is rebindable. The default table lives in code — in
`godot/core/services/input_service.gd` and `web/src/ui/desktop-input.js` — not
in `project.godot`, for three reasons: "reset to defaults" needs something to
reset to, a keycode written once by name cannot drift from a duplicate written
as a magic number, and a conflict check can run over the table before anything
is applied.

## Contexts, and why `Space` is bound twice

A binding belongs to a context: `fps`, `map`, `ui` or `shared`. Two actions may
share a key when their contexts are never live at once — `Space` traverses in a
mission and ends the week on the map, which is correct, not a bug. A clash
within a context, or with a `shared` action, is a real conflict.

Two things follow from that:

- An intentional pair is **declared**, not discovered. `Esc` pauses a mission
  and backs out of a menu; both bindings carry `shares_with` naming the other.
- Everything else is checked. `undeclaredClashes()` is a pure function over the
  default table, asserted by `web/tests/suite-input.js`, mirrored in
  `godot/core/services/input_service.gd`, and runnable without an engine via
  `python3 -I tools/check_input_bindings.py`. It found a real clash during this
  work: `end_turn` and `pause` were both on gamepad Start.

## Rebinding behaviour

Taking a key from another action **removes it there**, so two actions never
silently share one key after the player confirmed the clash. A clash is shown
rather than resolved: the row says which action already owns the key, and
pressing the same key again takes it.

A binding saved for an action a later build dropped is ignored, not applied.

## Mouse

- **Relative motion only.** No OS acceleration, no smoothing. In Godot,
  `Input.use_accumulated_input` is off while captured; in the browser, pointer
  lock is requested with `unadjustedMovement: true`.
- **Zoom-independent sensitivity.** Aiming narrows the field of view, and the
  look function divides by the field-of-view ratio, so the crosshair travels
  the same distance per centimetre of mouse movement whether aiming or not.
  Without this, every player re-learns their aim every time they right-click.
- **Capture is asked for, not taken.** Pointer lock requires a user gesture, and
  a game that grabs the cursor unannounced is a game people cannot leave. The
  prototype shows a click-to-capture overlay that doubles as the control hint.
- **Losing the cursor pauses.** Alt-tab, `Esc` or a lost pointer lock all pause
  and checkpoint. Returning re-captures only if a mission is still live.

## Display

A desktop window is resizable and remembers what the player chose. Display
mode (windowed, fullscreen, borderless), resolution, monitor, vertical sync and
frame-rate limit are all settings, not constants. A windowed "native" size is
90% of the usable screen rect and is centred on the **chosen** monitor, not
assumed to be the primary one.

The interface anchors rather than scaling to a fixed aspect, so 16:9, 16:10,
4:3, 21:9 and 32:9 all work. There is no safe-area inset to honour, and no
orientation to force: the mobile rotate hint became a hint that only appears in
a very narrow window, and it is always dismissible.

## Graphics options

A preset (`low`, `medium`, `high`, `ultra`) plus every expensive feature
individually: render scale with FSR2, anti-aliasing, shadow quality, texture
quality, anisotropic filtering, ambient occlusion, screen-space indirect light,
global illumination, reflections, volumetric fog, depth of field, bloom, draw
distance, vegetation density and the active-character cap.

Two invariants, both tested:

1. **A preset fully describes the graphics state.** Every preset sets every
   graphics option. A test asserts it, and it caught `bloom` being absent.
2. **Touching one option moves the preset to `custom`.** The menu never claims
   a preset it is not running.

A quality option may change presentation only. The stealth model takes no
rendering parameter at all, and a test greps the module to prove it — so a
player who turns shadows off does not thereby become harder to see.

## Interface, now that there is a mouse

Desktop panels are correct here, where the brief warned against them on a
phone: a mouse can hit a 24-pixel row and hover to reveal a tooltip. What does
**not** change:

- Text scale (0.85–1.6×), interface scale (0.8–1.6×) and HUD scale (0.8–1.5×)
  all remain, because a 4K monitor at desk distance has the same legibility
  problem as a phone at arm's length.
- High contrast, colour-independent indicators (a word and a shape as well as a
  colour), subtitles with speaker identity, directional sound captions, reduced
  motion, camera-shake control and separate recoil presentation all remain.
- Hold-or-toggle remains for aim, crouch and prone. A player who cannot hold a
  key still has to be able to crouch.
- Head bob became its own 0–1 slider, because it is the most common comfort
  complaint on PC and "reduced motion" is too blunt an instrument for it.

## HUD

Condition, stamina, rounds, the interaction prompt, objectives and stealth
feedback. The interaction prompt **names the actual key**, read from the live
bindings, so it stays correct after a rebind. Posture, lean and breath appear as
small tags only while they are not at rest.

## Error and recovery text

Unchanged from the mobile specification except where the platform differs:
"storage full" became disk space, and a new string covers a browser refusing
pointer lock. A test still asserts no locale string contains a stack trace, a
node name, a file extension or the word "undefined".

## Hebrew and RTL

Unchanged and still asserted: 346 keys at full parity between English and
Hebrew, document direction flips, and interpolated values are wrapped in
Unicode isolates so a Latin place name or a number inside a Hebrew sentence
cannot reorder the sentence around it.
