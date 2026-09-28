# Hardware Adaptation

## Goal

**Same code, same container image, same configuration on any hardware.** A laptop with one 8 GB GPU and a cloud cluster with dozens of 80 GB GPUs run the identical release. The only thing that differs is the **Plan**: a record, computed at startup from the hardware actually present, of which model variant serves each job, how many copies run, and whether models stay loaded or are swapped stage by stage.

```
┌──────────────┐   ┌────────────────┐   ┌─────────────────┐
│ Hardware     │   │ Model catalog  │   │ Workload        │
│ probe (NVML) │   │ (catalog.yaml) │   │ (agents, units) │
└──────┬───────┘   └───────┬────────┘   └────────┬────────┘
       │ inventory         │ variants            │ demand
       └───────────────────┼─────────────────────┘
                           ▼
                 ┌────────────────────┐   objective (quality | throughput)
                 │      PLANNER       │ ◄ pins (optional)
                 │  (pure function)   │
                 └─────────┬──────────┘
                           ▼
                 ┌────────────────────┐
                 │        PLAN        │  stored with the run; every flag cites it
                 └─────────┬──────────┘
                           ▼
       ┌───────────────────┴────────────────────┐
       ▼                                        ▼
┌──────────────────────┐           ┌─────────────────────────┐
│ Serving (Ray Serve)  │           │ Scheduler               │
│ one app per slot,    │ ◄───────► │ staged or resident,     │
│ vLLM for LLM/VLM     │           │ work units, retries,    │
└──────────────────────┘           │ OOM amendments          │
                                   └─────────────────────────┘
```

---

## Hardware Probe

At startup and whenever the Ray cluster's membership changes, a small Ray task runs on every node and reads GPUs through NVML (`nvidia-ml-py`, imported as `pynvml`).

```json
{
  "fingerprint": "sha256:5c1e…",
  "nodes": [
    {
      "node_id": "a1f3…",
      "cpus": 16,
      "ram_gb": 23.5,
      "gpus": [
        {"index": 0, "name": "NVIDIA GeForce RTX 4060 Laptop GPU",
         "vram_total_gb": 8.0, "vram_free_gb": 6.9, "compute_capability": "8.9"}
      ]
    }
  ],
  "autoscaling": {"enabled": false, "max_gpu_nodes": 0, "node_type": null}
}
```

Probe rules:

- **Free, not total.** Displays, drivers, and other processes hold VRAM. The planner budgets against `vram_free_gb` minus a safety margin (default 0.5 GB), capped by `NIP_GPU_MEM_UTILIZATION × total`.
- **Consistent GPU indices.** `CUDA_DEVICE_ORDER=PCI_BUS_ID` is set in the image so NVML and CUDA agree on numbering.
- **Our own accounting.** Ray treats GPUs as logical resources and does not isolate GPU memory, so VRAM budgeting is done by the planner, not by Ray. (Ray's `accelerator_type` is not used: consumer GPUs such as GeForce cards are not in Ray's known-accelerator list.)
- `ram_gb` is the memory visible to the container (under WSL2 this is the WSL VM's limit, not the host's).

---

## Model Catalog

`config/catalog.yaml` lists, for each **slot**, model variants ranked by quality. Swapping in a newer model is a catalog change and a benchmark run — never a code change.

| Slot | Job |
|------|-----|
| `text_llm` | Fact extraction, story-order disambiguation, LLM checks in all agents |
| `vlm` | Logo/artwork identification, continuity verification |
| `judge_llm` | Verification judge (prefers a different family from `text_llm`) |
| `asr` | Speech-to-text with word timestamps |
| `ocr` | Scene-text reading in keyframes |
| `detector` | Open-vocabulary region proposals (logos, signs, posters, screens, packaging) |
| `image_embedder` | Shot similarity for setup clustering and the continuity pre-filter |
| `text_embedder` | Scene retrieval |
| `ner` | Zero-shot entity recognition in dialogue and subtitles |
| `shot_detector` | Shot boundary detection |

### Variant fields

