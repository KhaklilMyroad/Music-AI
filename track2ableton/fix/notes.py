"""Repair transcribed notes with the evidence the song itself gives.

A transcription of a loop-based track hears every repetition a little differently: a hit missed here, a ghost note
there, an octave error, a note a semitone off. The song says what is right: a figure that returns bar after bar is
the figure, and what appears in one repetition only is suspect. Every repair here is a vote among repetitions of
the same bar, not a rule about what music should be. Where there are fewer than three repetitions to vote with,
the notes stay as heard and the report counts them as unverified.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from ..transcribe import Note

GRID = 0.25              # a 16th, in beats
MIN_AGREE = 0.35         # bars one loop apart must share this much before the part counts as looped
PEER_SIM = 0.4           # a repetition votes on the rhythm only if it shares this much with the bar being repaired
PITCH_SIM = 0.6          # stricter where pitches count: Am and F share two notes of three and are not the same bar
MIN_PEERS = 3            # a vote needs the bar and at least two repetitions
NEAR = 2                 # repetitions taken on each side of the bar
RECURS = 3               # a note at the same place in the bar this often is intended, whatever the scale says
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass
class Report:
    raw: int = 0
    fixed: int = 0
    removed: int = 0
    added: int = 0
    guessed: int = 0             # of the added notes: pitch copied from the note next to it, no repetition had one
    repitched: int = 0
    folded: int = 0              # isolated octave errors
    snapped: int = 0             # short, rare out-of-scale notes moved a semitone
    loop_bars: int = 0           # the rhythm repeats every this many bars (0: no loop found, nothing was voted)
    pitch_loop_bars: int = 0
    agreement: float = 0.0       # how alike bars one loop apart were before the repair (0-1)
    bars: int = 0                # bars with notes
    voted: int = 0               # of those: bars with at least three repetitions to vote with
    turns_kept: int = 0          # phrase-end bars whose last two beats differ from the loop and were left as heard
    outside_kept: list[str] = field(default_factory=list)   # out-of-scale pitch classes left in, with why

    @property
    def changed(self) -> int:
        return self.removed + self.added + self.repitched + self.folded + self.snapped


def _step(x: float) -> int:
    return int(round(x / GRID))


def _jaccard(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if (a or b) else 1.0


def loop_length(ev: dict[int, frozenset], candidates=(1, 2, 4, 8, 16)) -> tuple[int, float]:
    """After how many bars the part repeats, and how alike bars that far apart are (0-1). The loop with the best
    agreement wins, the shorter one on a tie: a loop that is too short would flatten what changes inside the phrase."""
    scores = {}
    for L in candidates:
        pairs = [_jaccard(ev[b], ev[b + L]) for b in ev if b + L in ev]
        if len(pairs) >= 2 and len(ev) >= MIN_PEERS * L:
            scores[L] = float(np.mean(pairs))
    if not scores or max(scores.values()) < MIN_AGREE:
        return 0, max(scores.values(), default=0.0)
    best = max(scores.values())
    L = min(l for l, sc in scores.items() if sc >= best - 0.02)
    return L, scores[L]


def _peers(ev: dict[int, frozenset], b: int, L: int, sim: float = PEER_SIM) -> list[int]:
    """The bar itself and its nearest repetitions that resemble it: two before and two after where the song has
    them. Voting among the nearest keeps what a whole section does differently from another section."""
    like = sorted(p for p in ev if p != b and (p - b) % L == 0 and _jaccard(ev[b], ev[p]) >= sim)
    before, after = [p for p in like if p < b], [p for p in like if p > b]
    take_b = min(len(before), max(NEAR, 2 * NEAR - len(after)))
    take_a = min(len(after), 2 * NEAR - take_b)
    return before[len(before) - take_b:] + [b] + after[:take_a]


def _wins(c: int, n: int, own: bool, light: bool) -> bool:
    """Does an event that `c` of the `n` voters have (the bar itself included) belong in the bar? Normally a strict
    majority decides. `light` changes a bar only when its repetitions are unanimous against it."""
    if not light:
        return 2 * c > n
    return c > 1 if own else c == n - 1


def vote(ev: dict[int, frozenset], L: int, turns: set[int], half: int, step_of: Callable = lambda e: e,
         sim: float = PEER_SIM, light: bool = False) -> tuple[dict, int, int]:
    """Per bar, the events the bar and its nearest repetitions agree on. In a phrase-end bar the last two beats
    are left as heard: that is where fills and the gap before a drop live.
    Returns (events, bars voted, turns kept)."""
    out, voted, kept = {}, 0, 0
    for b, own in ev.items():
        peers = _peers(ev, b, L, sim)
        if len(peers) < MIN_PEERS:
            out[b] = own
            continue
        voted += 1
        count = Counter(e for p in peers for e in ev[p])
        maj = frozenset(e for e, c in count.items() if _wins(c, len(peers), e in own, light))
        if b in turns:
            tail_own = frozenset(e for e in own if step_of(e) >= half)
            kept += tail_own != frozenset(e for e in maj if step_of(e) >= half)
            maj = frozenset(e for e in maj if step_of(e) < half) | tail_own
        out[b] = maj
    return out, voted, kept


def _clean(notes: list[Note]) -> list[Note]:
    """On the 16th grid, one note per (start, pitch), the louder one kept."""
    best: dict[tuple[int, int], Note] = {}
    for n in notes:
        s = _step(n.start)
        if s < 0:
            continue
        m = Note(int(n.pitch), s * GRID, max(GRID, _step(n.duration) * GRID), int(n.velocity))
        if (s, m.pitch) not in best or m.velocity > best[(s, m.pitch)].velocity:
            best[(s, m.pitch)] = m
    return sorted(best.values(), key=lambda n: (n.start, n.pitch))


def _median(xs, default):
    return float(np.median(xs)) if len(xs) else default


# ------------------------------------------------------------------------------------------- drums

def repair_drums(notes: list[Note], bpb: int, turns: set[int], light: bool = False) -> tuple[list[Note], dict[int, Report]]:
    """Each kit piece (MIDI pitch) is voted on its own. Returns the notes and one report per pitch."""
    spb = bpb * 4
    out: list[Note] = []
    reports: dict[int, Report] = {}
    notes = _clean(notes)
    for pitch in sorted({n.pitch for n in notes}):
        mine = [n for n in notes if n.pitch == pitch]
        at = {_step(n.start): n for n in mine}
        ev: dict[int, set] = {}
        for s in at:
            ev.setdefault(s // spb, set()).add(s % spb)
        ev = {b: frozenset(v) for b, v in ev.items()}
        rep = Report(raw=len(mine), bars=len(ev))
        rep.loop_bars, rep.agreement = loop_length(ev)
        if not rep.loop_bars:
            out += mine
            rep.fixed = len(mine)
            reports[pitch] = rep
            continue
        voted, rep.voted, rep.turns_kept = vote(ev, rep.loop_bars, turns, spb // 2, light=light)
        for b, steps in voted.items():
            peers = _peers(ev, b, rep.loop_bars)
            for s in steps:
                if b * spb + s in at:
                    out.append(at[b * spb + s])
                else:
                    vel = _median([at[p * spb + s].velocity for p in peers if p * spb + s in at], 90)
                    out.append(Note(pitch, (b * spb + s) * GRID, GRID, int(vel)))
                    rep.added += 1
            rep.removed += len(ev[b] - steps)
        rep.fixed = rep.raw + rep.added - rep.removed
        reports[pitch] = rep
    return sorted(out, key=lambda n: (n.start, n.pitch)), reports


# ------------------------------------------------------------------------------------------- pitched

def _recurring(notes: list[Note], spb: int) -> set[tuple[int, int]]:
    count = Counter((_step(n.start) % spb, n.pitch) for n in notes)
    return {k for k, c in count.items() if c >= RECURS}


def _fold_octaves(notes: list[Note], spb: int, rep: Report) -> None:
    """A note about an octave away from the notes around it, and not a recurring figure, is an octave error."""
    keep = _recurring(notes, spb)
    pitches = [n.pitch for n in notes]
    for i, n in enumerate(notes):
        near = pitches[max(0, i - 3): i] + pitches[i + 1: i + 4]
        if len(near) < 4 or (_step(n.start) % spb, n.pitch) in keep:
            continue
        d = n.pitch - float(np.median(near))
        k = int(round(d / 12))
        if abs(d) >= 10 and k and abs(d - 12 * k) <= 5:
            n.pitch -= 12 * k
            rep.folded += 1


def _snap_outside(notes: list[Note], spb: int, allowed: Callable[[int, float], bool], rep: Report) -> None:
    """A short note outside the scale and the chord, that does not recur, moves to the neighbouring semitone the
    notes around it point to. Long or recurring ones stay, and are reported."""
    keep = _recurring(notes, spb)
    total = sum(n.duration for n in notes) or 1.0
    share = Counter()
    for n in notes:
        share[n.pitch % 12] += n.duration / total
    kept = Counter()
    for i, n in enumerate(notes):
        pc = n.pitch % 12
        if allowed(pc, n.start) or share[pc] >= 0.04:
            continue
        if (_step(n.start) % spb, n.pitch) in keep or n.duration > 0.5:
            kept[pc] += 1
            continue
        around = [m.pitch for m in notes[max(0, i - 1): i] + notes[i + 1: i + 2]]
        options = [p for p in (n.pitch - 1, n.pitch + 1) if allowed(p % 12, n.start)]
        if not options:
            kept[pc] += 1
            continue
        n.pitch = min(options, key=lambda p: (min((abs(p - a) for a in around), default=0), p))
        rep.snapped += 1
    rep.outside_kept = [f"{NAMES[pc]} x{c}" for pc, c in sorted(kept.items())]


def repair_mono(notes: list[Note], bpb: int, turns: set[int], allowed: Callable[[int, float], bool],
                light: bool = False) -> tuple[list[Note], Report]:
    """A line that plays one note at a time (bass, lead). The rhythm is voted among bars one rhythm-loop apart, which
    are many; the pitch of each onset among bars one pitch-loop apart, which follow the chords and are fewer."""
    spb = bpb * 4
    raw = _clean(notes)
    one: dict[int, Note] = {}
    for n in raw:                                   # one note per onset: the louder
        s = _step(n.start)
        if s not in one or n.velocity > one[s].velocity:
            one[s] = n
    notes = [one[s] for s in sorted(one)]
    rep = Report(raw=len(raw))
    rep.removed = len(raw) - len(notes)
    _fold_octaves(notes, spb, rep)
    _snap_outside(notes, spb, allowed, rep)
    at = {_step(n.start): n for n in notes}
    ev_r: dict[int, set] = {}
    ev_p: dict[int, set] = {}
    for s, n in at.items():
        ev_r.setdefault(s // spb, set()).add(s % spb)
        ev_p.setdefault(s // spb, set()).add((s % spb, n.pitch))
    ev_r = {b: frozenset(v) for b, v in ev_r.items()}
    ev_p = {b: frozenset(v) for b, v in ev_p.items()}
    rep.bars = len(ev_r)
    rep.loop_bars, rep.agreement = loop_length(ev_r)
    rep.pitch_loop_bars, _ = loop_length(ev_p)
    if rep.loop_bars:
        steps, rep.voted, rep.turns_kept = vote(ev_r, rep.loop_bars, turns, spb // 2, light=light)
    else:
        steps = dict(ev_r)
    out: list[Note] = []
    for b in sorted(steps):
        peers_r = _peers(ev_r, b, rep.loop_bars) if rep.loop_bars else [b]
        peers_p = _peers(ev_p, b, rep.pitch_loop_bars) if rep.pitch_loop_bars else [b]
        rep.removed += len(ev_r[b] - steps[b])
        line: list[Note] = []
        for s in sorted(steps[b]):
            own = at.get(b * spb + s)
            heard = [at[p * spb + s].pitch for p in peers_p if p * spb + s in at]
            top, n_top = Counter(heard).most_common(1)[0] if heard else (None, 0)
            if own is not None:
                sure = n_top == len(heard) - 1 if light else 2 * n_top > len(heard)
                if len(heard) >= MIN_PEERS and sure and top != own.pitch and not (b in turns and s >= spb // 2):
                    own.pitch = top
                    rep.repitched += 1
                line.append(own)
                continue
            if heard and 2 * n_top > len(heard):
                pitch = top
            elif line:
                pitch = line[-1].pitch              # no repetition has a pitch here: the note before it in the bar
                rep.guessed += 1
            else:
                continue
            src = [at[p * spb + s] for p in peers_r + peers_p if p * spb + s in at]
            line.append(Note(pitch, (b * spb + s) * GRID, _median([n.duration for n in src], GRID),
                             int(_median([n.velocity for n in src], 90))))
            rep.added += 1
        out += line
    out.sort(key=lambda n: n.start)
    for a, b_ in zip(out, out[1:]):                 # one note at a time
        a.duration = max(GRID, min(a.duration, b_.start - a.start))
    rep.fixed = len(out)
    return out, rep


def repair_poly(notes: list[Note], bpb: int, turns: set[int], allowed: Callable[[int, float], bool],
                light: bool = False) -> tuple[list[Note], Report]:
    """Chords and layered parts: notes are voted as (place in the bar, pitch) among bars one loop apart."""
    spb = bpb * 4
    notes = _clean(notes)
    rep = Report(raw=len(notes))
    _snap_outside(notes, spb, allowed, rep)
    notes = _clean(notes)
    at = {(_step(n.start), n.pitch): n for n in notes}
    ev: dict[int, set] = {}
    for (s, p) in at:
        ev.setdefault(s // spb, set()).add((s % spb, p))
    ev = {b: frozenset(v) for b, v in ev.items()}
    rep.bars = len(ev)
    rep.loop_bars, rep.agreement = loop_length(ev)
    rep.pitch_loop_bars = rep.loop_bars
    if not rep.loop_bars:
        rep.fixed = len(notes)
        return notes, rep
    voted, rep.voted, rep.turns_kept = vote(ev, rep.loop_bars, turns, spb // 2, lambda e: e[0], PITCH_SIM, light)
    out: list[Note] = []
    for b, events in voted.items():
        peers = _peers(ev, b, rep.loop_bars, PITCH_SIM)
        for (s, p) in events:
            if (b * spb + s, p) in at:
                out.append(at[(b * spb + s, p)])
            else:
                src = [at[(q * spb + s, p)] for q in peers if (q * spb + s, p) in at]
                out.append(Note(p, (b * spb + s) * GRID, _median([n.duration for n in src], GRID),
                                int(_median([n.velocity for n in src], 80))))
                rep.added += 1
        rep.removed += len(ev[b] - events)
    out.sort(key=lambda n: (n.start, n.pitch))
    last: dict[int, Note] = {}
    for n in out:                                   # the same pitch never overlaps itself
        if n.pitch in last and last[n.pitch].start + last[n.pitch].duration > n.start:
            last[n.pitch].duration = max(GRID, n.start - last[n.pitch].start)
        last[n.pitch] = n
    rep.fixed = len(out)
    return out, rep


# ------------------------------------------------------------------------------------------- harmony

@dataclass
class Progression:
    loop_bars: int                    # 0: no repeating progression found
    chords: list[str]                 # one name per half bar of the loop
    share: float                      # how much of the song's half bars agree with the loop
    fixed: list[tuple[int, str]]      # per half bar of the song: (root pitch class or -1, quality)
    changed: int                      # half bars whose chord was replaced by the loop's


def chord_loop(seq: list[tuple[int, str]], tones: Callable[[int, str], set[int]], name: Callable[[int, str], str]) -> Progression:
    """seq: the detected chord of every half bar, (root, quality), root -1 for none. The progression is voted per
    place in the loop; a detected chord gives way to the loop's only when the two share at least two notes
    (the same harmony heard differently). A chord that shares fewer is a real change and stays."""
    n = len(seq)
    scores = {}
    for L in (1, 2, 4, 8, 16):
        pairs = [seq[i] == seq[i + 2 * L] for i in range(n - 2 * L) if seq[i][0] >= 0 and seq[i + 2 * L][0] >= 0]
        if len(pairs) >= 4:
            scores[L] = float(np.mean(pairs))
    if not scores or max(scores.values()) < MIN_AGREE:
        return Progression(0, [], max(scores.values(), default=0.0), list(seq), 0)
    best = max(scores.values())
    L = min(l for l, s in scores.items() if s >= 0.92 * best)
    loop = []
    for ph in range(2 * L):
        c = Counter(seq[i] for i in range(ph, n, 2 * L) if seq[i][0] >= 0)
        loop.append(c.most_common(1)[0][0] if c else (-1, ""))
    fixed, changed, agree = [], 0, 0
    for i, c in enumerate(seq):
        want = loop[i % (2 * L)]
        if c[0] < 0 or want[0] < 0 or c == want:
            fixed.append(c)
            agree += c == want and c[0] >= 0
        elif len(tones(*c) & tones(*want)) >= 2:
            fixed.append(want)
            changed += 1
            agree += 1
        else:
            fixed.append(c)
    sounding = sum(1 for c in seq if c[0] >= 0) or 1
    return Progression(L, [name(*c) if c[0] >= 0 else "N.C." for c in loop], agree / sounding, fixed, changed)
