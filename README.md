# The War Beneath the Map — mobile edition

An original, historically grounded World War II strategy and survival game for
phones and tablets. You command formations or underground networks on a
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
| Simulation rules, data contracts, exactly-once consequences, saves, stealth, weapons, content and editorial policy | **Verified** — 162 tests pass |
| The hybrid map → mission → map loop | **Playable** — on a phone, in the prototype |
| The Godot 4 project | **Written, never compiled** — no Godot binary existed in the authoring environment |
| Commercial art, audio, device performance, signed builds | **Not met / not present / unmeasured** |

Every historical citation is deliberately marked pending. **No source was
invented.** A named historian has to attach them before the chapters concerned
can ship.

---

## Try it in two minutes

1. **Play the loop.** Open the prototype link from the handoff on a phone, turn
   the phone sideways, and follow
   [`docs/12-BUILD-INSTRUCTIONS-WINDOWS.md`](docs/12-BUILD-INSTRUCTIONS-WINDOWS.md)
   Part A. Twelve numbered steps take you from the strategic map, through a
   first-person sabotage operation in the Normandy bocage, back to a map that
   changed.
2. **Check the rules.** Install Node.js, then:

   ```
   node web/tests/run-all.js
   ```

   The last line should read `162 passed`. Part B of the same document has the
   click-by-click version.

---

## What is in here

```
shared-data/        The content both implementations read. One source of truth.
  theaters.json           4 theatres, 124 hex tiles, terrain rules, 5 facilities, 3 sea links
  chapters.json           12 chapters, 11 mission families, 10 dated events
  weapons.json            4 weapons + 2 tools, each with its own handling, reload and audio rules
  historical-records.json 12 records, kept apart as documented fact / reconstruction / fiction
  asset-provenance.json   creator, source, licence and ship-clearance per asset
  districts/              the playable district, generated from a reviewable ASCII layout
  locales/                English and Hebrew, 273 keys each, at asserted parity, with RTL

godot/              The Godot 4.3 project. The shipped game. Never compiled — see docs/13.
  core/                   contracts, deterministic RNG, dates, hexes
  core/services/          content, campaign authority, transition machine, saves, settings, i18n, audio
  gameplay/strategic/     supply, order validation, deterministic turn resolver
  gameplay/fps/           detection model, weapon runtime, player controller, district builder, mission scene
  gameplay/ai/            patrol state machine, civilian priorities
  ui/                     touch controls, HUD, strategic map
  tests/test_runner.gd    headless mirror of the JavaScript suite

web/                The playable design prototype, and the verified reference implementation.
  src/sim/                the authoritative rules — this is what the 162 tests cover
  src/strategic/          the hex map view
  src/fps/                the 3D district, player, agents and mission orchestrator
  src/ui/                 design tokens, i18n, settings, touch layer
  tests/                  6 suites, 162 cases, no dependencies

tools/              author_district.py (ASCII layout → district JSON), bundle_data.py
docs/               14 documents: GDD, specs, bibles, acceptance matrix, build steps, limitations
```

## Documentation

| | |
|---|---|
| [00 Project State Matrix](docs/00-PROJECT-STATE-MATRIX.md) | Phase, component, evidence, blockers, next milestone, and the decisions that are the owner's to make |
| [01 Mobile GDD](docs/01-GDD-mobile.md) | The game, the loop, both layers, modes, accessibility |
| [02 Data contracts](docs/02-DATA-CONTRACTS.md) | Normative. The save contract and why a civilian group has no `strength` field |
| [03 Turn resolution](docs/03-TURN-RESOLUTION-SPEC.md) | Normative. The nine phases, and how determinism is guaranteed |
| [04 Transitions and exactly-once](docs/04-TRANSITION-EXACTLY-ONCE.md) | Normative. The state machine, the durable write order, recovery at every boundary |
| [05 Touch and interface](docs/05-TOUCH-UX-SPEC.md) | Control map, multi-touch, safe areas, sheets, error text, Hebrew and RTL |
| [06 Art bible](docs/06-ART-BIBLE.md) | The commercial bar, the eight fixed camera comparisons, the hands-and-weapon checklist |
| [07 Audio bible](docs/07-AUDIO-BIBLE.md) | Families, priority, the voice budget, the weapon audio registry, rights and authenticity |
| [08 Historical and editorial standard](docs/08-HISTORICAL-EDITORIAL-STANDARD.md) | The three kinds, the citation policy, sensitive settings, representation, open blockers |
| [09 Acceptance matrix](docs/09-ACCEPTANCE-MATRIX.md) | Every gate in §20, its automated coverage, and what a person must still do |
| [10 Device and performance plan](docs/10-DEVICE-PERF-PLAN.md) | Renderer choice, quality tiers, targets, reporting rules |
| [11 Content and device baseline](docs/11-CONTENT-DEVICE-BASELINE.md) | The ten values the owner has to fix, each with a recommendation and a reason |
| [12 Build instructions](docs/12-BUILD-INSTRUCTIONS-WINDOWS.md) | For someone with no programming experience. Exact clicks, including Android signing |
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
  rendering parameter. A test greps the module and fails if one appears.
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

Not a finished commercial game. Not a signed build. Not measured on a phone.
Not reviewed by a historian. The brief asks specifically that a successful
export or a high test count never be labelled as completion of the full
commercial vision, and it is not labelled that here.

The first production milestone is defined in brief §23 and costed in
[`docs/11`](docs/11-CONTENT-DEVICE-BASELINE.md): one representative district
connected to the strategic map, with convincing first-person hands and one
complete weapon, an interior and exterior, combat, a stealth or civilian
interaction, material-aware sound, persistent consequences and interruption-safe
saves — running on the **lower** supported device, not a flagship.
