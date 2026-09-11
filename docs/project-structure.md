# Project Structure

## Directory Layout

```
netflix-lm/
├── README.md
├── docs/                              # All project documentation
│   ├── architecture.md
│   ├── tech-stack.md
│   ├── phased-plan.md
│   ├── data-schemas.md
│   ├── api-contracts.md
│   └── project-structure.md
│
├── docker-compose.yml                 # All services defined here
├── .env.example                       # Template for environment variables
├── .gitignore
│
├── services/                          # Docker service definitions
│   ├── api/                           # FastAPI REST API
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── routes/
│   │   │   ├── episodes.py
│   │   │   ├── flags.py
│   │   │   ├── recaps.py
│   │   │   └── knowledge_graph.py
│   │   ├── deps.py                    # Dependency injection (DB sessions, auth)
│   │   ├── models.py                  # SQL/Pydantic models
│   │   └── requirements.txt
│   │
│   ├── editorial-ui/                  # React SPA
│   │   ├── Dockerfile
│   │   ├── package.json
│   │   ├── src/
│   │   │   ├── App.tsx
│   │   │   ├── views/
│   │   │   │   ├── EpisodeList.tsx
│   │   │   │   ├── FlagDetail.tsx
│   │   │   │   ├── RecapPreview.tsx
│   │   │   │   ├── KGCorrection.tsx
│   │   │   │   └── VersionDiff.tsx
│   │   │   ├── hooks/
│   │   │   │   └── useWebSocket.ts
│   │   │   └── api/
│   │   │       └── client.ts
│   │   └── vite.config.ts
│   │
│   ├── cv-pipeline/                   # Detectron2 + DeepSORT
│   │   ├── Dockerfile
│   │   ├── detect.py                  # Object detection entrypoint
│   │   ├── track.py                   # DeepSORT tracking
│   │   ├── extract_features.py        # Keyframe feature extraction
│   │   └── requirements.txt
│   │
│   └── whisper/                       # ASR service
│       ├── Dockerfile
│       ├── transcribe.py              # Whisper Large-v3 inference
│       └── requirements.txt
│
├── pipeline/                           # Core pipeline logic
│   ├── ingestion/
│   │   ├── parsers/
│   │   │   ├── fdx_parser.py          # Final Draft .fdx
│   │   │   ├── pdf_parser.py         # PDF scripts
│   │   │   ├── fountain_parser.py    # Fountain format
│   │   │   └── subtitle_parser.py    # .srt / .vtt
│   │   ├── video/
│   │   │   ├── keyframe_extractor.py # 1fps keyframe extraction
│   │   │   └── smpte_aligner.py     # Timecode alignment engine
│   │   └── normalizer/
│   │       └── episode_document.py   # → canonical EpisodeDocument
│   │
│   ├── knowledge_graph/
│   │   ├── schema/
│   │   │   ├── entities.py           # Entity type definitions
│   │   │   └── relations.py          # Relation type definitions
│   │   ├── extraction/
│   │   │   ├── ner_model.py          # GLiNER + fine-tuned NER
│   │   │   ├── relation_model.py     # Relation extraction
│   │   │   └── confidence_scorer.py  # Extraction confidence scoring
│   │   ├── builder/
│   │   │   ├── graph_builder.py      # Construct KG from extraction results
│   │   │   └── merger.py             # Merge new extractions into existing KG
│   │   ├── constraints/
│   │   │   ├── engine.py             # Deterministic constraint checker
│   │   │   └── rules.py              # Constraint rule definitions (C-LOC-001 etc.)
│   │   ├── queries/
│   │   │   └── temporal_queries.py   # Point-in-time + range queries
│   │   └── correction/
│   │       ├── handler.py            # Human correction processing
│   │       └── feedback_loop.py      # Corrections → NER retraining data
│   │
│   ├── vector_index/
│   │   ├── chunker.py                # Scene-level chunking
│   │   ├── embedder.py               # Embedding model + index build
│   │   └── retrieval.py              # Similarity search + filtering
│   │
│   ├── agents/
│   │   ├── script_critic/
│   │   │   ├── graph_traversal.py    # Layer 1: KG queries
│   │   │   ├── rac_retrieval.py      # Layer 2: RAC context windows
│   │   │   ├── bdi_simulator.py      # Layer 3: BDI character simulation (stretch)
│   │   │   └── config.yaml           # Agent-specific prompts + thresholds
│   │   ├── continuity_inspector/
│   │   │   ├── graph_check.py        # Deterministic KG constraint check
│   │   │   ├── visual_pipeline.py   # CV detection + tracking + VLM
│   │   │   ├── contrastive_filter.py # Cheap pre-filter for VLM routing
│   │   │   └── config.yaml
│   │   └── recap_agent/
│   │       ├── base_generator.py     # Scene-level recap drafting
│   │       ├── variant_engine.py     # Tonal/thematic variants
│   │       ├── metadata_schema.py    # Structured output contract
│   │       ├── spoiler_control.py    # Reveals-Until timecode enforcement
│   │       └── config.yaml
│   │
│   ├── verification/
│   │   ├── constraint_runner.py      # Deterministic pre/post-screen
│   │   └── llm_judge.py              # LLM-as-Judge compliance layer
│   │
│   ├── report/
│   │   ├── pre_live_report.py        # Unified report generation
│   │   └── diff_report.py            # Incremental version diff report
│   │
│   └── orchestrator/
│       ├── pipeline.py               # Dagster DAG definition
│       ├── versioning.py             # Script version tracking
│       └── incremental.py            # Changed-scene-only re-processing
│
├── training/                          # Fine-tuning (MVP stretch)
│   ├── datasets/
│   │   ├── ner_annotated/            # Per-genre annotated scripts
│   │   ├── recap_corpus/            # Per-show recap training data
│   │   └── vlm_continuity/          # Labeled keyframe pairs
│   ├── finetune_ner/
│   │   ├── train.py                  # GLiNER fine-tune script
│   │   └── eval.py
│   ├── finetune_recap/
│   │   ├── train.py                  # Per-show LoRA training
│   │   └── eval.py
│   ├── finetune_vlm/
│   │   ├── train.py                  # Qwen2-VL continuity fine-tune
│   │   └── eval.py
│   └── distillation/
│       └── distill.py                # 70B → 8B model distillation
│
├── monitoring/
│   ├── prometheus.yml
│   ├── grafana/
│   │   └── dashboards/
│   │       ├── pipeline_overview.json
│   │       ├── agent_performance.json
│   │       ├── kg_health.json
│   │       └── gpu_utilization.json
│   └── alerting/
│       └── alert_rules.yml
│
├── config/
│   ├── pipeline_settings.yaml        # Confidence thresholds, model endpoints, cost limits
│   ├── show_profiles/                 # Per-show tone guides, character schemas, graph templates
│   │   ├── template_drama.yaml
│   │   ├── template_scifi.yaml
│   │   └── template_comedy.yaml
│   └── feature_flags.yaml            # MVP stretch goal toggles
│
└── scripts/
    ├── setup.sh                       # Initial setup: Docker, models, indexes
    ├── download_models.sh             # Download Llama, Qwen, Whisper weights
    ├── seed_test_data.sh              # Load test scripts with known errors
    └── run_benchmark.sh              # End-to-end performance benchmark
```

