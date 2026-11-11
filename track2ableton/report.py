"""Human-readable outputs: report.html (Hebrew, RTL, self-contained) and REBUILD.md."""
from __future__ import annotations

import html
import json
import os

CONF_HE = {"high": "גבוהה", "medium": "בינונית", "low": "נמוכה", "medium-high": "בינונית-גבוהה"}
SECTION_COLORS = ["#5b8def", "#e8833a", "#3fb68b", "#c95fd6", "#d6c443", "#e05a6b", "#4fc3d9", "#8f8f8f"]


def _e(x) -> str:
    return html.escape(str(x))


def _params(p: dict) -> str:
    rows = []
    for k, v in p.items():
        if isinstance(v, dict):
            v = ", ".join(f"{a}: {b}" for a, b in v.items())
        elif isinstance(v, list):
            v = "<br>".join(_e(json.dumps(i, ensure_ascii=False)) if isinstance(i, dict) else _e(i) for i in v)
            rows.append(f"<tr><td dir='ltr'>{_e(k)}</td><td dir='ltr'>{v}</td></tr>")
            continue
        rows.append(f"<tr><td dir='ltr'>{_e(k)}</td><td dir='ltr'>{_e(v)}</td></tr>")
    return "<table class='p'>" + "".join(rows) + "</table>"


def _device(d: dict) -> str:
    conf = d.get("confidence", "")
    return (f"<div class='dev'><div class='dh'><b dir='ltr'>{_e(d['name'])}</b>"
            f"<span class='c c-{_e(conf)}'>ביטחון: {CONF_HE.get(conf, conf)}</span></div>"
            f"<div class='why' dir='ltr'>{_e(d.get('why', ''))}</div>{_params(d.get('params', {}))}</div>")


