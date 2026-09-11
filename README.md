# Netflix Narrative Intelligence Pipeline (NIP)

A local-first, multimodal agentic pipeline that writes episode recaps, predicts plot holes in scripts, and flags continuity errors across text and video — all before a show goes live.

## Problem

Netflix releases hundreds of original shows annually. Three problems persist into final cuts:

1. **Recap creation is manual and slow** — editorial bottleneck delays metadata, marketing copy, and in-app descriptions
2. **Plot holes reach audiences** — no reviewer can hold an entire multi-season narrative in working memory
3. **Continuity errors are caught too late** — script supervisors operate with partial show knowledge; visual errors (wardrobe, props, wounds) are invisible to text-only review

## Architecture

The pipeline runs through 6 stages:

```
Ingestion → SMPTE-Aligned Timeline → Dual Knowledge Representation (KG + RAC)
    → Multi-Agent Inference (3 agents) → Verification & Compliance → Human Editorial Gate
```

Three specialized agents:

| Agent | Method | Catches |
|-------|--------|---------|
| **Script Critic** | KG traversal + RAC retrieval + BDI simulation (stretch) | Factual contradictions, motivational gaps, unresolved subplots |
| **Continuity Inspector** | Deterministic graph check + CV/VLM + contrastive pre-filter | Prop swaps, wardrobe changes, wound persistence, location violations |
| **Recap Agent** | KG scene nodes + RAC tone retrieval + per-show LoRA (stretch) | Tone-matched recaps, multi-variant outputs, spoiler control |

All models run locally. No data leaves your machines.

## Documentation

| Document | Contents |
|----------|----------|
| [Architecture](docs/architecture.md) | Full pipeline design, data flow, agent deep dives, verification layers |
| [Tech Stack](docs/tech-stack.md) | Models, hardware, Docker Compose layout, monitoring, security |
| [Phased Plan](docs/phased-plan.md) | 4-phase build plan (P1–P4), milestones, entry/exit criteria |
| [Data Schemas](docs/data-schemas.md) | EpisodeDocument, KG schemas, agent output schemas, configs |
| [API Contracts](docs/api-contracts.md) | REST endpoints, personalization interface, editorial UI contract |
| [Project Structure](docs/project-structure.md) | Directory layout, module responsibilities, dev setup |

## Quick Start

```bash
# Prerequisites: Docker, Docker Compose, NVIDIA GPU with drivers
git clone <repo-url> netflix-lm
cd netflix-lm
cp .env.example .env
docker compose up -d
```

See [Project Structure](docs/project-structure.md) for full dev setup instructions.

## Hardware Requirements

| Config | GPUs | Use Case |
|--------|------|----------|
| Production | 8x A100 80GB | Full pipeline, all agents, VLM inference |
| MVP | 4x RTX 4090 24GB | Quantized models, sequential inference, no VLM fine-tuning |

See [Tech Stack](docs/tech-stack.md) for full hardware specifications.

## License

Proprietary. Internal use only.
