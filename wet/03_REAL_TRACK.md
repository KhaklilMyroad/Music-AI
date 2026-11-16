# Wet test, stage 3: a real track, start to finish

- Date: 2026-11-13 (steps 1 and 2) and 2026-11-15 (step 2 third attempt, steps 3 to 7)
- Live version: 12.4.16 Suite
- Tool commit: 6a4e0f8 (`origin/claude/vigilant-planck-d78nmz`)
- Bridge version: not available from any tool output (see `00_DOCTOR.md`)

Source: `C:\Users\ronen\Downloads\Manananaaaa\Manana`, 12 WAV stems (44.1 kHz, 24-bit, stereo, 289.9 s each,
73.2 MB each), plus `.asd`, two `.mid` and one `.html` file. (The chat first said 13 stems; the count is 12.)

The user's answer about the song: tempo "about 146", metre "4/4". Passed as `--about-bpm 146 --beats-per-bar 4`.

## Step 1: the fix stage, up to its first STOP

Call:

```
py -m track2ableton.fix "C:\Users\ronen\Downloads\Manananaaaa\Manana" -o "C:\Users\ronen\track2ableton\wet\03_manana" --about-bpm 146 --beats-per-bar 4
```

### First run: FAIL after 96 s, out of memory

It got through decode, tempo, loudness and the five drum stems, then died on the bass stem:

```
File "...\track2ableton\pipeline.py", line 292, in run
    trans = tr.mono_to_midi(m, sr, to_beats, 28, 420, tonal.tuning_cents)
File "...\track2ableton\transcribe.py", line 213, in mono_to_midi
    f0, ap = dsp.yin(x, SR, fmin, fmax, frame_len, hop)
File "...\track2ableton\dsp.py", line 144, in yin
    acf = np.fft.irfft(spec_full * np.conj(spec_head), nfft, axis=1)[:, : tau_max + 1]
numpy._core._exceptions._ArrayMemoryError: Unable to allocate 1.52 GiB for an array with shape (49944, 2049) and data type complex128
```

Machine at that moment: 23.4 GB RAM, 6.9 GB free, 7.3 GB free virtual memory; Live, two Edge processes and
rekordbox open. Python 3.13.2 64-bit, numpy 2.5.4. `dsp.yin` builds whole-song arrays of 1.5 GiB each, several at
a time, for a song under five minutes. It left a half-written output folder (five drum MIDI files and samples, no
report) and no message other than the traceback.

### Second run, same command, nothing changed: PASS, 238 s

Per-stage times from the console: decode 5.7 s; tempo, key, chords, structure 28.2 s; loudness 9.7 s; drum stems
about 8 s each; bass 27.3 s; piano 19.7 s; guitar 18.4 s; other 21.5 s; vocals 13.3 s; backing vocals 30.3 s; lead
vocals 14.0 s; writing 0.1 s. Free RAM afterwards 8.5 GB. So the failure depends on how much memory happens to be
free; it is not reproducible on demand.

### What `FIX_REPORT.md` and `fix.json` say

| | |
|---|---|
| Measured tempo | 145.5 BPM, 4/4 |
| Project tempo | 146 BPM, stretch +0.34 % |
| Drift | **yes.** "beats sit up to 216 ms away from a constant grid (143.95-146.53 BPM)". 54 warp markers follow the tracked beats |
| Beat lost | **-0.6 to 26 s and 171.1 to 190.8 s**: "Notes and warp markers there are not reliable." |
| Followed blind | -0.6 to 5.1 s and 287.4 to 290 s |
| Key | F minor, confidence 0.46 of 1 |
| Chord loop | none found |
| Sections | 15, bars 2 to 177; 10 of them are not a multiple of four bars |
| Finding | Bass: 201 of 619 notes start together with a kick |

Warnings, exactly as written:

- "Tempo searched around the 146 BPM that was given."
- "Tempo drifts across the track (live playing or tempo automation). The grid is an average."
- "Tempo is not steady: beats sit up to 216 ms away from a constant grid (143.95-146.53 BPM). Notes and warp markers follow the tracked beats."
- "The beat could not be followed in -1-26 s, 171-191 s (a sudden tempo change is the usual reason). Notes and warp markers there are not reliable."

