"""Write a composition to disk: one MIDI file per track, a combined General-MIDI drum file,
arrangement.json (sections, tracks, Ableton hints, check results) and REPORT.md (Hebrew)."""
from __future__ import annotations

import json
import os
import re
from types import SimpleNamespace

from .. import midi
from .arrange import Composition
from .model import bar_start
from .parts import sub_pitch
from .theory import PROGRESSIONS, DEFAULT_PROGRESSION, build_progression, key_name, note_name, uses_flats
from .validate import all_ok, validate


def _clock(seconds: float) -> str:
    tenths = int(round(seconds * 10))
    return f"{tenths // 600}:{(tenths % 600) / 10:04.1f}"


def summary(comp: Composition, checks: list | None = None) -> dict:
    sp = comp.spec
    checks = checks if checks is not None else validate(comp)
    prog = sp.progression or DEFAULT_PROGRESSION[comp.mode]
    chords = {k: build_progression(comp.tonic, comp.mode, sp.progression, k) for k in ("main", "break")}
    labels = {k: [c.label for c in v] for k, v in chords.items()}
    roots = [sub_pitch(c.root_pc) for c in chords["main"]]
    leap = max(abs(a - b) for a, b in zip(roots, roots[1:] + roots[:1]))
    flats = uses_flats(comp.tonic, comp.mode)
    return {
        "bpm": sp.bpm, "key": key_name(comp.tonic, comp.mode), "progression": prog, "chords": labels,
        "sub_roots": [note_name(p, flats) for p in roots], "sub_largest_root_leap_semitones": leap,
        "bars_per_chord": 2, "structure": sp.structure, "variant": sp.variant,
        "swing_percent": sp.swing, "skins_late_ms": sp.late_ms, "feel_baked_into_midi": sp.bake_feel,
        "total_bars": comp.total_bars, "length": _clock(comp.seconds(comp.total_bars + 1)),
        "sections": [{"name": s.name, "kind": s.kind, "first_bar": s.start, "bars": s.bars, "time": _clock(comp.seconds(s.start)),
                      "tracks": sorted(set().union(*(comp.bars[b].roles for b in range(s.start, s.start + s.bars))))}
                     for s in comp.sections],
        "tracks": [{"index": i, "name": t.name, "group": t.group, "role": t.role, "file": f"MIDI/{i:02d} {t.name}.mid",
                    "notes": len(t.notes), "swung": t.swing, "late_ms": t.late_ms,
                    "groove_in_live": "None" if (sp.bake_feel or not t.swing) else f"16th swing {sp.swing:g} %",
                    "straight_bars": sorted(t.straight_bars),
                    "pitches": [note_name(p, flats) for p in sorted({n.pitch for n in t.notes})] if t.role != "drum" else ["C3"],
                    "instrument": t.hint}
                   for i, t in enumerate(comp.tracks, 1)],
        "ableton_notes": [
            "Set the project tempo before importing; put every clip at bar 1 (1.1.1).",
            "Feel is baked into the MIDI: every clip must have Groove = None, otherwise percussion is swung twice."
            if sp.bake_feel else
            f"MIDI is straight: apply one 16th-swing groove ({sp.swing:g} %) to the tracks marked swung and none to the rest; set Track Delay "
            f"+{sp.late_ms:g} ms on the tracks with late_ms; a track's 'straight_bars' should not be swung (split the clip there or accept it).",
            "Drum tracks use C3 (60): one Simpler / sample per track. 'drums_gm.mid' holds the same hits on General-MIDI notes for a Drum Rack.",
            "Sub: Operator Voices must be 1 (set by hand). Only the sub plays below ~100 Hz besides the kick.",
            "Chant track: C3 = chant on beats 1-2, D3 = shout on beat 4 before a drop. Load your own licensed vocal chops.",
            "Risers, filter sweeps and the build's high-pass are automation: add them in Live.",
        ],
        "checks": [{"check": c.name, "ok": c.ok, "detail": c.detail} for c in checks], "all_checks_passed": all_ok(checks),
        "progressions_available": sorted(PROGRESSIONS),
    }


