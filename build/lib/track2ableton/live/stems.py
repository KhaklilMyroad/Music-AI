"""Split an audio file into stems and put them on tracks of the open Live Set."""
from __future__ import annotations

import os
from typing import Any, Callable

from .. import audio as aio, separation


def split(file_path: str, out_dir: str | None = None, method: str = "auto", model: str = "htdemucs_6s") -> dict:
    """Stems as WAV files in `out_dir` (default: '<name> stems' next to the file). With Demucs installed the split is
    neural; without it the built-in one is used, which is rough, and the result says so."""
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"audio file not found: {file_path}")
    base = os.path.splitext(os.path.basename(file_path))[0]
    out_dir = out_dir or os.path.join(os.path.dirname(os.path.abspath(file_path)), f"{base} stems")
    os.makedirs(out_dir, exist_ok=True)
    song = aio.load(file_path)
    st = separation.separate(file_path, song, method, model, workdir=os.path.join(out_dir, "_demucs_tmp"))
    files = {}
    for name, a in st.stems.items():
        if aio.rms_db(a.mono) < -50:
            continue                                  # an empty stem (no piano in the song) is not worth a track
        files[name] = aio.save(os.path.join(out_dir, f"{base} - {name}.wav"), a.data, a.sr)
    return {"method": st.method, "note": st.quality_note, "folder": out_dir, "stems": files}


def to_live(call: Callable[..., Any], stems: dict[str, str], position: float = 0.0, prefix: str = "") -> list[dict]:
    """One audio track per stem with the file at `position` (arrangement beats). Tracks are appended; nothing existing
    is changed. If a step fails the tracks made so far are removed again."""
    made, done = [], []
    try:
        for name, path in stems.items():
            idx = call("create_track", kind="audio", name=f"{prefix}{name}")["index"]
            made.append(idx)
            call("create_audio_clip", track=idx, file_path=os.path.abspath(path), position=float(position))
            done.append({"track": f"{prefix}{name}", "index": idx, "file": path})
    except Exception:
        for idx in reversed(made):
            try:
                call("delete_track", track=idx)
            except Exception:
                pass
        raise
    return done
