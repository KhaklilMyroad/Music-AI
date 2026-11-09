"""Per-stem effects forensics: what EQ, filters, compression, reverb, delay, sidechain, stereo and
saturation each stem shows, as a Hebrew HTML report with a spectrogram per stem.

Everything is estimated from the sound itself (it cannot read the original project), so every
number is an estimate with a confidence note.

usage:
  py tools/stem_forensics.py <stems_folder> [-o report.html] [--bpm 145.68]
                             [--anchor-sec 25.122 --anchor-beat 60] [--skip drums vocals]
"""
from __future__ import annotations

import argparse
import base64
import html
import os
import sys

import numpy as np

from track2ableton import mixanalysis as mx
from track2ableton import mixmaster
from track2ableton import sounddesign as sd
from track2ableton import transcribe as tr
from track2ableton.audio import load

HE_KIND = {"highpass": "חיתוך נמוכים (High-pass)", "lowpass": "חיתוך גבוהים (Low-pass)", "bell": "Bell",
           "lowshelf": "Low shelf", "highshelf": "High shelf"}
HE_SWEEP = {"lowpass opening": "פילטר Low-pass נפתח", "lowpass closing": "פילטר Low-pass נסגר",
            "highpass rising": "פילטר High-pass עולה", "highpass falling": "פילטר High-pass יורד"}
HE_COMP = {"heavy (limited / OTT-style)": "כבדה (לימיטר / OTT)", "strong": "חזקה", "moderate": "בינונית",
           "light / none": "קלה / אין"}
HE_VERB = {"dry": "יבש", "short room": "חדר קצר", "hall / plate": "Hall / Plate", "long ambient": "אמביינט ארוך"}


def bar_of(t: float, a: argparse.Namespace) -> float:
    beat = a.anchor_beat + (t - a.anchor_sec) * a.bpm / 60.0
    return 1 + beat / 4.0


def active_ranges(mono: np.ndarray, sr: int, a: argparse.Namespace, dur: float) -> list[tuple[int, int]]:
    """Bars where the stem plays (RMS within 30 dB of its loudest bar)."""
    bar_s = 240.0 / a.bpm
    first = a.anchor_sec - (a.anchor_beat / 4.0) * bar_s
    edges = np.arange(first, dur + bar_s, bar_s)
    rms = []
    for t0, t1 in zip(edges[:-1], edges[1:]):
        seg = mono[max(0, int(t0 * sr)): max(0, int(t1 * sr))]
        rms.append(20 * np.log10(np.sqrt(np.mean(seg.astype(np.float64) ** 2)) + 1e-9) if seg.size else -200)
    rms = np.array(rms)
    on = rms > rms.max() - 30
    out, start = [], None
    for i, v in enumerate(on):
        if v and start is None:
            start = i
        if (not v or i == len(on) - 1) and start is not None:
            end = i if v else i - 1
            if end - start >= 0:
                out.append((start + 1, end + 1))
            start = None
    return out


def analyse(path: str, kick_times: np.ndarray, a: argparse.Namespace) -> dict:
    au = load(path)
    m, sr = au.mono, au.sr
    name = os.path.splitext(os.path.basename(path))[0]
    spec = mx.spectrum_profile(m, sr)
    dyn = mx.dynamics(m, sr)
    ster = mx.stereo(au)
    rv = mx.reverb(m, sr)
    ec = mx.echo(m, sr, a.bpm)
    dist = mx.distortion_amount(m, sr)
    pump = None
    if name.lower() != "kick" and kick_times.size >= 8:
        beat_times = kick_times
        pump = max((mx.pumping(m, sr, beat_times, kick_times, hp) for hp in (None, 120.0)), key=lambda p: p.depth_db)
    bar_s = 240.0 / a.bpm
    first = a.anchor_sec - (a.anchor_beat / 4.0) * bar_s
    bar_times = np.arange(max(first, 0.0), au.duration, bar_s)
    sweeps, _ = mx.filter_sweeps(m, sr, bar_times, lambda t: a.anchor_beat + (np.asarray(t) - a.anchor_sec) * a.bpm / 60.0)
    png, _axis = mixmaster.spectrogram_png(au, width=1000, height=220)
    return {"name": name, "lufs": mx.integrated_lufs(au), "tp": mx.true_peak_db(au), "spec": spec, "dyn": dyn,
            "ster": ster, "rv": rv, "ec": ec, "dist": dist, "pump": pump, "sweeps": sweeps,
            "active": active_ranges(m, sr, a, au.duration), "png": png,
            "chain": [d for d in (sd._eq_device(spec, "EQ"), sd._comp_device(dyn), sd._utility(ster)) if d],
            "send": sd._reverb_send(rv)}


