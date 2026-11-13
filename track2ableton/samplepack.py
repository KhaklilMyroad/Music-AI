"""A sample pack out of a track: loops cut on the song's bar lines, and drum one-shots.

What makes a loop usable is that it starts on the hit that opens its bar and is exactly its bars long. The bar lines
come from the analysis of the whole mix (the beat map, so a tempo that is not round or drifts is followed), and each
loop's start is then moved onto the nearest hit in the mix where there is one, the same for every stem, so that
loops from different stems still line up. Loops are counted in phrases from the first bar that has sound.

What is left out, and said so in the manifest: bars with no sound, a loop that repeats one already taken, a stretch
where the analysis lost the beat, a stem that is nearly empty, and what is only bleed from another stem.

The analysis can be wrong, and the manifest carries what it is unsure of: its notes, its confidence in the tempo, and
for every loop how far the start was moved. If the tempo came out as twice or half the real one, or the bars as 3/4,
give `about_bpm` or `beats_per_bar`: nothing in the audio settles those for certain.

Only make a pack from music you own or have cleared: samples cut from someone else's recording are theirs.
"""
from __future__ import annotations

import json
import os

import numpy as np

from . import audio as aio, clash, pipeline, separation, transcribe as tr

PRE_S = 0.003            # a loop starts this much before its hit, so the hit keeps its attack
FADE_S = 0.0015
QUIET_DB = -45.0
EMPTY_STEM_DB = -30.0    # a stem this far under the mix is bleed, not a part
BLEED_DB = -18.0         # so is a loop this far under the same stem's loudest loop
SAME = 0.993             # two loops whose pictures are this alike are the same loop
SNAP_S = 0.03            # how far a loop's start may move to sit on a hit
PIECES = ("kick", "snare", "clap", "hat", "hihat", "hh", "tom", "ride", "crash", "shaker", "conga", "bongo", "cowbell",
          "clave", "rim", "tambourine", "perc")


def _key_tag(key_name: str) -> str:
    root, mode = key_name.split()
    return root + ("m" if mode == "minor" else "")


def _signature(a: aio.Audio, bars: int) -> np.ndarray:
    """A picture of the loop to tell repeats apart: its loudness in every third of an octave, sixteen slices to the
    bar. Fine enough that a busier hi-hat, a fill or a pumping pad is another loop."""
    m = clash.loudness(clash.power_map(a)).sum(axis=0)
    slices = max(16, 16 * bars)
    if m.shape[0] < slices:
        m = np.repeat(m, int(np.ceil(slices / max(1, m.shape[0]))), axis=0)
    cut = np.linspace(0, m.shape[0], slices + 1).astype(int)
    v = np.stack([m[cut[i]:max(cut[i] + 1, cut[i + 1])].mean(axis=0) for i in range(slices)]).ravel()
    return v / (np.linalg.norm(v) + 1e-12)


def _attack_near(mono: np.ndarray, sr: int, t: float, reach: float = SNAP_S) -> float | None:
    """The moment within `reach` of second t where a hit begins, or None if nothing clearly begins there."""
    a, b = max(0, int((t - reach) * sr)), min(mono.size, int((t + reach) * sr))
    w = max(1, int(0.002 * sr))
    if b - a < 4 * w:
        return None
    env = np.convolve(np.abs(mono[a:b]), np.ones(w) / w, mode="same")
    rise = env[w:] - env[:-w]
    k = int(np.argmax(rise))
    level = float(env[min(env.size - 1, k + w)])
    if level <= 0 or rise[k] < 0.5 * level or level < 0.25 * float(env.max()):
        return None                                   # a swell or a tail, not a hit
    j = k
    while j > 0 and env[j] > 0.1 * level:
        j -= 1
    return (a + j) / sr


def _level_db(data: np.ndarray) -> float:
    """RMS of the louder channel: a stem whose two channels cancel in mono is still sound."""
    return max(aio.rms_db(ch) for ch in data)


def _piece_of(stem_name: str) -> str | None:
    words = separation._words(stem_name)
    for w in words:
        for p in PIECES:
            if w == p or w == p + "s":
                return "hat" if p in ("hihat", "hh") else p
    return None


