# Wet test, stage 2: every Live tool against the real Live

- Date: 2026-11-13, 21:37 to 21:41
- Live version: 12.4.16 Suite (process path and `Log.txt`; `live_session` does not report it)
- Tool commit: 6a4e0f8 (`origin/claude/vigilant-planck-d78nmz`)
- Bridge version: not available. Neither `live_session` nor the doctor prints one (doctor: "39 commands").

Preconditions: the user restarted Live and wrote "stage 2". They were not asked again in words; instead
`live_session` was read first and showed an unsaved Set with the four default tracks, two returns, no devices, no
clips, and `Log.txt` shows `T2A_Bridge` as the Control Surface. The StudioPilot kit is still installed but not
selected.

## 1. `live_session`

PASS. Tempo 120, 4/4, tracks, returns, master, 8 scenes, `read_only: false`. Mixer values come in dB ("0.0 dB",
"-inf dB"). **No Live version field, no bridge version field** (WET_TEST.md asks to record both from here).
The answer is about 5 KB for an empty Set.

## 2. Read-only, for real

| Step | Call | Result |
|---|---|---|
| on | `py -m track2ableton.doctor --read-only on` | "Read-only mode is ON (C:\Users\ronen\.track2ableton\read_only)." |
| write refused | `set_song(tempo=126)` | **Refused**: "Read-only mode is on: 'set_song' was not sent to Live. Looking and measuring still work. Switch it off with: python -m track2ableton.doctor --read-only off" |
| nothing changed | `live_session` | tempo still 120.0, `read_only: true` |
| journal shows the refusal | `journal(last=5)` | **FAIL.** `entries: []` and "Nothing has been recorded: the journal folder does not exist..." The refusal is not in the journal |
| off | `py -m track2ableton.doctor --read-only off` | "Read-only mode is off" |
| write goes through | `set_song(tempo=126)` | `{"tempo": 126.0}` |
| journal | `journal(last=5)` | one entry, `set_song`, `ok: true`. The refused attempt is still absent |

So the refusal works and is clear, but WET_TEST.md's "journal must show the refusal" does not hold: refused
commands are not recorded at all. Also the refusal text says `python -m ...` where the doctor's own hints say
`py -m ...`.

## 3. Every tool