Stems: all 12 went in, `skipped_files: []`. Kinds as classified:

| File | Track | Kind | Notes before / after |
|---|---|---|---|
| drums.wav | Drums | drums | 2051 raw; kick 670/662, snare 1159/1183, closed hat 133/134, open hat 32/32, perc 57/57 |
| kick.wav | kick | drums | kick 477/486, **snare 108/111**, perc 19, closed hat 3 |
| snare.wav | snare | drums | **kick 549/531**, snare 378/368, closed hat 21, perc 13, open hat 4 |
| toms.wav | toms | drums | **kick 459/462**, snare 17, perc 17, closed hat 2 |
| cymbals.wav | cymbals | drums | **snare 1029/1054, kick 237**, closed hat 153/156, perc 85, open hat 25 |
| bass.wav | Bass | bass | 648 / 619 (26 removed, 17 added with guessed pitch, 8 octave, 2 semitone); 52 of 131 bars voted |
| piano.wav | Piano / Keys | piano | 3217 / 3201; 0 of 172 bars voted |
| guitar.wav | Guitar | guitar | 3526 / 3519; 0 of 174 bars voted |
| other.wav | Synths / Other | other | 1977 / 1966; 0 of 115 bars voted |
| vocals.wav, lead_vocals.wav, backing_vocals.wav | three vocal tracks | vocals | 357, 69, 320; not repaired (vocals stay audio) |

Written to `wet\03_manana`: `Manana Rebuild.als` (448 KB), `FIX_REPORT.md`, `fix.json`, `recipe.json`,
`REBUILD.md`, `report.html`, `MIDI/`, `MIDI_raw/`, `Samples/`, `Stems/`.

### Observations on step 1

1. **Overlapping stems are all used.** The folder holds a full `drums` stem and also `kick`, `snare`, `toms`,
   `cymbals`; a full `vocals` stem and also `lead_vocals`, `backing_vocals`. The tool makes a track for each and
   does not say that the same sound is now in the Set twice. Played together the drums and the vocals would double.
2. **A single-drum stem is transcribed as a whole kit.** The `kick` stem yields 108 "snare" notes, the `snare`
   stem 549 "kick" notes, the `toms` stem 459 "kick" notes, the `cymbals` stem 1029 "snare" notes. The file name
   says what the instrument is; the classifier ignores it. `Samples/kick/snare.wav` and the like follow from that.
3. Piano, guitar and other: 0 bars voted, so "repair" there only removed 7 to 16 notes. 3200 to 3500 notes per
   polyphonic stem.
