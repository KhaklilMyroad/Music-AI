"""Mix/master analysis against signals with known properties, and the MCP server over real stdio."""
import asyncio
import json
import os
import sys
import zlib

import numpy as np
import pytest
import soundfile as sf

from track2ableton import mixmaster

SR = 44100


def _wav(path, x):
    sf.write(path, np.asarray(x, dtype=np.float32).T, SR)
    return path


def _noise(seconds, seed, lo=None, hi=None, level=0.2):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(int(seconds * SR))
    if lo or hi:
        from scipy.signal import butter, sosfiltfilt
        if lo and hi:
            sos = butter(4, [lo, hi], "bandpass", fs=SR, output="sos")
        elif lo:
            sos = butter(4, lo, "highpass", fs=SR, output="sos")
        else:
            sos = butter(4, hi, "lowpass", fs=SR, output="sos")
        x = sosfiltfilt(sos, x)
    x = x / np.max(np.abs(x)) * level
    return np.stack([x, x])


def test_png_is_valid():
    from track2ableton import png
    img = np.zeros((3, 4, 3), np.uint8)
    data = png.encode(img)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    idat = data[data.index(b"IDAT") + 4:data.index(b"IEND") - 8]
    assert len(zlib.decompress(idat)) == 3 * (1 + 4 * 3)


def test_masking_detects_overlap(tmp_path):
    a = _wav(str(tmp_path / "bass.wav"), _noise(4, 1, 60, 200))
    b = _wav(str(tmp_path / "kick.wav"), _noise(4, 2, 60, 200))
    c = _wav(str(tmp_path / "hats.wav"), _noise(4, 3, 7000, None))
    rep = mixmaster.mix_report({"bass": a, "kick": b, "hats": c})
    pairs = {(tuple(sorted(m["tracks"])), m["band"]) for m in rep["masking"]}
    assert (("bass", "kick"), "bass") in pairs
    assert not any("hats" in p[0] for p in pairs)


def test_master_report_loudness_and_peak(tmp_path):
    t = np.arange(SR * 6) / SR
    x = 0.99 * np.sin(2 * np.pi * 997 * t)
    p = _wav(str(tmp_path / "m.wav"), np.stack([x, x]))
    rep = mixmaster.master_report(p, "streaming")
    assert rep["target_lufs"] == -14.0
    assert any("True peak" in a["why"] for a in rep["actions"])
    assert any("Integrated" in a["why"] for a in rep["actions"])


def test_reference_matching_finds_missing_highs(tmp_path):
    ref = _wav(str(tmp_path / "ref.wav"), _noise(6, 4))
    dull = _wav(str(tmp_path / "mix.wav"), _noise(6, 5, None, 3000))
    cmp_ = mixmaster.compare(dull, ref)
    assert any(m["freq_hz"] > 3000 and m["gain_db"] > 0 for m in cmp_["eq_moves"]), cmp_["eq_moves"]


def test_issue_flags(tmp_path):
    x = _noise(3, 6)
    x[1] = -x[1]  # polarity flipped right channel
    rep = mixmaster.measure(_wav(str(tmp_path / "phase.wav"), x))
    assert any("correlation" in i for i in rep.issues)


def test_mcp_server_over_stdio(tmp_path):
    mcp = pytest.importorskip("mcp")
    from mcp import Client, StdioServerParameters

    wav = _wav(str(tmp_path / "t.wav"), _noise(2, 7))

    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "track2ableton.live.mcp_server"],
                                       env={**os.environ, "T2A_PORT": "9"})
        async with Client(params) as c:
            names = {t.name for t in (await c.list_tools()).tools}
            assert {"live_session", "write_notes", "set_parameter", "sidechain", "routing", "spectrogram", "master_report"} <= names
            r = await c.call_tool("spectrogram", {"file_path": wav, "width": 100, "height": 50})
            assert type(r.content[0]).__name__ == "ImageContent"
            r = await c.call_tool("live_session", {})
            assert r.is_error and "T2A_Bridge" in r.content[0].text

    asyncio.run(run())
