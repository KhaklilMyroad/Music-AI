# How Suno builds tracks — and how Crescendo answers

## What the research shows (July 2026)

Suno v5/v5.5 is not one model — it's a **chain of layers**, each answering a different
question ([architecture guide](https://jackrighteous.com/en-us/blogs/guides-using-suno-ai-music-creation/inside-suno-v5-model-architecture),
[Suno Studio analysis](https://stokemctoke.com/a-comprehensive-analysis-of-suno-studio/)):

1. **Arrangement planning** — the system commits to an energy arc (intro → build →
   drop/chorus → breakdown → final peak) before audio is rendered. This is why Suno
   tracks "go somewhere".
2. **Generation** — 48kHz stems-aware synthesis with real dynamic contrast
   ([v5 changes](https://blog.picassoia.com/suno-v5-new-features-what-changed-in-2026)).
3. **Mastering pipeline** — Suno Studio runs mixes through a purpose-built mastering
   chain with LUFS loudness targets; even so, pros re-master to −14 LUFS / −1 dBTP for
   streaming ([mastering guide](https://neuralanalog.com/docs/improve-suno-ai-audio-quality)).

A raw diffusion engine (ACE-Step included) produces layer 2 only. Without layers 1
and 3, output reads as "flat/amateur" no matter how good the prompt is.

## Crescendo's implementation

| Suno layer | Crescendo equivalent |
|---|---|
| Arrangement planning | **Section Composer** (`services/composer.py`): the track is built section-by-section — each section *continues* the previous audio via the engine's `complete` op with its own energy prompt (stripped intro → stacking build → full drop → breakdown → bigger drop → outro). Genre-specific arc plans live in `frontend/src/presets.ts` (`COMPOSE_PLANS`). |
| Quality synthesis | **Pro mode**: `acestep-v15-sft` at 50 inference steps (vs. turbo's 8) — model/steps/guidance are passed per-request. |
| Mastering | **Mastering Engine** (`services/mastering.py`): every finished track is pulled from the engine and run through ffmpeg — rumble cut → glue compression → club EQ → stereo widening → loudnorm (−9 LUFS club default, −14 configurable for streaming) → true-peak limiter. Requires ffmpeg on the backend host. |

Where we go **beyond** Suno: every section boundary is a first-class API concept, so a
weak drop can be repainted alone (`/api/studio/{id}/repaint`) instead of re-rolling the
whole track; the arc plans are user-editable code, not a black box; and it all runs on
the user's own GPU at zero marginal cost.

## Honest ceiling note

On an 8 GB GPU the engine auto-selects the 2B DiT + 0.6B language model. Suno's
absolute vocal-polish ceiling is matched by the **XL stack** (4B DiT + 1.7B/4B LM),
which needs ≥12 GB VRAM — a rented RTX 4090/A100 (~$0.35/h) pointed to by
`ACESTEP_API_URL` unlocks it with zero code changes.
