"""Small, dependency-free DSP toolkit (numpy/scipy only)."""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.ndimage import median_filter


def frame(x: np.ndarray, n: int, hop: int, pad: bool = True) -> np.ndarray:
    if pad:
        x = np.pad(x, (n // 2, n // 2), mode="reflect" if x.size > n else "constant")
    if x.size < n:
        x = np.pad(x, (0, n - x.size))
    return sliding_window_view(x, n)[::hop]


def stft(x: np.ndarray, n_fft: int = 2048, hop: int = 512) -> np.ndarray:
    """Returns complex STFT, shape (frames, bins)."""
    frames = frame(x, n_fft, hop)
    win = np.hanning(n_fft + 1)[:-1].astype(np.float32)
    return np.fft.rfft(frames * win, axis=1)


def stft_mag(x: np.ndarray, n_fft: int = 2048, hop: int = 512, chunk: int = 1024) -> np.ndarray:
    """Memory-bounded float32 STFT magnitude, shape (frames, bins)."""
    frames = frame(x.astype(np.float32), n_fft, hop)
    win = np.hanning(n_fft + 1)[:-1].astype(np.float32)
    out = np.empty((frames.shape[0], n_fft // 2 + 1), dtype=np.float32)
    for s in range(0, frames.shape[0], chunk):
        out[s:s + chunk] = np.abs(np.fft.rfft(frames[s:s + chunk] * win, axis=1))
    return out


def istft(spec: np.ndarray, n_fft: int, hop: int, length: int) -> np.ndarray:
    win = np.hanning(n_fft + 1)[:-1]
    frames = np.fft.irfft(spec, n=n_fft, axis=1) * win
    out = np.zeros(hop * (frames.shape[0] - 1) + n_fft)
    norm = np.zeros_like(out)
    for i, f in enumerate(frames):
        s = i * hop
        out[s:s + n_fft] += f
        norm[s:s + n_fft] += win ** 2
    out /= np.maximum(norm, 1e-8)
    out = out[n_fft // 2: n_fft // 2 + length]
    if out.size < length:
        out = np.pad(out, (0, length - out.size))
    return out.astype(np.float32)


def fft_freqs(n_fft: int, sr: int) -> np.ndarray:
    return np.fft.rfftfreq(n_fft, 1.0 / sr)


def hz_to_mel(f):
    return 2595.0 * np.log10(1.0 + np.asarray(f) / 700.0)


def mel_to_hz(m):
    return 700.0 * (10.0 ** (np.asarray(m) / 2595.0) - 1.0)


def mel_filterbank(sr: int, n_fft: int, n_mels: int = 64, fmin: float = 30.0, fmax: float | None = None) -> np.ndarray:
    fmax = fmax or sr / 2
    freqs = fft_freqs(n_fft, sr)
    pts = mel_to_hz(np.linspace(hz_to_mel(fmin), hz_to_mel(fmax), n_mels + 2))
    fb = np.zeros((n_mels, freqs.size), dtype=np.float32)
    for i in range(n_mels):
        lo, c, hi = pts[i], pts[i + 1], pts[i + 2]
        up = (freqs - lo) / max(c - lo, 1e-9)
        down = (hi - freqs) / max(hi - c, 1e-9)
        fb[i] = np.maximum(0, np.minimum(up, down))
    return fb


def third_octave_centers(fmin: float = 25.0, fmax: float = 16000.0) -> np.ndarray:
    centers = 1000.0 * 2.0 ** (np.arange(-16, 14) / 3.0)
    return centers[(centers >= fmin) & (centers <= fmax)]


def band_levels_db(power_spectrum: np.ndarray, freqs: np.ndarray, centers: np.ndarray, frac: float = 1 / 3) -> np.ndarray:
    """Average power in fractional-octave bands, in dB."""
    out = np.empty(centers.size)
    k = 2 ** (frac / 2)
    for i, c in enumerate(centers):
        m = (freqs >= c / k) & (freqs < c * k)
        out[i] = 10 * np.log10(np.sum(power_spectrum[m]) + 1e-20) if m.any() else -200.0
    return out


def hpss(mag: np.ndarray, kernel_t: int = 17, kernel_f: int = 17, power: float = 2.0):
    """Median-filter harmonic/percussive soft masks (Fitzgerald 2010). mag: (frames, bins)."""
    harm = median_filter(mag, size=(kernel_t, 1), mode="nearest")
    perc = median_filter(mag, size=(1, kernel_f), mode="nearest")
    hp, pp = harm ** power, perc ** power
    total = hp + pp + 1e-12
    return hp / total, pp / total


def envelope(x: np.ndarray, sr: int, hop: int) -> np.ndarray:
    """RMS envelope with frame hop `hop`."""
    fr = frame(x, hop * 2, hop)
    return np.sqrt(np.mean(fr.astype(np.float64) ** 2, axis=1))


def smooth(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 1:
        return x
    k = np.hanning(n + 2)[1:-1]
    k /= k.sum()
    return np.convolve(x, k, mode="same")


def peak_pick(x: np.ndarray, pre: int = 3, post: int = 3, delta: float = 0.0, wait: int = 2, positive: bool = True) -> np.ndarray:
    """Local maxima above a moving-average threshold."""
    peaks = []
    last = -wait - 1
    n = x.size
    for i in range(n):
        lo, hi = max(0, i - pre), min(n, i + post + 1)
        if x[i] < x[lo:hi].max() or (positive and x[i] <= 0):
            continue
        lo2, hi2 = max(0, i - pre * 3), min(n, i + post * 3 + 1)
        if x[i] < x[lo2:hi2].mean() + delta:
            continue
        if i - last > wait:
            peaks.append(i)
            last = i
    return np.asarray(peaks, dtype=int)


def yin(x: np.ndarray, sr: int, fmin: float, fmax: float, frame_len: int = 2048, hop: int = 256, threshold: float = 0.15):
    """YIN f0 estimator. Returns (f0[Hz] with 0 for unvoiced, aperiodicity 0..1)."""
    tau_min = max(2, int(sr / fmax))
    tau_max = min(frame_len - 2, int(sr / fmin))
    frames = frame(x.astype(np.float64), frame_len, hop)
    w = frame_len - tau_max
    # difference function via FFT autocorrelation
    f0 = np.zeros(frames.shape[0])
    ap = np.ones(frames.shape[0])
    nfft = 1 << int(np.ceil(np.log2(2 * frame_len)))
    # exact r(tau) = sum_{j<w} x_j x_{j+tau}: cross-correlate the first w samples with the frame
    spec_full = np.fft.rfft(frames, nfft, axis=1)
    spec_head = np.fft.rfft(frames[:, :w], nfft, axis=1)
    acf = np.fft.irfft(spec_full * np.conj(spec_head), nfft, axis=1)[:, : tau_max + 1]
    sq = np.cumsum(np.pad(frames ** 2, ((0, 0), (1, 0))), axis=1)
    energy0 = sq[:, w] - sq[:, 0]
    taus = np.arange(tau_max + 1)
    energy_tau = sq[:, taus + w] - sq[:, taus]
    d = energy0[:, None] + energy_tau - 2 * acf
    d = np.maximum(d, 0)
    d[:, 0] = 0
    cmnd = np.ones_like(d)
    cums = np.cumsum(d[:, 1:], axis=1)
    cmnd[:, 1:] = d[:, 1:] * np.arange(1, tau_max + 1) / np.maximum(cums, 1e-12)
    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    for i in range(frames.shape[0]):
        if rms[i] < 1e-4:
            continue
        c = cmnd[i]
        below = np.where(c[tau_min:tau_max] < threshold)[0]
        if below.size:
            t = below[0] + tau_min
            while t + 1 < tau_max and c[t + 1] < c[t]:
                t += 1
        else:
            t = int(np.argmin(c[tau_min:tau_max]) + tau_min)
            if c[t] > 0.35:
                continue
        # parabolic interpolation
        if 1 <= t < tau_max:
            a, b, cc = c[t - 1], c[t], c[t + 1]
            den = a - 2 * b + cc
            shift = float(np.clip(0.5 * (a - cc) / den, -1, 1)) if abs(den) > 1e-12 else 0.0
        else:
            shift = 0.0
        f0[i] = sr / (t + shift)
        ap[i] = float(c[t])
    return f0, ap


def hz_to_midi(f):
    f = np.asarray(f, dtype=float)
    with np.errstate(divide="ignore"):
        return np.where(f > 0, 69 + 12 * np.log2(np.maximum(f, 1e-9) / 440.0), 0.0)


def midi_to_hz(m):
    return 440.0 * 2 ** ((np.asarray(m, dtype=float) - 69) / 12.0)


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_name(m: int, ableton: bool = True) -> str:
    """Ableton names middle C (MIDI 60) 'C3'; scientific pitch names it 'C4'."""
    octave = m // 12 - (2 if ableton else 1)
    return f"{NOTE_NAMES[m % 12]}{octave}"
