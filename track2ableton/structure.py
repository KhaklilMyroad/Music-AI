"""Song structure: bar-level self-similarity, novelty boundaries, section roles."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import dsp


@dataclass
class Section:
    start_bar: int
    end_bar: int     # exclusive
    start: float     # seconds
    end: float
    letter: str      # A/B/C: sections with the same letter sound alike
    role: str        # Intro / Verse / Build / Drop / Breakdown / Outro ...
    energy_db: float
    rising: bool

    @property
    def bars(self) -> int:
        return self.end_bar - self.start_bar


def bar_features(mono: np.ndarray, sr: int, bar_times: np.ndarray, chroma: np.ndarray, chroma_fps: float):
    edges = list(bar_times) + [bar_times[-1] + (bar_times[-1] - bar_times[-2] if len(bar_times) > 1 else 2.0)]
    n_fft = 2048
    bands = [(20, 120), (120, 400), (400, 1500), (1500, 5000), (5000, 16000)]
    feats, energy, slope = [], [], []
    for i in range(len(bar_times)):
        a, b = int(edges[i] * sr), int(edges[i + 1] * sr)
        seg = mono[a:b]
        if seg.size < n_fft:
            seg = np.pad(seg, (0, n_fft - seg.size))
        mag = dsp.stft_mag(seg, n_fft, 1024)
        p = (mag ** 2).mean(axis=0)
        freqs = dsp.fft_freqs(n_fft, sr)
        be = [10 * np.log10(p[(freqs >= lo) & (freqs < hi)].sum() + 1e-12) for lo, hi in bands]
        ca, cb = int(edges[i] * chroma_fps), max(int(edges[i] * chroma_fps) + 1, int(edges[i + 1] * chroma_fps))
        ch = chroma[ca:cb].mean(axis=0) if cb <= chroma.shape[0] and cb > ca else np.zeros(12)
        ch = ch / (np.linalg.norm(ch) + 1e-9)
        rms = float(10 * np.log10(np.mean(seg.astype(np.float64) ** 2) + 1e-12))
        half = seg.size // 2
        slope.append(10 * np.log10(np.mean(seg[half:] ** 2) + 1e-12) - 10 * np.log10(np.mean(seg[:half] ** 2) + 1e-12))
        feats.append(np.concatenate([np.array(be) / 10.0, ch * 2.0]))
        energy.append(rms)
    return np.array(feats), np.array(energy), np.array(slope)


def novelty(F: np.ndarray, half: int = 4) -> np.ndarray:
    X = (F - F.mean(axis=0)) / (F.std(axis=0) + 1e-9)
    X = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
    S = X @ X.T
    n = S.shape[0]
    k = np.ones((2 * half, 2 * half))
    k[:half, half:] = -1
    k[half:, :half] = -1
    g = np.outer(np.hanning(2 * half), np.hanning(2 * half))
    k *= g
    Sp = np.pad(S, half, mode="edge")
    nov = np.array([np.sum(Sp[i:i + 2 * half, i:i + 2 * half] * k) for i in range(n)])
    return np.maximum(nov, 0)


def analyze(mono: np.ndarray, sr: int, bar_times: np.ndarray, chroma: np.ndarray, chroma_fps: float) -> list[Section]:
    n = len(bar_times)
    if n < 4:
        return [Section(0, n, float(bar_times[0]) if n else 0.0, len(mono) / sr, "A", "Loop", 0.0, False)]
    F, energy, slope = bar_features(mono, sr, bar_times, chroma, chroma_fps)
    nov = novelty(F, half=4 if n >= 16 else 2)
    thr = nov.mean()
    cands = [i for i in range(2, n - 1) if nov[i] >= thr and nov[i] == nov[max(0, i - 2): i + 3].max()]
    # Snap to 4-bar phrases (dominant convention in produced music), keep >= 4 bars apart.
    bounds = [0]
    for c in sorted(cands, key=lambda i: -nov[i]):
        snapped = int(round(c / 4) * 4)
        if abs(snapped - c) <= 1 and 0 < snapped < n and nov[min(snapped, n - 1)] >= 0.6 * nov[c]:
            c = snapped
        if all(abs(c - b) >= 4 for b in bounds):
            bounds.append(c)
    bounds = sorted(bounds) + [n]
    # Energy jumps of >4 dB at a phrase line are boundaries too (drops rarely fail this).
    for i in range(4, n, 4):
        if abs(np.mean(energy[i:i + 2]) - np.mean(energy[i - 2:i])) > 4 and all(abs(i - b) >= 4 for b in bounds):
            bounds.append(i)
    bounds = sorted(set(bounds))

    segs = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
    seg_feat = [F[a:b].mean(axis=0) for a, b in segs]
    letters: list[str] = []
    protos: list[np.ndarray] = []
    for f in seg_feat:
        best, best_s = None, 0.0
        for j, p in enumerate(protos):
            s = float(np.dot(f, p) / (np.linalg.norm(f) * np.linalg.norm(p) + 1e-9))
            if s > best_s:
                best, best_s = j, s
        if best is not None and best_s > 0.985:
            letters.append(chr(65 + best))
        else:
            protos.append(f)
            letters.append(chr(65 + len(protos) - 1))

    seg_energy = np.array([energy[a:b].mean() for a, b in segs])
    seg_slope = np.array([slope[a:b].mean() + (energy[b - 1] - energy[a]) / max(1, b - a) for a, b in segs])
    emax = seg_energy.max()
    sections: list[Section] = []
    edges = list(bar_times) + [len(mono) / sr]
    for idx, ((a, b), L) in enumerate(zip(segs, letters)):
        e = seg_energy[idx]
        high = e >= emax - 2.0
        rising = seg_slope[idx] > 0.4
        nxt_high = idx + 1 < len(segs) and seg_energy[idx + 1] >= emax - 2.0
        if idx == 0 and not high:
            role = "Intro"
        elif idx == len(segs) - 1 and not high:
            role = "Outro"
        elif high:
            role = "Drop / Chorus"
        elif nxt_high and (rising or e < emax - 3):
            role = "Build-up" if rising else "Pre-chorus / Build"
        elif e < emax - 6:
            role = "Breakdown"
        else:
            role = "Verse / Groove"
        sections.append(Section(a, b, float(edges[a]), float(edges[b]), L, role, float(e), bool(rising)))
    return sections
