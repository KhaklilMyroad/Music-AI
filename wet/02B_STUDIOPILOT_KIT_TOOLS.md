# Wet test, stage 2b: the StudioPilot Setup Kit's tools against the real Live

**Status: finished for now. 74 of the 136 tools were called (the "47" further down was a miscount; it was 44 at
that point). Summary of findings is at the end. Read the "Correction" section before the two "killed the bridge"
sections: the bridge freezes, it does not die.**

- Date: 2026-11-13
- Live version: 12.4.16 Suite (from the process path and `Log.txt`)
- Tool commit (ours, for reference): 6a4e0f8
- Kit under test: StudioPilot Setup Kit, `pyproject.toml` version 1.0.0, Remote Script `StudioPilot` on port 9877,
  MCP server run with mcp 1.30.0 (the kit's own install pulls 2.3.0 and does not start, see `01B`).
- `T2A_Bridge`: not active during this test.

The Set: confirmed empty by reading it before any write (no file path, 120 BPM, tracks `1-MIDI`, `2-MIDI`,
`3-Audio`, `4-Audio`, returns `A-Reverb`, `B-Delay`, no clips, no devices). The user said "ready" twice but did not
say the words "the Set is empty"; the reads are the evidence.

136 tools are exposed. 47 were called before the stop.

## Results so far

| Tool | Result | Call | What came back / what was read back |
|---|---|---|---|
| `health_check` | PASS | `()` | connected, tempo 120, 4 tracks |
| `get_session_info` | PASS | `()` | tempo, signature, counts, master |
| `get_session_path` | PASS | `()` | empty path and name (unsaved Set) |
| `is_session_modified` | **FAIL (no data)** | `()` | "Session modification status not available" |
| `get_track_info` | PASS | `(0..4)` | names, mixer state, 8 clip slots, devices |
| `set_tempo` | PASS | `(124)` | read back 124.0 |
| `set_metronome` / `get_metronome_state` | PASS | `(true)`, `(false)` | read back on, then off |
| `create_scene` | PASS | `(-1)` | scene count 8 to 9 |
| `set_scene_name` | PASS (not read back) | `(8, "WET drop")` | "Renamed scene 8" |
| `get_all_scenes` | PASS | `()` | 9 scenes |
| `set_arrangement_loop` / `get_arrangement_length` | PASS | `(8, 24, true)` | loop_start 8, loop_length 16, enabled |
| `get_cpu_load` | **FAIL (no data)** | `()` | "CPU load information not available" |
| `get_current_view` | PASS | `()` | selected track and scene |
| `create_locator` | **FAIL, reports success** | `(16, "Drop")` | Said "Created locator 'Drop' at 16.0". Read back: one locator, name "1", time 0.0 |
| `create_locator` | **FAIL, reports success** | `(32, "Break")` | Said "Created locator 'Break' at 32.0". Read back: name "2", time 16.0 (where the playhead was) |
| `get_locators` | PASS | `()` | shows the two wrong locators |
| `delete_locator` | **FAIL** | `(1)` | "Error deleting locator: Communication error with Ableton: property of 'CuePoint' object has no setter". Locator still there |
| `jump_to_time` | PASS with a wrong message | `(16)` | Said "Jumped to position 0.0"; position read back 16.0 |
| `start_playback` / `stop_playback` / `get_playback_position` | PASS | `()` | is_playing true, time advancing; then stopped |
| `create_midi_track` | PASS | `(-1)` | "5-MIDI" |
| `create_audio_track` | PASS | `(-1)` | "6-Audio at index 5" |
| `set_track_name`, `_volume`, `_pan`, `_mute`, `_arm` | PASS | track 4: "WET Bass", 0.6, -0.25, true, true | all read back through `get_track_info` |
| `set_track_solo` | PASS (not read back) | `(5, true)` | "Track 5 is now soloed" |
| `set_track_color` / `get_track_color` | PASS | `(4, 12)` | color_index 12 |
| `set_send_level` / `get_send_level` | PASS | `(4, 0, 0.4)` | 0.4, send name "A-Reverb" |
| `set_return_volume`, `set_return_pan` | PASS | `(0, 0.7)`, `(1, 0.3)` | read back through `get_return_tracks` |
| `get_return_track_info`, `get_return_tracks`, `get_master_info` | PASS | | Reverb on A, counts, master empty |
| `select_track` | PASS | `(4)` | "Selected track 'WET Bass'" |
| `create_clip` | PASS (not read back) | `(4, 0, 4)` | "Created new clip" |
| `add_notes_to_clip` | PASS (not read back) | 4 off-grid notes | "Added 4 notes". Live logged: `set_notes is deprecated since Live 11.0` |
| `set_clip_name` | PASS (not read back) | `(4, 0, "WET bass loop")` | "Renamed clip" |
| `quantize_clip_notes` | **FAIL, and it killed the bridge** | `(4, 0, 0.25)` | see below |

Everything else (89 tools): NOT RUN.

## The stop: `quantize_clip_notes` takes the whole connection down

- Call: `quantize_clip_notes(track_index=4, clip_index=0, grid=0.25)` at 20:39:10.
- Returned: "Error quantizing clip notes: Communication error with Ableton: No data received".
- Expected: the four notes moved to the 16th grid.
- After it, `health_check` twice: `"connected": false, "error": "Could not connect to Ableton. Make sure the Remote
  Script is running."` A direct TCP connect to `127.0.0.1:9877`: "actively refused". Before the call that port was
  listening. Live itself is still running and responding (pid 55424).
- Live's `Log.txt` for that command shows only two deprecation warnings (`get_selected_notes`, `remove_notes`,
  "deprecated since Live 11.0") and then nothing at all from StudioPilot: no error, no traceback, no shutdown line.
