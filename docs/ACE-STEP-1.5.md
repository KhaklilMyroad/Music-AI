# ACE-Step 1.5 — מדריך והסבר

> מודל קוד-פתוח ליצירת מוזיקה מלאה (שירים עם מילים, כלים, ז'אנרים) שרץ מקומית על החומרה שלך.
> ריפו רשמי: https://github.com/ace-step/ACE-Step-1.5 | רישיון: MIT

## מה זה ACE-Step 1.5?

ACE-Step 1.5 הוא מודל בסיס (foundation model) ליצירת מוזיקה, בפיתוח משותף של ACE Studio ו-StepFun. לפי היוצרים, האיכות שלו נמצאת בין Suno v4.5 ל-Suno v5 — כלומר ברמה מסחרית — אבל הוא חינמי לחלוטין, קוד פתוח (MIT), ורץ מקומית.

### הארכיטקטורה בקצרה
המודל משלב שני רכיבים:
- **מודל שפה (LM)** — "המתכנן": מקבל תיאור פשוט ממך והופך אותו לתוכנית שיר מלאה (מילים, מטא-דאטה, מבנה) באמצעות Chain-of-Thought. מבוסס על Qwen3 (גרסאות 0.6B / 1.7B / 4B).
- **Diffusion Transformer (DiT)** — "המבצע": מייצר את האודיו עצמו לפי התוכנית. גרסאות 2B ו-XL (4B).

### יכולות עיקריות
| יכולת | תיאור |
|---|---|
| Text2Music | שיר מלא מתיאור טקסטואלי, 10 שניות עד 10 דקות |
| מילים ב-50+ שפות | כולל שליטה במבנה השיר דרך המילים |
| Cover | גרסת כיסוי לשיר קיים |
| Repaint | עריכה נקודתית — החלפת קטע בשיר בלי לגעת בשאר |
| Track Separation | הפרדת שיר ל-stems (תופים, בס, ווקאל...) |
| Vocal2BGM | יצירת ליווי אוטומטי לערוץ שירה |
| שליטה במטא-דאטה | BPM, סולם, משקל, משך |
| LoRA Training | אימון סגנון אישי מ-8 שירים בלבד (~שעה על RTX 3090) |
| מהירות | פחות מ-2 שניות לשיר על A100, פחות מ-10 שניות על RTX 3090 |

## דרישות חומרה

- **Python 3.11–3.12**
- **GPU מומלץ** (NVIDIA CUDA, AMD ROCm, Intel XPU, או Apple Silicon/MLX). רץ גם על CPU בלבד — אבל איטי משמעותית.
- מ-**4GB VRAM** בלבד אפשר להריץ (עם offload וקוונטיזציה).

| VRAM | מודל DiT מומלץ | מודל LM מומלץ |
|---|---|---|
| עד 6GB | 2B turbo | בלי LM |
| 6–8GB | 2B turbo | 0.6B |
| 8–16GB | 2B turbo/sft | 0.6B / 1.7B |
| 16–24GB | 2B sft או XL turbo | 1.7B |
| 24GB+ | XL sft | 4B |

ה-UI בוחר אוטומטית את הקונפיגורציה המתאימה ל-GPU שלך.

## התקנה

בתיקיית הפרויקט:

```bash
./setup-acestep.sh
```

הסקריפט מתקין את uv, משכפל את הריפו, ומתקין את כל התלויות. לחלופין, ידנית:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/ACE-Step/ACE-Step-1.5.git
cd ACE-Step-1.5
uv sync
```

למשתמשי **Windows** ו-**macOS** יש חבילות portable מוכנות — ראו את [מדריך ההתקנה הרשמי](https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/INSTALL.md).

## הרצה

```bash
cd ACE-Step-1.5

# ממשק ווב (Gradio) — http://localhost:7860
uv run acestep

# או שרת REST API — http://localhost:8001
uv run acestep-api
```

**בהרצה הראשונה המודלים יורדים אוטומטית מ-Hugging Face** (כמה GB, תלוי באיזה מודל נבחר).

אפשר לקבע הגדרות בקובץ `.env` (מבוסס על `.env.example`):

```
ACESTEP_CONFIG_PATH=acestep-v15-turbo
ACESTEP_LM_MODEL_PATH=acestep-5Hz-lm-1.7B
PORT=7860
```

## קישורים שימושיים

- [Tutorial רשמי](https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/Tutorial.md) — פילוסופיית העיצוב ואיך לכתוב פרומפטים
- [מדריך REST API](https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/API.md)
- [מדריך אימון LoRA](https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/LoRA_Training_Tutorial.md)
- [דמו אונליין בחינם](https://acemusic.ai) — בלי צורך ב-GPU
- [Hugging Face](https://huggingface.co/ACE-Step/Ace-Step1.5)
- [דוח טכני (arXiv)](https://arxiv.org/abs/2602.00744)

## הערה לגבי הסביבה המרוחקת הזו (Claude Code)

הקונטיינר שבו בוצעה ההתקנה הוא **זמני** — הוא נמחק אחרי חוסר פעילות. בנוסף, **אין בו GPU**, כך שיצירת מוזיקה בו תהיה איטית מאוד (CPU בלבד). ההתקנה בוצעה כאן כדי לאמת שהתהליך עובד; כדי להשתמש ב-ACE-Step באמת, הריצו את `./setup-acestep.sh` על מחשב עם GPU.
