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

הבדיקות האוטומטיות של הניתוח (`pytest`) מריצות כל מעריך על אות שהתשובה עליו ידועה:
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

### שליטה ב-Live תוך כדי עבודה: מבקשים תוצאה, והכלי מתרגם אותה לפעולות ב-Ableton

**לפני:** קליקים בתפריטים, ניתוב, קליפים, מכשירים והגדרת הסשן, הכל ידנית.
**אחרי:** כותבים ל-Claude מה רוצים, למשל "תוסיף לבס קומפרסור עם sidechain מהקיק ותוריד אותו ב-3dB", והוא מבצע את זה ב-Live הפתוח.
**מתאים ל:** מפיקים שרוצים להישאר בזרימה היצירתית ולא לעצור כדי להגדיר כלים.

**איך זה בנוי:**

```
Claude (Desktop / Code)  --MCP-->  track2ableton-mcp  --TCP 127.0.0.1:9877-->  T2A_Bridge (Remote Script בתוך Live)  -->  Live Object Model
```

**מה אפשר לשלוט בו (39 כלים):**

| תחום | יכולות |
|---|---|
| Transport | play / stop / continue, טמפו, playhead, לופ, מטרונום, הקלטה, משקל, סולם (root/scale), undo/redo, Locators |
| Tracks ו-Mixer | יצירה, מחיקה ושכפול של ערוצי MIDI, Audio ו-Return. שם, צבע, mute, solo, arm. ווליום ב-dB, פאן, sends ב-dB |
| Routing | הצגה ושינוי של input/output type ו-channel ושל monitoring, למשל Resampling. **Sidechain של Compressor** (Live 12.4 ומעלה) |
| Clips ו-MIDI | יצירת קליפ MIDI או אודיו, Session או Arrangement. כתיבה, קריאה ומחיקה של תווים, quantize. fire, stop, שכפול, העברה ל-Arrangement. לופ, מרקרים, gain, pitch, warp |
| Scenes | יצירה, מחיקה, שכפול, fire, capture, שם, טמפו וצבע |
| Devices | הוספת מכשיר לפי שם (Live 12.3 ומעלה, אחרת דרך ה-Browser), כל הפרמטרים, כולל בתוך Racks. **קביעת ערך ביחידות שמוצגות ב-Live** (dB, Hz, ms). on, off, delete |
| Browser | דפדוף בקטגוריות, חיפוש, וטעינת מכשיר, פריסט, סמפל או פלאגין לערוץ |
| Samples | נתיבי הקבצים שמאחורי קליפי אודיו ו-Simpler, ומטרים |
| Mix ו-Master | צורת גל ו-**ספקטרוגרמה** (תמונות), LUFS, True Peak, LRA, crest. הכלי מזהה התנגשויות תדרים (masking) בין ערוצים ובעיות פאזה ו-DC, בודק את המאסטר מול יעד עוצמה, ו**משווה לטראק רפרנס** כדי להציע מהלכי EQ Eight |
| Rebuild | `rebuild_in_live` לוקח את תיקיית הניתוח של `track2ableton`, ובונה אותה ב-Set הפתוח: טמפו, ערוצים, כלים, אפקטים, תווים וסטמים |

**התקנה:**

```bash
pip install -e ".[live]"                  # שרת ה-MCP
python tools/install_bridge.py            # מעתיק את T2A_Bridge ל-User Library/Remote Scripts
```

1. מפעילים את Live מחדש.
2. ב-*Settings → Link, Tempo & MIDI → Control Surface* בוחרים `T2A_Bridge`. ב-Input וב-Output משאירים None.
3. מחברים את Claude.

Claude Code:
```bash
claude mcp add ableton -- track2ableton-mcp
```

Claude Desktop, בקובץ `claude_desktop_config.json`:
```json
{ "mcpServers": { "ableton": { "command": "track2ableton-mcp" } } }
```

אם `track2ableton-mcp` לא נמצא ב-PATH, צריך לכתוב בקובץ את הנתיב המלא שלו.

**דוגמאות לבקשות:**
- "תבנה לי ביט האוס ב-124: קיק על כל רבע, הייהאט על האוף-ביט, ובס בלה מינור."
- "תעשה ל-Pad sidechain מהקיק, release בערך 150ms."
- "תנתח את הסטמים ב-Set ותגיד לי איפה הבס והקיק מתנגשים, ואז תתקן עם EQ."
- "הנה הבאונס של המאסטר ושל רפרנס, תביא אותי ל-14- LUFS ו-1- dBTP ותתאים את הטונאליות."

**מה נבדק ומה לא:**
- **נבדק:**
  - הלוגיקה של ה-Bridge מול מודל מדומה של Live, דרך socket אמיתי ודרך כלי ה-MCP.
  - שרת ה-MCP מעל stdio אמיתי: רשימת הכלים, תמונת ספקטרוגרמה, והודעת שגיאה ברורה כש-Live לא מחובר.
  - ניתוח המיקס והמאסטר על אותות ידועים.
  - בסך הכל 46 בדיקות.
