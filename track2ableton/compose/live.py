"""Put a composition into the running Live Set through the T2A bridge: one MIDI track and one
Arrangement clip per part, notes written and read back.

Tested against the fake Live in tests/, not against a real Live. What the bridge cannot do, you do
by hand or in the .als: load instruments, move tracks into groups, and set each clip's Groove to None
(Live gives new clips the set's default groove; with the feel baked into the MIDI that would swing twice).
"""
from __future__ import annotations

from typing import Any, Callable

from .arrange import Composition
from .model import bar_start


def push(comp: Composition, call: Callable[..., Any], at_bar: int = 1, prefix: str = "", set_tempo: bool = True,
         only: list | None = None) -> dict:
    """call(cmd, **args) is LiveClient.call. Clips start at `at_bar`; use a bar after the song to audition
    without touching it. Refuses to create a track whose name already exists. If a step fails, the tracks this
    call created are deleted again and the error is raised, so a retry starts clean (the tempo is not restored)."""
    if at_bar < 1:
        raise ValueError("at_bar must be 1 or more")
    names = [t.name for t in comp.tracks]
    unknown = sorted(set(only or []) - set(names))
    if unknown:
        raise ValueError(f"unknown track(s) {unknown}; this composition has {names}")
    existing = {t["name"] for t in call("get_session")["tracks"]}
    todo = [t for t in comp.tracks if not only or t.name in only]
    clash = sorted(prefix + t.name for t in todo if prefix + t.name in existing)
    if clash:
        raise ValueError(f"tracks already exist: {clash}; pass a prefix or delete them first")
    if set_tempo:
        call("set_song", tempo=comp.spec.bpm)
    start = bar_start(at_bar)
    done, created = [], []
    try:
        for t in todo:
            idx = call("create_track", kind="midi", name=prefix + t.name)["index"]
            created.append(idx)
            n_clips = call("create_arrangement_midi_clip", track=idx, start=start, length=comp.total_beats)["arrangement_clips"]
            ai = n_clips - 1
            notes = [{"pitch": n.pitch, "start": n.start, "duration": n.duration, "velocity": n.velocity} for n in t.notes]
            for i in range(0, len(notes), 400):
                call("add_notes", track=idx, arrangement_index=ai, notes=notes[i:i + 400])
            back = call("get_notes", track=idx, arrangement_index=ai, time_span=comp.total_beats + 1)
            done.append({"track": prefix + t.name, "index": idx, "written": len(notes), "read_back": len(back),
                         "ok": len(back) == len(notes)})
    except Exception as exc:
        left = []
        for idx in reversed(created):          # new tracks are appended, so deleting from the highest index keeps the rest valid
            try:
                call("delete_track", track=idx)
            except Exception:
                left.append(idx)
        raise RuntimeError(f"push failed ({exc}); removed {len(created) - len(left)} of the {len(created)} track(s) it had created"
                           + (f", track index(es) {left} are still there" if left else "")) from exc
    return {"tracks": done, "ok": all(d["ok"] for d in done),
            "todo_by_hand": ["Set Groove = None on every new clip." if comp.spec.bake_feel else "Apply the swing groove to the swung tracks.",
                             "Load an instrument on each track (see arrangement.json).", "Operator on Sub: Voices = 1."]}
