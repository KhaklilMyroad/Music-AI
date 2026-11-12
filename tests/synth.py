"""Synthetic test songs with known ground truth."""
from __future__ import annotations

import numpy as np

SR = 44100


def midi_hz(m):
    return 440.0 * 2 ** ((np.asarray(m, dtype=float) - 69) / 12)


def saw(f, t, n_harm=40):
    out = np.zeros_like(t)
    for k in range(1, n_harm + 1):
        if f * k > SR / 2.2:
            break
        out += np.sin(2 * np.pi * f * k * t) / k
    return out * (2 / np.pi)


def square(f, t, n_harm=40):
    out = np.zeros_like(t)
    for k in range(1, n_harm + 1, 2):
        if f * k > SR / 2.2:
            break
        out += np.sin(2 * np.pi * f * k * t) / k
    return out * (4 / np.pi)


def kick(sr=SR):
    t = np.arange(int(0.35 * sr)) / sr
    f = 50 + 120 * np.exp(-t * 35)
    ph = 2 * np.pi * np.cumsum(f) / sr
    fade = np.minimum(1, (t[-1] - t) / 0.03)  # no click at the end of the sample
    return np.sin(ph) * np.exp(-t * 9) * fade


def hat(sr=SR, seed=0, open_=False):
    rng = np.random.default_rng(seed)
    n = int((0.3 if open_ else 0.05) * sr)
    x = rng.standard_normal(n)
    x = np.diff(np.diff(x, prepend=0), prepend=0)  # crude high-pass
    t = np.arange(n) / sr
    return 0.25 * x * np.exp(-t * (10 if open_ else 80))


def snare(sr=SR, seed=1):
    rng = np.random.default_rng(seed)
    n = int(0.2 * sr)
    t = np.arange(n) / sr
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25)
    noise = rng.standard_normal(n) * np.exp(-t * 18)
    return 0.5 * body + 0.35 * noise


def reverb_tail(x, rt60, sr=SR, seed=3):
    rng = np.random.default_rng(seed)
    n = int(rt60 * sr)
    t = np.arange(n) / sr
    ir = rng.standard_normal(n) * 10 ** (-3 * t / rt60)  # -60 dB at rt60
    ir[0] = 0
    ir /= np.sqrt(np.sum(ir ** 2))
    from scipy.signal import fftconvolve
    return fftconvolve(x, ir)[: x.size]


def make_song(bpm=124.0, bars=32, key_root=57, seed=0, offset_s=0.0, sidechain=True, stereo_pad=True):
    """Returns (stereo float32 array (2, n), ground_truth dict).

    Layout: bars 0-7 intro (kick+hats), 8-15 verse (+bass), 16-23 drop (+pad, snare, louder),
    24-31 breakdown (pad only)."""
    beat = 60.0 / bpm
    n = int((bars * 4 * beat + offset_s + 2.0) * SR)
    L = np.zeros(n)
    R = np.zeros(n)
    drums = np.zeros(n)
    bass = np.zeros(n)
    pad_l = np.zeros(n)
    pad_r = np.zeros(n)
    k = kick()
    prog = [(0, "m"), (8, ""), (3, ""), (10, "")]  # Am F C G relative to A
    kick_times = []

    def add(buf, sig, t0, gain=1.0):
        i = int(round(t0 * SR))
        if i >= buf.size:
            return
        j = min(buf.size, i + sig.size)
        buf[i:j] += gain * sig[: j - i]

    for bar in range(bars):
        sect = bar // 8
        for b in range(4):
            t0 = offset_s + (bar * 4 + b) * beat
            if sect in (0, 1, 2):
                add(drums, k, t0, 0.9)
                kick_times.append(t0)
            if sect in (0, 1, 2):
                add(drums, hat(seed=bar * 4 + b), t0 + beat / 2, 0.8)
            if sect == 2 and b in (1, 3):
                add(drums, snare(), t0, 0.7)
        root_off, q = prog[bar % 4]
        chord_root = key_root + root_off
        tb = offset_s + bar * 4 * beat
        if sect in (1, 2):
            # 8th-note saw bass on the chord root, octave 2
            f = midi_hz(chord_root - 24)
            for e in range(8):
                t = np.arange(int(beat / 2 * 0.9 * SR)) / SR
                env = np.minimum(1, t / 0.005) * np.exp(-t * 2)
                add(bass, 0.5 * saw(f, t) * env, tb + e * beat / 2)
        if sect in (2, 3):
            ivs = [0, 3, 7] if q == "m" else [0, 4, 7]
            t = np.arange(int(4 * beat * SR)) / SR
            env = np.minimum(1, t / 0.25) * np.minimum(1, (4 * beat - t) / 0.05)
            for iv in ivs:
                f = midi_hz(chord_root + iv)
                add(pad_l, 0.12 * saw(f * 1.003, t, 12) * env, tb)
                add(pad_r, 0.12 * saw(f * 0.997, t, 12) * env, tb)
    if sidechain:
        # duck bass and pad after each kick: -10 dB, ~120 ms recovery
        g = np.ones(n)
        for kt in kick_times:
            i = int(kt * SR)
            t = np.arange(int(beat * SR)) / SR
            duck = 1 - (1 - 10 ** (-10 / 20)) * np.exp(-t / 0.12)
            j = min(n, i + t.size)
            g[i:j] = np.minimum(g[i:j], duck[: j - i])
        bass *= g
        pad_l *= g
        pad_r *= g
    pad_l = pad_l + 0.5 * reverb_tail(pad_l, 1.8, seed=4)
    pad_r = pad_r + 0.5 * reverb_tail(pad_r, 1.8, seed=5)
    if not stereo_pad:
        pad_l = pad_r = 0.5 * (pad_l + pad_r)
    L = drums + bass + pad_l
    R = drums + bass + pad_r
    out = np.stack([L, R])
    out /= np.max(np.abs(out)) * 1.12
    truth = {"bpm": bpm, "key_root_pc": key_root % 12, "mode": "minor", "first_downbeat": offset_s,
             "chords": ["Am", "F", "C", "G"], "rt60_pad": 1.8, "sidechain_db": 10, "bars": bars,
             "stems": {"drums": drums, "bass": bass, "pad": np.stack([pad_l, pad_r])}}
    return out.astype(np.float32), truth


