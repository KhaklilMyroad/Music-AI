"""Stem separation.

Backends:
  * "demucs"  - Hybrid Transformer Demucs (Meta, MIT licence), if installed (`pip install demucs`).
                Best quality. Downloads model weights on first run.
  * "dsp"     - Built-in mask-based fallback (HPSS + crossover + stereo-centre mask).
                Always available, much lower quality. Stems still sum back to the mix.
"""
from __future__ import annotations

import glob
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass

import numpy as np

from . import dsp
from .audio import Audio, load


@dataclass
class Stems:
    stems: dict[str, Audio]
    method: str
    quality_note: str


def demucs_available() -> bool:
    return importlib.util.find_spec("demucs") is not None


def separate(path: str, audio: Audio, method: str = "auto", model: str = "htdemucs_6s", workdir: str | None = None) -> Stems:
    if method in ("auto", "demucs") and demucs_available():
        try:
            return _demucs(path, model, workdir)
        except Exception as exc:  # weights blocked, OOM, ...
            if method == "demucs":
                raise
            note = f"Demucs failed ({type(exc).__name__}: {str(exc)[:200]}); used the built-in DSP separator instead."
            res = _dsp(audio)
            res.quality_note = note + " " + res.quality_note
            return res
    if method == "demucs":
        raise RuntimeError("Demucs is not installed. Run: pip install demucs")
    return _dsp(audio)


def _demucs(path: str, model: str, workdir: str | None) -> Stems:
    out = workdir or tempfile.mkdtemp(prefix="t2a_demucs_")
    cmd = [sys.executable, "-m", "demucs", "-n", model, "-o", out, path]
    subprocess.run(cmd, check=True)
    base = os.path.splitext(os.path.basename(path))[0]
    folder = os.path.join(out, model, base)
    files = sorted(glob.glob(os.path.join(folder, "*.wav")))
    if not files:
        raise RuntimeError(f"Demucs produced no stems in {folder}")
    stems = {os.path.splitext(os.path.basename(f))[0]: load(f) for f in files}
    if workdir is None:
        shutil.rmtree(out, ignore_errors=True)
    return Stems(stems, f"demucs:{model}", "Neural separation (Demucs). Expect some bleed between stems, mostly in reverb tails and cymbals.")


def _dsp(audio: Audio, n_fft: int = 4096, hop: int = 1024) -> Stems:
    sr = audio.sr
    chans = [audio.data[c] for c in range(audio.channels)]
    specs = [dsp.stft(c, n_fft, hop).astype(np.complex64) for c in chans]
    mag = np.mean([np.abs(s) for s in specs], axis=0)
    freqs = dsp.fft_freqs(n_fft, sr)
    kt = max(5, int(0.5 * sr / hop) | 1)
    kf = max(5, int(400 / (sr / n_fft)) | 1)
    H, P = dsp.hpss(mag, kt, kf)
    # bass crossover 150 -> 300 Hz (raised cosine)
    wb = np.clip((300 - freqs) / 150, 0, 1)
    wb = 0.5 - 0.5 * np.cos(np.pi * wb)
    # vocal/lead band weight 180 Hz - 7 kHz
    band = np.clip((freqs - 120) / 120, 0, 1) * np.clip((9000 - freqs) / 3000, 0, 1)
    if len(specs) == 2:
        L, R = np.abs(specs[0]), np.abs(specs[1])
        centre = 1 - np.abs(L - R) / (L + R + 1e-9)
        centre = centre ** 4
    else:
        centre = np.full_like(mag, 0.5)
    v = centre * band[None, :]
    masks = {
        "drums": P,
        "bass": H * wb[None, :],
        "vocals": H * (1 - wb[None, :]) * v,
        "other": H * (1 - wb[None, :]) * (1 - v),
    }
    n = audio.data.shape[1]
    stems = {}
    for name, m in masks.items():
        data = np.stack([dsp.istft(s * m, n_fft, hop, n) for s in specs])
        stems[name] = Audio(data, sr)
    return Stems(
        stems, "dsp:hpss-crossover",
        "Built-in DSP separation (rough). 'vocals' really means centre-panned melodic content (vocal or lead), "
        "kick sub-tails leak into 'bass'. Install Demucs for production-grade stems.",
    )
