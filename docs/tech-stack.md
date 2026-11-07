# Tech Stack

## Design Principles

- **Self-hosted, open-weight only.** No third-party AI APIs. Production nodes run without internet egress; model weights are mirrored into internal storage (`nip models mirror`).
- **One image everywhere.** The same image digest runs on a Windows laptop (via WSL2) and on cloud GPU clusters.
- **Permissive licenses by default.** Every default component and model is Apache-2.0, MIT, BSD, CC-BY, or PostgreSQL-licensed. The catalog validator rejects anything else (see [License Policy](#license-policy)).
- **Pin, then bump deliberately.** Versions are pinned in `uv.lock`, the Dockerfile, and `catalog.yaml`; bumping any of them requires a benchmark run ([Evaluation › Regression Gate](evaluation.md#regression-gate)).

Versions below were current on 2026-09-27.

---

## Platform Components

| Layer | Technology | Version | License | Why |
|-------|-----------|---------|---------|-----|
| Language | Python | 3.12 | PSF | Ecosystem for Ray, vLLM, and model tooling |
| Compute fabric | Ray (Core + Serve) | 2.58.0 | Apache-2.0 | Same code on one machine or a cluster; resource-aware scheduling; autoscaling on VMs and Kubernetes |
| LLM / VLM engine | vLLM (OpenAI-compatible server, run inside Ray Serve replicas) | 0.30.0 | Apache-2.0 | Supports every default LLM/VLM; AWQ/INT4/FP8; JSON-schema structured outputs; image inputs |
| Base image | `vllm/vllm-openai:v0.30.0` + Ray + `nip` | CUDA 13.0 | — | One image for API, Ray head/workers, and controller. Needs NVIDIA driver ≥ 580 |
| Database | PostgreSQL + `pgvector` + `btree_gist` | 18 · design to pgvector 0.8.2 | PostgreSQL | One transactional store for timeline, facts, vectors, flags, audit ([Data Model](data-model.md)) |
| Object storage (local) | SeaweedFS (S3 API) | 4.47 | Apache-2.0 | S3-compatible, lightweight, actively maintained |
| Object storage (cloud) | AWS S3 · Google Cloud Storage (XML API + HMAC keys) · Azure Blob via an S3 shim | — | — | Same S3 client code; only `NIP_S3_*` values change |
| API | FastAPI + Uvicorn | current | MIT / BSD | Typed REST + WebSocket |
| DB access | SQLAlchemy 2 (Core) + psycopg 3 + Alembic | current | MIT / LGPL-3.0 / MIT | Raw SQL for rules, migrations |
| Review UI | React-admin + `ra-keycloak` on React + TypeScript + Vite, served by Caddy (also reverse-proxies `/api` and `/ws`) | 5.15.4 · 2.0.0 | MIT / Apache-2.0 | List, filter, and detail screens and OIDC login out of the box; the evidence player is a plain React component on `<video>` ([D-029](decisions.md#d-029--review-ui-react-admin--ra-keycloak)) |
| Identity | Keycloak locally; any OIDC provider in production | current | Apache-2.0 | Standard OIDC; roles from a token claim |
| Media | FFmpeg (LGPL shared build) + TorchCodec | current · 0.17.0 | LGPL-2.1 / BSD-3-Clause | FFmpeg: probe and review proxies. TorchCodec: frame-exact decoding for shot detection and keyframes, using our FFmpeg libraries ([D-027](decisions.md#d-027--parsing-and-decoding-libraries-and-what-stays-custom)) |
| Parsing | ttconv (TTML/IMSC), pysubs2 (SRT/WebVTT), screenplay-tools (Fountain), pdfplumber (PDF), stdlib XML (FDX) | 1.2.3 · 1.9.0 · 0.0.10 · current | BSD-2-Clause / MIT | Libraries where they pass our tests; our own FDX and PDF script readers ([D-027](decisions.md#d-027--parsing-and-decoding-libraries-and-what-stays-custom)) |
| Phone numbers | `phonenumbers` (libphonenumber port) | current | Apache-2.0 | Format/possibility checks for `clr.phone` |
| GPU inventory | `nvidia-ml-py` (imported as `pynvml`) | 13.615.71 | BSD | NVML access; the old `pynvml` package is deprecated |
| Kubernetes | KubeRay operator + `ray-cluster` Helm chart; NVIDIA GPU Operator | 1.7.1 · v26.7.1 | Apache-2.0 | GPU nodes and Ray clusters on Kubernetes (the chart's default Ray image is old — always override it with the `nip` image) |
| Monitoring | Prometheus + `prometheus-client` + Grafana; vLLM's and Ray's built-in metrics; NVIDIA DCGM exporter on cloud GPU nodes (ships with the GPU Operator) | current | Apache-2.0 / AGPL-3.0 | Live operational metrics. Grafana runs unmodified as a separate service |
| Experiment tracking | MLflow (tracking server and UI; LLM call tracing on benchmark runs) | pinned at setup | Apache-2.0 | Every benchmark run's settings, metrics, and reports, compared side by side; stored in our Postgres and SeaweedFS ([D-022](decisions.md#d-022--self-hosted-mlflow-for-experiments-no-dag-tool-no-hosted-trackers)) |
| Run queue | pgqueuer (Postgres-backed) | 1.5.0 | MIT | One active run per episode, cancellation, and requeue after a worker crash, on the Postgres we already run ([D-023](decisions.md#d-023--run-queue-pgqueuer-no-ray-jobs)) |
| Cloud provisioning | SkyPilot | 0.14.0 | Apache-2.0 | Finds the cheapest available GPU machines across ~25 clouds and Kubernetes, runs our image, starts Ray ([D-024](decisions.md#d-024--cloud-provisioning-skypilot)) |
| Labelling | Label Studio Community | 1.23.2 | Apache-2.0 | Hand-made ground truth for experiments: cuts, camera setups, line starts, fact checks, story order ([D-028](decisions.md#d-028--labelling-and-inspection-label-studio--fiftyone)) |
| Data inspection | FiftyOne open source (local only) | 1.22.1 | Apache-2.0 | Browse keyframes, detection boxes, and embedding clusters. Bundles MongoDB (SSPL), so it is never deployed |
| Pipeline / DAG | None separate: the stage-group order and each check's declared inputs, run by our controller on Ray | — | — | A second scheduler would compete with Ray for GPUs ([D-004](decisions.md#d-004--no-orchestrator-incremental-re-runs-from-a-content-hash-cache)). Progress is visible in the Ray dashboard and the run view |
| Tooling | uv, ruff, mypy, pytest + pytest-cov, Hypothesis, import-linter, pre-commit, pip-licenses | current | MIT / Apache-2.0 / BSD | Lockfile, lint, types, tests, coverage, module boundaries, lint-before-commit, dependency license gate |
| CI/CD | GitHub Actions; a self-hosted runner on the dev laptop for nightly GPU jobs; GHCR (image registry); kind (tests the Helm chart without GPUs) | — | — | The same image digest built once in CI and pulled by every environment |
| Windows dev | Docker Desktop (WSL2 backend) + WSL | 4.92 · 2.7 | — | GPU containers on Windows 11 |

### Libraries

| Purpose | Library | License | Used for |
|---------|---------|---------|----------|
| Model runtimes | transformers, sentence-transformers, gliner | Apache-2.0 | Detector, image and text embedders, NER |
| | faster-whisper (CTranslate2) | MIT | Speech-to-text with word timestamps |
| | PaddleOCR | Apache-2.0 | On-screen text |
| | transnetv2-pytorch, scenedetect | MIT / BSD-3-Clause | Shot boundaries, fades |
| Model files | huggingface_hub | Apache-2.0 | `nip models pull` / `mirror` |
| Model client | openai (Python SDK) | Apache-2.0 | Calls to vLLM's OpenAI-compatible API, including `response_format` JSON schemas; instructor wraps it |
| Vision & numeric | OpenCV | Apache-2.0 | Image sharpness for clearance prominence; compositing in injectors |
| | scikit-learn | BSD-3-Clause | Clustering shots by camera setup |
| | NumPy, Pillow | BSD-3-Clause / MIT-CMU | Drift regression, image I/O |
| Text | rapidfuzz | MIT | Fuzzy matching of names, terms, and quotes (grounding validator) |
| | charset-normalizer | MIT | Detecting the text encoding of old SRT files |
| | PyYAML | MIT | Bible, catalog, rule packs |
| Storage client | boto3 | Apache-2.0 | S3 API for SeaweedFS, AWS S3, and GCS |
| Structured extraction | instructor | MIT | Pydantic schemas over vLLM's API, the quote-check validator, one repair retry ([D-025](decisions.md#d-025--structured-extraction-instructor--our-quote-check-registry-ids-as-an-enum)) |
| Sensitive-entity detection | Presidio analyzer with its GLiNER recognizer; urlextract | MIT / Apache-2.0 / MIT | Phone, email, URL, plate-format, and name detection with allow-lists and deny-lists for the Clearance Scanner ([D-026](decisions.md#d-026--clearance-text-detection-presidio--gliner--urlextract)) |
| Evaluation | scipy | BSD-3-Clause | Optimal one-to-one matching of flags to labels (`linear_sum_assignment`) |
| Planning aid | hf-mem | MIT | Estimates a new catalog variant's memory from model file headers, without downloading it |

### Test oracles (tests only, never shipped)

Independent implementations that check ours ([D-030](decisions.md#d-030--test-oracles-and-copyleft-tools)):

| Oracle | License | Checks |
|--------|---------|--------|
| OpenTimelineIO, `timecode` | Apache-2.0 / MIT | Our timecode math |
| Subtitle Edit `seconv lint --json` | MIT | Our subtitle timing and readability rules |
| ffsubsync | MIT, but it pins a GPL dependency (auditok), so it runs as a command in its own environment | Our drift and offset detection |
| screenplain | MIT | Generates FDX test fixtures from Fountain |

### Deliberately not used

| Tool | Why not | Add it when |
|------|---------|-------------|
| Airflow, Dagster, Prefect, Kubeflow Pipelines | A second scheduler would compete with Ray over GPU placement; the content-hash cache already gives incremental re-runs | Runs must start from schedules or from other teams' data arriving |
| DVC | Every benchmark set regenerates exactly from manifest checksums, injector version, and seed | People start hand-editing labelled data |
| Weights & Biases, Comet | Hosted services: benchmark dialogue and frames would leave our infrastructure | — (MLflow is the self-hosted equivalent) |
| LangChain, LlamaIndex | We make direct OpenAI-compatible calls with JSON schemas; a framework adds indirection, not capability | A feature needs tool-using agents with memory |
| Ragas, DeepEval, promptfoo | Generic LLM evaluators can't score subtitle drift or clearance occurrences; our benchmark has domain labels | — |
| Loki, ELK | The Ray dashboard and Compose logs cover a two-person team | Searching logs across many nodes becomes a daily need |
| Sentry | No users outside the team yet | Editors start using the review UI |
| MLflow model and prompt registries | `catalog.yaml` and prompt files in git already version these | — |
| MkDocs | GitHub renders the Markdown docs | A hosted docs site is needed |
| Ray Data / `ray.data.llm` | Fits the offline batch workload well, but the team kept Ray Serve ([D-014](decisions.md#d-014--vllm-as-a-process-inside-ray-serve-not-ray-serve-llm)) | The scheduler or process supervisor becomes a maintenance burden |
| Ray Jobs API | With Ray Serve, GPUs belong to the model deployments, so isolating each run in a job frees nothing | — |
| Graphiti, Cognee, Apache AGE | No Postgres support / Postgres store "not production-ready" / graph queries with no notion of time | Queries need deep graph traversal |
| LangExtract, Outlines | No Pydantic schemas or repair retry / only enforces structure, which vLLM already does | — |
| llama-swap | Swaps models per request; staged mode already loads models per stage group | — |
| Refine; Streamlit, NiceGUI, Reflex, Gradio | Stalled npm releases; poor fit for frame-level video review (and Reflex's OIDC is proprietary) | — |
| CVAT, Argilla | 18-service install (kept as the fallback for labelling cuts); no longer developed | Label Studio's seeking proves too imprecise for cuts |
| pycaption, pysrt | Misreads the SMPTE time base; GPL-3.0 | — |
| PyMuPDF, decord, fastdup | AGPL-3.0; abandoned; non-commercial license | — |
| OpenALPR, nomeroff-net | AGPL-3.0 / GPL-3.0 | — |
| spaCy Spanish and French models | GPL-3.0 / LGPL-LR | — |
| DeepEval, Ragas | Our judge is one structured call; telemetry and a paid-cloud push | — |
| pooch, imagehash, mir_eval | Covered by ~25 lines of stdlib, our DINOv2 embeddings, and scipy respectively | — |

### Build notes

- **faster-whisper** runs on CTranslate2 4.8.2 wheels built for CUDA 12 + cuDNN 9. The image adds the CUDA 12 cuBLAS and cuDNN pip wheels for the ASR actor; the ≥ 580 driver runs CUDA 12 and CUDA 13 code side by side.
- **PaddleOCR** needs the PaddlePaddle GPU build alongside PyTorch in one image. If their CUDA libraries conflict, the OCR actor falls back to RapidOCR (ONNX Runtime, Apache-2.0).
- **GCS through the S3 API** requires `AWS_REQUEST_CHECKSUM_CALCULATION=when_required` and `AWS_RESPONSE_CHECKSUM_VALIDATION=when_required` (newer boto3 checksum defaults break GCS).
- **Qwen models for JSON extraction** are called with thinking disabled (`chat_template_kwargs: {enable_thinking: false}`) and a `response_format` JSON schema.
- **pgvector HNSW** indexes `vector` columns up to 2,000 dimensions; large embedders are truncated to 1,024 dimensions (Matryoshka) to stay within the limit.
- **TorchCodec 0.17** needs torch ≥ 2.11 and FFmpeg 4–9 shared libraries. Check the torch version in the vLLM image in week 1; FFmpeg comes from an LGPL shared build, never from PyAV's wheels (which bundle GPL encoders).
- **ttconv** only logs bad timing expressions (the time becomes `None`), so ingest captures its log errors and fails validation on them.
- **instructor** runs in JSON-schema mode with `max_retries=1`, and the scene text is passed as validation context to the quote check.
- **Presidio** is English-only by default: every recognizer gets `supported_languages`, organizations are un-ignored, and Spain is added to the phone regions. Its language engine uses the MIT spaCy models for en and de and tokenizer-only pipelines for es and fr; names in all four languages come from GLiNER.
- **Label Studio** projects use frame rate `23.976023976` (the string `24000/1001` is silently read as 24), and its frames are numbered from 1.

---

## Model Catalog Defaults

The planner picks from these per slot ([Hardware Adaptation](hardware-adaptation.md)). *Placement* is where the planner typically ends up using each variant; it is decided per machine, not configured. All sizes are measured checkpoint sizes.

### `text_llm` + `vlm` — Qwen (natively multimodal; one deployment can serve both slots)

| Variant id | Base model | Quant | Weights | Typical placement |
|-----------|-----------|-------|--------:|-------------------|
| `qwen3.5-4b-awq` | Qwen/Qwen3.5-4B | AWQ int4 | 4.0 GB | 8 GB GPUs (the laptop) |
| `qwen3.5-9b-awq` | Qwen/Qwen3.5-9B | AWQ int4 | 9.1 GB | 12–16 GB GPUs |
| `qwen3.5-9b-fp8` | Qwen/Qwen3.5-9B | FP8 | 13.5 GB | 16–24 GB GPUs |
| `qwen3.8-27b-int4` | Qwen/Qwen3.8-27B (RedHatAI/Qwen3.8-27B-INT4) | W4A16 | 19.5 GB | 32–48 GB GPUs; resident plans |
| `qwen3.8-27b-fp8` | Qwen/Qwen3.8-27B | FP8 | ~30 GB | ≥ 40 GB GPUs |
| `qwen3.6-35b-a3b-awq` | Qwen/Qwen3.6-35B-A3B (MoE, 3B active) | AWQ int4 | 24 GB | Throughput objective on ≥ 32 GB GPUs |
| `qwen3.5-122b-a10b-int4` | Qwen/Qwen3.5-122B-A10B (MoE, 10B active) | GPTQ int4 | 65 GB | 1–2× 80 GB |
| `qwen3.5-397b-a17b-int4` | Qwen/Qwen3.5-397B-A17B (MoE, 17B active) | int4 | 211 GB | 4× 80 GB |
| `qwen3.5-397b-a17b-fp8` | Qwen/Qwen3.5-397B-A17B | FP8 | 403 GB | 8× 80 GB |

All Apache-2.0, all supported by vLLM 0.30. Qwen3.8-27B's vision benchmarks are not yet published; `vlm` quality for the 27B variants is taken from our own benchmark, with Qwen3.6-27B as the fallback if it underperforms. FP8 runs natively on Ada/Hopper and weight-only on A100.

### `judge_llm` — different families from the agents' model

| Variant id | Base model | Quant | Weights | Typical placement |
|-----------|-----------|-------|--------:|-------------------|
| `ministral-3-3b-fp8` | mistralai/Ministral-3-3B-Instruct-2512 | FP8 | 4.7 GB | 8 GB GPUs (staged, own group) |
| `gemma-4-12b-qat` | google/gemma-4-12B-it | QAT w4a16 | 10.3 GB | ≥ 12 GB GPUs |
| `gemma-4-31b-qat` | google/gemma-4-31B-it | QAT w4a16 | 23.3 GB | ≥ 32 GB GPUs, or split over 2× 24 GB |

All Apache-2.0. When no independent variant fits, the judge reuses the `text_llm` deployment and the Plan says so.

### Other slots (Ray Serve actor deployments)

| Slot | Default variant(s) | License | Notes |
|------|--------------------|---------|-------|
| `asr` | `faster-whisper-large-v3-int8` (Systran/faster-whisper-large-v3, ~3 GB); `faster-whisper-large-v3-turbo-int8` (~1.5 GB) when VRAM is tight | MIT | Word timestamps. vLLM's Whisper support doesn't return word timestamps, so ASR stays on faster-whisper |
| `ocr` | `pp-ocrv6-medium` (PaddleOCR 3.7.0, PP-OCRv6_medium) | Apache-2.0 | One model covers Latin-script languages; low-confidence crops are re-read by the `vlm` |
| `detector` | `llmdet-base` (iSEE-Laboratory/llmdet_base); LLMDet large on big GPUs | Apache-2.0 | Text-prompted region proposals for the logo/artwork channel |
| `image_embedder` | `dinov2-large` (facebook/dinov2-large) | Apache-2.0 | Image-only features suited to same-setup similarity |
| `text_embedder` | `qwen3-embedding-0.6b` (1,024-d); `qwen3-embedding-8b` truncated to 1,024-d on big GPUs | Apache-2.0 | Multilingual scene retrieval |
| `ner` | `gliner-x-base` (knowledgator/gliner-x-base); `gliner-x-large` on big GPUs | Apache-2.0 | 22 languages incl. es/fr/de |
| `shot_detector` | `transnetv2` (TransNetV2 via transnetv2-pytorch) + PySceneDetect 0.7.1 threshold detector for fades | MIT / BSD-3-Clause | CPU or GPU |

### Candidates (benchmark before promoting)

| Candidate | Slot | Why it's interesting | Caveat |
|-----------|------|----------------------|--------|
| nvidia/canary-1b-v2 | `asr` | Lower WER on es/fr/de, word timestamps | NeMo runtime; CC-BY-4.0 (attribution) |
| Voxtral-Small-24B + Qwen3-ForcedAligner-0.6B | `asr` | Best measured es/fr/de WER | Two models; alignment in ≤ 5-minute chunks |
| microsoft/harrier-oss-v1-0.6b | `text_embedder` | Higher multilingual retrieval scores at 0.6B | Self-reported scores |
| google/owlv2-base-patch16-ensemble | `detector` | Search by example image (legal's reference logos) | Post-MVP channel |
| openai/gpt-oss-120b | `judge_llm` | Strong es/fr/de | vLLM support on A100/Ada still in progress (Hopper only) |
| google/gemma-4-31B-it | `vlm` | Independent-family VLM | Boxes are `[y1, x1, y2, x2]` on 0–1000 (the catalog's `box_format` handles it) |

---

## License Policy

`config/licenses.yaml` holds the allowlist; catalog validation rejects any variant outside it.

| Status | Licenses / items |
|--------|------------------|
| **Allowed** | Apache-2.0, MIT, BSD-2/3-Clause, PostgreSQL, CC-BY-4.0 (model weights; attribution recorded) |
| **Allowed as unmodified standalone services only** | AGPL-3.0 (Grafana) |
| **Requires legal review before use** | SAM License (facebook/sam3: gated, use restrictions); Qwen Community License (e.g. Qwen3.8-Flash-Next); NVIDIA Open Model License |
| **Rejected** | AGPL/GPL code linked into `nip` (Ultralytics YOLO-World/YOLOE, AILab-CVC YOLO-World); non-commercial licenses (jina-embeddings v3/v4, MetaCLIP 2, jina-clip-v2, urchade/gliner_multi, gliner-x v0.5, Rex-Omni, WhisperX's default es/fr/de alignment models); revenue-capped or territory-restricted licenses (Mistral Medium 3.5, Surya, Chandra-2, HunyuanOCR); Business Source License (Moondream 3); MinIO community edition (archived, no longer maintained) |

Evaluation injectors (not shipped in the product) use SAM 2 (Apache-2.0) for garment masks.

---

## Single-Node Service Layout (`compose.yaml`)

```yaml
services:
  postgres:            # pgvector image pinned to PostgreSQL 18 + pgvector 0.8.x
    image: pgvector/pgvector:<pinned pg18 tag>
    volumes: [pg-data:/var/lib/postgresql]     # PostgreSQL 18 images keep data under this path

  objectstore:         # SeaweedFS; S3 API on :8333 (not published to the host)
    image: chrislusf/seaweedfs:<pinned 4.47 tag>
    command: server -s3 -dir=/data
    volumes: [s3-data:/data]

  ray-head:            # Ray head + run controller + model deployments (GPU)
    image: nip:<release>
    command: nip runtime head
    shm_size: 8gb
    environment: [VLLM_WSL2_ENABLE_PIN_MEMORY=1, CUDA_DEVICE_ORDER=PCI_BUS_ID]
    volumes: [models:/models]
    deploy:
      resources:
        reservations:
          devices: [{driver: nvidia, count: all, capabilities: [gpu]}]
    ports: ["127.0.0.1:8265:8265"]      # Ray dashboard: localhost only, never public

  api:
    image: nip:<release>
    command: nip api
    volumes: [models:/models]            # `nip models pull` fills the shared model cache

  ui:                  # Caddy: static UI + reverse proxy for /api and /ws
    image: nip-ui:<release>
    ports: ["8080:8080"]

  keycloak:
    image: quay.io/keycloak/keycloak:<pinned>
    command: start-dev --http-port=8080
    ports: ["8180:8080"]

  prometheus:
    image: prom/prometheus:<pinned>

  grafana:
    image: grafana/grafana:<pinned>
    ports: ["127.0.0.1:3001:3000"]

  mlflow:              # experiment tracking: Postgres database `mlflow` + SeaweedFS bucket `nip-mlflow`
    image: nip-mlflow:<release>          # ghcr.io/mlflow/mlflow + psycopg2-binary + boto3 (deploy/docker/mlflow.Dockerfile)
    command: >
      mlflow server --host 0.0.0.0 --port 5000
      --backend-store-uri ${NIP_MLFLOW_BACKEND_URI}
      --artifacts-destination s3://nip-mlflow
    environment: [MLFLOW_S3_ENDPOINT_URL=http://objectstore:8333, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY]
    ports: ["127.0.0.1:5000:5000"]

  label-studio:        # hand labelling for experiments: docker compose --profile labeling up
    image: heartexlabs/label-studio:<pinned 1.23 tag>
    profiles: [labeling]
    environment:
      - DJANGO_DB=default
      - POSTGRE_HOST=postgres
      - POSTGRE_NAME=labelstudio
      - POSTGRE_USER=nip
      - POSTGRE_PASSWORD
      - SSRF_PROTECTION_ENABLED=false   # lets it read media from SeaweedFS on the Compose network
    ports: ["127.0.0.1:8081:8080"]

volumes: {pg-data: {}, s3-data: {}, models: {}}
```

MLflow gets its own small image because the official one doesn't include the Postgres driver or the S3 client.

`<pinned …>` tags are fixed in the repository's `compose.yaml` by digest; the laptop and cloud VMs use the same file. Only the UI, Keycloak, and localhost-bound dashboards are published; Postgres, object storage, and model servers are reachable only on the Compose network. In production, egress is blocked at the host or VPC level (firewall rules, or NetworkPolicy on Kubernetes), and nodes fill their model cache from the internal mirror (`NIP_MODEL_SOURCE=s3://…`) instead of the internet. On Kubernetes, the Helm chart deploys the same `nip` image as a KubeRay `RayCluster` (head + GPU worker groups) plus API and UI; Postgres and object storage are managed services there.

---

## Monitoring

### Metrics (Prometheus)

| Metric | Type | Labels |
|--------|------|--------|
| `nip_units_total` | Counter | stage, status (`done`, `cached`, `failed`) |
| `nip_unit_duration_seconds` | Histogram | stage, variant |
| `nip_queue_depth` | Gauge | slot |
| `nip_slot_replicas` | Gauge | slot, variant |
| `nip_model_load_seconds` | Histogram | variant |
| `nip_plan_amendments_total` | Counter | slot, reason |
| `nip_flags_total` | Counter | agent, check, tier |
| `nip_verification_dropped_total` | Counter | step, check |
| `nip_coverage_ratio` | Gauge | run, agent |
| `nip_gpu_memory_used_bytes` | Gauge | node, gpu |
| `nip_gpu_utilization_ratio` | Gauge | node, gpu (not available under WSL2) |
| `nip_gpu_seconds_total` | Counter | slot, variant (cost accounting) |
| `nip_cache_hits_total` | Counter | stage |

Prometheus also scrapes vLLM's own `/metrics` (queue time, tokens per second, KV-cache use) from each model replica, and Ray's built-in metrics.

### Dashboards

1. **Pipeline** — runs, stage progress, queue depth, coverage gaps.
2. **Agents** — flags per check and tier, verification drop rates, unit latency.
3. **Plans & GPUs** — current Plan per slot, replicas, model load times, amendments, GPU memory, vLLM queue time and KV-cache use, GPU-seconds per content-hour.
4. **Review** — disposition rates by action, override reasons, time to review.

### Operations vs experiments

Prometheus and Grafana answer "what is the system doing right now?". MLflow answers "how good was this configuration, and how does it compare with the last one?". Benchmark results never live in Prometheus, and live operational metrics never live in MLflow.

---

## Security

| Area | Control |
|------|---------|
| Data residency | Self-hosted models only; production nodes have no internet egress (`HF_HUB_OFFLINE=1`; weights mirrored with `nip models mirror`) |
| Network zones | Only the UI/API (behind TLS ingress) and the identity provider are reachable by users. Postgres, object storage, Ray, and model servers are on an internal network. **The Ray dashboard and job API are never exposed** — they allow arbitrary code execution |
| Authentication / authorization | OIDC bearer tokens; roles `viewer`, `reviewer`, `legal`, `operator`; clearance dispositions require `legal` ([API Contracts](api-contracts.md#roles)) |
| Audit | Append-only `audit_event` table (no `UPDATE`/`DELETE` for the application role) |
| Data at rest | Full-disk encryption on hosts (LUKS on Linux, device encryption/BitLocker on Windows); cloud-managed keys for managed Postgres, object storage, and volumes |
| Media access | Short-lived presigned URLs (≤ 15 minutes); the UI streams proxies, never masters |
| Secrets | `.env` locally (git-ignored); Kubernetes Secrets or the cloud secret manager in production |
| Supply chain | Image digests pinned; `uv.lock`; model checkpoints pinned by revision; license allowlist enforced at startup |
| Test data | Private real-brand assets for clearance injection live in a restricted bucket and are never published |
| Experiment data | MLflow traces contain pre-release dialogue, so LLM tracing is on only for benchmark runs, and MLflow is reachable only on the internal network (localhost-bound locally) |
| CI runner | The self-hosted GPU runner on the dev laptop runs only scheduled or manually started workflows on `main`, never pull requests from forks |
| Telemetry and downloads | `MLFLOW_DISABLE_TELEMETRY=true`; Presidio's domain list stays offline (`TLDEXTRACT_PUBLIC_SUFFIX_LIST_URLS=""`); `HF_HUB_OFFLINE=1` in production |
| Labelling and inspection tools | Label Studio runs with SSRF protection off so it can read internal storage, so it is reachable only on localhost or the internal network. FiftyOne runs only locally: no login, and its bundled MongoDB (SSPL) awaits legal review |
| Codec licensing | FFmpeg is our own LGPL shared build; PyAV's GPL-bundled wheels are not used |