| Tool | Result | Call | What came back / read back |
|---|---|---|---|
| `live_session` | PASS | `()` | see 1 |
| `set_song` | PASS, **reply is stale** | `(time=16, loop=true, loop_start=8, loop_length=16, metronome=true)` | Reply said `"time": 0.0, "loop": false`. The playhead really moved: the locator added next sits at 16.0. Loop on/off: not read back |
| `transport` | PASS, **reply is stale** | `play`, then `stop` | `play` answered `"is_playing": false`; `stop` answered `"is_playing": true` (twice). The reply shows the state before the action |
| `locators` | PASS for position, **name ignored** | `(add, name="Drop")` | Locator at 16.0, correct, but named "1". The journal recorded `name: "Drop"`. The tool's text says add works "at playhead"; it accepts a name and drops it without saying so |
| `locators` | PASS | `(jump, name="1")` | list returned |
| `scenes` | PASS | `create(8)`, `set(8, "WET drop", tempo 128)`, `delete(7)` | create: 9 scenes. set: name and tempo read back in the reply |
| `undo` | PASS, **takes more than one step** | `()` after the scene `set` | "true". Afterwards `delete(7)` left 7 scenes, so the one undo had removed the whole new scene (create + rename), not only the rename. Not looked at more closely |
| `create_track` | PASS | `(midi, "WET Bass")`, `(audio, "WET Audio")` | index 4, index 5, names set in the same call |
| `set_track` | PASS | `("WET Bass", volume_db=-6, pan=-0.25, mute, arm, color 12)` | reply and `get_track`: "-6.0 dB", "12L", mute, arm, colour 12 |
| `set_send` | PASS | `("WET Bass", "A", -12)` | "-12.0 dB"; `get_track` shows sends ["-12.0 dB", "-inf dB"] |
| `routing` | PASS | `("WET Audio", output_type="Sends Only", monitoring="off")` | output "Sends Only", monitoring 2, with the lists of valid choices |
| `duplicate_track` | PASS | `("WET Audio")` | index 6 |
| `delete_track` | PASS (not read back) | `("6")` | "true" |
| `get_track` | PASS | `("WET Bass")` | mixer in dB, devices, 7 clip slots, arrangement clips, routing |
| `create_clip` | PASS | `("WET Bass", 0, 4, "WET bass loop")` | clip described in the reply |
| `write_notes` | PASS | 4 off-grid notes | `added: 4` |
| `quantize` | PASS | `("WET Bass", slot 0, "1/16")` | "true". **No freeze** (the same test froze the StudioPilot kit for minutes) |
| `get_notes` | PASS | | 0.0, 1.0, 2.25, 3.5, all four notes, with `note_id` |
| `set_clip` | PASS | `(loop_end=2, color_index=5)` | reply: length 2.0, loop_end 2.0, colour 5 |
| `clip_action` | PASS (not read back) | `duplicate_to` slot 1, `to_arrangement` time 8, `duplicate_loop`, `fire`, `stop` | "true" each. Replies carry no detail to check against |
| `create_arrangement_clip` | PASS | `("WET Bass", 16, 4)` | `arrangement_clips: 2` (the one from `to_arrangement` plus this one) |
| `create_audio_clip` | PASS | `("WET Audio", tada.wav, slot=0)` and `(position=8)` | Session: full clip description incl. file path, sample rate, warp. Arrangement: `arrangement_clips: 1` |
| `delete_clip` | PASS (not read back) | `("WET Bass", 1)` | "true" |
| `browse` | PASS | `()` | 12 categories |
| `search_browser` | PASS | `("Utility", "audio_effects", limit 3)` | 1 hit with path and URI, `visited: 1060` |
| `load_item` | PASS | `("WET Audio", path="audio_effects/Utility")` | loaded "Utility", device list |
| `add_device` | PASS | Operator, EQ Eight, Compressor on "WET Bass" | device list grows by one each time |
| `get_device` | PASS | `("WET Audio", "Utility")` | 12 parameters with raw value **and display text** ("120 Hz", "100 %", "0.00 dB") |
| `set_parameter` | PASS | `("1 Frequency A", display_value=300)` | `"display": "300 Hz"` |
| `set_parameters` | PASS | Gain -3, Filter Type "Bell", Frequency 1200 | "-3.00 dB" (raw -3.005), "Bell", "1.20 kHz" |
| `sidechain` | PASS | list, then `source="3-Audio"` | options listed, current "No Input"; then `source: "3-Audio"`, `enabled_parameter: "S/C On"`. Not read back afterwards |
| `device_action` | PASS | `off`, then `delete` on EQ Eight | after delete: ["Operator", "Compressor"]. `off` only returns the device list, so the off state is not confirmed by the reply |
| `get_audio_files` | PASS | `()` | both tada clips (slot 0, arrangement at 8.0) with paths |
| `meters` | PASS | `()` | 0.0 everywhere (nothing playing), `null` for MIDI tracks without an instrument |
| `analyze_audio` | PASS | `(tada.wav)` | -32.0 LUFS, peak -16.26 dBFS, true peak -16.21 dBTP, crest 21.2 dB, bands, stereo, no issues |
| `waveform` | PASS | `(tada.wav, width 600)` | image, two channels |
| `spectrogram` | PASS | `(tada.wav, 600x200)` | image plus axis description |
| `mix_report` | PASS | `()` | found the Set's audio file by itself, listed it once, no masking (one track) |
| `master_report` | PASS | `(tada.wav, target="club")` | target -9.0, action: raise about 23.0 dB into the limiter and re-measure |
| `journal` | PASS | `(last=60)` | 36 entries, every change above with arguments and `ok: true` |

