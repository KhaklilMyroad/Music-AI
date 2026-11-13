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


REF_SR = 44100           # both files are measured at this rate: band levels must not depend on the file's own
SUB_HZ = 45.0            # below this a comparison of spectra never suggests a boost
TONE_LO, TONE_HI = 38.0, 13000.0     # thirds of an octave that verify_match holds a master to
PEAK_LIMIT = -1.0
PEAK_TOLERANCE = 0.05    # dB of measurement slack on the true peak


def _measured(path: str) -> Audio:
    a = load(path)
    if a.duration < 3.0:
        raise ValueError(f"{os.path.basename(path)}: {a.duration:.1f} s is too short to measure (at least 3 s)")
    if a.sr != REF_SR:
        a = a.resampled(REF_SR)
    return a


def _lufs(a: Audio, path: str) -> float:
    v = mx.integrated_lufs(a)
    if v <= -60.0:
        raise ValueError(f"{os.path.basename(path)} is silent, or nearly: there is nothing to compare")
    return v + (3.01 if a.channels == 1 else 0.0)       # a mono file played on two speakers, as a stereo file of it would measure


def _side(a: Audio) -> float | None:
    """Side against mid in dB, or None when the file has no side signal to speak of (mono, or dual mono)."""
    if a.channels < 2:
        return None
    v = mx.stereo(a).side_to_mid_db
    return float(v) if v > -60.0 else None


def compare(mix_path: str, ref_path: str, max_moves: int = 5) -> dict:
    """Loudness-matched 1/3-octave comparison with a reference track -> gentle EQ Eight moves. Both files are brought
    to one sample rate first, and a band that is empty in either of them is left out."""
    a, r = _measured(mix_path), _measured(ref_path)
    la, lr = _lufs(a, mix_path), _lufs(r, ref_path)
    sa, sr_ = mx.spectrum_profile(a.mono, a.sr), mx.spectrum_profile(r.mono, r.sr)
    ca = np.array(sa.centers)
    n = min(len(sa.levels_db), len(sr_.levels_db))
    la_db, lr_db = np.array(sa.levels_db[:n]), np.array(sr_.levels_db[:n])
    real = (la_db > -60) & (lr_db > -60)                 # levels are relative to each file's loudest band
    raw = np.where(real, lr_db - la_db, np.nan)
    raw = raw - np.nanmedian(raw) if real.any() else raw   # tonal difference only (loudness is handled separately)
    filled = np.where(real, raw, 0.0)
    smooth = np.convolve(np.pad(filled, 1, mode="edge"), np.ones(3) / 3, mode="valid")
    moves = []
    used: list[int] = []
    for o in np.argsort(-np.abs(smooth)):
        if not real[o] or abs(smooth[o]) < 1.5 or len(moves) >= max_moves:
            continue
        if smooth[o] > 0 and ca[o] < SUB_HZ:
            continue        # more sub than the mix has is not something to add on a master from a spectrum: it may be another key
        if raw[o] * smooth[o] <= 0 or abs(raw[o]) < 0.5 * abs(smooth[o]):
            continue        # the band itself is close; the average only says so because of its neighbours
        if any(abs(o - u) < 3 for u in used):
            continue
        used.append(o)
        g = float(np.clip(smooth[o] * 0.7, -6, 6))  # move 70 % of the way: references differ in arrangement too
        # a boost in the low end is a bell, so that it does not lift everything under it as well
        typ = "Low Shelf" if ca[o] < 80 and g < 0 else "High Shelf" if ca[o] > 9000 else "Bell"
        moves.append({"type": typ, "freq_hz": round(float(ca[o]), 0), "gain_db": round(g, 1), "q": 0.7})
    return {"mix_lufs": round(la, 1), "reference_lufs": round(lr, 1), "loudness_gap_db": round(lr - la, 1),
            "band_difference_db": {f"{c:.1f}": round(float(x), 1) for c, x, ok in zip(ca[:n], smooth, real) if ok},
            "band_difference_unsmoothed_db": {f"{c:.1f}": round(float(x), 1) for c, x, ok in zip(ca[:n], raw, real) if ok},
            "eq_moves": sorted(moves, key=lambda m: m["freq_hz"]),
            "stereo_mix_vs_ref": {"mix_side_to_mid_db": _side(a), "ref_side_to_mid_db": _side(r)},
            "channels": {"mix": a.channels, "reference": r.channels}}


