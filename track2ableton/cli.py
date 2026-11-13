"""Command line: python -m track2ableton song.mp3 -o out/"""
from __future__ import annotations

import argparse
import os
import sys

from . import __version__


def main(argv=None) -> int:
    from ._console import safe_output
    safe_output()
    ap = argparse.ArgumentParser(prog="track2ableton", description="Reverse-engineer a mixed track into an Ableton Live 12 rebuild package.")
    ap.add_argument("audio", help="input audio file (wav, flac, aiff, mp3, m4a ...)")
    ap.add_argument("-o", "--out", help="output folder (default: '<name> Rebuild Project' next to the input)")
    ap.add_argument("--separation", choices=["auto", "demucs", "dsp"], default="auto", help="stem separation backend (default: demucs if installed, else dsp)")
    ap.add_argument("--demucs-model", default="htdemucs_6s", help="demucs model: htdemucs_6s (drums,bass,other,vocals,guitar,piano), htdemucs, htdemucs_ft")
    ap.add_argument("--transcription", choices=["auto", "basic-pitch", "builtin"], default="auto")
    ap.add_argument("--template", help="an empty Live Set saved by YOUR Live version (needs one MIDI, one audio and one return track)")
    ap.add_argument("--no-als", action="store_true", help="skip .als generation")
    ap.add_argument("--about-bpm", type=float, help="roughly the song's tempo, when you know it: settles a tempo read at twice or half")
    ap.add_argument("--beats-per-bar", type=int, choices=range(2, 8), metavar="2-7", help="beats in a bar, when the analysis reads 3 for 4 or the reverse")
    ap.add_argument("--version", action="version", version=f"track2ableton {__version__}")
    args = ap.parse_args(argv)
    if not os.path.isfile(args.audio):
        print(f"error: file not found: {args.audio}", file=sys.stderr)
        return 2
    base = os.path.splitext(os.path.basename(args.audio))[0]
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.audio)), f"{base} Rebuild Project")
    from .pipeline import run

    print(f"track2ableton {__version__}: {args.audio} -> {out}")
    a = run(args.audio, out, args.separation, args.demucs_model, args.transcription, not args.no_als, args.template,
            about_bpm=args.about_bpm, beats_per_bar=args.beats_per_bar)
    r, k = a.rhythm, a.tonal
    print(f"\n  Tempo {r.bpm:g} BPM ({r.beats_per_bar}/4) | Key {k.key_name} ({k.camelot}) | {a.lufs:.1f} LUFS | {len(a.sections)} sections | {len(a.tracks)} stems")
    for w in a.warnings:
        print(f"  ! {w}")
    print(f"\n  Open: {os.path.join(out, 'report.html')}")
    return 0
