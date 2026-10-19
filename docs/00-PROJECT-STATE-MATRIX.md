# 00 — Project State Matrix

Kept current per brief §21. Phase names follow the brief's seven-phase
structure. "Evidence" means something a reviewer can run or open — never a
list of file names.

**As of 2026-10-19.** Build: `proto-0.1.0` (web), `godot-0.1.0` (unbuilt).

| Phase | Component | Done | Evidence | Blockers | Next milestone |
|---|---|---|---|---|---|
| 0 Engine and project setup | Godot project, autoloads, Mobile renderer pinned | Project config, 25 GDScript modules, 4 scenes | `godot/project.godot` opens in 4.3 | **No Godot binary in the authoring environment: nothing compiled.** No Android SDK, no macOS/Xcode | Open in Godot 4.3, fix compile errors, produce a minimal signed Android build |
| 1 Design and architecture | Contracts, transition machine, timeline, device plan | 10 contracts implemented twice, 162 passing tests, acceptance matrix, device plan | `node web/tests/run-all.js` | None | Owner reviews `docs/02`, `docs/03`, `docs/04` and signs the contract set |
| 2 Strategic map | Touch map, orders, supply, construction, deterministic turn resolution, opposition | 124 tiles over 4 theatres, 5 facilities, 8 unit types with distinct verbs, 10 dated events | Playable in the web prototype; 25 strategy tests | None | Add the remaining theatres' cities and a second playable faction role |
| 3 First person core | Touch controls, combat, stealth, survival, weapon state machine | 6 weapon profiles, calibrated detection model, patrol AI with 5 states, civilian priorities | Playable mission in the prototype; 39 FPS/stealth/audio tests | **Art is blockout. No audio samples.** | One district at production art quality, with recorded foley |
| 4 Scene bridge | Entry snapshot, streaming, results, recovery, return | Exactly-once commit with 6-boundary recovery, district checkpoints, save integrity + migrations | 18 transition tests, 14 persistence tests | None | Repeat the boundary tests on a physical device with real process kills |
| 5 Historical campaign | Chapter register, timeline, community narratives | 12 chapters (3 authored, 6 outlined, 3 registered), 12 history records, 11 mission families | `shared-data/chapters.json`; 12 content tests | **No historian or narrative editor assigned. Every citation is pending.** | Appoint reviewers; attach real citations; author `chapter_wsw_02` |
| 6 Full product and polish | Sandbox, UI, localisation, saves, audio, graphics, QA, distribution | Full settings set, en + he with RTL and 273 keys at parity, accessibility defaults | Settings and locale tests; prototype settings panel | Everything in `docs/13` | Content and device baseline fixed by the owner (`docs/11`) |

## Named owners required before full production (brief §21)

Every discipline below needs a named person. None is currently named.

Game director · systems architect · mobile gameplay engineers · technical artist
· environment artists · character and weapon artists · riggers and animators ·
UI/UX designer · illustrator · level and mission designers · **historical
researcher** · **narrative editor** · sound designer · composer · device QA.

The two in bold are release blockers for the sensitive chapters, not
nice-to-haves: `shared-data/historical-records.json` will not pass its own
editorial gate without them.

## Decisions that are the owner's to make

These are escalated with a recommendation, per brief §21, because they
materially affect scope, cost or release.

1. **Device matrix.** Recommendation: two tiers, with the lower tier a 2022
   mid-range Android (Snapdragon 695-class, 6 GB) as the hard floor. See `docs/10`.
2. **Launch content size.** Recommendation: three districts and twelve authored
   missions at launch, not twelve districts. See `docs/11`.
3. **Release model.** Recommendation: single paid purchase, fully offline, no
   ads, no IAP, optional cloud backup. The brief says none of this was
   specified; this keeps it that way.
4. **Sensitive chapters at launch.** Recommendation: ship Normandy and London
   first and hold Warsaw, Salonica and the hiding-place chapter until the
   specialist reviewers have signed them off. Shipping them unreviewed is the
   one risk in this project that cannot be fixed in a patch.