def drift_clock(bpm=129.6, beats=400, wobble=0.004, ramp=0.006, wobble_beats=96.0):
    """A tempo that is not constant: `bpm` times (1 + a slow sine of +-wobble + a linear ramp of `ramp` over the song).
    Returns seconds(beat) for fractional beats."""
    b = np.arange(0, beats + 8, 1 / 32)
    tempo = bpm * (1 + wobble * np.sin(2 * np.pi * b / wobble_beats) + ramp * b / beats)
    sec = np.concatenate([[0.0], np.cumsum(60.0 / tempo[:-1] / 32)])
    return lambda x: np.interp(np.asarray(x, dtype=float), b, sec)


def render_parts(parts: dict, clock, offset_s=0.0, tail_s=2.0):
    """parts: {"kick": [beat], "clap": [beat], "hat": [beat], "bass": [(pitch, beat, beats)], "pad": [(pitch, beat, beats)]}.
    `clock` maps beats to seconds. Returns {name: mono float32} stems of equal length, sample rate SR."""
    last = 0.0
    for name, ev in parts.items():
        for e in ev:
            last = max(last, float(e) if np.isscalar(e) else e[1] + e[2])
    n = int((float(clock(last)) + offset_s + tail_s) * SR)
    out = {name: np.zeros(n) for name in parts}

    def add(buf, sig, t0, gain=1.0):
        i = int(round(t0 * SR))
        j = min(buf.size, i + sig.size)
        if j > i:
            buf[i:j] += gain * sig[: j - i]

    k, s = kick(), snare()
    for name, ev in parts.items():
        for q, e in enumerate(ev):
            if name == "kick":
                add(out[name], k, offset_s + float(clock(e)), 0.9)
            elif name == "clap":
                add(out[name], s, offset_s + float(clock(e)), 0.7)
            elif name == "hat":
                add(out[name], hat(seed=q), offset_s + float(clock(e)), 0.8)
            else:
                pitch, b0, dur = e
                t0, t1 = float(clock(b0)), float(clock(b0 + dur))
                t = np.arange(int((t1 - t0) * 0.92 * SR)) / SR
                if name == "bass":
                    env = np.minimum(1, t / 0.005) * np.exp(-t * 2) * np.minimum(1, (t[-1] - t) / 0.01 + 1e-9)
                    add(out[name], 0.5 * saw(midi_hz(pitch), t) * env, offset_s + t0)
                else:
                    env = np.minimum(1, t / 0.03) * np.minimum(1, (t[-1] - t) / 0.03 + 1e-9)
                    add(out[name], 0.15 * saw(midi_hz(pitch), t, 12) * env, offset_s + t0)
    return {name: x.astype(np.float32) for name, x in out.items()}