def write(comp: Composition, out_dir: str) -> dict:
    mdir = os.path.join(out_dir, "MIDI")
    os.makedirs(mdir, exist_ok=True)
    for old in os.listdir(mdir):          # an earlier export into the same folder must not leave stale parts behind
        if re.fullmatch(r"\d\d .+\.mid", old) or old == "drums_gm.mid":
            os.remove(os.path.join(mdir, old))
    for i, t in enumerate(comp.tracks, 1):
        midi.write(os.path.join(mdir, f"{i:02d} {t.name}.mid"), t.notes, comp.spec.bpm, t.name)
    gm = sorted((SimpleNamespace(pitch=t.gm_pitch, start=n.start, duration=n.duration, velocity=n.velocity)
                 for t in comp.tracks if t.role == "drum" for n in t.notes), key=lambda n: (n.start, n.pitch))
    if gm:
        midi.write(os.path.join(mdir, "drums_gm.mid"), gm, comp.spec.bpm, "Drums (GM)", channel=9)
    checks = validate(comp)
    info = summary(comp, checks)
    with open(os.path.join(out_dir, "arrangement.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write(report(comp, info))
    return info


def report(comp: Composition, info: dict) -> str:
    names = [t.name for t in comp.tracks]
    L = [f"# הלחנה: {info['key']}, {info['bpm']:g} BPM, {info['total_bars']} תיבות ({info['length']})", "",
         f"- מהלך: **{info['progression']}** – {' → '.join(info['chords']['main'])} (אקורד לכל 2 תיבות)",
         f"- בברייק: {' → '.join(info['chords']['break'])}",
         f"- מבנה: {info['structure']}, וריאנט {info['variant']}",
         f"- שורשי הסאב: {' → '.join(info['sub_roots'])}"
         + (f" (קפיצה של {info['sub_largest_root_leap_semitones']} חצאי טונים: טווח הסאב הוא אוקטבה אחת, ולכן בסולם הזה הליין קופץ. "
            "בסולמות A, Bb ו-B הירידה חלקה)" if info["sub_largest_root_leap_semitones"] > 7 else ""),
         f"- סווינג לפרקשן: {info['swing_percent']:g}%, העורות מאחרים ב-{info['skins_late_ms']:g}ms"
         + (" (כתוב בתוך ה-MIDI, לכן Groove = None בכל הקליפים)" if info["feel_baked_into_midi"] else " (ה-MIDI ישר, להחיל גרוב ב-Live)"),
         "", "הבדיקות למטה בודקות את התווים: תזמון, הרמוניה ומבנה. הן לא יכולות לקבוע אם זה נשמע טוב. את זה קובעת האוזן.", "",
         "## מבנה", "", "| קטע | תיבות | זמן | מה מנגן |", "|---|---|---|---|"]
    for s in info["sections"]:
        L.append(f"| {s['name']} | {s['first_bar']}–{s['first_bar'] + s['bars'] - 1} | {s['time']} | {', '.join(n for n in names if n in s['tracks']) or 'שקט'} |")
    L += ["", "## ערוצים", "", "| # | ערוץ | קבוצה | תווים | סווינג | כלי מוצע |", "|---|---|---|---|---|---|"]
    for t in info["tracks"]:
        L.append(f"| {t['index']} | {t['name']} | {t['group']} | {t['notes']} | {'כן' if t['swung'] else 'לא'} | {t['instrument']} |")
    L += ["", "## בדיקות", "", "| בדיקה | תוצאה | פירוט |", "|---|---|---|"]
    for c in info["checks"]:
        L.append(f"| {c['check']} | {'עבר' if c['ok'] else 'נכשל'} | {c['detail']} |")
    L += ["", "## ב-Ableton", ""] + [f"- {x}" for x in info["ableton_notes"]] + [""]
    return "\n".join(L)


def bar_table(comp: Composition, first: int, last: int) -> str:
    """Text grid of a bar range, one row per track, one character per 16th (x loud, o soft, . rest)."""
    rows = []
    for t in comp.tracks:
        cells = ["."] * ((last - first + 1) * 16)
        lo = bar_start(first)
        for n in t.notes:
            i = int(round((n.grid - lo) / 0.25))
            if 0 <= i < len(cells) and abs((n.grid - lo) / 0.25 - i) < 1e-6:
                cells[i] = "x" if n.velocity >= 90 else "o"
        if any(c != "." for c in cells):
            rows.append(f"{t.name:10} " + " ".join("".join(cells[k:k + 16]) for k in range(0, len(cells), 16)))
    return "\n".join(rows)
