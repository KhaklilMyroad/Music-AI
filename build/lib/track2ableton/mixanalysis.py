"""Measurements that reveal how a stem was processed: loudness, EQ shape, dynamics,
stereo image, reverb decay, tempo-synced echoes, sidechain pumping, saturation, filter sweeps."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.signal import lfilter, resample_poly

from . import dsp
from .audio import Audio, db

# ----------------------------------------------------------------------------- loudness (ITU-R BS.1770-4)


def k_weighting(sr: int):
    """Coefficients for the two K-weighting stages at any sample rate (bilinear design;
    reproduces the BS.1770 48 kHz table)."""
    f0, G, Q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    K = np.tan(np.pi * f0 / sr)
    Vh = 10 ** (G / 20)
    Vb = Vh ** 0.4996667741545416
    a0 = 1 + K / Q + K * K
    b1 = [(Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0]
    a1 = [1.0, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    f0, Q = 38.13547087602444, 0.5003270373238773
    K = np.tan(np.pi * f0 / sr)
    a0 = 1 + K / Q + K * K
    b2 = [1.0, -2.0, 1.0]
    a2 = [1.0, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    return (np.array(b1), np.array(a1)), (np.array(b2), np.array(a2))


def _block_loudness(audio: Audio, block: float, overlap: float) -> np.ndarray:
    (b1, a1), (b2, a2) = k_weighting(audio.sr)
    z = []
    for ch in audio.data[:2]:
        y = lfilter(b2, a2, lfilter(b1, a1, ch.astype(np.float64)))
        z.append(y ** 2)
    z = np.array(z)
    n = int(block * audio.sr)
    step = max(1, int(n * (1 - overlap)))
    if z.shape[1] < n:
        return np.array([])
    c = np.cumsum(np.pad(z, ((0, 0), (1, 0))), axis=1)
    starts = np.arange(0, z.shape[1] - n + 1, step)
    ms = (c[:, starts + n] - c[:, starts]) / n  # mean square per channel
    return -0.691 + 10 * np.log10(ms.sum(axis=0) + 1e-20)


def integrated_lufs(audio: Audio) -> float:
    L = _block_loudness(audio, 0.4, 0.75)
    if L.size == 0:
        return -70.0
    L = L[L > -70]
    if L.size == 0:
        return -70.0
    rel = 10 * np.log10(np.mean(10 ** (L / 10))) - 10
    L = L[L > rel]
    return float(10 * np.log10(np.mean(10 ** (L / 10)))) if L.size else -70.0


def loudness_range(audio: Audio) -> float:
    """EBU Tech 3342 LRA (short-term 3 s, abs gate -70, rel gate -20, 10th..95th percentile)."""
    L = _block_loudness(audio, 3.0, 2.9 / 3.0)
    L = L[L > -70]
    if L.size < 2:
        return 0.0
    rel = 10 * np.log10(np.mean(10 ** (L / 10))) - 20
    L = L[L > rel]
    return float(np.percentile(L, 95) - np.percentile(L, 10)) if L.size >= 2 else 0.0


def true_peak_db(audio: Audio) -> float:
    up = resample_poly(audio.data.astype(np.float64), 4, 1, axis=1)
    return float(db(np.max(np.abs(up))))


# ----------------------------------------------------------------------------- spectrum / EQ


@dataclass
class EQBand:
    kind: str       # "highpass" | "lowpass" | "bell" | "lowshelf" | "highshelf"
    freq: float
    gain_db: float = 0.0
    q: float = 0.71
    slope_db_oct: int = 24


@dataclass
class SpectrumProfile:
    centers: list[float]
    levels_db: list[float]
    tilt_db_per_oct: float
    centroid_hz: float
    rolloff85_hz: float
    lowest_hz: float      # -30 dB point re: in-band max
    highest_hz: float
    eq_moves: list[EQBand]


def spectrum_profile(mono: np.ndarray, sr: int) -> SpectrumProfile:
    n_fft = 8192
    mag = dsp.stft_mag(mono, n_fft, n_fft // 2)
    p = (mag.astype(np.float64) ** 2).mean(axis=0)
    freqs = dsp.fft_freqs(n_fft, sr)
    centers = dsp.third_octave_centers(25, min(16000, sr / 2.2))
    lv = dsp.band_levels_db(p, freqs, centers)
    # Per-Hz density -> per-band level is what an analyser shows; normalise to max.
    lv = lv - lv.max()
    total = p.sum() + 1e-20
    centroid = float((freqs * p).sum() / total)
    cum = np.cumsum(p) / total
    rolloff = float(freqs[min(np.searchsorted(cum, 0.85), freqs.size - 1)])
    active = np.where(lv > -30)[0]
    lowest = float(centers[active[0]]) if active.size else float(centers[0])
    highest = float(centers[active[-1]]) if active.size else float(centers[-1])
    oc = np.log2(centers / 1000.0)
    m = lv > -45
    tilt = float(np.polyfit(oc[m], lv[m], 1)[0]) if m.sum() >= 3 else 0.0
    eq = infer_eq(centers, lv, lowest, highest)
    return SpectrumProfile([float(c) for c in centers], [round(float(x), 2) for x in lv], round(tilt, 2), round(centroid, 1),
                           round(rolloff, 1), lowest, highest, eq)


def infer_eq(centers: np.ndarray, lv: np.ndarray, lowest: float, highest: float) -> list[EQBand]:
    """EQ Eight moves that would carve a broadband source into this spectral shape.

    Steep roll-offs at the band edges are read as high/low-pass filters. Bumps and dips of
    more than 3 dB relative to a smoothed version of the curve become bell bands (max 3)."""
    moves: list[EQBand] = []
    if lowest > 35:
        i = int(np.searchsorted(centers, lowest))
        below = lv[max(0, i - 3):i]
        slope = (lv[i] - below[0]) / max(1, below.size) * 3 if below.size else 0
        moves.append(EQBand("highpass", round(float(lowest) * 0.8, 1), 0, 0.71, 48 if slope > 20 else 24 if slope > 10 else 12))
    if highest < 14000:
        moves.append(EQBand("lowpass", round(float(highest) * 1.25, 1), 0, 0.71, 24))
    inband = (centers >= lowest) & (centers <= highest)
    if inband.sum() >= 7:
        idx = np.where(inband)[0]
        seg = lv[idx]
        k = 5
        smooth = np.convolve(np.pad(seg, k // 2, mode="edge"), np.ones(k) / k, mode="valid")
        resid = seg - smooth
        order = np.argsort(-np.abs(resid))
        used: list[int] = []
        for o in order:
            if abs(resid[o]) < 3 or len(used) >= 3:
                break
            if any(abs(o - u) < 3 for u in used):
                continue
            used.append(o)
            moves.append(EQBand("bell", round(float(centers[idx[o]]), 1), round(float(resid[o]), 1), 1.4))
    return moves


# ----------------------------------------------------------------------------- dynamics


@dataclass
class Dynamics:
    peak_db: float
    rms_db: float
    crest_db: float
    short_term_range_db: float   # spread of 100 ms RMS (10..95th pct)
    compression_guess: str
    ratio: float
    threshold_db: float
    attack_ms: float
    release_ms: float


def dynamics(mono: np.ndarray, sr: int) -> Dynamics:
    peak = float(db(np.max(np.abs(mono)) if mono.size else 0))
    rms = float(db(np.sqrt(np.mean(mono.astype(np.float64) ** 2)) if mono.size else 0))
    crest = peak - rms
    hop = int(0.1 * sr)
    env = dsp.envelope(mono, sr, hop)
    env_db = db(env)
    active = env_db[env_db > env_db.max() - 40]
    rng = float(np.percentile(active, 95) - np.percentile(active, 10)) if active.size > 4 else 0.0
    # Heuristic map: crest factor of an uncompressed acoustic/synth stem is typically 15-20 dB.
    if crest < 8:
        guess, ratio, att, rel = "heavy (limited / OTT-style)", 8.0, 1.0, 60.0
    elif crest < 11:
        guess, ratio, att, rel = "strong", 4.0, 5.0, 100.0
    elif crest < 14:
        guess, ratio, att, rel = "moderate", 2.5, 10.0, 150.0
    else:
        guess, ratio, att, rel = "light / none", 1.5, 20.0, 200.0
    thr = round(rms + (crest * 0.4), 1)
    return Dynamics(round(peak, 1), round(rms, 1), round(crest, 1), round(rng, 1), guess, ratio, thr, att, rel)


# ----------------------------------------------------------------------------- stereo


@dataclass
class Stereo:
    correlation: float
    side_to_mid_db: float
    width_percent: float        # Utility "Width" that produces this side/mid ratio from a full-width source
    low_mono_below_hz: float    # bass mono'd below this frequency (0 = not detected)
    pan: float                  # -1 L .. +1 R


def stereo(audio: Audio) -> Stereo:
    if audio.channels < 2:
        return Stereo(1.0, -120.0, 0.0, 0.0, 0.0)
    L, R = audio.data[0].astype(np.float64), audio.data[1].astype(np.float64)
    M, S = 0.5 * (L + R), 0.5 * (L - R)
    corr = float(np.sum(L * R) / (np.sqrt(np.sum(L * L) * np.sum(R * R)) + 1e-20))
    em, es = np.sum(M * M) + 1e-20, np.sum(S * S) + 1e-20
    sm = float(10 * np.log10(es / em))
    # For a decorrelated source of equal-level channels S/M = 1 (0 dB) at width 100%.
    width = float(np.clip(100 * np.sqrt(es / em), 0, 400))
    el, er = np.sum(L * L), np.sum(R * R)
    pan = float((er - el) / (er + el + 1e-20))
    # lowest frequency band where side energy appears
    n_fft = 8192
    ms = dsp.stft_mag(M, n_fft, n_fft // 2) ** 2
    ss = dsp.stft_mag(S, n_fft, n_fft // 2) ** 2
    freqs = dsp.fft_freqs(n_fft, audio.sr)
    pm, ps = ms.mean(axis=0), ss.mean(axis=0)
    low_mono = 0.0
    if sm > -20:
        for f in (60, 80, 100, 120, 150, 200, 250, 300):
            band = (freqs > f * 0.8) & (freqs < f)
            if band.any() and 10 * np.log10(ps[band].sum() / (pm[band].sum() + 1e-20) + 1e-20) < -30:
                low_mono = float(f)
    return Stereo(round(corr, 3), round(sm, 1), round(width, 0), low_mono, round(pan, 2))


# ----------------------------------------------------------------------------- reverb


@dataclass
class ReverbEstimate:
    rt60_s: float
    predelay_ms: float
    wet_hint: str
    decays_measured: int


def reverb(mono: np.ndarray, sr: int, onset_times: np.ndarray | None = None) -> ReverbEstimate:
    """Free-decay slope fitting after energy peaks (Schroeder-style backward integration per event)."""
    hop = int(0.005 * sr)
    env = dsp.envelope(mono, sr, hop) ** 2
    env_db = 10 * np.log10(env + 1e-20)
    fps = sr / hop
    peaks = dsp.peak_pick(dsp.smooth(env_db, 5), 10, 10, 3.0, int(0.15 * fps), positive=False)
    slopes = []
    for p in peaks:
        seg = env[p: p + int(2.5 * fps)]
        if seg.size < int(0.2 * fps):
            continue
        # stop at the next attack (energy rising by 3 dB)
        sdb = 10 * np.log10(seg + 1e-20)
        rise = np.where(np.diff(dsp.smooth(sdb, 5)) > 0.6)[0]
        if rise.size and rise[0] > int(0.15 * fps):
            seg = seg[: rise[0]]
        sch = np.cumsum(seg[::-1])[::-1]
        sch_db = 10 * np.log10(sch / (sch[0] + 1e-20) + 1e-20)
        # T20 (ISO 3382 style): fit -5..-25 dB; a decay that is cut off earlier by the next note
        # is the instrument's own envelope, not a reverb tail, and is skipped.
        i5 = np.searchsorted(-sch_db, 5)
        i25 = np.searchsorted(-sch_db, 25)
        if i25 >= sch_db.size - 1 or i25 - i5 < 4:
            continue
        # raw (non-integrated) level must also have fallen >= 25 dB within the segment
        if 10 * np.log10(seg.max() / (seg[-max(3, int(0.02 * fps)):].mean() + 1e-20)) < 25:
            continue
        t = np.arange(i5, i25) / fps
        k = np.polyfit(t, sch_db[i5:i25], 1)[0]
        if k < -1:
            slopes.append(-60.0 / k)
    if not slopes:
        return ReverbEstimate(0.0, 0.0, "not measurable (no free decays)", 0)
    rt = float(np.median(slopes))
    hint = "dry" if rt < 0.35 else "short room" if rt < 0.9 else "hall / plate" if rt < 2.5 else "long ambient"
    return ReverbEstimate(round(rt, 2), 0.0, hint, len(slopes))


# ----------------------------------------------------------------------------- echo / delay


@dataclass
class EchoEstimate:
    detected: bool
    division: str
    time_beats: float
    feedback: float
    strength: float


DIVISIONS = {"1/16": 0.25, "1/8": 0.5, "1/8 dotted": 0.75, "1/4": 1.0, "1/4 dotted": 1.5, "1/8 triplet": 1 / 3, "1/4 triplet": 2 / 3}


def echo(mono: np.ndarray, sr: int, bpm: float, note_onsets_beats: np.ndarray | None = None) -> EchoEstimate:
    """Tempo-synced echo: autocorrelation of the high-passed envelope at note-division lags,
    beyond what the part's own rhythm explains. Low confidence by nature."""
    hop = int(0.004 * sr)
    x = mono - dsp.smooth(mono, 64) if mono.size > 128 else mono
    env = dsp.envelope(x, sr, hop)
    if env.size < 100:
        return EchoEstimate(False, "", 0, 0, 0)
    e = np.log(env + 1e-6)
    e = e - dsp.smooth(e, int(0.5 * sr / hop))
    e = (e - e.mean()) / (e.std() + 1e-9)
    beat = 60.0 / bpm * sr / hop

    def ac(lag):
        lag = int(round(lag))
        if lag <= 0 or lag >= e.size - 10:
            return 0.0
        return float(np.dot(e[:-lag], e[lag:]) / (e.size - lag))

    # Straight divisions (1/16, 1/8, 1/4) cannot be told apart from the part's own rhythm with this
    # method, so only dotted/triplet echoes are reported; they must stand out from the straight lags.
    odd = {k: v for k, v in DIVISIONS.items() if "dotted" in k or "triplet" in k}
    scores = {k: ac(v * beat) for k, v in odd.items()}
    straight = max(ac(v * beat) for k, v in DIVISIONS.items() if k not in odd)
    best = max(scores, key=scores.get)
    s1 = scores[best]
    s2 = ac(2 * DIVISIONS[best] * beat)
    # the echo lag must beat the neighbouring straight lags, and must not just be a sub-multiple of the beat grid
    neighbours = [ac(DIVISIONS[best] * beat * f) for f in (0.85, 1.15)]
    detected = s1 > 0.5 and s1 > straight and s1 > 1.5 * max(neighbours) and 0.05 < s2 < s1
    fb = float(np.clip(s2 / (s1 + 1e-9), 0, 0.9)) if detected else 0.0
    return EchoEstimate(bool(detected), best if detected else "", DIVISIONS[best] if detected else 0.0, round(fb, 2), round(s1, 2))