def row(k: str, v: str) -> str:
    return f"<tr><th>{html.escape(k)}</th><td>{v}</td></tr>"


def section(r: dict) -> str:
    s, d, st, rv, ec, p = r["spec"], r["dyn"], r["ster"], r["rv"], r["ec"], r["pump"]
    eq = "".join(f"<li>{HE_KIND.get(b.kind, b.kind)} ב-{b.freq:.0f} הרץ"
                 + (f", {b.gain_db:+.1f} dB, Q {b.q:.2f}" if b.kind not in ("highpass", "lowpass") else f", {b.slope_db_oct} dB/oct")
                 + "</li>" for b in s.eq_moves) or "<li>לא זוהו מהלכי EQ בולטים</li>"
    sw = "".join(f"<li>{HE_SWEEP.get(x.kind, x.kind)}: תיבות {1 + x.start_beat / 4:.0f}–{1 + x.end_beat / 4:.0f}, "
                 f"{x.from_hz:.0f} → {x.to_hz:.0f} הרץ</li>" for x in r["sweeps"]) or "<li>לא זוהו סוויפים של פילטר</li>"
    act = ", ".join(f"{b0}–{b1}" if b1 > b0 else f"{b0}" for b0, b1 in r["active"]) or "—"
    if p is None:
        pump = "לא נבדק (זה הקיק עצמו, או שאין מספיק מכות קיק)"
    elif p.detected:
        pump = f"<b>כן</b>: עומק {p.depth_db} dB, חזרה תוך כ-{p.release_ms:.0f}ms"
    elif p.depth_db > 30:
        pump = "לא רלוונטי: הכלי לא מנגן ברצף, אז אין מה להשוות בין המכות"
    else:
        pump = f"לא זוהה (עומק נמדד {p.depth_db} dB)"
    echo = (f"<b>כן</b>: {ec.division}, feedback בערך {ec.feedback:.0%}" if ec.detected
            else "לא זוהה דיליי מנוקד/טריולי (דיליי ישר של 1/8 או 1/4 לא ניתן להבחנה בשיטה הזו)")
    verb = "לא נמדד" if rv.rt60_s <= 0 else f"RT60 בערך {rv.rt60_s:.2f} שניות, pre-delay {rv.predelay_ms:.0f}ms ({HE_VERB.get(rv.wet_hint, rv.wet_hint)})"
    width = "מונו" if st.side_to_mid_db < -30 else f"{st.width_percent:.0f}% (Side/Mid {st.side_to_mid_db} dB, קורלציה {st.correlation})"
    mono_lo = f"מונו מתחת ל-{st.low_mono_below_hz:.0f} הרץ" if st.low_mono_below_hz else "לא זוהה"
    pan = "מרכז" if abs(st.pan) < 0.15 else ("ימינה" if st.pan > 0 else "שמאלה") + f" ({st.pan:+.2f})"
    sat = "גבוהה" if r["dist"] > 0.5 else "בינונית" if r["dist"] > 0.25 else "נמוכה"
    chain = "".join(f"<li><b>{html.escape(c.name)}</b>: {html.escape(str(c.params))}</li>" for c in r["chain"])
    send = "" if r["send"] == float("-inf") else f"<li><b>Send ל-Reverb</b>: {r['send']:.0f} dB</li>"
    img = base64.b64encode(r["png"]).decode()
    return f"""
<section><h2>{html.escape(r['name'])}</h2>
<img src="data:image/png;base64,{img}" alt="spectrogram {html.escape(r['name'])}">
<p class="cap">ספקטרוגרמה: ציר הזמן משמאל לימין, נמוכים למטה. קווים אפורים ב-100 הרץ, 1k ו-10k.</p>
<table>
{row('איפה מנגן (תיבות)', act)}
{row('עוצמה', f"{r['lufs']:.1f} LUFS, true peak {r['tp']:.1f} dBTP")}
{row('תחום תדרים', f"{s.lowest_hz:.0f} – {s.highest_hz:.0f} הרץ, מרכז כובד {s.centroid_hz:.0f} הרץ, שיפוע {s.tilt_db_per_oct:+.1f} dB/oct")}
{row('EQ / פילטרים קבועים', f'<ul>{eq}</ul>')}
{row('אוטומציית פילטר', f'<ul>{sw}</ul>')}
{row('קומפרסיה', f"{HE_COMP.get(d.compression_guess, d.compression_guess)} (crest {d.crest_db} dB, peak {d.peak_db} / RMS {d.rms_db} dBFS)")}
{row('Sidechain מהקיק', pump)}
{row('ריוורב', verb)}
{row('דיליי', echo)}
{row('סטריאו', f"רוחב {width}, באס {mono_lo}, פאן {pan}")}
{row('סטורציה / דיסטורשן', f"{sat} ({r['dist']:.2f} בסולם 0–1)")}
</table>
<details><summary>שרשרת מוצעת ב-Ableton לשחזור הסאונד</summary><ul>{chain}{send}</ul></details>
</section>"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("-o", "--out")
    ap.add_argument("--bpm", type=float, default=145.68)
    ap.add_argument("--anchor-sec", type=float, default=25.122, help="time (s) of a known beat in the stems")
    ap.add_argument("--anchor-beat", type=float, default=60.0, help="arrangement beat of that time")
    ap.add_argument("--skip", nargs="*", default=["drums", "vocals"], help="stem names to skip (sums of other stems)")
    a = ap.parse_args(argv)
    files = sorted(f for f in os.listdir(a.folder) if f.lower().endswith((".wav", ".flac", ".aif", ".aiff"))
                   and os.path.splitext(f)[0].lower() not in {s.lower() for s in a.skip})
    if not files:
        print("no audio files found", file=sys.stderr)
        return 1
    kick_times = np.array([])
    kp = next((os.path.join(a.folder, f) for f in files if os.path.splitext(f)[0].lower() == "kick"), None)
    if kp:
        k = load(kp)
        kick_times = np.array(sorted(h.time for h in tr.detect_drum_hits(k.mono, k.sr) if h.piece == "kick"))
        print(f"kick: {kick_times.size} hits")
    results = []
    for f in files:
        print("analysing", f, flush=True)
        results.append(analyse(os.path.join(a.folder, f), kick_times, a))
    out = a.out or os.path.join(a.folder, "stem_forensics.html")
    body = "".join(section(r) for r in results)
    page = f"""<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>פירוק סטמים</title>