def _trim_one_shot(clip: np.ndarray, sr: int) -> np.ndarray:
    """Start two milliseconds before the hit, with a millisecond of fade-in: a sampler plays it on time and without a click."""
    peak = float(np.max(np.abs(clip)))
    if peak <= 0:
        return clip
    first = int(np.argmax(np.abs(clip) >= 0.1 * peak))
    clip = clip[max(0, first - int(0.002 * sr)):].copy()
    f = min(clip.size, max(1, int(0.001 * sr)))
    clip[:f] *= np.linspace(0, 1, f)
    return clip


def _clear_previous(out_dir: str) -> None:
    """Remove the files an earlier run into this folder listed, so that the folder and its manifest agree."""
    try:
        with open(os.path.join(out_dir, "pack.json"), encoding="utf-8") as fh:
            old = json.load(fh)
    except (OSError, ValueError):
        return
    for e in list(old.get("loops", [])) + list(old.get("one_shots", [])):
        f = os.path.normpath(os.path.join(out_dir, str(e.get("file", ""))))
        if f.startswith(os.path.normpath(out_dir) + os.sep) and os.path.isfile(f):
            os.remove(f)


def build(source: str, out_dir: str | None = None, name: str | None = None, bars: int = 4, max_loops_per_stem: int = 6,
          separation_method: str = "auto", demucs_model: str = "htdemucs_6s", normalize_db: float | None = -1.0,
          about_bpm: float | None = None, beats_per_bar: int | None = None, log=print) -> dict:
    """source: an audio file (it is split into stems first) or a folder of stems. about_bpm: the tempo if you know it
    roughly (the Live Set's); beats_per_bar: 3 or 4 if you know it. Returns the manifest."""
    if bars < 1 or max_loops_per_stem < 1:
        raise ValueError("bars and max_loops_per_stem must be 1 or more")
    src = os.path.normpath(os.path.abspath(source))
    if os.path.isdir(src):
        audio_files = sorted(f for f in os.listdir(src) if f.lower().endswith(separation.AUDIO_EXT) and not f.startswith("."))
        if len(audio_files) == 1:
            src = os.path.join(src, audio_files[0])
    given = separation.from_folder(src) if os.path.isdir(src) else None
    song = separation.mixdown(given) if given else aio.load(src)
    if song.sr > 48000:
        song = song.resampled(44100)
    if song.duration < pipeline.MIN_SECONDS:
        raise ValueError(f"{song.duration:.1f} s of audio is too short to find bars in")
    mix_db = _level_db(song.data)
    if mix_db < -60:
        raise ValueError("the audio is silent, or nearly: there is nothing to cut")
    base = os.path.basename(src) if os.path.isdir(src) else os.path.splitext(os.path.basename(src))[0]
    name = pipeline._slug(name or base)
    out_dir = out_dir or os.path.join(os.path.dirname(src), f"{base} Sample Pack")
    sr = song.sr
    mix = song.mono
    rhythm, tonal, beat_map, bar_grid = pipeline.musical_grid(mix, sr, song.duration, about_bpm, beats_per_bar)
    bpb = rhythm.beats_per_bar
    key = _key_tag(tonal.key_name)
    stems = given or separation.separate(src, song, separation_method, demucs_model, workdir=os.path.join(out_dir, "_demucs_tmp"))
    kinds = {n: stems.kinds.get(n, n if n in pipeline.STEM_ORDER else "other") for n in stems.stems}
    loops_dir, shots_dir = os.path.join(out_dir, "Loops"), os.path.join(out_dir, "One Shots")
    os.makedirs(out_dir, exist_ok=True)
    _clear_previous(out_dir)
    for d in (loops_dir, shots_dir):
        os.makedirs(d, exist_ok=True)
    pre, fade = int(PRE_S * sr), max(1, int(FADE_S * sr))

    # Bars with sound in the mix; phrases are counted from the first of them, not from the start of the file.
    edges = [int(round(t * sr)) for t in bar_grid]
    sounding = [aio.rms_db(mix[a:b]) > QUIET_DB for a, b in zip(edges, edges[1:])]
    first_bar = next((i for i, s in enumerate(sounding) if s), 0)
    starts = list(range(first_bar, len(bar_grid) - bars, bars))     # every loop needs the bar line that ends it
    lost = [(a, b) for a, b in beat_map.lost] if beat_map.drifting else []
    hit_at = {i: _attack_near(mix, sr, float(bar_grid[i])) for i in starts}
    entries, shots, skipped, used = [], [], [], set()
    in_lost = 0
    for stem_name in sorted(stems.stems):
        a = stems.stems[stem_name]
        if a.sr != sr:
            a = a.resampled(sr)
        if _level_db(a.data) < mix_db + EMPTY_STEM_DB:
            skipped.append(f"{stem_name}: nearly empty ({_level_db(a.data) - mix_db:.0f} dB against the mix), probably bleed")
            continue
        slug = pipeline._slug(stem_name)
        while slug in used:
            slug += "_2"
        used.add(slug)
        found = []
        for i in starts:
            t0, t1 = float(bar_grid[i]), float(bar_grid[i + bars])
            if any(t0 < b and t1 > a_ for a_, b in lost):
                in_lost += 1
                continue
            start = hit_at[i] if hit_at[i] is not None else t0
            length = int(round((t1 - t0) * sr))
            lo = int(round(start * sr)) - pre
            if lo + length > a.data.shape[1]:
                continue
            seg = np.zeros((a.data.shape[0], length), dtype=np.float32)
            src_lo = max(0, lo)                                    # a file that starts on its downbeat: silence stands in for the pre-roll
            seg[:, src_lo - lo:] = a.data[:, src_lo:lo + length]
            bar_len = length // bars
            alive = sum(_level_db(seg[:, k * bar_len:(k + 1) * bar_len]) > QUIET_DB for k in range(bars))
            if alive * 2 < bars or _level_db(seg) < QUIET_DB:
                continue                                           # silence, or sound in less than half of its bars
            sig = _signature(aio.Audio(seg, sr), bars)
            if any(float(sig @ f["sig"]) >= SAME for f in found):
                continue
            found.append({"sig": sig, "seg": seg, "bar": i, "seconds": length / sr, "peak": float(np.max(np.abs(seg))),
                          "moved_ms": 0.0 if hit_at[i] is None else (hit_at[i] - t0) * 1000, "on_a_hit": hit_at[i] is not None})
        if found:
            loudest = max(f["peak"] for f in found)
            bleed = [f for f in found if f["peak"] < loudest * 10 ** (BLEED_DB / 20)]
            if bleed:
                skipped.append(f"{stem_name}: {len(bleed)} loop(s) more than {-BLEED_DB:.0f} dB under the stem's loudest, left out as bleed")
            found = [f for f in found if not any(f is x for x in bleed)]
        if len(found) > max_loops_per_stem:                        # spread over the song, not the first few
            pick = np.unique(np.round(np.linspace(0, len(found) - 1, max_loops_per_stem)).astype(int))
            found = [found[k] for k in pick]
        for n, f in enumerate(found, 1):
            seg = f["seg"]
            seg[:, :fade] *= np.linspace(0, 1, fade, dtype=np.float32)
            seg[:, -fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
            peak = float(np.max(np.abs(seg)))
            gain_db = 0.0
            if peak > 0 and (normalize_db is not None or peak > 1.0):
                gain_db = (normalize_db if normalize_db is not None else 0.0) - 20 * np.log10(peak)     # over full scale is turned down, and said
                seg = seg * 10 ** (gain_db / 20)
            bpm = bars * bpb * 60.0 / f["seconds"]
            tag = f"{bpm:.0f}" if abs(bpm - round(bpm)) < 0.05 else f"{bpm:.1f}"
            fname = f"{name}_{slug}_{bars}bar_{tag}bpm" + ("" if kinds[stem_name] == "drums" else f"_{key}") + f"_{n:02d}.wav"
            aio.save(os.path.join(loops_dir, fname), seg, sr)
            entry = {"file": f"Loops/{fname}", "stem": stem_name, "kind": kinds[stem_name], "bars": bars,
                     "from_bar": f["bar"] + 1, "seconds": round(f["seconds"], 4), "bpm": round(bpm, 2),
                     "gain_db": round(float(gain_db), 1), "starts_on_a_hit": f["on_a_hit"], "start_moved_ms": round(f["moved_ms"], 1)}
            if kinds[stem_name] != "drums":
                entry["key"] = tonal.key_name
            entries.append(entry)
        if kinds[stem_name] == "drums":
            mono = a.data.mean(axis=0) if aio.rms_db(a.data.mean(axis=0)) > QUIET_DB else a.data[0]
            hits = tr.detect_drum_hits(mono, sr)
            named = _piece_of(stem_name)
            if named:                                              # a stem of one instrument: its name says what the hit is
                hits = [tr.DrumHit(named, h.time, h.strength) for h in hits]
            for piece, clip in sorted(tr.extract_one_shots(mono, sr, hits).items()):
                clip = _trim_one_shot(clip, sr)
                peak = float(np.max(np.abs(clip))) if clip.size else 0.0
                if peak <= 0:
                    continue
                if normalize_db is not None or peak > 1.0:
                    clip = clip * 10 ** ((normalize_db or 0.0) / 20) / peak
                fname = f"{name}_{slug}_{piece}.wav"
                aio.save(os.path.join(shots_dir, fname), clip, sr)
                shots.append({"file": f"One Shots/{fname}", "stem": stem_name, "piece": piece, "seconds": round(clip.size / sr, 3),
                              "label": "from the stem's name" if named else "a guess from the sound: a kick's tail or a hit under "
                                                                            "another can be in it. Listen before trusting the name"})
        log(f"  {stem_name}: {len(found)} loops")

    notes = []
    if beat_map.drifting:
        notes.append("The tempo is not steady: each loop is cut between the bar lines that were found, so its tempo is its own "
                     "(see bpm) and moves a little inside it.")
    if in_lost:
        notes.append(f"{in_lost} loop position(s) were left out because the beat could not be followed there (a sudden tempo change).")
    if rhythm.confidence < 0.3:
        notes.append(f"The tempo was found with low confidence ({rhythm.confidence:.2f} of 1): the bar lines may be wrong. "
                     "If you know the tempo, run again with it (about_bpm).")
    moved = [abs(e["start_moved_ms"]) for e in entries if e["starts_on_a_hit"]]
    if moved and max(moved) > 12:
        notes.append(f"Loop starts were moved by up to {max(moved):.0f} ms to sit on a hit: the tempo that was found is slightly off, "
                     "so the grid slides along the song. The loops themselves start on their hits.")
    if stems.method.startswith("dsp"):
        notes.append("Stems came from the rough built-in split: expect bleed between them. Install Demucs for clean stems.")
    if not about_bpm:
        notes.append("If the tempo here is twice or half what you know it to be, or the bars came out in 3 when the song is in 4, "
                     "run again with about_bpm / beats_per_bar: the loops are then cut at the wrong length.")
    manifest = {
        "name": name, "source": os.path.basename(src), "stems": stems.method, "stems_note": stems.quality_note,
        "tempo_bpm": round(float(rhythm.bpm), 3), "tempo_confidence": round(float(rhythm.confidence), 2),
        "tempo_steady": not beat_map.drifting, "time_signature": f"{bpb}/4", "key": tonal.key_name,
        "key_confidence": round(float(np.nan_to_num(tonal.key_confidence)), 2), "first_bar_with_sound": first_bar + 1,
        "loops": entries, "one_shots": shots, "skipped_files": stems.skipped, "left_out": skipped,
        "analysis_notes": list(rhythm.notes),
        "rights": "Samples cut from a recording belong to whoever owns that recording. Release or sell this pack only if the "
                  "source is your own music or you have cleared it.",
        "notes": notes,
    }
    with open(os.path.join(out_dir, "pack.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1, cls=pipeline._Enc)
    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(_readme(manifest))
    return dict(manifest, folder=out_dir)


def _readme(m: dict) -> str:
    L = [f"# {m['name']}: חבילת סאמפלים", "",
         f"- מקור: {m['source']}. טמפו: {m['tempo_bpm']:g} BPM ({'יציב' if m['tempo_steady'] else 'לא יציב'}, ביטחון {m['tempo_confidence']:g} מתוך 1), "
         f"משקל {m['time_signature']}. סולם: {m['key']} (ביטחון {m['key_confidence']:g} מתוך 1).",
         f"- {len(m['loops'])} לופים ו-{len(m['one_shots'])} one-shots. כל לופ נחתך לפי קווי התיבה שהניתוח מצא, מתחיל על המכה שפותחת את התיבה "
         "כשיש שם מכה, ואורכו מספר התיבות שבשם לפי הטמפו שנמדד.",
         "- הטמפו, המשקל והסולם הם מדידה, והיא יכולה לטעות. אם הטמפו כאן כפול או חצי ממה שאתה מכיר, הלופים באורך לא נכון: להריץ שוב עם הטמפו הידוע.",
         "- לופ של צליל ממושך (פד, סאב ארוך) מקבל פייד קצר בקצוות, ובנגינה בלולאה נשמעת שם נגיעה קלה.",
         "- **זכויות:** סאמפלים שנחתכו מהקלטה שייכים לבעלי ההקלטה. מותר לשחרר או למכור את החבילה רק אם המקור הוא מוזיקה שלך, או שקיבלת אישור.", ""]
    if m["notes"] or m["analysis_notes"]:
        L += ["## הערות", ""] + [f"- {n}" for n in m["notes"] + m["analysis_notes"]] + [""]
    if m["left_out"]:
        L += ["## מה נשאר בחוץ", ""] + [f"- {n}" for n in m["left_out"]] + [""]
    L += ["## לופים", "", "| קובץ | סטם | תיבות | מתיבה | BPM | מתחיל על מכה | הוזז (ms) |", "|---|---|---|---|---|---|---|"]
    L += [f"| {e['file']} | {e['stem']} | {e['bars']} | {e['from_bar']} | {e['bpm']:g} | {'כן' if e['starts_on_a_hit'] else 'לא'} | {e['start_moved_ms']:g} |"
          for e in m["loops"]]
    if m["one_shots"]:
        L += ["", "## One-shots", "", "| קובץ | סטם | כלי | מקור השם |", "|---|---|---|---|"]
        L += [f"| {e['file']} | {e['stem']} | {e['piece']} | {'שם הסטם' if e['label'].startswith('from') else 'ניחוש לפי הסאונד'} |" for e in m["one_shots"]]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    from ._console import safe_output
    safe_output()
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="track2ableton-samplepack", description="Loops cut on the song's bar lines, and drum "
                                 "one-shots, from an audio file or a folder of stems.")
    ap.add_argument("source")
    ap.add_argument("-o", "--out")
    ap.add_argument("--name")
    ap.add_argument("--bars", type=int, default=4)
    ap.add_argument("--max-loops", type=int, default=6, help="per stem")
    ap.add_argument("--bpm", type=float, help="the tempo, if you know it roughly: settles twice-or-half")
    ap.add_argument("--beats-per-bar", type=int, help="3 or 4, if you know it")
    ap.add_argument("--separation", choices=["auto", "demucs", "dsp"], default="auto")
    ap.add_argument("--no-normalize", action="store_true", help="keep the level of the source instead of peaking at -1 dBFS")
    args = ap.parse_args(argv)
    if not os.path.exists(args.source):
        print(f"error: not found: {args.source}", file=sys.stderr)
        return 2
    try:
        m = build(args.source, args.out, args.name, args.bars, args.max_loops, args.separation,
                  normalize_db=None if args.no_normalize else -1.0, about_bpm=args.bpm, beats_per_bar=args.beats_per_bar)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"\n  {len(m['loops'])} loops, {len(m['one_shots'])} one-shots, {m['tempo_bpm']:g} BPM, {m['key']}\n  {m['folder']}")
    for n in m["notes"]:
        print(f"  ! {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
