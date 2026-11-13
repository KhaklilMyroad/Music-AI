# Vocals from MIDI, stems and engines (instructions for the Claude Code session on the user's computer)

The tool prepares and connects; it does not sing. A vocal is made by a singing engine installed on this computer.
Your job: get the score right inside Live, find out which engines this computer can run, and wire one in only
after the user has chosen it. Report what does not behave as described; nothing here has run against a real Live
or a real engine yet. Speak Hebrew with the user.

## Stage 0: get the tool

```
cd C:\Users\ronen\track2ableton
git fetch origin claude/vigilant-planck-d78nmz
git checkout origin/claude/vigilant-planck-d78nmz -- track2ableton tests docs ableton_bridge pyproject.toml README.md
py -m pip install -e ".[live,vocal]"
py -m pytest tests/test_vocal.py -q
```

Expected: no failures. Two tests check the files with outside libraries and are skipped when those are missing
(`py -m pip install music21 mido` runs them too: `14 passed`). Restart the MCP server (restart Claude Code) so the new tools `vocal_score` and
`split_stems` appear. If local changes exist in those folders, stop and ask before overwriting them.

## Stage 1: what this computer can run

Report to the user, without installing anything yet:

- GPU and its memory (`nvidia-smi`), free disk space, Python version.
- Whether ACE Studio and its ACE Bridge plug-in are installed (search Live's browser for "ACE Bridge").
- Whether Demucs is installed (`py -m pip show demucs`).

STOP: the user decides which engine to use. `docs/VOCAL.md` lists the options, what is known about each and what
is not. Do not download a model or a voice before the user has seen its licence; every voice and model gets a row
in LICENSES.md (name, source, licence, whether commercial release is allowed).

## Stage 2: the vocal score

1. The melody must be a MIDI clip with one note at a time. Ask the user for the lyrics as text, one line per
   musical phrase.
2. Call `vocal_score(track, lyrics, out_dir, language, slot or arrangement_index)`. language: "es", "en", or
   "typed" (syllables exactly as typed with hyphens; use it for Hebrew in transliteration).
3. Read `VOCAL_REPORT.md` with the user. An error means the syllables and notes of a line do not match: show the
   line and its two counts, and let the user decide where a note holds a syllable (a lone `-` in the lyric) or
   which word changes. Do not use `fit="end"` unless the user asks for it.
4. Warnings (a syllable too fast, no room to breathe, a leap, word stress against the bar) are for the user's
   ear: say them, do not fix them unasked.

STOP when the report says ready.

## Stage 3: render and bring back

Depends on the engine the user chose:

- ACE Studio: insert ACE Bridge on a MIDI track as its documentation describes, or import `vocal.mid` /
  `vocal.musicxml` in ACE Studio if it accepts them (not verified: try and report which one keeps the lyrics).
- OpenUtau with a DiffSinger voice: its documentation names .ustx, .ust and .vsqx projects and File > Import MIDI.
  Whether the import keeps the lyric events of `vocal.mid`, and whether it reads `vocal.musicxml`, is not known:
  try both on a short clip and report exactly what arrived (notes only, or notes with a syllable each). If the
  lyrics do not arrive, stop and say so: the tool will then write the format OpenUtau does read. Do not type the
  lyrics in by hand as a workaround without telling the user.
- Any engine: export the voice as WAV starting at the clip's first beat, then `create_audio_clip` on a new audio
  track at the arrangement position where the MIDI clip starts. Measure: the first syllable's onset within about
  20 ms of the first note.

Voice conversion (cloning) comes after this, on the rendered or recorded vocal, and only with a voice model of the
user's own voice or one they hold a written licence for. Ask, and record the answer in LICENSES.md.

## Demucs, in its own environment

Demucs needs PyTorch: several GB, with its own version pins, and on a new Python on Windows not every part of it
installs cleanly. Keep it out of the environment the tool and its MCP server run in, so that a failed install
cannot break them. Ask the user before downloading; say the size pip reports.

1. Make a separate environment, with Python 3.12 if it is installed (`py -0` lists the versions), else the default:
   `py -3.12 -m venv C:\Users\ronen\demucs-env`
2. Install PyTorch into it with the command the selector on pytorch.org gives for Windows, pip and this
   computer's CUDA (do not guess the index URL), then `...\demucs-env\Scripts\python -m pip install demucs soundfile`.
3. Try it on a short file: `...\demucs-env\Scripts\python -m demucs -n htdemucs_6s -o "%TEMP%\demucs_try" "<a wav>"`.
   If it fails, report the error text as it is. Do not patch packages.
4. Tell the tool where it is, then restart Claude Code:
   `setx T2A_DEMUCS_PYTHON "C:\Users\ronen\demucs-env\Scripts\python.exe"`

Without the variable the tool looks for Demucs in its own environment, and without Demucs anywhere it uses the
rough built-in split and says so.

## Stems

`split_stems(file_path, position)` splits a file and puts each stem on a new audio track. Check `method` in the
result: `demucs:...` is the neural split; `dsp:...` is the rough built-in one, and the user should know which they
got. For a whole song that should also be put on the grid, use the fix stage instead (`docs/FIX_IN_LIVE.md`).
