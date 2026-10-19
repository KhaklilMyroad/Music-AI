# 08 — Historical research and editorial standard

Implements brief §15. This is the page that decides whether this game is
defensible. It is also the page with the most open work: **every citation in the
register is pending, and no historian or narrative editor is assigned.**

## The three kinds, kept apart

Every record in `shared-data/historical-records.json` declares exactly one:

| Kind | Meaning | What the game may do with it |
|---|---|---|
| `documented_fact` | Date and outline are established in standard reference works | Cite it in the journal. Drive dated events, access rules, availability. **A player outcome never edits its text.** |
| `reasoned_reconstruction` | A composite of typical practice, not one documented instance | Use it, and say in the journal that it is a reconstruction. |
| `game_fiction` | Original characters, households, operations and places | Play it. **Label it as fiction wherever the player can see it.** |

A mission briefing may not present an invented local action as a recorded
event. A successful fictional operation may change the campaign's *modelled*
local conditions while the historical reference entry stays accurate about what
happened in reality. That separation is enforced structurally: a MissionResult
can only reach the campaign through its chapter's `outcome_bounds`, and it has
no channel to the history register at all.

## Citation policy

`sources: []` with `review_status: pending_citation` or
`pending_specialist_review` is the **only** permitted placeholder.
**Inventing a citation is a release blocker.** A test asserts that no record has
sources without being approved, and none lacks sources without a pending flag.

Current register: 12 records — 10 `documented_fact`, 1
`reasoned_reconstruction`, 1 `game_fiction`. Four are flagged
`sensitivity: high`. Confidence is recorded as `high`, `medium` or `low`, and
`medium` means the outline is established but figures, local detail or exact
timing still need a specialist. Salonica's end date and transport counts are
flagged `medium` for exactly that reason.

## Sensitive settings

For hidden attics, ghettos, concentration camps and extermination centres, each
record must define: the point of view, the purpose, the limits of player agency,
the supporting evidence, and **what the player can actually do**. Each setting
gets its own treatment. A generic "camp survival loop" copied across places with
different histories and functions is prohibited.

A chapter marked `sensitivity: high` must carry
`gate: specialist_review_required`, and a test asserts it. That gate is a
release blocker for the chapter, not for the build.

### The three Warsaw records are three records
The 1940 sealing of the ghetto, the 1943 ghetto uprising and the 1944 city
uprising are separate records with separate dates, separate actors and separate
treatment. A test asserts their dates differ. They may never be presented as one
event.

### The 1943 uprising cannot be "won"
`chapter_wsw_03` declares `allowed_outcomes: [partial_success, failure,
withdrawal]`. There is no success outcome, by design, and a test asserts it.
Agency is granted to the defenders; the authored outcomes concern who the player
gets out and what the network retains, not changing the recorded result.

### Hiding places
The brief asks for Anne Frank-inspired hiding-place themes. The real history is
a **reference-only** record: cited in the journal, never reconstructed as a
playable building. The playable content is `fict_household_lindenweg` — an
original fictional household in an original building, flagged
`is_fictional: true` and labelled as fiction in the journal. Nothing in this
project may be described as an exact reconstruction of a real hiding place.

## Representation

- **Jewish communities are represented through their people, relationships,
  culture and agency — not solely through victimhood.** The data models
  communities with households, trades, institutions and narrative flags, and the
  civilian contract has no field that could express suffering as a score.
- Multiple perspectives are used **without suggesting false equivalence**
  between documented persecution and the actions of its victims.
- Military faction representation does not require turning participation in
  persecution into a player reward system, and no chapter does.
- Not every chapter ends in violence. Seven of eleven mission families need no
  lethal action; the Warsaw courier chapter issues no firearm at all; the London
  chapter has no enemy soldier in the district — the antagonist is fire, debris,
  darkness and time.

## Research detail that shapes perception

Architecture, street layout, languages, signage, clothing, uniforms, weapons,
transport, food, communications, social restrictions and ordinary community
life. The district data records climate, season, latitude and dated state so a
place reads as itself; Tunis is not Warsaw with a palette swap, and the chapter
register says so in its content requirements.

In-world signage stays in its own language. It is not translated into modern
English to simplify the interface.

## Content information and intensity

Contextual content information precedes sensitive chapters. An intensity setting
offers a reduced presentation, and **a reduced presentation preserves historical
meaning**: it never conceals or denies a documented event. The locale string says
so to the player directly.

## Provenance

Asset and content provenance is maintained alongside historical sourcing:
creator, source, licence, permissions, processing history and use restrictions,
in `shared-data/asset-provenance.json`. Generated assets require visual **and**
historical review before entering the approved production library.

## Open editorial work (release blockers for the chapters concerned)

1. Appoint a named historical researcher and a named narrative editor.
2. Attach real citations to all 12 records; replace or remove anything that
   cannot be cited.
3. Fix the `medium`-confidence items: Salonica's chronology and figures; the New
   York home-front organisations, which are currently a composite.
4. Specialist sign-off for `chapter_wsw_02`, `chapter_wsw_02b`,
   `chapter_wsw_03` and `chapter_sal_01` before any of them enters production.
5. Author the ghetto and camp soundscapes under editorial review, or ship
   without those settings.
