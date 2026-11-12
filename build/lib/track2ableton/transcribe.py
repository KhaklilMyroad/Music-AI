"""Audio -> MIDI: drums (kit-piece onsets), monophonic lines (bass/vocal/lead), polyphonic parts."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import dsp
from .audio import resample

SR = 22050

# Ableton Drum Rack default pad layout starts at C1 (MIDI 36). GM-compatible note numbers.
DRUM_NOTES = {"kick": 36, "snare": 38, "clap": 39, "closed_hat": 42, "open_hat": 46, "perc": 37}


@dataclass
class Note:
    pitch: int
    start: float      # beats (arrangement time)
    duration: float   # beats
    velocity: int = 100


@dataclass
class DrumHit:
    piece: str
    time: float       # seconds
    strength: float


@dataclass
class Transcription:
    notes: list[Note]
    method: str
    confidence: str
    details: dict = field(default_factory=dict)


def quantize(x: float, grid: float = 0.25) -> float:
    return round(x / grid) * grid


# --------------------------------------------------------------------------------------- drums

def detect_drum_hits(mono: np.ndarray, sr: int, low_source: np.ndarray | None = None) -> list[DrumHit]:
    """low_source: signal used for the kick band (e.g. the full mix when the separator moved the
    kick's low end out of the drum stem)."""
    x = resample(mono[None, :], sr, SR)[0] if sr != SR else mono
    n_fft, hop = 1024, 128
    fps = SR / hop
    # An onset is a rise from the frame before. A hit on the very first sample of the file has no frame before it,
    # so a little silence goes in front, and comes off the hit times at the end.
    lead = 16 * hop
    x = np.concatenate([np.zeros(lead, dtype=x.dtype), x])
    mag = dsp.stft_mag(x, n_fft, hop)
    freqs = dsp.fft_freqs(n_fft, SR)
    logm = np.log1p(100 * mag)

    def band(lo, hi, lm=logm, mg=mag):
        m = (freqs >= lo) & (freqs < hi)
        e = lm[:, m].mean(axis=1)
        return np.maximum(0, np.diff(e, prepend=e[:1])), mg[:, m].mean(axis=1)

    if low_source is not None:
        xl = resample(low_source[None, :], sr, SR)[0] if sr != SR else low_source
        xl = np.concatenate([np.zeros(lead, dtype=xl.dtype), xl])
        mag_l = dsp.stft_mag(xl, n_fft, hop)[: mag.shape[0]]
        low_f, low_e = band(30, 150, np.log1p(100 * mag_l), mag_l)
    else:
        low_f, low_e = band(30, 150)
    high_f, high_e = band(6000, 10500)
    full_f = np.maximum(0, np.diff(logm, axis=0, prepend=logm[:1])).mean(axis=1)
    hits: list[DrumHit] = []

    def picks(f, k=0.8):
        return dsp.peak_pick(dsp.smooth(f, 3), pre=4, post=4, delta=f.std() * k, wait=int(0.05 * fps))

    shares_bands = [(30, 150), (150, 1000), (1000, 5000), (5000, 11000)]
    masks = [(freqs >= lo) & (freqs < hi) for lo, hi in shares_bands]

    def attack_profile(p):
        """Per-band mean log-magnitude increase of this onset (low, body, mid, high), best-aligned
        within +-2 frames. Log domain keeps a quiet snare visible on top of a loud kick."""
        best, best_v = p, -1.0
        for q in range(max(3, p - 2), min(logm.shape[0] - 3, p + 3)):
            v = float(np.clip(logm[q:q + 3].mean(axis=0) - logm[q - 3], 0, None).sum())
            if v > best_v:
                best, best_v = q, v
        inc = np.clip(logm[best:best + 3].mean(axis=0) - logm[max(0, best - 3)], 0, None)
        return np.array([inc[m].mean() if m.any() else 0.0 for m in masks])

    # 1) kicks: low-band onsets
    for p in picks(low_f):
        hits.append(DrumHit("kick", p / fps, float(low_f[p])))
    kick_frames = np.array([int(h.time * fps) for h in hits])
    # 2) everything else: broadband onsets classified by the spectral shape of the attack
    for p in picks(full_f, 0.6):
        prof = attack_profile(p)
        mx_ = prof.max() + 1e-9
        r = prof / mx_
        near_kick = bool(kick_frames.size) and np.min(np.abs(kick_frames - p)) <= 3
        if r[3] >= 0.4 and r[1] >= 0.2:
            seg = full_f[max(0, p - 2): p + int(0.035 * fps)]
            bursts = int(np.sum((seg[1:-1] > seg[:-2]) & (seg[1:-1] > seg[2:]) & (seg[1:-1] > 0.4 * full_f[p])))
            hits.append(DrumHit("clap" if bursts >= 3 else "snare", p / fps, float(full_f[p])))
        elif r[3] >= 0.99 and r[1] < 0.15:
            tail = high_e[p: p + int(0.4 * fps)]
            if tail.size < 3:
                continue
            below = np.where(tail < tail[0] * 0.1)[0]
            decay = (below[0] if below.size else tail.size) / fps
            hits.append(DrumHit("open_hat" if decay > 0.14 else "closed_hat", p / fps, float(full_f[p])))
        elif not near_kick and r[0] < 0.5:
            hits.append(DrumHit("perc", p / fps, float(full_f[p])))
    # Drop weak detections (bleed, separation artefacts) with a *local* reference: a kick under a
    # busy bass line has a smaller log-domain attack than an exposed one, so compare within ~4 s.
    kept = []
    for piece in {h.piece for h in hits}:
        ph = [h for h in hits if h.piece == piece]
        t = np.array([h.time for h in ph])
        st = np.array([h.strength for h in ph])
        for h in ph:
            near = st[np.abs(t - h.time) <= 2.0]
            if h.strength >= 0.5 * np.percentile(near, 90):
                kept.append(h)
    for h in kept:
        h.time = max(0.0, h.time - lead / SR)
    kept.sort(key=lambda h: h.time)
    return kept


def drums_to_midi(hits: list[DrumHit], to_beats: Callable[[float], float]) -> Transcription:
    notes = []
    by_piece: dict[str, list[float]] = {}
    for h in hits:
        by_piece.setdefault(h.piece, []).append(h.strength)
    norms = {k: np.percentile(v, 90) if v else 1 for k, v in by_piece.items()}
    seen = set()
    for h in hits:
        b = quantize(float(to_beats(h.time)))
        if b < 0:
            continue
        key = (h.piece, b)
        if key in seen:
            continue
        seen.add(key)
        vel = int(np.clip(60 + 67 * h.strength / (norms[h.piece] + 1e-9), 30, 127))
        notes.append(Note(DRUM_NOTES[h.piece], b, 0.25, vel))
    patterns = drum_patterns(notes)
    return Transcription(notes, "band-onset drum transcription", "medium",
                         {"counts": {k: len(v) for k, v in by_piece.items()}, "patterns": patterns})


def drum_patterns(notes: list[Note], beats_per_bar: int = 4) -> dict[str, str]:
    """Most common one-bar 16-step pattern per kit piece, e.g. kick 'x...x...x...x...'."""
    steps = beats_per_bar * 4
    out = {}
    inv = {v: k for k, v in DRUM_NOTES.items()}
    for pitch in sorted({n.pitch for n in notes}):
        bars: dict[int, list[str]] = {}
        for n in notes:
            if n.pitch != pitch:
                continue
            bar = int(n.start // beats_per_bar)
            step = int(round((n.start % beats_per_bar) * 4)) % steps
            bars.setdefault(bar, ["."] * steps)[step] = "x"
        if not bars:
            continue
        pats = ["".join(v) for v in bars.values()]
        vals, counts = np.unique(pats, return_counts=True)
        out[inv.get(pitch, str(pitch))] = str(vals[int(np.argmax(counts))])
    return out


def extract_one_shots(mono: np.ndarray, sr: int, hits: list[DrumHit], max_len: float = 0.7) -> dict[str, np.ndarray]:
    """Cut the cleanest-looking hit of each kit piece (longest gap to the next hit, strong onset)."""
    out = {}
    times = np.array([h.time for h in hits])
    for piece in {h.piece for h in hits}:
        best, best_score = None, -1.0
        for h in hits:
            if h.piece != piece:
                continue
            later = times[times > h.time + 0.01]
            gap = (later[0] - h.time) if later.size else max_len
            score = min(gap, max_len) * h.strength
            if score > best_score:
                best, best_score = (h.time, min(gap, max_len)), score
        if best is None:
            continue
        t, length = best
        a = max(0, int((t - 0.004) * sr))
        b = min(mono.size, a + int(max(length, 0.08) * sr))
        clip = mono[a:b].copy()
        fade = min(clip.size, int(0.01 * sr))
        if fade > 0:
            clip[-fade:] *= np.linspace(1, 0, fade)
        out[piece] = clip
    return out


# --------------------------------------------------------------------------------------- monophonic

def mono_to_midi(mono: np.ndarray, sr: int, to_beats: Callable[[float], float], fmin: float, fmax: float,
                 tuning_cents: float = 0.0, min_dur: float = 0.06) -> Transcription:
    x = resample(mono[None, :], sr, SR)[0] if sr != SR else mono
    hop = 128
    fps = SR / hop
    frame_len = 2048 if fmin < 60 else 1024
    f0, ap = dsp.yin(x, SR, fmin, fmax, frame_len, hop)
    env = dsp.envelope(x, SR, hop)[: f0.size]
    if env.size < f0.size:
        env = np.pad(env, (0, f0.size - env.size))
    gate = env > env.max() * 10 ** (-40 / 20)
    voiced = (f0 > 0) & (ap < 0.3) & gate
    midi = np.where(voiced, dsp.hz_to_midi(f0) - tuning_cents / 100.0, 0)
    from scipy.ndimage import median_filter
    midi_r = np.where(voiced, np.round(median_filter(midi, 7)), 0).astype(int)
    # onset re-articulation inside one pitch
    flux = np.maximum(0, np.diff(np.log(env + 1e-6), prepend=0))
    rearts = set(dsp.peak_pick(flux, 3, 3, flux.std() * 1.5, int(0.05 * fps)).tolist())
    notes: list[Note] = []
    notes_sec: list[tuple[float, float]] = []
    glides = 0
    i = 0
    n = midi_r.size
    while i < n:
        if midi_r[i] <= 0:
            i += 1
            continue
        j = i + 1
        while j < n and midi_r[j] == midi_r[i] and j not in rearts:
            j += 1
        dur = (j - i) / fps
        if dur >= min_dur:
            t0, t1 = i / fps, j / fps
            notes_sec.append((t0, t1))
            b0, b1 = float(to_beats(t0)), float(to_beats(t1))
            s = quantize(b0)
            e = max(s + 0.25, quantize(b1))
            vel = int(np.clip(40 + 87 * env[i:j].max() / (env.max() + 1e-9), 1, 127))
            if notes and notes[-1].pitch != midi_r[i] and abs(notes[-1].pitch - midi_r[i]) >= 1:
                # glide/portamento: voiced frames passing through intermediate pitches between the notes
                seg = midi[max(0, i - 8): i + 2]
                lo_p, hi_p = sorted((notes[-1].pitch, int(midi_r[i])))
                between = (seg > lo_p + 0.3) & (seg < hi_p - 0.3)
                if seg.size and np.all(seg > 0) and between.sum() >= 3:
                    glides += 1
            if notes and notes[-1].pitch == midi_r[i] and abs(notes[-1].start + notes[-1].duration - s) < 1e-6 and (i not in rearts):
                notes[-1].duration = e - notes[-1].start
            else:
                if notes and notes[-1].start + notes[-1].duration > s:
                    notes[-1].duration = max(0.25, s - notes[-1].start)
                if s >= 0:
                    notes.append(Note(int(midi_r[i]), s, e - s, vel))
        i = j
    voiced_ratio = float(voiced.mean()) if voiced.size else 0.0
    # Pitch-correction signature: very small deviation of voiced frames from semitone centres.
    dev = np.abs(midi[voiced] - np.round(midi[voiced])) if voiced.any() else np.array([0.5])
    return Transcription(notes, "YIN monophonic pitch tracking", "medium" if voiced_ratio > 0.2 else "low", {
        "voiced_ratio": voiced_ratio,
        "glide_count": glides,
        "glide_ratio": glides / max(1, len(notes)),
        "median_cents_off_grid": float(np.median(dev) * 100),
        "range": [int(min((x.pitch for x in notes), default=0)), int(max((x.pitch for x in notes), default=0))],
        "f0_median_hz": float(np.median(f0[voiced])) if voiced.any() else 0.0,
        "_f0": f0, "_hop_s": hop / SR, "_x22k": x, "_notes_sec": notes_sec,
    })


# --------------------------------------------------------------------------------------- polyphonic

def basic_pitch_available() -> bool:
    return importlib.util.find_spec("basic_pitch") is not None


def poly_to_midi(mono: np.ndarray, sr: int, to_beats: Callable[[float], float], tuning_cents: float = 0.0,
                 lo: int = 36, hi: int = 96, max_poly: int = 6) -> Transcription:
    """Harmonic-sum salience multi-pitch estimate. Rough; best for pads/chords/keys."""
    x = resample(mono[None, :], sr, SR)[0] if sr != SR else mono
    n_fft, hop = 4096, 512
    fps = SR / hop
    mag = dsp.stft_mag(x, n_fft, hop)
    df = SR / n_fft
    pitches = np.arange(lo, hi + 1)
    f0s = dsp.midi_to_hz(pitches + tuning_cents / 100.0)
    sal = np.zeros((mag.shape[0], pitches.size), dtype=np.float32)
    logm = np.log1p(50 * mag / (mag.max() + 1e-12))
    for h in range(1, 7):
        bins = f0s * h / df
        ok = bins < mag.shape[1] - 1
        b0 = np.floor(bins[ok]).astype(int)
        fr = (bins[ok] - b0).astype(np.float32)
        vals = (1 - fr) * logm[:, b0] + fr * logm[:, b0 + 1]
        # max over +-1 bin for robustness
        vals = np.maximum(vals, np.maximum(logm[:, np.clip(b0 - 1, 0, None)], logm[:, np.clip(b0 + 2, None, mag.shape[1] - 1)]) * 0.8)
        sal[:, ok] += (0.84 ** (h - 1)) * vals
    # Penalise sub-octave ghosts: a pitch is weak if its own fundamental bin is weak.
    fund = np.stack([logm[:, min(int(round(f / df)), mag.shape[1] - 1)] for f in f0s], axis=1)
    sal *= np.clip(fund / (fund.max(axis=1, keepdims=True) + 1e-9) * 2, 0, 1)
    active = np.zeros_like(sal, dtype=bool)
    frame_max = sal.max(axis=1, keepdims=True)
    global_thr = np.percentile(frame_max, 40) * 0.5
    for t in range(sal.shape[0]):
        row = sal[t]
        cand = np.argsort(row)[::-1][:max_poly]
        for c in cand:
            if row[c] >= 0.6 * frame_max[t, 0] and row[c] > global_thr:
                active[t, c] = True
    notes: list[Note] = []
    min_frames = int(0.1 * fps)
    for k in range(pitches.size):
        col = active[:, k]
        t = 0
        while t < col.size:
            if not col[t]:
                t += 1
                continue
            u = t
            while u < col.size and (col[u] or (u + 1 < col.size and col[u + 1])):
                u += 1
            if u - t >= min_frames:
                s, e = quantize(float(to_beats(t / fps))), quantize(float(to_beats(u / fps)))
                if s >= 0:
                    vel = int(np.clip(50 + 70 * sal[t:u, k].mean() / (frame_max.max() + 1e-9), 1, 127))
                    notes.append(Note(int(pitches[k]), s, max(0.25, e - s), vel))
            t = u
    notes.sort(key=lambda n: (n.start, n.pitch))
    poly = float(np.mean(active.sum(axis=1)[active.any(axis=1)])) if active.any() else 0.0
    return Transcription(notes, "harmonic-salience multi-pitch", "low", {"mean_polyphony": poly})


def basic_pitch_to_midi(path: str, to_beats: Callable[[float], float]) -> Transcription:
    """Spotify basic-pitch (Apache-2.0), if installed. API: basic_pitch.inference.predict -> (model_output, midi, note_events)."""
    from basic_pitch.inference import predict  # type: ignore

    _, _, events = predict(path)
    notes = []
    for ev in events:
        start, end, pitch, amp = float(ev[0]), float(ev[1]), int(ev[2]), float(ev[3])
        s, e = quantize(float(to_beats(start))), quantize(float(to_beats(end)))
        if s >= 0:
            notes.append(Note(pitch, s, max(0.25, e - s), int(np.clip(amp * 127, 1, 127))))
    return Transcription(notes, "basic-pitch (neural)", "medium-high")


def chords_to_midi(chords, to_beats: Callable[[float], float], octave_base: int = 48) -> Transcription:
    notes = []
    for c in chords:
        if c.root < 0:
            continue
        s, e = quantize(float(to_beats(c.start)), 0.5), quantize(float(to_beats(c.end)), 0.5)
        if e <= s or s < 0:
            continue
        # keep voicings in a fixed register around the base octave (close voicing)
        for p in c.pitches(octave_base):
            while p >= octave_base + 14:
                p -= 12
            notes.append(Note(p, s, e - s, 90))
    return Transcription(notes, "chord detection voiced as block chords", "medium")
