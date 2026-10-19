# The War Beneath the Map — PC

An original, historically grounded World War II strategy and survival game for
PC.

> **Platform note.** The supplied brief is titled for a mobile edition and
> describes an existing Windows Godot project as its foundation. The target is
> PC, so this project sits on that foundation: **Forward+** instead of the
> mobile renderer, keyboard and mouse instead of touch, Steam instead of the
> app stores. None of the simulation changed — `docs/00` measures exactly what
> the retarget cost, layer by layer. You command formations or underground networks on a
turn-based strategic map, enter the particular place where an operation happens,
live through it in first person, and return to a world that changed because of
what you did.

Built to the brief in `War_Beneath_Map_Mobile_Developer_Brief_EN_1.docx`
(project owner: Khalil Myroad, 14 October 2026).

---

## Read this first

**What is verified, what is demonstrated and what is not built** is set out in
[`docs/13-LIMITATIONS.md`](docs/13-LIMITATIONS.md). Read it before believing any
other claim here. The short version:

| | Status |
|---|---|
| Simulation rules, data contracts, exactly-once consequences, saves, stealth, weapons, PC input, content and editorial policy | **Verified** — 182 tests pass |
| The hybrid map → mission → map loop | **Playable** — keyboard and mouse, in the prototype |
| The Godot 4 project | **Written, never compiled** — no Godot binary existed in the authoring environment |
| Commercial art, audio, Forward+ lighting on a real GPU, performance, Steam build | **Not met / not present / unmeasured** |

Every historical citation is deliberately marked pending. **No source was
invented.** A named historian has to attach them before the chapters concerned
can ship.

---

## Try it in two minutes

1. **Play the loop.** Open the prototype link from the handoff and follow
   [`docs/12-BUILD-AND-RELEASE.md`](docs/12-BUILD-AND-RELEASE.md) Part A.
   Twelve numbered steps take you from the strategic map, through a first-person
   sabotage operation in the Normandy bocage, back to a map that changed.
   `WASD` and the mouse; `Esc` releases the cursor and pauses.
2. **Check the rules.** Install Node.js, then:

   ```
   node web/tests/run-all.js
   ```

   The last line should read `182 passed`. Part B of the same document has the
   click-by-click version, and a second check for control-key clashes.

---

## What is in here

```
shared-data/        The content both implementations read. One source of truth.
  theaters.json           4 theatres, 124 hex tiles, terrain rules, 5 facilities, 3 sea links
  chapters.json           12 chapters, 11 mission families, 10 dated events
  weapons.json            4 weapons + 2 tools, each with its own handling, reload and audio rules
  historical-records.json 12 records, kept apart as documented fact / reconstruction / fiction
  asset-provenance.json   creator, source, licence and ship-clearance per asset
  districts/              the playable district (256 x 224 m), from a reviewable ASCII layout
  locales/                English and Hebrew, 346 keys each, at asserted parity, with RTL

godot/              The Godot 4.3 project, Forward+. The shipped game. Never compiled — see docs/13.
  core/                   contracts, deterministic RNG, dates, hexes
  core/services/          content, input + rebinding, campaign authority, transition machine,
                          saves, PC display/graphics settings, i18n, audio
  gameplay/strategic/     supply, order validation, deterministic turn resolver
  gameplay/fps/           detection model, weapon runtime, player controller, district builder, mission scene
  gameplay/ai/            patrol state machine, civilian priorities
  ui/                     HUD, strategic map, optional touch layer
  tests/test_runner.gd    headless mirror of the JavaScript suite

web/                The playable design prototype, and the verified reference implementation.
  src/sim/                the authoritative rules — this is what the 162 tests cover
  src/strategic/          the hex map view
  src/fps/                the 3D district, player, agents and mission orchestrator
  src/ui/                 design tokens, i18n, PC settings, desktop input + rebinding
  tests/                  7 suites, 182 cases, no dependencies

tools/              author_district.py (ASCII layout → district JSON, with a reachability
                    flood fill), bundle_data.py, check_input_bindings.py
docs/               14 documents: GDD, specs, bibles, acceptance matrix, build steps, limitations
```

## Documentation

