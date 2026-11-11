"""Pitched parts: sub / mid bass, pad chords, hook, vocal triggers. Everything is on the 16th grid.

An event is (position in beats inside the bar, pitch, duration in beats, velocity).
"""
from __future__ import annotations

from .model import STEP
from .theory import Chord, QUALITIES

SUB_LO, SUB_HI = 28, 39          # E0..D#1 in Ableton names: 41-78 Hz, the range a club sub reproduces cleanly
PAD_LO = 52                      # nothing in the pad below ~165 Hz
HOOK_LO = 60
KICK_STEPS = (0, 4, 8, 12)
BASS_DUR = 0.2125                # 85 % of a 16th
CHANT_PITCH, SHOUT_PITCH = 60, 62


def sub_pitch(pc: int) -> int:
    p = 24 + pc % 12
    return p + 12 if p < SUB_LO else p


def _approach(cur: int, nxt: int, chord: Chord) -> int | None:
    """Scale tone right below the next root when the line moves up (e.g. the leading tone into the tonic)."""
    if nxt <= cur:
        return None
    for p in range(nxt - 1, cur, -1):
        if p % 12 in chord.scale_pcs:
            return p
    return None


def bass_bar(pattern: str, chord: Chord, next_chord: Chord, bar_in_chord: int, chord_idx: int, variant: int = 0) -> list:
    """One bar of sub bass. Never plays on a kick step (0, 4, 8, 12) except the 'drone' used in breaks."""
    r = sub_pitch(chord.root_pc)
    nxt = sub_pitch(next_chord.root_pc)
    app = _approach(r, nxt, chord) if bar_in_chord == 1 else None
    v = variant % 3
    if pattern == "drone":
        return [(0.0, r, 2 * 4 - 0.1, 100)] if bar_in_chord == 0 else []
    if pattern == "offbeat":
        ev = [(s, r, 0.375, 108) for s in (2, 6, 10, 14)]
        if app is not None:
            ev[-1] = (14, r, 0.2, 108)
            ev.append((15, app, BASS_DUR, 92))
    elif pattern == "rolling":
        if v == 1:      # gallop
            ev = [(s, r, BASS_DUR, vel) for s, vel in ((3, 100), (6, 112), (7, 92), (11, 100), (14, 112), (15, 92))]
        elif v == 2:    # long-short
            ev = [(3, r, BASS_DUR, 104), (6, r, 0.375, 112), (11, r, BASS_DUR, 104), (14, r, 0.375, 112)]
        else:           # pairs between the kicks
            ev = [(s, r, BASS_DUR, 112 if s % 2 == 0 else 92) for s in (2, 3, 6, 7, 10, 11, 14, 15)]
            if chord_idx == 0 and bar_in_chord == 1:   # answer bar on the tonic: third above, seventh below
                ev[1] = (3, r + chord.third, BASS_DUR, 92)
                if r + chord.degree(-1) >= SUB_LO:
                    ev[4] = (10, r + chord.degree(-1), BASS_DUR, 112)
        if app is not None and ev[-1][0] == 15:
            ev[-1] = (15, app, BASS_DUR, 92)
    else:
        raise ValueError(f"unknown bass pattern {pattern!r}")
    assert not any(s in KICK_STEPS for s, *_ in ev)
    return [(s * STEP, p, d, vel) for s, p, d, vel in ev]


def voice_chord(chord: Chord, prev: list | None) -> list:
    """Close-position voicing with the least movement from the previous chord, lowest note >= PAD_LO."""
    pcs = [(chord.root_pc + i) % 12 for i in QUALITIES[chord.quality]]
    if chord.quality == "M7b9":
        pcs.append((chord.root_pc + 10) % 12)
    best = None
    for base in range(PAD_LO, PAD_LO + 12):
        v = sorted(base + (pc - base) % 12 for pc in pcs)
        if prev:
            cost = sum(min(abs(p - q) for q in prev) for p in v) + sum(min(abs(p - q) for p in v) for q in prev)
        else:
            cost = abs(sum(v) / len(v) - 62)
        key = (cost, sum(v))
        if best is None or key < best[0]:
            best = (key, v)
    return best[1]


def pad_bar(mode: str, voicing: list, bar_in_chord: int) -> list:
    if mode == "sustain":
        return [(0.0, p, 2 * 4 - 0.25, 78) for p in voicing] if bar_in_chord == 0 else []
    if mode == "stab":
        return [(s * STEP, p, 0.2, vel) for s, vel in ((3, 90), (10, 84)) for p in voicing]
    raise ValueError(f"unknown pad mode {mode!r}")


# Hook motifs live on beats 3-4 (steps 8-15) so a chant can sit on beats 1-2.
# (step, scale steps above the chord root, length in 16ths, velocity); A = first bar of a chord, B = second.
MOTIFS = {
    0: ("respuesta", [(8, 4, 2, 104), (10, 5, 1, 88), (11, 4, 2, 96), (13, 2, 1, 86), (14, 0, 2, 100)],
                     [(9, 0, 1, 84), (10, 2, 1, 90), (11, 4, 2, 100), (13, 5, 1, 84), (14, 4, 2, 96)]),
    1: ("andaluz", [(8, 4, 2, 104), (10, 3, 2, 92), (12, 2, 2, 98), (14, 1, 2, 88)],
                   [(8, 0, 4, 106), (13, -1, 1, 80), (14, 0, 2, 96)]),
    2: ("golpe", [(9, 2, 1, 92), (11, 4, 1, 100), (14, 2, 1, 88), (15, 0, 1, 96)],
                 [(9, 4, 1, 92), (11, 2, 1, 100), (14, 0, 1, 90), (15, 2, 1, 84)]),
}


def hook_root(chord: Chord) -> int:
    return HOOK_LO + (chord.root_pc - HOOK_LO) % 12


# last bar of the 8-bar chord loop: a run up the chord's scale (Phrygian dominant over the V of a minor key)
TURNAROUND = [(8, 0, 1, 92), (9, 1, 1, 84), (10, 2, 1, 96), (11, 3, 1, 88), (12, 4, 2, 108), (14, 2, 2, 94)]


def hook_bar(chord: Chord, bar_in_chord: int, variant: int = 0, octave: bool = False, turnaround: bool = False) -> list:
    _, a, b = MOTIFS[variant % 3]
    root = hook_root(chord)
    ev = []
    for step, deg, length, vel in (TURNAROUND if turnaround else a if bar_in_chord == 0 else b):
        p = root + chord.degree(deg)
        ev.append((step * STEP, p, length * STEP * 0.8, vel))
        if octave:
            ev.append((step * STEP, p + 12, length * STEP * 0.8, max(1, vel - 18)))
    return ev


def nearest_chord_tone(pitch: int, chord: Chord, avoid: int | None = None) -> int:
    tones = set(chord.tones)
    for d in (1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6):
        if (pitch + d) % 12 in tones and pitch + d != avoid:
            return pitch + d
    return pitch
