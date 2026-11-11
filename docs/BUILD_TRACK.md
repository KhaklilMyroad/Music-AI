# Build the composed track in Ableton (instructions for the Claude Code session on the user's computer)

Goal: a complete 200-bar track at 130 BPM in A minor, built from the composer's MIDI and the drum kit and bass
instruments the user already approved by ear in `AfroTech130`. Work one stage at a time, read back after every
write, and stop for the user's approval where it says STOP. The user's ears decide; the checks only verify notes.

## Stage 0: get the composer and generate the MIDI (no Live needed)

```
cd C:\Users\ronen\track2ableton
git fetch origin claude/vigilant-planck-d78nmz
git checkout origin/claude/vigilant-planck-d78nmz -- track2ableton/compose docs/COMPOSER.md docs/BUILD_TRACK.md
py -m track2ableton.compose --out "C:\Users\ronen\Downloads\AfroTech130\composed\extended" --bpm 130 --key "A minor"
py -m track2ableton.compose --out "C:\Users\ronen\Downloads\AfroTech130\composed\radio" --bpm 130 --key "A minor" --structure radio
```

Expected for `extended`: `200 bars (6:09.2), 18 tracks, checks 15/15 passed`. Record in PLAN.md the commit hash
(`git rev-parse origin/claude/vigilant-planck-d78nmz`) and the total note count that the command prints, so a
later regeneration can be told apart. Read `composed\extended\REPORT.md` and `arrangement.json`: sections, tracks,
note counts per track and the suggested instrument for each.

## Stage 1: a separate copy of the set

Ask the user to save the open set as `AfroTech130_composed.als` in the same project folder (File > Save Live Set As).
The current `AfroTech130.als`, with the drums and bass the user approved, stays untouched as the fallback.
Take your usual snapshot of every track before changing anything.

## Stage 2: notes onto the existing instrument tracks

The composer uses the same track names as the approved T2 kit. For each of these, replace the notes of the track's
Arrangement clip (bars 1-200) with the notes of the matching file in `composed\extended\MIDI`:

| Composer file | Existing track | Group |
|---|---|---|
| 01 Kick, 02 Clap, 03 Wood, 04 Hat | Kick, Clap, Wood, Hat | DRUMS |
| 06 Shaker, 07 Conga Hi, 08 Conga Low, 09 Bongo, 10 Djembe, 11 Low Drum | same names | PERC |
| 14 Sub | Sub (Operator, Voices = 1) | BASS |
| 15 Mid Bass | Mid-bass (Drift) | BASS |

Ghost Kick: its notes must equal the new Kick notes (same count and positions).
Do not change any sample, Simpler, EQ, bus or mix setting. Read every clip back and compare with the file
(pitch, start, duration, velocity; note count per track is in arrangement.json).

## Stage 3: new tracks

Create with distinct names, inside the right group, each with one Arrangement clip from bar 1:

| Composer file | Track | Instrument |
|---|---|---|
| 05 Roll | Roll (DRUMS) | a snare or clap one-shot from the Core Library (it plays only in bars 73-80 and 137-144) |
| 12 Clave | Clave (PERC) | Clave Bright Wide |
| 13 Cowbell | Cowbell (PERC) | Cowbell Latin Ting, quiet, behind the kick |
| 16 Pad | Pad (MUSIC) | a warm string / analog pad, EQ high-pass about 120 Hz (its lowest notes are around 165 Hz) |
| 17 Hook | Hook (MUSIC) | Nylon Flamenco Guitar (or Nylon Mute Guitar); EQ high-pass 150 Hz |
| 18 Chant | Chant (VOCALS) | none yet: C3 = chant on beats 1-2, D3 = shout before the drop. Leave it muted until the user picks vocal chops |

Sidechain from Ghost Kick: keep it on Sub and Mid-bass as planned; add a light one (3-4 dB) on Pad.
Every new sample gets a row in LICENSES.md. Check monitoring = In on any audio bus you create.

## Stage 4: groove = None on every clip

Swing (57.5 %) and the skins' +6 ms are already written into the composer's notes. Every clip must have
Groove = None, otherwise the percussion is swung twice. Live gives new clips the set's default groove
(`DefaultGrooveId = 4` in this set) and the API cannot change it, so: ask the user to save and close Live, back
up the .als, set `GrooveId` to -1 on every MIDI clip, verify with a diff that nothing else changed, and reopen.

Timing targets for your checks: kick, clap and roll exactly on the straight grid (the roll uses 32nds in bars 79-80
and 143-144). Every other track, bass, pad and hook included, has its odd 16ths 0.0375 beat (17.3 ms) late: one
swing for everything, so the bass does not lead the percussion that doubles it. Conga Hi, Conga Low, Bongo, Djembe
and Low Drum sit a further 0.013 beat (6 ms) late. Exception: Conga Hi is not swung in bars 76-80 and 140-144,
where it plays 16ths beside the roll. `arrangement.json` lists which tracks are swung.

## Stage 5: export and check, then STOP

Ask the user to export `exports\composed_full.wav` (Main, start 1.1.1, length 200.0.0, WAV 24-bit, normalize off).
Run the usual checks: kick and clap within 5 ms of the grid, measured swing 57-58 %, a per-section table of what
is audible against `arrangement.json` (Break 2 has no drums; beat 4 of bars 80 and 144 has only the shout),
sub ducking 8-12 dB on each kick, mono below 120 Hz, peak below -6 dBFS.
Then STOP: the user listens to the whole track and says what to change.

## After the user's verdict

- Stage 7 from PLAN.md: risers, a high-pass rising on the Roll, a low-pass opening on Mid-bass and Hook through
  each build. These are automation, not notes.
- Stage 8 mix and stage 9 master as planned (club about -9 LUFS, streaming -14, true peak <= -1 dBTP).
- Radio edit: the same procedure with `composed\radio` (97 bars: 96 plus a closing bar) in its own copy of the set.

The user can also compare the two swing options by ear: the default swings bass, pad and hook with the
percussion; `--straight-pitched` keeps them on the straight grid.

## If the user prefers the drums they already approved

Keep the current drum clips and import only Sub, Mid Bass, Pad, Hook, Chant, Clave, Cowbell and Roll. The
composer's sections are the same 200-bar plan (drops at bars 81 and 145), so they line up. In that case remove
the existing drum notes on beat 4 of bars 80 and 144 so the gap before each drop stays empty.
