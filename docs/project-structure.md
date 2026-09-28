# Project Structure

## Repository Layout

```
netflix-lm/
├── README.md
├── docs/                                  # This documentation
├── pyproject.toml                         # Python project (package: nip), managed with uv
├── uv.lock
├── compose.yaml                           # Single-node deployment: laptop, workstation, one cloud VM
├── .env.example                           # Every NIP_* variable with defaults
│
├── config/                                # Behavior lives here, not in code
│   ├── catalog.yaml                       # Model catalog: slots → ranked variants
│   ├── pipeline.yaml                      # Thresholds, keyframe policy, caps, retry policy
│   ├── languages/                         # Localization rule packs
│   │   ├── _base.yaml  ├── en.yaml  ├── es.yaml  ├── es-ES.yaml  ├── fr.yaml  └── de.yaml
│   ├── clearance/
│   │   ├── fiction_phone_ranges.yaml      # Fiction-reserved number ranges per country
│   │   └── detector_prompts.yaml          # Open-vocabulary labels for the logo/artwork channel
│   └── rules/                             # Deterministic rule queries (SQL), one file per check
│       ├── plot.knowledge_order.sql  ├── plot.two_places.sql  └── ...
│
├── src/nip/
│   ├── contracts/          # Pydantic models shared by everything: Flag, Evidence, Fact, Plan, HardwareInventory
│   ├── timecode/           # Frame ↔ SMPTE ↔ ms math (pure functions, property-tested)
│   ├── ingest/             # Parsers + validation: fountain, fdx, pdf, srt, vtt, ttml, bible, glossary, clearance log, media probe
│   ├── timeline/           # Shot detection, keyframes, speech-to-text, script↔transcript and subtitle alignment
│   ├── knowledge/          # Extraction, grounding validator, entity resolution, consolidation, story order, registries, retrieval
│   ├── agents/
│   │   ├── base.py         # Check interface: required inputs, work-unit generation, flag emission
│   │   ├── localization/   # term, gender, formality, spoiler, readability, shot_change, drift, offset
│   │   ├── clearance/      # ocr_text, logos, dialogue_refs, matching, occurrences, report
│   │   ├── script_critic/  # layer1 (SQL rules), motivation, setups
│   │   └── continuity/     # text_rules, setup_clustering, prefilter, visual_verify
│   ├── verification/       # evidence resolver, rule re-check, judge, routing, dedup
│   ├── runtime/
│   │   ├── probe.py        # HardwareInventory from every Ray node (NVML)
│   │   ├── catalog.py      # Load + validate catalog.yaml
│   │   ├── planner.py      # Pure function: (inventory, catalog, workload, objective, pins) → Plan
│   │   ├── serving.py      # Ray Serve applications per slot; deploy / teardown / scale
│   │   ├── scheduler.py    # Staged vs resident execution, work-unit dispatch, retries, OOM amendments
│   │   ├── controller.py   # Long-lived Ray actor: picks queued runs from Postgres and executes them
│   │   ├── cache.py        # Cache keys + stage cache
│   │   └── clients/        # Capability clients (text_llm, vlm, asr, ocr, detector, embedders, ner) + stub backends
│   ├── store/              # Postgres access, migrations (Alembic), object storage client
│   ├── api/                # FastAPI app: routes, OIDC auth, WebSocket events
│   └── cli.py              # `nip` command-line interface
│
├── ui/                                    # Review UI (React + TypeScript + Vite)
│   └── src/views/  EpisodeList · Report · FlagDetail · ClearanceReport · FactQueue · RunView · DiffView
│
├── eval/
│   ├── corpus/manifest.yaml               # Titles, licenses, attribution, source URLs, checksums (media never committed)
│   ├── injectors/                         # localization · clearance · script · continuity
│   ├── synthetic/                         # Generator for multi-episode scripts with planted plot holes
│   ├── metrics.py                         # Matching flags to labels; precision / recall / F1 per check
│   └── report.py                          # Per-Plan benchmark report
│
├── deploy/
│   ├── docker/
│   │   ├── nip.Dockerfile                 # One image: API, Ray head/worker, controller (FROM vllm/vllm-openai:v0.30.0 + Ray 2.58)
│   │   └── ui.Dockerfile                  # Caddy + built UI
│   ├── helm/nip/                          # Cluster deployment: KubeRay RayCluster + API + UI
│   └── ray/                               # Ray cluster-launcher configs for VM-based clusters
│
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/dashboards/                # pipeline · agents · plans-and-gpus · review
│
└── tests/
    ├── unit/            # timecode, parsers, planner, rules, cache keys, evidence resolver
    ├── contract/        # model clients against recorded responses (no GPU)
    ├── integration/     # full pipeline on the fixture episode (cpu profile in CI; real models nightly)
    └── fixtures/        # 2-minute clip, matching script, en + es subtitles, bible, clearance log
```

