# Decision Log

Every significant choice in the project, recorded when it was made: what we considered, what we chose, why, and what it cost. Entries are never deleted; a reversed decision is marked **Superseded** and links to the entry that replaced it.

Decisions that a measurement should confirm link to a planned experiment in [experiments.md](experiments.md). Day-to-day events are in [journal.md](journal.md).

## Index

| ID | Date | Decision | Status |
|----|------|----------|--------|
| [D-001](#d-001--replace-the-recap-agent-with-two-qa-agents) | 2026-09-27 | Replace the Recap Agent with the Localization Auditor and Clearance Scanner | Accepted |
| [D-002](#d-002--hardware-adaptive-runtime-ray--our-own-planner) | 2026-09-27 | Hardware-adaptive runtime: Ray + our own planner | Accepted |
| [D-003](#d-003--postgres--pgvector-instead-of-neo4j--qdrant) | 2026-09-27 | Postgres + pgvector instead of Neo4j + Qdrant | Accepted |
| [D-004](#d-004--no-orchestrator-incremental-re-runs-from-a-content-hash-cache) | 2026-09-27 | No orchestrator; incremental re-runs from a content-hash cache | Accepted (reaffirmed 2026-10-06) |
| [D-005](#d-005--no-output-without-evidence-verification-only-subtracts) | 2026-09-27 | No output without evidence; verification only subtracts | Accepted |
| [D-006](#d-006--two-orderings-screen-order-and-story-order) | 2026-09-27 | Two orderings: screen order and story order | Accepted |
| [D-007](#d-007--script-estimate-mode) | 2026-09-27 | Script-estimate mode so everything runs before picture exists | Accepted |
| [D-008](#d-008--judge-from-a-different-model-family) | 2026-09-27 | Judge from a different model family when hardware allows | Accepted — to validate ([EXP-013](experiments.md#exp-013--judge-same-family-vs-different-family)) |
| [D-009](#d-009--clearance-excludes-face-recognition-and-music) | 2026-09-27 | Clearance excludes face recognition and music | Accepted |
| [D-010](#d-010--continuity-compares-same-setup-shots-not-adjacent-shots) | 2026-09-27 | Continuity compares same-setup shots, not adjacent shots | Accepted — to validate ([EXP-009](experiments.md#exp-009--continuity-pre-filter-adjacent-shots-vs-same-setup-shots)) |
| [D-011](#d-011--mvp-languages-and-what-formality-checks-mean) | 2026-09-27 | MVP languages es/fr/de; formality checks consistency, not correctness | Accepted |
| [D-012](#d-012--test-corpus-open-films--public-domain-episodes--injected-errors) | 2026-09-27 | Test corpus: open films + public-domain episodes + injected errors | Accepted |
| [D-013](#d-013--seaweedfs-instead-of-minio) | 2026-09-27 | SeaweedFS instead of MinIO | Accepted |
| [D-014](#d-014--vllm-as-a-process-inside-ray-serve-not-ray-serve-llm) | 2026-09-27 | vLLM as a process inside Ray Serve, not Ray Serve LLM | Accepted (reaffirmed 2026-10-06 over Ray Data) |
| [D-015](#d-015--one-multimodal-model-for-text-and-vision-on-small-gpus) | 2026-09-27 | One multimodal model for text and vision on small GPUs | Accepted — to validate ([EXP-005](experiments.md#exp-005--fact-extraction-context-8k-vs-32k-tokens)) |
| [D-016](#d-016--license-allowlist-enforced-at-startup) | 2026-09-27 | License allowlist enforced at startup | Accepted |
| [D-017](#d-017--scene-index-embeds-scene-text-only) | 2026-09-27 | Scene index embeds scene text only | Accepted |
| [D-018](#d-018--dinov2-for-camera-setup-similarity) | 2026-09-27 | DINOv2 for camera-setup similarity | Accepted — to validate ([EXP-010](experiments.md#exp-010--setup-clustering-dinov2-vs-siglip-2)) |
| [D-019](#d-019--oidc-everywhere-with-separate-issuer-and-key-urls) | 2026-09-27 | OIDC everywhere, with separate issuer and key URLs | Accepted |
| [D-020](#d-020--cpu-profile-with-recorded-model-outputs-for-ci) | 2026-09-27 | `cpu` profile with recorded model outputs for CI | Accepted |
| [D-021](#d-021--language-rule-packs-resolve-by-tag-fallback) | 2026-09-27 | Language rule packs resolve by tag fallback | Accepted |
| [D-022](#d-022--self-hosted-mlflow-for-experiments-no-dag-tool-no-hosted-trackers) | 2026-10-06 | Self-hosted MLflow for experiments; no DAG tool; no hosted trackers | Accepted |
| [D-023](#d-023--run-queue-pgqueuer-no-ray-jobs) | 2026-10-06 | Run queue: pgqueuer; no Ray Jobs | Accepted |
| [D-024](#d-024--cloud-provisioning-skypilot) | 2026-10-06 | Cloud provisioning: SkyPilot | Accepted |
| [D-025](#d-025--structured-extraction-instructor--our-quote-check-registry-ids-as-an-enum) | 2026-10-06 | Structured extraction: instructor + our quote check; registry IDs as an enum | Accepted — to validate ([EXP-020](experiments.md#exp-020--entity-resolution-enum-constrained-ids-vs-fuzzy-matching-afterwards)) |
| [D-026](#d-026--clearance-text-detection-presidio--gliner--urlextract) | 2026-10-06 | Clearance text detection: Presidio + GLiNER + urlextract | Accepted — plates to validate ([EXP-019](experiments.md#exp-019--license-plates-ocr--format-rules-vs-a-dedicated-plate-reader)) |
| [D-027](#d-027--parsing-and-decoding-libraries-and-what-stays-custom) | 2026-10-06 | Parsing and decoding libraries, and what stays custom | Accepted |
| [D-028](#d-028--labelling-and-inspection-label-studio--fiftyone) | 2026-10-06 | Labelling and inspection: Label Studio + FiftyOne | Accepted |
| [D-029](#d-029--review-ui-react-admin--ra-keycloak) | 2026-10-06 | Review UI: React-admin + ra-keycloak | Accepted |
| [D-030](#d-030--test-oracles-and-copyleft-tools) | 2026-10-06 | Test oracles and copyleft tools | Accepted |

---

## D-001 · Replace the Recap Agent with two QA agents

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Product scope

**Context.** The original first use case generated episode recaps. Reviewing it showed four problems:
- Any LLM can summarize an episode, so it was not differentiated.
- It used none of the project's strengths: the frame-accurate timeline, the knowledge layer, the video pipeline.
- It had no objective ground truth, so quality could only be rated subjectively.
- It sat awkwardly in a pipeline whose other agents find errors; the old design even blocked recaps until plot holes were resolved.

**Options considered.**
1. Keep the Recap Agent.
2. Dependency-aware "Previously On" generation (which past facts does episode N depend on?). Proposed and rejected: still a generation feature.
3. Localization QA: subtitle and dub checks against the knowledge layer.
4. Spoiler-safe marketing QA: trailers and artwork checked against reveal timecodes.
5. Ratings and compliance tagging: timecoded content descriptors per country.
6. On-screen clearance: logos, trademarks, phone numbers, and real names needing legal clearance.

**Decision.** Options 3 and 6 together, as the Localization Auditor and the Clearance Scanner.

**Why.** All four agents now do the same kind of job, finding problems before release, which makes one coherent product. Both new agents address real, expensive manual work. Both can be scored objectively against planted errors. Localization exercises the knowledge layer heavily (gender, relationships, reveal points); clearance exercises the video pipeline.

**Cost / trade-off.** Four agents instead of three, in the same eight weeks. Subtitle tracks and the clearance log become required inputs for those agents. Dubbed-audio checks were pushed past the MVP to keep scope.

**Revisit if.** Clearance detection quality on logos stays far below target after Phase 3 ([evaluation targets](evaluation.md#mvp-targets)).

---

## D-002 · Hardware-adaptive runtime: Ray + our own planner

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Runtime

**Context.** The system must run unchanged on whatever hardware it's given: an 8 GB laptop GPU for development, and a cloud cluster at full capacity in production, with no code or config edits in between.

**Options considered.**
1. **Ray + planner.** Ray discovers resources, places work, and autoscales; our planner picks model sizes and copy counts per GPU.
2. **Job queue + workers + Kubernetes autoscaling (KEDA).** Simple parts, but we would write placement and multi-GPU logic ourselves and keep two deployment stacks (Compose and Kubernetes) in sync.
3. **Kubernetes everywhere (k3s on the laptop).** Identical manifests, but heavy on Windows/WSL2, and Kubernetes allocates whole GPUs, so it cannot load and unload models on one 8 GB card.

**Decision.** Option 1. The planner is a pure function of (hardware, catalog, workload, objective), defaulting to the `quality` objective, and every run stores its Plan.

**Why.** It is the only option where "same code at full capacity on any hardware" comes built in. A pure planner can be tested against simulated machines we don't own.

**Cost / trade-off.** Ray is one more system to learn, and on Windows it must run inside Linux containers. Quality is not constant across hardware: smaller GPUs get smaller models, so results must be reported per Plan.

**Revisit if.** Ray's scheduling overhead dominates small runs, or the planner's choices diverge from measured best configurations.

---

## D-003 · Postgres + pgvector instead of Neo4j + Qdrant

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Data

**Context.** The old design used Neo4j for the knowledge graph and Qdrant for vectors, and would still have needed a relational store for flags, reviews, and audit.

**Options considered.** Keep Neo4j + Qdrant (+ Postgres), or one Postgres with the `pgvector` and `btree_gist` extensions (Apache AGE available if Cypher is ever needed).

**Decision.** One Postgres.

**Why.**
- The core checks are about overlapping time ranges ("in two places during overlapping frames", "mentions a secret before learning it"), which Postgres range types with GiST indexes answer directly.
- The few multi-step questions are short chains that recursive SQL handles.
- A season is a few thousand scene vectors, well within pgvector's range.
- One transactional store holds facts, flags, reviews, audit, and the cache index.
- Managed Postgres with pgvector exists on every major cloud: AWS RDS and Aurora (pgvector 0.8.2), Google Cloud SQL (0.8.5), AlloyDB, and Azure Flexible Server (0.8.2), as checked 2026-09-27.

**Cost / trade-off.** No Cypher and no built-in graph visualization. We design to pgvector 0.8.2, the oldest version among the managed clouds. HNSW indexes cap `vector` columns at 2,000 dimensions, so large embedders are truncated to 1,024.

**Revisit if.** Queries start needing deep, variable-length graph traversal.

---

## D-004 · No orchestrator; incremental re-runs from a content-hash cache

**Date:** 2026-09-27, reaffirmed 2026-10-06 · **Status:** Accepted · **Area:** Runtime

**Context.** The old design used Dagster for orchestration and incremental re-processing.

**Options considered.** Dagster (or Airflow/Prefect) on top of Ray; or the stage-group order inside our own controller on Ray, plus a cache.

**Decision.** No separate orchestrator. Every work unit's output is cached under a hash of its stage version, model variant, prompt version, parameters, and **the exact inputs it read**.

**Why.** A second scheduler would compete with Ray over GPU placement. Hashing what each unit actually read gives incremental re-runs for free: edit scene 5 and only the units that read scene 5's facts run again.

**Cost / trade-off.** No orchestrator UI. Run progress is visible in the Ray dashboard and our run view instead.

**Revisit if.** Runs must be triggered by schedules or by other teams' data arriving.

---

## D-005 · No output without evidence; verification only subtracts

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Trust

**Context.** LLM outputs can be confidently wrong, and the old design risked circular trust: an LLM checking an LLM's claims against facts an LLM extracted.

**Decision.**
- Every fact must quote the line it came from; a deterministic validator drops facts whose quote isn't in the text.
- Every flag must cite timeline objects that exist; flags with unresolvable evidence are dropped.
- Verification can only drop, downgrade, or merge flags, never create them.

**Why.** It turns hallucination into something a program can detect. A reviewer can trust that every flag shown has checkable evidence.

**Cost / trade-off.** Some true findings without a quotable source are lost. The grounding threshold is tuned by [EXP-006](experiments.md#exp-006--grounding-validator-threshold).

---

## D-006 · Two orderings: screen order and story order

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Knowledge layer

**Context.** Flashbacks and intercuts mean the order scenes appear on screen is not the order events happen in the story.

**Decision.** Every scene has a screen position, plus a story position (`story_seq`) and a story day. Each check uses the right one:
- Plot logic uses story order.
- Spoiler checks use screen order (what the viewer has seen).
- Continuity uses story days.

**Why.** Without this, a flashback looks like a dead character acting, and a reveal in a flashback is placed at the wrong point for spoiler checks.

**Cost / trade-off.** Story order must be derived from scene headings and transitions, which is error-prone; flags that depend on an inferred position get reduced confidence. Rules-only vs rules + LLM derivation is [EXP-007](experiments.md#exp-007--story-order-rules-only-vs-rules--llm).

---

## D-007 · Script-estimate mode

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Timeline

**Decision.** Without picture, scenes get estimated frame ranges from script order and page length (industry rule of thumb: one page ≈ one minute, at 24 fps). When picture arrives, alignment replaces the estimates.

**Why.** The Script Critic is most valuable before shooting, when fixes are cheap. One code path serves both cases, so nothing branches on "do we have video yet?".

**Cost / trade-off.** Evidence before picture shows scene references instead of real timecodes.

---

## D-008 · Judge from a different model family

**Date:** 2026-09-27 · **Status:** Accepted — to validate · **Area:** Verification

**Context.** A judge from the same model family as the agents tends to share their blind spots.

**Decision.** The planner prefers a judge from a different family whenever one fits; otherwise the judge reuses the agents' model with a fresh context, and the Plan records `judge_independent: false`. Concrete choices from the 2026-09-27 model research:
- Ministral-3-3B FP8 (4.7 GB) for 8 GB GPUs.
- Gemma 4 12B and 31B for larger GPUs (Gemma 4 moved to the Apache-2.0 license).

**Why.** Independent errors are what make a second opinion worth having.

**Cost / trade-off.** On the laptop the independent judge is a small 3B model; a weaker judge could drop true findings. [EXP-013](experiments.md#exp-013--judge-same-family-vs-different-family) measures this trade-off.

---

## D-009 · Clearance excludes face recognition and music

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Clearance scope

**Decision.** The Clearance Scanner does not identify real people by face and does not check music.

**Why.** Face recognition of real people is a privacy and legal risk in itself. Music clearance needs an audio-fingerprint reference database we don't have.

**Cost / trade-off.** Recognizable real people in the background and uncleared music remain manual review items.

---

## D-010 · Continuity compares same-setup shots, not adjacent shots

**Date:** 2026-09-27 · **Status:** Accepted — to validate · **Area:** Continuity

**Context.** The old design ran its cheap pre-filter on **adjacent** keyframes, flagging pairs with unusual embedding distance before calling the expensive vision model.

**Problem found during design.** In normal editing, adjacent shots are *supposed* to differ (a wide shot, then a close-up), so an adjacent-shot filter would flag nearly every cut.

**Decision.** Cluster each scene's shots by camera setup and compare shots *within* a setup (the return to the wide shot, each side of a shot/reverse-shot), where the frames should look alike and differences are real anomalies.

**Why.** It targets exactly where continuity errors become visible, and should send far fewer pairs to the vision model.

**Cost / trade-off.** It depends on clustering setups correctly. [EXP-009](experiments.md#exp-009--continuity-pre-filter-adjacent-shots-vs-same-setup-shots) compares the two pre-filters on the benchmark.

---

## D-011 · MVP languages and what formality checks mean

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Localization

**Decision.** MVP target languages are Spanish, French, and German, which between them cover every check type. Language behavior lives in rule packs (config, not code).

**Formality.** The Netflix style guides ask translators to match the original's register rather than prescribing tú/usted, tu/vous, or du/Sie. So `loc.formality` checks **consistency against the relationship timeline**, not "correctness".

**Rule pack values** are taken from the Netflix Timed Text Style Guide (checked 2026-09-27): 42 characters per line; reading speed 20 characters/second (English, adult) or 17 (es/fr/de, adult); at most 2 lines; 5/6 s minimum and 7 s maximum duration; 2-frame minimum gap.

**Cost / trade-off.** Non-Latin scripts and dubbed audio are post-MVP.

---

## D-012 · Test corpus: open films + public-domain episodes + injected errors

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Evaluation

**Context.** Real Netflix material is unavailable, and every check needs ground truth.

**Options considered.** Open films with injected errors; real material we don't have; fully synthetic content; text-only first.

**Decision.** Open films with injected errors. These findings from the license research shaped the corpus:
- Only **Sintel** and **Tears of Steel** have official Spanish, French, and German subtitles.
- **Agent 327** is CC BY-ND, and every injected copy is a derivative, so it is excluded.
- **The Beverly Hillbillies** season 1 (36 public-domain episodes) gives real multi-episode content for cross-episode checks; its theme song is still copyrighted and is stripped from derived media.
- *The Andy Griffith Show* "public-domain" episodes are avoided because a court treated them as derivatives of copyrighted episodes. *Pioneer One* is non-commercial only and is excluded.
- Public-domain status is US-only.

**Why.** Every planted error is a known answer, so precision and recall are measurable from week 3.

**Cost / trade-off.** Titles without scripts or official subtitles need derived assets (transcription plus human correction), which is extra work in Phase 2.

---

## D-013 · SeaweedFS instead of MinIO

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Storage

**Context.** The first draft used MinIO for local S3-compatible storage. The 2026-09-27 research found:
- The community edition lost its admin console in mid-2025.
- It stopped publishing binaries and images in October 2025.
- It entered maintenance mode in December 2025.
- Its GitHub repository was archived as no longer maintained in April 2026.

**Options considered.**

| Option | License | Why not chosen |
|--------|---------|----------------|
| **SeaweedFS** 4.47 | Apache-2.0 | — (chosen) |
| RustFS 1.0.0 | Apache-2.0 | Closest to MinIO, but reached 1.0 only on 2026-09-16 |
| Garage 2.4.1 | AGPL-3.0 | No versioning, object lock, or bucket policies |
| Versity S3 Gateway 1.8.0 | Apache-2.0 | Stores objects as plain files; less suited to large media |
| Ceph RGW | LGPL | Too heavy for a laptop |

**Decision.** SeaweedFS locally; native S3 or Google Cloud Storage (via its S3-compatible API) in production; Azure Blob only through an S3 shim.

**Cost / trade-off.** One-time migration of the plan and docs. GCS needs two boto3 checksum settings (see [Tech Stack › Build notes](tech-stack.md#build-notes)).

---

## D-014 · vLLM as a process inside Ray Serve, not Ray Serve LLM

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Serving

**Context.** Ray 2.58's built-in LLM serving (`ray.serve.llm`) is still beta and pins vLLM 0.26. The default model catalog needs vLLM 0.30 (released 2026-09-22).

**Options considered.**
1. Ray Serve LLM with its pinned vLLM 0.26, limiting the catalog to models that version supports.
2. Run vLLM's own OpenAI-compatible server (`vllm serve`) as a child process inside each Ray Serve replica.

**Decision.** Option 2. The base image becomes `vllm/vllm-openai:v0.30.0` plus Ray 2.58.

**Why.** The engine version is decoupled from Ray's release cycle. The planner already decides replicas and placement, so Serve LLM's autoscaling adds nothing here.

**Cost / trade-off.** We write a small process supervisor (start, health-check, stop) and lose Serve LLM's built-in router. The CUDA 13 image requires an NVIDIA driver ≥ 580; the dev laptop has 610.62.

**Re-examined 2026-10-06.** The reuse audit pointed out that the workload is entirely offline batch processing, which Ray Data (`map_batches` with GPU actor pools, plus vLLM's offline `LLM` class) handles natively: batching, retries, backpressure, and unloading a model when a stage ends. That would have removed the process supervisor and most of our scheduler. The team kept Ray Serve. What keeping it gives us:
- Models stay behind an HTTP, OpenAI-compatible API, so instructor ([D-025](#d-025--structured-extraction-instructor--our-quote-check-registry-ids-as-an-enum)) and MLflow's automatic call tracing work unchanged.
- In resident mode, concurrent runs share the same model replicas.
- The same serving path could later back interactive features.

**Revisit if.** The scheduler or the process supervisor becomes a maintenance burden; Ray Data is the documented alternative.

---

## D-015 · One multimodal model for text and vision on small GPUs

**Date:** 2026-09-27 · **Status:** Accepted — to validate · **Area:** Models

**Context.** The first laptop plan assumed an ~8B text model plus a separate 4–8B vision model. The model research found:
- The Qwen3.5 models read images natively.
- Qwen3.5-9B's 4-bit (AWQ) checkpoint is 9.1 GB, larger than the laptop's 8 GB card.
- Qwen3.5-4B AWQ is 4.0 GB.

**Decision.** On small GPUs, one Qwen3.5-4B deployment serves both the text and vision slots. Larger machines use larger Qwen variants the same way.

**Why.** It fits the card, and in stage-by-stage mode it removes one model load per run, since vision and text work merge into a single stage group.

**Cost / trade-off.** The laptop's text model is smaller than first planned. Whether 8k context is enough for fact extraction is [EXP-005](experiments.md#exp-005--fact-extraction-context-8k-vs-32k-tokens).

---

## D-016 · License allowlist enforced at startup

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Compliance

**Decision.** `config/licenses.yaml` lists the allowed licenses; catalog validation and CI (via `pip-licenses`) reject anything else. Allowed: Apache-2.0, MIT, BSD, PostgreSQL, and CC-BY-4.0 for weights. AGPL-3.0 is allowed only for unmodified standalone services (Grafana).

**Examples rejected during research.**
- Ultralytics YOLO-World / YOLOE (AGPL), replaced by LLMDet (Apache-2.0).
- Non-commercial models: jina-embeddings, MetaCLIP 2, the original GLiNER multi, WhisperX's default alignment models.
- Revenue- or territory-restricted licenses.
- MinIO (archived).
- SAM 3 needs legal review before use.

**Why.** The project is proprietary. License problems are cheapest to catch before code depends on a model.

---

## D-017 · Scene index embeds scene text only

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Knowledge layer

**Decision.** The vector index embeds each scene's text, not summaries of its extracted facts. Structured filters from the facts are applied at query time instead.

**Why.** Embedding fact summaries would require the text embedder to run *after* fact extraction, forcing an extra model load in stage-by-stage mode.

**Cost / trade-off.** Retrieval relies on the structured filters to bring in fact-level relations.

---

## D-018 · DINOv2 for camera-setup similarity

**Date:** 2026-09-27 · **Status:** Accepted — to validate · **Area:** Continuity

**Decision.** The `image_embedder` slot defaults to DINOv2-large (Apache-2.0) rather than SigLIP 2.

**Why.** Grouping shots by camera setup is a near-duplicate visual-similarity problem, where image-only features are a natural fit; SigLIP's strength, matching images to text, isn't needed here.

**Cost / trade-off.** It is an untested assumption until [EXP-010](experiments.md#exp-010--setup-clustering-dinov2-vs-siglip-2) compares them.

---

## D-019 · OIDC everywhere, with separate issuer and key URLs

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Security

**Decision.** Authentication always uses OIDC (Keycloak locally, any provider in production). The expected token issuer (`NIP_OIDC_ISSUER`) and the URL for fetching signing keys (`NIP_OIDC_JWKS_URL`) are separate settings.

**Why.** The auth code is identical in development and production. Separating the two URLs avoids a classic Docker pitfall: the browser reaches Keycloak at `localhost:8180`, so tokens carry that issuer, while the API container can only reach Keycloak at `keycloak:8080`.

---

## D-020 · `cpu` profile with recorded model outputs for CI

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Testing

**Decision.** With `NIP_PROFILE=cpu`, every model slot resolves to a stub that replays recorded real responses.

**Why.** CI runs the whole pipeline without a GPU, and checks can be built from day 3 without waiting for model serving.

**Cost / trade-off.** Recordings must be refreshed whenever a prompt or model changes. The nightly GPU run catches drift between recordings and real models.

---

## D-021 · Language rule packs resolve by tag fallback

**Date:** 2026-09-27 · **Status:** Accepted · **Area:** Localization

**Decision.** Rule packs resolve from the most specific language tag to the base: `es-ES` → `es` → `_base`.

**Why.** Corpus subtitles are often tagged only `es` (Sintel's are). The Spanish style guide covers both Latin American and Castilian Spanish, which differ only in address forms (`vosotros` is used in Spain), so `es-ES` overrides just that.

---

## D-022 · Self-hosted MLflow for experiments; no DAG tool; no hosted trackers

**Date:** 2026-10-06 · **Status:** Accepted · **Area:** Tooling

**Context.** Every experiment must be recorded with real, traceable numbers.

**Options considered.**
- Hosted trackers (Weights & Biases, Comet): would send dialogue and frames from benchmark runs to a third party.
- A DAG tool for the evaluation pipeline (Dagster): adds a service and a second way to run things.
- Self-hosted MLflow on our existing Postgres and SeaweedFS.

**Decision.** MLflow, self-hosted. `nip eval run` logs every benchmark run; `nip eval compare` generates the result tables in [experiments.md](experiments.md), with run IDs. No DAG tool (see D-004).

**Why.** Every number in the logs traces back to a run. MLflow needs only one extra container, because it reuses storage we already run.

**Cost / trade-off.** MLflow traces contain pre-release dialogue, so tracing is on only for benchmark runs and MLflow stays on the internal network.

---

## D-023 · Run queue: pgqueuer; no Ray Jobs

**Date:** 2026-10-06 · **Status:** Accepted · **Area:** Runtime

**Context.** The controller was going to claim queued runs from a Postgres table with hand-written locking, cancellation, and requeue-after-crash logic.

**Options considered.**
- **pgqueuer** (MIT, 1.5.0): a Postgres-backed queue. A `dedupe_key` (enforced by a partial unique index) allows one active run per episode; it supports cancellation, and a heartbeat requeues jobs from crashed workers.
- **Procrastinate** (MIT, 3.10.0): similar, slightly more code; requeueing stalled jobs needs our own periodic task.
- **Ray Jobs API**: a process per run with logs and stop, but not a queue (no ordering, no uniqueness beyond the submission ID).

**Decision.** pgqueuer. The controller becomes a pgqueuer worker inside the Ray cluster. No Ray Jobs.

**Why.** It replaces the claim, lock, cancel, and requeue code with a maintained library on the database we already run. Ray Jobs' main benefit, freeing a run's GPU actors when it stops, doesn't apply: with Ray Serve ([D-014](#d-014--vllm-as-a-process-inside-ray-serve-not-ray-serve-llm)) the GPUs belong to the model deployments, not to runs.

**Cost / trade-off.** In staged mode the worker takes one run at a time, because concurrent runs would fight over loading and unloading models on the same GPU. In resident mode several runs share the deployed models.

---

## D-024 · Cloud provisioning: SkyPilot

**Date:** 2026-10-06 · **Status:** Accepted · **Area:** Deployment

**Context.** VM clusters were going to be launched from hand-written Ray cluster-launcher configs.

**Decision.** SkyPilot (Apache-2.0, 0.14.0) provisions cloud GPU machines.

**Why.** One task file asks for, say, 8× H100 or 8× A100-80GB; SkyPilot picks the cheapest available option across about 25 clouds and Kubernetes, fails over between regions and clouds, runs our container image, and starts Ray on its standard port. That is exactly the Phase 4 cloud validation, without writing per-cloud configs.

**Cost / trade-off.** SkyPilot clusters are fixed-size; autoscaling stays with KubeRay on Kubernetes. Our image must be Debian-based with root or passwordless sudo, and SkyPilot replaces the image's entrypoint with a shell.

---

## D-025 · Structured extraction: instructor + our quote check; registry IDs as an enum

**Date:** 2026-10-06 · **Status:** Accepted — to validate · **Area:** Knowledge layer

**Context.** Fact extraction needs Pydantic-schema output, a check that every quote exists in the scene text, and one repair attempt on invalid output.

**Options considered.**
- **instructor** (MIT, 1.17.0): Pydantic models over any OpenAI-compatible API; validators receive the scene text as context; `max_retries=1` gives exactly one repair.
- **LangExtract** (Apache-2.0): strong source grounding, but schemas come from few-shot examples rather than Pydantic, matching is fuzzy by default, and there is no repair retry.
- **Outlines**: only enforces JSON structure, which vLLM already does.

**Decision.** instructor in JSON-schema mode against the vLLM endpoints, with our ~10-line quote check as its validator: facts with a bad quote are dropped, and only structural errors trigger the repair. Character and entity IDs from the registry are an **enum inside the schema**, so constrained decoding returns a known ID or `UNKNOWN`; rapidfuzz handles the rest.

**Why.** Least custom code for schema, validation, and repair. The enum moves most entity resolution into the extraction call itself.

**Cost / trade-off.** Text is normalized (Unicode, whitespace, quote marks) before the substring check. Very large registries make the enum unwieldy; [EXP-020](experiments.md#exp-020--entity-resolution-enum-constrained-ids-vs-fuzzy-matching-afterwards) compares it with fuzzy matching afterwards.

---

## D-026 · Clearance text detection: Presidio + GLiNER + urlextract

**Date:** 2026-10-06 · **Status:** Accepted — plates to validate · **Area:** Clearance

**Context.** The Clearance Scanner was going to have its own detectors for phone numbers, emails, URLs, addresses, plates, and real names in OCR text, dialogue, and subtitles.

**Decision.**
- **Presidio** (MIT; now maintained by the community "Data Privacy Stack" organization) orchestrates detection: built-in phone and email recognizers, context scoring, an **allow-list** for fiction-reserved numbers (an anchored 555-01xx pattern, because libphonenumber considers (212) 555-0123 a valid number) and **deny-lists** built from the clearance log and brand list.
- Its **GLiNER** recognizer finds people, organizations, and products in en/es/fr/de.
- **urlextract** (MIT, full top-level-domain list) runs as a custom Presidio recognizer for URLs, behind a ~10-line cleanup of OCR mistakes ("www . site . com").
- **License plates** start with OCR text plus Presidio's plate-format recognizers. A dedicated plate reader (fast-alpr, MIT) is considered only after legal checks how its weights were trained ([EXP-019](experiments.md#exp-019--license-plates-ocr--format-rules-vs-a-dedicated-plate-reader)).

**Why.** It replaces five custom detectors and their orchestration with a maintained framework built for this job.

**Cost / trade-off.** Presidio is English-only out of the box, so every recognizer gets `supported_languages`, and organizations must be un-ignored. spaCy's Spanish models are GPL-3.0 and its French models LGPL-LR, which our license policy rejects, so Presidio's language engine uses the MIT spaCy models for en/de and tokenizer-only pipelines for es/fr, with names coming from GLiNER. There is no street-address recognizer; GLiNER's address label is used and measured. Presidio's email check uses tldextract, which downloads a domain list unless `TLDEXTRACT_PUBLIC_SUFFIX_LIST_URLS=""` is set.

---

## D-027 · Parsing and decoding libraries, and what stays custom

**Date:** 2026-10-06 · **Status:** Accepted · **Area:** Timeline

**Decision.**

| Component | Choice | Evidence |
|-----------|--------|----------|
| TTML / IMSC subtitles | **ttconv** (BSD-2) | 6 of 6 TTML timing test cases correct, with exact fractions (pycaption 4/6, pysubs2 0/6). It only logs bad times, so we turn logged errors into validation failures |
| SRT / WebVTT | pysubs2 (MIT), unchanged | — |
| Fountain scripts | **screenplay-tools** (MIT) | Passed a Fountain test including dual dialogue |
| FDX scripts | **Our own reader** (stdlib XML) | screenplay-tools reads only the first text run of a paragraph, so formatted words are lost (confirmed in its source) |
| PDF scripts | **Our own parser** on pdfplumber | The existing PDF screenplay parsers are abandoned; PyMuPDF is AGPL |
| Frame decoding | **TorchCodec** (BSD-3), exact seek mode | Guarantees frame *i* is returned for index *i*; one decode feeds shot detection and keyframes. Uses our own LGPL FFmpeg shared libraries (PyAV's wheels bundle GPL encoders) |
| Timecode math | **Our own** (Fraction-based, integer frames) | OpenTimelineIO stores rates as floats and its frames→seconds→frames round trip at 24000/1001 was off by one for 11,541 of 200,000 frames; the `timecode` package rounds 24000/1001 to 23.98 |
| Subtitle QC rules | **Our own**, porting thresholds from Subtitle Edit 5's Netflix check (MIT since version 5) | No maintained Python library implements them |
| Flag-to-label matching | scipy `linear_sum_assignment` | Optimal one-to-one matching, replacing the planned greedy matcher |

**Why.** Use a library wherever one exists, is maintained, permissively licensed, and correct on our edge cases; keep our own code only where libraries failed tests or don't exist.

**Cost / trade-off.** screenplay-tools is young (version 0.0.10), so its Fountain output is covered by our parser tests. TorchCodec needs torch ≥ 2.11, which must be checked against the torch in the vLLM image.

---

## D-028 · Labelling and inspection: Label Studio + FiftyOne

**Date:** 2026-10-06 · **Status:** Accepted · **Area:** Evaluation

**Context.** The experiments need hand-made ground truth (shot cuts, camera setups, script-line start times, fact correctness, story order), and the docs had no tool for it.

**Decision.**
- **Label Studio Community** (Apache-2.0, 1.23.2) for all five labelling jobs, in one container on our Postgres.
- **FiftyOne** open source (Apache-2.0) as a local tool for inspecting keyframes, detection boxes, embedding clusters, and near-duplicates.

**Options rejected.** CVAT (frame-exact video labelling but an 18-service install; kept as the fallback for cuts), Argilla (no longer developed).

**Cost / trade-off.**
- Label Studio silently reads a frame rate of `"24000/1001"` as 24 (about 86 frames of drift per hour), so projects use `23.976023976`; its frames are numbered from 1; reaching storage or a model backend on our private network requires turning off its SSRF protection, acceptable only on the internal network.
- FiftyOne bundles a MongoDB server (SSPL license), flagged for legal review; it runs only locally and is never deployed.

---

## D-029 · Review UI: React-admin + ra-keycloak

**Date:** 2026-10-06 · **Status:** Accepted · **Area:** Review UI

**Options considered.** Plain React + Vite; Refine (npm releases stalled since April 2026); React-admin; Python UI frameworks (Streamlit, NiceGUI, Reflex, Gradio — none handles frame-level video review well, and Reflex's OIDC support is proprietary).

**Decision.** React-admin (MIT) with `ra-keycloak` (MIT, by the React-admin maintainers) for login. List endpoints return a `Content-Range` header for its data provider. The evidence player is a plain React component on the browser's `<video>` element, with WebVTT `<track>` subtitles and `requestVideoFrameCallback` to read the frame actually shown.

**Why.** It gives list, filter, and detail screens and OIDC login out of the box, leaving the two-week UI budget for the evidence player.

**Evidence.** A seek test in Chrome on a 23.976 fps clip with frame numbers encoded in the pixels: seeking to the **middle** of a frame landed on the right frame 150/150 times; seeking to the exact frame start, 95/150. The player therefore always seeks to frame middles: `(n + 0.5) × 1001 / 24000` seconds.

---

## D-030 · Test oracles and copyleft tools

**Date:** 2026-10-06 · **Status:** Accepted · **Area:** Testing / compliance

**Decision.** Independent implementations check ours in tests, never in the product:
- **OpenTimelineIO** and **`timecode`** check our timecode math.
- **Subtitle Edit's `seconv lint --json`** checks our subtitle rules in CI.
- **ffsubsync** checks our drift and offset detection. It pins a GPL dependency (auditok), so it runs as a command in its own environment.
- **screenplain** generates FDX test fixtures from Fountain.

Copyleft tools (GPL/AGPL, e.g. alass) may be used only as external processes in tests; they are never imported, linked, or shipped.

**Why.** An independent oracle catches the bugs our own tests share with our own code.

---

## Entry Template

```markdown
## D-0XX · <decision in a few words>

**Date:** YYYY-MM-DD · **Status:** Proposed | Accepted | Accepted — to validate (EXP-0XX) | Superseded by D-0YY · **Area:** <area>

**Context.** What forced a decision.

**Options considered.** Each option and its main drawback.

**Decision.** What we chose.

**Why.** The reasons, with evidence (measurements, links, experiment IDs).

**Cost / trade-off.** What we gave up.

**Revisit if.** The condition that would reopen this.
```
