"""A sample pack out of a track: loops cut on the song's real bar lines, and drum one-shots.

What makes a loop usable is that it is exactly its bars long. The bar lines come from the beat map, so they sit on
the beats the recording really has, also when its tempo is not round or drifts. Each stem gives loops of `bars`
bars starting on phrase lines; silent stretches are skipped and a loop that is a repeat of one already taken is
left out. Drum stems also give one hit of each kit piece.

Only make a pack from music you own or have cleared: samples cut from someone else's recording are theirs.
"""
from __future__ import annotations

import json
import os

import numpy as np

from . import audio as aio, clash, pipeline, separation, transcribe as tr

PRE_S = 0.003            # a loop starts this much before its bar line, so the first hit keeps its attack
FADE_S = 0.0015
QUIET_DB = -45.0
SAME = 0.97              # two loops whose loudness maps are this alike are the same loop


def _key_tag(key_name: str) -> str:
    root, mode = key_name.split()
    return root + ("m" if mode == "minor" else "")


def _signature(a: aio.Audio) -> np.ndarray:
    """A small picture of the loop (16 slices of time by its bands) to tell repeats apart."""
    m, _ = clash.loudness_map(a)
    if m.shape[0] < 16:
        m = np.pad(m, ((0, 16 - m.shape[0]), (0, 0)))
    cut = np.linspace(0, m.shape[0], 17).astype(int)
    v = np.stack([m[cut[i]:max(cut[i] + 1, cut[i + 1])].mean(axis=0) for i in range(16)]).ravel()
    return v / (np.linalg.norm(v) + 1e-12)


