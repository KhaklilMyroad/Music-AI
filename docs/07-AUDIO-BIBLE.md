# 07 — Audio bible

Implements brief §14. The routing, priority, reverb, occlusion, repetition and
mono rules are implemented and tested. **There is no sample bank.** Nothing in
this repository is audible, and the audio acceptance gate cannot start until
recorded or licensed material exists.

## Goal

An inhabitable world with identifiable materials, mechanisms, distance and
acoustic space. Specifically required by the owner: convincing running, weapon
and ammunition sounds, streets, military operations, ghettos, camps and
bunkers — each with its own researched, location-specific production, not one
interchangeable ambience track.

## Families and required variation

| Family | Required variation and behaviour | Routing implemented |
|---|---|---|
| Footsteps and running | surface, footwear, speed, load, wetness, starts, stops, landings; multiple takes with no obvious rapid repetition | `character_foley`, 28 m, rolloff 1.8; repetition guard at 180 ms |
| Clothing and equipment | fabric and gear movement linked to the person's actual kit and motion; **no continuous rustle while stationary** | driven by measured displacement, so a stationary character is silent |
| Firearms | distinct model and action identity, mechanical operation, shot attack, appropriate tail, reload stages, empty state, distance behaviour | `weapon_shot` 900 m with a distant layer from 60 m; `weapon_mechanism` 22 m |
| Explosions and equipment | event scale, distance, material interaction; separate profiles per item actually present | `explosion` 1600 m with a distant layer from 80 m |
| Impacts | material-dependent hits and debris, with origin and obstruction consistent with the visible scene | obstruction resolved by ray against real geometry |
| Streets and occupied cities | date-appropriate traffic, footsteps, work, doors, languages, public activity, adjusted for restrictions and time of day | ambience zones per surface group |
| Rural and frontline | wind, local natural life, military activity by season, place and intensity | ambience zones |
| Interiors and bunkers | enclosure, doorway transmission, dampening, reverberation, construction-appropriate mechanical sound | 9 reverb profiles; an open doorway transmits at 0.15 occlusion, a stone wall at 0.85 |
| Hiding places | quiet, detailed movement and sound transmission that communicate risk **without random jump-scare loops** | `rv_attic`: short decay, high HF damping |
| Ghettos and camps | a researched soundscape for the particular place and period, with editorial review and restrained use of silence | **not authored. Gated on the same specialist review as the chapters.** |
| Dialogue and communication | understandable speech, contextual distance, subtitles, language authenticity, period-appropriate radio treatment | `dialogue` 35 m, top priority, subtitles with speaker identity |
| Music | original or licensed scoring supporting exploration, tension, combat, mourning and recovery without burying dialogue or environmental cues | separate bus; a plan is required before any cue is commissioned |

## Priority and the voice budget

A hard voice budget per device tier (16 / 24 / 32). Over budget, a request only
plays if it can displace a **strictly lower**-priority voice; the eviction is
recorded with what displaced what, so a QA log can show which cue lost.

```
dialogue 100 > weapon_mechanism 90 > weapon_shot 85 > player_feedback 80
> threat 70 > interaction 60 > character_foley 50 > ambience_zone 30 > prop 10
```

An insignificant prop therefore cannot cut off a reload cue or a spoken line.
A test asserts it directly.

## Layering

Where it helps: mechanism, shot body, environmental response, distant
representation. Room and obstruction treatment is assigned **per source**, by
the listener's room, not the source's. Long ambience and music stream with
bounded caches and bounded voice counts.

## The weapon audio registry

Every weapon and every relevant ammunition or mechanism variant in a shipped
release needs a row. Each registry entry in `shared-data/weapons.json` already
declares its own event list, and a test asserts no two weapons share one:

| Weapon | Events |
|---|---|
| bolt-action service rifle | fire, fire_distant, bolt_open, bolt_close, charger_insert, charger_strip, single_insert, dry, sling_shift |
| semi-automatic service rifle | fire, fire_distant, clip_insert, bolt_return, clip_eject_ping, dry, sling_shift |
| submachine gun | fire, fire_distant, mag_release, mag_insert, bolt_pull, dry, sling_shift |
| service pistol | fire, fire_distant, mag_release, mag_insert, slide_release, dry, holster |
| wire cutters | cut_stage_1, cut_stage_2, cut_complete, stow |
| medical kit | open, apply, close, stow |

Availability follows the game's faction and date rules, so a weapon's sound
cannot be heard before the weapon exists.

**A small generic sound bank may not be described as every weapon used during
the war.** The owner's long-term ambition for comprehensive coverage becomes a
named production catalogue with explicit staged coverage, or it stays
unclaimed.

## Rights and authenticity

- Historical radio or songs require an explicit source and rights record in the
  provenance registry before use.
- **Newly recorded or generated audio must never be described as an original
  wartime recording.**
- **No fabricated testimony. No invented dialogue attributed to a real victim.**
  Fictional characters are flagged `is_fictional: true` in the data and labelled
  as fiction in the journal.
- No invented recordings of suffering to make a location feel dramatic.

## Interruption and lifecycle

A phone call stops every positional voice and resumes ambience and music only.
Focus loss stops them and resumes positional audio. Neither leaves an orphan
voice. An interrupted weapon action issues `mechanism_audio_stop`, so a
cancelled reload cannot keep clicking.

## Mix validation

Required on phone speakers, ordinary wired headphones, Bluetooth output and
mono. In mono, direction is gone, so an **essential** cue is converted into a
directional caption rather than lost. Masking, repetition, clipping, delayed
events, interruption and return from background all need checking.

Waveform and level measurement support this work — the implementation exposes a
measurable mix peak so a dense-mix fixture can fail a test before anyone
listens. **Actual human listening is required for audio acceptance and cannot be
replaced.**