---

## Module Responsibilities

### `pipeline/ingestion/`

**Purpose**: Accept raw input files (scripts, video, subtitles) and produce a canonical `EpisodeDocument` with SMPTE-aligned timeline.

| Module | Input | Output | Key Dependencies |
|--------|-------|--------|-----------------|
| `parsers/fdx_parser.py` | .fdx file | `SceneBlock[]` | lxml |
| `parsers/pdf_parser.py` | .pdf file | `SceneBlock[]` | pdfplumber |
| `parsers/fountain_parser.py` | .fountain file | `SceneBlock[]` | Custom parser |
| `parsers/subtitle_parser.py` | .srt/.vtt | `SubtitleSegment[]` | pysrt |
| `video/keyframe_extractor.py` | .mp4 | `Keyframe[]` | OpenCV |
| `video/smpte_aligner.py` | `SceneBlock[]`, `TranscriptSegment[]`, `Keyframe[]` | `EpisodeDocument` | difflib (fuzzy match) |
| `normalizer/episode_document.py` | Aligned data | Canonical JSON | jsonschema |

### `pipeline/knowledge_graph/`

**Purpose**: Extract entities and relations from `EpisodeDocument`, build KG, run deterministic constraints, serve temporal queries.

| Module | Input | Output | Key Dependencies |
|--------|-------|--------|-----------------|
| `extraction/ner_model.py` | `EpisodeDocument` | `Entity[]` | GLiNER, transformers |
| `extraction/relation_model.py` | `EpisodeDocument`, `Entity[]` | `Relation[]` | Custom model |
| `builder/graph_builder.py` | `Entity[]`, `Relation[]` | Neo4j populated graph | neo4j-driver |
| `constraints/engine.py` | KG state | `Violation[]` | neo4j-driver (Cypher) |
| `queries/temporal_queries.py` | KG + timecode params | `EntityState[]` | neo4j-driver |
| `correction/handler.py` | Human correction | KG update | neo4j-driver |