**Why one image.** The API, the Ray head, Ray workers, and the run controller all use `nip.Dockerfile`, differing only by entrypoint. The laptop and the cloud run the same image digest.

---

## Module Responsibilities

| Module | Depends on | Must not depend on |
|--------|-----------|--------------------|
| `contracts` | pydantic | anything else in `nip` |
| `timecode` | stdlib | anything else |
| `ingest`, `timeline` | contracts, timecode, store, runtime.clients | agents |
| `knowledge` | contracts, store, runtime.clients | agents |
| `agents/*` | contracts, knowledge (read), store (read), runtime.clients | other agents, verification |
| `verification` | contracts, store, rules, runtime.clients | agents |
| `runtime` | contracts, Ray, vLLM | agents' internals (it sees only work units) |
| `api` | contracts, store | runtime internals (runs are queued in Postgres, not called directly) |

Agents never import each other; the import-linter contract in CI enforces the table above.

**How a run flows through modules:** `api` inserts a `run` row (`queued`) → `runtime.controller` (inside the Ray cluster) claims it → `runtime.planner` produces the Plan → `runtime.scheduler` executes stage groups, calling `ingest`/`timeline`/`knowledge`/`agents` work units → `verification` → report persisted → WebSocket event.

---

## Dev Setup

### Prerequisites

| Environment | Requirements |
|-------------|--------------|
| **Windows 11 (e.g. the RTX 4060 laptop)** | NVIDIA Windows driver **≥ 580** (the image is CUDA 13; it provides CUDA inside WSL2), WSL ≥ 2.1.5 with Ubuntu (`wsl --update`), Docker Desktop with the WSL2 backend (it ships its own NVIDIA container toolkit). Do **not** install a Linux NVIDIA driver inside WSL. |
| **Linux workstation / cloud VM** | NVIDIA driver ≥ 580, Docker Engine + Compose v2, NVIDIA Container Toolkit |
| **Kubernetes** | NVIDIA GPU Operator on GPU nodes, KubeRay operator 1.7.x, Helm |
| **Everywhere** | `uv` (Python), Node.js LTS (UI development only) |

**Windows disk placement.** Model weights and media need tens to hundreds of GB. Put Docker Desktop's disk image and the WSL distro on the large drive (Docker Desktop → Settings → Resources → Advanced → *Disk image location*), and clone the repository **inside the WSL filesystem** (e.g. `~/code/netflix-lm`) — bind mounts from `/mnt/c` or `/mnt/d` are much slower.

**Windows memory.** WSL2 gives its VM 50% of host RAM by default. On a 32 GB laptop, raise it so Ray's object store and vLLM have room:

```ini
# %UserProfile%\.wslconfig
[wsl2]
memory=24GB
```

Run `wsl --shutdown` after editing, then restart Docker Desktop.

### First run

```bash
git clone <repo-url> netflix-lm && cd netflix-lm
cp .env.example .env                    # set passwords; defaults work for local use
docker compose up -d                    # Postgres, object storage, Ray head, API, UI, Keycloak, monitoring
docker compose exec api nip doctor      # GPU visible? services healthy? prints inventory + Plan preview
docker compose exec api nip models pull # downloads only the variants the current Plan needs
docker compose exec api nip eval corpus fetch --set smoke
docker compose exec api nip run --show smoke --episodes S01E01 --agents auto
```

| URL | Service |
|-----|---------|
| `http://localhost:8080` | Review UI (served by the `ui` container, which also reverse-proxies `/api` and `/ws`) |
| `http://localhost:8080/api/v1` | API (same origin as the UI — no CORS configuration needed) |
| `http://localhost:8265` | Ray dashboard |
| `http://localhost:3001` | Grafana |
| `http://localhost:8180` | Keycloak (local identity provider) |

