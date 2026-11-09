# Music-AI

## track2ableton: פירוק טראק ובנייה מחדש ב-Ableton Live 12

מעלים טראק מוקלט וגמור (WAV/FLAC/MP3/AIFF...). הכלי מפרק אותו ומחזיר תיקיית פרויקט שאפשר לפתוח ב-Live 12, כאילו הטראק נבנה שם מאפס:

| מה מקבלים | איך זה נמדד |
|---|---|
| **טמפו, משקל, דאונביט, סווינג** | spectral flux בכמה פסים, התאמת גריד, הכרעת אוקטבה לפי הקיק והסנר |
| **סולם, כיוון (A4), אקורדים לפי חצאי תיבות** | כרומה על החלק ההרמוני (HPSS), פרופילי Krumhansl-Kessler, תבניות אקורדים |
| **מבנה: Intro / Build / Drop / Breakdown...** | מטריצת דמיון בין תיבות, novelty ויישור לפראזות של 4 תיבות. נשמר כ-Locators |
| **סטמים** | Demucs (htdemucs_6s: תופים, בס, שירה, גיטרה, פסנתר, אחר) אם הוא מותקן. אחרת מפריד DSP פנימי גס |
| **MIDI לכל סטם** | תופים לפי צורת ההתקפה הספקטרלית (kick/snare/clap/hat), בס ושירה עם YIN, פוליפוני עם salience או basic-pitch |
| **דגימות תופים** | כל רכיב בערכה נחתך מהמכה הנקייה ביותר בסטם, ונטען ל-Sampler בערוץ משלו |
| **כלי לכל ערוץ** | צורת הגל מתוך סדרת ההרמוניות (sine/saw/square), חיתוך הפילטר, ADSR מתוך המעטפת. משם בחירה בין Drift, Operator ו-Wavetable |
| **שרשרת אפקטים עם ערכים** | EQ Eight מהספקטרום, Compressor מ-crest factor, **Sidechain** מקיפול המעטפת על הקיק (עומק ו-release), Utility מ-Mid/Side, Reverb מ-RT60 (T20), Echo מנקודה מנוקדת או טריולית, **אוטומציית Auto Filter** מתזוזת קצוות הספקטרום |
| **מאסטר** | LUFS משולב (ITU-R BS.1770), True Peak (פי 4 oversampling), LRA, ומשם Glue ו-Limiter |
| **קובץ `.als`** | ערוצי REF עם הסטמים, ערוצי MIDI עם כלים ואפקטים מכוונים, Returns, Locators וטמפו |
| **דו"ח** | `report.html` בעברית עם רמת ביטחון ונימוק לכל החלטה, וגם `REBUILD.md` ו-`recipe.json` |

### התקנה והרצה

```bash
pip install -e .                 # numpy, scipy, soundfile בלבד
pip install -e ".[demucs]"       # מומלץ מאוד: הפרדת ערוצים ברמה מקצועית (מוריד מודל בהרצה הראשונה)
pip install -e ".[transcription]"  # אופציונלי: basic-pitch לתמלול פוליפוני

track2ableton "My Song.wav"                    # יוצר "My Song Rebuild Project/" ליד הקובץ
track2ableton song.mp3 -o out --separation dsp # בלי Demucs
track2ableton song.wav --template "Empty.als"  # מומלץ: Set ריק שנשמר ב-Live שלכם (ראו למטה)
```

צריך גם `ffmpeg` לקבצים ש-libsndfile לא קורא, למשל m4a.

### תוכן התיקייה שנוצרת

```
<name> Rebuild Project/
  <name> Rebuild.als     # פותחים ב-Live 12
  report.html            # הדו"ח המלא בעברית
  REBUILD.md, recipe.json
  Stems/*.wav            # הסטמים המופרדים
  MIDI/*.mid             # MIDI לכל ערוץ, וגם *_chords.mid
  Samples/Drums/*.wav    # one-shots שנחתכו מהטראק
```

### מה בדיוק יש ב-Set

- **REF <stem>**: ערוץ אודיו עם הסטם המקורי, מיושר לגריד. הערוצים האלה מושתקים, חוץ מהשירה, כדי שאפשר יהיה להשוות A/B.
- **Kick / Snare / Closed Hat ...**: ערוץ MIDI עם Sampler, הדגימה מהטראק, והתווים שתומללו. כל התווים על C3.
- **Drums (full MIDI, GM map)**: כל התופים בערוץ אחד, למי שמעדיף Drum Rack. הערוץ מושתק.
- **Bass / Synths / Keys**: ערוץ MIDI עם כלי מובנה, EQ, Compressor, Utility ו-Auto Filter עם אוטומציה. הערכים נמדדו מהטראק. הנימוק לכל מכשיר מופיע ב-Info View של הערוץ (Annotation).
- **A Reverb / B Echo**: Returns עם זמן הדעיכה שנמדד.
- **Master**: EQ Eight, Glue Compressor ו-Limiter עם התקרה שנמדדה.

