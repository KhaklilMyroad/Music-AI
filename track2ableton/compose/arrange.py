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

CLASH_PCS = (1, 6, 11)     # minor second, tritone, major seventh against the bass
CLASH_MIN = 0.25           # sounding together for longer than this (one 16th) counts as a clash; passing 16ths are allowed
TRACK_ORDER = ["Kick", "Clap", "Wood", "Hat", "Roll", "Shaker", "Conga Hi", "Conga Low", "Bongo", "Djembe", "Low Drum",
               "Clave", "Cowbell", "Sub", "Mid Bass", "Pad", "Hook", "Chant"]
PITCHED = {"Sub": ("bass", "BASS", "Operator: one sine oscillator, no FM, LFO off, Voices = 1, low-pass 110 Hz, sidechain from the kick"),
           "Mid Bass": ("bass", "BASS", "Drift / analog saw+pulse, low-pass ~900 Hz, high-pass 120 Hz, sidechain from the kick"),
           "Pad": ("harmony", "MUSIC", "warm string / analog pad, high-pass 150-180 Hz, wide"),
           "Hook": ("hook", "MUSIC", "nylon guitar, marimba or pluck; answers the vocal on beats 3-4"),
           "Chant": ("trigger", "VOCALS", "vocal chops in a Drum Rack / Sampler: C3 (60) = chant on beats 1-2, D3 (62) = shout before a drop")}


@dataclass
class Spec:
    bpm: float = 130.0
    key: str = "A minor"
    progression: str | None = None     # None = the default for the key's mode
    structure: str = "extended"        # extended (200 bars) | radio (96 bars, cut from extended) | loop16
    variant: int = 0                   # 0..2 selects alternative wood / bass / hook figures
    swing: float = 57.5                # percent, applied to percussion off-16ths
    late_ms: float = 6.0               # skins sit this far behind the beat
    swing_hook: bool = False
    swing_bass: bool = False
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
    return [
        Section("Intro A", 16, "intro", drums={"Kick": "evolve", "Shaker": "evolve", "Hat": "evolve", "Clave": ("evolve", 9)}),
        Section("Intro B", 16, "intro", drums={"Kick": "full", "Clap": "evolve", "Shaker": "full", "Hat": "full",
                                               "Conga Hi": "evolve", "Conga Low": "evolve", "Wood": "evolve"},
                pad=("stab", 9)),
        Section("Groove", 16, "groove", drums=_full("Kick", "Clap", "Wood", "Hat", "Shaker", "Conga Hi", "Conga Low", "Low Drum",
                                                    Bongo="evolve", Djembe="evolve"),
                sub="offbeat", mid="offbeat", pad="sustain", chant=("teaser", 9)),
        Section("Break 1", 16, "break", drums={"Shaker": "sparse", "Conga Hi": "evolve", "Conga Low": "evolve", "Bongo": "evolve",
                                               "Wood": "evolve", "Djembe": "evolve"},
                pad="sustain", hook="motif", chant="call", progression="break"),
        Section("Build 1", 16, "build", drums=dict(build), mid="offbeat", hook="motif"),
        Section("Drop 1", 32, "drop", drums=_full(*ALL_DRUMS, Cowbell=("full", 17)),
                sub="rolling", mid="rolling", pad="stab", hook="motif", chant="call"),
        Section("Pre-break", 8, "prebreak", drums={"Kick": "sparse", "Shaker": "sparse", "Conga Hi": "sparse", "Conga Low": "sparse"},
                sub="offbeat"),
        Section("Break 2", 8, "break", pad="sustain", hook="motif", sub="drone", chant="call"),
        Section("Build 2", 16, "build", drums=dict(build), sub=("offbeat", 1, 8), mid="offbeat", hook="motif"),
        Section("Drop 2", 32, "drop", drums=_full(*ALL_DRUMS, "Cowbell"),
                sub="rolling", mid="rolling", pad="stab", hook=[("motif", 1, 16), ("octave", 17, 32)], chant="call"),
        Section("Outro A", 16, "outro", drums=_full(*ALL_DRUMS), sub=("rolling", 1, 8), mid=("rolling", 1, 8)),
        Section("Outro B", 8, "outro", drums=_full("Kick", "Hat", "Shaker")),
    ]


def loop_sections() -> list:
    return [Section("Loop", 16, "drop", drums=_full(*ALL_DRUMS), sub="rolling", mid="rolling", pad="stab", hook="motif", chant="call")]


