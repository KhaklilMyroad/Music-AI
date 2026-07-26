# Crescendo — AI Music Studio

**The open, unlimited AI music platform.** Crescendo wraps the ACE-Step 1.5 foundation model
(MIT-licensed, runs on your own GPU) with a full product layer that matches — and in key areas
exceeds — Suno v5: an AI Producer copilot, a non-destructive editing studio (stems, repaint,
cover, extend), style LoRAs ("Artist DNA"), batch takes, and a real public API.

> עברית: קרשנדו היא פלטפורמת מוזיקה מבוססת AI — ג'נרציה בלתי מוגבלת על GPU שלך,
> סטודיו עריכה מלא, ו-AI Producer שכותב מילים ומתכנן שירים ב-50+ שפות כולל עברית.

## Why Crescendo wins

| Capability | Suno v5 | ACE-Step 1.5 (raw) | **Crescendo** |
|---|---|---|---|
| Cost per song | Credits ($) | Free (DIY setup) | **Free / flat** |
| Official API | ❌ | Bare REST | ✅ Product API |
| AI lyric/song copilot | Basic | ❌ | ✅ Multi-model via OmniRoute |
| Stems | 12 tracks | Generative extract | ✅ One click |
| Inpainting (repaint) | Studio only | Raw endpoint | ✅ Timeline UI |
| Style cloning | Vocal personas | LoRA (CLI) | ✅ Artist DNA (planned UI) |
| Batch takes | 1–2 | up to 8 | ✅ 8 takes per run |
| Ownership / license | Platform ToS | MIT | ✅ You own output |
| Runs locally / on-prem | ❌ | ✅ | ✅ |

## Repository layout

```
backend/     FastAPI orchestration API (jobs, library, studio ops, AI Producer)
frontend/    React studio UI (Vite + TypeScript)
docs/        Market research, architecture, launch workflow, go-to-market
docker-compose.yml
```

## Quick start

Prereqs: a machine with a GPU for the engine (RTX 3090+ recommended; <4 GB VRAM works with
offload), Docker, and optionally an [OmniRoute](https://omniroute.online/) gateway for
near-zero-cost LLM calls.

```bash
# 1. Start the ACE-Step 1.5 engine (on the GPU machine)
git clone https://github.com/ace-step/ACE-Step-1.5.git && cd ACE-Step-1.5
uv sync && uv run acestep-api          # REST engine on :8001

# 2. Start Crescendo
cp .env.example .env                   # point ACESTEP_API_URL / OMNIROUTE_* at your services
docker compose up --build              # backend :8000, frontend :5173
```

Local development without Docker:

```bash
cd backend && pip install -e . && uvicorn app.main:app --reload   # :8000
cd frontend && npm install && npm run dev                          # :5173
```

## Docs

- [docs/MARKET_RESEARCH.md](docs/MARKET_RESEARCH.md) — competitive scan (Suno, Udio, ElevenLabs, Riffusion, Stable Audio) and why this positioning holds
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design
- [docs/WORKFLOW.md](docs/WORKFLOW.md) — end-to-end build → beta → launch workflow
- [docs/GO_TO_MARKET.md](docs/GO_TO_MARKET.md) — pricing, channels, launch plan

## License

Platform code: MIT. Generated audio: yours (ACE-Step 1.5 is MIT; disclose AI involvement where required).

---

## Claude Code: caveman plugin

This repo is configured to use the [caveman](https://github.com/JuliusBrussee/caveman)
Claude Code plugin — an ultra-compressed communication mode that cuts ~75% of
output tokens while keeping full technical accuracy ("why use many token when
few token do trick").

The setup lives in [`.claude/settings.json`](.claude/settings.json), which
registers the marketplace and enables the plugin at the **project scope**. After
opening and trusting the repo, run `/reload-plugins` (or restart) and trigger it
with `/caveman`, or just say "caveman mode". Manual install:

```bash
claude plugin marketplace add JuliusBrussee/caveman
claude plugin install caveman@caveman
```
