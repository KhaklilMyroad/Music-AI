# Wet test, stage 0: update the tool

- Date: 2026-11-13 (first attempt about 16:24, second attempt 21:08)
- Live version: 12.4.16 Suite (process path and `Log.txt`)
- Tool commit: 6a4e0f8 (`origin/claude/vigilant-planck-d78nmz`); files checked out over local HEAD f2ffa16
- Bridge version: not read yet. The doctor only says the Live that is running answers "with an older Remote
  Script"; the new one loads after the next Live restart.

## First attempt (16:24): blocked at pip

`py -m pip install -e ".[live,vocal,test]"` failed:

```
ERROR: Could not install packages due to an OSError: [WinError 32] The process cannot access the file because it
is being used by another process:
'c:\\users\\ronen\\appdata\\local\\programs\\python\\python313\\scripts\\track2ableton-mcp.exe'
```

Two `track2ableton-mcp.exe` processes held the file: one belonged to another Claude Code session, **one to the
session running the test itself**. So "close the other sessions" (WET_TEST.md) is not enough. pip's rollback left
`site-packages\~rack2ableton-0.1.0.dist-info` behind (still there at 21:08).

Suggestion for the repository: do not expose the MCP server as a console-script exe that the running client
locks (register `py -m ...` instead), or tell the user to close every Claude Code window and run pip in a plain
terminal.

## State found at 21:08

