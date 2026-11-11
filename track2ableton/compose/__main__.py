"""Command line: python -m track2ableton.compose --out "My Track" --bpm 130 --key "A minor" """
from __future__ import annotations

import argparse
import os
import sys

from .arrange import Spec, compose
from .export import bar_table, write
from .theory import PROGRESSIONS


def _bar_range(text: str) -> tuple:
    try:
        first, last = (int(x) for x in text.split("-"))
    except ValueError:
        raise argparse.ArgumentTypeError("expected two bar numbers such as 81-84") from None
    if not 1 <= first <= last:
        raise argparse.ArgumentTypeError("bars must be positive and in order, e.g. 81-84")
    return first, last


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="track2ableton-compose",
                                 description="Compose a full club track as MIDI (drums, bass, chords, hook, vocal triggers), checked bar by bar.")
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--bpm", type=float, default=130.0)
    ap.add_argument("--key", default="A minor", help='e.g. "A minor", "F minor", "D dorian", "E phrygian", "D hijaz"')
    ap.add_argument("--progression", choices=sorted(PROGRESSIONS), help="default: the usual one for the key's mode")
    ap.add_argument("--structure", choices=["extended", "radio", "loop16"], default="extended",
                    help="extended = 200-bar DJ mix, radio = 97 bars cut from it (96 + a closing bar), loop16 = 16 bars of the drop for auditioning")
    ap.add_argument("--variant", type=int, choices=[0, 1, 2], default=0, help="alternative wood, bass and hook figures")
    ap.add_argument("--variants", type=int, choices=[0, 1, 2, 3], default=0,
                    help="write this many variants into sub-folders v0, v1, ... (there are 3)")
    ap.add_argument("--swing", type=float, default=57.5, help="percussion swing in percent (50 = straight)")
    ap.add_argument("--late-ms", type=float, default=6.0, help="how far the skins sit behind the beat")
    ap.add_argument("--straight-pitched", action="store_true",
                    help="keep bass, pad and hook on the straight grid; only the percussion swings (for A/B by ear)")
    ap.add_argument("--straight", action="store_true", help="write straight MIDI and apply the groove in Live instead")
    ap.add_argument("--show", metavar="A-B", type=_bar_range, help="print a text grid of bars A..B, e.g. 81-84")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ok = True
    for v in (range(a.variants) if a.variants else [a.variant]):
        spec = Spec(bpm=a.bpm, key=a.key, progression=a.progression, structure=a.structure, variant=v, swing=a.swing,
                    late_ms=a.late_ms, swing_hook=not a.straight_pitched, swing_bass=not a.straight_pitched,
                    swing_pad=not a.straight_pitched, bake_feel=not a.straight)
        try:
            comp = compose(spec)
        except ValueError as exc:
            ap.error(str(exc))
        out = os.path.join(a.out, f"v{v}") if a.variants else a.out
        info = write(comp, out)
        failed = [c for c in info["checks"] if not c["ok"]]
        print(f"{out}: {info['key']}, {info['bpm']:g} BPM, {info['total_bars']} bars ({info['length']}), "
              f"{len(info['tracks'])} tracks, {sum(t['notes'] for t in info['tracks'])} notes, "
              f"checks {len(info['checks']) - len(failed)}/{len(info['checks'])} passed")
        for c in failed:
            print(f"  FAILED: {c['check']}: {c['detail']}")
        if a.show:
            print(bar_table(comp, *a.show))
        ok = ok and not failed
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
