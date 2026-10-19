# 11 — Content baseline (owner decisions required)

Brief §23 requires this before full production can be estimated, and says
plainly that the owner has not fixed these values. Each row is a
**recommendation with a reason**, not a decision.

Revised for PC. Where a number changed from the mobile version, the reason is
given.

## 1. Supported hardware

Recommendation: minimum GTX 1060 6 GB / RX 580, recommended RTX 3060 / RX 6600
XT, Windows 10 and 11 primary, Linux via Proton tested, macOS deferred.
Reason: the floor sets every budget in `docs/10`, and a 2016-era mid-range card
is still the honest floor for a 2027 PC release.

Steam Deck is a separate verified-compatibility claim, not a free extra.

## 2. Theatres and districts

| | Recommended at launch | Changed from mobile | Reason |
|---|---|---|---|
| Theatres | 4 (as built) | — | Strategic scope is cheap; districts are not. |
| Authored districts | **4** — Normandy bocage, Warsaw north, London shelter, Tunis medina | was 3 | PC content expectations are higher and a district is no longer constrained by phone memory. |
| District size | **256 × 224 m** as built | was 128 × 112 m | Four times the area. A 400 m draw distance and 28–40 active characters make a district this size readable, where a phone did not. |
| Registered for later | Salonica port, New York lower east | — | Already in the register with their content requirements written. |

A district at the art bar in `docs/06` remains the expensive unit. Four is a
real first release; twelve is three releases.

## 3. Mission count and types

Recommendation: **16 authored missions** at launch across 11 mission families,
with at least 10 completable without lethal action. Was 12 on mobile.

Reason: the mobile pacing constraint — meaningful progress in 5–15 minutes —
relaxes on PC. Sessions are longer, so missions can be longer and fewer of them
have to carry the campaign. 16 longer missions is more content than 12 short
ones, not less.

Currently authored: 3. Outlined: 6. Registered: 3.

## 4. Arsenal coverage

Recommendation: **14 weapons and 5 tools** at launch, each with its own
handling, reload rules, model and complete audio event set. Was 10 and 4.

Reason: PC players inspect a weapon at 4K with the camera a hand's width from
the receiver. Fewer, better is still right, but the bar for "better" is higher.
The brief's own warning stands: a small generic bank must never be described as
every weapon of the war.

Currently: 4 weapons, 2 tools, all `model_status: blockout`.

## 5. Characters and voice

Recommendation: 8 principal fictional characters with faces and full animation
sets; 16 secondary civilians; 4 hostile archetypes. Subtitled performance in
French, Polish, German, Hebrew/Yiddish and English as the setting requires,
with language authenticity reviewed.

Reason: close scrutiny again. The brief makes characters a priority and warns
against repeated identical faces in prominent views; a 27-inch monitor is less
forgiving than a phone.

## 6. Language scope

Recommendation: ship English and Hebrew complete (both already at full parity
with RTL), add French, Polish, German and Simplified Chinese in the first
content update. Reason: unchanged, except that Simplified Chinese is a material
share of the PC market and is cheap to add once the string table is stable.

## 7. Saves and cloud

Recommendation: local saves plus Steam Cloud for explicit campaign checkpoints,
with conflicts preserved and described rather than merged. Add manual save
slots and quick save / quick load, which PC players expect and the mobile
build did not have.

The conflict handling is already implemented and tested; `F5` / `F9` are bound.

## 8. Storage

Recommendation: 12–18 GB installed with four districts; no download packs,
because PC players install once and the mobile content-pack machinery is not
worth its complexity here. Keep the manifest and verification code: it is what
makes a corrupt install detectable.

**These are guesses.** Real figures need one district at the production art bar
with final texture budgets. Do not quote them.

## 9. Release model and distribution

Recommendation: a single paid purchase on **Steam** first, then GOG and itch.io.
No advertising, no in-app purchase, no subscription, no live service, no
always-online requirement. Reason: the brief specified none of them, so
assuming any would be inventing product strategy.

Steam specifics that are real work and are not done: store page, capsule art,
trailer, Steamworks integration if achievements or Cloud are wanted, a demo
build decision, and the Steam Deck compatibility pass.

## 10. Content rating, and one thing to check early

Ratings move from the mobile stores to ESRB, PEGI and USK. One item deserves
attention before art production rather than after:

**Germany.** A WWII game that depicts period insignia has historically faced a
specific legal and ratings question there under §86a of the German criminal
code. My understanding is that the USK began assessing such content case by
case under the "social adequacy" clause from 2018, where previously ratings
were generally refused — **I am not certain of the current position and this is
exactly the kind of rule that changes, so it needs a German lawyer or the USK
directly, not my recollection.** It matters because the answer decides whether
the game ships one art set or two, and that is an art-production decision, not
a localisation one.

I have no verified source to cite for this and have not checked the current
position. Treat the paragraph above as a flag to investigate, not as advice.

## 11. Staffing and schedule

Not estimated, deliberately. An estimate is meaningless until items 1–10 are
fixed and one district exists at the production art bar. What can be said:

- Every discipline in `docs/00` needs a named owner. One person may hold
  several; every responsibility needs a name.
- The two unavoidable specialist roles remain the **historical researcher** and
  the **narrative editor**. Four chapters cannot enter production without them.
- The iOS/macOS problem went away with the platform change. The new equivalent
  procurement items are a Steam partner account, three test machines spanning
  the hardware matrix, and a Steam Deck if a Deck claim is wanted.
- The first production milestone, adapted from brief §23 to PC: one
  representative district connected to the strategic map, with convincing
  first-person hands and one complete weapon, an interior and exterior, combat,
  a stealth or civilian interaction, material-aware sound, persistent
  consequences and interruption-safe saves — **holding 60 FPS at 1080p on the
  minimum GPU**, not only on the development machine.

## Audit required before reusing the existing Windows project

The brief describes a Windows Godot project with a 0.6.3 checkpoint, 27
bilingual chapters, 46 events, a ~66 × 64 m Normandy district and 41 foley
clips. **That project was not supplied and nothing here was ported from it.**

The platform change makes this audit more valuable, not less: that project was
already a desktop Forward+ project, so its shaders, model complexity and audio
budgets are now *relevant* rather than something to strip for a phone. Before
any reuse decision:

1. Audit the repository, assets and save contracts.
2. Likely useful, and now more so: desktop shaders and materials, model
   complexity, strategic models, validation rules, exactly-once outcome
   handling, historical data, test infrastructure.
3. Needs review regardless: input assumptions (it predates the rebinding
   system), save timing, and the foley caveats the brief itself lists — modern
   recordings, the M1 attack processed from an indoor take, running variation
   reusing walking takes, a generic enemy rifle, and no human listening review
   at handoff.
4. **Do not replace the desktop source project or overwrite its saves.** Keep a
   separate branch, document intentional incompatibilities, and retain a
   reproducible checkpoint.
