# Vocals from MIDI, stems and engines (instructions for the Claude Code session on the user's computer)

The tool prepares and connects; it does not sing. A vocal is made by a singing engine installed on this computer.
Your job: get the score right inside Live, find out which engines this computer can run, and wire one in only
after the user has chosen it. Report what does not behave as described; nothing here has run against a real Live
or a real engine yet. Speak Hebrew with the user.

## Stage 0: get the tool

```
cd C:\Users\ronen\track2ableton
git fetch origin claude/vigilant-planck-d78nmz
git checkout origin/claude/vigilant-planck-d78nmz -- track2ableton tests docs pyproject.toml
py -m pip install -e ".[live,vocal]"
py -m pytest tests/test_vocal.py -q
```

Expected: no failures. Two tests check the files with outside libraries and are skipped when those are missing
(`py -m pip install music21 mido` runs them too: `13 passed`). Restart the MCP server (restart Claude Code) so the new tools `vocal_score` and
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
- OpenUtau with a DiffSinger voice: import `vocal.mid` or `vocal.musicxml`, check the lyrics landed on the notes,
  render to WAV at the project tempo.
- Any engine: export the voice as WAV starting at the clip's first beat, then `create_audio_clip` on a new audio
  track at the arrangement position where the MIDI clip starts. Measure: the first syllable's onset within about
  20 ms of the first note.

Voice conversion (cloning) comes after this, on the rendered or recorded vocal, and only with a voice model of the
user's own voice or one they hold a written licence for. Ask, and record the answer in LICENSES.md.

## Stems

`split_stems(file_path, position)` splits a file and puts each stem on a new audio track. Check `method` in the
result: `demucs:...` is the neural split; `dsp:...` is the rough built-in one, and the user should know which they
got. For a whole song that should also be put on the grid, use the fix stage instead (`docs/FIX_IN_LIVE.md`).
