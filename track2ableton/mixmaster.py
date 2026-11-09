"""Mix & master analysis: waveform / spectrogram images, per-track and master metrics,
masking between tracks, reference-track matching, and suggestions phrased as Ableton actions.

All numbers are measurements of the audio files given. Targets (e.g. streaming loudness) are
user-selectable conventions, not rules; platform normalisation values change over time and
should be checked against each platform's current documentation.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from . import dsp, mixanalysis as mx, png
from .audio import Audio, load

# Commonly cited loudness-normalisation reference levels (integrated LUFS). Verify before relying on them.
TARGETS = {"streaming": -14.0, "apple": -16.0, "broadcast_ebu_r128": -23.0, "club": -9.0}

BANDS = [("sub", 20, 60), ("bass", 60, 250), ("low-mid", 250, 800), ("mid", 800, 2500),
         ("presence", 2500, 6000), ("air", 6000, 20000)]


# ------------------------------------------------------------------------------------------ images

def waveform_png(audio: Audio, width: int = 1200, lane_h: int = 110) -> bytes:
    """Min/max peak + RMS per pixel column, one lane per channel; clipped samples marked red."""
    chans = audio.data[:2]
    h = lane_h * len(chans)
    img = np.full((h, width, 3), 18, np.uint8)
    n = chans.shape[1]
    edges = np.linspace(0, n, width + 1).astype(int)
    for c, x in enumerate(chans):
        top = c * lane_h
        mid = top + lane_h // 2
        img[mid, :] = (60, 60, 70)
        for col in range(width):
            seg = x[edges[col]:max(edges[col] + 1, edges[col + 1])]
            if seg.size == 0:
                continue
            lo, hi = float(seg.min()), float(seg.max())
            rms = float(np.sqrt(np.mean(seg.astype(np.float64) ** 2)))
            y0 = int(mid - hi * (lane_h / 2 - 2))
            y1 = int(mid - lo * (lane_h / 2 - 2))
            img[max(top, y0):min(top + lane_h, y1 + 1), col] = (90, 150, 230)
            r0, r1 = int(mid - rms * (lane_h / 2 - 2)), int(mid + rms * (lane_h / 2 - 2))
            img[max(top, r0):min(top + lane_h, r1 + 1), col] = (170, 210, 255)
            if max(abs(lo), abs(hi)) >= 0.999:
                img[top:top + 6, col] = (230, 50, 50)
        img[top + lane_h - 1, :] = (40, 40, 48)
    return png.encode(img)


def spectrogram_png(audio: Audio, width: int = 1200, height: int = 320, fmin: float = 20.0, db_range: float = 90.0) -> tuple[bytes, dict]:
    """Log-frequency spectrogram (mono sum). Returns PNG and the axis description."""
    mono = audio.mono
    sr = audio.sr
    n_fft = 4096
    hop = max(256, int(mono.size / max(1, width * 2)))
    mag = dsp.stft_mag(mono, n_fft, hop)
    freqs = dsp.fft_freqs(n_fft, sr)
    fmax = sr / 2
    rows = np.geomspace(fmin, fmax, height)
    idx = np.clip(np.searchsorted(freqs, rows), 1, freqs.size - 1)
    S = 20 * np.log10(mag[:, idx] + 1e-9)  # (frames, height)
    # time-bin to width columns (max keeps transients visible)
    cols = np.array_split(np.arange(S.shape[0]), width)
    S = np.stack([S[c].max(axis=0) if c.size else np.full(height, -200.0) for c in cols], axis=1)  # (height, width)
    top = S.max()
    V = (S - (top - db_range)) / db_range
    img = png.colormap(V[::-1])  # low frequencies at the bottom
    # octave grid lines at 100 Hz, 1 kHz, 10 kHz
    for f in (100, 1000, 10000):
        if fmin < f < fmax:
            y = height - 1 - int(np.searchsorted(rows, f))
            img[y, ::4] = (200, 200, 200)
    axis = {"x": f"time 0..{audio.duration:.2f} s, {width} px", "y": f"log frequency {fmin:.0f} Hz (bottom) .. {fmax:.0f} Hz (top)",
            "grid_lines_hz": [100, 1000, 10000], "colour": f"dB re. loudest bin, range {db_range:.0f} dB (dark = quiet)"}
    return png.encode(img), axis


# ------------------------------------------------------------------------------------------ metrics

@dataclass
class TrackMetrics:
    name: str
    path: str
    duration_s: float
    integrated_lufs: float
    peak_dbfs: float
    true_peak_dbtp: float
    crest_db: float
    lra_lu: float
    band_db: dict[str, float]          # mean power per band, dB re. full scale (relative across tracks)
    spectrum: dict[str, Any]
    stereo: dict[str, Any]
    clipped_samples: int
    dc_offset: float
    issues: list[str] = field(default_factory=list)


def band_energies(mono: np.ndarray, sr: int) -> dict[str, float]:
    n_fft = 8192
    p = (dsp.stft_mag(mono, n_fft, n_fft // 2).astype(np.float64) ** 2).mean(axis=0) / (n_fft ** 2)
    freqs = dsp.fft_freqs(n_fft, sr)
    return {name: round(float(10 * np.log10(p[(freqs >= lo) & (freqs < hi)].sum() + 1e-20)), 1) for name, lo, hi in BANDS}


def measure(path: str, name: str | None = None) -> TrackMetrics:
    a = load(path)
    m = a.mono
    peak = float(np.max(np.abs(a.data))) if a.data.size else 0.0
    rms = float(np.sqrt(np.mean(m.astype(np.float64) ** 2))) if m.size else 0.0
    st = mx.stereo(a)
    tm = TrackMetrics(
        name=name or os.path.splitext(os.path.basename(path))[0], path=path, duration_s=round(a.duration, 2),
        integrated_lufs=round(mx.integrated_lufs(a), 1), peak_dbfs=round(float(mx.db(peak)), 2),
        true_peak_dbtp=round(mx.true_peak_db(a), 2), crest_db=round(float(mx.db(peak) - mx.db(rms)), 1),
        lra_lu=round(mx.loudness_range(a), 1), band_db=band_energies(m, a.sr), spectrum=asdict(mx.spectrum_profile(m, a.sr)),
        stereo=asdict(st), clipped_samples=int(np.sum(np.abs(a.data) >= 0.9999)), dc_offset=round(float(np.mean(m)), 5))
    if tm.clipped_samples > 0:
        tm.issues.append(f"{tm.clipped_samples} samples at full scale (possible clipping).")
    if abs(tm.dc_offset) > 0.005:
        tm.issues.append(f"DC offset {tm.dc_offset:+.4f}: add a high-pass (EQ Eight Low Cut ~20 Hz).")
    if a.channels == 2 and st.correlation < 0:
        tm.issues.append(f"Negative L/R correlation ({st.correlation}): phase problem, collapses in mono.")
    if a.channels == 2 and st.side_to_mid_db > -20 and not st.low_mono_below_hz and tm.band_db["sub"] > tm.band_db["mid"] - 6:
        tm.issues.append("Side energy reaches into the low end: consider Utility > Bass Mono (~120 Hz).")
    return tm


# ------------------------------------------------------------------------------------------ mix

def masking(tracks: list[TrackMetrics], threshold_db: float = 6.0) -> list[dict]:
    """Pairs of tracks that are both strong in the same band (each within `threshold_db` of the
    louder one, and that band within 10 dB of each track's own strongest band)."""
    out = []
    for i in range(len(tracks)):
        for j in range(i + 1, len(tracks)):
            a, b = tracks[i], tracks[j]
            for band, *_ in BANDS:
                ea, eb = a.band_db[band], b.band_db[band]
                if ea < max(a.band_db.values()) - 10 or eb < max(b.band_db.values()) - 10:
                    continue
                if abs(ea - eb) <= threshold_db:
                    quieter = a if ea < eb else b
                    louder = b if quieter is a else a
                    out.append({"band": band, "tracks": [a.name, b.name], "levels_db": [ea, eb],
                                "suggestion": f"Carve {band} in '{quieter.name}' (EQ Eight bell -2..-4 dB) or sidechain it to "
                                              f"'{louder.name}', so one of them owns the {band} range."})
    return out


def mix_report(files: dict[str, str]) -> dict:
    tracks = [measure(p, n) for n, p in files.items()]
    loud = sorted(tracks, key=lambda t: -t.integrated_lufs)
    actions = []
    for t in tracks:
        for iss in t.issues:
            actions.append({"track": t.name, "why": iss})
    sum_peak = 20 * np.log10(sum(10 ** (t.peak_dbfs / 20) for t in tracks) + 1e-12)
    if sum_peak > -3:
        actions.append({"track": "all", "why": f"Worst-case summed peak {sum_peak:.1f} dBFS: lower track faders "
                                               f"~{sum_peak + 6:.0f} dB in total to keep 6 dB of headroom on the master before limiting."})
    return {"tracks": [asdict(t) for t in tracks], "loudness_order": [t.name for t in loud],
            "masking": masking(tracks), "actions": actions}


# ------------------------------------------------------------------------------------------ master

def master_report(path: str, target: str | float = "streaming", reference: str | None = None) -> dict:
    t = measure(path, "master")
    target_lufs = float(TARGETS.get(target, target)) if not isinstance(target, (int, float)) else float(target)
    act: list[dict] = []
    diff = target_lufs - t.integrated_lufs
    if abs(diff) > 0.5:
        act.append({"device": "Limiter (Master, last)", "why": f"Integrated {t.integrated_lufs} LUFS vs target {target_lufs}: "
                    + (f"raise input gain by ~{diff:.1f} dB" if diff > 0 else f"reduce gain by ~{-diff:.1f} dB")
                    + " and re-measure (limiting changes loudness non-linearly)."})
    if t.true_peak_dbtp > -1.0:
        act.append({"device": "Limiter (Master)", "why": f"True peak {t.true_peak_dbtp} dBTP: set Ceiling to -1.0 dB "
                                                         "(common recommendation to leave room for lossy encoding)."})
    if t.crest_db < 6:
        act.append({"device": "Glue Compressor / Limiter", "why": f"Crest factor {t.crest_db} dB is very low (heavily limited); "
                                                                  "transients may be flattened. Back off limiting if punch is lacking."})
    for iss in t.issues:
        act.append({"device": "Master", "why": iss})
    out: dict[str, Any] = {"metrics": asdict(t), "target_lufs": target_lufs, "actions": act}
    if reference:
        out["reference"] = compare(path, reference)
        for mv in out["reference"]["eq_moves"]:
            act.append({"device": "EQ Eight (Master)", "why": f"Match reference: {mv['type']} {mv['freq_hz']} Hz {mv['gain_db']:+.1f} dB"})
    return out


def compare(mix_path: str, ref_path: str, max_moves: int = 5) -> dict:
    """Loudness-matched 1/3-octave comparison with a reference track -> gentle EQ Eight moves."""
    a, r = load(mix_path), load(ref_path)
    la, lr = mx.integrated_lufs(a), mx.integrated_lufs(r)
    sa, sr_ = mx.spectrum_profile(a.mono, a.sr), mx.spectrum_profile(r.mono, r.sr)
    ca = np.array(sa.centers)
    n = min(len(sa.levels_db), len(sr_.levels_db))
    # spectrum_profile normalises to each track's loudest band; re-anchor by loudness difference via mean level
    d = np.array(sr_.levels_db[:n]) - np.array(sa.levels_db[:n])
    d = d - np.median(d)  # tonal difference only (loudness handled separately)
    smooth = np.convolve(np.pad(d, 1, mode="edge"), np.ones(3) / 3, mode="valid")
    moves = []
    order = np.argsort(-np.abs(smooth))
    used: list[int] = []
    for o in order:
        if abs(smooth[o]) < 1.5 or len(moves) >= max_moves or ca[o] < 25:
            continue
        if any(abs(o - u) < 3 for u in used):
            continue
        used.append(o)
        g = float(np.clip(smooth[o] * 0.7, -6, 6))  # move 70 % of the way: references differ in arrangement too
        typ = "Low Shelf" if ca[o] < 80 else "High Shelf" if ca[o] > 9000 else "Bell"
        moves.append({"type": typ, "freq_hz": round(float(ca[o]), 0), "gain_db": round(g, 1), "q": 0.7})
    return {"mix_lufs": round(la, 1), "reference_lufs": round(lr, 1), "loudness_gap_db": round(lr - la, 1),
            "band_difference_db": {f"{c:.0f}": round(float(x), 1) for c, x in zip(ca[:n], smooth)},
            "eq_moves": sorted(moves, key=lambda m: m["freq_hz"]),
            "stereo_mix_vs_ref": {"mix_side_to_mid_db": mx.stereo(a).side_to_mid_db, "ref_side_to_mid_db": mx.stereo(r).side_to_mid_db}}
