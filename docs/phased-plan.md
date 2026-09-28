# Phased Build Plan

## Summary

**8 weeks, 2 people, 4 two-week phases.** Each phase ends with a demo and benchmark numbers ([Evaluation](evaluation.md)).

```
P1 Foundation (W1–2) ─→ P2 Knowledge + rules (W3–4) ─→ P3 Vision + LLM checks (W5–6) ─→ P4 Review + scale-out (W7–8)
   walking skeleton        first benchmark numbers        all 4 agents verified          same commit: laptop & cloud
```

### Roles

| Person | Owns |
|--------|------|
| **A — Text & Knowledge** | Script and subtitle ingest, timecode library, fact extraction and consolidation, Script Critic, Localization Auditor, verification, review UI |
| **B — Media & Runtime** | Hardware probe, catalog, planner, Ray/vLLM serving, scheduler, media pipeline (shots, keyframes, speech-to-text, OCR, detection), Clearance Scanner, Continuity Inspector, deployment (Compose, Helm/KubeRay), monitoring |

Shared: contracts (`nip/contracts`), database schema, evaluation harness, weekly benchmark run.

### Working rules

- **Walking skeleton first.** By the end of week 2, one real check runs end-to-end (ingest → timeline → check → verification → report) on real content.
- **Contracts before code.** Flag, Evidence, Fact, Plan, and HardwareInventory models are agreed on day 2 and change only by joint decision.
- **Benchmark every Friday** from week 3, on the laptop Plan; from week 7 also on a cloud Plan.
- **Stubs keep people unblocked.** Person A develops checks against stub model backends while Person B brings up real serving.

---

## Phase 1 — Foundation (Weeks 1–2)

**Goal:** the platform exists and one real check runs through it.

| # | Owner | Deliverable |
|---|-------|-------------|
| 1.1 | Both | Repo scaffolding, CI (lint, types, unit tests on the `cpu` profile), contracts v1, schema v1 + migrations |
| 1.2 | A | Timecode library: rational frame rates, drop-frame SMPTE, ms↔frame conversion, property-based tests |
| 1.3 | A | Parsers + validation: Fountain, FDX, PDF scripts; SRT, WebVTT, TTML subtitles; `bible.yaml`, glossary CSV, clearance log CSV |
| 1.4 | A | Script-estimate timeline; flag emission; minimal report JSON |
| 1.5 | B | `compose.yaml`: Postgres + pgvector, object storage, Ray head, API skeleton, Keycloak |
| 1.6 | B | Hardware probe, model catalog loader, planner v1 (pure function) with simulated inventories |
| 1.7 | B | Ray Serve model deployments with deploy/teardown (staged mode) on the laptop; stub backends |
| 1.8 | B | Media probe, shot detection, keyframe extraction |
| 1.9 | Both | Corpus manifest + downloader; injector framework skeleton |
| 1.10 | A | Walking-skeleton check: `loc.readability` end-to-end |

**Exit criteria**
- A corpus film + script + Spanish subtitles ingest into a timeline with shots and keyframes.
- `loc.readability` flags appear in the report JSON with resolvable evidence.
- The planner produces the expected Plan for three simulated inventories (1× 8 GB, 1× 48 GB, 8× 80 GB) — table-driven tests.
- CI green without a GPU.

---

## Phase 2 — Knowledge + Deterministic Checks (Weeks 3–4)

**Goal:** the knowledge layer is populated and every rule-based check works.

| # | Owner | Deliverable |
|---|-------|-------------|
| 2.1 | A | Fact extraction (JSON-schema output, grounding validator), entity resolution, consolidation into timed facts |
| 2.2 | A | Story order and story-day derivation (rules + LLM for ambiguous transitions + bible overrides) |
| 2.3 | A | Script Critic Layer 1 rules (`plot.knowledge_order`, `plot.dead_acts`, `plot.two_places`, `plot.prop_provenance`) |
| 2.4 | A | Source↔target cue alignment; `loc.term`, `loc.shot_change`, `loc.drift`, `loc.offset` |
| 2.5 | B | Speech-to-text + script↔transcript alignment (picture timeline replaces estimates) |
| 2.6 | B | OCR channel + parsers (`clr.phone`, `clr.url`, `clr.email`, `clr.address`, `clr.plate`, `clr.brand_text`) |
| 2.7 | B | Clearance-log matching, occurrence grouping, prominence scoring, clearance CSV |
| 2.8 | B | Scene vector index (text embedder), hybrid retrieval |
| 2.9 | Both | Injectors for localization-deterministic, clearance-text, and plot-Layer-1 errors; stage cache + incremental re-runs |

