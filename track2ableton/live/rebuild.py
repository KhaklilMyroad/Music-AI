"""Build a track2ableton analysis inside the running Live Set through the bridge."""
from __future__ import annotations

import json
import math
import os
from typing import Any, Callable

from .. import midi

# Map recipe device names to names Live shows in its browser / insert API.
NATIVE = {"Drift": "Drift", "Operator": "Operator", "Wavetable": "Wavetable", "EQ Eight": "EQ Eight",
          "Compressor": "Compressor", "Glue Compressor": "Glue Compressor", "Utility": "Utility",
          "Auto Filter": "Auto Filter", "Saturator": "Saturator", "Reverb": "Reverb", "Echo": "Echo", "Limiter": "Limiter"}


def rebuild(project_dir: str, call: Callable[..., Any], slot: int = 0) -> dict:
    recipe = json.load(open(os.path.join(project_dir, "recipe.json"), encoding="utf-8"))
    log: list[str] = []
    bpm = recipe["tempo"]["bpm"]
    call("set_song", tempo=bpm)
    log.append(f"tempo {bpm}")
    session = call("get_session")
    n_scenes = len(session["scenes"])
    while n_scenes <= slot:
        call("scene", action="create", index=-1)
        n_scenes += 1
    for tr in recipe["tracks"]:
        # reference stem on an audio track
        stem = os.path.join(project_dir, tr["audio_file"]) if tr.get("audio_file") else None
        if stem and os.path.exists(stem):
            ref = call("create_track", kind="audio", name=f"REF {tr['name']}")
            try:
                call("create_audio_clip", track=ref["index"], file_path=os.path.abspath(stem), slot=slot)
                call("set_track", track=ref["index"], mute=tr["stem"] != "vocals")
                log.append(f"REF {tr['name']}: stem in slot {slot}")
            except Exception as exc:
                log.append(f"REF {tr['name']}: track created, stem not placed ({exc}); drag {stem} in manually")
        if tr["kind"] != "midi" or not tr.get("midi_file"):
            continue
        t = call("create_track", kind="midi", name=f"{tr['name']} ({tr['role']})")
        idx = t["index"]
        chain = ([tr["instrument"]] if tr.get("instrument") else []) + tr.get("devices", [])
        for dev in chain:
            name = NATIVE.get(dev["name"])
            if tr["stem"] == "drums" and dev["name"] == "Drum Rack":
                name = "Drum Rack"
            if not name:
                log.append(f"{tr['name']}: skipped '{dev['name']}' (no native equivalent to load automatically)")
                continue
            try:
                call("insert_device", track=idx, name=name)
                log.append(f"{tr['name']}: + {name}")
            except Exception as exc:
                log.append(f"{tr['name']}: could not add {name} ({exc})")
        notes = midi.read(os.path.join(project_dir, tr["midi_file"]))
        if notes:
            length = max(4.0, math.ceil(max(n["start"] + n["duration"] for n in notes) / 4) * 4)
            call("create_clip", track=idx, slot=slot, length=length, name=tr["name"])
            for i in range(0, len(notes), 500):  # keep messages small
                call("add_notes", track=idx, slot=slot, notes=notes[i:i + 500])
            log.append(f"{tr['name']}: {len(notes)} notes in slot {slot}")
        for ret, lvl in (tr.get("sends") or {}).items():
            log.append(f"{tr['name']}: suggested send {ret} {lvl:.0f} dB (create returns, then use set_send)")
    return {"done": log, "note": "Device parameters from the recipe are listed in report.html; set them with set_parameter "
                                 "after checking names with get_device."}
