"""Audio input/output helpers.

Everything internally is float32, shape (channels, samples), values in [-1, 1].
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


@dataclass
class Audio:
    data: np.ndarray  # (channels, samples)
    sr: int

    @property
    def mono(self) -> np.ndarray:
        return self.data.mean(axis=0)

    @property
    def duration(self) -> float:
        return self.data.shape[1] / float(self.sr)

    @property
    def channels(self) -> int:
        return self.data.shape[0]

    def mid_side(self) -> tuple[np.ndarray, np.ndarray]:
        if self.channels < 2:
            return self.data[0], np.zeros_like(self.data[0])
        left, right = self.data[0], self.data[1]
        return 0.5 * (left + right), 0.5 * (left - right)

    def resampled(self, sr: int) -> "Audio":
        return Audio(resample(self.data, self.sr, sr), sr)


def resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return x
    g = np.gcd(int(sr_in), int(sr_out))
    return resample_poly(x, sr_out // g, sr_in // g, axis=-1).astype(np.float32)


def load(path: str, sr: int | None = None) -> Audio:
    """Load any audio file. Uses libsndfile, then ffmpeg as a fallback decoder."""
    try:
        data, file_sr = sf.read(path, dtype="float32", always_2d=True)
        data = data.T
    except Exception as first:
        try:
            data, file_sr = _ffmpeg_decode(path)
        except Exception as second:                  # neither decoder could: say which file, in one sentence
            raise ValueError(f"cannot read audio from {path}: not an audio file, or damaged "
                             f"({type(first).__name__}; {type(second).__name__})") from second
    if data.size == 0:
        raise ValueError(f"{path} has no audio in it (0 samples)")
    if data.shape[0] > 2:
        data = data[:2]
    audio = Audio(np.ascontiguousarray(data), int(file_sr))
    if sr is not None and sr != audio.sr:
        audio = audio.resampled(sr)
    return audio


def _ffmpeg_decode(path: str) -> tuple[np.ndarray, int]:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(f"Cannot decode {path}: libsndfile failed and ffmpeg is not installed")
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "decoded.wav")
        subprocess.run(
            ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", path, "-vn", "-c:a", "pcm_f32le", out],
            check=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        data, file_sr = sf.read(out, dtype="float32", always_2d=True)
    return data.T, int(file_sr)


def save(path: str, data: np.ndarray, sr: int, subtype: str = "PCM_24") -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    arr = np.asarray(data, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr[None, :]
    peak = float(np.max(np.abs(arr))) if arr.size else 0.0
    if peak > 1.0:  # never clip silently on export
        arr = arr / peak
    sf.write(path, arr.T, sr, subtype=subtype)
    return path


def db(x: float | np.ndarray, floor: float = -120.0):
    return np.maximum(20.0 * np.log10(np.maximum(np.abs(x), 1e-12)), floor)


def rms_db(x: np.ndarray) -> float:
    return float(db(np.sqrt(np.mean(np.square(x, dtype=np.float64))) if x.size else 0.0))
