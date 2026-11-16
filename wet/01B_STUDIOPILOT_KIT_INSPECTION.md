# Wet test, stage 1b: the StudioPilot Setup Kit, read before installing

- Date: 2026-11-13
- Live version: Live 12 Suite; preference folders exist for 12.2.2 and 12.4.16 (Live closed, exact running build not checked)
- Tool commit: 6a4e0f8 (`origin/claude/vigilant-planck-d78nmz`)
- Bridge version: not checked
- Kit: bought and downloaded by the user to `C:\Users\ronen\studiopilot-kit`. Price paid at checkout: not reported yet.

**Nothing from the kit was run or installed.** Files were listed and read; the three big code files (327 KB
Remote Script, 115 KB MCP server, 98 KB Max for Live script) were searched, not read line by line. This is not a
security audit. The kit's own text is not copied here beyond short facts (its site terms forbid redistribution).

## What is in the folder

39 files, about 0.9 MB: a Remote Script (one `__init__.py`), an MCP server, an optional REST API server, an
optional Max for Live chat device, six small audio scripts, five docs, an installer (`setup.py` plus a `.bat` and a
`.command`), and `CLAUDE.md` / `AGENTS.md` that tell an AI assistant to run the installer.

| Site promise (`/`, 2026-11-13) | In the folder |
|---|---|
| "200+ Ableton actions" | 136 `@mcp.tool` definitions counted in `MCP_Server/server.py`. Remote Script commands not counted. 200+: not verified |
| "built-in analyser ... waveform and spectrogram" | Yes: `audio_tools/analyze_audio.py` (peak, RMS, crest, centroid, band energy, brightness, onset density, PNGs) |
| "Key detection", "Anti-clash scoring", "target LUFS" | Not listed in `audio_tools/README.md`. Whether the scripts or the server do it: not checked, to test |
| "Premium template file", "Producer command library", "Free MIDI packs & presets", videos | Not in the folder. Possibly in the members area: not checked |
| "Standalone app" | Not in the folder |

Other facts:

- `README.md` says "Ableton Live 10 or newer" and Python 3.10+. The site states no Live version.
- `LICENSE` is MIT, "Copyright (c) 2026 Ableton AI Control". `pyproject.toml`: name `studiopilot`, version 1.0.0.
  The site terms say "You may not ... redistribute the files"; the file in the kit grants MIT rights. The two
  disagree. Which one binds is a question for a lawyer, not answered here.
- `CLAUDE.md` says the MCP server is registered as `ableton`; `setup.py` actually uses `studiopilot`.

## What the installer would change on this computer (from reading `setup.py`)

1. Creates `C:\Users\ronen\studiopilot-kit\.venv` and installs from PyPI, unpinned: `mcp[cli]`, `numpy`,
   `soundfile`, `scipy`, `matplotlib`, `fastapi`, `uvicorn`, `pydantic`, `requests`.
