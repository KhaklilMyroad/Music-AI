"""Keys, scales, chords and progressions for the composer. Equal temperament only.

Pitch numbers are MIDI notes; names follow Ableton (C3 = 60). Makam-based music is not modelled:
the 'hijaz' preset is the 12-tone approximation (Phrygian dominant), not authentic intonation.
"""
from __future__ import annotations

from dataclasses import dataclass

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
ALIASES = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#", "CB": "B", "FB": "E", "E#": "F", "B#": "C"}

SCALES = {
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "harmonic_minor": (0, 2, 3, 5, 7, 8, 11),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "phrygian_dominant": (0, 1, 4, 5, 7, 8, 10),
}

QUALITIES = {"m": (0, 3, 7), "M": (0, 4, 7), "M7b9": (0, 4, 7)}
COLOURS = {"m": (), "M": (), "M7b9": (10, 1)}  # extra chord tones allowed in the harmony (b7, b9)


def pitch_class(name: str) -> int:
    n = name.strip().upper().replace("♯", "#").replace("♭", "B")
    n = ALIASES.get(n, n)
    if n not in NOTE_NAMES:
        raise ValueError(f"unknown note name: {name!r}")
    return NOTE_NAMES.index(n)


def note_name(pitch: int) -> str:
    return f"{NOTE_NAMES[pitch % 12]}{pitch // 12 - 2}"


def parse_key(key: str) -> tuple[int, str]:
    """'A minor' -> (9, 'minor'). Modes: minor, dorian, phrygian, phrygian_dominant (alias: hijaz)."""
    parts = key.replace("-", " ").split()
    if not parts:
        raise ValueError("empty key")
    mode = "_".join(p.lower() for p in parts[1:]) or "minor"
    mode = {"min": "minor", "m": "minor", "hijaz": "phrygian_dominant", "natural_minor": "minor"}.get(mode, mode)
    if mode not in SCALES or mode == "harmonic_minor":
        raise ValueError(f"unsupported mode {mode!r}; use one of minor, dorian, phrygian, phrygian_dominant")
    return pitch_class(parts[0]), mode


@dataclass(frozen=True)
class Chord:
    root_pc: int          # absolute pitch class of the root
    quality: str          # key of QUALITIES
    scale_pcs: tuple      # absolute pitch classes of the 7-note scale used for melody over this chord (ascending from tonic)

    @property
    def tones(self) -> tuple:
        return tuple((self.root_pc + i) % 12 for i in QUALITIES[self.quality])

    @property
    def allowed(self) -> frozenset:
        return frozenset(self.scale_pcs) | frozenset(self.tones) | frozenset((self.root_pc + i) % 12 for i in COLOURS[self.quality])

    @property
    def third(self) -> int:
        return QUALITIES[self.quality][1]

    def degree(self, steps: int) -> int:
        """Semitones from the chord root to the scale tone `steps` scale steps above it (negative = below)."""
        return _semitones(self.scale_pcs, self.scale_pcs.index(self.root_pc), steps)

    @property
    def label(self) -> str:
        return NOTE_NAMES[self.root_pc] + {"m": "m", "M": "", "M7b9": "7(b9)"}[self.quality]


def _semitones(scale_pcs: tuple, idx: int, steps: int) -> int:
    """Semitones from scale tone idx to the tone `steps` scale steps away (positive up, negative down)."""
    asc = [(p - scale_pcs[0]) % 12 for p in scale_pcs]  # 0..11 ascending from the tonic
    octs, i = divmod(idx + steps, 7)
    return asc[i] + 12 * octs - asc[idx]


# name -> (required mode, [(root offset from tonic, quality, melody scale)], break variant or None)
PROGRESSIONS = {
    "andalusian": ("minor", [(0, "m", "minor"), (10, "M", "minor"), (8, "M", "minor"), (7, "M7b9", "harmonic_minor")],
                   [(5, "m", "minor"), (7, "M7b9", "harmonic_minor"), (0, "m", "minor"), (0, "m", "minor")]),
    "minor_loop": ("minor", [(0, "m", "minor"), (8, "M", "minor"), (3, "M", "minor"), (10, "M", "minor")], None),
    "dorian_vamp": ("dorian", [(0, "m", "dorian"), (5, "M", "dorian"), (0, "m", "dorian"), (10, "M", "dorian")], None),
    "phrygian": ("phrygian", [(0, "m", "phrygian"), (1, "M", "phrygian"), (0, "m", "phrygian"), (10, "m", "phrygian")], None),
    "hijaz": ("phrygian_dominant", [(0, "M", "phrygian_dominant"), (1, "M", "phrygian_dominant"),
                                    (10, "m", "phrygian_dominant"), (0, "M", "phrygian_dominant")], None),
}
DEFAULT_PROGRESSION = {"minor": "andalusian", "dorian": "dorian_vamp", "phrygian": "phrygian", "phrygian_dominant": "hijaz"}


def build_progression(tonic: int, mode: str, name: str | None, kind: str = "main") -> list[Chord]:
    name = name or DEFAULT_PROGRESSION[mode]
    if name not in PROGRESSIONS:
        raise ValueError(f"unknown progression {name!r}; choose from {sorted(PROGRESSIONS)}")
    need, main, brk = PROGRESSIONS[name]
    if need != mode:
        raise ValueError(f"progression {name!r} is written for a {need} key, not {mode}")
    spec = brk if (kind == "break" and brk) else main
    out = []
    for off, q, scale in spec:
        pcs = tuple((tonic + s) % 12 for s in SCALES[scale])
        root = (tonic + off) % 12
        if root not in pcs:
            raise ValueError(f"progression {name!r}: chord root is not in its melody scale")
        out.append(Chord(root, q, pcs))
    return out