# ----------------------------------------------------------------------------- sidechain pumping


@dataclass
class Pumping:
    detected: bool
    depth_db: float
    release_ms: float
    shape: list[float] = field(default_factory=list)  # dB curve over one beat (32 points)
    kick_alignment: float = 0.0


def pumping(mono: np.ndarray, sr: int, beat_times: np.ndarray, kick_times: np.ndarray | None = None,
            highpass_hz: float | None = None) -> Pumping:
    """Beat-synchronous envelope folding. A sidechained part dips right after each kick and
    recovers before the next beat; a steady pad/bass shows a flat folded curve."""
    if beat_times.size < 8:
        return Pumping(False, 0, 0)
    if highpass_hz:
        from scipy.signal import butter, sosfilt
        mono = sosfilt(butter(4, highpass_hz, "highpass", fs=sr, output="sos"), mono)
    hop = int(0.002 * sr)
    # 25 ms RMS window: longer than one period of a 40 Hz bass, short enough to see a 50 ms duck.
    win = int(0.025 * sr)
    c = np.cumsum(np.pad(mono.astype(np.float64) ** 2, (win, 0)))
    pos = np.arange(win, c.size, hop)
    env = np.sqrt((c[pos] - c[pos - win]) / win)
    env_db = 20 * np.log10(env + 1e-9)
    period = float(np.median(np.diff(beat_times)))
    points = 32
    anchors = kick_times if kick_times is not None and kick_times.size >= 8 else beat_times
    curves = []
    for t in anchors:
        a = int(t * sr / hop)
        b = int((t + period) * sr / hop)
        if b >= env_db.size:
            break
        seg = env_db[a:b]
        if seg.size < points or seg.max() < env_db.max() - 35:
            continue
        idx = np.linspace(0, seg.size - 1, points).astype(int)
        curves.append(seg[idx] - seg.max())
    if len(curves) < 8:
        return Pumping(False, 0, 0)
    curve = np.median(np.array(curves), axis=0)
    # Dip right after the trigger, then a recovery during the first third of the beat.
    imin = 1 + int(np.argmin(curve[1: points // 6 + 1]))
    late = curve[points // 2:].max()
    depth = float(late - curve[imin])
    target = curve[imin] + 0.63 * depth
    rec = np.where(curve[imin:] >= target)[0]
    release = (rec[0] / points * period * 1000) if rec.size else period * 1000
    recovered = curve[points // 3] - curve[imin] > 0.4 * depth
    detected = depth > 3.0 and recovered
    return Pumping(bool(detected), round(depth, 1), round(float(release), 0), [round(float(c), 2) for c in curve],
                   kick_alignment=1.0 if kick_times is not None and kick_times.size >= 8 else 0.5)


# ----------------------------------------------------------------------------- saturation


def harmonic_profile(mono: np.ndarray, sr: int, f0_hz: np.ndarray, frame_hop_s: float, max_freq: float | None = None) -> dict:
    """Harmonic amplitudes relative to the fundamental, averaged over stable pitched frames.

    Returns slope (dB per octave of harmonic number), odd/even balance and a waveform guess:
    saw ~ -6 dB/oct all harmonics, square ~ -6 dB/oct odd only, triangle ~ -12 dB/oct odd only,
    sine ~ fundamental only."""
    n_fft = 8192
    amps = []
    hops = np.where(f0_hz > 0)[0]
    if hops.size == 0:
        return {"waveform": "unknown", "frames": 0}
    if max_freq is not None and np.median(f0_hz[hops]) * 4 > max_freq:
        return {"waveform": "unknown", "frames": 0,
                "reason": f"stem is band-limited at ~{max_freq:.0f} Hz by the separator; fewer than 4 harmonics are visible"}
    # sample up to 60 stable frames
    stable = [i for i in hops if i + 4 < f0_hz.size and np.all(np.abs(np.diff(f0_hz[i:i + 5])) < f0_hz[i] * 0.03)]
    if not stable:
        return {"waveform": "unknown", "frames": 0}
    pick = np.array(stable)[np.linspace(0, len(stable) - 1, min(60, len(stable))).astype(int)]
    win = np.hanning(n_fft)
    for i in pick:
        c = int(i * frame_hop_s * sr)
        seg = mono[max(0, c - n_fft // 2): c + n_fft // 2]
        if seg.size < n_fft:
            continue
        sp = np.abs(np.fft.rfft(seg * win))
        f0 = f0_hz[i]
        h = []
        for k in range(1, 13):
            b = int(round(f0 * k * n_fft / sr))
            if b + 2 >= sp.size or (max_freq is not None and f0 * k > max_freq):
                break
            h.append(sp[max(0, b - 2): b + 3].max())
        if len(h) >= (4 if max_freq else 6) and h[0] > 0:
            amps.append(20 * np.log10(np.array(h[:12]) / h[0] + 1e-9))
    if not amps:
        return {"waveform": "unknown", "frames": 0}
    L = min(len(a) for a in amps)
    H = np.median(np.array([a[:L] for a in amps]), axis=0)
    ks = np.arange(1, L + 1)
    if L < 4:
        return {"waveform": "unknown", "frames": len(amps)}
    odd = H[0::2][1:]  # 3,5,7...
    even = H[1::2]     # 2,4,6...
    odd_m, even_m = float(np.mean(odd)), float(np.mean(even))
    sel = H > -60
    slope = float(np.polyfit(np.log2(ks[sel]), H[sel], 1)[0]) if sel.sum() >= 3 else -60.0
    if H[1:].max() < -30:
        wf = "sine"
    elif even_m < odd_m - 12:
        wf = "square" if slope > -9 else "triangle"
    elif slope > -9:
        wf = "saw"
    else:
        wf = "filtered saw"
    return {"waveform": wf, "harmonic_slope_db_oct": round(slope, 1), "odd_db": round(odd_m, 1),
            "even_db": round(even_m, 1), "harmonics_db": [round(float(v), 1) for v in H], "frames": len(amps)}


def distortion_amount(mono: np.ndarray, sr: int) -> float:
    """0..1: how 'flat-topped' the waveform is (fraction of samples near the stem's peak)
    combined with spectral flatness at high frequencies."""
    if mono.size == 0:
        return 0.0
    a = np.abs(mono)
    pk = a.max() + 1e-12
    near = float(np.mean(a > 0.9 * pk)) / (float(np.mean(a > 0.1 * pk)) + 1e-9)
    return float(np.clip(near * 8, 0, 1))


# ----------------------------------------------------------------------------- filter automation


@dataclass
class FilterSweep:
    start_beat: float
    end_beat: float
    from_hz: float
    to_hz: float
    kind: str  # "lowpass opening" | "lowpass closing" | "highpass rising" | "highpass falling"


def filter_sweeps(mono: np.ndarray, sr: int, bar_times: np.ndarray, to_beats, min_bars: int = 2,
                  boundaries_s: list[float] | None = None) -> tuple[list[FilterSweep], list[tuple[float, float]]]:
    """Track the 85 % roll-off and the 10 % low edge per half-bar; long monotonic moves of >1 octave
    are written as Auto Filter cutoff automation."""
    if bar_times.size < 4:
        return [], []
    n_fft = 4096
    pts = []
    edges = list(bar_times) + [bar_times[-1] + (bar_times[-1] - bar_times[-2])]
    for i in range(len(bar_times)):
        for half in (0, 1):
            t0 = edges[i] + half * (edges[i + 1] - edges[i]) / 2
            t1 = t0 + (edges[i + 1] - edges[i]) / 2
            seg = mono[int(t0 * sr): int(t1 * sr)]
            if seg.size < n_fft:
                continue
            p = (dsp.stft_mag(seg, n_fft, n_fft // 2).astype(np.float64) ** 2).mean(axis=0)
            if p.sum() < 1e-10:
                pts.append((t0, np.nan, np.nan))
                continue
            freqs = dsp.fft_freqs(n_fft, sr)
            cum = np.cumsum(p) / p.sum()
            # 98 % / 2 % energy edges follow a filter cutoff much more closely than the 85 % roll-off,
            # which stays parked on the strong low harmonics.
            hi = freqs[min(np.searchsorted(cum, 0.98), freqs.size - 1)]
            lo = freqs[min(np.searchsorted(cum, 0.02), freqs.size - 1)]
            pts.append((t0, max(hi, 40.0), max(lo, 20.0)))
    if len(pts) < 4:
        return [], []
    t = np.array([p[0] for p in pts])
    hi = np.log2(np.array([p[1] for p in pts]))
    lo = np.log2(np.array([p[2] for p in pts]))
    sweeps: list[FilterSweep] = []
    curve = [(float(to_beats(tt)), float(2 ** h)) for tt, h in zip(t, hi) if np.isfinite(h)]
    for arr, name in ((hi, "lowpass"), (lo, "highpass")):
        dd = np.diff(np.nan_to_num(arr))
        d = np.where(np.abs(dd) < 0.05, 0, np.sign(dd))  # < 0.05 octave counts as 'holding'
        i = 0
        while i < d.size:
            if d[i] == 0:
                i += 1
                continue
            j = i
            while j + 1 < d.size and d[j + 1] in (0, d[i]):
                j += 1
            while j > i and d[j] == 0:  # do not end on a plateau
                j -= 1
            span = j - i + 1
            if span >= min_bars * 2:
                change = arr[j + 1] - arr[i]
                # A change of instrumentation at a section boundary also moves the spectral edges;
                # only moves that stay inside one section are read as filter automation.
                crosses = any(t[i] + 0.05 < b < t[j + 1] - 0.05 for b in (boundaries_s or []))
                if abs(change) >= 1.0 and not crosses:
                    if name == "lowpass":
                        kind = "lowpass opening" if change > 0 else "lowpass closing"
                    else:
                        kind = "highpass rising" if change > 0 else "highpass falling"
                    sweeps.append(FilterSweep(float(to_beats(t[i])), float(to_beats(t[j + 1])), float(2 ** arr[i]), float(2 ** arr[j + 1]), kind))
            i = j + 1
    return sweeps, curve


def smooth_envelope(mono: np.ndarray, sr: int, hop_s: float = 0.002, win_s: float = 0.025) -> np.ndarray:
    """RMS envelope with a window longer than a low bass period (no ripple), hop `hop_s`."""
    hop = max(1, int(hop_s * sr))
    win = max(1, int(win_s * sr))
    c = np.cumsum(np.pad(mono.astype(np.float64) ** 2, (win, 0)))
    pos = np.arange(win, c.size, hop)
    return np.sqrt((c[pos] - c[pos - win]) / win)