- So on Live 12.4.16 one ordinary MIDI command silently ends the kit's server inside Live, and every later tool
  fails with a message that blames the user's setup. Whether the notes survived (the command removes notes before
  re-adding them): not checked, the bridge is down. The user has to look at the clip.
- Recovery needs the user's hands: re-select the Control Surface or restart Live.

## Second run, after the user re-selected the Control Surface (20:47)

| Tool | Result | Call | What came back |
|---|---|---|---|
| `health_check` | PASS | `()` | connected again, tempo 124, 6 tracks: re-selecting the surface revives the bridge |
| `get_clip_notes` | PASS | `(4, 0)` | 4 notes at 0.0, 1.0, 2.25, 3.5. **So the quantize itself did its work** (0.03, 1.12, 2.22, 3.4 moved to the grid, nothing lost) and the bridge died after it |
| `set_clip_loop` | PASS (not read back) | `(4, 0, 0, 2, true)` | "Set clip loop: 0.0 - 2.0" |
| `duplicate_clip` | PASS (not read back) | `(4, 0)` | "Duplicated clip to slot 1" |
| `generate_drum_pattern` | **FAIL, and it killed the bridge again** | `(0, 0, "house", 4)` | "Error generating drum pattern: Communication error with Ableton: No data received" |
| `generate_bassline` | NOT RUN (bridge down) | `(1, 0, 36, "minor", 4)` | "Could not connect to Ableton. Make sure the Remote Script is running." |
| `get_scale_notes` | NOT RUN (bridge down) | `(60, "dorian")` | same error. A scale lookup needs no Live at all, yet the tool refuses without the connection |
| `search_browser` | NOT RUN (bridge down) | `("Operator", "instruments")` | same error |

The last four were sent in one batch with the two before them; earlier batches of up to eleven calls ran fine.

### What the two bridge deaths share

- Both commands call the same Live function, `clip.remove_notes(0, 0, clip.length, 128)`, the pre-Live-11 note
  API (`__init__.py` lines 3747 and 3884). Live logs "deprecated since Live 11.0" for it, and that warning is the
  last line StudioPilot produces before the silence. `add_notes_to_clip`, which uses the old `set_notes` but not
  `remove_notes`, did not kill it.
- The same call sits in `remove_notes`, `remove_all_notes`, `transpose_notes`, `humanize_clip_timing`,
  `humanize_clip_velocity`, `generate_bassline` and two more internal commands. Those were not run; by this
  reading they would do the same. **Likely cause, two cases out of two, not proven.**
- After the death the port can still show as listening while every call is refused or unanswered. The only
  recovery found: the user re-selects the Control Surface by hand.
- Whether `generate_drum_pattern` wrote anything into `1-MIDI` slot 0 before dying: not checked.
- The Remote Script defines about 300 command handlers; the MCP server exposes 136 of them as tools.

### Correction after reading the full log (20:52): it freezes, it does not die

Earlier sections say the bridge was "killed" and that re-selecting the Control Surface revived it. The log does not
support either statement:

- First freeze: last line 20:39:10 (`quantize_clip_notes`), then **no line at all for 3 min 55 s**, then at
  20:43:05 the script woke by itself and worked through a pile of queued connections, each ending in
  `ConnectionAbortedError: [WinError 10053]` at `__init__.py` line 193 (`client.sendall`), because the clients had
  long given up. That was before the user reported re-selecting the surface (about 20:47).