### `pipeline/vector_index/`

**Purpose**: Chunk text, embed, store in Qdrant, serve similarity search.

| Module | Input | Output | Key Dependencies |
|--------|-------|--------|-----------------|
| `chunker.py` | `EpisodeDocument` | `Chunk[]` | — |
| `embedder.py` | `Chunk[]` | Qdrant collection | sentence-transformers |
| `retrieval.py` | Query + filters | `Chunk[]` (ranked) | qdrant-client |

### `pipeline/agents/`

**Purpose**: Three specialized agents that query KG + Qdrant and produce flags/recaps.

| Module | Input | Output | Key Dependencies |
|--------|-------|--------|-----------------|
| `script_critic/graph_traversal.py` | KG queries | `PlotHoleFlag[]` | neo4j-driver |
| `script_critic/rac_retrieval.py` | RAC search + KG context | `PlotHoleFlag[]` | qdrant-client, vLLM API |
| `script_critic/bdi_simulator.py` | Character models + script | `PlotHoleFlag[]` | Custom BDI framework |
| `continuity_inspector/graph_check.py` | KG constraint results | `ContinuityFlag[]` | neo4j-driver |
| `continuity_inspector/visual_pipeline.py` | Keyframes + CV results | `ContinuityFlag[]` | vLLM API (VLM) |
| `continuity_inspector/contrastive_filter.py` | Keyframe embeddings | Flagged pairs | sentence-transformers |
| `recap_agent/base_generator.py` | KG scene nodes | Base recap text | vLLM API |
| `recap_agent/variant_engine.py` | Base recap + tone config | Variant recaps | vLLM API |
| `recap_agent/metadata_schema.py` | Recap + analysis | `RecapOutput` | — |
| `recap_agent/spoiler_control.py` | KG reveals-Until + recap | Spoiler-rated recap | neo4j-driver |

### `pipeline/verification/`

**Purpose**: Two-path verification before human review.

| Module | Input | Output | Key Dependencies |
|--------|-------|--------|-----------------|
| `constraint_runner.py` | Agent outputs + KG | Verified/flagged outputs | neo4j-driver |
| `llm_judge.py` | Agent outputs + KG state | Compliance report | vLLM API (8B) |

### `pipeline/report/`

**Purpose**: Merge all agent outputs into prioritized Pre-Live Report.

| Module | Input | Output | Key Dependencies |
|--------|-------|--------|-----------------|
| `pre_live_report.py` | `Flag[]` + `RecapOutput[]` | Pre-Live Report JSON | — |
| `diff_report.py` | Old + new report | Incremental diff | — |

---

## Docker Compose Service Map

