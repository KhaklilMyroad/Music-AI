"""Notes, tracks and timing feel shared by the composer modules."""
from __future__ import annotations

from dataclasses import dataclass, field

STEP = 0.25          # one 16th note in beats
BEATS_PER_BAR = 4


@dataclass(frozen=True)
class Note:
    pitch: int
    start: float      # beats from the start of the song, feel (swing / laid-back offset) applied
    duration: float   # beats
    velocity: int
    grid: float       # the straight grid position this note was written on, in beats


@dataclass
class Track:
    name: str
    role: str                 # drum | bass | harmony | hook | trigger
    group: str                # DRUMS | PERC | BASS | MUSIC | VOCALS
    notes: list = field(default_factory=list)
    swing: bool = False       # swing is applied to this track's off-16ths
    late_ms: float = 0.0      # constant, planned laid-back offset
    hint: str = ""            # instrument / sample suggestion for Ableton
    gm_pitch: int | None = None  # General MIDI drum note for the combined drum file
    straight_bars: frozenset = frozenset()   # bars in which this track is not swung (build rolls)


def bar_start(bar: int) -> float:
    """Beat position of a 1-based bar."""
    return (bar - 1) * BEATS_PER_BAR


def swing_shift(swing_pct: float) -> float:
    """Beats by which an off-16th is delayed. 50 = straight, 66.7 = triplet."""
    return (swing_pct - 50.0) / 100.0 * 0.5


def feel_offset(grid: float, swing: bool, swing_pct: float, late_beats: float) -> float:
    off = late_beats
    if swing:
        s = grid / STEP
        if abs(s - round(s)) < 1e-9 and int(round(s)) % 2 == 1:
            off += swing_shift(swing_pct)
    return off
