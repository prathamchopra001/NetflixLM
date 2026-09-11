# Tech Stack

## Design Principle

All models run locally. No data leaves your machines. No external API calls. Every component is self-hosted via Docker Compose.

---

## Full Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Primary Text LLM** | Llama 3.1 70B (4-bit AWQ) via vLLM | Best open-weight reasoning model that fits in 2x A100. AWQ quantization preserves >95% quality. |
| **Vision-Language Model** | Qwen2-VL 72B via vLLM | Best open-weight VLM. Continuity-specific fine-tune required. |
| **Distilled LLM (scale)** | Llama 3.1 8B (per-show LoRA) via vLLM | After validation, distill recap/NER to 8B for 10x cost reduction on high-volume shows. **MVP stretch goal.** |
| **LLM-as-Judge** | Llama 3.1 8B Instruct | Fast, cheap, sufficient for KG-faithfulness checks. |
| **Knowledge Graph** | Neo4j Community Edition (Docker) | Production graph DB. Time-versioned properties via relationship attributes. ~5ms query latency. |
| **Vector Index** | Qdrant (Docker) | Rust-native, low latency, simple to operate. |
| **ASR** | Whisper Large-v3 (faster-whisper, CTranslate2) | Optimized inference. Timestamped output. 100+ languages. |
| **CV Pipeline** | Detectron2 + DeepSORT (Docker) | Object detection + persistent tracking across keyframes. |
| **NER + Relation Extraction** | GLiNER (base) + custom fine-tuned relation model | Zero-shot baseline; per-genre fine-tune for >95% accuracy. |
| **Orchestration** | Dagster (Docker) | Data/AI-native orchestration. Python-native. Built-in observability, versioning, retry. |
| **Object Storage** | MinIO (Docker, S3-compatible) | Drop-in S3 API. Can migrate to real S3 later with zero code changes. |
| **Fine-Tuning** | Axolotl (LoRA/QLoRA) | Production-grade fine-tuning framework. Supports Llama, Qwen. **MVP stretch goal for per-show LoRA.** |
| **API** | FastAPI (Docker) | REST endpoints for editorial UI and integrations. |
| **Editorial UI** | React SPA (Docker, served via Caddy) | Static hosting + reverse proxy. No CloudFront needed on local network. |
| **Monitoring** | Prometheus + Grafana (Docker) | Standard observability. Custom metrics: latency/agent, cost/episode, accuracy. |
| **Security** | Disk encryption (LUKS) + Keycloak (OIDC) + network isolation | No internet egress. All traffic internal. |
| **IaC** | Docker Compose (v1) → Kubernetes (v2) | Start simple (single node). Migrate to K8s when scaling beyond one machine. |

---

## Hardware Requirements

### Production Configuration (8x A100 80GB)

| Component | GPU Allocation | Model | Serving |
|-----------|---------------|-------|---------|
| Text LLM (Llama 3.1 70B) | 2x A100 80GB | 4-bit AWQ | vLLM |
| VLM (Qwen2-VL 72B) | 2x A100 80GB | 4-bit AWQ | vLLM |
| CV Pipeline (Detectron2 + DeepSORT) | 1x A100 | Batch processing | Docker |
| Whisper Large-v3 | 1x A100 | Batch processing | faster-whisper |
| Fine-Tuning (Axolotl) | 4x A100 | LoRA/QLoRA | Periodic, not continuous |
| BDI Simulation | CPU-only | Python | Lightweight |
| NER + Relation Extraction | 1x A100 | GLiNER + custom | Batch processing |

**Total: 8x A100 80GB**

### Minimal MVP Configuration (4x RTX 4090 24GB)

| Component | GPU Allocation | Model | Notes |
|-----------|---------------|-------|-------|
| Text LLM (Llama 3.1 70B) | 2x RTX 4090 | 4-bit AWQ, limited KV cache | Reduced max context length |
| VLM (Qwen2-VL 7B) | 1x RTX 4090 | Downgraded from 72B | Significantly weaker visual reasoning |
| CV Pipeline + Whisper + NER | 1x RTX 4090 | Sequential batch | All 3 share one GPU, run sequentially |
| Fine-Tuning | Not available | — | Cannot fine-tune on this config |
| LLM-as-Judge | Same as Text LLM | Shared inference | Sequential, not parallel |