| | |
|---|---|
| [00 Project State Matrix](docs/00-PROJECT-STATE-MATRIX.md) | Phase, component, evidence, blockers, next milestone, and the decisions that are the owner's to make |
| [01 GDD](docs/01-GDD.md) | The game, the loop, both layers, modes, accessibility |
| [02 Data contracts](docs/02-DATA-CONTRACTS.md) | Normative. The save contract and why a civilian group has no `strength` field |
| [03 Turn resolution](docs/03-TURN-RESOLUTION-SPEC.md) | Normative. The nine phases, and how determinism is guaranteed |
| [04 Transitions and exactly-once](docs/04-TRANSITION-EXACTLY-ONCE.md) | Normative. The state machine, the durable write order, recovery at every boundary |
| [05 Input and interface](docs/05-INPUT-AND-INTERFACE.md) | Control map, rebinding, contexts, mouse feel, display modes, graphics options, Hebrew and RTL |
| [06 Art bible](docs/06-ART-BIBLE.md) | The commercial bar, the eight fixed camera comparisons, the hands-and-weapon checklist |
| [07 Audio bible](docs/07-AUDIO-BIBLE.md) | Families, priority, the voice budget, the weapon audio registry, rights and authenticity |
| [08 Historical and editorial standard](docs/08-HISTORICAL-EDITORIAL-STANDARD.md) | The three kinds, the citation policy, sensitive settings, representation, open blockers |
| [09 Acceptance matrix](docs/09-ACCEPTANCE-MATRIX.md) | Every gate in §20, its automated coverage, and what a person must still do |
| [10 Performance plan](docs/10-PERFORMANCE-PLAN.md) | Forward+ choice, quality presets, targets, hardware matrix, reporting rules |
| [11 Content baseline](docs/11-CONTENT-BASELINE.md) | The eleven values the owner has to fix, each with a recommendation and a reason |
| [12 Build and release](docs/12-BUILD-AND-RELEASE.md) | For someone with no programming experience. Exact clicks, including the Steam depot |
| [13 Limitations and honest status](docs/13-LIMITATIONS.md) | **Start here.** What is proven, what is shown, what does not exist |

## Design decisions worth knowing

- **One source of truth for content.** The Godot project and the prototype read
  the same JSON, so the layout, the chapters and the weapon rules cannot drift
  apart. The district is generated from a reviewable ASCII layout a level
  designer, a historian and the owner can all argue about in a text diff.
- **A mission cannot write the world.** It returns an outcome, the objectives it
  completed, metrics and bounded requests. Everything is clamped to the bounds
  its chapter authored, and clamped fields are reported rather than swallowed.
- **Determinism is a guarantee, not a hope.** The GDScript PRNG was verified to
  produce a bit-identical stream to the JavaScript one, so both implementations
  resolve a turn the same way.
- **Quality settings cannot change gameplay.** The stealth model takes no
  rendering parameter. A test greps the module and fails if one appears — so a
  player who turns shadows off does not become harder to see.
- **Every control is rebindable, and clashes are caught before a player finds
  them.** The default table lives in code, grouped by context, and a pure
  clash check runs in the test suite and in `tools/check_input_bindings.py`
  without needing an engine. It found a real one.
- **Aiming is zoom-independent.** Narrowing the field of view does not change
  how far the crosshair travels per centimetre of mouse movement, so nobody
  re-learns their aim every time they right-click.
- **A level cannot ship with an unreachable objective.** The district authoring
  tool flood-fills from the spawn and refuses to emit a district where any
  objective is walled off.
- **Noise comes from measured movement.** A footstep needs ground contact and
  horizontal displacement, so pushing into a wall and moving through the air are
  silent by construction rather than by a special case.
- **The 1943 Warsaw ghetto uprising has no "success" outcome.** By design, with
  a test. Agency belongs to the defenders; the recorded result is not for a game
  to overturn.
- **Blockout art says so.** The district data carries an `art_status.statement`,
  the prototype prints it on screen, and the provenance registry marks every
  placeholder `may_ship: "never"`.

## What this is not

Not a finished commercial game. Not a Windows build. Not measured on a GPU.
Not reviewed by a historian. The Forward+ lighting has never been seen
rendering. The brief asks specifically that a successful
export or a high test count never be labelled as completion of the full
commercial vision, and it is not labelled that here.

The first production milestone is defined in brief §23 and costed in
[`docs/11`](docs/11-CONTENT-BASELINE.md): one representative district
connected to the strategic map, with convincing first-person hands and one
complete weapon, an interior and exterior, combat, a stealth or civilian
interaction, material-aware sound, persistent consequences and interruption-safe
saves — holding **60 FPS at 1080p on the minimum GPU**, not only on the
development machine.
