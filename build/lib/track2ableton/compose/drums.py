"""Organic afro-tech drum patterns, written note by note (no randomness).

Skins and wood carry the groove, metal is sparse and soft, the shaker leaves gaps, congas answer each
other inside the bar (in a two-bar form), and bongo / djembe take turns across bars. A phrase is 16 bars
(4 x 4): instruments enter by phrase, bar 8 has a pickup, bar 12 a low-drum pickup and bar 16 the full
turnaround: a roll handed from the high to the low conga with the last kick left out.

A hit is (position in beats inside the bar, velocity, duration in beats). `pb` is the bar of the
16-bar phrase (1..16). `k` is the bar of an 8-bar build tail (1..8).
"""
from __future__ import annotations

from .model import STEP

DRUM_ROLES = ["Kick", "Clap", "Wood", "Hat", "Shaker", "Conga Hi", "Conga Low", "Bongo", "Djembe", "Low Drum",
              "Clave", "Cowbell", "Roll"]
GROUP = {r: "PERC" for r in DRUM_ROLES}
GROUP.update({"Kick": "DRUMS", "Clap": "DRUMS", "Wood": "DRUMS", "Hat": "DRUMS", "Roll": "DRUMS"})
SKINS = frozenset({"Conga Hi", "Conga Low", "Bongo", "Djembe", "Low Drum"})   # played slightly behind the beat
STRAIGHT = frozenset({"Kick", "Clap", "Roll"})                                # never swung
TAIL_STRAIGHT = {"Conga Hi": 4}   # from this bar of a build tail the role plays straight 16ths, like the roll beside it
GM_PITCH = {"Kick": 36, "Clap": 39, "Wood": 76, "Hat": 42, "Shaker": 70, "Conga Hi": 62, "Conga Low": 64, "Bongo": 60,
            "Djembe": 61, "Low Drum": 41, "Clave": 75, "Cowbell": 56, "Roll": 38}
HINT = {
    "Kick": "round, warm kick with a short tail (<200 ms), tuned to the key's tonic",
    "Clap": "clap layered with a finger snap",
    "Wood": "low wood block or rim",
    "Hat": "soft closed hat; high-pass 300 Hz, no high boost",
    "Shaker": "short, low shaker or soft maracas",
    "Conga Hi": "high conga, open or slap",
    "Conga Low": "low conga, open and soft",
    "Bongo": "bongo or hand slap",
    "Djembe": "djembe or African hand drum",
    "Low Drum": "low African drum / floor tom, marks phrases",
    "Clave": "bright clave (3-2 son)",
    "Cowbell": "latin cowbell, beat hits together with the kick",
    "Roll": "snare or clap for the build roll; automate a high-pass / pitch rise in Live",
}
DUR = 0.2        # 16th-note drum hit: shorter than a 16th so a swung hit never overlaps the next one
DUR_32 = 0.1


def _h(pairs, dur=DUR):
    return [(s * STEP, int(v), dur) for s, v in pairs]


def _clip(v):
    return max(1, min(127, int(round(v))))