`pip show track2ableton` finds the package: version 0.1.0, editable, project location
`C:\Users\ronen\track2ableton`, dist-info stamped 2026-11-13 16:25:12. So a pip run one minute after the failed
one succeeded. Who ran it: not known to this session (the 16:24 report said the workaround was "not used this
time"). The install is editable, so the code in use is the checked-out 6a4e0f8 tree.

## Doctor, before `--install-bridge` (21:08, exit code 1)

```
OK        Python: 3.13.2
OK        track2ableton: 0.1.0
OK        MCP server package: installed
OK        MCP server command: C:\Users\ronen\AppData\Local\Programs\Python\Python313\Scripts\track2ableton-mcp.exe (its folder is not on PATH: register it by its full path)
            -> claude mcp add ableton -- "C:\Users\ronen\AppData\Local\Programs\Python\Python313\Scripts\track2ableton-mcp.exe"
PROBLEM   Remote Script in C:\Users\ronen\OneDrive\Documents\Ableton\User Library: installed, but not this version
            -> py -m track2ableton.doctor --install-bridge --user-library "C:\Users\ronen\OneDrive\Documents\Ableton\User Library", then restart Live
PROBLEM   Ableton Live: answering on 127.0.0.1:9877, but with an older Remote Script
            -> py -m track2ableton.doctor --install-bridge, then restart Live
OK        Read-only mode: off
OK        Demucs (neural stem splitting): runs with C:\Users\ronen\demucs-env\Scripts\python.exe
OK        English pronunciation (vocal scores): installed
OK        Hyphenation (vocal scores): installed
optional  Neural note transcription: not installed
            -> py -m pip install basic-pitch (it pins an old TensorFlow and may not install on a recent Python)

2 thing(s) to fix, see the arrows.
```

## `py -m track2ableton.doctor --install-bridge` (exit code 0)

```
Installed to C:\Users\ronen\OneDrive\Documents\Ableton\User Library\Remote Scripts\T2A_Bridge
Restart Live, then Settings > Link, Tempo & MIDI > Control Surface: T2A_Bridge (Input/Output: None).
```

It found the User Library inside OneDrive without being told (the StudioPilot kit's installer did not, see `01B`).
The previous `T2A_Bridge` folder is in the backup `C:\Users\ronen\studiopilot-backup-2026-11-13`.

## Doctor, after `--install-bridge` (exit code 1)

Same as above except:

```
OK        Remote Script in C:\Users\ronen\OneDrive\Documents\Ableton\User Library: installed, same as this version
PROBLEM   Ableton Live: answering on 127.0.0.1:9877, but with an older Remote Script
            -> py -m track2ableton.doctor --install-bridge, then restart Live

1 thing(s) to fix, see the arrows.
```

Expected: Live (restarted by the user at 21:08:01, `T2A_Bridge` selected at 21:08:18) still runs the script it
loaded before the install. One more Live restart is needed, as WET_TEST.md says.

Observations:

- The doctor's hint for the last PROBLEM says "--install-bridge, then restart Live" even when the script on disk
  is already current; "restart Live" alone would be the accurate fix at that point.
- "MCP server command ... its folder is not on PATH" is printed under OK with a `claude mcp add` arrow, although
  the `ableton` server is already registered at user scope. Harmless, a little confusing.
- With the StudioPilot kit installed too, both scripts want port 9877. The doctor recognised the situation
  correctly while `T2A_Bridge` was the selected surface. It was not run while `StudioPilot` was selected: not
  checked.

## `py -m pytest tests -q`

Started 21:09, with Live running and `T2A_Bridge` (older script) answering on port 9877.

**RESULT: `3 failed, 168 passed, 1 warning in 685.85s (0:11:25)`.** Expected: `171 passed` in about four minutes.

The three failures, re-run alone (`--tb=short`, 3.7 s, same result):

1. `tests/test_studio.py::test_the_user_library_is_looked_for_where_windows_really_keeps_it` (line 160)
   ```
   assert doctor.user_library_candidates("Darwin", {}, "/Users/me") == ["/Users/me/Music/Ableton/User Library"]
   At index 0 diff: '/Users/me\\Music\\Ableton\\User Library' != '/Users/me/Music/Ableton/User Library'
   ```
   On Windows the function joins a macOS path with backslashes. The test expects forward slashes. Either the
   function should build paths for the platform it is asked about, or the test only holds on Linux/macOS.

2. `tests/test_studio.py::test_install_and_recognise_the_remote_script` (line 181)
   ```
   assert "PROBLEM   Ableton Live" in text and "Control Surface: T2A_Bridge" in text and "installed, same as this version" in text
   ```
   The doctor text in the failure ends "1 thing(s) to fix" (middle truncated by pytest). The test assumes no Live
   is listening; here a real Live with a real bridge answered on 9877, so the wording differed. The test is not
   isolated from a running Live. Which of the three phrases was missing: not checked.

3. `tests/test_studio.py::test_the_journal_says_when_it_is_not_recording_and_stays_small` (line 360)
   ```
   assert journal.folder() == os.path.join(os.path.expanduser("~"), "journal here")
   - ...\home2\journal here
   + ...\home2/journal here
   ```
   With `T2A_JOURNAL_DIR="~/journal here"`, `journal.folder()` returns a Windows path with a forward slash in it
   (mixed separators). Windows accepts it; the test does not.

Not explained: the run took 11 min 25 s instead of about four. Whether the running Live, the editable install or
this machine is the reason: not checked. Not repaired here.

Warning: `PytestRemovedIn10Warning: _pytest.python.CallSpec2 has been renamed to CallSpec` from the `anyio` plugin.

## Final doctor, after the user restarted Live (21:36, exit code 0)

Live 12.4.16 started 21:36:30; `Log.txt` 21:36:34: "(T2ABridge) Initializing...".

```
OK        Python: 3.13.2
OK        track2ableton: 0.1.0
OK        MCP server package: installed
OK        MCP server command: C:\Users\ronen\AppData\Local\Programs\Python\Python313\Scripts\track2ableton-mcp.exe (its folder is not on PATH: register it by its full path)
            -> claude mcp add ableton -- "C:\Users\ronen\AppData\Local\Programs\Python\Python313\Scripts\track2ableton-mcp.exe"
OK        Remote Script in C:\Users\ronen\OneDrive\Documents\Ableton\User Library: installed, same as this version
OK        Ableton Live: answering on 127.0.0.1:9877, 39 commands
OK        Read-only mode: off
OK        Demucs (neural stem splitting): runs with C:\Users\ronen\demucs-env\Scripts\python.exe
OK        English pronunciation (vocal scores): installed
OK        Hyphenation (vocal scores): installed
optional  Neural note transcription: not installed
            -> py -m pip install basic-pitch (it pins an old TensorFlow and may not install on a recent Python)

Everything needed is in place.
```

One call to `live_session` to read the versions for the report header: it answered (tempo 120, four default
tracks, `read_only: false`, mixer values in dB), but **the result has no Live version and no bridge version
field**. WET_TEST.md asks every report to start with the bridge version and stage 2 step 1 to record both from
`live_session`. The doctor prints "39 commands" and no version either. Bridge version: still not available from
any tool output. To fix in the repository, or to correct in WET_TEST.md.

The `ableton` MCP server in this Claude Code session was started at 20:36 from the editable install, i.e. from the
6a4e0f8 files. `--install-bridge` did not change the MCP server, so no Claude Code restart was needed.

## Stage 0 outcome

- Tool updated to 6a4e0f8, bridge installed and loaded, doctor clean.
- pytest: 168 passed, 3 failed (two Windows path-separator assumptions, one test not isolated from a running
  Live), 11 min 25 s.
- pip cannot update the package while any Claude Code session is open, including the one doing the update.

STOP.
