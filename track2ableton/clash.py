"""Do two layers get in each other's way? Measured in time and in frequency.

An average spectrum cannot answer that: a kick and an off-beat bass live in the same band and never meet, and a
pad can sit under a vocal for the whole song. Here every layer becomes a map of how loud it is in each third of an
octave every 46 ms, for the left and the right channel, and two layers overlap to the extent that they are loud in
the same cell of that map.

The numbers, exactly:
  a_under_b   sum of min(A, B) over all cells, divided by the sum of A: the share of A's loudness that B matches or
              exceeds in the same cell. 0: A has its cells to itself. 1: B is at least as loud wherever A plays.
  clash       the same overlap as a share of the quieter layer.
  when_both_play   the overlap in the moments both layers sound, against the usual loudness of the quieter one. A
              pair that meets in four bars of sixty-four has a small clash and a large when_both_play: they collide,
              where they meet.
  share_of_the_mix   the overlap as a share of everything in the call: pairs are listed by it, so that a layer nobody
              hears does not come first.

Files are compared at one sample rate and must start at the same moment (stems exported from the same point, or
loops from bar 1). Each pair is compared over the stretch both files cover, and the result says how long that is.
This measures where energy is. Whether two sounds are pleasant together is still for ears.
"""
from __future__ import annotations

import functools

import numpy as np

from . import dsp
from .audio import Audio, load

SR = 44100                                            # everything is brought to this rate: frames are always 46 ms
N_FFT = 4096
HOP = N_FFT // 2
EDGES = 25.0 * 2 ** (np.arange(0, 29) / 3.0)          # third-octave edges, 25 Hz to about 16 kHz
SILENCE_DBFS = -75.0                                  # a cell under this (re a full-scale sine in the band) is silence
RANGE_DB = 70.0                                       # so is one this far under the layer's own loudest cell
OCCUPIED = 0.25                                       # a cell at this share of the bed's loud level is taken (about 20 dB under it)


@functools.lru_cache(maxsize=1)
def _bands() -> np.ndarray:
    freqs = dsp.fft_freqs(N_FFT, SR)
    band = np.searchsorted(EDGES, freqs) - 1
    inside = (band >= 0) & (band < EDGES.size - 1)
    w = np.zeros((freqs.size, EDGES.size - 1), dtype=np.float32)
    w[np.where(inside)[0], band[inside]] = 1.0
    return w