| Service | Source | Port(s) | GPU | Description |
|---------|--------|---------|-----|-------------|
| `vllm-llama70b` | Pre-built image | 8000 | 2x A100 | Primary LLM |
| `vllm-qwen2vl` | Pre-built image | 8001 | 2x A100 | VLM |
| `vllm-llama8b` | Pre-built image | 8002 | 1x A100 | Judge + distilled tasks |
| `neo4j` | Pre-built image | 7474, 7687 | None | Knowledge graph |
| `qdrant` | Pre-built image | 6333 | None | Vector index |
| `minio` | Pre-built image | 9000, 9001 | None | Object storage |
| `cv-pipeline` | `services/cv-pipeline/` | — | 1x A100 | Object detection |
| `whisper` | `services/whisper/` | — | 1x A100 | ASR (batch) |
| `dagster-webserver` | Pre-built image | 3000 | None | Orchestration UI |
| `dagster-daemon` | Pre-built image | — | None | Orchestration runner |
| `api` | `services/api/` | 8080 | None | REST API |
| `editorial-ui` | `services/editorial-ui/` | 80 | None | Editorial dashboard |
| `prometheus` | Pre-built image | 9090 | None | Metrics |
| `grafana` | Pre-built image | 3001 | None | Dashboards |
| `keycloak` | Pre-built image | 8443 | None | OIDC auth |

**Total GPUs: 8x A100 (production) or 4x RTX 4090 (MVP)**

---

## Dev Setup

### Prerequisites

- Docker Engine 24+
- Docker Compose v2+
- NVIDIA Container Toolkit
- NVIDIA Driver 535+
- 8x A100 80GB (production) or 4x RTX 4090 24GB (MVP)
- 256GB RAM
- 2TB NVMe SSD

### First-Time Setup

```bash
# 1. Clone and configure
git clone <repo-url> netflix-lm
cd netflix-lm
cp .env.example .env
# Edit .env: set NEO4J_PASSWORD, MINIO_USER, MINIO_PASSWORD, KEYCLOAK credentials

# 2. Download model weights (requires HF access tokens)
./scripts/download_models.sh
# Downloads: Llama-3.1-70B-Instruct-AWQ, Qwen2-VL-72B-Instruct-AWQ,
#            Llama-3.1-8B-Instruct, Whisper Large-v3, GLiNER base,
#            BAAI/bge-large-en-v1.5

# 3. Start all services
docker compose up -d

# 4. Wait for health checks
docker compose ps  # All services should show "healthy"

# 5. Seed test data (5 scripts with known errors)
./scripts/seed_test_data.sh

# 6. Run first pipeline
curl -X POST http://localhost:8080/api/v1/episodes \
  -H "Authorization: Bearer $(cat .test_token)" \
  -H "Content-Type: application/json" \
  -d '{"show_id":"test-drama","season":1,"episode":1,"script_file":"s1e1_draft01.fdx"}'

# 7. Verify
# - Dagster UI: http://localhost:3000
# - Editorial UI: http://localhost:80
# - Grafana: http://localhost:3001
# - MinIO Console: http://localhost:9001
# - Neo4j Browser: http://localhost:7474
```

### Running Tests

```bash
# Unit tests (no GPU required)
docker compose run api pytest pipeline/ -v

# Integration tests (requires GPU)
docker compose run api pytest tests/integration/ -v

# End-to-end benchmark
./scripts/run_benchmark.sh
```

### Environment Variables

```bash
# .env.example

# LLM Model Paths (local weights)
LLAMA_70B_MODEL_PATH=/models/Llama-3.1-70B-Instruct-AWQ
QWEN2VL_MODEL_PATH=/models/Qwen2-VL-72B-Instruct-AWQ
LLAMA_8B_MODEL_PATH=/models/Llama-3.1-8B-Instruct

# Infrastructure
NEO4J_PASSWORD=change_me
MINIO_USER=minioadmin
MINIO_PASSWORD=change_me

# Auth
KEYCLOAK_ADMIN=admin
KEYCLOAK_PASSWORD=change_me

# Feature Flags
ENABLE_BDI_SIMULATION=false
ENABLE_PER_SHOW_LORA=false
ENABLE_VLM_CONTINUITY_FT=false

# Pipeline Settings
NER_CONFIDENCE_THRESHOLD=0.95
FLAG_AUTO_ESCALATE_THRESHOLD=0.90
FLAG_REVIEW_RECOMMENDED_THRESHOLD=0.70
SPOILER_RISK_BLOCK_THRESHOLD=0.40
VLM_CONTINUITY_PRECISION_FLOOR=0.75
CONTRASTIVE_ANOMALY_THRESHOLD=0.85
```
