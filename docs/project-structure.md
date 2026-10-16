# Project Structure

## Repository Layout

```
netflix-lm/
├── README.md
├── docs/                                  # This documentation, incl. decisions.md, experiments.md, journal.md
├── pyproject.toml                         # Python project (package: nip), managed with uv
├── uv.lock
├── compose.yaml                           # Single-node deployment: laptop, workstation, one cloud VM
├── .env.example                           # Every NIP_* variable with defaults
├── .pre-commit-config.yaml                # ruff, mypy, end-of-file checks before each commit
├── .github/workflows/
│   ├── ci.yml                             # Every PR: lint, types, licenses, unit + contract + cpu-profile integration tests
│   ├── nightly.yml                        # Scheduled, self-hosted GPU runner: real-model integration + smoke benchmark
│   └── release.yml                        # Tag: build images once, push to GHCR, Helm chart test on kind
│
├── config/                                # Behavior lives here, not in code
│   ├── catalog.yaml                       # Model catalog: slots → ranked variants
│   ├── pipeline.yaml                      # Thresholds, keyframe policy, caps, retry policy
│   ├── languages/                         # Localization rule packs
│   │   ├── _base.yaml  ├── en.yaml  ├── es.yaml  ├── es-ES.yaml  ├── fr.yaml  └── de.yaml
│   ├── clearance/
│   │   ├── fiction_phone_ranges.yaml      # Fiction-reserved number ranges per country
│   │   └── detector_prompts.yaml          # Open-vocabulary labels for the logo/artwork channel
│   ├── rules/                             # Deterministic rule queries (SQL), one file per check
│   │   ├── plot.knowledge_order.sql  ├── plot.two_places.sql  └── ...
│   ├── prompts/                           # Versioned prompts, one file per version: loc.gender.v5.md (git is the prompt registry)
│   └── licenses.yaml                      # License allowlist enforced at startup and in CI
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
│   │   ├── controller.py   # pgqueuer worker inside the Ray cluster: claims queued runs (one active per episode) and executes them
│   │   ├── cache.py        # Cache keys + stage cache
│   │   └── clients/        # Capability clients (text_llm, vlm, asr, ocr, detector, embedders, ner) + stub backends
│   ├── store/              # Postgres access, migrations (Alembic), object storage client
│   ├── api/                # FastAPI app: routes, OIDC auth, WebSocket events
│   └── cli.py              # `nip` command-line interface
│
├── ui/                                    # Review UI: React-admin + ra-keycloak (React + TypeScript + Vite)
│   └── src/views/  EpisodeList · Report · FlagDetail · ClearanceReport · FactQueue · RunView · DiffView
│
├── eval/
│   ├── corpus/manifest.yaml               # Titles, licenses, attribution, source URLs, checksums (media never committed)
│   ├── injectors/                         # localization · clearance · script · continuity
│   ├── synthetic/                         # Generator for multi-episode scripts with planted plot holes
│   ├── labeling/                          # Label Studio project configs; push media, pull finished labels
│   ├── metrics.py                         # Optimal one-to-one matching of flags to labels (scipy); precision / recall / F1 per check
│   └── report.py                          # Per-Plan benchmark report, MLflow logging, `nip eval compare`
│
├── deploy/
│   ├── docker/
│   │   ├── nip.Dockerfile                 # One image: API, Ray head/worker, controller (FROM vllm/vllm-openai:v0.30.0 + Ray 2.58)
│   │   ├── ui.Dockerfile                  # Caddy + built UI
│   │   └── mlflow.Dockerfile              # Official MLflow image + Postgres driver + S3 client
│   ├── helm/nip/                          # Cluster deployment: KubeRay RayCluster + API + UI
│   └── sky/                               # SkyPilot task files for cloud GPU machines (Phase 4)
│
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/dashboards/                # pipeline · agents · plans-and-gpus · review
│
└── tests/
    ├── unit/            # timecode, parsers, planner, rules, cache keys, evidence resolver
    ├── contract/        # model clients against recorded responses (no GPU)
    ├── integration/     # full pipeline on the fixture episode (cpu profile in CI; real models nightly)
    ├── oracles/         # cross-checks against OpenTimelineIO, timecode, seconv lint, ffsubsync (own environment)
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
| `http://localhost:5000` | MLflow (experiment runs and comparisons) |
| `http://localhost:8081` | Label Studio (only with `docker compose --profile labeling up`) |
| `http://localhost:5151` | FiftyOne (local only: `uv run fiftyone app launch`) |

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
| `nip eval run --set mvp [--exp EXP-0XX --variant <name>] [--seeds 1,2,3]` | Run the benchmark on the current Plan, write the report, and log the run to MLflow |
| `nip eval labels push --project <name>` · `pull` | Send clips or keyframes to a Label Studio project; pull finished labels into `eval/labels/` |
| `nip eval compare --exp EXP-0XX --md` · `--runs <id> <id>` | Comparison table (mean ± std across seeds, with MLflow run IDs) for [experiments.md](experiments.md) |

### Tests

```bash
uv run pytest tests/unit tests/contract          # no GPU, no services — runs in CI
docker compose run --rm api pytest tests/integration   # fixture episode, NIP_PROFILE=cpu (stub models)
NIP_PROFILE=auto docker compose run --rm api pytest tests/integration -m gpu   # real models (nightly)
uv run nip eval run --set smoke                  # quick benchmark sanity check
```

CI (GitHub Actions, `ci.yml`) runs on every pull request: lint (ruff), type checks (mypy), import-linter, the dependency license gate (pip-licenses against `config/licenses.yaml`), unit + contract tests with coverage, and the integration suite on the `cpu` profile. `pre-commit` runs the same lint and type checks locally before each commit.

The nightly job (`nightly.yml`) runs on a **self-hosted runner on the dev laptop** (WSL2 + Docker Desktop GPU): the integration suite with real models and the `smoke` benchmark, logged to MLflow. Merges that lower benchmark F1 beyond the threshold in [Evaluation](evaluation.md#regression-gate) are blocked. The self-hosted runner only accepts scheduled or manually started workflows on `main`; it never runs pull requests from forks.

`release.yml` builds the `nip`, `nip-ui`, and `nip-mlflow` images once per tag, pushes them to GHCR, and tests the Helm chart on a `kind` cluster. Every environment pulls those exact digests.

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
AWS_ACCESS_KEY_ID=nip             # S3 credentials (SeaweedFS locally; IAM or HMAC keys in the cloud)
AWS_SECRET_ACCESS_KEY=change_me

# Experiment tracking
NIP_MLFLOW_TRACKING_URI=http://mlflow:5000
NIP_MLFLOW_BACKEND_URI=postgresql://nip:change_me@postgres:5432/mlflow
NIP_MLFLOW_TRACE=benchmark        # benchmark = trace LLM calls only in benchmark runs; off = never
MLFLOW_DISABLE_TELEMETRY=true     # no usage telemetry to MLflow's servers

# Egress
TLDEXTRACT_PUBLIC_SUFFIX_LIST_URLS=   # Presidio's email check uses the bundled domain list, never downloads
HF_HUB_OFFLINE=0                  # set to 1 in production: weights only from the local cache or internal mirror

# Labelling (docker compose --profile labeling up)
POSTGRE_PASSWORD=change_me        # Label Studio's own variable name for its database password

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