- No "(StudioPilot) Initializing..." line appears after 20:33:09. So no re-selection ever reloaded the script, or
  the re-selections were not what the user did. What ended the first freeze is unknown; it coincides with the user
  switching to Live's window (their screenshot is from 20:44).
- Second freeze: last line 20:47:57 (`generate_drum_pattern`). At 20:52:53, after the user said "connected" a
  third time, still frozen: no new log line, `health_check` refused, port 9877 listed as listening, Live
  responding, title "Untitled* - Ableton Live 12 Suite", plus one more visible Live window with an empty title
  (what it is: not checked).
- So the honest statement is: after either of these two commands the kit's script stops processing anything for
  minutes, logs nothing, and the tools tell the user "Make sure the Remote Script is running". Cause: unknown.
  The shared `remove_notes` call is still the only common factor found.

## Third run (21:04 onwards)

The second freeze lasted 16 min 12 s (20:47:57 to 21:04:09). It ended when the user switched to Live's window to
take a screenshot (file stamped 21:04:25); they did not re-select anything. The first freeze also ended as the
user went to Live. **Two out of two: after a `remove_notes`-family command the script stays frozen until the user
touches Live.** The screenshot shows no dialog in Live.

Both frozen commands had done their work: `1-MIDI` slot 0 holds a 10-note house pattern (kick on every beat, clap
on 2 and 4, open hat on the off-beats); the screenshot shows the four quantized notes and the 2-beat loop.
The screenshot also shows a groove "Swing 16ths 66" in the Groove Pool and on the clip. No groove tool was called
by this session; where it came from: not checked.

| Tool | Result | Call | What came back / read back |
|---|---|---|---|
| `get_clip_loop` | PASS | `(4, 0)` | 0.0 to 2.0, looping: confirms `set_clip_loop` |
| `duplicate_clip` | PASS | (earlier) | slot 1 holds "WET bass loop": confirmed by `get_track_info` and the screenshot |
| `get_scale_notes` | PASS, one odd field | `(60, "dorian")` | MIDI notes 60 62 63 65 67 69 70 correct; the field `notes` repeats the intervals (0 2 3 5 7 9 10) |
| `search_browser` | PASS | `("Operator", "instruments")` | one result, URI `query:Synths#Operator` |
| `get_browser_tree` | **FAIL (empty)** | `("audio_effects")` | "showing 0 folders" |
| `get_browser_items_at_path` | PASS | `("audio_effects")` | 47 effects with URIs |
| `load_instrument_or_effect` | PASS with a broken message | Operator, then EQ Eight, on track 4 | "Devices on track: " (empty list in the message). `get_track_info` shows Operator and EQ Eight |
| `load_item_to_track` | **FAIL** | `(4, EQ Eight URI)` | "Unknown command: load_instrument_or_effect. Available commands include: ..." The tool sends a command its own bridge does not know |
| `get_device_parameters` | PASS | `(4, 1)` | 84 parameters. Frequency and Q come as raw 0.0 to 1.0 only (e.g. "1 Frequency A": 0.1427), with no Hz or display text. Device `type` is "unknown" |
| `set_device_parameter` | PASS (not read back) | `(4, 1, 7, -3)` | "Set 1 Gain A to -3.0 (range: -15.0 - 15.0)" |
| `toggle_device` | PASS (not read back) | `(4, 1)` | "Toggled device 'EQ Eight' off" |
| `build_arrangement` | PASS | bass at 0,2,..14 and drums at 8,12 | 10 clips placed; `get_arrangement_clips` shows all at the right beats |
| `get_arrangement_clips` | PASS | `(4)`, `(0)` | start, end, length per clip |
| `delete_arrangement_range` | PASS (not read back) | `(8, 16, [4])` | "total_removed: 4", only on the track asked |
| `load_audio_file` | PASS | `(2, 0, C:\Windows\Media\tada.wav)` | clip "tada", length 4.0 |
| `get_clip_warp_info` | PASS | `(2, 0)` | warping true, mode "beats". No warp markers, no tempo |
| `get_available_outputs`, `get/set_track_output_routing` | PASS | track 2 to "Sends Only" | read back "Sends Only" |
| `duplicate_track`, `delete_track` | PASS | `(5)`, `(6)` | "7-Audio" created, then deleted |
| `undo` | PASS | `()` | track count 6 to 7 (the delete undone) |
| `redo` | PASS | `()` | track count back to 6 |
| `create_group_track` | **FAIL** | `([2, 3], "WET group")` | "Error creating group track: Communication error with Ableton: property of 'Track' object has no setter". Nothing changed |
| `delete_clip`, `delete_device` | PASS | `(4, 1)`, `(4, 1)` | named what was deleted |
| `set_master_volume` | PASS | `(0.8)` | read back 0.8 |

