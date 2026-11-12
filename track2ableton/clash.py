"""Do two layers get in each other's way? Measured in time and in frequency.

An average spectrum cannot answer that: a kick and an off-beat bass live in the same band and never meet, and a
pad can sit under a vocal for the whole song. Here every layer becomes a map of how loud it is in each third of an
octave every 46 ms, and two layers clash to the extent that they are loud in the same cell of that map.

The number for "A under B" is the share of A's loudness that sits in cells where B is at least as present: 0 means
A has its space to itself, 1 means everything A plays is covered. The same map ranks candidate layers against what
is already there (`fit`): the candidate whose loudness falls where the bed is empty comes first.

Files must start at the same moment (stems exported from the same point, or loops from bar 1). This measures where
energy is; whether two sounds are pleasant together is still for ears.
"""
from __future__ import annotations

import numpy as np

from . import dsp
from .audio import Audio, load

N_FFT = 4096
EDGES = 25.0 * 2 ** (np.arange(0, 29) / 3.0)          # third-octave edges, 25 Hz to about 16 kHz
FLOOR_DB = 50.0                                       # cells this far under the layer's loudest are silence


def loudness_map(audio: Audio) -> tuple[np.ndarray, float]:
    """(frames x bands) of loudness-like values (band power to the 0.3, the usual compression of hearing), with
    everything more than FLOOR_DB under the loudest cell set to nothing. Also returns the frame rate."""
    mono, sr = audio.mono, audio.sr
    hop = N_FFT // 2
    power = dsp.stft_mag(mono, N_FFT, hop) ** 2
    freqs = dsp.fft_freqs(N_FFT, sr)
    band = np.searchsorted(EDGES, freqs) - 1
    inside = (band >= 0) & (band < EDGES.size - 1)
    w = np.zeros((freqs.size, EDGES.size - 1), dtype=np.float32)
    w[np.where(inside)[0], band[inside]] = 1.0
    cells = power @ w
    cells[cells < cells.max() * 10 ** (-FLOOR_DB / 10)] = 0.0
    return cells ** 0.3, sr / hop


def _band_label(b: int) -> str:
    return f"{EDGES[b]:.0f}-{EDGES[b + 1]:.0f} Hz"


def under(a: np.ndarray, b: np.ndarray) -> float:
    """Share of A's loudness in cells where B is present too (the smaller of the two, summed, over A's sum)."""
    total = float(a.sum())
    return float(np.minimum(a, b).sum() / total) if total > 0 else 0.0


def _pair(name_a: str, a: np.ndarray, name_b: str, b: np.ndarray, fps: float, bar_s: float | None) -> dict:
    both = np.minimum(a, b)
    per_band = both.sum(axis=0)
    worst = []
    for k in np.argsort(-per_band)[:3]:
        if per_band[k] <= 0:
            break
        ta, tb = float(a[:, k].sum()), float(b[:, k].sum())
        worst.append({"band": _band_label(int(k)), "share_of_the_clash": round(float(per_band[k] / both.sum()), 2),
                      "quieter_there": name_a if ta < tb else name_b})
    # the same two layers with time averaged away: what a static spectrum comparison would say
    static = float(np.minimum(a.mean(axis=0), b.mean(axis=0)).sum() / (min(a.mean(axis=0).sum(), b.mean(axis=0).sum()) + 1e-12))
    out = {"a": name_a, "b": name_b, "a_under_b": round(under(a, b), 3), "b_under_a": round(under(b, a), 3),
           "clash": round(float(both.sum() / (min(a.sum(), b.sum()) + 1e-12)), 3), "same_bands_ignoring_time": round(static, 3),
           "worst_bands": worst}
    if bar_s:
        per_frame = both.sum(axis=1)
        n = max(1, int(np.ceil(per_frame.size / (bar_s * fps))))
        bars = np.array([per_frame[int(i * bar_s * fps): int((i + 1) * bar_s * fps)].sum() for i in range(n)])
        if bars.sum() > 0:
            top = np.argsort(-bars)[:4]
            out["worst_bars"] = sorted(int(i) + 1 for i in top if bars[i] > 0)
    if out["clash"] < 0.5 * out["same_bands_ignoring_time"] and out["same_bands_ignoring_time"] > 0.3:
        out["note"] = "They use the same bands but mostly not at the same time: no carving needed."
    return out


