# Crescendo — End-to-End Workflow: Build → Beta → Launch

The operational plan from this repo to a marketed product. Phases 0–1 are **done in this
repo**; 2–4 are the runway to revenue.

## Phase 0 — Research & positioning ✅
- Deep-dive ACE-Step 1.5 (architecture, REST contract, licensing) — done, see ARCHITECTURE.md.
- Competitive scan of every music-gen product (Suno v5, Udio, ElevenLabs, Riffusion,
  Stable Audio, MiniMax, Lyria) — done, see MARKET_RESEARCH.md. Conclusion: the
  unlimited+studio+API+ownership combination is unclaimed.

## Phase 1 — Core product (this repo) ✅
- [x] Backend orchestration API over the engine (all 5 task types)
- [x] AI Producer via OmniRoute (plan / lyrics 50+ languages / prompt enhance)
- [x] Studio ops with non-destructive lineage (stems, repaint, cover, extend)
- [x] Batch takes (1–8), audio streaming proxy, live-status library
- [x] React studio UI, docker-compose deployment

## Phase 2 — Private beta (weeks 1–3)
1. Stand up one GPU box (RTX 4090 ≈ $0.35/h spot, or on-prem 3090) running `acestep-api`.
2. `docker compose up` on a $10 VM; put Caddy/Cloudflare in front (TLS + basic auth).
3. Recruit 20–50 creators (Discord servers of Suno power-users are the exact ICP —
   they're the ones hitting credit walls).
4. Instrument: generation counts, take-selection rate, studio-op usage, LLM cost per user
   (should be ≈ $0 via OmniRoute free tiers).
5. Weekly iteration on the top friction point only.

**Exit criteria:** 30+ weekly-active creators, ≥40% use a studio op, engine p95 < 30s.

## Phase 3 — Productization (weeks 4–8)
- Auth + workspaces (start with magic-link email; `users` table alongside `track.owner_id`).
- Billing: **flat tiers, never per-song credits** — that's the wedge vs Suno.
  Free (self-host, unlimited) / Cloud $12/mo (we host GPU, fair-use unlimited) /
  Studio $29/mo (XL model, priority queue, LoRA training) / API metered for devs.
- **Artist DNA**: UI over ACE-Step LoRA training (8 songs → personal style, ~1h on 3090);
  then a public LoRA marketplace — this is the network-effect moat.
- Postgres + object storage; N engine replicas; queue service replaces in-process poller.
- Legal: ToS (user owns output, AI disclosure guidance), DMCA process, ACE-Step MIT
  attribution.

## Phase 4 — Launch & marketing (weeks 8–12)
- **Positioning:** "Unlimited AI music. Your GPU or ours. You own every note."
- **Launch train:** Product Hunt + Hacker News (open-source angle) + r/SunoAI &
  r/LocalLLaMA (self-host angle) + TikTok/Shorts demos ("full song in 10 seconds on a
  gaming PC") + Hebrew tech media (Geektime) for the home market.
- **Content engine:** weekly genre-pack LoRAs; "Suno credit refugee" comparison landing
  page; API quickstart for indie-game/video devs (underserved since Suno has no API).
- **KPIs:** 5k signups in launch month, 8% free→cloud conversion, CAC < $8 via organic.

## Continuous — engine watch
Track ACE-Step releases, YuE, new open models monthly. The adapter pattern means a better
engine is a one-file swap; Crescendo's value compounds in the product layer regardless.