@functools.lru_cache(maxsize=1)
def _full_scale() -> float:
    """Band power of a full-scale sine, measured with the same transform: the reference for SILENCE_DBFS."""
    t = np.arange(SR // 2) / SR
    return float((dsp.stft_mag(np.sin(2 * np.pi * 1000.0 * t).astype(np.float32), N_FFT, HOP) ** 2 @ _bands()).max())


def power_map(audio: Audio) -> np.ndarray:
    """(2 channels x frames x bands) of band power. A mono file is the same in both channels, as it is on speakers."""
    if audio.sr != SR:
        audio = audio.resampled(SR)
    chans = [audio.data[0], audio.data[1] if audio.channels > 1 else audio.data[0]]
    cells = np.stack([dsp.stft_mag(np.ascontiguousarray(c), N_FFT, HOP) ** 2 @ _bands() for c in chans])
    quiet = max(_full_scale() * 10 ** (SILENCE_DBFS / 10), float(cells.max()) * 10 ** (-RANGE_DB / 10))
    cells[cells < quiet] = 0.0
    return cells


def loudness(power: np.ndarray) -> np.ndarray:
    """Band power to the 0.3: the usual compression of hearing, so that a loud low band does not decide everything."""
    return power ** 0.3


def _band_label(b: int) -> str:
    return f"{EDGES[b]:.0f}-{EDGES[b + 1]:.0f} Hz"


def under(a: np.ndarray, b: np.ndarray) -> float:
    """Sum of min(A, B) over the cells, divided by the sum of A."""
    total = float(a.sum())
    return float(np.minimum(a, b).sum() / total) if total > 0 else 0.0


def _sounding(m: np.ndarray) -> np.ndarray:
    """Frames in which the layer is really playing: above a tenth of its usual loud frame."""
    per_frame = m.sum(axis=(0, 2))
    loud = per_frame[per_frame > 0]
    return per_frame > 0.1 * np.percentile(loud, 90) if loud.size else np.zeros(per_frame.size, dtype=bool)


def _pair(name_a: str, a: np.ndarray, name_b: str, b: np.ndarray, bar_s: float | None, everything: float) -> dict:
    n = min(a.shape[1], b.shape[1])
    longer = max(a.shape[1], b.shape[1])
    a, b = a[:, :n], b[:, :n]
    both = np.minimum(a, b)
    overlap = float(both.sum())
    per_band = both.sum(axis=(0, 1))
    worst = []
    for k in np.argsort(-per_band)[:3]:
        if per_band[k] <= 0:
            break
        ta, tb = float(a[:, :, k].sum()), float(b[:, :, k].sum())
        worst.append({"band": _band_label(int(k)), "share_of_the_clash": round(float(per_band[k] / overlap), 2),
                      "quieter_there": name_a if ta < tb else name_b})
    # the same two layers with time averaged away: what a comparison of average spectra would say
    sa, sb = a.mean(axis=1), b.mean(axis=1)
    static = float(np.minimum(sa, sb).sum() / (min(sa.sum(), sb.sum()) + 1e-12))
    # While both sound: the overlap per moment against what the quieter layer usually is when it plays. Measured
    # against its usual level and not its level in those moments, or a kick's dying tail under the next bass note
    # (quiet, and fully covered) would read as a collision.
    on_a, on_b = _sounding(a), _sounding(b)
    meet = on_a & on_b
    together = 0.0
    if meet.any():
        usual = min(a[:, on_a].sum() / on_a.sum(), b[:, on_b].sum() / on_b.sum())
        together = float(min(1.0, both[:, meet].sum() / (meet.sum() * usual + 1e-12)))
    out = {"a": name_a, "b": name_b, "a_under_b": round(under(a, b), 3), "b_under_a": round(under(b, a), 3),
           "clash": round(float(overlap / (min(a.sum(), b.sum()) + 1e-12)), 3), "when_both_play": round(float(together), 3),
           "both_play_share_of_time": round(float(meet.mean()), 2) if meet.size else 0.0,
           "same_bands_ignoring_time": round(static, 3), "share_of_the_mix": round(overlap / (everything + 1e-12), 4),
           "seconds_compared": round(n * HOP / SR, 1), "worst_bands": worst}
    if longer > n * 1.05:
        out["length_note"] = (f"The files differ in length: only the first {n * HOP / SR:.1f} s, which both cover, were compared "
                              f"(the longer runs {longer * HOP / SR:.1f} s).")
    if bar_s and overlap > 0:
        per_frame = both.sum(axis=(0, 2))
        step = bar_s * SR / HOP
        bars = np.array([per_frame[int(i * step): int((i + 1) * step)].sum() for i in range(max(1, int(np.ceil(n / step))))])
        usual_bar, top = float(np.median(bars)), float(bars.max())
        # They meet in under half of the bars: those bars are the answer. Otherwise the bars well above the usual one.
        stand = np.where(bars >= 0.25 * top)[0] if usual_bar <= 0.1 * top else np.where(bars >= 1.5 * usual_bar)[0]
        if stand.size and stand.size <= 0.5 * bars.size:
            out["worst_bars"] = [int(i) + 1 for i in stand[np.argsort(-bars[stand], kind="stable")][:8]]       # the heaviest first
        else:
            out["worst_bars"] = []
            out["where"] = "spread evenly over the bars where both play, no bar stands out"
    if static > 0.3 and together < 0.5 * static:
        out["note"] = "They use the same bands but not at the same moments: they take turns, and need no carving."
    elif together >= 0.5 and out["clash"] < 0.5 * together:
        out["note"] = ("They collide where they play together, though that is only part of the time: look at when_both_play "
                       "and worst_bars, not at clash.")
    return out


def _load(files: dict[str, str]) -> tuple[dict[str, np.ndarray], list[str]]:
    """Power maps of the files that have sound in them, and the names of those that have none."""
    maps, empty = {}, []
    for name, path in files.items():
        m = power_map(load(path))
        if m.max() <= 0:
            empty.append(name)
        else:
            maps[name] = m
    return maps, empty


def _padded(maps: list[np.ndarray]) -> np.ndarray:
    n = max(m.shape[1] for m in maps)
    return sum(np.pad(m, ((0, 0), (0, n - m.shape[1]), (0, 0))) for m in maps)


def report(files: dict[str, str], bpm: float | None = None, beats_per_bar: int = 4) -> dict:
    """Every pair of layers, the one that takes most of the mix first."""
    if len(files) < 2:
        raise ValueError("a clash needs at least two files")
    power, empty = _load(files)
    if len(power) < 2:
        raise ValueError("fewer than two of the files have any sound in them: " + ", ".join(empty or files))
    maps = {k: loudness(p) for k, p in power.items()}
    everything = float(sum(m.sum() for m in maps.values()))
    bar_s = beats_per_bar * 60.0 / bpm if bpm else None
    names = list(maps)
    pairs = [_pair(a, maps[a], b, maps[b], bar_s, everything) for i, a in enumerate(names) for b in names[i + 1:]]
    pairs.sort(key=lambda p: (-p["share_of_the_mix"], -p["clash"]))
    owners = {}
    total = _padded(list(maps.values())).sum(axis=(0, 1))
    for k in range(EDGES.size - 1):
        if total[k] <= 0:
            continue
        share = {n: float(m[:, :, k].sum() / total[k]) for n, m in maps.items()}
        top = max(share, key=share.get)
        owners[_band_label(k)] = {"owner": top, "share": round(share[top], 2)}
    out = {"pairs": pairs, "who_owns_each_band": owners,
           "how_to_read": "a_under_b: the share of A's loudness that B matches or exceeds in the same moment, band and channel "
                          "(sum of the smaller of the two over A's sum). clash: that overlap as a share of the quieter layer. "
                          "when_both_play: the overlap while both sound, against the quieter layer's usual loudness; read it when "
                          "the two meet for part of the song. "
                          "share_of_the_mix: the overlap against everything in this call; the list is in that order. "
                          "same_bands_ignoring_time: what average spectra would say. These are measurements of where energy is, "
                          "not a judgement of the sound."}
    if empty:
        out["no_signal"] = empty
    return out


def fit(bed: dict[str, str], candidates: dict[str, str]) -> dict:
    """Rank candidate layers by the room the bed leaves them. A cell of the map counts as taken to the extent the
    bed is present in it (fully, from about 20 dB under the bed's loud level), and `free` is the share of the
    candidate's loudness that falls on cells not taken. The candidate's own level does not enter, nor does it
    matter whether the bed comes as one bounce or as stems. A candidate with no sound in it is not ranked."""
    if not bed or not candidates:
        raise ValueError("give at least one bed file and one candidate")
    bed_power, bed_empty = _load(bed)
    if not bed_power:
        raise ValueError("the bed has no sound in it")
    bed_map = loudness(_padded(list(bed_power.values())))         # powers add; loudness comes after
    level = float(np.percentile(bed_map[bed_map > 0], 90))
    taken = np.clip(bed_map / (OCCUPIED * level), 0.0, 1.0)
    cand_power, silent = _load(candidates)
    rows = []
    for name, p in cand_power.items():
        c = loudness(p)
        n = min(c.shape[1], taken.shape[1])
        c, t = c[:, :n], taken[:, :n]
        covered = (c * t).sum(axis=(0, 1))
        total = c.sum(axis=(0, 1))
        share = np.divide(covered, total, out=np.zeros_like(covered), where=total > 0)
        heard = np.where(total > 0.02 * total.sum())[0]            # bands the candidate really uses
        row = {"candidate": name, "free": round(1.0 - float(covered.sum() / (total.sum() + 1e-12)), 3),
               "crowded_bands": [_band_label(int(b)) for b in heard[np.argsort(-covered[heard])] if share[b] >= 0.5][:2],
               "open_bands": [_band_label(int(b)) for b in heard[np.argsort(-total[heard])] if share[b] <= 0.3][:2],
               "seconds_compared": round(n * HOP / SR, 1)}
        if c.shape[1] != taken.shape[1] and abs(p.shape[1] - taken.shape[1]) > 0.05 * max(p.shape[1], taken.shape[1]):
            row["length_note"] = f"Compared over the first {n * HOP / SR:.1f} s only: the candidate and the bed differ in length."
        rows.append(row)
    rows.sort(key=lambda r: -r["free"])
    out = {"ranking": rows,
           "how_to_read": "free: the share of the candidate's loudness that falls where the bed is not already present, in the same "
                          "moment, band and channel. crowded_bands: where the bed covers at least half of it. open_bands: where "
                          "the bed covers at most a third of it. It is about where energy is, not about taste or level."}
    if silent:
        out["no_signal"] = silent
    if bed_empty:
        out["bed_files_with_no_signal"] = bed_empty
    return out