- **אומת מול מקורות:** כל שם של פונקציה ב-API של Live נבדק מול dump של ה-API של Live 12.4.0 ומול הסקריפטים של Ableton עצמה. הפירוט ב-[docs/LIVE-API-VERIFIED.md](docs/LIVE-API-VERIFIED.md). פונקציות שקיימות רק בגרסאות מסוימות של Live 12 נבדקות לפני השימוש ומחזירות שגיאה ברורה.
- **לא נבדק:** ריצה בתוך Live אמיתי. אין Live בסביבת הפיתוח. בהפעלה הראשונה כדאי לבדוק עם `live_session`. אם משהו לא עובד, הלוג של Live (`Log.txt`) יכיל שורות שמתחילות ב-`T2A`.
- **אבטחה:** ה-Bridge מאזין רק ל-127.0.0.1, בלי אימות. כל תהליך במחשב יכול לשלוט ב-Live בזמן שהוא פועל.

### תיקון טראק מוכן: טמפו עגול, תווים מסודרים, מהלך אקורדים אחד

**לפני:** טראק שיוצא מכלי AI (או מכל מקור אחר) יושב על טמפו לא עגול שלפעמים זז, והתמלול שלו ל-MIDI מלא במכות חסרות, תווי רפאים ושגיאות אוקטבה. ב-Ableton שום דבר לא יושב על הגריד.
**אחרי:** פקודה אחת מודדת את הפעמות האמיתיות, מיישרת את הסטמים לטמפו עגול עם סמני Warp, מתקנת את ה-MIDI לפי החזרות של השיר עצמו, ומפיקה דוח שסופר כל שינוי.

```bash
python -m track2ableton.fix "C:\Users\me\Downloads\My Song stems"
```

המקור יכול להיות קובץ אחד או תיקיית סטמים (למשל ייצוא של סונו). מתקבלים `MIDI/` מתוקן, `MIDI_raw/` להשוואה, קובץ `.als` עם הסטמים והערוצים, ו-`FIX_REPORT.md` בעברית. בבדיקה על טראק שקולקל בכוונה, בערך שליש מהשגיאות תוקנו, וטראק תקין נשאר כמו שהוא (99.98% מהתווים). **לא נבדק עדיין על טראק אמיתי מסונו.** פירוט מלא, כולל המגבלות: [docs/FIX.md](docs/FIX.md). הוראות הבנייה ב-Live ל-Claude Code: [docs/FIX_IN_LIVE.md](docs/FIX_IN_LIVE.md).

### ווקאל מ-MIDI: פרטיטורה ווקאלית, וסטמים ישר ל-Ableton

**לפני:** כדי להפיק שירה ממלודיה צריך לחלק ידנית את המילים להברות, להצמיד כל הברה לתו, ולגלות רק במנוע השירה שמשהו לא מסתדר.
**אחרי:** קליפ MIDI ומילים הופכים לפרטיטורה ווקאלית בדוקה: הברה לכל תו, הטעמה, פונמות, ורשימה של מה שקול לא יכול לשיר.

```bash
python -m track2ableton.vocal melody.mid lyrics.txt --lang es --bpm 130
```

מתקבלים `vocal.mid` (עם המילים), `vocal.musicxml`, `vocal.json` ודוח בעברית. מול Live פתוח יש שני כלים חדשים ל-Claude Code: `vocal_score` (מקליפ בפרויקט) ו-`split_stems` (קובץ אודיו לסטמים על ערוצים חדשים). **הכלי מכין את הפרטיטורה ולא שר:** את הקול מפיק מנוע שירה שמותקן אצלכם (ACE Studio, או OpenUtau עם קול DiffSinger). מה מחובר, מה לא, ומה ידוע על הרישיונות: [docs/VOCAL.md](docs/VOCAL.md). הוראות ל-Claude Code: [docs/VOCAL_IN_LIVE.md](docs/VOCAL_IN_LIVE.md).

### מנוע הלחנה: טראק שלם ב-MIDI מתוך מפרט קצר

**לפני:** כל תבנית תופים, ליין באס, אקורד והוק נכתבים ידנית, ואחר כך בודקים באוזן אם הם יושבים יחד.
**אחרי:** פקודה אחת כותבת את כל חלקי הטראק כקובצי MIDI, מסונכרנים ובאותו סולם, ומריצה עליהם 15 בדיקות (גריד, באס מול קיק, הרמוניה, מבנה, בילדים).

```bash
python -m track2ableton.compose --out "My Track" --bpm 130 --key "A minor"
```

מתקבלים 18 ערוצים (תופים, פרקשן, סאב, מיד-באס, פד, הוק וטריגרים לווקאל) במבנה של 200 תיבות, וגם גרסת רדיו של 97 תיבות (`--structure radio`) ולופ של 16 תיבות להאזנה לשלוש חלופות (`--structure loop16 --variants 3`). המנוע כותב תווים בלבד: הסאונדים, המיקס וההחלטה אם זה טוב נשארים אצלכם. פירוט מלא, כולל מה נבדק ומה לא: [docs/COMPOSER.md](docs/COMPOSER.md).

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
