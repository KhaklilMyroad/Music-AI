# 09 — Acceptance matrix

Every gate in brief §20, mapped to the demonstration that satisfies it and to
the automated cases that support it. Automated coverage is necessary but never
sufficient: the right-hand column says what a *person* still has to do.

Automated cases live in `web/tests/` (verified) and `godot/tests/test_runner.gd`
(mirror, not yet executed — see `docs/13`).

| # | Gate (brief §20) | Automated coverage | What a person must still demonstrate |
|---|---|---|---|
| G1 | **Hybrid gameplay** — start on the map, issue an order, enter first person, finish or fail, return, verify the authorised strategic consequences | `suite-transition.js`: 16 cases, including "the authorised consequence actually lands" and "a mission whose chapter does not authorise it cannot remove a formation" | Play the full loop on a phone. Confirm the result screen names each change and that the map shows it. |
| G2 | **Persistence** — save and resume a campaign operation and a district; terminate the process at transition boundaries without duplicate outcomes | `suite-transition.js` "recovery at every boundary" (6 cases, one per state) + `suite-persistence.js` (14 cases) | Force-kill the app at each boundary on a real device. Confirm no duplicate reward and no lost inventory. |
| G3 | **Touch usability** — complete representative missions on a phone using touch alone | Structural: `touch.js` exposes every action as a button with a ≥48 dp target, and `interact_held` plus `pressed` give every staged action a tap route | One person completes the Normandy operation on a phone with no keyboard, left-handed layout on, text scale at maximum. |
| G4 | **Strategy** — complete turns with movement, supply, construction and opposition; rejected orders leave resources and state unchanged | `suite-strategy.js`: 24 cases. "an impossible move leaves resources and state byte-identical" compares a full state digest before and after | Play 20 weeks. Confirm the week report explains every change and that no order is silently reinterpreted. |
| G5 | **Combat and animation** — aim, firing, grip, reload, ammunition and interruption in continuous gameplay at ordinary camera distance | `suite-firstperson.js`: 22 cases, including round-count conservation across 400 random interleaved fire/reload/cancel actions | Watch the hands at ordinary distance through idle → aim → fire → reload → interact. Check contact, fingers, cuffs and the transitions. **Blockout art will fail this gate; that is expected.** |
| G6 | **Stealth and survival** — sound and visibility rules match behaviour; essential decisions stay understandable with accessibility options on | `suite-firstperson.js` stealth group: 17 cases including the quality-independence check | Play the operation with high contrast, colour-independent indicators, reduced motion and mono output all on. Confirm every risk decision is still legible. |
| G7 | **Art** — compare the agreed reference qualities against ordinary gameplay, including unfavourable angles and motion, on the target tier | `suite-contracts.js` district group: openings declare recess and swing, walls have thickness, every building has an interior | The eight fixed camera comparisons in `docs/06-ART-BIBLE.md`, recorded on the lower supported device. |
| G8 | **Audio** — human listening across speakers and headphones; weapon identity, room transitions, obstruction, mix, repetition, interruption recovery | `suite-audio.js`: 19 cases on priority, budget, distance, occlusion, mono captions, repetition guard, interruption policy | **Required and unreplaceable.** A person listens on a phone speaker, wired headphones, Bluetooth and mono. No sample bank exists yet, so this gate cannot even start. |
| G9 | **History** — reviewed provenance and date consistency for every released chapter and sensitive setting | `suite-contracts.js` content group: 12 cases on citation policy, sensitivity gating, record separation, fiction labelling | A named historian signs each record off and attaches real citations. A named narrative editor signs off every sensitive chapter. |
| G10 | **Mobile resilience** — backgrounding, calls, locks, low storage, interrupted downloads, offline play, cloud conflicts, OS termination | `suite-persistence.js` (interrupted write, incomplete write, corrupt fallback, conflict description) | On device: incoming call mid-mission, screen lock, airplane mode, fill the storage, kill from the task switcher. |
| G11 | **Sustained performance** — recorded frame times, memory and thermal behaviour over long sessions on the supported matrix | None. Not automatable here. | A 30-minute session per device tier with recorded frame times, memory, battery and temperature, under the conditions in `docs/10`. |
| G12 | **Distribution** — clean install, update, content verification, correct credits, readable onboarding, functional signed Android and iOS builds | None. | Follow `docs/12`. Produce installable builds and record the device, OS and build id. |

## The explicitly named minimum tests (brief §20, final paragraph)

| Named test | Where | Status |
|---|---|---|
| duplicate result delivery | `suite-transition.js` "a repeated delivery of the same result is a no-op" | pass |
| a missing or incompatible content pack | `suite-transition.js` "a missing content pack refuses entry and reserves nothing" | pass |
| app termination during save | `suite-persistence.js` "termination part-way through a write leaves the previous save intact" | pass |
| wall-pushing footsteps | `suite-firstperson.js` "pushing into a wall makes no footstep" | pass |
| airborne footsteps | `suite-firstperson.js` "moving through the air makes no footstep" | pass |
| death during reload | `suite-firstperson.js` "death during a reload cancels it and leaves the count correct" | pass |
| reduced motion | Structural: `--dur*` tokens collapse and `DistrictBuilder` skips sway. No automated case. | **gap — needs a visual check** |
| stereo-to-mono output | `suite-audio.js` "mono output removes panning but keeps essential cues as captions" | pass |
| UI scaling | Structural: every size derives from `--ts` / `--hud`. No automated case. | **gap — needs a visual check at 0.85 and 1.6** |
| RTL text | `suite-contracts.js` locale group (parity, direction) — layout itself is not asserted | **partial — needs a visual check in Hebrew** |

The three gaps above are honest gaps, not oversights: each needs a human looking
at a screen, and none should be reported as covered until that has happened.
