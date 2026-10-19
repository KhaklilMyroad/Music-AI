# 11 — Content and device baseline (owner decisions required)

Brief §23 requires this before full production can be estimated, and states
plainly that the owner has not fixed these values. Each row below is a
**recommendation with a reason**, not a decision. Nothing here is a commitment.

## 1. Supported phone and tablet models

Recommendation: three tiers with a hard floor at a 2022 mid-range Android
(Snapdragon 695-class, 6 GB RAM), plus iPhone 13 and newer. Reason: the floor
sets every budget in `docs/10`, and the brief insists the first milestone run on
the lower supported device.

**Needs:** the first representative mobile build, then a measured pass per tier.

## 2. Theatres and districts

| | Recommended at launch | Reason |
|---|---|---|
| Theatres | 4 (as built) | Strategic scope is cheap; districts are not. |
| Authored districts | **3** — Normandy bocage, Warsaw north, London shelter | A district at the art bar in `docs/06` is the expensive unit. Three gives the brief's range (frontline, occupied city, home front) and proves the setting is not one place reskinned. |
| Registered for later | Tunis medina, Salonica port, New York lower east | Already in the register as placeholders, with their content requirements written. |

Shipping twelve districts at the stated art bar is not a first release. It is
three releases.

## 3. Mission count and types

Recommendation: **12 authored missions** at launch across 11 mission families,
with at least 7 completable without lethal action. Reason: the brief's pacing
target is 5–15 minutes of meaningful progress, so 12 authored missions plus
Sandbox gives a campaign that is substantial without being padded by moving one
objective marker to another building.

Currently authored: 3. Outlined: 6. Registered: 3.

## 4. Arsenal coverage

Recommendation: **10 weapons and 4 tools** at launch, each with its own
handling, reload rules, model and complete audio event set; the registry
structured for staged expansion. Reason: the brief's own warning — a small
generic bank must not be described as every weapon of the war. Ten done
properly is a credible claim; sixty done generically is not.

Currently: 4 weapons, 2 tools, all `model_status: blockout`.

## 5. Character and voice requirements

Recommendation: 6 principal fictional characters with faces and full animation
sets; 12 secondary civilians; 3 hostile archetypes. Voice: subtitled
performance in French, Polish, German, Hebrew/Yiddish and English as the setting
requires, with language authenticity reviewed. Reason: the brief makes
characters a priority and warns against repeated identical characters in
prominent views.

**Needs:** a casting and localisation budget, and the editorial review in
`docs/08`.

## 6. Language scope

Recommendation: ship English and Hebrew (both complete, with RTL), add French,
Polish and German in the first content update. Reason: English and Hebrew carry
the owner's stated direction and are already at full key parity; the other three
are the in-world languages and benefit most from being right rather than fast.

## 7. Offline and cloud behaviour

Recommendation: fully playable offline once required content is installed.
Optional account-based cloud backup of explicit campaign checkpoints, with
conflicts preserved and described, never merged. Reason: the brief's own
direction, and the conflict handling is already implemented and tested.

## 8. Storage and download

Recommendation: base install ≤ 2.5 GB with one district; optional district packs
of 600–900 MB each; language packs ≤ 60 MB. Show download size and available
storage; support interruption and resumption; verify integrity; provide uninstall
and cache controls.

**These are guesses.** Real figures need one district at the production art bar
with final texture budgets. Do not quote them.

## 9. Release model

Recommendation: a single paid purchase, no advertising, no in-app purchase, no
subscription, no live service. Reason: the brief specifies none of these, so
assuming any of them would be inventing product strategy. Telemetry, if any,
limited to a declared purpose with the game resilient when it is disabled.

## 10. Staffing and schedule

Not estimated, deliberately. An estimate is meaningless until items 1–9 are
fixed and one district exists at the production art bar. What can be said:

- The disciplines in `docs/00` all need named owners; one person may hold
  several, but every responsibility needs a name.
- The two unavoidable specialist roles are the **historical researcher** and the
  **narrative editor**. Four chapters cannot enter production without them.
- The iOS path requires access to macOS and Xcode. That is a procurement item,
  not a coding task.
- The first production milestone is defined in brief §23 and is the right thing
  to cost: one representative district connected to the strategic map, with
  convincing first-person hands and one complete weapon, an interior and
  exterior, combat, a stealth or civilian interaction, material-aware sound,
  persistent consequences and interruption-safe saves — **running on the lower
  supported device**.

## Audit required before any reuse of the existing Windows prototype

The brief describes a Windows project with a 0.6.3 checkpoint, 27 bilingual
chapters, 46 events, a ~66×64 m Normandy district and 41 foley clips. **That
project was not supplied and nothing here was ported from it.** Before any reuse
decision:

1. Audit the repository, assets and save contracts.
2. Likely useful: strategic models, validation rules, exactly-once outcome
   handling, historical data, test infrastructure.
3. Needs a mobile-specific review: desktop shaders, model complexity, input
   assumptions, caches, save timing, audio budgets.
4. Note the brief's own caveats about the sound update — modern recordings, the
   M1 attack processed from an indoor take, running variation reusing walking
   takes, a generic enemy rifle, and no human listening review at handoff.
5. **Do not replace the desktop source project or overwrite its saves.** Keep a
   separate branch or mobile configuration, document intentional
   incompatibilities, and retain a reproducible development checkpoint.
