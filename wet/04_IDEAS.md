# Wet test, stage 4: ideas, from the evidence only

- Date: 2026-11-15
- Live version: 12.4.16 Suite
- Tool commit: 6a4e0f8 (`origin/claude/vigilant-planck-d78nmz`)
- Bridge version: not available from any tool output (see `00_DOCTOR.md`)

Sources: `00_DOCTOR.md`, `01_STUDIOPILOT_SITE.md`, `01B`, `02_LIVE_TOOLS.md`, `02B`, `03_REAL_TRACK.md`. Every idea
points at a row in one of them. Sizes are rough guesses by the tester, who did not read the code beyond the
tracebacks. Ranked across both groups by how much they block real use; the group is marked on each.

## A. Improves the tool for this user

### 1. The generated `.als` must open, and must never be able to crash Live

- **Evidence:** `03`, step 2. `Manana Rebuild.als` took Live 12.4.16 down three times (2026-11-13 22:30:10 and
  22:30:47, 2026-11-15 13:36:38), with the built-in template and with the user's own. Log: 37 lines of
  `The file "<name>" could not be opened.`, then "Aborting with crashdump". The first crash also took an unsaved
  Set. The same audio loads through the bridge. `--template`, the documented cure, did not help.
- **Change:** find what in the written XML Live rejects (the file references are the lead: `OriginalCrc 0`,
  `RelativePathType 3`, every sample refused) by cutting the file down until it opens: no clips, then one audio
  clip, then warp markers, then MIDI. Add a test that writes a Set and checks it against a Set that Live itself
  saved with the same content. Until it is fixed, make `rebuild_in_live` the default path and say so.
- **How we would know:** the user opens `Manana Rebuild.als` from the same 12 stems: Live stays up, the log has
  no "could not be opened" line, and 12 warped clips sit in the Arrangement.
- **Size:** days (unknown cause; could be hours once the minimal failing file is found).

### 2. `rebuild_in_live` should build what the fix describes

- **Evidence:** `03`, third attempt. It set tempo 145.5 where `recipe.json` says `project_bpm: 146.0`; put
  everything in Session slot 0, nothing in the Arrangement; ignored `song_start_beat` (3.53), so MIDI (700 beats)
  and stems (702.17 beats) are not aligned to each other; left the Drum Racks empty (`"chains": []`) with
  `Samples/` unused; skipped piano and guitar instruments; said "create returns" when return A existed. The
  tester had to add the Arrangement clip and the tempo by hand.
- **Change:** use `project_bpm`; place stems and MIDI in the Arrangement at `song_start_beat`; load the
  one-shots into the Drum Rack pads; fall back to a stock instrument instead of none; check returns before
  advising to create them.
- **How we would know:** one call, then the user presses Space: the MIDI kick and the `REF kick` stem play
  together on the click, and the drum MIDI tracks make sound. `get_track` shows `arrangement_clips` not empty and
  tempo 146.
- **Size:** days.

### 3. `dsp.yin` must not need gigabytes for a five-minute song

- **Evidence:** `03`, step 1, first run: `Unable to allocate 1.52 GiB for an array with shape (49944, 2049) and
  data type complex128` at `dsp.py` line 144, with 6.9 GB free. Same command passed minutes later. It left a
  half-written output folder with no message besides the traceback.
- **Change:** process the frames in blocks (and in complex64), so memory is bounded whatever the song length.
  On any failure, remove or mark the partial output folder.
- **How we would know:** peak memory of the fix on the Manana folder, measured, stays under 1 GB; the run passes
  five times in a row with Live and a browser open.
- **Size:** hours.

### 4. Notice overlapping stems and single-drum stems

- **Evidence:** `03`, step 1 observations 1 and 2; step 4 observation 4; step 5. The folder held `drums` plus
  `kick`, `snare`, `toms`, `cymbals`, and `vocals` plus `lead_vocals`, `backing_vocals`. The fix built a track for
  each (doubles), transcribed the `snare` stem as 549 "kick" notes and the `cymbals` stem as 1029 "snare" notes,
  and the top of `clash_report` was drums against kick at 0.999. `sample_pack` already labels one-shots "from the
  stem's name", so the knowledge exists in one tool and not in the other.
- **Change:** one shared step: when a stem is almost wholly contained in another (the 0.999 that
  `clash_report` already measures), say so and keep only the parts or only the whole, as the user chooses; when
  a file is named `kick`, `snare`, `toms`, write only that drum. `clash_report` lists such pairs apart as "same
  sound".
- **How we would know:** fix on the same folder: the report says which stems overlap, the `snare` track holds no
  kick notes, and the first three `clash_report` pairs are three different instruments.
- **Size:** days.

### 5. Make the tools agree with each other, and check the drift claim

