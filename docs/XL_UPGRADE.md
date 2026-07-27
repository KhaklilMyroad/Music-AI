# Unlocking full quality: the XL stack on a rented GPU

## Why

ACE-Step 1.5's published quality ("between Suno v4.5 and v5, beats v5 on parts of
SongEval") is measured on the **full stack**: the 4B-parameter XL DiT + a 1.7B/4B
language-model planner. An 8 GB laptop GPU auto-selects the reduced stack (2B DiT +
0.6B LM) — the planner is 6x smaller, and it is the component that composes. No prompt
engineering closes that gap. A rented GPU does, for ~$0.35–0.60/hour, with **zero code
changes**: Crescendo's engine adapter just points at a different URL.

| | Laptop 8 GB | Rented RTX 4090 (24 GB) | Rented A100 |
|---|---|---|---|
| DiT | 2B turbo/sft | **XL sft (4B)** | XL sft |
| LM planner | 0.6B | **1.7B–4B** | 4B |
| Song gen time | ~75s | ~15–25s | <5s |
| Cost | free | ~$0.40/h | ~$1.2/h |

## Setup (15 minutes, RunPod example)

1. **Create a pod**: [runpod.io](https://runpod.io) → Deploy → GPU Pod → RTX 4090 (24 GB)
   → template "PyTorch 2.x / CUDA 12" → expose TCP port **8001**.
2. **Install the engine** (pod terminal):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh && source ~/.bashrc
   git clone https://github.com/ace-step/ACE-Step-1.5.git && cd ACE-Step-1.5
   uv sync
   ACESTEP_CONFIG_PATH=acestep-v15-xl-sft ACESTEP_LM_MODEL_PATH=acestep-5Hz-lm-4B \
     uv run acestep-api --host 0.0.0.0 --port 8001
   ```
   First run downloads ~15 GB of weights (one-time per pod volume).
3. **Point Crescendo at it** — on your machine edit `backend/.env` (create it if missing):
   ```
   ACESTEP_API_URL=https://<pod-id>-8001.proxy.runpod.net
   ```
   Restart the backend. The Engine pill goes green when connected.
4. **Generate.** Same UI, same workflow — XL quality. Studio ops that need other models
   (base for stems/extend) auto-download on the pod on first use.

## Cost discipline

- Stop the pod when not producing (billing is per-minute on most providers).
- A 3-hour production session ≈ $1.2 — roughly the price of ~120 songs' worth of Suno
  credits, except the count is unlimited.
- Alternatives: vast.ai (often cheaper spot 4090s), Lambda, or any box with ≥12 GB VRAM
  (XL with offload) / ≥20 GB (XL comfortable).

## Local fallback

Keep the laptop engine for free drafts; switch `ACESTEP_API_URL` (or keep two backend
`.env` profiles) when you want release quality. Draft locally → recreate the keeper on XL.