| Field | Meaning |
|-------|---------|
| `id` | Stable variant id used in Plans, pins, flags, and cache keys |
| `serves` | Slots this variant can serve. A natively multimodal model lists both `text_llm` and `vlm`; the planner can deploy it once for both |
| `family` | Model family (judge independence compares this) |
| `engine` | `vllm` (pinned vLLM OpenAI-compatible server), `actor` (plain Ray Serve deployment), or `stub` (recorded outputs, for tests) |
| `base_model`, `checkpoint`, `quant` | Model repository, the exact quantized checkpoint (pinned to a revision when the catalog is frozen), and its quantization |
| `min_vllm` | Minimum vLLM version that can load it; checked against the image at startup |
| `box_format` | How the model reports boxes (`xyxy_0_1000`, `yxyx_0_1000`, `xyxy_pixels`); clients normalize to `[x, y, w, h]` in 0–1 |
| `weights_gb` | GPU memory for weights |
| `overhead_gb` | CUDA context, activations, vision encoder buffers |
| `kv_mb_per_1k_tokens` | KV-cache cost (LLM/VLM only) |
| `context` | `{default, min}` tokens; the planner may shrink toward `min` before downgrading |
| `tp_options` | Allowed tensor-parallel degrees (must divide the model's attention heads) |
| `min_compute_capability` | E.g. `8.9` for FP8 checkpoints |
| `quality_rank` | Higher is better within the slot; calibrated by the benchmark |
| `cost_hint` | Relative cost per work unit, used to weight replicas by demand |
| `license` | Recorded for compliance; non-permissive licenses fail catalog validation |

### Excerpt

```yaml
# config/catalog.yaml (excerpt)
# weights_gb are measured checkpoint sizes. overhead_gb and kv_mb_per_1k_tokens are starting
# estimates; after a variant's first load, measured peak memory replaces them (see Memory model).
variants:
  - id: qwen3.5-4b-awq
    serves: [text_llm, vlm]            # natively multimodal: one deployment serves both slots
    family: qwen
    engine: vllm
    base_model: Qwen/Qwen3.5-4B
    quant: awq-int4
    weights_gb: 4.0
    overhead_gb: 1.2
    kv_mb_per_1k_tokens: 60
    context: {default: 32768, min: 8192}
    tp_options: [1]
    min_vllm: "0.30"
    box_format: xyxy_0_1000
    quality_rank: 30
    cost_hint: 1.0
    license: Apache-2.0

  - id: qwen3.8-27b-int4
    serves: [text_llm, vlm]
    family: qwen
    engine: vllm
    base_model: Qwen/Qwen3.8-27B
    checkpoint: RedHatAI/Qwen3.8-27B-INT4
    quant: w4a16
    weights_gb: 19.5
    overhead_gb: 2.5
    kv_mb_per_1k_tokens: 160
    context: {default: 32768, min: 8192}
    tp_options: [1, 2]
    min_vllm: "0.30"
    box_format: xyxy_0_1000            # verify on first benchmark run
    quality_rank: 65
    cost_hint: 4.0
    license: Apache-2.0

  - id: ministral-3-3b-fp8
    serves: [judge_llm]
    family: mistral
    engine: vllm
    base_model: mistralai/Ministral-3-3B-Instruct-2512
    quant: fp8
    weights_gb: 4.7
    min_compute_capability: "8.0"      # FP8 is native on 8.9+ (Ada, Hopper), weight-only on A100
    context: {default: 16384, min: 8192}
    tp_options: [1]
    quality_rank: 20
    license: Apache-2.0

  - id: faster-whisper-large-v3-int8
    serves: [asr]
    family: whisper
    engine: actor
    base_model: Systran/faster-whisper-large-v3
    quant: int8
    vram_gb: 3.0
    quality_rank: 50
    license: MIT

  - id: stub
    serves: [text_llm, vlm, judge_llm, asr, ocr, detector, image_embedder, text_embedder, ner, shot_detector]
    engine: stub
    vram_gb: 0
    quality_rank: 0
    license: n/a
```

**Catalog validation** runs at startup. A variant is excluded, with a logged reason, if its license is not in `config/licenses.yaml`, its `min_vllm` is newer than the image's vLLM, or no GPU meets its `min_compute_capability`.

The full default catalog, with licenses, is in [Tech Stack › Model Catalog Defaults](tech-stack.md#model-catalog-defaults).

### Memory model

For an LLM/VLM variant at tensor-parallel degree `tp`:

```
per_gpu_gb = weights_gb / tp
           + kv_mb_per_1k_tokens × context_k × concurrency / 1024 / tp
           + overhead_gb
fits if per_gpu_gb ≤ usable_gb(gpu)
usable_gb  = min(NIP_GPU_MEM_UTILIZATION × vram_total_gb, vram_free_gb − margin)
```

vLLM then receives `gpu_memory_utilization = per_gpu_gb / vram_total_gb` (plus small headroom) instead of a blanket default, so co-resident models never compete for the same memory. Non-LLM variants declare a fixed `vram_gb`.

**Calibration.** Catalog numbers are estimates. After every load, the measured peak memory for `(variant, GPU model, context)` is stored (`variant_calibration` table) and preferred over the estimate in later Plans, so the planner gets more accurate on each machine it runs on.

---

## The Planner

A **pure, deterministic function**: the same inventory, catalog, workload, objective, and pins always produce the same Plan. It is unit-tested against simulated inventories and can be run for hardware you don't have (`nip plan --simulate inventory.json`).

### Algorithm

1. **Required slots.** Resolve agents and checks from the run's inputs; collect the slots they need. A script-only run needs no `vlm`, `asr`, `ocr`, or `detector`.
2. **Candidates.** For each slot, list `(variant, tp)` placements that fit on some group of `tp` identical GPUs within one node, sorted by `quality_rank`. For LLM/VLM variants, first try the default context, then shrink toward `min` context before falling back to a lower-ranked variant.
3. **Best alone.** Each slot's *best-alone* choice is its highest-ranked candidate that fits on the largest available GPU group. A slot with no candidate at all disables its checks, which are reported as skipped with reason `no hardware for <slot>`. With `NIP_PROFILE=cpu` every slot resolves to its `stub` variant.
4. **Resident or staged.**
   - `quality` objective: keep every slot at its best-alone choice. If all of them pack onto the cluster simultaneously → **resident**; otherwise → **staged**.
   - `throughput` objective: search for the highest-quality set that packs simultaneously (greedy: downgrade the slot with the smallest quality loss per GB freed until the set packs). If a set packs → **resident**; if not even the smallest set packs → **staged**.
5. **Packing.** LLM/VLM engines get whole GPUs where possible. Fractional placement of a vLLM engine is used only when a single large GPU must host two engines; small `actor` models (OCR, detector, embedders, NER, shot detection) are packed fractionally into leftover memory.
6. **Replicas.** After one replica of each slot is placed, remaining capacity is filled with extra replicas, one at a time, to the slot with the highest remaining demand per replica (demand = work units × `cost_hint`). In staged mode, the model of the current stage is replicated across every GPU that can hold it.
7. **Judge.** Prefer a `judge_llm` variant whose `family` differs from `text_llm`'s, if one fits under the same mode without pushing any slot below its best-alone choice. Otherwise the judge reuses the `text_llm` deployment with a judge prompt, and the Plan records `judge_independent: false`.
8. **Pins.** `NIP_PIN_<SLOT>` (or a run's `pins`) forces a variant. A pin that cannot fit fails fast with `CLUSTER_UNAVAILABLE` rather than silently changing.

### Stage groups (staged mode)

Groups are ordered by data dependency; the planner merges adjacent groups whenever their models fit together.

| Order | Group | Slots | Needs |
|-------|-------|-------|-------|
| 1 | `timeline` | `shot_detector`, `asr` | Ingested media |
| 2 | `vision_prep` | `ocr`, `detector`, `image_embedder` | Keyframes |
| 3 | `text_prep` | `text_embedder`, `ner` | Aligned script and subtitles |
| 4 | `vlm` | `vlm` | Detector candidates, setup clusters |
| 5 | `llm` | `text_llm` | Timeline, scene index |
| 6 | `judge` | `judge_llm` (skipped if it reuses `text_llm`, which then judges at the end of group 5) | All flags |

When one variant serves both `vlm` and `text_llm` (a natively multimodal model), groups 4 and 5 merge into a single load. Each model is loaded at most once per run; a typical laptop run performs five loads, and their durations are recorded in the run view.

### Worked examples

Illustrative planner outputs with the default catalog. The authoritative versions are the expected Plans in `tests/unit/planner/`, and `nip plan --simulate` prints them for any inventory.

| Machine | Objective | Mode | `text_llm` + `vlm` (shared) | `judge_llm` | Notes |
|---------|-----------|------|-----------------------------|-------------|-------|
| Laptop, 1× 8 GB (≈6.9 GB free) | quality | staged, 5 groups | Qwen3.5-4B AWQ, 8k context, images capped at ~1024×576 | Ministral-3-3B FP8 (independent, own group) | Every small model loads with its stage group |
| Workstation, 1× 24 GB | quality | staged, 3 groups | Qwen3.5-9B FP8 | Gemma-4-12B QAT (independent) | Small models co-reside with the shared model |
| Workstation, 1× 48 GB | quality | staged, 2 groups | Qwen3.8-27B FP8 | Gemma-4-12B QAT | With `throughput`: resident, Qwen3.8-27B INT4 + Gemma-4-12B |
| Cloud node, 8× 80 GB | quality | staged, 2 groups | Qwen3.5-397B-A17B FP8, tensor-parallel over 8 GPUs | Gemma-4-31B QAT, replicated across GPUs | With `throughput`: resident, several replicas of Qwen3.5-122B-A10B Int4 plus judge replicas |
| Cloud cluster, N× (8× 80 GB) | either | as above per node | Same variants | Same | Extra nodes become replicas of the bottleneck slot |

Full variant list and licenses: [Tech Stack › Model Catalog Defaults](tech-stack.md#model-catalog-defaults).

---

## The Plan

The planner's output. Stored in the `plan` table and in `runs/{run_id}/plan.json`; every flag's `produced_by.plan_id` points to it. Example for the laptop:

```json
{
  "plan_id": "plan_42",
  "inventory_fingerprint": "sha256:5c1e…",
  "catalog_sha256": "b07d…",
  "objective": "quality",
  "mode": "staged",
  "groups": [
    {"name": "timeline",    "slots": ["shot_detector", "asr"]},
    {"name": "vision_prep", "slots": ["ocr", "detector", "image_embedder"]},
    {"name": "text_prep",   "slots": ["text_embedder", "ner"]},
    {"name": "vlm+llm",     "slots": ["vlm", "text_llm"]},
    {"name": "judge",       "slots": ["judge_llm"]}
  ],
  "decisions": {
    "text_llm":       {"variant": "qwen3.5-4b-awq", "shared_with": ["vlm"], "replicas": 1,
                       "gpus_per_replica": 1, "context": 8192, "gpu_memory_utilization": 0.80},
    "vlm":            {"variant": "qwen3.5-4b-awq", "shared_with": ["text_llm"],
                       "max_pixels": 589824, "images_per_prompt": 2},
    "judge_llm":      {"variant": "ministral-3-3b-fp8", "independent_family": true, "replicas": 1},
    "asr":            {"variant": "faster-whisper-large-v3-int8", "gpu_fraction": 0.5},
    "shot_detector":  {"variant": "transnetv2", "gpu_fraction": 0.2},
    "ocr":            {"variant": "pp-ocrv6-medium", "gpu_fraction": 0.2},
    "detector":       {"variant": "llmdet-base", "gpu_fraction": 0.3},
    "image_embedder": {"variant": "dinov2-large", "gpu_fraction": 0.2},
    "text_embedder":  {"variant": "qwen3-embedding-0.6b", "gpu_fraction": 0.3},
    "ner":            {"variant": "gliner-x-base", "gpu_fraction": 0.3}
  },
  "skipped_slots": [],
  "warnings": ["text_llm context reduced 32768 → 8192 to fit 6.4 GB usable VRAM"],
  "amendments": []
}
```

**Amendments** are appended during a run, never rewritten: an out-of-memory downgrade, a node joining (replicas added), or a node leaving (deployment re-created).

---

## Execution

### Serving on Ray Serve

- **One Serve application per deployed variant**, named `nip-<variant>` with route prefix `/models/<variant>`; slots map to deployments through the Plan (a shared multimodal variant is one deployment serving two slots). One application per model is what makes loading and unloading independent.
- **LLM/VLM variants** run as a Serve deployment whose replicas each start the image's pinned **vLLM OpenAI-compatible server** (`vllm serve …`) as a child process on the GPUs Ray assigned to that replica, and forward requests to it over localhost. The planner sets the server flags: `--tensor-parallel-size`, `--max-model-len`, `--gpu-memory-utilization`, `--enforce-eager` on small GPUs, `--kv-cache-dtype fp8` where supported, and for vision `--limit-mm-per-prompt.image` and `--mm-processor-kwargs` (`max_pixels`). Replica counts come from the Plan.
- **Why not Ray Serve LLM (`ray.serve.llm`).** It is still beta and pins its own vLLM (Ray 2.58 ships vLLM 0.26, four releases behind the version the default models need). Running vLLM's server as a process decouples the engine version from Ray's, and the planner already decides placement and replicas, so Serve LLM's autoscaling adds nothing here.
- **Actor slots** are ordinary Serve deployments with `ray_actor_options={"num_gpus": <fraction>}`.
- **Loading and unloading** use `serve.run(app, name=…, route_prefix=…)` and `serve.delete(name)` from the controller. The Serve REST `PUT` endpoint is never used: it removes every application not included in the request.
- **Structured output.** All LLM/VLM calls use OpenAI-style `response_format` with a JSON schema generated from the `contracts` models, so even small models return valid structures.

### Staged vs resident

| | Staged | Resident |
|--|--------|----------|
| When | Not all slots fit at once (laptop, small workstations) | Everything fits (large GPUs, clusters) |
| Lifecycle | Load group → drain all its work units → unload → next group | All deployments up for the whole run |
| Parallelism | Within a group: replicas across GPUs; units in flight per replica bounded | Across groups: agents' units run concurrently as their inputs become ready |
| Throughput | Bounded by the slowest group | Bounded by the bottleneck slot, which receives the extra replicas |

vLLM sleep mode (moving weights to CPU RAM instead of unloading) could make staged swaps faster, but it requires the server's development mode, and a sleeping engine still holds its GPU reservation in Ray, which blocks the next group from being scheduled. Staged mode therefore unloads fully; sleep mode is a post-MVP optimization.

### Work units and backpressure

Every check produces small, idempotent work units (a scene, a subtitle-cue window, a shot pair). The scheduler keeps at most `max_in_flight = replicas × per-replica concurrency` units outstanding per slot, so adding hardware increases throughput without code changes, and a small GPU is never flooded.

---

## Elasticity

| Event | Behavior |
|-------|----------|
| Run starts with autoscaling enabled | The planner computes a *target* Plan for `NIP_AUTOSCALE_MAX_GPU_NODES` nodes and requests those resources from the Ray autoscaler, then starts immediately on current capacity |
| Node joins | Inventory re-probed; the planner adds replicas (immediately in resident mode, at the next group boundary in staged mode); a Plan amendment is recorded. Variants are upgraded only at group boundaries, never mid-group |
| Node leaves | Ray retries the affected units; lost deployments are re-created on remaining capacity, possibly at a smaller variant (amendment) |
| Persistent GPU out-of-memory | Retry with smaller batch/context; then downgrade the slot to the next variant for the rest of the run (amendment) |
| Run ends | The resource request is cleared so the cluster can scale back down |

**Autoscaling backends.** On cloud VMs, the Ray cluster launcher (AWS, GCP, and Azure are supported by the Ray team) adds and removes worker VMs. On Kubernetes, a KubeRay `RayCluster` with `enableInTreeAutoscaling: true` scales Ray worker pods, and a node autoscaler (Cluster Autoscaler or Karpenter) adds the GPU nodes they need.

---

## Deployment Targets

| Target | How | What changes |
|--------|-----|--------------|
| **Single machine** (laptop, workstation, one cloud VM) | `docker compose up` | Nothing |
| **VM cluster** | The head VM runs `compose.yaml`; worker VMs, launched by the Ray cluster launcher from `deploy/ray/`, run the same image with `ray start --address=<head>:6379` | Env: `NIP_AUTOSCALE_MAX_GPU_NODES` |
| **Kubernetes** | `deploy/helm/nip`: KubeRay `RayCluster` (head + GPU worker groups), API, UI. A plain `RayCluster` is used rather than `RayService`, because the controller deploys and deletes Serve applications at runtime and a `RayService` would re-apply its declared config over them | Env: `NIP_DATABASE_URL` (managed Postgres), `NIP_S3_ENDPOINT` (native object storage), `NIP_OIDC_*` (corporate identity provider), `NIP_AUTOSCALE_MAX_GPU_NODES` |

In every case the image digest and the contents of `config/` are identical. The release checklist verifies this by running the benchmark on the laptop and on the cloud from the same tag ([Phased Plan › Phase 4](phased-plan.md#phase-4--review-scale-out-hardening-weeks-78)).

---

## Windows / WSL2 Notes

Ray and vLLM run inside Linux containers (Ray's native Windows support is beta; vLLM is Linux-only).

| Topic | What to know |
|-------|--------------|
| GPU access | Docker Desktop's WSL2 backend provides the GPU; containers use `gpus: all` (Docker Desktop does not support selecting individual GPUs) |
| Driver | The CUDA 13 base image needs an NVIDIA Windows driver ≥ 580 |
| Free VRAM | Usually ~1 GB below total because of the display; the probe's free-memory rule handles this |
| Pinned memory | Set `VLLM_WSL2_ENABLE_PIN_MEMORY=1` (WSL2 disables pinned memory by default) |
| RAM | The WSL VM gets 50% of host RAM by default; raise it in `%UserProfile%\.wslconfig` for CPU offload and Ray's object store |
| Shared memory | Give the Ray container a large `/dev/shm` (`shm_size`) or `ipc: host` |
| Monitoring | NVML under WSL cannot report GPU utilization or processes; memory metrics work, utilization panels stay empty |

Setup steps: [Project Structure › Dev Setup](project-structure.md#dev-setup).

---

## Reproducibility

- Every run stores its inventory, catalog hash, objective, pins, decisions, and amendments.
- Every flag records the model variant, prompt version, Plan, and cache key that produced it.
- Benchmark baselines are kept per Plan fingerprint, so laptop and cloud results are never compared against the wrong baseline ([Evaluation › Regression Gate](evaluation.md#regression-gate)).
