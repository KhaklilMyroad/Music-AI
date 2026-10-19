# 13 — Limitations and honest status

This page exists because the brief asks for it in several places at once:
record build identifier and conditions with every claim (§20), label generated
art versus gameplay (§12), and never label a successful export or a high test
count as completion of the commercial vision (§23). Read this page before
reading any other claim in this repository.

**Target platform: PC.** The supplied brief is titled for a mobile edition; the
project was retargeted to PC after it was written. `docs/00` records exactly
what that cost.

## What was actually produced, and in what environment

The work was produced by an AI agent in a Linux container with **no Godot
binary, no GPU, no Windows machine, no Steam account, no 3D art pipeline and no
audio recording chain**. That shapes every statement below.

| Claim | Status | Evidence |
|---|---|---|
| Simulation rules are correct | **Verified** | 182 tests pass under `node web/tests/run-all.js`. Run it yourself; it takes about a second and needs no install. |
| Exactly-once mission consequences | **Verified** | 18 cases including process termination at all six transition boundaries. |
| Deterministic turn resolution | **Verified** | Same `(state, seed)` gives a byte-identical state digest over 120 turns. The GDScript PRNG was checked to produce a bit-identical stream to the JavaScript one. |
| Save integrity, last-known-good, migrations | **Verified** | Includes a test that cuts a write short mid-file and asserts the previous save still loads. |
| Stealth and weapon rules | **Verified** | Includes the brief's named cases: wall-pushing footsteps, airborne footsteps, death during reload, quality-independent detection. |
| PC input: binding table, contexts, clash detection, presets | **Verified** | 17 cases in `suite-input.js`, plus `python3 -I tools/check_input_bindings.py`, which found a real clash (`end_turn` and `pause` both on gamepad Start). |
| Content and editorial rules | **Verified** | Locale parity at 346 keys, citation policy, sensitive-chapter gating, separation of the 1940 sealing / 1943 ghetto uprising / 1944 city uprising. |
| District is reachable and coherent | **Verified** | The authoring tool flood-fills from the spawn and refuses to emit a district where any objective is walled off. 644 walkable cells + 252 hedgerow banks = 896 total, with nothing unaccounted. |
| The hybrid loop is playable | **Demonstrated** | The prototype plays map → mission → map with real consequences, with keyboard and mouse. |
| The Godot 4 project compiles and runs | **NOT VERIFIED** | No Godot binary existed in the authoring environment. The GDScript mirrors the verified JavaScript and `godot/tests/test_runner.gd` mirrors the suite, but **it has never been executed.** Treat the first run as a debugging session, not a demonstration. |
| Commercial art quality | **NOT MET** | Every mesh is a procedural or box blockout. Every material is generated. Every character is a jointed blockout. The district data says so in `art_status.statement`, the prototype prints it on screen, and the provenance registry marks every placeholder `may_ship: "never"`. |
| Forward+ features look right | **NOT VERIFIED** | SDFGI, SSIL, SSAO, volumetric fog, SSR and FSR2 are all configured and exposed as settings. **None has been seen rendering.** They are the reason the art bar is reachable and they are also the most likely place for a visual regression on the floor GPU. |
| Audio | **NOT PRESENT** | The routing, priority, reverb, occlusion, repetition, mono and headphone rules are implemented and tested. There is **no sample bank**: nothing audible has been recorded or licensed. |
| Performance | **UNMEASURED** | Every number in `docs/10` is an engineering target. No frame time, memory figure or VRAM figure has been measured on any GPU. The 60 FPS floor is a commitment, not a result. |
| Steam Deck | **UNTESTED** | No Deck was involved. Do not put a Deck badge on the store page. |
| Windows build / Steam depot | **NOT PRODUCED** | Needs Godot export templates and a Steam partner account. `docs/12` has the exact steps. |
| Historical citations | **PENDING** | Every record in `shared-data/historical-records.json` carries `review_status: pending_citation` or `pending_specialist_review` with `sources: []`. **No citation was invented.** |

## Specific things that are deliberately *not* claimed

- **The Anne Frank theme.** The brief asks for Anne Frank-inspired hiding-place
  themes. The real history is carried as a **reference-only** record cited in
  the journal. The playable content is an original fictional household
  (`fict_household_lindenweg`) in an original building, explicitly labelled
  fiction. No district reconstructs the Prinsengracht annexe and nothing here
  may be presented as it.
- **Ghettos, camps and extermination centres.** Separate records, separate
  dates, separate treatment notes. No "camp survival loop" exists and none may
  be written without the specialist sign-off the data demands.
- **"Every weapon of the war."** Six entries ship: four weapons and two tools,
  each with its own handling, reload rules and audio event list. The registry is
  structured for staged expansion; it does not claim comprehensive coverage.
- **Competitive comparison.** No 2027 competitor has been assessed, because
  none has shipped. The art and audio bars in `docs/06` and `docs/07` are
  written as reviewable criteria against the owner's own reference pack, which
  the authoring environment never received.
- **German market.** `docs/11` flags a ratings and legal question about
  depicting period insignia in Germany. **I do not have a verified current
  answer, I did not invent one, and I have no source to cite.** It needs a
  German lawyer or the USK directly. It is flagged early because the answer
  decides whether the game ships one art set or two, which is an art-production
  decision.
- **The existing Windows project.** It was described in the brief but not
  supplied. Nothing here was ported from it, reused from it, or verified
  against it. `docs/11` lists the audit that has to happen first — and that
  audit is now *more* valuable than it was, because a desktop Forward+ project's
  shaders and model complexity are relevant to a PC target rather than
  something to strip for a phone.

## What to do first

1. Run `node web/tests/run-all.js`. If it is green, the rules are sound.
2. Play the prototype and judge the loop and the controls.
3. Open `godot/` in Godot 4.3 and run
   `godot --headless --path godot --script res://tests/test_runner.gd`.
   Expect failures from untested translation; fix them against the JavaScript.
4. Export a Windows build (`docs/12` Part D) and look at the Forward+ lighting
   on a real GPU. That is the single biggest unknown in this repository.
5. Then read `docs/11` and fix the values the brief says the owner has not yet
   fixed.
