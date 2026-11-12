"""python -m track2ableton.vocal melody.mid lyrics.txt --lang es -o out"""
from __future__ import annotations

import argparse
import os
import sys

from .. import midi
from . import score as vs


def main(argv=None) -> int:
    from .._console import safe_output
    safe_output()
    ap = argparse.ArgumentParser(prog="track2ableton-vocal", description="A melody (MIDI) and its words as a vocal score: a syllable "
                                 "on every note, checked, as MIDI with lyrics, MusicXML and JSON. It prepares the score; it does not sing.")
    ap.add_argument("melody", help="a MIDI file with the vocal melody, one note at a time")
    ap.add_argument("lyrics", help="a text file: one line per phrase; a lone - or + holds the previous syllable; sha-lom sets syllables by hand")
    ap.add_argument("-o", "--out", default=None, help="output folder (default: next to the melody)")
    ap.add_argument("--lang", choices=["en", "es", "typed"], default="en", help="en, es, or typed: every word is one syllable unless hyphenated")
    ap.add_argument("--bpm", type=float, default=120.0)
    ap.add_argument("--beats-per-bar", type=int, default=4)
    ap.add_argument("--fit", choices=["strict", "end"], default="strict", help="end: the last syllable of a line carries its extra notes")
    ap.add_argument("--phrase-gap", type=float, default=1.0, help="a rest of this many beats ends a phrase")
    args = ap.parse_args(argv)
    for f in (args.melody, args.lyrics):
        if not os.path.isfile(f):
            print(f"error: not found: {f}", file=sys.stderr)
            return 2
    try:
        notes = midi.read(args.melody)
        text = open(args.lyrics, encoding="utf-8").read()
        sc = vs.build(notes, text, args.lang, args.bpm, args.beats_per_bar, args.fit, args.phrase_gap)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.melody)), "vocal score")
    res = vs.write(sc, out)
    print(f"{res['note_count']} notes, {res['syllable_count']} syllables, {'ready' if res['ready'] else 'NOT ready'}")
    for p in sc.problems:
        print(f"  {p['level']:7} {p['at']:>6}  {p['detail']}")
    print(f"\n  Read: {res['files']['report']}")
    return 0 if sc.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