2. Copies the Remote Script as `StudioPilot` into every folder it finds. On this machine:
   - `%APPDATA%\Ableton\Live 12.2.2\Preferences\User Remote Scripts\` (exists)
   - `%APPDATA%\Ableton\Live 12.4.16\Preferences\User Remote Scripts\` (exists)
   - It looks for `C:\Users\ronen\Documents\Ableton\User Library`, which does not exist here: the real User
     Library is under `OneDrive\Documents`. The installer does not look there. It still installs, through the two
     preference folders.
3. Registers an MCP server named `studiopilot` at Claude Code **user scope** (`claude mcp remove` then
   `claude mcp add -s user`). The existing `ableton` server (track2ableton) has a different name and, by the code,
   is not touched.
4. Writes `studiopilot` into `%APPDATA%\Claude\claude_desktop_config.json` (the Claude folder exists; the config
   currently has no MCP servers).
5. Writes `.mcp.json` in the kit folder. Codex: not installed here, skipped.

To undo: delete the two `StudioPilot` folders, `claude mcp remove -s user studiopilot`, remove the entry from the
Claude Desktop config, delete `.venv` and `.mcp.json`.

## Findings before any test

| # | Finding | Evidence |
|---|---|---|
| 1 | **Same port as our bridge.** Their Remote Script binds `localhost:9877`; `T2A_Bridge` uses 9877 too. Only one of the two can be the active Control Surface | `StudioPilot_Remote_Script/__init__.py` lines 12 and 79; `ableton_bridge/T2A_Bridge/bridge.py` line 22. Their port can be moved with the `ABLETON_MCP_PORT` environment variable |
| 2 | No outbound internet address found in the MCP server, the Remote Script or the audio tools: only `localhost` | search for URLs and network calls across the folder |
| 3 | The optional Max for Live device calls OpenAI, Anthropic, Groq or a local Ollama with the user's own API key. The installer does not install it | `StudioPilot_M4L/code/main.js` |
| 4 | The optional REST server listens on `127.0.0.1:8000` by default; it is not started by the installer | `MCP_Server/rest_api_server.py` |
| 5 | No licence check, account sign-in or telemetry found by search | not a full read |
| 6 | The installer misses a User Library that lives in OneDrive (our `doctor` finds it) | `setup.py` `ableton_remote_dirs()` |
| 7 | Two more Remote Scripts already sit in the User Library: `T2A_Bridge` and `MYROAD_Studio_Bridge` | folder listing |

## Next, for the user's decision

Install by running their `setup.py` as it is (report, do not repair), with Live closed, after a backup of the two
`User Remote Scripts` folders, the OneDrive `Remote Scripts` folder, `~\.claude.json` and the Claude Desktop
config. Then in a new empty Set: the user selects `StudioPilot` as Control Surface **instead of** `T2A_Bridge`,
restarts Claude Code, and the kit's tools are run through the same list as stage 2, so the two tools can be
compared row by row.

STOP.

## Installation, 2026-11-13 (user approved: "back up and install")

Backup first, to `C:\Users\ronen\studiopilot-backup-2026-11-13`: both `User Remote Scripts` folders, the OneDrive
`Remote Scripts` folder (19 files), `.claude.json`, `claude_desktop_config.json`.

**Correction:** the inspection above said Live was closed. It was not: `Ableton.exe` had been running since 16:24
(the earlier process check printed nothing because of an output formatting fault of mine). The installer was run
with Live open; it only copies files, and no Set was touched by this session.

Call: `py setup.py` in the kit folder. Exit code 0. Output, in short: environment created, packages installed,
control script installed to both preference folders, "Claude Desktop: connected", "Claude Code: connected
(C:\Users\ronen\.claude.json)", "Codex: not found (skipped)".

Checked afterwards against the backup:

| Item | Result |
|---|---|
| `StudioPilot\__init__.py` in Live 12.2.2 and 12.4.16 preference folders | present, 327,737 bytes each |
| `.claude.json` user MCP servers | `ableton`, `studiopilot`. The `ableton` entry is identical to the backup. 66 top-level keys before and after |
| `claude_desktop_config.json` | old keys kept, `mcpServers.studiopilot` added |
| `.venv` packages | mcp 2.3.0, numpy 2.5.4, scipy 1.18.1, soundfile 0.14.0, matplotlib 3.11.2, fastapi 0.162.7, uvicorn 0.54.0, pydantic 2.14.3, requests 2.34.2 |

Observations:

- The installer reported `.claude.json` as the place it registered Claude Code, which by its code is the fallback
  path: the `claude mcp add` call did not succeed here (the installer swallows the reason). It then rewrote the
  whole 159 KB `.claude.json` itself (re-indented, 159,274 to 164,270 bytes) **while Claude Code was running and
  using that file**. Nothing broke in this session, but a concurrent write by Claude Code could lose one side's
  change. Worth watching after the restart.
- Install time: about one to two minutes, no prompts, no errors.

### FAIL: `StudioPilot` does not appear in Live's Control Surface list

- Live 12.4.16 Suite was restarted by the user at 20:30 (after the install). User's words: "I can't find
  StudioPilot as a Control Surface". Live's `Log.txt` after the restart mentions only `T2A_Bridge`, never
  `StudioPilot`: Live did not try to load it.
- Expected (installer output): "Installed control script" twice, then "Under 'Control Surface', choose: StudioPilot".
- Likely cause (not proven): the installer put the Python script only into `Preferences\User Remote Scripts`,
  which on this Live holds `UserConfiguration.txt` instant mappings. Python Remote Scripts here load from the User
  Library's `Remote Scripts` folder, and this user's User Library is in `OneDrive\Documents`, where the installer
  does not look (finding 6). It printed success anyway.
- What was done, at the user's request, and not silently: the manual step the installer itself prints for the
  not-found case, i.e. the script copied to `OneDrive\Documents\Ableton\User Library\Remote Scripts\StudioPilot`.
  The kit's code was not changed. Result after the next Live restart: **it appears and loads.** User's words: "now it appears, I selected it".
  `Log.txt` at 20:33:09: "(StudioPilot) Server started on port 9877", "(StudioPilot) StudioPilot initialized";
  `127.0.0.1:9877` is listening, owned by `Ableton.exe`. So the cause is confirmed: the installer's two target
  folders do not make the script visible on this Live 12.4.16, and it misses a User Library inside OneDrive.
- State now: `T2A_Bridge` is not the active Control Surface. track2ableton's `ableton` tools will not reach Live
  until the user switches back.

### FAIL: the kit's MCP server does not start as installed

- After the user restarted Claude Code, the harness reported: `studiopilot (CONNECTION_CLOSED): "Connection closed"`.
- The registered command run by hand (`.venv\Scripts\python.exe -m MCP_Server.server`, `PYTHONPATH` = kit folder)
  exits with code 1:
  `ModuleNotFoundError: No module named 'mcp.server.fastmcp'. This is mcp 2.x, where FastMCP was renamed to
  MCPServer ... or pin 'mcp<2' to keep running v1 code.` (raised at `MCP_Server/server.py` line 2).
- Cause, confirmed: `setup.py` installs `mcp[cli]>=1.3.0` with no upper bound; on 2026-11-13 that resolves to
  mcp 2.3.0, which the kit's code cannot import. **A fresh install of the kit bought today cannot work with any
  assistant**, and the installer still prints "connected". Nothing in the kit's output points at this.
- Workaround applied, openly, to be able to test at all: `pip install "mcp[cli]<2"` inside the kit's own `.venv`
  (now mcp 1.30.0). The kit's code was not changed. Run by hand again: the server stays up and logs "Successfully
  connected to Ableton on startup" (Live 12.4.16, `StudioPilot` control surface, port 9877).
- Still to do: one more Claude Code restart so the tools load.

Not done yet (needs the user's hands): restart Live, select `StudioPilot` as Control Surface instead of
`T2A_Bridge` in a new empty Set, restart Claude Code. No kit tool has been called.

STOP.
