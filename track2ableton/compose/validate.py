"""Checks on a finished composition. They verify what the notes say (timing, harmony, structure);
they cannot tell whether the result sounds good. That needs ears."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from . import parts as pt
from .arrange import CLASH_MIN, CLASH_PCS, Composition
from .model import BEATS_PER_BAR, bar_start, feel_offset

EPS = 1e-9


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def _bar(grid: float) -> int:
    return int(grid // BEATS_PER_BAR) + 1


def validate(comp: Composition) -> list:
    sp = comp.spec
    late = sp.late_ms / 1000.0 * sp.bpm / 60.0
    T = {t.name: t for t in comp.tracks}
    drums = [t for t in comp.tracks if t.role == "drum"]
    out = []

    def add(name, bad, good):
        bad = list(bad)
        out.append(Check(name, not bad, good if not bad else f"{len(bad)} problem(s), first: {bad[0]}"))

    # 1. every note sits where the grid + planned feel says
    bad = []
    for t in comp.tracks:
        res = 0.125 if t.name == "Roll" else 0.25
        for n in t.notes:
            sw = t.swing and _bar(n.grid) not in t.straight_bars
            exp = feel_offset(n.grid, sw, sp.swing, late if t.late_ms else 0.0) if sp.bake_feel else 0.0
            if abs(n.start - n.grid - exp) > EPS or abs(n.grid / res - round(n.grid / res)) > EPS:
                bad.append(f"{t.name} @ beat {n.grid}")
    add("timing: every note on the grid plus its planned swing / laid-back offset", bad, f"{sum(len(t.notes) for t in comp.tracks)} notes")

    bad = [f"{nm} @ {n.start}" for nm in ("Kick", "Clap") if nm in T for n in T[nm].notes
           if abs(n.start / 0.25 - round(n.start / 0.25)) > EPS]
    add("kick and clap exactly on the straight grid", bad, "0 ms offset")

    kicks = {round(n.grid, 6) for n in T["Kick"].notes} if "Kick" in T else set()
    bad = [f"{nm} @ beat {n.grid}" for nm in ("Sub", "Mid Bass") if nm in T for n in T[nm].notes if round(n.grid, 6) in kicks]
    add("bass never starts together with a kick", bad, "bass plays between the kicks")

    bad = []
    for nm in ("Sub", "Mid Bass"):
        ns = sorted(T[nm].notes, key=lambda n: n.start) if nm in T else []
        bad += [f"{nm} @ beat {a.grid}" for a, b in zip(ns, ns[1:]) if b.start < a.start + a.duration - EPS]
    add("bass is monophonic (no overlapping notes)", bad, "one note at a time")

    bad = []
    for t in comp.tracks:
        by = defaultdict(list)
        for n in t.notes:
            by[n.pitch].append(n)
        for ns in by.values():
            ns.sort(key=lambda n: n.start)
            bad += [f"{t.name} @ beat {a.grid}" for a, b in zip(ns, ns[1:]) if b.start < a.start + a.duration - EPS]
    add("no note overlaps the next note of the same pitch", bad, "clean note-offs")

    bad = [f"{t.name} {n.pitch} in bar {_bar(n.grid)}" for t in comp.tracks if t.role in ("bass", "harmony", "hook")
           for n in t.notes if n.pitch % 12 not in comp.bars[_bar(n.grid)].chord.allowed]
    add("harmony: every pitched note belongs to the scale or chord of its bar", bad, "all in key")

    rng = {"Sub": (pt.SUB_LO, pt.SUB_HI + 4), "Mid Bass": (pt.SUB_LO + 12, pt.SUB_HI + 16), "Pad": (pt.PAD_LO, 84), "Hook": (57, 96)}
    bad = [f"{nm} {n.pitch}" for nm, (lo, hi) in rng.items() if nm in T for n in T[nm].notes if not lo <= n.pitch <= hi]
    add("registers: sub 41-98 Hz, pad above 165 Hz, hook in the lead range", bad, "all in range")

    bad = []
    if "Hook" in T and "Sub" in T:
        by_bar = defaultdict(list)
        for n in T["Sub"].notes:
            by_bar[_bar(n.grid)].append(n)
        for h in T["Hook"].notes:
            b = _bar(h.grid)
            ov = sum(max(0.0, min(h.grid + h.duration, s.grid + s.duration) - max(h.grid, s.grid))
                     for s in by_bar.get(b, []) + by_bar.get(b - 1, []) if (h.pitch - s.pitch) % 12 in CLASH_PCS)
            if ov > CLASH_MIN:
                bad.append(f"bar {b} hook {h.pitch}")
    add("hook never holds a minor 2nd / tritone / major 7th against the bass for longer than a 16th", bad, "no clashes")

    bad = [f"{s.name} starts on bar {s.start}" for s in comp.sections if (s.start - 1) % 8]
    add("every section starts on a bar of the form 8n+1", bad, f"{len(comp.sections)} sections")

    bad = []
    for t in comp.tracks:
        seen = set()
        for n in t.notes:
            b = _bar(n.grid)
            if t.name not in comp.bars[b].roles and b not in seen:
                seen.add(b)
                bad.append(f"{t.name} plays in bar {b} ({comp.bars[b].section}) where it is not planned")
    for s in comp.sections:
        planned = set().union(*(comp.bars[b].roles for b in range(s.start, s.start + s.bars)))
        lo, hi = bar_start(s.start), bar_start(s.start + s.bars)
        actual = {t.name for t in comp.tracks if any(lo <= n.grid < hi for n in t.notes)}
        bad += [f"{nm} is planned in {s.name} but silent" for nm in sorted(planned - actual)]
    add("arrangement: each section contains exactly the planned instruments", bad, "matches the plan")

    bad, tails = [], sorted(b for b, info in comp.bars.items() if info.tail)
    energy = {}
    for b in tails:
        lo, k = bar_start(b), comp.bars[b].tail
        energy[b] = sum(n.velocity for t in drums for n in t.notes if lo <= n.grid < lo + 4) / (3.0 if k == 8 else 4.0)
        if k > 1 and b - 1 in energy and energy[b] <= energy[b - 1]:
            bad.append(f"bar {b} ({energy[b]:.0f}) is not above bar {b - 1} ({energy[b - 1]:.0f})")
    add("builds: drum energy per played beat rises in every bar of the last 8", bad, f"{len(tails) // 8} build(s)")

    bad = []
    for b in tails:
        lo = bar_start(b)
        if comp.bars[b].tail == 8:
            bad += [f"{t.name} on beat 4 of bar {b}" for t in comp.tracks if t.role in ("drum", "bass")
                    and any(lo + 3.0 <= n.grid < lo + 4.0 for n in t.notes)]
        if "Sub" in T and any(lo <= n.grid < lo + 4 for n in T["Sub"].notes):
            bad.append(f"sub plays in build bar {b}")
    for s in comp.sections:
        if s.kind == "drop" and "Sub" in comp.bars[s.start].roles and "Sub" in T:
            lo = bar_start(s.start)
            if not any(lo <= n.grid < lo + 4 for n in T["Sub"].notes):
                bad.append(f"no sub in the first bar of {s.name}")
    add("drops: beat 4 before a drop is empty, the sub is out for the build's last 8 bars and back on the drop", bad, "ok")

    bad = [f"bar {_bar(n.grid)}" for n in T["Hook"].notes if n.grid % 4 < 2.0 - EPS] if "Hook" in T else []
    add("hook stays on beats 3-4, leaving beats 1-2 to the vocal", bad, "call and response")

    end = comp.total_beats
    bad = [f"{t.name} @ beat {n.grid}" for t in comp.tracks for n in t.notes
           if n.start < 0 or n.start + n.duration > end + EPS or n.duration <= 0 or not 1 <= n.velocity <= 127 or not 0 <= n.pitch <= 127]
    add("every note is inside the song with a valid length, pitch and velocity", bad, f"{comp.total_bars} bars")
    return out


def all_ok(checks: list) -> bool:
    return all(c.ok for c in checks)
