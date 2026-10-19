# 09 — Acceptance matrix

Every gate in brief §20, mapped to the demonstration that satisfies it and to
the automated cases that support it. Automated coverage is necessary but never
sufficient: the right-hand column says what a *person* still has to do.

Automated cases live in `web/tests/` (verified) and `godot/tests/test_runner.gd`
(mirror, not yet executed — see `docs/13`).

| # | Gate (brief §20) | Automated coverage | What a person must still demonstrate |
|---|---|---|---|
| G1 | **Hybrid gameplay** — start on the map, issue an order, enter first person, finish or fail, return, verify the authorised strategic consequences | `suite-transition.js`: 16 cases, including "the authorised consequence actually lands" and "a mission whose chapter does not authorise it cannot remove a formation" | Play the full loop on a machine. Confirm the result screen names each change and that the map shows it. |
| G2 | **Persistence** — save and resume a campaign operation and a district; terminate the process at transition boundaries without duplicate outcomes | `suite-transition.js` "recovery at every boundary" (6 cases, one per state) + `suite-persistence.js` (14 cases) | Kill the process from Task Manager at each boundary. Confirm no duplicate reward and no lost inventory. |
| G3 | **Input usability** — complete representative missions with keyboard and mouse, and again with a gamepad alone | `suite-input.js`: 17 cases on the binding table, context separation, clash detection and preset integrity; `tools/check_input_bindings.py` runs the clash check without an engine | One person completes the Normandy operation with keyboard and mouse, once more with a gamepad only, and once with every action rebound away from its default. Text scale at maximum, interface scale at maximum. |
| G4 | **Strategy** — complete turns with movement, supply, construction and opposition; rejected orders leave resources and state unchanged | `suite-strategy.js`: 24 cases. "an impossible move leaves resources and state byte-identical" compares a full state digest before and after | Play 20 weeks. Confirm the week report explains every change and that no order is silently reinterpreted. |
| G5 | **Combat and animation** — aim, firing, grip, reload, ammunition and interruption in continuous gameplay at ordinary camera distance | `suite-firstperson.js`: 22 cases, including round-count conservation across 400 random interleaved fire/reload/cancel actions | Watch the hands at ordinary distance through idle → aim → fire → reload → interact. Check contact, fingers, cuffs and the transitions. **Blockout art will fail this gate; that is expected.** |
| G6 | **Stealth and survival** — sound and visibility rules match behaviour; essential decisions stay understandable with accessibility options on | `suite-firstperson.js` stealth group: 17 cases including the quality-independence check | Play the operation with high contrast, colour-independent indicators, reduced motion, zero head bob and mono output all on. Confirm every risk decision is still legible. |
| G7 | **Art** — compare the agreed reference qualities against ordinary gameplay, including unfavourable angles and motion, on both GPU tiers | `suite-contracts.js` district group: openings declare recess and swing, walls have thickness, every building has an interior | The eight fixed camera comparisons in `docs/06-ART-BIBLE.md`, recorded twice: minimum GPU at `medium`, recommended GPU at `high`. |
| G8 | **Audio** — human listening across speakers and headphones; weapon identity, room transitions, obstruction, mix, repetition, interruption recovery | `suite-audio.js`: 19 cases on priority, budget, distance, occlusion, mono captions, repetition guard, interruption policy | **Required and unreplaceable.** A person listens on desk speakers, laptop speakers, wired headphones, a headset and mono. No sample bank exists yet, so this gate cannot even start. |
| G9 | **History** — reviewed provenance and date consistency for every released chapter and sensitive setting | `suite-contracts.js` content group: 12 cases on citation policy, sensitivity gating, record separation, fiction labelling | A named historian signs each record off and attaches real citations. A named narrative editor signs off every sensitive chapter. |
| G10 | **Desktop resilience** — alt-tab, lost pointer lock, sleep and resume, full disk, offline play, cloud conflicts, process kill | `suite-persistence.js` (interrupted write, incomplete write, corrupt fallback, conflict description) | On a machine: alt-tab mid-mission, sleep and resume, fill the disk, kill from Task Manager mid-save, pull the network during a Steam Cloud sync. |
| G11 | **Sustained performance** — recorded frame times and memory over long sessions across the hardware matrix | None. Not automatable here. | A 2-hour session per hardware tier with recorded frame times, memory and VRAM, plus a cold-shader-cache first run reported separately, under the conditions in `docs/10`. |
| G12 | **Distribution** — clean install, update, content verification, correct credits, readable onboarding, a working Steam depot | None. | Follow `docs/12`. Produce a Windows build and a Steam branch build, install from Steam on a machine that never had the project, and record the OS, GPU and build id. |

## The explicitly named minimum tests (brief §20, final paragraph)

Two of the named tests concerned a phone and have been replaced by their PC
equivalents rather than quietly dropped: "stereo-to-mono output" still applies
and still passes; "app termination during save" became killing the process
during a save, which is the same test with a different button.

| Named test | Where | Status |
|---|---|---|
| duplicate result delivery | `suite-transition.js` "a repeated delivery of the same result is a no-op" | pass |
| a missing or incompatible content pack | `suite-transition.js` "a missing content pack refuses entry and reserves nothing" | pass |
| app termination during save | `suite-persistence.js` "termination part-way through a write leaves the previous save intact" | pass |
| wall-pushing footsteps | `suite-firstperson.js` "pushing into a wall makes no footstep" | pass |
| airborne footsteps | `suite-firstperson.js` "moving through the air makes no footstep" | pass |
| death during reload | `suite-firstperson.js` "death during a reload cancels it and leaves the count correct" | pass |
| reduced motion | Structural: `--dur*` tokens collapse, `DistrictBuilder` skips sway, head bob forced to zero. No automated case. | **gap — needs a visual check** |
| stereo-to-mono output | `suite-audio.js` "mono output removes panning but keeps essential cues as captions" | pass |
| UI scaling | Structural: every size derives from `--ts` / `--hud`. No automated case. | **gap — needs a visual check at 0.85 and 1.6, at 1080p and at 4K** |
| RTL text | `suite-contracts.js` locale group (parity, direction) — layout itself is not asserted | **partial — needs a visual check in Hebrew** |

The three gaps above are honest gaps, not oversights: each needs a human looking
at a screen, and none should be reported as covered until that has happened.