Not run in this stage (not on WET_TEST.md's stage 2 list): `fit_layers`, `clash_report`, `match_reference`,
`verify_reference`, `sample_pack`, `split_stems`, `vocal_score`, `rebuild_in_live`. They belong to stage 3.

### Journal check

All 36 changes are there, in order, with arguments. By design playback (`transport`) is not listed. Also not
listed: `locators jump`, and the refused `set_song`. Clip `fire` and `stop` are listed although they are playback.

## Slow calls, dialogs, hands

- Nothing took five seconds. Journal timestamps are one to four seconds apart including the assistant's own time.
- No dialog in Live was reported. Nothing needed the user's hands during the run.

## Findings to fix in the repository

| # | Finding |
|---|---|
| 1 | Refused commands in read-only mode are not journaled, and the journal folder is not created until the first successful write |
| 2 | `set_song` and `transport` replies show the state from before the change (time, loop, is_playing). An assistant reading the reply will believe the change failed |
| 3 | `locators add` accepts `name` and ignores it; the journal then records a name that was never applied |
| 4 | `live_session` and the doctor expose no bridge version and no Live version |
| 5 | One `undo` after create + rename of a scene removed the scene. Either expected Live behaviour to document, or the bridge is not closing undo steps |
| 6 | `clip_action`, `delete_clip`, `delete_track`, `quantize`, `undo` answer only "true": nothing to verify against without a second call |
| 7 | `analyze_audio`, `mix_report`, `master_report` repeat the full 28-band spectrum each time (about 3 KB per file); `analyze_audio` proposes EQ cuts of 7 to 9 dB for a file with "issues: []" |
| 8 | Refusal text says `python -m`, doctor hints say `py -m` |

## Against the StudioPilot kit, same Live, same day (`02B`)

| | track2ableton | StudioPilot Setup Kit |
|---|---|---|
| Install on this machine | pip blocked while Claude Code is open; bridge install found the OneDrive library | two blocking faults (mcp 2.x, wrong script folder) |
| Tools exposed | 47 | 136 |
| Failed or wrong, of those run | 0 errors; 3 misleading replies (stale state, ignored name); 1 missing journal entry | 2 freezes, 3 errors, 1 false success, 6 empty or misleading |
| Quantize four notes | works | works, then the bridge freezes until the user clicks into Live |
| Locator at beat 16 | right place, name ignored | wrong place, wrong name, reported as success |
| Mixer and device values | dB, Hz, display text, set by display value | raw 0 to 1 only |
| Names instead of indexes | yes ("WET Bass", "A") | indexes only |
| Journal, read-only | yes | no |
| Audio measurement inside the tool set | LUFS, true peak, bands, stereo, images | none in the MCP server |
| Whole arrangement in one call | **not tested here, no equivalent in the stage 2 list** | `build_arrangement`, worked first time |
| Group tracks | no tool | tool exists, fails |

## 4. For the user

The user's answer: "I took a screenshot, check it yourself" (file stamped 21:59:14, Session view). They gave no
verdict in words and did not say whether they pressed Ctrl+Z.

### What the screenshot shows

| Expected | On screen |
|---|---|
| Tracks "WET Bass" and "WET Audio" after the four default tracks | yes |
| "WET Bass" muted, armed, volume down, send A up | yes: activator off, arm red, both knobs moved |
| "WET Bass" has an instrument | yes: its output shows "Audio To Main" |
| "WET Audio": output "Sends Only", monitor Off, a Utility device | yes, all three |
| 7 scenes | yes (rows up to 7) |
| Loop on, from bar 3, four bars long | yes: loop switch lit, "3. 1. 1" and "4. 0. 0". So `set_song(loop=true)` did apply although its reply said `"loop": false` |
| Metronome on | yes |
| **Tempo 126** | **no: 120.00** |

The top clip row, the Arrangement and the locators are outside the picture. Read with the tools at 22:00 instead:
both tracks, both Session clips, all three Arrangement clips, devices, sends and routing are as created.
**`locators list` returns `[]`: the locator at beat 16 is gone.** "WET bass loop" in slot 0 reports
`is_playing: true` (launched at 21:39:49, `clip_action stop` at 21:39:52, `transport stop` after): whether the
clip stop did not take or the user launched it again: not checked.

### Undo, measured instead of asked

- At 22:00 one `undo` was called. The last change had been the deletion of EQ Eight. After the undo the device
  list is ["Operator", "EQ Eight", "Compressor"], and Utility (loaded one step earlier) is still on "WET Audio".
  **This undo took back exactly one step.**
- The `undo` at 21:38:31 is different. Before it: tempo 126, locator added, scene created, scene renamed. After
  the run: tempo 120, no locator, the scene gone, while everything done later is still there. A Ctrl+Z by the user
  would have removed the latest changes first, and they are intact. **So that one `undo` most likely took back
  four changes at once.** Inferred from the end state; tempo and locators were not read right after it.
- Loop and metronome were set in the same period and survived: in Live those are not undoable.
- Whether Ctrl+Z from the keyboard goes one step at a time: not checked, the user did not report it.

Finding 5 in the table above should read: `undo` took back one step in one case and four in another. Changes sent
close together at the start of a session seem to share one undo step. For a tool whose description says "Undo
the last change", that can silently remove work the assistant did not mean to remove.

Also seen: the Groove Pool holds "Swing 16ths 66" in this fresh Set too, and the loop brace sat at bar 3 before
any tool touched it. Both come with the user's default Set, not from either tool. This closes the open question
in `02B` about the groove.

State left in Live: unsaved "Untitled", as described above, with EQ Eight back on "WET Bass". It can be closed
without saving.

STOP.
