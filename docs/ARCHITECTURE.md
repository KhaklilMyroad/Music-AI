# Architecture

```
┌────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Frontend   │────▶│  Crescendo API    │────▶│  ACE-Step 1.5 engine │
│  React/Vite │     │  FastAPI :8000    │     │  REST :8001 (GPU)    │
└────────────┘     │                  │     └─────────────────────┘
                   │  SQLite/Postgres │     ┌─────────────────────┐
                   │  job poller      │────▶│  OmniRoute gateway   │
                   └──────────────────┘     │  :4000 (LLM routing) │
                                            └─────────────────────┘
```

## Components

### Crescendo API (`backend/`)
- **`services/acestep.py`** — adapter for the engine's REST contract
  (`/release_task`, `/query_result`, `/v1/audio`). All five task types are wired:
  `text2music`, `repaint`, `cover`, `extract` (stems), `complete` (extend).
  Engine-agnostic by design: a future engine = one new adapter class.
- **`services/llm.py`** — the AI Producer. All LLM calls (song planning, lyrics in 50+
  languages, prompt enhancement) go through **OmniRoute**, an OpenAI-compatible gateway
  that routes each call down a fallback chain (subscription → API key → cheap → free
  tiers) and compresses tokens — so copilot features cost near-zero credits.
- **`services/jobs.py`** — async poller reconciling pending tracks against the engine
  every few seconds. In-process (no Redis) for v1; swap for a queue at scale.
- **`routers/`** — `songs` (generate/list/stream/delete), `studio` (non-destructive edit
  ops that spawn child tracks with `parent_id` lineage), `copilot` (LLM endpoints).
- **DB** — SQLModel; SQLite for dev, `DATABASE_URL` switches to Postgres unchanged.

### Frontend (`frontend/`)
Vite + React + TS single-page studio: idea box → AI Producer (plan/enhance/lyrics) →
generation form (language, duration, 1–8 takes) → live library (status polling) →
per-track studio (player, stems, repaint by time range, cover with strength, extend).
RTL-safe (`dir="auto"`) for Hebrew/Arabic lyrics.

### Audio delivery
Generated files live on the engine host; the backend streams them through
`GET /api/songs/{id}/audio` (proxy over the engine's `/v1/audio?path=`), so the GPU box
never needs public exposure.

## Deployment topologies
1. **Single box** (dev/indie): everything + GPU on one machine, `docker compose up`.
2. **Split** (prod): GPU engine box(es) private; API + frontend on cheap VMs/CDN.
3. **Scale-out**: N engine replicas behind a round-robin in the adapter; Postgres; object
   storage for finished audio; per-user auth & billing (see WORKFLOW.md phase 3).

## Design decisions
- **Non-destructive lineage**: every edit is a new `Track` with `parent_id` — a full
  version tree per song, undo for free, and a future "remix graph" UI.
- **Batch takes**: engine `batch_size` up to 8 exposed as "takes" — the pick-the-best-take
  flow that Suno charges per-generation for.
- **Credits philosophy**: generation is compute the user already owns (their GPU);
  only LLM calls could cost money, and OmniRoute drives that to ~zero.
