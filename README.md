# Netflix Narrative Intelligence Pipeline (NIP)

A local-first, multimodal agentic pipeline that audits subtitles and dubs for narrative accuracy, flags on-screen clearance risks, predicts plot holes in scripts, and catches continuity errors across text and video — all before a show goes live.

## Problem

Netflix releases hundreds of original shows annually, each localized into 30+ languages. Four problems persist into final cuts:

1. **Localization breaks the story** — subtitles and dubs are produced per language by vendors who never see the whole show. Character names and invented terms drift between episodes, pronouns and gender are wrong in gendered languages, formal/informal address ignores how a relationship has evolved, and translations sometimes reveal a twist earlier than the original does. Timing errors against picture go unnoticed until viewers complain.
2. **Clearance risks slip into final cuts** — logos, trademarks, artwork, real names, phone numbers, and addresses appear in footage and dialogue without legal clearance. Errors-and-omissions (E&O) review is a manual, frame-by-frame process, and a miss means reshoots, blurring, or legal exposure after release.
3. **Plot holes reach audiences** — no reviewer can hold an entire multi-season narrative in working memory
4. **Continuity errors are caught too late** — script supervisors operate with partial show knowledge; visual errors (wardrobe, props, wounds) are invisible to text-only review

## Architecture

The pipeline runs through 6 stages:

```
Ingest → Frame-Accurate Timeline (SMPTE) → Knowledge Layer (timed facts + scene index + registries)
    → Multi-Agent Inference (4 independent agents) → Verification → Human Review
```

Four specialized agents:

| Agent | Method | Catches |
|-------|--------|---------|
| **Localization Auditor** | KG term/character registry + relationship state + reveal timecodes + SMPTE subtitle alignment | Name/terminology drift, wrong pronouns/gender, formality mismatches, translation-induced spoilers, subtitle timing errors |
| **Clearance Scanner** | CV logo/text detection (OCR) + NER on dialogue + clearance-list matching | Uncleared logos, trademarks, artwork, real names, phone numbers, addresses — timecoded for E&O review |
| **Script Critic** | KG traversal + RAC retrieval + BDI simulation (stretch) | Factual contradictions, motivational gaps, unresolved subplots |
| **Continuity Inspector** | Deterministic graph check + CV/VLM + contrastive pre-filter | Prop swaps, wardrobe changes, wound persistence, location violations |

All models are open-weight and self-hosted — on a laptop, a workstation, or your own cloud account. No data is sent to third-party AI services.

## Documentation

| Document | Contents |
|----------|----------|
| [Architecture](docs/architecture.md) | Pipeline stages, each agent's checks, verification, review, incremental re-runs |
| [Hardware Adaptation](docs/hardware-adaptation.md) | Hardware probe, model catalog, planner, staged vs resident execution, deployment targets |
| [Data Model](docs/data-model.md) | Time representation, Postgres schema, flag and evidence format, input file formats |
| [Tech Stack](docs/tech-stack.md) | Components and versions, model catalog defaults, license policy, Compose layout, monitoring, security |
| [Evaluation](docs/evaluation.md) | Open and public-domain corpus, error injectors, metrics, MVP targets, regression gate |
| [Phased Plan](docs/phased-plan.md) | 8-week plan for 2 people, exit criteria, cut order, risks |
| [API Contracts](docs/api-contracts.md) | REST and WebSocket API, roles, review UI contract |
| [Project Structure](docs/project-structure.md) | Repository layout, module boundaries, dev setup (incl. Windows + WSL2), CLI, configuration |

## Quick Start

```bash
# Prerequisites: Docker (Docker Desktop + WSL2 on Windows), NVIDIA GPU with driver >= 580
git clone <repo-url> netflix-lm
cd netflix-lm
cp .env.example .env
docker compose up -d
docker compose exec api nip doctor   # checks GPU and services, prints the Plan for this hardware
```

See [Project Structure](docs/project-structure.md) for full dev setup instructions.

## Hardware

There is no fixed hardware tier. The same code and container image run everywhere: at startup the system probes the GPUs it has and plans which model sizes to use, how many copies to run, and whether to keep models loaded or swap them stage by stage.

| Machine | What the planner does |
|---------|-----------------------|
| Laptop, 1× 8 GB GPU | Runs stage by stage, one model loaded at a time (a ~4B multimodal model) |
| Workstation, 1× 24–48 GB GPU | Larger models (9B–27B class), mostly or fully resident |
| Cloud node, 8× 80 GB GPUs | Largest models split across GPUs, plus extra copies of the busiest ones |
| Cloud cluster | Copies scale with nodes; autoscaling on Kubernetes (KubeRay) or cloud VMs |

Results get better on bigger hardware; the benchmark reports quality and cost for each hardware Plan. See [Hardware Adaptation](docs/hardware-adaptation.md).

## License

Proprietary. Internal use only.
