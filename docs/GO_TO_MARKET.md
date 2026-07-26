# Go-to-Market

## Positioning
**"Unlimited AI music. Your GPU or ours. You own every note."**

Three attack vectors, each aimed at a competitor's structural weakness:
1. **vs Suno/Udio (metering):** no credits, ever. Flat tiers or self-host free.
2. **vs Suno (no API):** first-class REST API from day one — indie games, video tools,
   ad-tech, meditation/fitness apps all need programmatic music.
3. **vs raw open-source (no product):** Suno-grade UX — copilot, studio, takes, library.

## ICP (in order)
1. **Suno power users hitting credit walls** — highest intent, easiest to find (Discord,
   r/SunoAI), already educated. Message: "everything Suno Studio does, unlimited."
2. **Developers needing music APIs** — Riffusion is the only real API player; undercut on
   price and beat on editing endpoints.
3. **Local-AI enthusiasts** — free self-host tier converts to cloud when they want XL
   quality without a 12GB card. (r/LocalLLaMA, HN)
4. **Israeli/regional creators** — native Hebrew lyrics support is a real differentiator;
   Suno's Hebrew is weak. Local PR beachhead before global.

## Pricing
| Tier | Price | What |
|---|---|---|
| Self-Host | Free | Full platform, your GPU, community support |
| Cloud | $12/mo | Hosted GPU, fair-use unlimited, turbo model |
| Studio | $29/mo | XL model, priority queue, Artist-DNA LoRA training, stems export |
| API | $0.02/track + plans | Programmatic access, webhooks |

Unit economics: turbo model ≈ 10s of RTX-4090 time per song ≈ **$0.001/track** hosted —
two orders of magnitude below Suno's implied credit price. LLM copilot cost ≈ $0 via
OmniRoute free-tier routing.

## Launch sequence (see WORKFLOW.md phase 4)
Week 1: Product Hunt + Show HN (open-source repo is the story).
Week 2: creator showcase — 10 beta users' best tracks, TikTok/Shorts cutdowns.
Week 3: API launch on dev channels + hackathon bounty.
Week 4: LoRA marketplace announcement — creators publish/sell styles (rev-share 80/20).

## Moat over time
1. **LoRA marketplace network effects** (styles only work here).
2. **Version-tree remix graph** (lineage data no one else has).
3. **Engine-agnostic core** — every open-model release makes the product better for free.

## Risks & mitigations
- *Suno price cut* → they can't reach $0 marginal; we already are.
- *ACE-Step stalls* → adapter pattern; swap engines.
- *Copyright climate* → we're better placed than Suno (MIT model, user-owned output,
  AI-disclosure tooling built into export flow).