4. Negative times in the report ("-0.6 s", "-1-26 s").
5. The report says the beat was lost for the first 26 seconds and for 20 seconds near 2:51 to 3:11. By
   `docs/FIX_IN_LIVE.md` those are "the places to check", not a reason to stop; the stop condition (tempo "not
   steady and could not be followed", or a large stretch) is not met: stretch is 0.34 %.
6. **`Stems/` is a full copy: 12 x 73.2 MB = 878 MB inside `wet\`.** WET_TEST.md's way to send the reports back is
   `git add wet`. That would commit 878 MB of the user's audio. Exclude `wet/03_manana/Stems` (and decide about the
   rest of that folder) before any `git add`.
7. The out-of-memory crash leaves a partial output folder that looks like a normal one until `FIX_REPORT.md` is
   found missing.

**STOP (from `docs/FIX_IN_LIVE.md`): the user confirms the tempo and the stem list before anything is built.**

User's answer: to "Are 146 BPM and 4/4 right for the song?" they wrote "1. yes". The second question (keep all
12 stems, or run again without the full `drums` and `vocals` stems) was not answered; the test goes on with the
Set as built, doubles included.

## Step 2: the `.als` in the user's Live — FAIL, Live crashes

The user opened `wet\03_manana\Manana Rebuild.als` in Live 12.4.16 Suite. Their words: "It did not open, I took a
screenshot with the error message". The screenshot (22:30:53) is Live's own dialog:

```
A serious program error has occurred.
Live will shut down after this message box is closed.
Please restart Live and follow the instructions in the 'Report a Crash' lesson that will appear in Live's Help View.
```

From Live's `Log.txt` and `Live Reports`:

- Two crashes within 40 seconds: process 40324 at 22:30:10 and, after Live came up again, process 55512 at
  22:30:47 (`Ableton Crash Report 2026-11-13 223017 Live 12.4.16.zip` and two `.dmp` files).
- The second one is fully logged. 22:30:46.27 "Loading document ...Manana Rebuild.als", then within half a
  second **37 lines of `Exception: The file "<name>" could not be opened.`**: every stem (`Drums.wav`,
  `cymbals.wav`, `kick.wav`, `snare.wav`, `toms.wav`, `Bass.wav`, `Piano_Keys.wav`, `Guitar.wav`,
  `Synths_Other.wav`, `Vocals.wav`, `backing_vocals.wav`, `lead_vocals.wav`) and every drum one-shot. Then
  "Loaded document was created by Ableton Live 12.4.5", "Begin ExchangeDocument", "LSongAgent: End SetSongUnit",
  and the crash.
- The first crash took the unsaved stage 2 test Set with it (nothing of the user's).

What is in the file (read by unpacking it, not changed):

- Header `Creator="Ableton Live 12.4.5"`, `MinorVersion="12.0_12402"`. The Live that opens it is 12.4.16.
- 12 audio tracks, 32 MIDI tracks, 12 audio clips, 32 MIDI clips, 648 warp markers, 35 different files referenced.
- A file reference looks like this, and the path exists on disk:
  ```
  <RelativePathType Value="3" />
  <RelativePath Value="Stems/Drums.wav" />
  <Path Value="C:/Users/ronen/track2ableton/wet/03_manana/Stems/Drums.wav" />
  <OriginalFileSize Value="76712876" />
  <OriginalCrc Value="0" />
  ```
  All 35 referenced paths were checked for the first eight: they exist. Why Live says they "could not be opened":
  not found. Whether the unopened files, the 12.4.5 template under 12.4.16, or something else is what crashes
  Live: not known. The crash dump was not analysed.

Expected (`docs/FIX_IN_LIVE.md`): the Set opens with every stem on a `REF` track with warp markers. Observed: the
most serious failure of the wet test so far. A generated file must never be able to take Live down; and here it
took down a Live that had an unsaved Set open.

Next, as `docs/FIX_IN_LIVE.md` prescribes for "Live refuses the file": the user saves an empty Set from their own
Live with one MIDI track, one audio track and one return track, and the fix runs again with `--template`. Not
done yet.

### Second attempt, with the user's template

- 22:36: the user opened Live again. Through the bridge the default Set was trimmed to one MIDI track
  (`1-MIDI`), one audio track (`2-Audio`) and one return (`A-Reverb`): `delete_track` on "4-Audio", "2-MIDI" and
  "B", each "true"; `meters` then lists `1-MIDI`, `2-Audio`, `Main`, and a send "B" is "out of range (1 sends)".
- 22:38: the user saved it as `wet\Template Project\Template.als` (10 KB).
- Fix run again with `--template "...\wet\Template Project\Template.als"` into `wet\03_manana_tpl`: exit code 0,
  225 s, same numbers as before (145.5 to 146 BPM, +0.34 %, drifting, 54 warp markers, F minor). New
  `Manana Rebuild.als`: 450 KB. No out-of-memory failure this time.
- Result of opening it in Live (2026-11-15, 13:36): **FAIL, Live crashes again.** The user's words: "It crashed
  with the same error message as before". `Log.txt`: 13:36:35 the same run of `Exception: The file "<name>" could
  not be opened.` for every stem and one-shot, 13:36:35.98 "Loaded document was created by Ableton Live 12.4.16",
  13:36:38.20 "Aborting with crashdump". Crash pack: `Ableton Crash Report 2026-11-15 133700 Live 12.4.16.zip`.
  So the 12.4.5 header was not the cause: with the user's own 12.4.16 template the file still takes Live down.
  The `--template` fallback in `docs/FIX_IN_LIVE.md` does not help here.

### Third attempt: built through the bridge (`rebuild_in_live`) — PASS, with differences

Live restarted by the user (13:36:58), default Set, `T2A_Bridge` active. One call:
`rebuild_in_live(project_dir="...\wet\03_manana_tpl")`. No error, Live stayed up. It reports: "tempo 145.5", 12
`REF` audio tracks "stem in slot 0", 9 MIDI tracks with devices and notes "in slot 0" (Drums 2068, cymbals 1557,
kick 619, snare 937, toms 498, Bass 619, Piano / Keys 3201, Guitar 3519, Synths / Other 1966).

So Live opens these same stem files without complaint when they come through the bridge; the "could not be
opened" lines belong to the generated `.als`, not to the audio.

Read back with `get_track` (`REF kick`, `kick (Drums)`), differences from what `docs/FIX_IN_LIVE.md` describes:

1. **Tempo set to 145.5, the measured tempo, not the project tempo 146** of `fix.json` / `recipe.json`
   (`arrangement.project_bpm: 146.0`).
2. **Everything is in Session slot 0, nothing in the Arrangement.** The REF clip starts at clip beat 0;
   `arrangement.song_start_beat` (3.53) is not applied. The MIDI clip is 700 beats, the audio clip 702.17: the
   notes follow the tracked beats, the stem follows Live's own straight warp, with no offset between them set.
3. REF clip: `warping: true`, `warp_mode: 0` (Beats) for every stem; length 702.17 beats for 289.9 s. No warp
   markers written (documented: the bridge cannot write them). The 54 markers of the fix are lost on this path.
4. REF tracks are muted. The Drum Racks are empty (`"chains": []`): the five drum MIDI tracks make no sound, the
   one-shots in `Samples/` are not loaded.
5. "skipped 'Grand Piano (Core Library, Sampler)'" and "skipped 'Simpler (load the guitar stem slice)...'": Piano
   and Guitar tracks have effects and notes but no instrument.
6. "suggested send A Reverb -10 dB (create returns, then use set_send)" although return `A-Reverb` exists.
7. The four tracks of the default Set (`1-MIDI`, `2-MIDI`, `3-Audio`, `4-Audio`) stay in front, empty.
8. One-drum stems as whole kits again (kick track: 619 notes on four drums).

Then the documented manual step, for the timing check: `set_song(tempo=146)` and
`create_audio_clip(track="3-Audio", file_path="...\Stems\kick.wav", position=3.5295438076188295)`. Answer
`{"arrangement_clips": 1}`. Read back: clip at 3.5295, length 703.056 beats, `warping: true`, `warp_mode: 0`.
703.056 beats for 289.9 s is a straight 145.5 BPM grid: no drift correction. Side effect: the track was renamed
by Live from `3-Audio` to `3-kick`, so the next call by name failed ("no track named '3-Audio'").

## Step 3: timing against the metronome

Set up through the bridge: metronome on, track `3-kick` soloed (the kick stem alone, Arrangement, straight warp,
project tempo 146). The user listens at the start, the middle and the end.

The playhead was set with `set_song(time=...)`; the user pressed Space and listened about 20 s each time.

| Place | Playhead (beats) | About | User's words |
|---|---|---|---|
| Start | 104 | 0:43 | "Sits exactly on the metronome" |
| Middle | 352 | 2:25 | "Sits exactly on the metronome" |
| End | 640 | 4:23 | "Sits exactly on the metronome" |

RESULT: PASS at the three places heard. No half-beat offset, so no STOP.

Limits of this result:

- The start was heard from 0:43, not from the first bars, because the fix report says the beat was lost up to
  26 s. The first 26 s and 2:51 to 3:11 (the two "beat lost" ranges) were **not listened to**.
- What was heard is the kick stem on Live's own straight warp (703.056 beats for 289.9 s) at 146 BPM, placed at
  `song_start_beat`. It is not the fix's 54 warp markers; those exist only in the `.als` that crashes Live.
- To note for the repository: the fix report says "beats sit up to 216 ms away from a constant grid" and
  "drifting", yet on a constant grid the user hears the kick exactly on the click at 0:43, 2:25 and 4:23. Whether
  the drift is real but elsewhere, or the tracker's own error: not checked.
- `set_song(time=...)` answered `"time": 0.0` twice and 3.53 once (the old position). `live_session` after the
  second call showed `current_song_time: 352.0`; the third move was confirmed only by the user not objecting.

## Step 4: `sample_pack`

Call: `sample_pack(source="...\Downloads\Manananaaaa\Manana", about_bpm=146, beats_per_bar=4,
out_dir="...\wet\03_pack")`. No error. Run time: not measured.

Result: tempo 145.5 (confidence 0.7, `tempo_steady: false`), F minor (0.46), 62 four-bar loops (six per stem;
guitar two; piano none), 13 one-shots, `skipped_files: []`.

`left_out`, as written:

- "backing_vocals: 1 loop(s) more than 18 dB under the stem's loudest, left out as bleed"
- "piano: nearly empty (-42 dB against the mix), probably bleed"
- "vocals: 1 loop(s) more than 18 dB under the stem's loudest, left out as bleed"

`notes`, as written:

- "The tempo is not steady: each loop is cut between the bar lines that were found, so its tempo is its own (see
  bpm) and moves a little inside it."
- "88 loop position(s) were left out because the beat could not be followed there (a sudden tempo change)."
- "Loop starts were moved by up to 30 ms to sit on a hit: the tempo that was found is slightly off, so the grid
  slides along the song. The loops themselves start on their hits."

Observations:

1. Loop tempos in the file names run from 144.4 to 146.7 BPM; `start_moved_ms` is exactly -30.0 (the limit) for
   8 loops, so for those the hit may be further away than the move.
2. **`sample_pack` calls the piano stem "nearly empty ... probably bleed"; the fix stage transcribed 3201 notes
   from the same piano stem** and built a track for it. The two tools disagree about the same file and the fix
   report does not carry this warning.
3. Here one-shots from `kick`, `snare`, `toms` are labelled "from the stem's name" (one piece each), unlike the
   fix stage, which turned those stems into whole kits. `cymbals` still yields a "kick" and a "snare" one-shot.
4. Loops are also cut from both `drums` and its sub-stems, and from `vocals` and its sub-stems (doubles again).
5. Loud make-up gains on quiet loops: `gain_db` up to +14.9 (lead_vocals 06), +14.1, +13.8.

Loops in the Set: the user is not at ease in Live's interface, so instead of dragging, the bridge placed them
(`create_audio_clip`, track index 3, Session slots 0 to 2): `Manana_drums_4bar_146bpm_03.wav`,
`Manana_bass_4bar_146bpm_Fm_03.wav`, one-shot `Manana_kick_kick.wav`. Read back: both loops `length: 16.0`,
`looping: true`, `warping: true`; the one-shot `warping: false`, 0.686 s. So Live takes each loop as exactly
four bars at the project tempo.

User's verdict, drums loop (`Manana_drums_4bar_146bpm_03.wav`, fired with `clip_action fire`, metronome on):
"The loop comes back smoothly and sits on the metronome". PASS.

User's verdict, bass loop (`Manana_bass_4bar_146bpm_Fm_03.wav`): "Comes back smoothly and sits on the
metronome". PASS.

Kick one-shot "starts on time?": NOT CHECKED (the user does not launch clips in Live themselves, and a launch
through the bridge is quantised, so it would not answer the question).

Only two of 62 loops were heard, both with a file-name tempo of 146; loops named 144.4 or 146.7 BPM and the
eight loops moved by the full 30 ms: not heard.

## Step 5: `clash_report`

Call: all 12 source stems, `bpm=146`, `beats_per_bar=4`. No error. **The answer is 59,332 characters and was
refused by the client as too large**; it was read from the saved file (copy: `wet\03_clash_report.json`). 66
pairs.

The worst three pairs as the tool orders them (share of the mix):

| # | Pair | clash | when both play | share of the mix | worst bands |
|---|---|---|---|---|---|
| 1 | drums / kick | 0.999 | 1.0 | 0.121 | 50-63, 40-50, 63-79 Hz |
| 2 | vocals / backing_vocals | 1.0 | 1.0 | 0.099 | 635-800, 1270-1600, 504-635 Hz |
| 3 | drums / cymbals | 0.999 | 1.0 | 0.064 | 10-12.8 k, 12.8-16 k, 8-10 k Hz |

All three are a stem against a part of itself (the kick is inside the drums stem). #4 (drums / snare) and #7
(vocals / lead_vocals) are the same. The tool does not notice; a clash of 0.999 is the giveaway and could be
used to say "these two are the same sound, drop one". As a mixing finding the top of the list is empty.

The first three pairs that are two different sounds:

| # | Pair | clash | when both play | share of the mix | worst bands | tool's note |
|---|---|---|---|---|---|---|
| 5 | drums / vocals | 0.322 | 0.392 | 0.042 | 800-1008 Hz, 10-12.8 k, 2-2.5 k | "They use the same bands but not at the same moments: they take turns, and need no carving." |
| 6 | drums / bass | 0.253 | 0.298 | 0.042 | 63-79, 159-200, 50-63 Hz | same note |
| 10 | bass / other | 0.276 | 0.456 | 0.030 | 159-200, 126-159, 79-100 Hz | none |

Compare with the fix report's own finding, "Bass: 201 of 619 notes start together with a kick ... the sub needs
sidechain or a shorter kick": `clash_report` says of kick / bass (#11, clash 0.238) "they take turns, and need
no carving". The two tools give opposite advice about the same kick and bass.

User's answer (is that what they hear?): **none.** The pairs were read to the user and the question asked
twice; both replies answered only the loop question. Agreement or disagreement: not known.

## Step 6: `match_reference` / `verify_reference`

NOT RUN. The user's words: "skip the reference".

## Step 7: `split_stems`, `vocal_score`

NOT RUN. The user was asked whether to test them now and did not answer.

## Stage 3 outcome

| Step | Result |
|---|---|
| 1. Fix stage | PASS on the second run; first run died out of memory (1.52 GiB array in `dsp.yin`) |
| 2. The `.als` in Live | **FAIL twice: the generated Set crashes Live 12.4.16**, with the built-in template and with the user's own. Built through the bridge instead (`rebuild_in_live`): works, but Session only, tempo 145.5 not 146, no start offset, no warp markers, empty Drum Racks |
| 3. Timing | PASS at 0:43, 2:25, 4:23 in the user's words, on the kick stem with Live's straight warp. The fix's own warp markers were never heard |
| 4. `sample_pack` | PASS: two loops heard, both loop cleanly on the click. One-shots not checked |
| 5. `clash_report` | Ran; the worst three pairs are stems against their own sub-stems; answer too large for the client; user gave no verdict |
| 6. Reference | Not run (user skipped) |
| 7. Stems / vocal score | Not run |

The findings to carry back, most serious first:

1. The `.als` writer produces a file that takes Live down (37 "could not be opened" lines, then
   "Aborting with crashdump"), and `--template` does not cure it. The same audio files load through the bridge.
2. `dsp.yin` allocates whole-song arrays and fails when about 7 GB is free.
3. `rebuild_in_live` does not build what the fix describes (tempo, Arrangement position, warp markers, drum
   samples).
4. Overlapping stems (a full stem and its parts) are doubled by the fix, by `sample_pack` and flood
   `clash_report`; none of the three says so.
5. The tools contradict each other on the same files: piano "nearly empty, probably bleed" against 3201 piano
   notes; kick and bass "need sidechain" against "take turns, need no carving"; "drifting, up to 216 ms off a
   constant grid" against a kick the user hears exactly on a constant grid at three places.

State left behind: Live holds an unsaved test Set (the default Set plus the rebuilt tracks); nothing of the
user's was opened or saved. `wet\` now holds two full stem copies (`03_manana\Stems`, `03_manana_tpl\Stems`,
878 MB each) and `03_pack`; exclude them before any `git add wet`.

STOP.