def bar_hits(role: str, pb: int, variant: int = 0) -> list:
    """Hits of one normal bar. pb = bar inside the 16-bar phrase (1..16)."""
    v = variant % 3
    if role == "Kick":
        hits = [(0, 124), (4, 118), (8, 122), (12, 118)]
        return _h(hits[:3] if pb == 16 else hits)
    if role == "Clap":
        return _h([(4, 110), (12, 114)] + ([(15, 58)] if pb in (8, 12, 16) else []))
    if role == "Wood":
        if pb < 5:
            return []
        if v == 1:
            return _h([(3, 84), (10, 92), (13, 70)] + ([(15, 76)] if pb % 4 == 0 else []))
        if v == 2:
            return _h([(0, 100), (3, 78), (6, 90), (10, 96), (12, 84)])
        return _h([(2, 84), (7, 72), (11, 96), (14, 80)] if pb == 15 else [(3, 88), (6, 70), (10, 96)])
    if role == "Hat":
        if pb < 9:
            return []
        if v == 2:
            return _h([(2, 72), (6, 60), (10, 76), (13, 44), (14, 66)])
        return _h([(2, 70), (6, 64), (10, 74), (14, 64)] + ([(15, 48)] if pb >= 13 else []))
    if role == "Shaker":
        hits = [(2, 82), (6, 70), (8, 56), (10, 84), (14, 72)]
        if pb >= 9:
            hits += [(3, 44), (7, 48), (11, 44), (15, 52)]
        if pb in (8, 16):                     # the shaker breathes before a pickup
            hits = [x for x in hits if x[0] < 12]
        return _h(sorted(hits))
    if role == "Conga Hi":
        if pb <= 4:
            base = [(6, 92), (7, 106)]
        elif v == 1:
            base = [(2, 60), (6, 88), (7, 104)]
        else:                                 # two-bar form: the answer bar starts later and softer
            base = [(3, 58), (6, 92), (7, 100)] if pb % 2 == 0 else [(2, 56), (3, 62), (6, 92), (7, 106)]
        if pb == 8:
            base = [x for x in base if x[0] < 13] + [(13, 70), (14, 82), (15, 98)]
        if pb == 16:                          # turnaround: the roll starts here on beat 3 ...
            base = [x for x in base if x[0] < 8] + [(8, 62), (9, 70), (10, 72), (11, 86)]
        return _h(base)
    if role == "Conga Low":
        if pb == 16:                          # ... and the low conga finishes it on beat 4
            return _h([(12, 94), (13, 96), (14, 110), (15, 118)])
        if pb <= 4:
            base = [(10, 96), (14, 84)]
        else:
            base = [(10, 90), (11, 60), (15, 104)] if pb % 2 == 0 and v != 1 else [(10, 96), (11, 54), (14, 84), (15, 100)]
        return _h([x for x in base if x[0] < 13] if pb == 8 else base)
    if role == "Bongo":
        if pb < 5:
            return []
        base = [(1, 58), (5, 88), (9, 62), (13, 92)] if pb % 2 == 0 else [(5, 84), (13, 72)]
        return _h([x for x in base if x[0] < 8] if pb == 16 else base)
    if role == "Djembe":
        if pb < 5:
            return []
        base = [(9, 70), (11, 96)] if pb % 2 == 1 else []    # odd bars, when the bongo plays its thin bar
        if pb >= 13:
            base = [(3, 70)] + base
        return _h([x for x in base if x[0] < 8] if pb == 16 else base)
    if role == "Low Drum":
        if pb in (9, 13):
            return _h([(3, 100)])
        if pb == 12:
            return _h([(10, 92), (14, 108)])
        if pb == 16:
            return _h([(2, 96), (6, 104)])
        return []
    if role == "Clave":
        return _h([(0, 96), (3, 76), (6, 88), (10, 92), (12, 80)])
    if role == "Cowbell":
        return _h([(0, 88), (4, 76), (7, 50), (8, 84), (12, 76), (15, 50)])   # with the kick, behind the skins
    if role == "Roll":
        return []
    raise ValueError(f"unknown drum role {role!r}")


def build_hits(role: str, k: int, variant: int = 0) -> list:
    """Hits of bar k (1..8) of a build tail. Level and density rise every bar; no triplets.
    The caller removes everything on beat 4 of bar 8 (the gap before the drop)."""
    ramp = 0.72 + 0.04 * k
    if role == "Kick":
        return _h([(0, 124), (4, 118), (8, 122), (12, 118)])
    if role == "Clap":
        return _h([(4, 110), (12, 114)])
    if role == "Hat":
        if k < 5:
            return _h([(s, _clip(v * ramp)) for s, v in [(2, 76), (6, 70), (10, 80), (14, 70)]])
        return _h([(s, _clip((62 if s % 4 == 0 else 80) * ramp)) for s in range(0, 16, 2)])
    if role == "Shaker":                      # its drop figure, getting louder; the roll and congas carry the 16ths
        return [(p, _clip(vel * ramp), d) for p, vel, d in bar_hits("Shaker", 13, variant)]
    if role == "Conga Hi":
        if k <= 3:
            return _h([(s, _clip(v * ramp)) for s, v in [(2, 56), (3, 62), (6, 92), (7, 106)]])
        return _h([(s, _clip((58 + 3 * s + (12 if s % 4 == 3 else 0)) * ramp)) for s in range(16)])
    if role == "Conga Low":
        if k <= 3:
            return _h([(s, _clip(v * ramp)) for s, v in [(10, 96), (11, 54), (14, 84), (15, 100)]])
        return _h([(s, _clip(v * ramp)) for s, v in [(2, 84), (6, 88), (10, 92), (14, 96)]])
    if role == "Low Drum":
        return _h({6: [(14, 100)], 7: [(10, 96), (12, 104), (14, 110)],
                   8: [(0, 100), (2, 104), (4, 108), (6, 112), (8, 116), (10, 120)]}.get(k, []))
    if role == "Roll":
        if k <= 4:
            pos = [(s * STEP, DUR) for s in range(0, 16, 2)]
        elif k <= 6:
            pos = [(s * STEP, DUR) for s in range(16)]
        elif k == 7:
            pos = [(s * STEP, DUR) for s in range(8)] + [(2.0 + i * 0.125, DUR_32) for i in range(16)]
        else:
            pos = [(i * 0.125, DUR_32) for i in range(24)]
        return [(p, _clip(52 + 72 * ((k - 1) + p / 4.0) / 8.0), d) for p, d in pos]
    # roles without a special build figure keep their fullest normal bar
    return bar_hits(role, 13, variant)
