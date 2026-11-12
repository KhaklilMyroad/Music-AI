"""Tempo, beat grid, downbeats, meter and swing."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import dsp

SR = 22050
N_FFT = 1024
# Centred STFT frames start 'hearing' a hit before it happens; measured bias with N_FFT=1024 on
# synthetic kicks is ~7-13 ms early, so beat times are shifted later by this amount.
ONSET_LAG_S = 0.010
HOP = 256
FPS = SR / HOP


@dataclass
class OnsetData:
    full: np.ndarray       # broadband spectral flux
    low: np.ndarray        # < 150 Hz flux (kick-ish)
    mid: np.ndarray        # 150 Hz - 2 kHz
    high: np.ndarray       # > 5 kHz flux (hats-ish)
    fps: float = FPS


@dataclass
class Rhythm:
    bpm: float
    bpm_raw: float
    beat_times: np.ndarray
    downbeat_offset: int          # index of first downbeat inside beat_times
    beats_per_bar: int
    first_downbeat: float         # seconds
    swing_percent: float          # MPC style: 50 = straight, 66.7 = triplet feel
    tempo_stability: float        # std of local tempo estimates in BPM
    confidence: float
    notes: list[str] = field(default_factory=list)

    @property
    def beat_len(self) -> float:
        return 60.0 / self.bpm

    @property
    def bar_len(self) -> float:
        return self.beat_len * self.beats_per_bar

    def bar_times(self) -> np.ndarray:
        return self.beat_times[self.downbeat_offset::self.beats_per_bar]

    def to_beats(self, t: float | np.ndarray):
        """Seconds -> Ableton arrangement beats (bar 1 beat 1 == beat 0 at first downbeat)."""
        return (np.asarray(t) - self.first_downbeat) / self.beat_len


def onset_envelopes(mono: np.ndarray, sr: int) -> OnsetData:
    from .audio import resample

    x = resample(mono[None, :], sr, SR)[0] if sr != SR else mono
    mag = np.abs(dsp.stft(x, N_FFT, HOP))
    fb = dsp.mel_filterbank(SR, N_FFT, 80, 30, 11000)
    mel = np.log1p(1000 * (mag ** 2) @ fb.T)
    flux = np.maximum(0, np.diff(mel, axis=0, prepend=mel[:1]))
    centers = dsp.mel_to_hz(np.linspace(dsp.hz_to_mel(30), dsp.hz_to_mel(11000), 82)[1:-1])

    def band(lo, hi):
        m = (centers >= lo) & (centers < hi)
        return _norm(flux[:, m].mean(axis=1))

    return OnsetData(
        full=_norm(flux.mean(axis=1)),
        low=band(30, 150),
        mid=band(150, 2000),
        high=band(5000, 11000),
    )


def _norm(x: np.ndarray) -> np.ndarray:
    x = x - dsp.smooth(x, int(FPS))  # remove slow trend (local mean)
    x = np.maximum(x, 0)
    s = x.std()
    return x / s if s > 0 else x


def _grid_score(env: np.ndarray, period: float) -> tuple[float, float]:
    """Best mean onset strength over a beat grid of `period` frames; returns (score, phase)."""
    n = env.size
    k = np.arange(0, int((n - 1) / period))
    best, best_phase = -1.0, 0.0
    for phase in np.arange(0, period, 0.5):
        idx = np.round(phase + k * period).astype(int)
        idx = idx[idx < n]
        s = env[idx].mean() if idx.size else 0
        if s > best:
            best, best_phase = s, phase
    return best, best_phase


def estimate_tempo(env: np.ndarray, fps: float = FPS, lo: float = 60, hi: float = 200, octave_env: np.ndarray | None = None) -> tuple[float, float]:
    """Autocorrelation + comb tempo estimate, refined by beat-grid fit. Returns (bpm, confidence)."""
    x = env - env.mean()
    ac = np.correlate(x, x, mode="full")[x.size - 1:]
    ac /= ac[0] + 1e-12
    bpms = np.arange(lo, hi, 0.25)
    scores = np.zeros_like(bpms)
    for i, b in enumerate(bpms):
        p = 60 * fps / b
        s = 0.0
        for k, w in ((1, 1.0), (2, 0.5), (4, 0.25), (0.5, 0.25)):
            lag = p * k
            if lag >= ac.size - 1:
                continue
            j = int(lag)
            frac = lag - j
            s += w * ((1 - frac) * ac[j] + frac * ac[j + 1])
        prior = np.exp(-0.5 * (np.log2(b / 120.0) / 0.9) ** 2)
        scores[i] = s * (0.5 + 0.5 * prior)
    order = np.argsort(scores)[::-1]
    coarse = bpms[order[0]]
    # Octave check with the grid fit: compare tempo, x2 and x0.5 candidates.
    # Octave decision. Start from the slowest plausible octave; double while the half-beat
    # positions carry onsets about as strong as the grid itself (i.e. they are beats, not off-beats).
    oenv = octave_env if octave_env is not None else env

    def mid_ratio(c):
        period = 60 * fps / c
        s, ph = _grid_score(oenv, period)
        k = np.arange(0, int((env.size - 1 - ph - period / 2) / period))
        if not k.size or s <= 0:
            return 0.0
        idx = np.round(ph + period / 2 + k * period).astype(int)
        idx = idx[idx < oenv.size]
        mid = np.array([oenv[max(0, i - 1): i + 2].max() for i in idx]).mean()
        return float(mid / s)

    best_bpm = coarse
    while best_bpm / 2 >= lo:
        best_bpm /= 2
    while best_bpm * 2 <= hi and (mid_ratio(best_bpm) > 0.75 or best_bpm < 70):
        best_bpm *= 2
    # Fine refinement
    fine = np.arange(best_bpm - 1.0, best_bpm + 1.0, 0.01)
    fs = np.array([_grid_score(env, 60 * fps / b)[0] for b in fine])
    bpm = float(fine[int(np.argmax(fs))])
    # Confidence: how much better the chosen grid fits than unrelated tempi (ratios that are not
    # simple multiples), 0 = no better, 1 = unrelated grids catch none of the onsets.
    best_s = _grid_score(env, 60 * fps / bpm)[0]
    alt = [_grid_score(env, 60 * fps / (bpm * r))[0] for r in (0.87, 0.93, 1.07, 1.13, 1.21)]
    conf = float(np.clip(1 - np.mean(alt) / (best_s + 1e-9), 0, 1))
    return bpm, conf


def beat_accents(beat_frames: np.ndarray, onsets: OnsetData, chroma_frames: np.ndarray | None = None,
                 chroma_fps: float = FPS) -> tuple[np.ndarray, np.ndarray]:
    """The two bar markers at every beat: the low-band accent and how much the harmony changes there."""
    def sync(e):
        idx = np.clip(np.round(beat_frames).astype(int), 0, e.size - 1)
        return np.array([e[max(0, i - 2): i + 3].max() for i in idx])

    low_b = sync(onsets.low)
    chord_change = np.zeros_like(low_b)
    if chroma_frames is not None and chroma_frames.shape[0] > 0:
        cf = chroma_frames
        idx = np.clip(np.round(beat_frames * chroma_fps / FPS).astype(int), 0, cf.shape[0] - 1)
        bc = np.array([cf[idx[i]: idx[i + 1]].mean(axis=0) if i + 1 < idx.size and idx[i + 1] > idx[i] else cf[idx[i]] for i in range(idx.size)])
        chord_change[1:] = np.linalg.norm(np.diff(bc, axis=0), axis=1)
        chord_change = chord_change / (chord_change.std() + 1e-9)
    return low_b, chord_change


def downbeat_phase(low_b: np.ndarray, chord_change: np.ndarray, beats_per_bar: int) -> int:
    """Which beat (0 .. beats_per_bar-1) starts the bars: harmonic change is the strongest bar marker; low-band accents help."""
    scores = []
    for off in range(beats_per_bar):
        sel = slice(off, None, beats_per_bar)
        scores.append(2.0 * chord_change[sel].mean() + low_b[sel].mean() / (low_b.mean() + 1e-9) * 0.5)
    return int(np.argmax(scores))


def analyze(mono: np.ndarray, sr: int, onsets: OnsetData | None = None, chroma_frames: np.ndarray | None = None, chroma_fps: float = FPS) -> Rhythm:
    onsets = onsets or onset_envelopes(mono, sr)
    env = onsets.full + 0.5 * onsets.low
    # Kick/snare bands decide the tempo octave (hi-hats often subdivide the beat).
    bpm_raw, conf = estimate_tempo(env, octave_env=onsets.low + onsets.mid)
    notes: list[str] = []
    bpm = bpm_raw
    if abs(bpm_raw - round(bpm_raw)) <= 0.1:
        bpm = float(round(bpm_raw))
        notes.append("Tempo snapped to an integer BPM (typical for productions made in a DAW).")
    period = 60 * FPS / bpm
    _, phase = _grid_score(env, period)
    n_beats = int((env.size - phase) / period) + 1
    beat_frames = phase + np.arange(n_beats) * period
    beat_times = beat_frames / FPS + ONSET_LAG_S

    # Meter: compare 3 vs 4 beat periodicity of beat-synchronous low-band accents.
    low_b, chord_change = beat_accents(beat_frames, onsets, chroma_frames, chroma_fps)
    accent = low_b / (low_b.std() + 1e-9) + chord_change

    def lag_corr(a, lag):
        if a.size <= lag + 4:
            return 0
        a = a - a.mean()
        return float(np.dot(a[:-lag], a[lag:]) / (np.linalg.norm(a[:-lag]) * np.linalg.norm(a[lag:]) + 1e-9))

    beats_per_bar = 4
    c3, c4 = lag_corr(accent, 3), lag_corr(accent, 4)
    if c3 > c4 + 0.15 and lag_corr(accent, 6) > lag_corr(accent, 8):
        beats_per_bar = 3
        notes.append("Triple meter detected (3/4).")

    downbeat_offset = downbeat_phase(low_b, chord_change, beats_per_bar)
    first_downbeat = float(beat_times[downbeat_offset])
    # Extrapolate the grid backwards so bar 1 starts at or before t=0 alignment.
    while first_downbeat - beats_per_bar * 60 / bpm >= -1e-6:
        first_downbeat -= beats_per_bar * 60 / bpm
    if first_downbeat < 0:
        first_downbeat += beats_per_bar * 60 / bpm

    swing = estimate_swing(onsets.full, beat_frames, period)

    # Local tempo stability (20 s windows)
    win = int(20 * FPS)
    local = []
    for s in range(0, env.size - win, win // 2):
        seg = env[s:s + win]
        if seg.std() == 0:
            continue
        b, _ = estimate_tempo(seg, lo=bpm * 0.9, hi=bpm * 1.1)
        local.append(b)
    stability = float(np.std(local)) if len(local) > 1 else 0.0
    if stability > 1.0:
        notes.append("Tempo drifts across the track (live playing or tempo automation). The grid is an average.")

    return Rhythm(
        bpm=bpm, bpm_raw=bpm_raw, beat_times=beat_times, downbeat_offset=downbeat_offset,
        beats_per_bar=beats_per_bar, first_downbeat=first_downbeat, swing_percent=swing,
        tempo_stability=stability, confidence=conf, notes=notes,
    )


def estimate_swing(env: np.ndarray, beat_frames: np.ndarray, period: float) -> float:
    """MPC-style swing on 16ths: where the 2nd 16th of each 8th pair lands (50 = straight)."""
    peaks = dsp.peak_pick(env, 2, 2, 0.5, 2)
    if peaks.size < 16:
        return 50.0
    sixteenth = period / 4
    pos = []
    for p in peaks:
        i = np.searchsorted(beat_frames, p) - 1
        if i < 0 or i >= beat_frames.size:
            continue
        rel = (p - beat_frames[i]) / sixteenth  # 0..4
        for anchor in (1.0, 3.0):  # the "e" and "a" positions
            if abs(rel - anchor) < 0.45:
                pos.append(rel - anchor)
    if len(pos) < 8:
        return 50.0
    delay = float(np.median(pos))  # in 16ths
    # 2nd 16th sits at (1 + delay) / 2 of the 8th-note pair -> MPC swing percent.
    return float(np.clip(50 + 50 * delay, 40, 75))