# radio edit = these bar ranges of the extended mix, in order (name, first source bar, bars); cuts only on 8n+1
RADIO_CUT = [("Groove", 33, 16), ("Break 1", 49, 8), ("Build 1", 73, 8), ("Drop 1", 81, 32), ("Break 2", 121, 8),
             ("Build 2", 137, 8), ("Drop 2", 145, 8), ("Outro", 185, 8)]


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
    if mode == "full":       # always the dense half, with a turnaround every 8 bars
        return 9 + (i - 1) % 8
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
    if spec.structure == "radio":
        return cut(compose(replace(spec, structure="extended")), RADIO_CUT, spec)
    if spec.structure not in ("extended", "loop16"):
        raise ValueError("structure must be extended, radio or loop16")
    tonic, mode = parse_key(spec.key)
    progs = {"main": build_progression(tonic, mode, spec.progression, "main"),
             "break": build_progression(tonic, mode, spec.progression, "break")}
    sections = extended_sections() if spec.structure == "extended" else loop_sections()
    events = defaultdict(list)       # track -> [(grid beats, pitch, duration, velocity)]
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
                next_chord = prog[(ci + 1) % len(prog)]
            else:
                next_chord = nxt_first or chord
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
                hits = dr.build_hits(role, tail, spec.variant) if tail else dr.bar_hits(role, _phrase_bar(i, m), spec.variant)
                if tail == 8:
                    hits = [h for h in hits if h[0] < 3.0]          # silence on beat 4 before the drop
                events[role] += [(t0 + pos, 60, dur, vel) for pos, vel, dur in hits]
            for name, v, shift in (("Sub", sec.sub, 0), ("Mid Bass", sec.mid, 12)):
                pat = _mode_at(v, i, sec.bars)
                if pat:
                    roles.add(name)
                    for pos, p, d, vel in pt.bass_bar(pat, chord, next_chord, bic, ci, spec.variant):
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
    return Composition(spec, sections, _clamp(_tracks(events, spec), total * BEATS_PER_BAR), bars, total, tonic, mode)


def _clamp(tracks: list, end: float) -> list:
    """No note rings past the end of the song (a swung hit on the very last 16th would)."""
    for t in tracks:
        t.notes = [n if n.start + n.duration <= end else replace(n, duration=end - n.start) for n in t.notes]
    return tracks


def _clash_overlap(g: float, p: int, d: float, bass: list) -> float:
    return sum(max(0.0, min(g + d, bg + bd) - max(g, bg)) for bg, bp, bd, _ in bass if (p - bp) % 12 in CLASH_PCS)


def _resolve_hook_clashes(events: dict, bars: dict) -> None:
    """Move a hook note that sounds a minor 2nd / tritone / major 7th against the bass to the nearest chord tone."""
    by_bar = defaultdict(list)
    for ev in events.get("Sub", []):
        by_bar[int(ev[0] // BEATS_PER_BAR) + 1].append(ev)
    hook = sorted(events.get("Hook", []))
    out, prev = [], None
    for g, p, d, vel in hook:
        b = int(g // BEATS_PER_BAR) + 1
        near = by_bar.get(b, []) + by_bar.get(b - 1, [])
        if _clash_overlap(g, p, d, near) > CLASH_MIN:
            p = pt.nearest_chord_tone(p, bars[b].chord, avoid=prev)
        out.append((g, p, d, vel))
        prev = p
    if out:
        events["Hook"] = out


def _tracks(events: dict, spec: Spec) -> list:
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
            swing = (name == "Hook" and spec.swing_hook) or (role == "bass" and spec.swing_bass)
        late_b = late if name in dr.SKINS else 0.0
        notes = []
        for g, p, d, vel in sorted(set(events[name])):
            off = feel_offset(g, swing, spec.swing, late_b) if spec.bake_feel else 0.0
            # swing delays the onset, not the release: a swung hit must not ring into the next 16th
            notes.append(Note(p, g + off, max(0.03, d - (off - late_b)), vel, g))
        out.append(Track(name, role, group, notes, swing, spec.late_ms if name in dr.SKINS else 0.0, hint, dr.GM_PITCH.get(name)))
    return out


def cut(src: Composition, segments: list, spec: Spec | None = None) -> Composition:
    """New composition made of whole-bar ranges of `src` (name, first source bar, bars). Used for the radio edit."""
    sections, bars, moved = [], {}, defaultdict(list)
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
        sections.append(Section(name, n, src.bars[first].kind, start=dst))
        dst += n
    tracks = [replace(t, notes=sorted(moved[t.name], key=lambda x: (x.grid, x.pitch))) for t in src.tracks if moved[t.name]]
    return Composition(spec or src.spec, sections, _clamp(tracks, bar_start(dst)), bars, dst - 1, src.tonic, src.mode)
