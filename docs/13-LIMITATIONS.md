# 13 — Limitations and honest status

This page exists because the brief asks for it in several places at once: record
build identifier and conditions with every claim (§20), label generated art
versus gameplay (§12), and never label a successful export or a high test count
as completion of the commercial vision (§23). Read this page before reading any
other claim in this repository.

## What was actually produced, and in what environment

The work in this repository was produced by an AI agent in a Linux container
with **no Godot binary, no GPU, no mobile device, no macOS/Xcode, no audio
recording chain and no 3D art pipeline**. That shapes every statement below.

| Claim | Status | Evidence |
|---|---|---|
| Simulation rules are correct | **Verified** | 162 tests pass under `node web/tests/run-all.js`. Run it yourself; it takes about a second and needs no install. |
| Exactly-once mission consequences | **Verified** | Covered by 18 cases including process termination at all six transition boundaries. |
| Deterministic turn resolution | **Verified** | Same `(state, seed)` produces a byte-identical state digest over 120 turns. |
| Save integrity, last-known-good, migrations | **Verified** | Includes a test that cuts a write short mid-file and asserts the previous save still loads. |
| Stealth and weapon rules | **Verified** | Includes the brief's named cases: wall-pushing footsteps, airborne footsteps, death during reload, quality-independent detection. |
| Content and editorial rules | **Verified** | Locale parity, citation policy, sensitive-chapter gating, separation of the 1940 sealing / 1943 ghetto uprising / 1944 city uprising. |
| The hybrid loop is playable | **Demonstrated** | The web prototype plays map → mission → map with real consequences on a phone. |
| The Godot 4 project compiles and runs | **NOT VERIFIED** | No Godot binary existed in the authoring environment. The GDScript is a careful mirror of the verified JavaScript, and `godot/tests/test_runner.gd` mirrors the suite, but **it has never been executed.** Treat the first run as a debugging session, not a demonstration. |
| Commercial art quality | **NOT MET** | Every mesh is a procedural or box blockout. Every material is generated. Every character is a jointed blockout. The district data says so in `art_status.statement`, and the prototype prints it on screen. |
| Audio | **NOT PRESENT** | The routing, priority, reverb, occlusion, repetition and mono rules are implemented and tested. There is **no sample bank**: nothing audible has been recorded or licensed. |
| Mobile performance | **UNMEASURED** | Every number in `docs/10-DEVICE-PERF-PLAN.md` is an engineering target. No frame time, memory figure or thermal result has been measured on any phone. |
| Signed Android/iOS builds | **NOT PRODUCED** | Android export needs the SDK and a keystore; iOS export needs macOS and Xcode. Neither was available. `docs/12` has the exact steps. |
| Historical citations | **PENDING** | Every record in `shared-data/historical-records.json` carries `review_status: pending_citation` or `pending_specialist_review` with `sources: []`. **No citation was invented.** A named historian must attach them before the relevant chapter ships. |

## Specific things that are deliberately *not* claimed

- **The Anne Frank theme.** The brief asks for Anne Frank-inspired hiding-place
  themes. The real history is carried as a **reference-only** record cited in
  the journal. The playable hiding-place content is an original fictional
  household (`fict_household_lindenweg`) in an original building, explicitly
  labelled fiction. No district reconstructs the Prinsengracht annexe and
  nothing in this project may be presented as it.
- **Ghettos, camps and extermination centres.** They are separate records with
  separate dates and separate treatment notes. No "camp survival loop" exists
  and none may be written without the specialist sign-off the data demands.
- **"Every weapon of the war."** Six entries ship: four weapons and two tools,
  each with its own handling, reload rules and audio event list. The registry is
  structured for staged expansion; it is not and does not claim to be
  comprehensive coverage of the period's ordnance.
- **Competitive comparison.** No 2027 competitor has been assessed, because
  none has shipped. The art and audio bars in `docs/06` and `docs/07` are
  written as reviewable criteria against the owner's own reference pack, which
  the authoring environment never received.
- **The existing Windows prototype.** It was described in the brief but not
  supplied. Nothing here was ported from it, reused from it, or verified against
  it. `docs/11` lists the audit that has to happen before any reuse decision.

## What to do first

1. Run `node web/tests/run-all.js`. If it is green, the rules are sound.
2. Open the web prototype on a phone and play the Normandy operation. If the
   loop feels right, the design is sound.
3. Open `godot/` in Godot 4.3 and run `godot --headless --script res://tests/test_runner.gd`.
   Expect failures from untested translation; fix them against the JavaScript.
4. Only then read `docs/11-CONTENT-DEVICE-BASELINE.md` and fix the numbers the
   brief says the owner has not yet fixed.