def match_chain(mix_path: str, ref_path: str) -> dict:
    """A starting master chain, in Live's own devices and as numbers to set, that moves the mix towards a reference:
    tone (EQ Eight) and loudness (Limiter); a Glue Compressor only when the crest factors are far apart and tone does
    not explain it. One pass closes roughly half of a tonal gap: export, run verify_match, and go again."""
    c = compare(mix_path, ref_path)
    m, r = measure(mix_path, "mix"), measure(ref_path, "reference")
    chain: list[dict] = []
    notes: list[str] = []
    if c["eq_moves"]:
        chain.append({"device": "EQ Eight", "bands": [dict(band=i + 1, **mv) for i, mv in enumerate(c["eq_moves"])],
                      "why": "Tone differences from the reference at matched loudness, moved 70 % of the way: the two songs are "
                             "not the same arrangement. No boost is suggested under 45 Hz."})
    crest_gap = m.crest_db - r.crest_db
    biggest_eq = max((abs(mv["gain_db"]) for mv in c["eq_moves"]), default=0.0)
    if crest_gap > 4.0 and biggest_eq < 3.0:
        chain.append({"device": "Glue Compressor", "ratio": 2, "attack_ms": 10, "release": "Auto",
                      "aim_gain_reduction_db": round(float(min(4.0, crest_gap / 2)), 1),
                      "why": f"The mix has {crest_gap:.1f} dB more crest factor than the reference ({m.crest_db} against {r.crest_db} dB), "
                             "and the tone is close, so the difference is in the dynamics."})
    elif crest_gap > 2.0:
        notes.append(f"Crest factor: the mix has {crest_gap:.1f} dB more than the reference. A difference in tone changes crest "
                     "factor too, so no compressor is suggested: apply the EQ, measure again, then decide by ear.")
    gain = float(np.clip(c["loudness_gap_db"], -12, 12))
    chain.append({"device": "Limiter", "ceiling_db": PEAK_LIMIT, "gain_db": round(gain, 1),
                  "why": f"The reference is {c['loudness_gap_db']:+.1f} LU from the mix ({c['reference_lufs']} against {c['mix_lufs']} LUFS)."})
    shaved = m.true_peak_dbtp + gain - PEAK_LIMIT
    if shaved > 0.5:
        notes.append(f"With this gain the limiter takes about {shaved:.1f} dB off the highest peaks. The gain equals the loudness gap, so "
                     "the result lands short of the reference by part of that; past 3 to 4 dB the limiting becomes audible. "
                     "Verify, and raise the gain only if it still sounds clean.")
    sm, sr_ = c["stereo_mix_vs_ref"]["mix_side_to_mid_db"], c["stereo_mix_vs_ref"]["ref_side_to_mid_db"]
    if sm is not None and sr_ is not None and abs(sm - sr_) > 3:
        notes.append(f"Stereo: the mix's side signal is {sm - sr_:+.1f} dB against the reference's (relative to mid). "
                     "Width is an arrangement and mix decision; a master-bus widener is a last resort.")
    elif (sm is None) != (sr_ is None):
        notes.append("Stereo: " + ("the mix" if sm is None else "the reference") + " has no side signal (mono), the other does. "
                     "Width was not compared.")
    if abs(c["loudness_gap_db"]) > 12:
        notes.append("The loudness gap is larger than a limiter should close: fix the mix level first.")
    return {"chain": chain, "notes": notes, "mix": {"lufs": c["mix_lufs"], "true_peak_dbtp": m.true_peak_dbtp, "crest_db": m.crest_db},
            "reference": {"lufs": c["reference_lufs"], "true_peak_dbtp": r.true_peak_dbtp, "crest_db": r.crest_db},
            "apply": "On the master track, in this order. Read each device with get_device first and set by display value "
                     "(Hz, dB); parameter names differ between Live versions.",
            "then": "Export the master and run verify_match against the same reference."}


def verify_match(master_path: str, ref_path: str, loudness_lu: float = 1.0, band_db: float = 2.5) -> dict:
    """Did the master land near the reference? Five measurements, each a pass or a fail:
      loudness   within `loudness_lu`
      tone       every third of an octave from 40 Hz to 12.5 kHz within `band_db` when averaged with its two
                 neighbours, and within twice that on its own, at matched loudness
      true_peak  at or under -1 dBTP (0.05 dB of measurement slack)
      stereo     side against mid within 4 dB of the reference's, when the reference has a side signal
      dynamics   crest factor within 4 dB of the reference's (a clipped or flattened master fails here)
    A pass means these numbers are close. It is not a verdict on the sound: a narrow resonance inside one band, or
    distortion that leaves the crest factor alone, passes."""
    c = compare(master_path, ref_path)
    m, r = measure(master_path, "master"), measure(ref_path, "reference")
    inside = lambda f: TONE_LO <= float(f) <= TONE_HI
    off = {f: d for f, d in c["band_difference_db"].items() if inside(f) and abs(d) > band_db}
    narrow = {f: d for f, d in c["band_difference_unsmoothed_db"].items() if inside(f) and abs(d) > 2 * band_db}
    sm, sr_ = c["stereo_mix_vs_ref"]["mix_side_to_mid_db"], c["stereo_mix_vs_ref"]["ref_side_to_mid_db"]
    stereo_ok = True if sr_ is None else (sm is not None and abs(sm - sr_) <= 4.0)
    crest_gap = round(m.crest_db - r.crest_db, 1)
    checks = {"loudness": abs(c["loudness_gap_db"]) <= loudness_lu, "tone": not off and not narrow,
              "true_peak": m.true_peak_dbtp <= PEAK_LIMIT + PEAK_TOLERANCE, "stereo": stereo_ok, "dynamics": abs(crest_gap) <= 4.0}
    return {"pass": all(checks.values()), "checks": checks, "loudness_gap_db": c["loudness_gap_db"],
            "bands_still_off_db": off, "single_bands_far_off_db": narrow, "true_peak_dbtp": m.true_peak_dbtp,
            "side_to_mid_db": {"master": sm, "reference": sr_}, "crest_gap_db": crest_gap,
            "master_lufs": c["mix_lufs"], "reference_lufs": c["reference_lufs"],
            "meaning": "Band figures are reference minus master at matched loudness, by the band's centre in Hz. "
                       "bands_still_off_db is averaged over three bands; single_bands_far_off_db is one band alone. "
                       "A pass is five measurements being close, not a verdict on the sound."}