def _load(files: dict[str, str]) -> tuple[dict[str, np.ndarray], float]:
    if len(files) < 1:
        raise ValueError("no files")
    maps, fps, sr = {}, 0.0, None
    for name, path in files.items():
        a = load(path)
        if sr is None:
            sr = a.sr
        elif a.sr != sr:
            a = a.resampled(sr)
        maps[name], fps = loudness_map(a)
    n = min(m.shape[0] for m in maps.values())
    return {k: m[:n] for k, m in maps.items()}, fps


def report(files: dict[str, str], bpm: float | None = None, beats_per_bar: int = 4) -> dict:
    """Every pair of layers, the worst first. `clash` is the overlap as a share of the quieter layer's loudness."""
    if len(files) < 2:
        raise ValueError("a clash needs at least two files")
    maps, fps = _load(files)
    bar_s = beats_per_bar * 60.0 / bpm if bpm else None
    names = list(maps)
    pairs = [_pair(a, maps[a], b, maps[b], fps, bar_s) for i, a in enumerate(names) for b in names[i + 1:]]
    pairs.sort(key=lambda p: -p["clash"])
    owners = {}
    total = sum(maps.values())
    for k in range(EDGES.size - 1):
        if total[:, k].sum() <= 0:
            continue
        share = {n: float(m[:, k].sum() / total[:, k].sum()) for n, m in maps.items()}
        top = max(share, key=share.get)
        owners[_band_label(k)] = {"owner": top, "share": round(share[top], 2)}
    return {"pairs": pairs, "who_owns_each_band": owners,
            "how_to_read": "a_under_b: share of A's loudness that sits where B is present at the same moment and in the same "
                           "third of an octave (0 free, 1 covered). clash: the overlap as a share of the quieter layer. "
                           "same_bands_ignoring_time: what an average spectrum would say; when it is high and clash is low, the "
                           "two take turns and need no EQ."}


def fit(bed: dict[str, str], candidates: dict[str, str]) -> dict:
    """Rank candidate layers by how much of each falls where the bed leaves room. Every candidate is set to the
    bed's loudness first, so the ranking is about where it sits in time and frequency, not how loud its file is."""
    if not bed or not candidates:
        raise ValueError("give at least one bed file and one candidate")
    maps, _ = _load({**{f"bed:{k}": v for k, v in bed.items()}, **{f"cand:{k}": v for k, v in candidates.items()}})
    bed_map = sum(m for k, m in maps.items() if k.startswith("bed:"))
    rows = []
    for k, m in maps.items():
        if not k.startswith("cand:"):
            continue
        scaled = m * (bed_map.sum() / (len(bed) * m.sum() + 1e-12))       # the level of an average bed layer
        covered = np.minimum(scaled, bed_map)
        per_band = covered.sum(axis=0)
        rows.append({"candidate": k[5:], "free": round(1.0 - under(scaled, bed_map), 3),
                     "crowded_bands": [_band_label(int(b)) for b in np.argsort(-per_band)[:2] if per_band[b] > 0],
                     "fills_empty_bands": [_band_label(int(b)) for b in np.argsort(-(scaled.sum(axis=0) - per_band))[:2]
                                           if scaled[:, b].sum() - per_band[b] > 0]})
    rows.sort(key=lambda r: -r["free"])
    return {"ranking": rows, "how_to_read": "free: share of the candidate's loudness that lands where the bed is not already "
                                            "playing, at matched level. Higher fits with less carving. It says nothing about taste."}
