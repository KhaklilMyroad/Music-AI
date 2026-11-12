"""Take a finished recording (one file, or a folder of stems) and put it right: a round, steady project tempo that
the stems are warped to, notes that agree with their own repetitions, one chord loop, and a Live Set to go on from.

What it changes is counted per track in FIX_REPORT.md, and the notes as first heard stay in MIDI_raw/ to compare.
It works on notes and timing. It does not judge sound, and it has no way to know a deliberate one-off from a mistake
except where the mistake sits: that is what the report's "left as heard" numbers are for.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict

import numpy as np

from .. import midi, pipeline, tonal as tn, transcribe as tr
from . import notes as nt

PIECE = {v: k for k, v in tr.DRUM_NOTES.items()}


def _merge_sections(sections: list) -> list:
    """Neighbouring sections the analysis found alike (same letter) are one section: its boundaries inside a
    stretch of the same material are where the chords turn, not where the song does."""
    out = []
    for s in sections:
        if out and out[-1].letter == s.letter:
            p = out[-1]
            w0, w1 = p.end_bar - p.start_bar, s.end_bar - s.start_bar
            p.energy_db = (p.energy_db * w0 + s.energy_db * w1) / max(1, w0 + w1)
            p.end_bar, p.end = s.end_bar, s.end
        else:
            out.append(s)
    return out


def _clear_previous(out_dir: str, source: str) -> None:
    """A second run into the same folder must not mix in the first run's files: a stem that is gone, or last
    time's repaired notes turning up as this time's raw ones. Only folders this tool writes are removed, only when
    the folder holds an earlier result, and never one the source itself is in."""
    if not any(os.path.exists(os.path.join(out_dir, f)) for f in ("fix.json", "recipe.json")):
        return
    src = os.path.normcase(os.path.abspath(source))
    for name in ("MIDI", "MIDI_raw", "Stems", "Samples"):
        d = os.path.join(out_dir, name)
        inside = os.path.commonpath([src, os.path.normcase(os.path.abspath(d))]) == os.path.normcase(os.path.abspath(d))
        if os.path.isdir(d) and not inside:
            shutil.rmtree(d)
    for f in os.listdir(out_dir):
        if f.endswith(" Rebuild.als"):
            os.remove(os.path.join(out_dir, f))


def _turns(a, bpb: int) -> set[int]:
    """Arrangement bars (0-based) that end a 4-bar phrase or a section."""
    lead = int(a.lead_in_beats // bpb)
    out = set()
    for s in a.sections:
        lo, hi = s.start_bar + lead, s.end_bar + lead
        out |= {b for b in range(lo, hi) if (b - lo + 1) % 4 == 0} | {hi - 1}
    return out


def _half_bar_chords(a, bpb: int, total_beats: float) -> list[tuple[int, str]]:
    half = bpb / 2
    seq = []
    for h in range(int(np.ceil(total_beats / half))):
        t = float(a.to_seconds((h + 0.5) * half))
        c = next((c for c in a.chords if c.start <= t < c.end), None)
        seq.append((c.root, c.quality) if c is not None and c.root >= 0 else (-1, ""))
    return seq


def _tones(root: int, quality: str) -> set[int]:
    return {(root + i) % 12 for i in tn.CHORD_TEMPLATES[quality]} if root >= 0 else set()


def run(source: str, out_dir: str, bpm: float | None = None, light: bool = False, separation_method: str = "auto",
        demucs_model: str = "htdemucs_6s", transcription: str = "auto", write_als: bool = True,
        als_template: str | None = None, log=print) -> dict:
    if als_template and not os.path.isfile(als_template):
        raise FileNotFoundError(f"template not found: {als_template}")          # before minutes of analysis, not after
    if os.path.isdir(out_dir):
        _clear_previous(out_dir, source)
    a = pipeline.run(source, out_dir, separation_method, demucs_model, transcription, write_als=False, log=log)
    bpb = a.rhythm.beats_per_bar
    measured = float(a.rhythm.bpm)
    a.project_bpm = float(bpm) if bpm else float(round(measured))
    a.sections = _merge_sections(a.sections)
    total_beats = float(a.to_beats(a.duration))
    turns = _turns(a, bpb)

    # ---------------------------------------------------------------- harmony: one loop, voted per place in it
    seq = _half_bar_chords(a, bpb, total_beats)
    prog = nt.chord_loop(seq, lambda r, q: tn.Chord(0, 0, r, q).name)
    scale = set(a.tonal.scale_pcs)

    def allowed(pc: int, beat: float) -> bool:
        h = int(beat // (bpb / 2))
        return pc in scale or (0 <= h < len(prog.fixed) and pc in _tones(*prog.fixed[h]))

    chords = []
    for h, (root, q) in enumerate(prog.fixed):
        s, e = float(a.to_seconds(h * bpb / 2)), float(a.to_seconds((h + 1) * bpb / 2))
        if chords and chords[-1].root == root and chords[-1].quality == q:
            chords[-1].end = e
        else:
            chords.append(tn.Chord(s, e, root, q))
    a.chords = chords

    # ---------------------------------------------------------------- notes
    midi_dir, raw_dir = os.path.join(out_dir, "MIDI"), os.path.join(out_dir, "MIDI_raw")
    if os.path.isdir(raw_dir):
        shutil.rmtree(raw_dir)
    os.rename(midi_dir, raw_dir)
    os.makedirs(midi_dir)
    rows = []
    kick_steps: set[int] = set()
    for t in a.tracks:
        if not t.midi_file:
            continue
        raw = list(t.clip_notes)
        row = {"track": t.name, "kind": t.stem, "midi": t.midi_file, "raw_notes": len(raw)}
        if t.stem == "drums":
            fixed, reps = nt.repair_drums(raw, bpb, turns, light)
            row["pieces"] = {PIECE.get(p, str(p)): asdict(r) for p, r in reps.items()}
            row["changed"] = sum(r.changed for r in reps.values())
            row["voted_bars"], row["bars"] = sum(r.voted for r in reps.values()), sum(r.bars for r in reps.values())
            kick_steps |= {nt._step(n.start) for n in fixed if n.pitch == tr.DRUM_NOTES["kick"]}
            if t.instrument is not None:
                t.instrument.params["patterns_16_steps"] = tr.drum_patterns(fixed, bpb)
        elif t.stem == "vocals":
            fixed = raw                               # the voice stays audio; its MIDI is only a guide
            row.update(changed=0, voted_bars=0, bars=0, note="left as heard: the vocal stays audio, this MIDI is a guide")
        else:
            fixed, rep = (nt.repair_mono if t.stem == "bass" else nt.repair_poly)(raw, bpb, turns, allowed, light)
            row.update(asdict(rep), changed=rep.changed, voted_bars=rep.voted)
        row["fixed_notes"] = len(fixed)
        t.clip_notes = fixed
        midi.write(os.path.join(out_dir, t.midi_file), fixed, a.project_bpm, t.name, 9 if t.stem == "drums" else 0, bpb)
        if t.stem not in ("drums", "bass", "vocals"):
            base = 48 if t.measurements["spectrum"]["centroid_hz"] < 1500 else 60
            path = os.path.join(midi_dir, os.path.splitext(os.path.basename(t.midi_file))[0] + "_chords.mid")
            midi.write(path, tr.chords_to_midi(chords, a.to_beats, base).notes, a.project_bpm, f"{t.name} chords", 0, bpb)
        rows.append(row)

    # ---------------------------------------------------------------- what the result looks like
    findings = []
    for t in a.tracks:
        if t.stem == "bass" and t.clip_notes and kick_steps:
            on = sum(1 for n in t.clip_notes if nt._step(n.start) in kick_steps)
            findings.append({"finding": "bass_notes_starting_on_a_kick", "track": t.name, "count": on, "of": len(t.clip_notes)})
    lead = int(a.lead_in_beats // bpb)
    turn = (2 * lead) % max(1, len(prog.chords))          # show the loop from the first downbeat, not from the lead-in bar
    loop = prog.chords[turn:] + prog.chords[:turn]
    sections = [{"name": s.role, "letter": s.letter, "first_bar": s.start_bar + lead + 1, "bars": s.bars,
                 "whole_phrases": s.bars % 4 == 0} for s in a.sections]
    odd = [s for s in sections if not s["whole_phrases"]]
    bm = a.beat_map
    info = {
        "source": os.path.basename(os.path.normpath(a.source)), "stems": a.separation_method, "skipped_files": a.skipped_files,
        "tempo": {"measured_bpm": round(measured, 2), "project_bpm": a.project_bpm,
                  "stretch_percent": round((a.project_bpm / measured - 1) * 100, 2),
                  "drifting": a.drifting, "not_steady_but_not_followed": bm.unclear,
                  "furthest_from_constant_grid_ms": round(bm.drift_ms, 1),
                  "slowest_8_bars_bpm": round(bm.bpm_lo, 2), "fastest_8_bars_bpm": round(bm.bpm_hi, 2),
                  "followed_blind_s": [[round(x, 1), round(y, 1)] for x, y in bm.weak],
                  "found_again_at_s": [round(x, 1) for x in bm.relocked],
                  "map_does_not_fit_audio_s": [[round(x, 1), round(y, 1)] for x, y in bm.lost],
                  "warp_markers": len(a.warp_markers()), "time_signature": f"{bpb}/4"},
        "key": {"name": a.tonal.key_name, "confidence": round(a.tonal.key_confidence, 2)},
        "progression": {"loop_bars": prog.loop_bars, "chords_per_half_bar": loop, "share_of_song": round(prog.share, 2),
                        "half_bars_changed": prog.changed},
        "sections": sections, "mode": "light" if light else "normal", "tracks": rows, "findings": findings,
        "warnings": a.warnings,
    }
    def save():
        with open(os.path.join(out_dir, "fix.json"), "w", encoding="utf-8") as fh:
            json.dump(info, fh, ensure_ascii=False, indent=1, cls=pipeline._Enc)
        with open(os.path.join(out_dir, "FIX_REPORT.md"), "w", encoding="utf-8") as fh:
            fh.write(report(info, odd))

    save()                                            # the report first: a Live Set that fails to write must not cost it
    try:
        pipeline.write_outputs(a, out_dir, write_als, log, als_template)
    except Exception as exc:
        info["als_error"] = f"{type(exc).__name__}: {exc}"
        pipeline.write_outputs(a, out_dir, False, log, None)
        save()
    return info


def report(info: dict, odd: list[dict]) -> str:
    t = info["tempo"]
    L = [f"# תיקון: {info['source']}", "",
         "הדוח מפרט מה נמדד ומה שונה. הכלי מתקן תזמון ותווים לפי החזרות של השיר עצמו. הוא לא שומע, ולא קובע אם זה נשמע טוב.", "",
         "## טמפו", "",
         f"- נמדד: **{t['measured_bpm']:g} BPM** ({t['time_signature']}). טמפו הפרויקט: **{t['project_bpm']:g} BPM** "
         f"(מתיחה של {t['stretch_percent']:+.2f}%)."]
    if abs(t["stretch_percent"]) > 6:
        L.append("- **המתיחה גדולה.** ייתכן שהטמפו נמדד בחצי או בכפול מהאמיתי (למשל 70 במקום 140), או ש-`--bpm` רחוק מהשיר. "
                 "לבדוק לפני שממשיכים.")
    if t["drifting"]:
        L.append(f"- הטמפו **לא יציב**: פעמות יושבות עד {t['furthest_from_constant_grid_ms']:g}ms מגריד קבוע "
                 f"({t['slowest_8_bars_bpm']:g}–{t['fastest_8_bars_bpm']:g} BPM). התווים וסמני ה-Warp עוקבים אחרי הפעמות האמיתיות "
                 f"({t['warp_markers']} סמנים).")
    elif t["not_steady_but_not_followed"]:
        L.append(f"- **הטמפו לא יציב, והמעקב לא הצליח לעקוב אחריו בביטחון.** פעמות יושבות עד {t['furthest_from_constant_grid_ms']:g}ms "
                 "מגריד קבוע, ונשאר גריד קבוע. הסיבה הרגילה היא שינוי טמפו באמצע השיר, שהכלי לא תומך בו. "
                 "התווים וסמני ה-Warp עלולים להיות לא נכונים בחלק מהשיר: לבדוק את הגריד באוזן בכל קטע.")
    else:
        L.append(f"- הטמפו יציב (סטייה מרבית מגריד קבוע: {t['furthest_from_constant_grid_ms']:g}ms). מספיקים {t['warp_markers']} סמני Warp.")
    if t["map_does_not_fit_audio_s"]:
        L.append("- **המעקב איבד את הפעמה** ב: " + ", ".join(f"{x:g}–{y:g} שניות" for x, y in t["map_does_not_fit_audio_s"])
                 + ". שם פחות מחצי מהמכות יושבות על הגריד שנמצא, כנראה בגלל שינוי טמפו חד שהכלי לא יודע לעקוב אחריו. "
                 "התווים וסמני ה-Warp בקטעים האלה לא אמינים.")
    if t["drifting"] and t["followed_blind_s"]:
        L.append("- קטעים שבהם הפעמה לא הייתה ברורה והמעקב המשיך לפי הקצב שלפניהם (לבדוק באוזן): "
                 + ", ".join(f"{x:g}–{y:g} שניות" for x, y in t["followed_blind_s"]) + ".")
    if t["drifting"] and t["found_again_at_s"]:
        L.append("- הפעמה נמצאה מחדש אחרי קטע כזה ב: " + ", ".join(f"{x:g}" for x in t["found_again_at_s"])
                 + " שניות. אם משהו זז שם בחצי פעמה, זה המקום.")
    p = info["progression"]
    L += ["", "## סולם ואקורדים", "", f"- סולם: **{info['key']['name']}** (ביטחון {info['key']['confidence']:g} מתוך 1)."]
    if p["loop_bars"]:
        runs: list[list] = []
        for c in p["chords_per_half_bar"]:
            if runs and runs[-1][0] == c:
                runs[-1][1] += 0.5
            else:
                runs.append([c, 0.5])
        L.append(f"- מהלך שחוזר כל {p['loop_bars']} תיבות, מהדאונביט הראשון: "
                 + " → ".join(f"{c} ({n:g} {'תיבה' if n == 1 else 'תיבות'})" for c, n in runs))
        L.append(f"- {p['share_of_song'] * 100:.0f}% מהשיר תואם למהלך הזה. {p['half_bars_changed']} חצאי תיבות שבהם זוהה אקורד קרוב "
                 "(שני צלילים משותפים לפחות) הוחלפו באקורד של המהלך. אקורד שונה באמת נשאר כמו שזוהה.")
    else:
        L.append("- לא נמצא מהלך אקורדים שחוזר. האקורדים נשארו כמו שזוהו.")
    L += ["", "## מבנה", "", "| קטע | מתיבה | תיבות | הערה |", "|---|---|---|---|"]
    for s in info["sections"]:
        L.append(f"| {s['name']} ({s['letter']}) | {s['first_bar']} | {s['bars']} | {'' if s['whole_phrases'] else 'לא כפולה של 4 תיבות'} |")
    L += ["", "גבולות הקטעים מוערכים מהאודיו, וייתכן שהם זזים בתיבה או שתיים."]
    if odd:
        L += [f"{len(odd)} קטעים באורך שאינו כפולה של 4 תיבות. לבדוק באוזן אם זה השיר או ההערכה. הכלי לא חותך ולא מוסיף תיבות."]
    L += ["", "## תווים", "",
          f"מצב: **{'עדין (משנה רק כשכל החזרות הסמוכות מסכימות)' if info['mode'] == 'light' else 'רגיל (רוב החזרות הסמוכות קובע)'}**. "
          "כל תיבה מושווית לחזרות הקרובות שלה. תיבה שאין לה לפחות שתי חזרות דומות נשארת כמו שנשמעה. "
          "בתיבה שסוגרת משפט, שתי הפעמות האחרונות לא נגעות, כי שם נמצאים פילים ומעברים.", "",
          "| ערוץ | תווים לפני | אחרי | הוסרו | נוספו | גובה תוקן | אוקטבה | חצי טון | לולאה (תיבות) | תיבות שנבדקו |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in info["tracks"]:
        if "pieces" in r:
            for name, q in r["pieces"].items():
                L.append(f"| {r['track']}: {name} | {q['raw']} | {q['fixed']} | {q['removed']} | {q['added']} | – | – | – | "
                         f"{q['loop_bars'] or 'אין'} | {q['voted']} מתוך {q['bars']} |")
        elif r.get("note"):
            L.append(f"| {r['track']} | {r['raw_notes']} | {r['fixed_notes']} | – | – | – | – | – | – | לא תוקן (ווקאל נשאר אודיו) |")
        else:
            guess = f" ({r['guessed']} בגובה מנוחש)" if r["guessed"] else ""
            L.append(f"| {r['track']} | {r['raw_notes']} | {r['fixed_notes']} | {r['removed']} | {r['added']}{guess} | {r['repitched']} | "
                     f"{r['folded']} | {r['snapped']} | {r['loop_bars'] or 'אין'} | {r['voted']} מתוך {r['bars']} |")
    kept = [(r["track"], r["outside_kept"]) for r in info["tracks"] if r.get("outside_kept")]
    if kept:
        L += ["", "צלילים מחוץ לסולם שנשארו, כי הם ארוכים או חוזרים באותו מקום בתיבה (כנראה מכוונים): "
              + "; ".join(f"{n}: {', '.join(k)}" for n, k in kept) + "."]
    if info["findings"]:
        L += ["", "## ממצאים שלא שונו", ""]
        for f in info["findings"]:
            L.append(f"- {f['track']}: {f['count']} מתוך {f['of']} תווים מתחילים יחד עם קיק. לא שונה. "
                     "איפה שהקיק והבאס מכים יחד, הסאב צריך sidechain או קיק קצר יותר.")
    if info["skipped_files"]:
        why = {"its name says it is a mix, not a stem": "לפי השם זה מיקס ולא סטם", "silent": "שקט"}
        L += ["", "## קבצים שלא נכנסו", ""]
        for x in info["skipped_files"]:
            name, _, reason = x.rpartition(": ")
            L.append(f"- {name}: {why.get(reason, reason)}")
    if info["warnings"]:
        L += ["", "## אזהרות מהניתוח (באנגלית, כמו שהכלי כותב אותן)", ""] + [f"- {x}" for x in info["warnings"]]
    if info.get("als_error"):
        L += ["", "## קובץ ה-.als לא נכתב", "", f"- {info['als_error']}", "- שאר הקבצים תקינים. אפשר לבנות דרך הגשר, או להריץ שוב עם `--template`."]
    L += ["", "## מה יש בתיקייה", "",
          "- `MIDI/` התווים אחרי התיקון. `MIDI_raw/` התווים כמו שזוהו, להשוואה.",
          "- `Stems/` הסטמים. ב-`.als` כל סטם כבר מונח עם סמני Warp לטמפו הפרויקט.",
          "- `fix.json` כל המספרים שבדוח הזה. `recipe.json` ו-`report.html` ניתוח הסאונד והמיקס.", ""]
    return "\n".join(L)
