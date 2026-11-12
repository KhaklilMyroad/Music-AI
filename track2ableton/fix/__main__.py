"""python -m track2ableton.fix SONG.wav   or   python -m track2ableton.fix "folder of stems" """
from __future__ import annotations

import argparse
import os
import sys


def _bpm(x: str) -> float:
    v = float(x)
    if not 40 <= v <= 250:
        raise argparse.ArgumentTypeError("tempo must be between 40 and 250 BPM")
    return v


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="track2ableton-fix", description="Put a finished recording right: a round steady tempo, "
                                 "notes that agree with their own repetitions, one chord loop, and a Live Set to go on from.")
    ap.add_argument("source", help="an audio file, or a folder with one audio file per stem")
    ap.add_argument("-o", "--out", help="output folder (default: '<name> Fixed Project' next to the source)")
    ap.add_argument("--bpm", type=_bpm, help="project tempo (default: the measured tempo rounded to a whole number)")
    ap.add_argument("--light", action="store_true", help="change a bar only when all its nearest repetitions agree against it")
    ap.add_argument("--separation", choices=["auto", "demucs", "dsp"], default="auto", help="for a single file: how to split it into stems")
    ap.add_argument("--demucs-model", default="htdemucs_6s")
    ap.add_argument("--transcription", choices=["auto", "basic-pitch", "builtin"], default="auto")
    ap.add_argument("--template", help="an empty Live Set saved by your Live version")
    ap.add_argument("--no-als", action="store_true", help="skip the .als")
    args = ap.parse_args(argv)
    if not os.path.exists(args.source):
        print(f"error: not found: {args.source}", file=sys.stderr)
        return 2
    src = os.path.normpath(os.path.abspath(args.source))
    base = os.path.basename(src) if os.path.isdir(src) else os.path.splitext(os.path.basename(src))[0]
    out = args.out or os.path.join(os.path.dirname(src), f"{base} Fixed Project")
    from .project import run

    print(f"track2ableton fix: {src} -> {out}")
    try:
        info = run(src, out, args.bpm, args.light, args.separation, args.demucs_model, args.transcription, not args.no_als, args.template)
    except (ValueError, FileNotFoundError) as exc:      # nothing usable in the folder, a clip too short, a missing template
        print(f"error: {exc}", file=sys.stderr)
        return 2
    t = info["tempo"]
    print(f"\n  Tempo {t['measured_bpm']:g} -> {t['project_bpm']:g} BPM ({t['stretch_percent']:+.2f} %), "
          f"{'drifting, ' if t['drifting'] else ''}{t['warp_markers']} warp markers | Key {info['key']['name']}")
    for r in info["tracks"]:
        print(f"  {r['track']:24} {r['raw_notes']:5d} -> {r['fixed_notes']:5d} notes, {r['changed']} changed")
    if t["not_steady_but_not_followed"]:
        print("  ! The tempo is not steady and could not be followed: check the grid by ear in every section.")
    if info.get("als_error"):
        print(f"  ! The Live Set was not written ({info['als_error']}). Everything else is there.")
    print(f"\n  Read: {os.path.join(out, 'FIX_REPORT.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
