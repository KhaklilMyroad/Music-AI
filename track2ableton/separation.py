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
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

import numpy as np

from . import dsp
from .audio import Audio, load


@dataclass
class Stems:
    stems: dict[str, Audio]
    method: str
    quality_note: str
    kinds: dict[str, str] = field(default_factory=dict)   # stem name -> drums / bass / vocals / piano / guitar / other
    skipped: list[str] = field(default_factory=list)      # files in a stem folder that were left out, with why


AUDIO_EXT = (".wav", ".flac", ".aif", ".aiff", ".mp3", ".m4a", ".ogg")
KIND_WORDS = {
    "vocals": ("vocal", "vox", "voice", "choir", "acapella", "backing", "sing", "adlib"),
    "drums": ("drum", "kick", "snare", "hat", "hihat", "perc", "clap", "cymbal", "conga", "bongo", "shaker", "tom", "cowbell", "clave", "rim"),
    "bass": ("bass", "sub", "808"),
    "piano": ("piano", "keys", "keyboard", "rhodes"),
    "guitar": ("guitar", "gtr"),
}
MIX_WORDS = ("mix", "master", "instrumental", "full", "original")


def _words(name: str) -> list[str]:
    return re.findall(r"[a-z]+|\d+", name.lower())


def stem_kind(label: str) -> str:
    """What a stem file is, from the words in its name; the last word that says something wins ('Bass Drum' is drums)."""
    kind = "other"
    for w in _words(label):
        for k, keys in KIND_WORDS.items():
            if any(w.startswith(key) for key in keys):
                kind = k
    return kind


def from_folder(folder: str) -> Stems:
    """Stems somebody else separated (an export from the generator or the DAW): every audio file in the folder is one
    stem. A file that names itself a mix is left out, or the song would be counted twice."""
    files = sorted(f for f in os.listdir(folder) if f.lower().endswith(AUDIO_EXT) and os.path.isfile(os.path.join(folder, f)))
    if not files:
        raise ValueError(f"no audio files in {folder}")
    bases = [os.path.splitext(f)[0] for f in files]
    pre = os.path.commonprefix(bases) if len(bases) > 1 else ""
    pre = pre[: max(pre.rfind(c) for c in " -_([") + 1] if any(c in pre for c in " -_([") else ""   # cut at a word boundary
    stems, kinds, skipped = {}, {}, []
    for f, base in zip(files, bases):
        label = base[len(pre):].strip(" -_()[]") or base
        if len(files) > 1 and any(w in MIX_WORDS for w in _words(label)):
            skipped.append(f"{f}: its name says it is a mix, not a stem")
            continue
        a = load(os.path.join(folder, f))
        if float(np.max(np.abs(a.data))) < 1e-4:
            skipped.append(f"{f}: silent")
            continue
        while label in stems:
            label += " 2"
        stems[label] = a
        kinds[label] = stem_kind(label)
    if not stems:
        raise ValueError(f"no usable stems in {folder}: {skipped}")
    sr = next(iter(stems.values())).sr
    n = 0
    for k in list(stems):
        if stems[k].sr != sr:
            stems[k] = stems[k].resampled(sr)
        n = max(n, stems[k].data.shape[1])
    for k, a in stems.items():
        d = a.data if a.data.shape[0] == 2 else np.repeat(a.data[:1], 2, axis=0)
        stems[k] = Audio(np.pad(d, ((0, 0), (0, n - d.shape[1]))), sr)
    return Stems(stems, "folder", f"{len(stems)} stems supplied in a folder; nothing was separated here.", kinds, skipped)


def mixdown(stems: Stems) -> Audio:
    first = next(iter(stems.stems.values()))
    return Audio(np.sum([a.data for a in stems.stems.values()], axis=0).astype(np.float32), first.sr)


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
