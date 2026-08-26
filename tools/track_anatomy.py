#!/usr/bin/env python3
"""Deconstruct a finished track into the numbers you need to rebuild it.

Reports tempo grid, key, per-bar arrangement map, harmony, drum step grids,
sidechain envelope, third-octave balance, stereo width and BS.1770 loudness.

    python3 tools/track_anatomy.py song.mp3
    python3 tools/track_anatomy.py song.wav --bpm 128

Requires numpy, scipy, librosa, soundfile and an ffmpeg binary on PATH
(or the one bundled with the imageio-ffmpeg package) for non-wav input.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import warnings

import numpy as np
import scipy.signal as ss

warnings.filterwarnings("ignore")

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
BANDS = [(20, 60), (60, 120), (120, 300), (300, 800), (800, 2500), (2500, 7000), (7000, 16000)]


def ffmpeg_exe():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return None


def load(path, sr=44100):
    """Return (left, right) float arrays, decoding through ffmpeg when needed."""
    import librosa
    if not path.lower().endswith(".wav"):
        exe = ffmpeg_exe()
        if exe is None:
            sys.exit("ffmpeg not found - install it, or `pip install imageio-ffmpeg`")
        tmp = os.path.join(tempfile.mkdtemp(), "decoded.wav")
        subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", "-i", path,
                        "-ac", "2", "-ar", str(sr), "-c:a", "pcm_s16le", tmp], check=True)
        path = tmp
    y, _ = librosa.load(path, sr=sr, mono=False)
    if y.ndim == 1:
        y = np.stack([y, y])
    return y


def tempo_grid(mono, sr, bpm_hint=None):
    """Exhaustive search for the bpm+phase whose beat grid carries most onset energy."""
    import librosa
    hop = 256
    oenv = librosa.onset.onset_strength(y=mono, sr=sr, hop_length=hop, aggregate=np.median)
    dur = len(mono) / sr
    lo, hi = (bpm_hint - 0.5, bpm_hint + 0.5) if bpm_hint else (100.0, 160.0)
    best = None
    for bpm in np.arange(lo, hi, 0.02):
        period = 60.0 / bpm
        t = np.arange(int(dur / period)) * period
        for phase in np.arange(0, period, 0.005):
            idx = np.clip(((t + phase) / (hop / sr)).astype(int), 0, len(oenv) - 1)
            score = oenv[idx].mean()
            if best is None or score > best[0]:
                best = (score, bpm, phase)
    return best[1], best[2]


def key_estimate(mono, sr):
    import librosa
    chroma = librosa.feature.chroma_cqt(y=mono, sr=sr, hop_length=1024).mean(axis=1)
    chroma = chroma / chroma.sum()
    major = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    scored = []
    for i in range(12):
        scored.append((np.corrcoef(chroma, np.roll(major, i))[0, 1], f"{NOTES[i]} major"))
        scored.append((np.corrcoef(chroma, np.roll(minor, i))[0, 1], f"{NOTES[i]} minor"))
    return sorted(scored, reverse=True)[:4]


def lufs(left, right, sr):
    """ITU-R BS.1770 integrated loudness plus peak statistics."""
    def k_weight(x):
        f0, gain, q = 1681.97, 3.999, 0.7071
        k = np.tan(np.pi * f0 / sr)
        vh = 10 ** (gain / 20)
        vb = vh ** 0.4996667
        a0 = 1 + k / q + k * k
        x = ss.lfilter([(vh + vb * k / q + k * k) / a0, 2 * (k * k - vh) / a0,
                        (vh - vb * k / q + k * k) / a0],
                       [1, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0], x)
        f0, q = 38.13, 0.5003
        k = np.tan(np.pi * f0 / sr)
        a0 = 1 + k / q + k * k
        return ss.lfilter([1 / a0, -2 / a0, 1 / a0],
                          [1, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0], x)

    kl, kr = k_weight(left), k_weight(right)

    def blocks(window, step):
        n, h = int(window * sr), int(step * sr)
        return np.array([-0.691 + 10 * np.log10(max((kl[i:i + n] ** 2).mean() +
                                                    (kr[i:i + n] ** 2).mean(), 1e-12))
                         for i in range(0, len(kl) - n, h)])

    momentary = blocks(0.4, 0.1)
    gated = momentary[momentary > -70]
    absolute = -0.691 + 10 * np.log10(np.mean(10 ** ((gated + 0.691) / 10)))
    gated = momentary[momentary > absolute - 10]
    integrated = -0.691 + 10 * np.log10(np.mean(10 ** ((gated + 0.691) / 10)))

    short = blocks(3.0, 0.5)
    peak = max(np.abs(left).max(), np.abs(right).max())
    true_peak = max(np.abs(ss.resample_poly(left, 4, 1)).max(),
                    np.abs(ss.resample_poly(right, 4, 1)).max())
    mono = (left + right) / 2
    return {
        "integrated": integrated,
        "short_max": short.max(),
        "short_min": short.min(),
        "range": np.percentile(short, 95) - np.percentile(short, 10),
        "peak_db": 20 * np.log10(peak),
        "true_peak_db": 20 * np.log10(true_peak),
        "crest_db": 20 * np.log10(peak / np.sqrt((mono ** 2).mean())),
        "clipped": int(np.sum(np.abs(left) > 0.999) + np.sum(np.abs(right) > 0.999)),
    }


def stereo_profile(left, right, sr):
    mid, side = (left + right) / 2, (left - right) / 2
    rows = []
    for lo, hi in BANDS:
        sos = ss.butter(4, [lo / (sr / 2), min(hi, sr / 2 - 1) / (sr / 2)], btype="band", output="sos")
        m, s = ss.sosfilt(sos, mid), ss.sosfilt(sos, side)
        ratio = 20 * np.log10((np.sqrt((s ** 2).mean()) + 1e-12) / (np.sqrt((m ** 2).mean()) + 1e-12))
        corr = np.corrcoef(ss.sosfilt(sos, left), ss.sosfilt(sos, right))[0, 1]
        rows.append((lo, hi, ratio, corr))
    return rows


def arrangement(mono, sr, bpm, phase):
    """Per-bar RMS and spectral centroid - the shape of the arrangement."""
    import librosa
    bar = 4 * 60.0 / bpm
    hop = 512
    spec = np.abs(librosa.stft(mono, n_fft=4096, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)
    rows = []
    for b in range(int((len(mono) / sr - phase) / bar)):
        t0 = phase + b * bar
        f0, f1 = int(t0 * sr / hop), int((t0 + bar) * sr / hop)
        seg = spec[:, f0:f1]
        if seg.shape[1] < 2:
            break
        chunk = mono[int(t0 * sr):int((t0 + bar) * sr)]
        rows.append({
            "bar": b,
            "time": t0,
            "rms_db": 20 * np.log10(np.sqrt((chunk ** 2).mean()) + 1e-9),
            "centroid": float((seg.mean(1) * freqs).sum() / seg.mean(1).sum()),
            "sub_db": 20 * np.log10(seg[(freqs >= 20) & (freqs < 80)].mean() + 1e-10),
        })
    return rows


def step_grid(mono, sr, bpm, phase, bar_from, bar_to, lo, hi):
    """Normalised onset energy on each of the 16 steps of a bar."""
    import librosa
    bar = 4 * 60.0 / bpm
    step = bar / 16
    hop = 128
    spec = np.abs(librosa.stft(mono, n_fft=1024, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=1024)
    band = spec[(freqs >= lo) & (freqs < hi)].mean(axis=0)
    onset = np.maximum(0, np.diff(band, prepend=band[0]))
    acc = np.zeros(16)
    for b in range(bar_from, bar_to):
        for k in range(16):
            i = int((phase + b * bar + k * step) * sr / hop)
            acc[k] += onset[max(0, i - 3):i + 8].max()
    return acc / (acc.max() + 1e-9)


def sidechain(mono, sr, bpm, phase, bar_from, bar_to, lo=300, hi=6000):
    """Average envelope across one beat, aligned to the downbeat."""
    beat = 60.0 / bpm
    bar = 4 * beat
    sos = ss.butter(4, [lo / (sr / 2), hi / (sr / 2)], btype="band", output="sos")
    env = ss.savgol_filter(np.abs(ss.hilbert(ss.sosfilt(sos, mono))), 301, 2)
    n = int(beat * sr)
    acc, count = np.zeros(n), 0
    for k in range(int((bar_from * bar + phase) / beat), int((bar_to * bar + phase) / beat)):
        i = int(k * beat * sr + phase * sr)
        if i + n < len(env):
            acc += env[i:i + n]
            count += 1
    acc = acc / max(count, 1)
    acc = acc / acc.max()
    depth_db = 20 * np.log10(acc[:int(0.25 * n)].min() + 1e-9)
    recovery_ms = int(np.argmax(acc > 0.9)) / sr * 1000
    return acc, depth_db, recovery_ms


def third_octave(mono, sr, t0, t1):
    import librosa
    seg = mono[int(t0 * sr):int(t1 * sr)]
    spec = np.abs(librosa.stft(seg, n_fft=8192, hop_length=2048))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=8192)
    out, fc = [], 31.25
    while fc < 18000:
        sel = spec[(freqs >= fc / 2 ** (1 / 6)) & (freqs < fc * 2 ** (1 / 6))]
        out.append((fc, 20 * np.log10(sel.mean() + 1e-10)))
        fc *= 2 ** (1 / 3)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio")
    ap.add_argument("--bpm", type=float, help="skip the tempo search and refine around this bpm")
    ap.add_argument("--drop", type=int, nargs=2, metavar=("FROM", "TO"),
                    help="bar range of the drop, for the step grids and sidechain readout")
    args = ap.parse_args()

    import librosa
    sr = 44100
    left, right = load(args.audio, sr)
    mono = (left + right) / 2
    duration = len(mono) / sr

    bpm, phase = tempo_grid(mono, sr, args.bpm)
    bar = 4 * 60.0 / bpm
    bars = int((duration - phase) / bar)

    print(f"file        {os.path.basename(args.audio)}")
    print(f"duration    {int(duration // 60)}:{duration % 60:05.2f}  ({bars} bars)")
    print(f"tempo       {bpm:.2f} BPM   first downbeat {phase:.3f}s   bar {bar:.3f}s")
    print("key         " + ", ".join(f"{name} ({score:.2f})" for score, name in key_estimate(mono, sr)))

    loud = lufs(left, right, sr)
    print(f"\nloudness    {loud['integrated']:.2f} LUFS-I   short-term {loud['short_min']:.1f} to "
          f"{loud['short_max']:.1f}   range {loud['range']:.1f} LU")
    print(f"peaks       sample {loud['peak_db']:+.2f} dBFS   true {loud['true_peak_db']:+.2f} dBTP   "
          f"crest {loud['crest_db']:.1f} dB   {loud['clipped']} clipped samples")

    print("\nstereo width")
    for lo, hi, ratio, corr in stereo_profile(left, right, sr):
        print(f"  {lo:5d}-{hi:<5d} Hz   side/mid {ratio:6.1f} dB   correlation {corr:.3f}")

    rows = arrangement(mono, sr, bpm, phase)
    print("\narrangement  (bar / time / RMS dB / centroid Hz / sub dB)")
    for r in rows:
        meter = "#" * max(0, int((r["rms_db"] + 30)))
        print(f"  {r['bar']:3d} {r['time']:7.2f} {r['rms_db']:7.1f} {r['centroid']:7.0f} "
              f"{r['sub_db']:7.1f}  {meter}")

    if args.drop:
        a, b = args.drop
        labels = "1 e & a 2 e & a 3 e & a 4 e & a".split()
        print(f"\nstep grids over bars {a}-{b}")
        for name, lo, hi in [("kick   35-90Hz", 35, 90), ("snare 180-320Hz", 180, 320),
                             ("clap  1.5-4kHz", 1500, 4000), ("hat    7-14kHz", 7000, 14000),
                             ("bass  150-500Hz", 150, 500)]:
            grid = step_grid(mono, sr, bpm, phase, a, b, lo, hi)
            print(f"  {name:16s} " + " ".join(f"{v:4.2f}" for v in grid))
        print(f"  {'':16s} " + " ".join(f"{l:>4s}" for l in labels))

        env, depth, recovery = sidechain(mono, sr, bpm, phase, a, b)
        print(f"\nsidechain   depth {depth:.1f} dB   90% recovery at {recovery:.0f} ms "
              f"(beat is {60000 / bpm:.0f} ms)")
        print("  envelope  " + " ".join(f"{env[min(int(p * len(env)), len(env) - 1)]:.2f}"
                                        for p in np.linspace(0, 1, 17)))

        print("\nthird-octave balance (dB)      full track | drop")
        full = third_octave(mono, sr, 0, duration)
        drop = third_octave(mono, sr, phase + a * bar, phase + b * bar)
        for (fc, x), (_, y) in zip(full, drop):
            print(f"  {fc:8.0f} Hz {x:9.1f} | {y:6.1f}")


if __name__ == "__main__":
    main()
