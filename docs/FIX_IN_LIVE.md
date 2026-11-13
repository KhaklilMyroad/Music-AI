# From a finished recording to a clean Live Set (instructions for the Claude Code session on the user's computer)

Goal: the user brings a finished track (for example from Suno) as one audio file or as a folder of stems. You run
the fix stage, read its report with the user, and rebuild the track in Ableton Live on a round, steady tempo, with
real instruments playing the repaired MIDI. Work one stage at a time, read back after every write, and stop where
it says STOP. The user's ears decide. The tool checks notes and timing, not sound.

Nothing in this document has been run against a real Suno track or a real Live yet. Report what does not behave
as described instead of working around it silently.

## Stage 0: get the tool

```
cd C:\Users\ronen\track2ableton
git fetch origin claude/vigilant-planck-d78nmz
git checkout origin/claude/vigilant-planck-d78nmz -- track2ableton tests docs pyproject.toml
py -m pip install -e ".[live]"
py -m pytest tests/test_fix.py -q
```

Expected: `36 passed`. If the source is one mixed file and not a stem folder, the tool has to separate it itself;
that needs Demucs for usable stems: a large download with PyTorch, installed in its own environment as
`docs/VOCAL_IN_LIVE.md` describes (ask the user first).
With a stem folder nothing is separated and Demucs is not needed.

## Stage 1: run the fix

```
py -m track2ableton.fix "<folder of stems, or the audio file>" -o "<project folder>"
```

Add `--bpm N` only if the user asked for a specific tempo; the default is the measured tempo rounded to a whole
number. If the user knows roughly what the song's tempo is now, add `--about-bpm N` (it keeps the analysis from
reading the tempo at twice or half), and `--beats-per-bar N` if they know the metre and the report got it wrong. Then read `FIX_REPORT.md` and `fix.json` in the output folder and tell the user, in Hebrew, in a few lines:

- measured tempo, project tempo, the stretch in percent, and whether the tempo drifts;
- any stretch the report says was followed blind, where the beat was found again, or where the map lost the beat:
  those are the places to check. If the report says the tempo is not steady and could not be followed, or warns
  that the stretch is large (the tempo may have been measured at half or double), stop here and tell the user;
- the key and the chord loop;
- per track: notes before and after, and how many bars were voted on out of how many;
- files that were left out of a stem folder, and stems whose kind was guessed as "other".

If a stem was classified wrongly (the report lists each track's kind), rename the file so its name says what it is
(Drums, Percussion, Bass, Vocals, Guitar, Keyboard) and run again.

STOP: the user confirms the tempo and the stem list before anything is built.

## Stage 2: open the set

The output folder has `<name> Rebuild.als`: project tempo set, every stem on a `REF` audio track with warp markers
that pin its real beats to the grid, one MIDI track per part with the repaired notes, and the devices the analysis
suggests. Ask the user to open it in Live.

If Live refuses the file: ask the user to save an empty set from their Live with one MIDI track, one audio track and
one return track, and run the fix again with `--template "<that set>"`. If that also fails, build it through the
bridge: set the tempo, create an audio track per stem with `create_audio_clip` at arrangement position
`arrangement.song_start_beat` from `recipe.json`, create MIDI tracks and write the notes from `MIDI/`. The bridge
cannot write warp markers; with Live closed and a backup made, write the pairs in
`arrangement.warp_markers_sec_beat` (second, arrangement beat) into each stem clip's `WarpMarkers` in the .als
(`BeatTime` is relative to the clip start: subtract the first pair's beat), and verify with a diff.

Then, through the bridge, on every `REF` stem clip: warp mode Beats for drum stems and Complex Pro for the others
(`set_clip` with `warp_mode`; read the clip back to see which number your Live reports for each mode).

## Stage 3: check the timing by ear and by measurement, then STOP

Ask the user to export the drums `REF` stem alone (start 1.1.1, the whole song, 24-bit WAV, normalize off) and
measure: kicks within about 10 ms of the grid from the first bar to the last. If the end of the song is later or
earlier than the start, the beat map is off: report the numbers, do not nudge clips by hand.
The user listens to the stems against the metronome. STOP for their verdict.

## Stage 4: rebuild part by part

One part at a time, in this order: kick, the rest of the drums, bass, chords, leads. For each:

1. Solo the `REF` stem and the MIDI track together. Load an instrument from what is installed on this computer
   (search the browser; the recipe names a starting point) and match the stem's sound: register, attack, length.
2. Compare the MIDI with the stem by ear. `MIDI_raw/` has the notes as first heard if a repair looks wrong: a
   one-off figure in the middle of a phrase can be voted away, and an error that repeats every time survives.
3. Drums: `Samples/` holds one-shots cut from the stem; replace them with better samples of the same kind when the
   user wants a new sound, keeping the notes.
4. Bass: Operator or the instrument the user picked, Voices = 1, sidechain from the kick. The report says how many
   bass notes start together with a kick.
5. Mute the `REF` stem when the rebuilt part holds up, and say so. The vocal stays audio.

Every sample that did not come from the stems gets a row in LICENSES.md. STOP after each group for the user's ears.

## Stage 5: arrangement, mix, master

The report lists the sections and flags lengths that are not whole 4-bar phrases. Section boundaries are estimates
(a bar or two either way); cutting or adding bars is the user's decision, made in the Arrangement with them.
After that the usual stages apply: automation and transitions, mix, master (club about -9 LUFS, streaming -14,
true peak at most -1 dBTP), with an export and a measurement after each.