**Total: 4x RTX 4090 24GB**

**MVP compromises**:
- VLM downgraded to Qwen2-VL 7B — visual continuity detection will have lower recall and precision
- No parallel agent execution — all inference runs sequentially through vLLM
- No fine-tuning — all agents use prompted-only approaches
- Reduced context windows — may miss long-range cross-episode references

---

## Per-Episode Cost Estimate (Self-Hosted)

| Component | Est. GPU-Hours/Episode | Notes |
|-----------|------------------------|-------|
| Script parsing + NER | 0.1 | Lightweight |
| KG construction + constraints | 0.05 | Mostly CPU |
| Vector indexing | 0.05 | Mostly CPU |
| Script Critic (Layers 1+2) | 0.2 | KG queries + LLM inference |
| Continuity Inspector | 0.8 | VLM is the expensive step |
| Recap Agent (1 base + 4 variants) | 0.15 | Multiple LLM calls |
| LLM-as-Judge | 0.1 | Smaller model |
| Dagster orchestration | 0.02 | Negligible |
| **Total GPU-hours/episode** | **~1.5** | |

At ~500 episodes/month: ~750 GPU-hours/month. On 8x A100 (available 720 hrs/mo each): 1 A100 dedicated is sufficient.

---

## Docker Compose Service Layout

```yaml
services:
  # === LLM Inference ===
  vllm-llama70b:
    image: vllm/vllm-openai:latest
    runtime: nvidia
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
              count: 2
    command: >
      --model meta-llama/Llama-3.1-70B-Instruct-AWQ
      --quantization awq
      --max-model-len 32768
      --port 8000

  vllm-qwen2vl:
    image: vllm/vllm-openai:latest
    runtime: nvidia
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
              count: 2
    command: >
      --model Qwen/Qwen2-VL-72B-Instruct-AWQ
      --quantization awq
      --limit-mm-per-prompt image=5
      --port 8001

  vllm-llama8b:
    image: vllm/vllm-openai:latest
    runtime: nvidia
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
              count: 1
    command: >
      --model meta-llama/Llama-3.1-8B-Instruct
      --port 8002

  # === Data Stores ===
  neo4j:
    image: neo4j:5-community
    ports: ["7474:7474", "7687:7687"]
    volumes: ["neo4j-data:/data"]
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}

  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes: ["qdrant-data:/storage"]

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]
    volumes: ["minio-data:/data"]
    environment:
      MINIO_ROOT_USER: ${MINIO_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_PASSWORD}

  # === CV Pipeline ===
  cv-pipeline:
    build: ./services/cv-pipeline
    runtime: nvidia
    volumes: ["minio-data:/data:ro"]
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
              count: 1

  # === ASR ===
  whisper:
    build: ./services/whisper
    runtime: nvidia
    volumes: ["minio-data:/data:ro"]
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
              count: 1

  # === Orchestration ===
  dagster-webserver:
    image: dagster/dagster-webserver:latest
    ports: ["3000:3000"]
    depends_on: [dagster-daemon]

  dagster-daemon:
    image: dagster/dagster-daemon:latest
    depends_on: [neo4j, qdrant, minio, vllm-llama70b, vllm-qwen2vl, vllm-llama8b]

  # === API + UI ===
  api:
    build: ./services/api
    ports: ["8080:8080"]
    depends_on: [neo4j, qdrant, minio, dagster-webserver]

  editorial-ui:
    build: ./services/editorial-ui
    ports: ["80:80"]
    depends_on: [api]

  # === Monitoring ===
  prometheus:
    image: prom/prometheus:latest
    volumes: ["./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml"]
    ports: ["9090:9090"]

  grafana:
    image: grafana/grafana:latest
    ports: ["3001:3000"]
    volumes: ["grafana-data:/var/lib/grafana"]

  # === Auth ===
  keycloak:
    image: quay.io/keycloak/keycloak:latest
    command: start-dev
    ports: ["8443:8080"]
    environment:
      KC_DB: postgres
      KEYCLOAK_ADMIN: ${KEYCLOAK_ADMIN}
      KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_PASSWORD}

volumes:
  neo4j-data:
  qdrant-data:
  minio-data:
  grafana-data:
```