def build(source: str, out_dir: str | None = None, name: str | None = None, bars: int = 4, max_loops_per_stem: int = 6,
          separation_method: str = "auto", demucs_model: str = "htdemucs_6s", normalize_db: float | None = -1.0, log=print) -> dict:
    """source: an audio file (it is split into stems first) or a folder of stems. Returns the manifest."""
    if bars < 1 or max_loops_per_stem < 1:
        raise ValueError("bars and max_loops_per_stem must be 1 or more")
    src = os.path.normpath(os.path.abspath(source))
    if os.path.isdir(src):
        audio_files = sorted(f for f in os.listdir(src) if f.lower().endswith(separation.AUDIO_EXT))
        if len(audio_files) == 1:
            src = os.path.join(src, audio_files[0])
    given = separation.from_folder(src) if os.path.isdir(src) else None
    song = separation.mixdown(given) if given else aio.load(src)
    if song.sr > 48000:
        song = song.resampled(44100)
    if song.duration < pipeline.MIN_SECONDS:
        raise ValueError(f"{song.duration:.1f} s of audio is too short to find bars in")
    base = os.path.basename(src) if os.path.isdir(src) else os.path.splitext(os.path.basename(src))[0]
    name = pipeline._slug(name or base)
    out_dir = out_dir or os.path.join(os.path.dirname(src), f"{base} Sample Pack")
    sr = song.sr
    rhythm, tonal, beat_map, bar_grid = pipeline.musical_grid(song.mono, sr, song.duration)
    bpb = rhythm.beats_per_bar
    key = _key_tag(tonal.key_name)
    stems = given or separation.separate(src, song, separation_method, demucs_model, workdir=os.path.join(out_dir, "_demucs_tmp"))
    kinds = {n: stems.kinds.get(n, n if n in pipeline.STEM_ORDER else "other") for n in stems.stems}
    loops_dir, shots_dir = os.path.join(out_dir, "Loops"), os.path.join(out_dir, "One Shots")
    for d in (loops_dir, shots_dir):
        os.makedirs(d, exist_ok=True)
    pre, fade = int(PRE_S * sr), max(1, int(FADE_S * sr))
    starts = list(range(0, len(bar_grid) - bars, bars))            # every loop needs the bar line that ends it
    entries, shots, used = [], [], set()
    for stem_name in sorted(stems.stems):
        a = stems.stems[stem_name]
        if a.sr != sr:
            a = a.resampled(sr)
        slug = pipeline._slug(stem_name)
        while slug in used:
            slug += "_2"
        used.add(slug)
        found = []
        for i in starts:
            lo = int(round(bar_grid[i] * sr)) - pre
            hi = int(round(bar_grid[i + bars] * sr)) - pre
            if lo < 0 or hi > a.data.shape[1]:
                continue
            seg = a.data[:, lo:hi].astype(np.float32).copy()
            mono = seg.mean(axis=0)
            if aio.rms_db(mono) < QUIET_DB or np.mean(np.abs(mono) > 10 ** (QUIET_DB / 20)) < 0.05:
                continue                                           # silence, or a few stray clicks
            sig = _signature(aio.Audio(seg, sr))
            if any(float(sig @ f["sig"]) >= SAME for f in found):
                continue
            found.append({"sig": sig, "seg": seg, "bar": i, "seconds": (hi - lo) / sr})
        if len(found) > max_loops_per_stem:                        # spread over the song, not the first few
            pick = np.unique(np.round(np.linspace(0, len(found) - 1, max_loops_per_stem)).astype(int))
            found = [found[k] for k in pick]
        for n, f in enumerate(found, 1):
            seg = f["seg"]
            seg[:, :fade] *= np.linspace(0, 1, fade, dtype=np.float32)
            seg[:, -fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
            peak = float(np.max(np.abs(seg)))
            gain_db = 0.0
            if normalize_db is not None and peak > 0:
                gain_db = normalize_db - 20 * np.log10(peak)
                seg = seg * 10 ** (gain_db / 20)
            bpm = bars * bpb * 60.0 / f["seconds"]
            tag = f"{bpm:.0f}" if abs(bpm - round(bpm)) < 0.3 else f"{bpm:.1f}"
            fname = f"{name}_{slug}_{bars}bar_{tag}bpm_{key}_{n:02d}.wav"
            aio.save(os.path.join(loops_dir, fname), seg, sr)
            entries.append({"file": f"Loops/{fname}", "stem": stem_name, "kind": kinds[stem_name], "bars": bars,
                            "from_bar": f["bar"] + 1, "seconds": round(f["seconds"], 4), "bpm": round(bpm, 2), "key": tonal.key_name,
                            "gain_db": round(float(gain_db), 1)})
        if kinds[stem_name] == "drums":
            mono = a.mono
            for piece, clip in sorted(tr.extract_one_shots(mono, sr, tr.detect_drum_hits(mono, sr)).items()):
                peak = float(np.max(np.abs(clip)))
                if peak <= 0:
                    continue
                if normalize_db is not None:
                    clip = clip * 10 ** (normalize_db / 20) / peak
                fname = f"{name}_{slug}_{piece}.wav"
                aio.save(os.path.join(shots_dir, fname), clip, sr)
                shots.append({"file": f"One Shots/{fname}", "stem": stem_name, "piece": piece, "seconds": round(clip.size / sr, 3)})
        log(f"  {stem_name}: {len(found)} loops")
    manifest = {
        "name": name, "source": os.path.basename(src), "stems": stems.method, "stems_note": stems.quality_note,
        "tempo_bpm": rhythm.bpm, "tempo_steady": not beat_map.drifting, "time_signature": f"{bpb}/4", "key": tonal.key_name,
        "key_confidence": round(tonal.key_confidence, 2), "loops": entries, "one_shots": shots, "skipped_files": stems.skipped,
        "rights": "Samples cut from a recording belong to whoever owns that recording. Release or sell this pack only if the "
                  "source is your own music or you have cleared it.",
        "notes": ([] if not beat_map.drifting else ["The tempo drifts: every loop is cut on the real bar lines and is exactly its bars "
                                                    "long, but its tempo is its own (see bpm) and moves a little inside it."])
                 + (["Stems came from the rough built-in split: expect bleed between them. Install Demucs for clean stems."]
                    if stems.method.startswith("dsp") else []),
    }
    with open(os.path.join(out_dir, "pack.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1, cls=pipeline._Enc)
    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(_readme(manifest))
    return dict(manifest, folder=out_dir)


def _readme(m: dict) -> str:
    L = [f"# {m['name']}: חבילת סאמפלים", "",
         f"- מקור: {m['source']}. טמפו: {m['tempo_bpm']:g} BPM ({'יציב' if m['tempo_steady'] else 'לא יציב'}). סולם: {m['key']} "
         f"(ביטחון {m['key_confidence']:g} מתוך 1).",
         f"- {len(m['loops'])} לופים ו-{len(m['one_shots'])} one-shots. כל לופ נחתך על קווי התיבה האמיתיים של ההקלטה, ואורכו בדיוק מספר התיבות שבשם.",
         "- **זכויות:** סאמפלים שנחתכו מהקלטה שייכים לבעלי ההקלטה. מותר לשחרר או למכור את החבילה רק אם המקור הוא מוזיקה שלך, או שקיבלת אישור.", ""]
    if m["notes"]:
        L += ["## הערות", ""] + [f"- {n}" for n in m["notes"]] + [""]
    L += ["## לופים", "", "| קובץ | סטם | תיבות | מתיבה | BPM |", "|---|---|---|---|---|"]
    L += [f"| {e['file']} | {e['stem']} | {e['bars']} | {e['from_bar']} | {e['bpm']:g} |" for e in m["loops"]]
    if m["one_shots"]:
        L += ["", "## One-shots", "", "| קובץ | סטם | כלי |", "|---|---|---|"] + [f"| {e['file']} | {e['stem']} | {e['piece']} |" for e in m["one_shots"]]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="track2ableton-samplepack", description="Loops cut on the song's real bar lines, and drum "
                                 "one-shots, from an audio file or a folder of stems.")
    ap.add_argument("source")
    ap.add_argument("-o", "--out")
    ap.add_argument("--name")
    ap.add_argument("--bars", type=int, default=4)
    ap.add_argument("--max-loops", type=int, default=6, help="per stem")
    ap.add_argument("--separation", choices=["auto", "demucs", "dsp"], default="auto")
    ap.add_argument("--no-normalize", action="store_true", help="keep the level of the source instead of peaking at -1 dBFS")
    args = ap.parse_args(argv)
    if not os.path.exists(args.source):
        print(f"error: not found: {args.source}", file=sys.stderr)
        return 2
    try:
        m = build(args.source, args.out, args.name, args.bars, args.max_loops, args.separation,
                  normalize_db=None if args.no_normalize else -1.0)
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"\n  {len(m['loops'])} loops, {len(m['one_shots'])} one-shots, {m['tempo_bpm']:g} BPM, {m['key']}\n  {m['folder']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
