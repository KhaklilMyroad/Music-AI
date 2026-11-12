"""A melody and its words as one vocal score: a syllable on every note, checked for what a singer (or a singing
engine) cannot do, written as MIDI with lyrics, MusicXML and JSON.

This prepares the score. It does not sing: the sound comes from whatever singing engine reads these files.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from types import SimpleNamespace
from xml.sax.saxutils import escape

from .. import midi
from . import lyrics as ly

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Comfortable ranges as MIDI numbers (60 = middle C, which Ableton calls C3). Textbook values; singers differ.
VOICES = {"soprano": (60, 81), "mezzo-soprano": (57, 77), "alto": (53, 74), "tenor": (48, 69), "baritone": (43, 64), "bass": (40, 62)}
FAST_S = 0.09            # a new syllable on a note shorter than this cannot be articulated
BREATH_S = 0.2           # the shortest gap a breath fits in
PHRASE_S = 8.0           # singing longer than this without such a gap


@dataclass
class Sung:
    pitch: int
    start: float                     # beats
    duration: float
    syllable: ly.Syllable | None     # None: no lyric reached this note
    hold: bool = False               # the note carries on the syllable before it


@dataclass
class Score:
    bpm: float
    beats_per_bar: int
    notes: list[Sung]
    problems: list[dict] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not any(p["level"] == "error" for p in self.problems)


def ableton_name(pitch: int) -> str:
    return f"{NAMES[pitch % 12]}{pitch // 12 - 2}"


def _where(start: float, bpb: int) -> str:
    """Bar.beat.sixteenth, the way Live shows a position."""
    six = int(round(start * 4))
    return f"{six // (bpb * 4) + 1}.{six % (bpb * 4) // 4 + 1}.{six % 4 + 1}"


def _strength(start: float, bpb: int) -> int:
    """How strong a place in the bar is: 4 the downbeat, 3 the middle of the bar, 2 another beat, 1 an 8th, 0 anything finer."""
    step = (start % bpb) * 4
    if abs(step - round(step)) > 0.05:
        return 0
    step = int(round(step)) % (bpb * 4)
    if step == 0:
        return 4
    if bpb % 2 == 0 and step == bpb * 2:
        return 3
    return 2 if step % 4 == 0 else 1 if step % 2 == 0 else 0


def _p(level: str, kind: str, at: str, detail: str, **data) -> dict:
    return {"level": level, "kind": kind, "at": at, "detail": detail, "data": data}


def build(notes, text: str, lang: str = "en", bpm: float = 120.0, beats_per_bar: int = 4, fit: str = "strict",
          phrase_gap: float = 1.0) -> Score:
    """notes: anything with pitch, start, duration (beats) - objects or dicts. fit="strict" reports a line whose
    syllables and notes differ in number; fit="end" lets the last syllable of such a line carry the extra notes."""
    if fit not in ("strict", "end"):
        raise ValueError("fit must be 'strict' or 'end'")
    if not 20 <= bpm <= 400:
        raise ValueError("bpm out of range")
    get = (lambda n, k: n[k]) if notes and isinstance(notes[0], dict) else getattr
    raw = sorted(((int(get(n, "pitch")), float(get(n, "start")), float(get(n, "duration"))) for n in notes
                  if not (isinstance(n, dict) and n.get("mute"))), key=lambda n: (n[1], -n[0]))
    problems: list[dict] = []
    melody: list[list] = []
    for p, s, d in raw:                             # one note at a time: a voice cannot sing a chord
        if melody and abs(melody[-1][1] - s) < 1e-6:
            problems.append(_p("error", "chord", _where(s, beats_per_bar),
                               f"{ableton_name(melody[-1][0])} and {ableton_name(p)} start together; the higher one was kept",
                               a=ableton_name(melody[-1][0]), b=ableton_name(p)))
            continue
        if melody and melody[-1][1] + melody[-1][2] > s + 1e-6:
            problems.append(_p("warning", "overlap", _where(s, beats_per_bar),
                               f"{ableton_name(melody[-1][0])} was still sounding; it was shortened to end here", a=ableton_name(melody[-1][0])))
            melody[-1][2] = s - melody[-1][1]
        melody.append([p, s, d])
    sylls = ly.parse(text, lang)
    lines: dict[int, list[ly.Syllable]] = {}
    for s in sylls:
        lines.setdefault(s.line, []).append(s)
    phrases: list[list[list]] = []
    for n in melody:
        if phrases and n[1] - (phrases[-1][-1][1] + phrases[-1][-1][2]) < phrase_gap - 1e-9:
            phrases[-1].append(n)
        else:
            phrases.append([n])
    by_line = len(lines) == len(phrases) and len(lines) > 0
    units = list(zip(lines.values(), phrases)) if by_line else [(sylls, melody)]
    sung: list[Sung] = []
    for i, (words, part) in enumerate(units):
        if not part:
            continue
        label = f"line {i + 1}" if by_line else "the whole lyric"
        if words and words[0].hold:
            problems.append(_p("error", "hold", _where(part[0][1], beats_per_bar),
                               f"{label} starts with a hold sign: there is no syllable before it to carry on", line=i + 1 if by_line else 0))
        if len(words) != len(part):
            extra = len(part) - len(words)
            eased = fit == "end" and extra > 0 and words
            problems.append(_p("warning" if eased else "error", "count", _where(part[0][1], beats_per_bar),
                               f"{label}: {len(words)} syllables for {len(part)} notes"
                               + (f"; the last syllable carries the {extra} extra notes" if eased else ""),
                               line=i + 1 if by_line else 0, syllables=len(words), notes=len(part), eased=bool(eased)))
        for k, (p, s, d) in enumerate(part):
            if k < len(words):
                sung.append(Sung(p, s, d, None if words[k].hold else words[k], words[k].hold))
            else:
                sung.append(Sung(p, s, d, None, fit == "end" and bool(words)))
    if not by_line and len(lines) > 1 and len(phrases) > 1:
        problems.append(_p("info", "lines", "", f"{len(lines)} lyric lines but {len(phrases)} phrases of notes (a rest of {phrase_gap:g} "
                           "beat or more ends a phrase), so the lyric was laid on the notes in one run. With one line per phrase a "
                           "mistake stays inside its line.", lines=len(lines), phrases=len(phrases), gap=phrase_gap))
    score = Score(float(bpm), int(beats_per_bar), sung, problems)
    _check(score, sylls)
    return score


def _check(sc: Score, sylls: list[ly.Syllable]) -> None:
    beat_s = 60.0 / sc.bpm
    bpb = sc.beats_per_bar
    P = sc.problems
    notes = sc.notes
    for n in notes:
        if n.syllable is not None and n.duration * beat_s < FAST_S:
            P.append(_p("warning", "fast", _where(n.start, bpb),
                        f"'{n.syllable.text}' has {n.duration * beat_s * 1000:.0f} ms: too short to pronounce a syllable",
                        text=n.syllable.text, ms=round(n.duration * beat_s * 1000)))
    for a, b in zip(notes, notes[1:]):
        if abs(b.pitch - a.pitch) > 12:
            P.append(_p("warning", "leap", _where(b.start, bpb),
                        f"a leap of {abs(b.pitch - a.pitch)} semitones ({ableton_name(a.pitch)} to {ableton_name(b.pitch)})",
                        n=abs(b.pitch - a.pitch), a=ableton_name(a.pitch), b=ableton_name(b.pitch)))
    run_start = notes[0].start if notes else 0.0
    for a, b in zip(notes, notes[1:] + [None]):
        gap = (b.start - (a.start + a.duration)) * beat_s if b is not None else 1e9
        if gap >= BREATH_S:
            length = (a.start + a.duration - run_start) * beat_s
            if length > PHRASE_S:
                P.append(_p("warning", "breath", _where(run_start, bpb),
                            f"{length:.1f} s of singing with no gap of {BREATH_S * 1000:.0f} ms to breathe in", s=round(length, 1)))
            if b is not None:
                run_start = b.start
        elif a.syllable is not None and a.syllable.breath_after and b is not None and not b.hold:
            P.append(_p("info", "comma", _where(b.start, bpb),
                        f"the lyric pauses after '{a.syllable.word}' but the next note follows without a gap", word=a.syllable.word))
    # word stress against the bar: an unstressed syllable on a clearly stronger place than the stressed one
    group: list[Sung] = []
    for n in notes + [None]:
        s = n.syllable if n is not None else None
        if s is not None and group and s.index == group[-1].syllable.index + 1 and s.word == group[-1].syllable.word:
            group.append(n)
            continue
        if len(group) > 1 and any(g.syllable.stressed for g in group):
            top = next(g for g in group if g.syllable.stressed)
            for g in group:
                if g is not top and _strength(g.start, bpb) - _strength(top.start, bpb) >= 2 and top.duration < 2 * g.duration:
                    P.append(_p("info", "stress", _where(top.start, bpb),
                                f"'{top.syllable.word}': the stressed syllable '{top.syllable.text}' falls on a weaker place "
                                f"in the bar than '{g.syllable.text}'", word=top.syllable.word, top=top.syllable.text, other=g.syllable.text))
                    break
        group = [n] if s is not None and s.count > 1 and s.index == 1 else []
    unsure = sorted({s.word for s in sylls if not s.sure and not s.hold})
    if unsure:
        P.append(_p("info", "dictionary", "", "not in the pronouncing dictionary, syllables counted from the spelling: "
                    + ", ".join(unsure) + ". Type a word with hyphens (af-ro-tech) to set its syllables yourself.", words=unsure))
    if notes:
        lo, hi = min(n.pitch for n in notes), max(n.pitch for n in notes)
        fits = [v for v, (a, b) in VOICES.items() if a <= lo and hi <= b]
        shifts = {v: next((k for k in (12, -12, 24, -24) if a <= lo + k and hi + k <= b), None) for v, (a, b) in VOICES.items() if v not in fits}
        sc.info["range"] = {"lowest": ableton_name(lo), "highest": ableton_name(hi), "lowest_midi": lo, "highest_midi": hi,
                            "semitones": hi - lo, "fits": fits,
                            "fits_after_transposing": {v: k for v, k in shifts.items() if k is not None}}
        if hi - lo > 21:
            P.append(_p("warning", "range", "", f"the melody spans {hi - lo} semitones ({ableton_name(lo)} to {ableton_name(hi)}): "
                        "wider than one voice sings comfortably", n=hi - lo, a=ableton_name(lo), b=ableton_name(hi)))
    sc.info["note_count"] = len(notes)
    sc.info["syllable_count"] = sum(1 for s in sylls if not s.hold)
    sc.info["length_s"] = round((notes[-1].start + notes[-1].duration) * beat_s, 2) if notes else 0.0


# ------------------------------------------------------------------------------------------- files

def to_json(sc: Score) -> dict:
    rows = []
    for n in sc.notes:
        s = n.syllable
        rows.append({"pitch": n.pitch, "name": ableton_name(n.pitch), "start": round(n.start, 4), "duration": round(n.duration, 4),
                     "bar_beat": _where(n.start, sc.beats_per_bar), "text": s.text if s else ("-" if n.hold else ""),
                     "word": s.word if s else "", "syllable": f"{s.index}/{s.count}" if s else "",
                     "phonemes": s.phonemes if s else [], "stressed": s.stressed if s else None, "hold": n.hold})
    return {"bpm": sc.bpm, "time_signature": f"{sc.beats_per_bar}/4", "ready": sc.ok, **sc.info, "problems": sc.problems, "notes": rows}


def _lyric_events(sc: Score) -> list[tuple[float, str]]:
    """One lyric per note that starts a syllable; a syllable that is not the last of its word ends in a hyphen."""
    return [(n.start, n.syllable.text + ("-" if n.syllable.index < n.syllable.count else ""))
            for n in sc.notes if n.syllable is not None]


_TYPES = [(16, "whole", 0), (12, "half", 1), (8, "half", 0), (6, "quarter", 1), (4, "quarter", 0), (3, "eighth", 1), (2, "eighth", 0), (1, "16th", 0)]


def musicxml(sc: Score, part_name: str = "Vocal") -> str:
    """The score on a 16th grid (notes are rounded to it; triplets are not written). A note that crosses a bar line
    or is not one plain value is written as tied notes; the lyric sits on the first of them."""
    bar = sc.beats_per_bar * 4
    events = []                                     # (start 16th, length in 16ths, Sung or None for a rest)
    pos = 0
    for n in sc.notes:
        a = max(pos, int(round(n.start * 4)))
        b = max(a + 1, int(round((n.start + n.duration) * 4)))
        if a > pos:
            events.append((pos, a - pos, None))
        events.append((a, b - a, n))
        pos = b
    if pos % bar:
        events.append((pos, bar - pos % bar, None))
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">',
           '<score-partwise version="3.1">', f'<part-list><score-part id="P1"><part-name>{escape(part_name)}</part-name></score-part></part-list>',
           '<part id="P1">']
    measure = -1

    def open_measure(m: int):
        nonlocal measure
        if measure >= 0:
            out.append("</measure>")
        measure = m
        out.append(f'<measure number="{m + 1}">')
        if m == 0:
            out.append(f"<attributes><divisions>4</divisions><key><fifths>0</fifths></key><time><beats>{sc.beats_per_bar}</beats>"
                       "<beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef></attributes>")
            out.append(f'<direction placement="above"><direction-type><metronome><beat-unit>quarter</beat-unit><per-minute>{sc.bpm:g}'
                       f'</per-minute></metronome></direction-type><sound tempo="{sc.bpm:g}"/></direction>')

    for start, length, n in events:
        pieces = []                                 # cut at bar lines, then into plain note values
        at, left = start, length
        while left > 0:
            room = bar - at % bar
            size = next(v for v, _, _ in _TYPES if v <= min(left, room))
            pieces.append((at, size))
            at, left = at + size, left - size
        for k, (at, size) in enumerate(pieces):
            if at // bar != measure:
                open_measure(at // bar)
            _, kind, dots = next(t for t in _TYPES if t[0] == size)
            x = ["<note>"]
            if n is None:
                x.append("<rest/>")
            else:
                step = NAMES[n.pitch % 12]
                x.append(f"<pitch><step>{step[0]}</step>{'<alter>1</alter>' if len(step) > 1 else ''}<octave>{n.pitch // 12 - 1}</octave></pitch>")
            x.append(f"<duration>{size}</duration>")
            ties = [] if n is None else (["stop"] if k > 0 else []) + (["start"] if k < len(pieces) - 1 else [])
            x += [f'<tie type="{t}"/>' for t in ties]
            x.append(f"<voice>1</voice><type>{kind}</type>" + "<dot/>" * dots)
            if ties:
                x.append("<notations>" + "".join(f'<tied type="{t}"/>' for t in ties) + "</notations>")
            if n is not None and n.syllable is not None and k == 0:
                s = n.syllable
                place = "single" if s.count == 1 else "begin" if s.index == 1 else "end" if s.index == s.count else "middle"
                x.append(f'<lyric number="1"><syllabic>{place}</syllabic><text>{escape(s.text)}</text></lyric>')
            x.append("</note>")
            out.append("".join(x))
    if measure < 0:
        open_measure(0)
    out += ["</measure>", "</part>", "</score-partwise>", ""]
    return "\n".join(out)


def write(sc: Score, out_dir: str, name: str = "vocal") -> dict:
    os.makedirs(out_dir, exist_ok=True)
    data = to_json(sc)
    paths = {k: os.path.join(out_dir, f"{name}.{ext}") for k, ext in (("json", "json"), ("midi", "mid"), ("musicxml", "musicxml"))}
    paths["report"] = os.path.join(out_dir, f"{name.upper()}_REPORT.md")
    with open(paths["json"], "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    notes = [SimpleNamespace(pitch=n.pitch, start=n.start, duration=n.duration, velocity=100) for n in sc.notes]
    midi.write(paths["midi"], notes, sc.bpm, "Vocal", 0, sc.beats_per_bar, lyrics=_lyric_events(sc))
    with open(paths["musicxml"], "w", encoding="utf-8") as fh:
        fh.write(musicxml(sc))
    with open(paths["report"], "w", encoding="utf-8") as fh:
        fh.write(report(sc))
    return {"files": paths, **{k: v for k, v in data.items() if k != "notes"}}


_KIND = {"count": "מספר ההברות והתווים לא תואם", "chord": "שני תווים יחד", "overlap": "תווים חופפים", "hold": "סימן המשך בלי הברה לפניו",
         "fast": "הברה מהירה מדי", "leap": "קפיצה גדולה", "breath": "אין מקום לנשום", "comma": "פסיק בלי הפסקה",
         "stress": "הטעמה נגד המשקל", "dictionary": "מילים שלא במילון", "range": "מנעד רחב", "lines": "שורות מול משפטים"}
_LEVEL = {"error": "שגיאה", "warning": "אזהרה", "info": "לידיעה"}


def _hebrew(p: dict) -> str:
    d, k = p.get("data", {}), p["kind"]
    line = f"שורה {d['line']}" if d.get("line") else "כל המילים"
    if k == "count":
        if d["eased"]:
            hint = "; ההברה האחרונה נמשכת על התווים העודפים"
        elif d["notes"] > d["syllables"]:
            hint = ". יש יותר תווים מהברות: לכתוב - במילים במקום של כל תו שממשיך את ההברה שלפניו"
        else:
            hint = ". יש יותר הברות מתווים: להוסיף תווים למלודיה או לקצר את המילים"
        return f"{line}: {d['syllables']} הברות ל-{d['notes']} תווים{hint}"
    if k == "chord":
        return f"{d['a']} ו-{d['b']} מתחילים יחד; נשאר הגבוה מהם"
    if k == "overlap":
        return f"{d['a']} עדיין נשמע כשהתו הבא מתחיל; הוא קוצר כך שיסתיים כאן"
    if k == "hold":
        return f"{line} מתחילה בסימן המשך, ואין לפניו הברה להמשיך"
    if k == "fast":
        return f"'{d['text']}' מקבלת {d['ms']} אלפיות שנייה: קצר מדי כדי לבטא הברה"
    if k == "leap":
        return f"קפיצה של {d['n']} חצאי טונים ({d['a']} ל-{d['b']})"
    if k == "breath":
        return f"{d['s']:g} שניות של שירה בלי הפסקה של {BREATH_S * 1000:.0f} אלפיות שנייה לנשימה"
    if k == "comma":
        return f"במילים יש הפסקה אחרי '{d['word']}', אבל התו הבא מגיע בלי רווח"
    if k == "stress":
        return f"'{d['word']}': ההברה המוטעמת '{d['top']}' יושבת במקום חלש יותר בתיבה מאשר '{d['other']}'"
    if k == "dictionary":
        return ("לא במילון ההגייה, ולכן ההברות נספרו לפי הכתיב: " + ", ".join(d["words"])
                + ". אפשר לכתוב מילה עם מקפים (af-ro-tech) כדי לקבוע את ההברות")
    if k == "range":
        return f"המלודיה משתרעת על {d['n']} חצאי טונים ({d['a']} עד {d['b']}): רחב ממה שקול אחד שר בנוחות"
    if k == "lines":
        return (f"{d['lines']} שורות מילים אבל {d['phrases']} משפטים של תווים (הפסקה של {d['gap']:g} פעמות ומעלה סוגרת משפט), ולכן המילים "
                "הונחו על התווים ברצף אחד. כשיש שורה לכל משפט, טעות נשארת בתוך השורה שלה")
    return p["detail"]


def report(sc: Score) -> str:
    info = sc.info
    L = ["# פרטיטורה ווקאלית", "",
         "הקבצים מכינים את השירה: הברה לכל תו, עם בדיקות. הם לא שרים. את הקול מפיק מנוע השירה שקורא אותם, והאוזן קובעת אם זה טוב.", "",
         f"- {info.get('note_count', 0)} תווים, {info.get('syllable_count', 0)} הברות, {info.get('length_s', 0):g} שניות ב-{sc.bpm:g} BPM.",
         f"- מצב: **{'מוכן' if sc.ok else 'לא מוכן: יש שגיאות לתקן'}**."]
    r = info.get("range")
    if r:
        L.append(f"- מנעד: {r['lowest']} עד {r['highest']} בשמות של Ableton ({r['semitones']} חצאי טונים). "
                 + ("מתאים לפי טווחים מקובלים ל: " + ", ".join(r["fits"]) + "." if r["fits"] else "לא נכנס בשלמותו לטווח מקובל של אף סוג קול.")
                 + (" אחרי טרנספוזיציה: " + ", ".join(f"{v} ({k:+d})" for v, k in r["fits_after_transposing"].items()) + "."
                    if r["fits_after_transposing"] else "") + " הטווחים הם ערכי ספר, וזמרים שונים זה מזה.")
    if sc.problems:
        L += ["", "## ממצאים", "", "| רמה | מה | איפה (תיבה.פעמה.שש-עשרית) | פירוט |", "|---|---|---|---|"]
        for p in sorted(sc.problems, key=lambda p: ("error", "warning", "info").index(p["level"])):
            L.append(f"| {_LEVEL[p['level']]} | {_KIND.get(p['kind'], p['kind'])} | {p['at']} | {_hebrew(p)} |")
    L += ["", "## הברה לכל תו", "", "| מיקום | תו | אורך (פעמות) | הברה | מילה | פונמות |", "|---|---|---|---|---|---|"]
    for n in sc.notes:
        s = n.syllable
        L.append(f"| {_where(n.start, sc.beats_per_bar)} | {ableton_name(n.pitch)} | {n.duration:g} | "
                 f"{(('**' + s.text + '**') if s.stressed else s.text) if s else ('(המשך)' if n.hold else '—')} | "
                 f"{s.word if s else ''} | {' '.join(s.phonemes) if s else ''} |")
    L += ["", "הברה מודגשת היא ההברה המוטעמת של מילה בת כמה הברות.", ""]
    return "\n".join(L)