הניתוב ל-sidechain לא מוגדר בקובץ. בוחרים ידנית *Audio From → Kick* ב-Compressor שמסומן בדו"ח.

### אמינות: מה נבדק ומה לא

הבדיקות האוטומטיות (`pytest`, 27 בדיקות) מריצות כל מעריך על אות שהתשובה עליו ידועה:
- טמפו 92–174 BPM בדיוק של ±0.3 ודאונביט בטווח של 30ms.
- זיהוי A minor ואקורדי Am–F–C–G.
- RT60 של 1.5 שניות, שנמדד כ-1.51.
- מקדמי K-weighting שתואמים לטבלת BS.1770 ב-48kHz, וסינוס 997Hz שנמדד ב-−3.01 LUFS.
- זיהוי צורת גל (sine/saw/square), sidechain, Echo מנוקד וסוויפ פילטר.
- תמלול תופים מסטם נקי: 96/96 קיקים, 96/96 הייהאטים, 16/16 סנרים במקום הנכון.
- המבנה של קובץ ה-`.als`: מזהים ייחודיים, הפניות תקינות וקבצים קיימים.

**מה לא נבדק:**
- **לא פתחנו את קובץ ה-`.als` ב-Live עצמו.** הפורמט לא מתועד, ולכן הכלי משכפל מבנים מתוך קבצים אמיתיים של Live 12.4.5 ולא ממציא אותם (פרטים ב-`track2ableton/ableton/templates/NOTICE.md`). אם הפתיחה נכשלת, הריצו עם `--template` על Set ריק שנשמר ב-Live שלכם (עם ערוץ MIDI, ערוץ אודיו ו-Return), או גררו את `Stems/` ו-`MIDI/` ל-Set חדש. כל שאר התוצרים לא תלויים בקובץ ה-`.als`.
- לא נבדק על מוזיקה מסחרית אמיתית בסביבת הפיתוח. כל המספרים למעלה הם מאותות סינתטיים.
- **המפריד הפנימי (DSP) גס.** בלי Demucs מתקבלים קיקים כפולים מההתקפות של הבס, הבס מאבד הרמוניות מעל 300Hz, ו-"Centre Lead" יכול להיות שירה או סינת. עם Demucs הסטמים נקיים בהרבה. הנתיב של Demucs לא הורץ כאן, כי שרת המשקולות היה חסום ברשת.
- הפרמטרים הם **שחזור מתוך הסאונד**, לא קריאה של הפרויקט המקורי. אי אפשר לדעת איזה פריסט או פלאגין צד-שלישי שימש את המפיק. אפשר להגיע לטון, למבנה, לגרוב ולמיקס דומים.

מסמך התכנון ושאלות-התשובות של "צוות המחקר": [docs/RESEARCH-QA.md](docs/RESEARCH-QA.md).

### פיתוח

```bash
pip install -e ".[test]" && pytest -q
python tools/build_templates.py <dir with the donor .als files>   # מחדש את תבניות ה-.als
```

---


## Claude Code: caveman plugin (repository tooling)

This repo is configured to use the [caveman](https://github.com/JuliusBrussee/caveman)
Claude Code plugin — an ultra-compressed communication mode that cuts ~75% of
output tokens while keeping full technical accuracy ("why use many token when
few token do trick").

The setup lives in [`.claude/settings.json`](.claude/settings.json), which
registers the marketplace and enables the plugin at the **project scope** so it
applies to everyone who works in this repo:

```json
{
  "extraKnownMarketplaces": {
    "caveman": {
      "source": { "source": "github", "repo": "JuliusBrussee/caveman" }
    }
  },
  "enabledPlugins": {
    "caveman@caveman": true
  }
}
```

When you open this repo in Claude Code and trust the folder, you'll be prompted
to install the `caveman` marketplace and plugin. After install, run
`/reload-plugins` (or restart) and trigger it with `/caveman`, or just say
"caveman mode".

### Manual install (equivalent)

```bash
claude plugin marketplace add JuliusBrussee/caveman
claude plugin install caveman@caveman
```

Or the upstream one-liner:

```bash
curl -fsSL https://raw.githubusercontent.com/JuliusBrussee/caveman/main/install.sh | bash
```
