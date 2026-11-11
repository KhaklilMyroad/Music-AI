"""Tuning, chroma, key/scale and chord progression."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import dsp

SR = 22050
N_FFT = 8192
HOP = 1024
FPS = SR / HOP

# Krumhansl-Kessler key profiles (probe-tone ratings).
KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Camelot wheel: major keys "B", minor keys "A".
_CAMELOT_MAJOR = {0: "8B", 7: "9B", 2: "10B", 9: "11B", 4: "12B", 11: "1B", 6: "2B", 1: "3B", 8: "4B", 3: "5B", 10: "6B", 5: "7B"}
_CAMELOT_MINOR = {9: "8A", 4: "9A", 11: "10A", 6: "11A", 1: "12A", 8: "1A", 3: "2A", 10: "3A", 5: "4A", 0: "5A", 7: "6A", 2: "7A"}

CHORD_TEMPLATES = {
    "": [0, 4, 7],
    "m": [0, 3, 7],
    "sus4": [0, 5, 7],
    "dim": [0, 3, 6],
    "7": [0, 4, 7, 10],
    "maj7": [0, 4, 7, 11],
    "m7": [0, 3, 7, 10],
}
MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII"]


@dataclass
class Chord:
    start: float  # seconds
    end: float
    root: int     # pitch class, -1 = no chord
    quality: str

    @property
    def name(self) -> str:
        return "N.C." if self.root < 0 else dsp.NOTE_NAMES[self.root] + self.quality

    def pitches(self, octave_base: int = 48) -> list[int]:
        if self.root < 0:
            return []
        return [octave_base + self.root + iv for iv in CHORD_TEMPLATES[self.quality]]


@dataclass
class Tonal:
    tuning_cents: float
    tuning_a4_hz: float
    key_root: int
    mode: str  # "major" | "minor"
    key_confidence: float
    key_candidates: list[tuple[str, float]]
    chords: list[Chord]
    chroma: np.ndarray       # (frames, 12) at FPS
    bass_chroma: np.ndarray  # (frames, 12)
    fps: float = FPS
    notes: list[str] = field(default_factory=list)

    @property
    def key_name(self) -> str:
        return f"{dsp.NOTE_NAMES[self.key_root]} {self.mode}"

    @property
    def camelot(self) -> str:
        return (_CAMELOT_MAJOR if self.mode == "major" else _CAMELOT_MINOR)[self.key_root]

    @property
    def scale_pcs(self) -> list[int]:
        steps = MAJOR_SCALE if self.mode == "major" else MINOR_SCALE
        return [(self.key_root + s) % 12 for s in steps]

    def roman(self, chord: Chord) -> str:
        if chord.root < 0:
            return "-"
        rel = (chord.root - self.key_root) % 12
        steps = MAJOR_SCALE if self.mode == "major" else MINOR_SCALE
        if rel in steps:
            num = ROMAN[steps.index(rel)]
        elif (rel + 1) % 12 in steps:
            num = "b" + ROMAN[steps.index((rel + 1) % 12)]
        else:
            num = "#" + ROMAN[steps.index((rel - 1) % 12)]
        minorish = chord.quality.startswith("m") and not chord.quality.startswith("maj") or chord.quality == "dim"
        return (num.lower() if minorish else num) + ("°" if chord.quality == "dim" else "")


def chroma_features(mono: np.ndarray, sr: int):
    from .audio import resample

    x = resample(mono[None, :], sr, SR)[0] if sr != SR else mono
    mag = dsp.stft_mag(x, N_FFT, HOP)
    # Harmonic part only: a time-median removes drum hits (incl. tuned kick sweeps) before pitch-class folding.
    from scipy.ndimage import median_filter
    mag = np.minimum(mag, median_filter(mag, size=(9, 1), mode="nearest"))
    freqs = dsp.fft_freqs(N_FFT, SR)
    tuning = estimate_tuning(mag, freqs)
    sel = (freqs >= 55) & (freqs <= 4200)
    midi = dsp.hz_to_midi(freqs[sel]) - tuning / 100.0
    pc = np.mod(np.round(midi), 12).astype(int)
    comp = np.sqrt(mag[:, sel])
    chroma = np.zeros((mag.shape[0], 12), dtype=np.float32)
    for k in range(12):
        chroma[:, k] = comp[:, pc == k].sum(axis=1)
    bsel = (freqs >= 40) & (freqs <= 250)
    bmidi = dsp.hz_to_midi(freqs[bsel]) - tuning / 100.0
    bpc = np.mod(np.round(bmidi), 12).astype(int)
    bcomp = mag[:, bsel]
    bass = np.zeros_like(chroma)
    for k in range(12):
        bass[:, k] = bcomp[:, bpc == k].sum(axis=1)
    return chroma, bass, tuning


def estimate_tuning(mag: np.ndarray, freqs: np.ndarray) -> float:
    """Weighted circular mean of spectral-peak deviation from 12-TET (A4=440), in cents."""
    spec = mag.mean(axis=0)
    sel = np.where((freqs > 80) & (freqs < 2000))[0]
    s = spec[sel]
    peaks = sel[1:-1][(s[1:-1] > s[:-2]) & (s[1:-1] > s[2:])]
    if peaks.size < 5:
        return 0.0
    w = spec[peaks]
    top = peaks[np.argsort(w)[::-1][:60]]
    # parabolic interpolation for sub-bin peak frequency
    a, b, c = np.log(spec[top - 1] + 1e-12), np.log(spec[top] + 1e-12), np.log(spec[top + 1] + 1e-12)
    shift = 0.5 * (a - c) / np.where(np.abs(a - 2 * b + c) > 1e-12, a - 2 * b + c, 1e-12)
    f = (top + shift) * (freqs[1] - freqs[0])
    dev = (dsp.hz_to_midi(f) - np.round(dsp.hz_to_midi(f)))  # semitones, -0.5..0.5
    ang = dev * 2 * np.pi
    ww = spec[top]
    mean = np.arctan2(np.sum(ww * np.sin(ang)), np.sum(ww * np.cos(ang))) / (2 * np.pi)
    return float(mean * 100.0)


def estimate_key(chroma_profile: np.ndarray):
    prof = chroma_profile / (chroma_profile.sum() + 1e-12)
    res = []
    for root in range(12):
        for mode, tpl in (("major", KK_MAJOR), ("minor", KK_MINOR)):
            t = np.roll(tpl, root)
            r = np.corrcoef(prof, t)[0, 1]
            res.append((r, root, mode))
    res.sort(reverse=True)
    best = res[0]
    conf = float(np.clip((best[0] - res[1][0]) * 5 + 0.3 * best[0], 0, 1))
    cands = [(f"{dsp.NOTE_NAMES[r]} {m}", float(round(s, 3))) for s, r, m in res[:4]]
    return best[1], best[2], conf, cands


def estimate_chords(chroma: np.ndarray, bass: np.ndarray, segments: list[tuple[float, float]], fps: float = FPS) -> list[Chord]:
    templates = []
    for q, ivs in CHORD_TEMPLATES.items():
        for r in range(12):
            t = np.zeros(12)
            t[[(r + i) % 12 for i in ivs]] = 1.0
            # Seventh chords need clear evidence: slightly penalised.
            # Sevenths need clear evidence: a saw/brass tone's 7th harmonic alone already adds a b7 to the chroma.
            penalty = 0.10 if len(ivs) > 3 else (0.03 if q in ("sus4", "dim") else 0.0)
            templates.append((r, q, t / np.linalg.norm(t), penalty))
    energy = chroma.sum(axis=1)
    quiet = np.percentile(energy, 10) * 1.5 if energy.size else 0
    out: list[Chord] = []
    for s, e in segments:
        a, b = int(s * fps), max(int(s * fps) + 1, int(e * fps))
        seg = chroma[a:b]
        if seg.size == 0:
            continue
        v = seg.mean(axis=0)
        if v.sum() <= 0 or energy[a:b].mean() < quiet:
            out.append(Chord(s, e, -1, ""))
            continue
        v = v / (np.linalg.norm(v) + 1e-12)
        bv = bass[a:b].mean(axis=0)
        bv = bv / (bv.max() + 1e-12)
        best, best_s = None, -9
        for r, q, t, pen in templates:
            sc = float(v @ t) + 0.15 * bv[r] - pen
            if sc > best_s:
                best, best_s = (r, q), sc
        out.append(Chord(s, e, best[0], best[1]))
    # merge identical neighbours
    merged: list[Chord] = []
    for c in out:
        if merged and merged[-1].root == c.root and merged[-1].quality == c.quality:
            merged[-1].end = c.end
        else:
            merged.append(c)
    return merged


def analyze(mono: np.ndarray, sr: int, chroma_pack=None) -> Tonal:
    chroma, bass, tuning = chroma_pack or chroma_features(mono, sr)
    energy = chroma.sum(axis=1)
    loud = energy > np.percentile(energy, 30)
    profile = chroma[loud].sum(axis=0) + 0.2 * bass[loud].sum(axis=0) / (bass[loud].sum() + 1e-12) * chroma[loud].sum()
    root, mode, conf, cands = estimate_key(profile)
    notes = []
    a4 = 440.0 * 2 ** (tuning / 1200)
    if abs(tuning) > 15:
        notes.append(f"Track is tuned {tuning:+.0f} cents from A4=440 Hz (A4 = {a4:.1f} Hz). Set instrument fine-tune/Global Transpose accordingly.")
    return Tonal(tuning, a4, root, mode, conf, cands, [], chroma, bass, notes=notes)


def chords_on_grid(tonal: Tonal, bar_times: np.ndarray, beat_times: np.ndarray, beats_per_bar: int) -> list[Chord]:
    """Chords per half bar (two candidates per bar), merged."""
    edges = []
    for i, t in enumerate(bar_times):
        nxt = bar_times[i + 1] if i + 1 < len(bar_times) else t + (bar_times[1] - bar_times[0] if len(bar_times) > 1 else 2.0)
        mid = (t + nxt) / 2
        edges += [(t, mid), (mid, nxt)]
    return estimate_chords(tonal.chroma, tonal.bass_chroma, edges, tonal.fps)
