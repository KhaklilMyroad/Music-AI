# 00 — Project State Matrix

Kept current per brief §21. Phase names follow the brief's seven-phase
structure. "Evidence" means something a reviewer can run or open — never a list
of file names.

**As of 2026-10-19. Target platform: PC** (Windows primary, Linux via Proton,
macOS deferred). Build: `proto-0.1.0` (web), `godot-0.1.0` (unbuilt).

> The supplied brief is titled for a mobile edition and describes an existing
> Windows Godot project as its foundation. The target is PC, so this project
> returns to that foundation: Forward+ instead of the mobile renderer, keyboard
> and mouse instead of touch, Steam instead of the app stores. **None of the
> simulation changed** — see the note at the end of `docs/02`.

| Phase | Component | Done | Evidence | Blockers | Next milestone |
|---|---|---|---|---|---|
| 0 Engine and project setup | Godot project, autoloads, **Forward+** pinned, full input map | Project config, 27 GDScript modules, 4 scenes, 30 rebindable actions | `godot/project.godot` opens in 4.3; `python3 -I tools/check_input_bindings.py` passes | **No Godot binary in the authoring environment: nothing compiled.** | Open in Godot 4.3, fix compile errors, export a Windows build |
| 1 Design and architecture | Contracts, transition machine, timeline, hardware plan | 10 contracts implemented twice, 182 passing tests, acceptance matrix, performance plan | `node web/tests/run-all.js` | None | Owner reviews `docs/02`, `docs/03`, `docs/04` and signs the contract set |
| 2 Strategic map | Mouse map navigation, orders, supply, construction, deterministic turn resolution, opposition | 124 tiles over 4 theatres, 5 facilities, 8 unit types with distinct verbs, 10 dated events | Playable in the prototype; 25 strategy tests | None | Add the remaining theatres' cities and a second playable faction role |
| 3 First person core | Keyboard and mouse, gamepad, rebinding, combat, stealth, survival, weapon state machine | 6 weapon profiles, calibrated detection model, patrol AI with 5 states, civilian priorities, **prone, lean and hold-breath** | Playable mission; 39 FPS/stealth/audio tests + 17 input tests | **Art is blockout. No audio samples.** | One district at production art quality, with recorded foley |
| 4 Scene bridge | Entry snapshot, streaming, results, recovery, return | Exactly-once commit with 6-boundary recovery, district checkpoints, save integrity + migrations, quick save and load | 18 transition tests, 14 persistence tests | None | Repeat the boundary tests on a real machine with real process kills |
| 5 Historical campaign | Chapter register, timeline, community narratives | 12 chapters (3 authored, 6 outlined, 3 registered), 12 history records, 11 mission families | `shared-data/chapters.json`; 12 content tests | **No historian or narrative editor assigned. Every citation is pending.** | Appoint reviewers; attach real citations; author `chapter_wsw_02` |
| 6 Full product and polish | Sandbox, UI, localisation, saves, audio, graphics, QA, distribution | Full PC settings set (54 options, 4 presets), en + he with RTL at 346 keys parity, accessibility defaults | Settings, input and locale tests; prototype settings panel with rebinding | Everything in `docs/13` | Content baseline fixed by the owner (`docs/11`); Steam partner account |

## What the platform change cost, measured

The core was deliberately written free of platform assumptions, and the move
tested that claim:

| Layer | Changed? |
|---|---|
| `web/src/sim/` — 14 modules: contracts, turn resolver, transition machine, saves, supply, orders, detection, weapons, audio rules | **unchanged**, all tests still green |
| `godot/core/models`, `core/util`, `gameplay/strategic` — the GDScript mirror | **unchanged** |
| `shared-data/` — theatres, chapters, weapons, history, provenance | **unchanged** (the district grew; its schema did not) |
| Renderer config, display settings, input layer, performance tiers | **rewritten** |
| District scale | 128 × 112 m → **256 × 224 m** |
| Docs | 5 rewritten, 5 patched, 4 untouched |

## Named owners required before full production (brief §21)

Every discipline below needs a named person. None is currently named.

Game director · systems architect · gameplay engineers · technical artist ·
environment artists · character and weapon artists · riggers and animators ·
UI/UX designer · illustrator · level and mission designers · **historical
researcher** · **narrative editor** · sound designer · composer · QA.

The two in bold are release blockers for the sensitive chapters, not
nice-to-haves: `shared-data/historical-records.json` will not pass its own
editorial gate without them.

## Decisions that are the owner's to make

Escalated with a recommendation, per brief §21, because they materially affect
scope, cost or release.

1. **Hardware floor.** Recommendation: GTX 1060 6 GB / RX 580 at 1080p
   `medium` 60 FPS. It sets every budget in `docs/10` and every lighting
   decision in `docs/06`, because the floor runs with global illumination off.
2. **Launch content.** Recommendation: four districts and sixteen authored
   missions. See `docs/11`.
3. **Release model.** Recommendation: single paid purchase on Steam, fully
   offline, no ads, no IAP, no anti-cheat, Steam Cloud optional.
4. **Steam Deck.** Recommendation: do not claim Deck support until a Deck has
   run the 2-hour test. A badge you cannot back is worse than no badge.
5. **Germany.** The depiction of period insignia raises a ratings and legal
   question there that decides whether the game ships one art set or two. It
   needs a German lawyer, early. See the flagged open question in `docs/11`;
   I do not have a verified current answer and did not invent one.
6. **Sensitive chapters at launch.** Recommendation: ship Normandy, London and
   Tunis first; hold Warsaw, Salonica and the hiding-place chapter until the
   specialist reviewers have signed them off. Shipping them unreviewed is the
   one risk here that cannot be fixed in a patch.
