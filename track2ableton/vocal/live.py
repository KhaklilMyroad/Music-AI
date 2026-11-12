"""The vocal score of a MIDI clip in the open Live Set: read the clip through the bridge, write the score files."""
from __future__ import annotations

from typing import Any, Callable

from . import score as vs


def score_clip(call: Callable[..., Any], track, lyrics: str, out_dir: str, lang: str = "en", slot: int | None = None,
               arrangement_index: int | None = None, fit: str = "strict", phrase_gap: float = 1.0, name: str = "vocal") -> dict:
    """call(cmd, **args) is LiveClient.call. Note times are the clip's own (beat 0 = the start of the clip), so a
    rendered vocal goes into the arrangement where the clip starts."""
    lang = vs.language(lang)                          # before Live is asked for anything
    if (slot is None) == (arrangement_index is None):
        raise ValueError("give slot (Session) or arrangement_index (Arrangement), one of them")
    session = call("get_session")
    beats = int(str(session.get("signature", "4/4")).split("/")[0])
    args = {"track": track, "slot": slot} if slot is not None else {"track": track, "arrangement_index": arrangement_index}
    notes = call("get_notes", **args)
    if not notes:
        raise ValueError("the clip has no notes")
    sc = vs.build(notes, lyrics, lang, float(session["tempo"]), beats, fit, phrase_gap)
    res = vs.write(sc, out_dir, name)
    res["next"] = ("Open one of the files in the singing engine, render the voice at this tempo, and put the audio in the "
                   "arrangement where the clip starts." if sc.ok else "Fix the errors (see problems) and run again before rendering.")
    return res