NOT RUN, on purpose (they use the same `remove_notes` call and would need the user's hands again):
`remove_notes`, `remove_all_notes`, `transpose_notes`, `humanize_clip_timing`, `humanize_clip_velocity`,
`generate_bassline`. NOT RUN, no time: recording, freeze/flatten, automation, warp markers, grooves, racks,
monitoring, input routing, colours of clips and scenes, `fire_clip`/`fire_scene`, `arrange_track`,
`clear_arrangement`, `load_drum_kit`, `capture_midi`, views. About 55 tools.

## Summary of findings

Failures on this machine (Windows 11, Live 12.4.16 Suite, kit bought 2026-11-13):

| # | Severity | Finding |
|---|---|---|
| 1 | Blocks install | MCP server cannot start: unpinned `mcp` dependency resolves to 2.x (`01B`) |
| 2 | Blocks install | Control Surface does not appear: script copied to a folder Live does not load from, OneDrive User Library missed (`01B`) |
| 3 | Blocks work | `quantize_clip_notes` and `generate_drum_pattern` leave the bridge frozen until the user clicks into Live; six more tools share the call |
| 4 | Wrong result reported as success | `create_locator`: wrong position, wrong name, twice |
| 5 | Error | `delete_locator`, `create_group_track` ("no setter"), `load_item_to_track` ("Unknown command") |
| 6 | Empty or misleading output | `is_session_modified`, `get_cpu_load`, `get_browser_tree`, `jump_to_time` message, `load_instrument_or_effect` message |
| 7 | Misleading error text | every failure after a freeze says "Make sure the Remote Script is running" |

What works well and is worth learning from:

- `build_arrangement`: a whole song layout from Session loops in one call, with a per-track result. Ten clips
  placed correctly at the first attempt. track2ableton should be compared on exactly this.
- `delete_arrangement_range` scoped to the tracks asked, and deletes that name what they removed.
- `load_audio_file` from any disk path into a slot.
- Tool descriptions that steer the assistant ("do NOT call this repeatedly, use build_arrangement").
- Speed: every working call answered in under a second.

What the kit does not have, against the site's description of the product: no dB or Hz values (raw 0 to 1), no
audio analysis tools in the MCP server, no key detection, no clash scoring, no LUFS or reference matching, no
change journal, no read-only mode, no warp-marker or tempo-map handling for drifting audio.

State of the test Set at the end: unsaved "Untitled", tempo 124, tracks `1-MIDI` (drum clip), `2-MIDI`, `3-Audio`
(tada clip, output "Sends Only"), `4-Audio`, `WET Bass` (muted, Operator, one clip), `6-Audio` (soloed), two
locators, arrangement clips on tracks 0 and 4, master at 0.8. It can be closed without saving.

## What the user's screen shows (screenshot taken 20:44, Arrangement view)

- Two locators, named "1" at bar 1 and "2" at bar 5 (beat 16). No "Drop", no "Break", nothing at bar 9. This is
  the `create_locator` failure seen with the user's own eyes, not only through the kit's read tool.
- The loop brace runs from bar 3 to bar 7 (beats 8 to 24): `set_arrangement_loop` is real.
- Track "WET Bass" exists, recoloured, its activator off (muted). Tracks really were created and changed.
- The clip and its notes live in Session view and are not in this picture: notes after the failed quantize are
  still **not checked**. The user said they do not know how to check.

## Other observations

- Every tool call is preceded by a `health_check` command to Live (visible in `Log.txt`): two round trips per call.
- No call was slow: all under about one second.
- Mixer values are raw 0.0 to 1.0, not dB ("0.85 is Ableton's default"). No tool takes or returns a dB value.
- No tool list entry for: audio analysis, key detection, clash scoring, LUFS, reference matching, a journal of
  changes, or a read-only mode. The six audio scripts are command-line files outside the MCP server.
- Nothing appeared in a Live dialog. Nothing needed the user's hands until the bridge died.

## Compared with stage 2 of our own tool

Not possible yet: stage 0 and stage 2 for track2ableton have not run (pip was blocked in stage 0). The same list
should be run on `T2A_Bridge` in the same Live, especially locators, quantize and the read-back of every write.

STOP.