**Exit criteria**
- Benchmark v1 published for all deterministic checks ([targets](evaluation.md#mvp-targets)).
- Incremental re-run demo: edit one scene → only units that read it re-run (shown in `GET /runs/{id}/diff`).

---

## Phase 3 — Vision + LLM Checks (Weeks 5–6)

**Goal:** all four agents produce verified flags.

| # | Owner | Deliverable |
|---|-------|-------------|
| 3.1 | A | `loc.gender`, `loc.formality`, `loc.spoiler` with es/fr/de rule packs |
| 3.2 | A | Script Critic Layer 2: `plot.motivation`, `plot.unresolved_setup` |
| 3.3 | A | Verification pipeline: evidence resolver, rule re-check, LLM judge, routing, dedup |
| 3.4 | B | Open-vocabulary detector + vision-model channel (`clr.logo`, `clr.artwork`); `clr.dialogue_ref` via NER |
| 3.5 | B | Continuity text rules (`cont.wardrobe_text`, `cont.injury_text`, `cont.prop_text`) |
| 3.6 | B | `cont.visual`: setup clustering, same-setup pre-filter, vision-model verification, per-episode call cap |
| 3.7 | Both | Injectors for LLM-localization, logos/artwork, plot Layer 2, and visual continuity errors |

**Exit criteria**
- Every check ID in [Data Model › Check IDs](data-model.md#check-ids) produces verified flags on the benchmark.
- Full benchmark report generated; clean-run (un-injected) triage started.

---

## Phase 4 — Review, Scale-out, Hardening (Weeks 7–8)

**Goal:** people can use it, and it runs at full capacity on cloud hardware without changes.

| # | Owner | Deliverable |
|---|-------|-------------|
| 4.1 | A | Review UI: report, flag detail with evidence player, clearance report, fact queue, run view, diff view |
| 4.2 | A | Dispositions with fingerprint carry-forward; fact corrections → flag re-evaluation; audit trail views |
| 4.3 | B | Helm chart (KubeRay RayCluster + API + UI) and GPU worker autoscaling |
| 4.4 | B | Cloud validation on rented multi-GPU capacity: benchmark on a resident, multi-replica Plan |
| 4.5 | B | OOM amendment path, coverage-gap reporting, Prometheus metrics + Grafana dashboards |
| 4.6 | B | `nip models pull` / `nip models mirror` (download only what the Plan needs; mirror to internal storage) |
| 4.7 | Both | Threshold tuning on the benchmark; per-Plan comparison report; demo script |

**Exit criteria**
- **Same commit, laptop and cloud:** the release tag runs the benchmark on the laptop and on the cloud cluster with **no code or config edits** — only environment values (endpoints, credentials, autoscaling limit) differ.
- Per-Plan benchmark table published (quality, GPU-seconds, wall time per episode).
- MVP targets met on the cloud Plan, or misses documented with cause.
- Demo recorded: upload → run → review → fix & re-run → diff.

---

## Cut Order

Eight weeks leaves no slack. If a phase slips by more than three working days, cut in this order:

1. `cont.visual` (keep the continuity text rules).
2. Judge from a different model family (use same-family judge everywhere).
3. Helm/KubeRay (prove scale-out on one large multi-GPU cloud machine with `compose.yaml` instead).
4. German rule pack for `loc.formality` and `loc.gender` (keep Spanish and French).

**Never cut:** any of the four agents' deterministic checks, verification, the benchmark, and coverage-gap reporting.

---

## Milestones

| End of | Milestone | Demo |
|--------|-----------|------|
| Week 2 | Walking skeleton | Readability flags on a corpus film, planner decisions for three machines |
| Week 4 | Knowledge + rules | Benchmark v1; incremental re-run |
| Week 6 | All agents | Verified flags from all four agents; full benchmark |
| Week 8 | MVP | Review UI; same commit on laptop and cloud; per-Plan comparison |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| 8 GB VRAM too tight for the vision model at useful resolution | High | Continuity/clearance quality on the laptop | Staged mode, smaller variant, keyframe downscaling; judge quality on the cloud Plan; report per Plan |
| vLLM in Docker on WSL2 misbehaves on the laptop GPU | Medium | P1 serving delayed | Stub backends keep A unblocked; the serving layer runs any OpenAI-compatible server as a process, so another engine can be substituted for a variant without code changes elsewhere |
| The pinned vLLM lags a newly released model | Medium | Can't adopt a better model | Catalog validation excludes variants whose `min_vllm` is newer than the image; bump vLLM deliberately with a benchmark run |
| PaddlePaddle and PyTorch CUDA libraries conflict in the single image | Medium | OCR channel delayed | Fall back to RapidOCR (ONNX Runtime) for the `ocr` slot |
| Small-model extraction quality too low for Script Critic Layer 2 | Medium | Low recall on the laptop Plan | Constrained decoding, narrow per-scene prompts, grounding validator; evaluate targets on the cloud Plan |
| Corpus lacks multi-episode content with scripts | Medium | Weak cross-episode Script Critic evaluation | Supplement with synthetic multi-episode scripts with planted holes ([Evaluation](evaluation.md#corpus)) |
| Open-vocabulary detector misses logos | Medium | Low `clr.logo` recall | Planner can switch to vision-model-first sampling when throughput allows; tune prompts on injected logos |
| Cloud GPU cost | Low | Budget | Short benchmark windows, spot/preemptible capacity, autoscale to zero between runs |
| Scope creep | High | Missed week-8 exit | Cut order above; weekly benchmark as the forcing function |
| Corpus licensing | Low | Can't publish results | Manifest records license and attribution per title; injected real-brand material stays in private test data |
