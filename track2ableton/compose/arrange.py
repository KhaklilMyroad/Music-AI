"""Arrangement: sections, which instrument plays where, and the composer entry point.

Every section starts on a bar of the form 8n+1, so the 8-bar chord loop restarts with each section.
Drops are fixed in advance; a build's last 8 bars rise bar by bar and leave beat 4 of the last bar empty.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace

from . import drums as dr
from . import parts as pt
from .model import BEATS_PER_BAR, Note, Track, bar_start, feel_offset
from .theory import Chord, build_progression, parse_key

# Hook against the bass: a tritone or a major seventh above the bass note is a clash. A semitone above it is not
# listed: on these scales it can only be the b2 over a Phrygian-type root (the b9 of V7(b9)), which is the colour.
CLASH_PCS = (6, 11)
CLASH_MIN = 0.25           # sounding together for longer than this (one 16th) counts as a clash; passing 16ths are allowed
TRACK_ORDER = ["Kick", "Clap", "Wood", "Hat", "Roll", "Shaker", "Conga Hi", "Conga Low", "Bongo", "Djembe", "Low Drum",
               "Clave", "Cowbell", "Sub", "Mid Bass", "Pad", "Hook", "Chant"]
PITCHED = {"Sub": ("bass", "BASS", "Operator: one sine oscillator, no FM, LFO off, Voices = 1, low-pass 110 Hz, sidechain from the kick"),
           "Mid Bass": ("bass", "BASS", "Drift / analog saw+pulse, low-pass ~900 Hz, high-pass 120 Hz, sidechain from the kick"),
           "Pad": ("harmony", "MUSIC", "warm string / analog pad, high-pass ~120 Hz (its lowest notes are around 165 Hz), wide"),
           "Hook": ("hook", "MUSIC", "nylon guitar, marimba or pluck; answers the vocal on beats 3-4"),
           "Chant": ("trigger", "VOCALS", "vocal chops in a Drum Rack / Sampler: C3 (60) = chant on beats 1-2, D3 (62) = shout before a drop")}


@dataclass
class Spec:
    bpm: float = 130.0
    key: str = "A minor"
    progression: str | None = None     # None = the default for the key's mode
    structure: str = "extended"        # extended (200 bars) | radio (96 bars cut from extended + a closing bar) | loop16
    variant: int = 0                   # 0..2 selects alternative wood / bass / hook figures
    swing: float = 57.5                # percent; one swing for every part that plays off-16ths (not kick, clap, roll)
    late_ms: float = 6.0               # skins sit this far behind the beat
    swing_hook: bool = True            # False = that part stays on the straight grid while the percussion swings
    swing_bass: bool = True
    swing_pad: bool = True
    bake_feel: bool = True             # write swing / laid-back timing into the MIDI (clips then need Groove = None)


@dataclass
class Section:
    name: str
    bars: int
    kind: str                                   # intro | groove | break | build | drop | prebreak | outro
    drums: dict = field(default_factory=dict)   # role -> mode | (mode, first bar[, last bar]) inside the section
    sub: object = None
    mid: object = None
    pad: object = None
    hook: object = None
    chant: object = None
    progression: str = "main"
    start: int = 1


@dataclass
class BarInfo:
    section: str
    kind: str
    chord: Chord
    tail: int            # 1..8 inside a build tail, else 0
    roles: frozenset     # tracks planned to play in this bar


@dataclass
class Composition:
    spec: Spec
    sections: list
    tracks: list
    bars: dict           # 1-based bar -> BarInfo
    total_bars: int
    tonic: int
    mode: str

    @property
    def total_beats(self) -> float:
        return self.total_bars * BEATS_PER_BAR

    def track(self, name: str) -> Track:
        return next(t for t in self.tracks if t.name == name)

    def seconds(self, bar: int) -> float:
        return bar_start(bar) * 60.0 / self.spec.bpm


ALL_DRUMS = ["Kick", "Clap", "Wood", "Hat", "Shaker", "Conga Hi", "Conga Low", "Bongo", "Djembe", "Low Drum"]


def _full(*roles, **extra):
    d = {r: "full" for r in roles}
    d.update(extra)
    return d


def extended_sections() -> list:
    build = _full("Kick", "Clap", "Hat", "Shaker", "Conga Hi", "Conga Low", "Low Drum")
    # "sparse" keeps the kick an unbroken four-on-the-floor where a DJ mixes; the kick only drops out at a
    # 16-bar turnaround inside the groove and drops, and on beat 4 before each drop.
    return [
        Section("Intro A", 16, "intro", drums={"Kick": "sparse", "Shaker": "evolve", "Wood": "evolve", "Clave": ("evolve", 9)}),
        Section("Intro B", 16, "intro", drums={"Kick": "sparse", "Clap": "evolve", "Shaker": "full", "Hat": "full",
                                               "Conga Hi": "evolve", "Conga Low": "evolve", "Wood": "full"},
                pad=("stab", 9)),
        # the groove holds back the djembe, the low drum and the shaker's 16ths so the drop has drums to add
        Section("Groove", 16, "groove", drums=_full("Kick", "Clap", "Wood", "Hat", "Conga Hi", "Conga Low",
                                                    Bongo="evolve", Shaker="sparse"),
                sub="offbeat", mid="offbeat", pad="sustain", chant=("teaser", 9)),
        Section("Break 1", 16, "break", drums={"Shaker": "sparse", "Conga Hi": "evolve", "Conga Low": "evolve", "Bongo": "evolve",
                                               "Wood": "evolve", "Djembe": "evolve"},
                pad="sustain", hook="motif", chant="call", progression="break"),
        Section("Build 1", 16, "build", drums=dict(build), mid="offbeat", hook=("motif", 1, 8)),   # the hook rests, then returns on the drop
        Section("Drop 1", 32, "drop", drums=_full(*ALL_DRUMS, Cowbell=("full", 17)),
                sub="rolling", mid="rolling", pad="stab", hook="motif", chant="call"),
        Section("Pre-break", 8, "prebreak", drums={"Kick": "sparse", "Shaker": "sparse", "Conga Hi": "sparse", "Conga Low": "sparse"},
                sub="offbeat"),
        Section("Break 2", 8, "break", pad="sustain", hook="motif", sub="drone", chant="call"),
        Section("Build 2", 16, "build", drums=dict(build), mid="offbeat", hook=("motif", 1, 8)),
        Section("Drop 2", 32, "drop", drums=_full(*ALL_DRUMS, "Cowbell"),
                sub="rolling", mid="rolling", pad="stab", hook=[("motif", 1, 16), ("octave", 17, 32)], chant="call"),
        Section("Outro A", 16, "outro", drums=_full(*ALL_DRUMS, Kick="sparse"), sub=("rolling", 1, 8), mid=("rolling", 1, 8)),
        Section("Outro B", 8, "outro", drums={"Kick": "sparse", "Shaker": "sparse", "Conga Hi": "sparse", "Conga Low": "sparse"}),
    ]


def loop_sections() -> list:
    return [Section("Loop", 16, "drop", drums=_full(*ALL_DRUMS), sub="rolling", mid="rolling", pad="stab", hook="motif", chant="call")]


# radio edit = these bar ranges of the extended mix, in order (name, first source bar, bars); cuts only on 8n+1.
# The second drop is the long one (it carries the octave lift); a closing bar is added after the outro.
RADIO_CUT = [("Groove", 41, 8), ("Break 1", 49, 8), ("Build 1", 73, 8), ("Drop 1", 81, 16), ("Break 2", 121, 8),
             ("Build 2", 137, 8), ("Drop 2", 145, 32), ("Outro", 185, 8)]


def _ranges(v, bars: int) -> list:
    if v is None:
        return []
    items = v if isinstance(v, list) else [v]
    out = []
    for it in items:
        if isinstance(it, str):
            out.append((it, 1, bars))
        else:
            out.append((it[0], it[1], it[2] if len(it) > 2 else bars))
    return out


def _mode_at(v, i: int, bars: int):
    for mode, a, b in _ranges(v, bars):
        if a <= i <= b:
            return mode
    return None


def _phrase_bar(i: int, mode: str) -> int:
    """Bar of the 16-bar drum phrase for bar i (1-based) of a section."""
    if mode == "full":       # the dense half; a light pickup (phrase bar 12) every 8 bars, the full turnaround every 16
        pb = 9 + (i - 1) % 8
        return 12 if pb == 16 and i % 16 else pb
    if mode == "sparse":
        return 1 + (i - 1) % 8
    if mode == "evolve":
        return 1 + (i - 1) % 16
    raise ValueError(f"unknown drum mode {mode!r}")


def compose(spec: Spec | None = None) -> Composition:
    spec = spec or Spec()
    if not 60 <= spec.bpm <= 200:
        raise ValueError("bpm must be between 60 and 200")
    if not 50 <= spec.swing <= 66.7:
        raise ValueError("swing must be between 50 (straight) and 66.7 (triplet)")
    if not 0 <= spec.late_ms <= 30:
        raise ValueError("late_ms must be between 0 and 30")
    if spec.structure == "radio":
        return _with_ending(cut(compose(replace(spec, structure="extended")), RADIO_CUT, spec))
    if spec.structure not in ("extended", "loop16"):
        raise ValueError("structure must be extended, radio or loop16")
    tonic, mode = parse_key(spec.key)
    progs = {"main": build_progression(tonic, mode, spec.progression, "main"),
             "break": build_progression(tonic, mode, spec.progression, "break")}
    sections = extended_sections() if spec.structure == "extended" else loop_sections()
    events = defaultdict(list)       # track -> [(grid beats, pitch, duration, velocity)]
    straight = defaultdict(set)      # track -> bars it plays straight
    bars: dict = {}
    voicing = None
    bar = 1
    for si, sec in enumerate(sections):
        sec.start = bar
        if (sec.start - 1) % 8:
            raise ValueError(f"section {sec.name} does not start on a bar of the form 8n+1")
        prog = progs[sec.progression]
        nxt_first = progs[sections[si + 1].progression][0] if si + 1 < len(sections) else None
        sec_end = bar_start(sec.start + sec.bars)
        for i in range(1, sec.bars + 1):
            b = sec.start + i - 1
            t0 = bar_start(b)
            ci, bic = ((i - 1) // 2) % len(prog), (i - 1) % 2
            chord = prog[ci]
            if i < sec.bars:
                next_chord, nxt_sec, nxt_i = prog[(ci + 1) % len(prog)], sec, i + 1
            else:
                next_chord, nxt_sec, nxt_i = nxt_first, (sections[si + 1] if si + 1 < len(sections) else None), 1
            tail = i - (sec.bars - 8) if sec.kind == "build" and sec.bars >= 8 and i > sec.bars - 8 else 0
            roles = set()
            plan = dict(sec.drums)
            if tail:
                plan["Roll"] = "full"
            for role, v in plan.items():
                m = _mode_at(v, i, sec.bars)
                if not m:
                    continue
                roles.add(role)
                if tail and tail >= dr.TAIL_STRAIGHT.get(role, 99):
                    straight[role].add(b)
                hits = dr.build_hits(role, tail, spec.variant) if tail else dr.bar_hits(role, _phrase_bar(i, m), spec.variant)
                if tail == 8:
                    hits = [h for h in hits if h[0] < 3.0]          # silence on beat 4 before the drop
                events[role] += [(t0 + pos, 60, dur, vel) for pos, vel, dur in hits]
            for name, v, shift in (("Sub", sec.sub, 0), ("Mid Bass", sec.mid, 12)):
                pat = _mode_at(v, i, sec.bars)
                if pat:
                    roles.add(name)
                    # an approach note only leads somewhere if this bass plays in the next bar
                    nv = None if nxt_sec is None else (nxt_sec.sub if name == "Sub" else nxt_sec.mid)
                    goes_on = nxt_sec is not None and _mode_at(nv, nxt_i, nxt_sec.bars) and not (tail == 7)
                    for pos, p, d, vel in pt.bass_bar(pat, chord, next_chord if goes_on else None, bic, spec.variant):
                        events[name].append((t0 + pos, p + shift, min(d, sec_end - (t0 + pos)), vel))
            if bic == 0 or voicing is None:
                voicing = pt.voice_chord(chord, voicing)
            pm = _mode_at(sec.pad, i, sec.bars)
            if pm:
                roles.add("Pad")
                events["Pad"] += [(t0 + pos, p, min(d, sec_end - (t0 + pos)), vel) for pos, p, d, vel in pt.pad_bar(pm, voicing, bic)]
            hm = _mode_at(sec.hook, i, sec.bars)
            if hm:
                roles.add("Hook")
                turn = ci == len(prog) - 1 and bic == 1 and i % 8 == 0      # bar 8 of every 8-bar loop
                events["Hook"] += [(t0 + pos, p, d, vel) for pos, p, d, vel in pt.hook_bar(chord, bic, spec.variant, hm == "octave", turn)]
            for cm, a, _b in _ranges(sec.chant, sec.bars):
                if not a <= i <= _b:
                    continue
                roles.add("Chant")
                if (cm == "call" and bic == 0) or (cm == "teaser" and i == a):
                    events["Chant"].append((t0, pt.CHANT_PITCH, 2.0, 110))
            if tail == 8:
                # beat 4 before the drop belongs to the shout (and the riser): nothing else plays or rings there
                for name in ("Sub", "Mid Bass", "Pad", "Hook"):
                    events[name] = [(g, p, min(d, t0 + 3.0 - g), vel) for g, p, d, vel in events[name] if g < t0 + 3.0]
                roles.add("Chant")
                events["Chant"].append((t0 + 3.0, pt.SHOUT_PITCH, 1.0, 120))
            bars[b] = BarInfo(sec.name, sec.kind, chord, tail, frozenset(roles))
        bar += sec.bars
    total = bar - 1
    events = {k: v for k, v in events.items() if v}
    _resolve_hook_clashes(events, bars)
    return Composition(spec, sections, _clamp(_tracks(events, spec, straight), total * BEATS_PER_BAR), bars, total, tonic, mode)


def _clamp(tracks: list, end: float) -> list:
    """No note rings past the end of the song (a swung hit on the very last 16th would)."""
    for t in tracks:
        t.notes = [n if n.start + n.duration <= end else replace(n, duration=end - n.start) for n in t.notes]
    return tracks


def _clash_overlap(g: float, p: int, d: float, bass: list) -> float:
    return sum(max(0.0, min(g + d, bg + bd) - max(g, bg)) for bg, bp, bd, _ in bass if (p - bp) % 12 in CLASH_PCS)


def _resolve_hook_clashes(events: dict, bars: dict) -> None:
    """Move a hook note that holds a tritone / major 7th against the sub or mid bass to the nearest chord tone
    that is neither the note before nor the note after it. An octave double moves with its lower note."""
    by_bar = defaultdict(list)
    seen = set()
    for name in ("Sub", "Mid Bass"):                 # the mid bass doubles the sub an octave up: count each moment once
        for g, p, d, vel in events.get(name, []):
            if (g, p % 12) not in seen:
                seen.add((g, p % 12))
                by_bar[int(g // BEATS_PER_BAR) + 1].append((g, p, d, vel))
    groups = defaultdict(list)                       # grid -> the notes that start there (1, or 2 with the octave double)
    for ev in events.get("Hook", []):
        groups[ev[0]].append(ev)
    grids = sorted(groups)
    low = [min(p for _, p, _, _ in groups[g]) for g in grids]
    out = []
    for k, g in enumerate(grids):
        b = int(g // BEATS_PER_BAR) + 1
        near = by_bar.get(b, []) + by_bar.get(b - 1, [])
        d = max(x[2] for x in groups[g])
        shift = 0
        if _clash_overlap(g, low[k], d, near) > CLASH_MIN:
            avoid = {low[k - 1] if k else None, low[k + 1] if k + 1 < len(low) else None}
            shift = pt.nearest_chord_tone(low[k], bars[b].chord, avoid) - low[k]
            low[k] += shift
        out += [(gg, p + shift, dd, vel) for gg, p, dd, vel in groups[g]]
    if out:
        events["Hook"] = out


def _tracks(events: dict, spec: Spec, straight: dict) -> list:
    late = spec.late_ms / 1000.0 * spec.bpm / 60.0 if spec.bake_feel else 0.0
    out = []
    for name in TRACK_ORDER:
        if name not in events:
            continue
        if name in dr.GROUP:
            role, group, hint = "drum", dr.GROUP[name], dr.HINT[name]
            swing = name not in dr.STRAIGHT
        else:
            role, group, hint = PITCHED[name]
            swing = (name == "Hook" and spec.swing_hook) or (role == "bass" and spec.swing_bass) or (name == "Pad" and spec.swing_pad)
        late_b = late if name in dr.SKINS else 0.0
        st = frozenset(straight.get(name, ()))
        notes = []
        for g, p, d, vel in sorted(set(events[name])):
            sw = swing and int(g // BEATS_PER_BAR) + 1 not in st
            sw_off = feel_offset(g, sw, spec.swing, 0.0)
            off = sw_off + late_b if spec.bake_feel else 0.0
            # swing delays the onset, not the release: a swung hit must not ring into the next 16th.
            # In straight mode the length is shortened as well (in every bar, because a groove applied in Live
            # swings the whole clip), so the hits cannot overlap once the groove moves them.
            shorten = sw_off if spec.bake_feel else feel_offset(g, swing, spec.swing, 0.0)
            notes.append(Note(p, g + off, max(0.03, d - shorten), vel, g))
        out.append(Track(name, role, group, notes, swing, spec.late_ms if name in dr.SKINS else 0.0, hint, dr.GM_PITCH.get(name), st))
    return out


def cut(src: Composition, segments: list, spec: Spec | None = None) -> Composition:
    """New composition made of whole-bar ranges of `src` (name, first source bar, bars). Used for the radio edit."""
    sections, bars, moved, straight = [], {}, defaultdict(list), defaultdict(set)
    dst = 1
    for name, first, n in segments:
        if (first - 1) % 8 or n % 8:
            raise ValueError("cuts must start on a bar of the form 8n+1 and be a multiple of 8 bars long")
        lo, hi, shift = bar_start(first), bar_start(first + n), bar_start(dst) - bar_start(first)
        for t in src.tracks:
            for nt in t.notes:
                if lo <= nt.grid < hi:
                    moved[t.name].append(Note(nt.pitch, nt.start + shift, min(nt.duration, hi - nt.grid), nt.velocity, nt.grid + shift))
        for k in range(n):
            bars[dst + k] = src.bars[first + k]
            for t in src.tracks:
                if first + k in t.straight_bars:
                    straight[t.name].add(dst + k)
        sections.append(Section(name, n, src.bars[first].kind, start=dst))
        dst += n
    # a bass approach note was written towards the next bar of the source; at a seam where the bass does not go on,
    # it would hang, so it goes back to the root of its bar
    for name, shift in (("Sub", 0), ("Mid Bass", 12)):
        ns = moved.get(name, [])
        for s in sections:
            last = s.start + s.bars - 1
            nxt_lo = bar_start(last + 1)
            if any(nxt_lo <= x.grid < nxt_lo + BEATS_PER_BAR for x in ns):
                continue
            root = pt.sub_pitch(bars[last].chord.root_pc) + shift
            moved[name] = ns = [replace(x, pitch=root) if x.grid == nxt_lo - 0.25 and x.pitch != root else x for x in ns]
    tracks = [replace(t, notes=sorted(moved[t.name], key=lambda x: (x.grid, x.pitch)), straight_bars=frozenset(straight[t.name]))
              for t in src.tracks if moved[t.name]]
    return Composition(spec or src.spec, sections, _clamp(tracks, bar_start(dst)), bars, dst - 1, src.tonic, src.mode)


def _with_ending(comp: Composition) -> Composition:
    """One closing bar so an edit does not stop on a pickup: the kick and the tonic chord on beat 1, left to ring."""
    b = comp.total_bars + 1
    t0 = bar_start(b)
    chord = build_progression(comp.tonic, comp.mode, comp.spec.progression, "main")[0]
    add = {"Kick": [Note(60, t0, 0.2, 124, t0)], "Pad": [Note(p, t0, 3.5, 84, t0) for p in pt.voice_chord(chord, None)]}
    have = {t.name for t in comp.tracks}
    tracks = [replace(t, notes=t.notes + add.get(t.name, [])) for t in comp.tracks]
    bars = dict(comp.bars)
    bars[b] = BarInfo("End", "outro", chord, 0, frozenset(n for n in add if n in have))
    return replace(comp, tracks=tracks, bars=bars, sections=comp.sections + [Section("End", 1, "outro", start=b)], total_bars=b)