<style>
:root{{--bg:#fff;--fg:#1d1d1f;--mut:#666;--line:#ddd;--card:#f6f6f7}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151517;--fg:#eee;--mut:#aaa;--line:#333;--card:#1f1f22}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:1040px;margin:auto;padding:16px}}
section{{background:var(--card);border-radius:10px;padding:12px 16px;margin:18px 0}}
img{{width:100%;height:auto;border-radius:6px;direction:ltr}} .cap,.note{{color:var(--mut);font-size:13px}}
table{{width:100%;border-collapse:collapse}} th,td{{text-align:right;vertical-align:top;padding:6px;border-top:1px solid var(--line)}}
th{{width:170px;font-weight:600}} ul{{margin:0;padding-inline-start:18px}}
</style></head><body>
<h1>פירוק סטמים: אפקטים ועיבוד</h1>
<p class="note">כל הערכים <b>מוערכים מתוך הסאונד</b>, לא נקראו מהפרויקט המקורי. סטמים שעברו הפרדה כוללים שאריות של כלים אחרים,
וזה משפיע על המדידות (למשל ריוורב ודיליי). מספרי התיבות לפי {a.bpm} BPM, כשהזמן {a.anchor_sec} שניות הוא beat {a.anchor_beat:g}.
דיליי ישר (1/8, 1/4) לא ניתן להבחנה מהקצב של הכלי עצמו, ולכן מדווח רק דיליי מנוקד או טריולי.</p>
{body}</body></html>"""
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print("saved:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
