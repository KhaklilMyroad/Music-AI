"""Where every beat of a recording really is.

rhythm.analyze fits one constant tempo. Generated or played music often sits a little off a round tempo and can
drift, so a constant grid slides away from the audio. track() follows the beat through the song: in a 4-bar window
around every bar it measures how far the beats sit from the constant grid, and never looks further than half a 16th
from where the windows before it point, so it cannot hop onto an off-beat. The result maps seconds to arrangement
beats. That map is what puts a transcribed note on the right 16th, and what the warp markers are made of.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import rhythm as rh

DRIFT_MS = 15.0          # a beat further than this from the best constant-tempo grid counts as drift,
MIN_GAIN = 0.10          # if the tracked beats also hit this much more onset energy than that grid
WINDOW_BARS = 4


@dataclass
class BeatMap:
    times: np.ndarray            # seconds of every beat; covers the whole file (extrapolated at both ends)
    downbeat: int                # index in `times` of the first downbeat at or after second 0
    beats_per_bar: int
    lead_in: float               # arrangement beat of that downbeat: one bar if the audio starts before it, else 0
    bpm: float                   # mean tempo
    drift_ms: float              # furthest any beat sits from the best constant-tempo grid
    bpm_lo: float                # slowest and fastest 8-bar stretch
    bpm_hi: float
    tracked: float               # share of the windows in which the beat was clear enough to measure
    gain: float = 0.0            # how much more onset energy the tracked beats hit than the best constant grid does
    weak: list[tuple[float, float]] = field(default_factory=list)   # seconds: stretches followed blind
    relocked: list[float] = field(default_factory=list)             # seconds where the beat was found again after one

    @property
    def drifting(self) -> bool:
        """Only when following the beat pays: where onsets are soft the tracker wanders a little by itself, and a
        steady song must not be bent to fit that."""
        return self.drift_ms > DRIFT_MS and self.gain > MIN_GAIN

    def to_beats(self, t):
        return np.interp(np.asarray(t, dtype=float), self.times, np.arange(self.times.size)) - self.downbeat + self.lead_in

    def to_seconds(self, beats):
        return np.interp(np.asarray(beats, dtype=float) + self.downbeat - self.lead_in, np.arange(self.times.size), self.times)

    def bar_times(self, duration: float) -> np.ndarray:
        """Seconds of every bar line inside the file, from the first downbeat."""
        t = self.times[np.arange(self.downbeat, self.times.size, self.beats_per_bar)]
        return t[t < duration]

    def warp_markers(self, duration: float, tol_s: float = 0.002) -> list[tuple[float, float]]:
        """(second, arrangement beat) pairs: the fewest bar lines that reproduce the map within `tol_s`."""
        bars = np.arange(self.downbeat, self.times.size, self.beats_per_bar)
        sec = [0.0] + [float(self.times[i]) for i in bars if 0 < self.times[i] < duration] + [float(duration)]
        beat = [float(b) for b in self.to_beats(sec)]
        keep = {0, len(sec) - 1}
        stack = [(0, len(sec) - 1)]
        while stack:
            a, b = stack.pop()
            if b - a < 2:
                continue
            mid = np.arange(a + 1, b)
            line = sec[a] + (np.array(beat)[mid] - beat[a]) * (sec[b] - sec[a]) / (beat[b] - beat[a])
            err = np.abs(np.array(sec)[mid] - line)
            k = int(np.argmax(err))
            if err[k] > tol_s:
                keep.add(int(mid[k]))
                stack += [(a, int(mid[k])), (int(mid[k]), b)]
        return [(sec[i], beat[i]) for i in sorted(keep)]


def track(onsets: rh.OnsetData, rhythm: rh.Rhythm, duration: float, chroma: np.ndarray | None = None,
          chroma_fps: float = rh.FPS) -> BeatMap:
    fps = onsets.fps
    env = onsets.full + 0.5 * onsets.low
    frames = np.arange(env.size)
    period = 60.0 / rhythm.bpm
    bpb = rhythm.beats_per_bar
    t0 = float(rhythm.beat_times[0]) - rh.ONSET_LAG_S
    n = max(2, int((env.size / fps - t0) / period) + 1)
    ref = t0 + np.arange(n) * period              # the constant grid the deviations are measured from
    half = WINDOW_BARS * bpb // 2
    centres = np.arange(0, n, bpb)
    reach = period / 8                            # half a 16th: only one grid line fits inside the search range
    offs = np.arange(-reach, reach + 5e-4, 1e-3)

    relock = np.arange(-period / 2, period / 2, 1e-3)   # after a blind stretch: any phase, the strongest wins

    def peak(c: int, around: float, lean: float, spread, offs=offs) -> tuple[float, float, float]:
        """Best (score, deviation at the window centre, contrast) of a comb whose spacing is the reference period
        plus `lean` seconds per beat, trying a few spacings around it."""
        idx = np.arange(max(0, c - half), min(n, c + half))
        best = (-1.0, around, 0.0)
        for extra in spread:
            at = (ref[idx][:, None] + around + (lean + extra) * (idx - c)[:, None] + offs[None, :]) * fps
            s = np.convolve(np.interp(at, frames, env, left=0.0, right=0.0).mean(axis=0), np.ones(5) / 5, mode="same")
            k = int(np.argmax(s))
            if offs is relock:
                # Off-beats can be louder than the beat (a bass that ducks under the kick): of the strong peaks,
                # take the one nearest to where the song was heading, not simply the strongest.
                tops = [i for i in range(1, s.size - 1) if s[i] >= s[i - 1] and s[i] >= s[i + 1] and s[i] >= 0.6 * s[k]]
                k = min(tops, key=lambda i: abs(offs[i])) if tops else k
            if s[k] > best[0]:
                best = (float(s[k]), around + float(offs[k]), float(s[k] - s.min()))
        return best

    fine = period * 0.002 * np.arange(-2, 3)       # local tempo within +-0.4 % of where the last windows point
    wide = period * 0.002 * np.arange(-15, 16)     # the first window has nothing to go by: +-3 %
    first = [peak(c, 0.0, 0.0, wide) for c in centres]
    anchor = int(np.argmax([f[0] for f in first]))
    scale = first[anchor][0] + 1e-12
    dev = np.full(centres.size, np.nan)
    weight = np.zeros(centres.size)
    dev[anchor], weight[anchor] = first[anchor][1], first[anchor][0]

    relocks: list[int] = []

    def follow(order):
        seen = [(anchor, dev[anchor])]
        for j in order:
            j1, d1 = seen[-1]
            slope = 0.0                                # seconds of deviation per window (= per bar)
            if len(seen) >= 3:
                xs, ys = np.array(seen[-6:]).T
                slope = float(np.clip(np.polyfit(xs, ys, 1)[0], -0.06 * period * bpb, 0.06 * period * bpb))
            around = d1 + slope * float(np.clip(j - j1, -8, 8))
            blind = abs(j - j1) > WINDOW_BARS       # no window since the last clear one even overlaps this one
            score, d, contrast = peak(centres[j], around, slope / bpb, fine if len(seen) >= 3 and not blind else wide,
                                      relock if blind else offs)
            if score >= 0.06 * scale and contrast >= 0.3 * score:          # a clear peak, not silence or a flat stretch
                dev[j], weight[j] = d, score
                seen = [(j, d)] if blind else seen + [(j, d)]
                relocks.append(j) if blind else None

    follow(range(anchor + 1, centres.size))
    follow(range(anchor - 1, -1, -1))
    ok = np.isfinite(dev)
    # Neighbouring windows share most of their beats, and tempo moves slowly: average each with the two on either
    # side, the clearer windows counting for more.
    filled = np.interp(np.arange(centres.size), np.where(ok)[0], dev[ok])
    w = np.where(ok, weight, 0.0) + 1e-9
    kernel = np.ones(5)
    filled = np.convolve(filled * w, kernel, mode="same") / np.convolve(w, kernel, mode="same")
    per_beat = np.interp(np.arange(n), centres, filled)
    per_beat = np.convolve(np.pad(per_beat, bpb, mode="edge"), np.ones(2 * bpb + 1) / (2 * bpb + 1), mode="valid")
    times = ref + per_beat + rh.ONSET_LAG_S

    low_b, change = rh.beat_accents((times - rh.ONSET_LAG_S) * fps, onsets, chroma, chroma_fps)
    phase = rh.downbeat_phase(low_b, change, bpb)

    fit = np.polyfit(np.arange(n), times, 1)
    drift_ms = float(np.max(np.abs(times - np.polyval(fit, np.arange(n)))) * 1000)
    soft = np.convolve(env, np.ones(3) / 3, mode="same")

    def hit(t):
        return float(np.interp((t - rh.ONSET_LAG_S) * fps, frames, soft, left=0.0, right=0.0).sum())

    gain = hit(times) / (max(hit(np.polyval(fit, np.arange(n))), hit(ref + rh.ONSET_LAG_S)) + 1e-12) - 1.0
    span = 8 * bpb
    local = 60.0 * span / (times[span:] - times[:-span]) if n > span else np.array([60.0 / fit[0]])

    head, tail = times[1] - times[0], times[-1] - times[-2]
    before = int(np.ceil(max(0.0, times[0]) / head)) + 1
    after = int(np.ceil(max(0.0, duration - times[-1]) / tail)) + 1
    times = np.concatenate([times[0] - head * np.arange(before, 0, -1), times, times[-1] + tail * np.arange(1, after + 1)])
    downbeat = next(i for i in range(times.size) if (i - before - phase) % bpb == 0 and times[i] >= -1e-6)
    weak = []
    for j in np.where(~ok)[0]:
        a, b = float(times[before + max(0, centres[j] - bpb // 2)]), float(times[before + min(n - 1, centres[j] + bpb // 2)])
        if weak and a <= weak[-1][1] + 1e-6:
            weak[-1] = (weak[-1][0], b)
        else:
            weak.append((a, b))
    return BeatMap(times, downbeat, bpb, float(bpb if times[downbeat] > 0.01 else 0), 60.0 / float(fit[0]), drift_ms,
                   float(local.min()), float(local.max()), float(ok.mean()), gain, weak,
                   sorted(float(times[before + centres[j]]) for j in relocks))