---

## Monitoring Stack

### Custom Metrics (via Prometheus)

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `nip_agent_latency_seconds` | Histogram | agent, layer | End-to-end latency per agent |
| `nip_agent_flags_total` | Counter | agent, severity, confidence_bucket | Flags produced by each agent |
| `nip_kg_nodes_total` | Gauge | entity_type | Total nodes in knowledge graph |
| `nip_kg_constraints_violated_total` | Counter | constraint_type | Deterministic violations caught |
| `nip_recap_spoiler_risk_score` | Histogram | tone_variant | Spoiler risk distribution |
| `nip_episode_processing_duration_seconds` | Histogram | show, season | Full pipeline duration per episode |
| `nip_human_disposition_total` | Counter | action (accept/fix/override) | Human review outcomes |
| `nip_gpu_utilization_percent` | Gauge | gpu_id | GPU utilization per device |

### Grafana Dashboards

1. **Pipeline Overview** — episodes processed, active runs, queue depth
2. **Agent Performance** — latency, flag counts, confidence distributions
3. **KG Health** — node count, constraint violations, extraction accuracy
4. **GPU Utilization** — per-device usage, memory, temperature
5. **Human Review** — disposition rates, override reasons, review latency

---

## Security Architecture

```
┌─────────────────────────────────────────────────────────┐
│  LOCAL NETWORK (no internet egress)                     │
│                                                         │
│  ┌──────────────────┐  ┌──────────────────────────────┐│
│  │  Frontend Zone   │  │  Backend Zone                ││
│  │                  │  │                              ││
│  │  - Editorial UI  │  │  - Neo4j (port 7687)        ││
│  │  - Grafana       │  │  - Qdrant (port 6333)       ││
│  │                  │  │  - MinIO (port 9000)        ││
│  │                  │  │  - vLLM servers (8000-8002) ││
│  │                  │  │  - CV/Whisper services       ││
│  │                  │  │  - Dagster (port 3000)      ││
│  └──────────────────┘  └──────────────────────────────┘│
│                                                         │
│  ── Keycloak: OIDC auth for all HTTP endpoints         │
│  ── LUKS: full-disk encryption on all storage         │
│  ── Docker network: isolated bridge, no host network   │
│  ── No internet egress from any container              │
└─────────────────────────────────────────────────────────┘
```

**Key rules**:
- All traffic stays within local network
- Keycloak OIDC required for API UI access
- LUKS full-disk encryption on all volumes
- Docker bridge network isolation — no `network_mode: host`
- MinIO / Neo4j / Qdrant not exposed to host (internal only)
- All API keys stored in `.env` (git-ignored), never committed

---

## Fine-Tuning Strategy (MVP Stretch)

### Per-Genre NER + Relation Extraction

| Genre | Training Data | Target |
|-------|-------------|--------|
| Drama | 50 annotated scripts | >95% entity extraction, >90% relation accuracy |
| Sci-Fi | 30 annotated scripts | >95% entity extraction, handles fictional terminology |
| Comedy | 30 annotated scripts | >95% entity extraction, handles gag/continuity-break patterns |

**Framework**: Axolotl with LoRA/QLoRA on GLiNER base model.

### Per-Show Recap LoRA

| Show Type | Training Data | Tuning Method |
|-----------|-------------|---------------|
| Marquee title | 2-3 seasons of prior recaps + brand style guide | LoRA on Llama 3.1 8B, rank 16, 3 epochs |
| Standard title | Netflix-wide recap corpus | Prompted-only (no fine-tune) |

**Framework**: Axolotl. Training runs on dedicated fine-tune GPU cluster (4x A100). Not continuous — triggered when new recap corpus is available.

### VLM Continuity Fine-Tune

**Training data**: Synthetic examples of prop swaps, wardrobe changes, wound persistence. ~500 labeled keyframe pairs.

**Target**: Improve visual continuity flagging precision from ~0.65 (base Qwen2-VL) to ~0.85 on continuity-specific cases.
