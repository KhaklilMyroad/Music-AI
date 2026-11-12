"""Tiny dependency-free PNG encoder and colour maps."""
from __future__ import annotations

import struct
import zlib

import numpy as np


def encode(rgb: np.ndarray) -> bytes:
    """rgb: uint8 array (height, width, 3) -> PNG bytes."""
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


# Perceptually ordered dark -> bright ramp (approximation of an inferno-like map).
_ANCHORS = np.array([
    [0, 0, 4], [40, 11, 84], [101, 21, 110], [159, 42, 99], [212, 72, 66], [245, 125, 21], [250, 193, 39], [252, 255, 164],
], dtype=float)


def colormap(v: np.ndarray) -> np.ndarray:
    """v in 0..1 -> uint8 RGB."""
    v = np.clip(np.nan_to_num(v), 0, 1) * (len(_ANCHORS) - 1)
    i = np.floor(v).astype(int)
    i = np.clip(i, 0, len(_ANCHORS) - 2)
    f = (v - i)[..., None]
    return (_ANCHORS[i] * (1 - f) + _ANCHORS[i + 1] * f).astype(np.uint8)