- **Evidence:** `03`, step 3 limits, step 4 observation 2, step 5. (a) Fix report: "beats sit up to 216 ms away
  from a constant grid", "drifting"; the user, on a constant grid: "sits exactly on the metronome" at 0:43, 2:25
  and 4:23. (b) `sample_pack`: "piano: nearly empty (-42 dB against the mix), probably bleed"; the fix: 3201
  piano notes and a track. (c) Fix report: kick and bass hit together, "needs sidechain"; `clash_report` on kick
  and bass: "they take turns, and need no carving".
- **Change:** (a) before reporting drift, test the beats against the best constant grid and report the residual
  after that fit; if it is small, say "steady" and write no warp markers. (b) the fix uses the same "nearly
  empty" test as `sample_pack` and skips or flags such a stem. (c) one of the two bass/kick statements is
  derived from the other, so they cannot disagree.
- **How we would know:** on Manana the fix report either says "steady" or names the bars where the kick leaves
  the click, and the user hears it leave there; the piano stem is flagged in both tools; one sentence about kick
  and bass, the same in both reports.
- **Size:** days.

### 6. Replies that show what happened

- **Evidence:** `02`, findings 2, 3, 5, 6; `03`, step 3: `set_song(time=...)` answered `"time": 0.0` and 3.53 (the
  old position) and the move had to be confirmed by a full `live_session`; `create_audio_clip` renamed the track
  (`3-Audio` to `3-kick`) and the next call by name failed; `locators add` ignores `name`; one `undo` took back
  several steps.
- **Change:** read the state back after Live has applied it and return that; return the track's index and
  current name from any call that can rename it; apply the locator name; return what `undo` undid.
- **How we would know:** the stage 2 script again: every `set_song`/`transport` reply equals the following
  `live_session`; zero second calls needed to confirm a change.
- **Size:** hours to days.

### 7. Smaller answers

- **Evidence:** `03`, step 5: `clash_report` on 12 stems returned 59,332 characters and the client refused it;
  `02`, finding 7: the audio reports repeat the 28-band spectrum (about 3 KB per file); `sample_pack` returned 62
  loop records in full.
- **Change:** return the top pairs (default 10) and a count, write the full result to a file and return its
  path; the same for long loop lists and spectra.
- **How we would know:** the same three calls on Manana each return under 8,000 characters and nothing the test
  needed is missing.
- **Size:** hours.

### 8. Installing and updating on Windows

- **Evidence:** `00`: pip failed with WinError 32 because `track2ableton-mcp.exe` was locked by Claude Code
  sessions, the testing one included; three tests fail on Windows (two path-separator assumptions, one not
  isolated from a running Live); the suite took 11 min 25 s against an expected four; no bridge or Live version
  in `live_session` or the doctor (`02`, finding 4), which every report header asks for.
- **Change:** register the server as `py -m ...` instead of a locked exe, or have the doctor explain the lock;
  fix the three tests; add `bridge_version` and `live_version` to `live_session` and the doctor.
- **How we would know:** update with Claude Code open succeeds; `171 passed` on this machine; the next report
  header has a bridge version in it.
- **Size:** hours.

## B. What a product for sale would need

### 9. A one-call arrangement builder, and no hidden manual steps

- **Evidence:** `02B`: the StudioPilot kit's `build_arrangement` laid out ten clips from Session loops in one
  call with a per-track result, and its tool descriptions steer the assistant to it; `03`: with this tool the
  tester had to trim a template, place a clip and set a tempo by hand, and the user "does not know how to see"
  things in Live and asked the tester to read screenshots.
- **Change:** a `build_arrangement`-style tool (sections from `recipe.json` to Arrangement clips and locators),
  built on idea 2; every stage of the fix workflow runnable by an assistant with no step that needs the user to
  operate Live beyond pressing Space.
- **How we would know:** a user who has never used Live gets from a folder of stems to a playing Arrangement with
  section locators by typing one sentence and opening nothing by hand; timed.
- **Size:** days to weeks.

### 10. Safety and proof before selling

- **Evidence:** `03`: a generated file crashed the buyer's DAW and lost an unsaved Set; `02B`/`01B`: the paid kit
  itself failed to install in two places and froze its bridge twice, and `01` found no independent reviews of it
  and a no-refund policy, so reliability is the open ground; `02`, finding 1: refused commands in read-only mode
  are not journaled.
- **Change:** a release gate: a fixed set of real songs (steady, drifting, overlapping stems) must go through
  fix, open in each supported Live version, and pass a kick-on-click measurement (export the REF kick, compare
  hits to the grid within about 10 ms, as `docs/FIX_IN_LIVE.md` already describes) before any release; journal
  refusals; a written list of supported Live versions.
- **How we would know:** the gate's table for a release: every song opens, zero crashes, measured kick offset
  per song; the Manana row passes.
- **Size:** weeks.

## Left out, and why

- Reference mastering (`match_reference`, `verify_reference`), `split_stems`, `vocal_score`: not run in stage 3
  (the user skipped them), so there is no evidence to rank.
- The user's verdict on the clash pairs: asked twice, not given.
- Anything about how the result sounds: the only listening verdicts are the four timing answers in `03`.

STOP.