### The `nip` CLI

| Command | Purpose |
|---------|---------|
| `nip doctor` | Verify GPU visibility, service health, NVML access; print inventory and Plan preview |
| `nip plan [--objective quality\|throughput] [--simulate inventory.json]` | Show the Plan for this hardware, or for a simulated inventory (planner testing and capacity planning) |
| `nip models pull` · `nip models mirror --to s3://…` | Fetch the variants the Plan needs; mirror weights into internal storage for egress-free production |
| `nip ingest --show S --episode E files…` | Register sources (same validation as the API) |
| `nip run --show S --episodes E… [--agents …] [--force]` | Queue a run and stream progress |
| `nip eval corpus fetch --set {smoke\|mvp}` | Download corpus titles from the manifest and verify checksums |
| `nip eval inject --set mvp --seed 7` | Generate injected variants + ground-truth labels |
| `nip eval run --set mvp` | Run the benchmark on the current Plan and write the report |

### Tests

```bash
uv run pytest tests/unit tests/contract          # no GPU, no services — runs in CI
docker compose run --rm api pytest tests/integration   # fixture episode, NIP_PROFILE=cpu (stub models)
NIP_PROFILE=auto docker compose run --rm api pytest tests/integration -m gpu   # real models (nightly)
uv run nip eval run --set smoke                  # quick benchmark sanity check
```

CI runs lint (ruff), type checks, import-linter, unit + contract tests, and the integration suite on the `cpu` profile. The nightly job runs the integration suite with real models and the `smoke` benchmark on a GPU runner; merges that lower benchmark F1 beyond the threshold in [Evaluation](evaluation.md#regression-gate) are blocked.

---

## Configuration

All configuration is environment variables (`NIP_*`) plus the files in `config/`. Moving from the laptop to the cloud changes **environment values only** — never code, images, or `config/` files.

```bash
# .env.example (excerpt)

# Runtime
NIP_PROFILE=auto                  # auto = probe hardware; cpu = stub model backends (tests/CI)
NIP_PLAN_OBJECTIVE=quality        # quality | throughput
NIP_PIN_TEXT_LLM=                 # optional: pin a slot to a catalog variant id
NIP_PIN_VLM=
NIP_GPU_MEM_UTILIZATION=0.90      # upper bound per GPU; the planner also subtracts memory already in use
NIP_RAY_ADDRESS=auto              # auto locally; set by Helm on Kubernetes
NIP_AUTOSCALE_MAX_GPU_NODES=0     # 0 = no autoscaling

# Storage
NIP_DATABASE_URL=postgresql://nip:change_me@postgres:5432/nip
NIP_S3_ENDPOINT=http://objectstore:8333   # SeaweedFS locally; empty = native cloud endpoint
NIP_S3_MEDIA_BUCKET=nip-media
NIP_S3_ARTIFACT_BUCKET=nip-artifacts
NIP_MODEL_CACHE=/models           # local weights cache (mount a large disk here)
NIP_MODEL_SOURCE=hf               # hf = download (dev); s3://nip-models = internal mirror (egress-free production)

# Public URL (what browsers use; the API base is ${NIP_PUBLIC_URL}/api/v1)
NIP_PUBLIC_URL=http://localhost:8080

# Auth
NIP_OIDC_ISSUER=http://localhost:8180/realms/nip        # must equal the token's `iss` (the URL browsers use)
NIP_OIDC_JWKS_URL=http://keycloak:8080/realms/nip/protocol/openid-connect/certs   # internal fetch URL
NIP_OIDC_AUDIENCE=nip-api
NIP_OIDC_ROLES_CLAIM=roles

# Review thresholds
NIP_TIER_MUST_REVIEW=0.90
NIP_TIER_REVIEW_RECOMMENDED=0.70
NIP_FACT_REVIEW_THRESHOLD=0.80
NIP_INFERRED_STORY_CONFIDENCE_FACTOR=0.85

# Cost controls
NIP_VLM_CALLS_PER_EPISODE_MAX=auto   # auto = derived from the Plan's throughput
```