def write_html(a, data: dict, path: str):
    t = data["tempo"]
    k = data["key"]
    m = data["master"]
    total = max(1e-6, data["duration_s"])
    sec_html = ""
    letters = sorted({s["letter"] for s in data["sections"]})
    for s in data["sections"]:
        w = (s["end"] - s["start"]) / total * 100
        col = SECTION_COLORS[letters.index(s["letter"]) % len(SECTION_COLORS)]
        sec_html += (f"<div class='sec' style='width:{w:.3f}%;background:{col}' title='{_e(s['role'])} {s['bars']} bars'>"
                     f"<span>{_e(s['role'])}<br>{s['letter']} · {s['bars']}</span></div>")
    chord_rows = "".join(f"<span class='ch' dir='ltr'>{_e(c['name'])}<small>{_e(c['roman'])}</small></span>" for c in data["chords"][:96])
    tracks = ""
    for tr in data["tracks"] + data["returns"]:
        meas = tr.get("measurements", {})
        info = []
        if "rms_dbfs" in meas:
            info.append(f"RMS {meas['rms_dbfs']} dBFS")
        if "dynamics" in meas:
            info.append(f"Crest {meas['dynamics']['crest_db']} dB")
        if "stereo" in meas:
            info.append(f"Side/Mid {meas['stereo']['side_to_mid_db']} dB")
        if "reverb" in meas and meas["reverb"]["rt60_s"]:
            info.append(f"RT60 ≈ {meas['reverb']['rt60_s']} s")
        if meas.get("pumping", {}).get("detected"):
            info.append(f"Sidechain {meas['pumping']['depth_db']} dB / {meas['pumping']['release_ms']:.0f} ms")
        if "transcription" in meas:
            tt = meas["transcription"]
            info.append(f"MIDI: {tt['notes']} notes ({_e(tt['method'])}, ביטחון {CONF_HE.get(tt['confidence'], tt['confidence'])})")
        pats = ""
        if tr.get("instrument") and tr["instrument"]["params"].get("patterns_16_steps"):
            pats = "<pre dir='ltr'>" + "\n".join(f"{p:11} |{s}|" for p, s in tr["instrument"]["params"]["patterns_16_steps"].items()) + "</pre>"
        devs = (_device(tr["instrument"]) if tr.get("instrument") else "") + "".join(_device(d) for d in tr["devices"])
        auto = "".join(f"<li dir='ltr'>{_e(x['device'])} › {_e(x['param'])}: {_e(x['points'])} — {_e(x['why'])}</li>" for x in tr.get("automation", []))
        sends = ", ".join(f"{n}: {v:.0f} dB" for n, v in tr.get("sends", {}).items())
        notes = "".join(f"<li>{_e(n)}</li>" for n in tr.get("notes", []))
        files = " · ".join(f"<code dir='ltr'>{_e(f)}</code>" for f in (tr.get("audio_file"), tr.get("midi_file")) if f)
        tracks += (f"<section class='trk'><h3><span dir='ltr'>{_e(tr['name'])}</span> <small>{_e(tr['role'])} · "
                   f"{'MIDI' if tr['kind'] == 'midi' else 'Audio'}</small></h3><div class='meta'>{' · '.join(info)}</div>"
                   f"<div class='meta'>{files}</div>{pats}{devs}"
                   + (f"<div class='meta'>Sends: <span dir='ltr'>{_e(sends)}</span></div>" if sends else "")
                   + (f"<h4>אוטומציה</h4><ul>{auto}</ul>" if auto else "")
                   + (f"<ul class='notes'>{notes}</ul>" if notes else "") + "</section>")
    master_devs = "".join(_device(d) for d in m["chain"])
    warns = "".join(f"<li dir='ltr'>{_e(w)}</li>" for w in data["warnings"])
    spec_pts = " ".join(f"{i * 18 + 10},{110 - max(-60, lv) * -1.6:.1f}" for i, lv in enumerate(m["spectrum"]["levels_db"]))
    spec_labels = "".join(f"<text x='{i * 18 + 10}' y='128' text-anchor='middle'>{int(c) if c < 1000 else f'{c / 1000:g}k'}</text>"
                          for i, c in enumerate(m["spectrum"]["centers"]) if i % 3 == 0)
    width = len(m["spectrum"]["levels_db"]) * 18 + 20
    doc = f"""<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Track Rebuild Report</title>
<style>
:root{{--bg:#f6f6f4;--fg:#1d1d1f;--mut:#6b6b70;--card:#fff;--line:#e3e3e0;--acc:#ff764d}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151517;--fg:#ececec;--mut:#9a9aa0;--card:#1f1f22;--line:#2f2f33;--acc:#ff8a66}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Arial,sans-serif}}
main{{max-width:1100px;margin:auto;padding:24px 16px}}h1{{margin:0 0 4px}}h2{{margin-top:36px;border-bottom:1px solid var(--line);padding-bottom:6px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}}.kpi b{{display:block;font-size:22px}}.kpi span{{color:var(--mut);font-size:13px}}
.timeline{{display:flex;direction:ltr;border-radius:8px;overflow:hidden;height:64px}}.sec{{color:#fff;font-size:11px;display:flex;align-items:center;justify-content:center;text-align:center;overflow:hidden;border-left:1px solid rgba(0,0,0,.25)}}
.chords{{direction:ltr;display:flex;flex-wrap:wrap;gap:6px}}.ch{{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:3px 8px;font-weight:600}}.ch small{{display:block;color:var(--mut);font-weight:400;font-size:11px}}
.trk{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:14px 0}}.trk h3{{margin:0 0 6px}}.trk small{{color:var(--mut);font-weight:400}}
.meta{{color:var(--mut);font-size:13px;margin:4px 0}}.dev{{border-top:1px dashed var(--line);padding:8px 0}}.dh{{display:flex;justify-content:space-between;gap:8px}}
.why{{color:var(--mut);font-size:13px;margin:2px 0 6px;text-align:left}}table.p{{border-collapse:collapse;font-size:13px;direction:ltr;width:100%}}table.p td{{border-bottom:1px solid var(--line);padding:3px 6px;vertical-align:top}}table.p td:first-child{{width:200px;color:var(--mut)}}
.c{{font-size:12px;border-radius:20px;padding:1px 9px;white-space:nowrap}}.c-high{{background:#d7f5e5;color:#11643b}}.c-medium,.c-medium-high{{background:#fdf0cf;color:#7a5600}}.c-low{{background:#fde0de;color:#8a1f17}}
pre{{background:var(--bg);border-radius:8px;padding:8px;overflow-x:auto}}code{{font-size:12px}}svg text{{font-size:9px;fill:var(--mut)}}.warn li{{color:var(--mut)}}
.scroll{{overflow-x:auto}}
</style></head><body><main>
<h1>פירוק הטראק ובנייה מחדש ב-Ableton Live 12</h1>
<div class="meta" dir="ltr">{_e(data['source'])} · {data['duration_s']:.1f}s · {data['sample_rate']} Hz · {_e(data['tool'])}</div>
<div class="kpis">
<div class="kpi"><span>טמפו</span><b dir="ltr">{t['bpm']:g} BPM</b><span dir="ltr">{t['time_signature']} · ביטחון {t['confidence']}</span></div>
<div class="kpi"><span>סולם</span><b dir="ltr">{_e(k['name'])}</b><span dir="ltr">Camelot {k['camelot']} · A4={k['a4_hz']} Hz</span></div>
<div class="kpi"><span>עוצמה</span><b dir="ltr">{m['integrated_lufs']} LUFS</b><span dir="ltr">True peak {m['true_peak_dbtp']} dBTP · LRA {m['lra_lu']} LU</span></div>
<div class="kpi"><span>סווינג (MPC)</span><b dir="ltr">{t['swing_percent_mpc']}%</b><span>50% = ישר</span></div>
<div class="kpi"><span>הפרדת ערוצים</span><b dir="ltr" style="font-size:15px">{_e(data['separation']['method'])}</b><span>{len(data['tracks'])} סטמים</span></div>
</div>
<h2>מבנה השיר</h2><div class="timeline">{sec_html}</div>
<p class="meta">אותיות זהות = חלקים שנשמעים דומים. הגבולות מיושרים לפראזות של 4 תיבות. ב-Set הם מופיעים כ-Locators.</p>
<h2>הרמוניה</h2><div class="chords">{chord_rows}</div>
<h2>איזון ספקטרלי (מאסטר)</h2><div class="scroll"><svg width="{width}" height="135" viewBox="0 0 {width} 135"><polyline fill="none" stroke="var(--acc)" stroke-width="2" points="{spec_pts}"/>{spec_labels}</svg></div>
<p class="meta">רמה יחסית בפסי שליש-אוקטבה (dB מתחת לפס החזק ביותר). שיפוע: {m['spectrum']['tilt_db_per_oct']} dB/oct.</p>
<h2>ערוצים: כלי, שרשרת אפקטים ופרמטרים</h2>{tracks}
<h2>Master</h2><section class="trk">{master_devs}</section>
<h2>איך לפתוח ב-Live</h2>
<ol>
<li>פתחו את קובץ ה-<code>.als</code> שבתיקייה. אם Live לא מצליח לפתוח אותו, גררו את הקבצים מ-<code>Stems/</code> ו-<code>MIDI/</code> ל-Set חדש. ב-<code>tempo</code> השתמשו ב-{t['bpm']:g} BPM.</li>
<li>הסטמים המקוריים נמצאים בערוצי <b>REF</b>. הם מושתקים, חוץ מהשירה. כדאי להשוות A/B מול הבנייה מחדש.</li>
<li>ערוצי ה-MIDI כבר מכילים כלים מובנים ואפקטים עם הערכים שנמדדו. הנימוק לכל מכשיר מופיע ב-Info View של הערוץ (Annotation).</li>
<li>Sidechain: ב-Compressor של הערוץ בחרו <i>Audio From → Kick</i>. הניתוב לא מוגדר מראש בקובץ.</li>
<li>תופים: לכל רכיב בערכה יש ערוץ Sampler משלו, עם הדגימה שנחתכה מהסטם. יש גם ערוץ "Drums (full MIDI)" שמתאים ל-Drum Rack.</li>
</ol>
<h2>אזהרות ומגבלות</h2><ul class="warn">{warns}<li>{_e(data['separation']['note'])}</li>
<li>הפרמטרים הם הערכה מתוך האודיו, לא קריאה של הפרויקט המקורי. אפשר לשחזר את הסאונד ואת המבנה, אבל לא את הפריסטים המדויקים או התוספים שבהם השתמש המפיק.</li></ul>
</main></body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)


def write_markdown(a, data: dict, path: str):
    t, k, m = data["tempo"], data["key"], data["master"]
    L = [f"# Rebuild recipe: {data['source']}", "",
         f"- **Tempo:** {t['bpm']:g} BPM ({t['time_signature']}), measured {t['bpm_measured']}, confidence {t['confidence']}",
         f"- **Key:** {k['name']} (Camelot {k['camelot']}), tuning {k['tuning_cents']:+.0f} cents (A4 = {k['a4_hz']} Hz)",
         f"- **Loudness:** {m['integrated_lufs']} LUFS integrated, {m['true_peak_dbtp']} dBTP true peak, LRA {m['lra_lu']} LU",
         f"- **Swing:** {t['swing_percent_mpc']}% (MPC scale, 50 = straight)",
         f"- **Stems:** {data['separation']['method']}", "", "## Structure", "",
         "| Bars | Section | Letter | Start (s) |", "|---|---|---|---|"]
    for s in data["sections"]:
        L.append(f"| {s['start_bar'] + 1}-{s['end_bar']} | {s['role']} | {s['letter']} | {s['start']:.1f} |")
    L += ["", "## Chords", "", " ".join(f"`{c['name']}`" for c in data["chords"][:64]), ""]
    for tr in data["tracks"] + data["returns"]:
        L += [f"## {tr['name']} ({tr['role']}, {tr['kind']})", ""]
        if tr.get("instrument"):
            i = tr["instrument"]
            L.append(f"**Instrument: {i['name']}** ({i['confidence']}). {i['why']}")
            L.append("")
            L.append("```json\n" + json.dumps(i["params"], indent=1, ensure_ascii=False)[:2500] + "\n```")
        for d in tr["devices"]:
            L.append(f"- **{d['name']}** ({d['confidence']}): {d['why']}  ")
            L.append(f"  `{json.dumps(d['params'], ensure_ascii=False)}`")
        for au in tr.get("automation", []):
            L.append(f"- Automation {au['device']} › {au['param']}: {au['points']} ({au['why']})")
        for n in tr.get("notes", []):
            L.append(f"- Note: {n}")
        L.append("")
    L += ["## Master", ""] + [f"- **{d['name']}**: {d['why']} `{json.dumps(d['params'], ensure_ascii=False)}`" for d in m["chain"]]
    L += ["", "## Warnings", ""] + [f"- {w}" for w in data["warnings"]] + [f"- {data['separation']['note']}"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
