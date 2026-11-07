# Engineering Journal

A dated, chronological record of what was done, what was measured, what broke, and how it was fixed. Newest entries go at the bottom. Numbers here are measurements or verified facts, with their source.

Related logs: [decisions.md](decisions.md) (why we chose things) and [experiments.md](experiments.md) (X vs Y comparisons).

---

### 2026-09-27 · Use-case review: the recap agent goes

- Reviewed the original problem statement. The first use case (episode recaps) was a generation feature in an otherwise error-finding pipeline, with no objective way to score it.
- Proposed a replacement, dependency-aware "Previously On" generation. The team rejected it as still not convincing.
- Compared four alternatives: localization QA, spoiler-safe marketing QA, ratings and compliance tagging, and on-screen clearance. Chose localization + clearance → [D-001](decisions.md#d-001--replace-the-recap-agent-with-two-qa-agents).

### 2026-09-27 · Dev machine inventory (measured)

| Component | Value | Source |
|-----------|-------|--------|
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU, 8,188 MiB, driver 610.62, compute capability 8.9 | `nvidia-smi` |
| Integrated GPU | AMD Radeon 780M | Windows device query |
| CPU | AMD Ryzen 7 7840HS, 8 cores / 16 threads | Windows device query |
| RAM | 31.2 GB | Windows device query |
| Disk free | D: 1,511 GB · C: 114 GB | Windows drive query |
| OS | Windows 11 Home | — |

Consequence: development hardware is a single 8 GB GPU, so stage-by-stage execution is the default there, and model weights and media must live on D:.

### 2026-09-27 · Design agreed, section by section

Six design sections were reviewed and approved in order: system overview, hardware-adaptive runtime, data layer, agents (two parts), verification and evaluation, and the build plan. Main outcomes:
- Ray + our own planner → [D-002](decisions.md#d-002--hardware-adaptive-runtime-ray--our-own-planner)
- Postgres + pgvector → [D-003](decisions.md#d-003--postgres--pgvector-instead-of-neo4j--qdrant)
- No orchestrator → [D-004](decisions.md#d-004--no-orchestrator-incremental-re-runs-from-a-content-hash-cache)
- Evidence-or-nothing → [D-005](decisions.md#d-005--no-output-without-evidence-verification-only-subtracts)
- Two orderings → [D-006](decisions.md#d-006--two-orderings-screen-order-and-story-order)
- Same-setup continuity comparison → [D-010](decisions.md#d-010--continuity-compares-same-setup-shots-not-adjacent-shots)

Team and timeline fixed at 2 people, 8 weeks.

### 2026-09-27 · Research findings that changed the design

Three research passes (models, test corpus and subtitle rules, infrastructure) were run before writing the docs. Findings that forced changes:

| Finding | Change |
|---------|--------|
| MinIO community edition archived (April 2026), no binaries since October 2025 | SeaweedFS → [D-013](decisions.md#d-013--seaweedfs-instead-of-minio) |
| Ray 2.58's Serve LLM pins vLLM 0.26; the default models need vLLM 0.30 | vLLM as a process → [D-014](decisions.md#d-014--vllm-as-a-process-inside-ray-serve-not-ray-serve-llm) |
| Qwen3.5 reads images natively; Qwen3.5-9B AWQ is 9.1 GB, Qwen3.5-4B AWQ is 4.0 GB | One multimodal model on the laptop → [D-015](decisions.md#d-015--one-multimodal-model-for-text-and-vision-on-small-gpus) |
| Gemma 4 is Apache-2.0 | Clean independent judge family → [D-008](decisions.md#d-008--judge-from-a-different-model-family) |
| Only Sintel and Tears of Steel have official es/fr/de subtitles; Agent 327 is CC BY-ND | Corpus choices → [D-012](decisions.md#d-012--test-corpus-open-films--public-domain-episodes--injected-errors) |
| Netflix style guide: 42 characters per line; 20 characters/second (English adult), 17 (es/fr/de adult); 5/6 s minimum and 7 s maximum duration; 2-frame minimum gap | Rule pack defaults → [D-011](decisions.md#d-011--mvp-languages-and-what-formality-checks-mean) |
| Only 555-0100 to 555-0199 is reserved for fiction; other 555 numbers returned to general use in 2016 | `clr.phone` treats other 555 numbers as real |
| Several candidate models have restrictive licenses (AGPL, non-commercial, revenue caps) | License allowlist → [D-016](decisions.md#d-016--license-allowlist-enforced-at-startup) |

### 2026-09-27 · Correction: subtitle drift estimate

- **Initial estimate (wrong):** 25 fps subtitles on 23.976 fps picture drift about 4 seconds by the end of an episode.
- **Verified:** the speed difference is 4.27% (25 vs 24000/1001), so subtitles run ≈ 2.46 s early per minute: **≈ 110.6 s (1 min 51 s) early after 45 minutes** of 23.976 runtime. A second, smaller case was also documented: confusing SMPTE-24 timecode with 23.976 media time drifts 0.1%, ≈ 2.7 s over 45 minutes.
- **Impact:** `loc.drift` looks for both slopes, and the injectors plant both.

### 2026-09-27 · Docs written and self-reviewed

- Wrote 8 docs (architecture, hardware adaptation, data model, tech stack, evaluation, phased plan, API contracts, project structure) and updated the README.
- **Link check.** A script checks every internal link, anchor, and code fence: 37 internal links, 0 broken. The checker itself was tested by planting a bad anchor and a missing file, and caught both.
- **Problems found and fixed during review:**
  - A nullable column inside a Postgres primary key (invalid) → defaulted to `'any'`.
  - An example phone number that could belong to a real person → masked.
  - Keycloak issuer mismatch between the browser and the API container → separate issuer and key URLs ([D-019](decisions.md#d-019--oidc-everywhere-with-separate-issuer-and-key-urls)).
  - Compose: containers only on an `internal` network can't publish ports, and that network blocked model downloads → removed; egress is blocked at the host/VPC instead.
  - A schema block closed early, leaving one table outside the SQL fence → fixed.
  - `NIP_PUBLIC_URL` used but never defined → added.
  - Subtitle refs tagged `es` vs `es-419` inconsistently, and no rule pack for plain `es` → tag fallback ([D-021](decisions.md#d-021--language-rule-packs-resolve-by-tag-fallback)).
- Docs committed by the team (`6e5d943`).

### 2026-10-02 · Phase 1 walkthrough

- Walked through every Phase 1 component, its purpose, and why each tool was chosen.
- Identified the single biggest unknown in the plan: whether `vllm serve` with `qwen3.5-4b-awq` starts inside Docker on the RTX 4060 under WSL2. Made it Person B's first task, with [EXP-001](experiments.md#exp-001--vllm-memory-headroom-on-the-laptop) to calibrate memory.

### 2026-10-06 · Measured idle VRAM on the dev laptop

- **Command:** `nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv`
- **Result:** 8,188 MiB total · 636 MiB used · **7,321 MiB free** (the remaining 231 MiB is reserved by the driver).
- **Why it matters:** the planner budgets against free memory. The earlier planning figure (6.9 GB) came from a Docker example on a different 8 GB card; the docs now use this measurement. Usable budget = min(0.90 × 8.0, 7.15 − 0.5 margin) = **6.65 GB**, so vLLM's `gpu_memory_utilization` ≈ 0.83. [EXP-001](experiments.md#exp-001--vllm-memory-headroom-on-the-laptop) confirms the value.
- **Caveat:** measured at idle. Free memory drops when other apps use the GPU, which is why the probe re-measures at every run.

### 2026-10-06 · Experiment tracking and tooling

- Added self-hosted MLflow for experiment tracking, reusing Postgres and SeaweedFS. Decided against a DAG tool and hosted trackers → [D-022](decisions.md#d-022--self-hosted-mlflow-for-experiments-no-dag-tool-no-hosted-trackers).
- Wrote the experiment backlog, EXP-001 to EXP-018, each with its success bar defined before running.
- Listed the full toolset, including the tools deliberately not used ([Tech Stack](tech-stack.md)).

### 2026-10-06 · Reuse-before-build audit

- **What:** four research passes checked every component we had planned to write ourselves against maintained open-source projects: media, subtitles, and scripts; LLM extraction, knowledge graphs, and sensitive-entity detection; runtime, queues, and cloud provisioning; labelling and UI. Candidate libraries were installed in scratch environments and tested on our edge cases.
- **Measured results:**

| Test | Result |
|------|--------|
| TTML timing, 6 cases (frame-rate multiplier, ticks, frame counts, SMPTE drop-frame, SMPTE 23.976 non-drop) | ttconv **6/6** · pycaption 4/6 (ignores `timeBase="smpte"`: 01:00:00:00 at 23.976 read as 3600.0 s instead of 3603.6 s) · pysubs2 0/6 |
| OpenTimelineIO frames → seconds → frames at 24000/1001, 200,000 frames | **11,541 off by one** (`to_frames()` truncates) |
| `timecode` package | Rounds 24000/1001 to 23.98; frames numbered from 1 |
| ffsubsync, subtitle track vs subtitle track | Recovered a +2.5 s offset, the 25/23.976 ratio, and an arbitrary 1.0123 scale exactly |
| Chrome seeking on a 23.976 fps clip, 150 random seeks | Frame middles **150/150** · exact frame starts 95/150 · frame start + 1 ms 150/150 · single-frame steps 60/60 · subtitle switch lag 6.6 ms median, 12.5 ms max |
| screenplay-tools reading FDX | Formatted words dropped: only the first text run of each paragraph is read |

- **Decisions:** [D-023](decisions.md#d-023--run-queue-pgqueuer-no-ray-jobs) to [D-030](decisions.md#d-030--test-oracles-and-copyleft-tools). [D-014](decisions.md#d-014--vllm-as-a-process-inside-ray-serve-not-ray-serve-llm) was re-examined against Ray Data and kept.
- **Versions noticed:** Ray 2.59.0 (2026-10-02) and vLLM 0.31.0 (2026-10-05) are out. The project stays on Ray 2.58 + vLLM 0.30 until a benchmark justifies the upgrade.
- **Privacy and license findings:**
  - MLflow has sent usage telemetry by default since version 3.2 → `MLFLOW_DISABLE_TELEMETRY=true`.
  - Presidio's email check downloads the public domain-suffix list unless `TLDEXTRACT_PUBLIC_SUFFIX_LIST_URLS=""` is set.
  - PyAV's wheels bundle GPL video encoders.
  - FiftyOne bundles MongoDB (SSPL license).
  - spaCy's Spanish models are GPL-3.0 and its French models LGPL-LR.
- **Next:** [EXP-001](experiments.md#exp-001--vllm-memory-headroom-on-the-laptop) now also checks that GPU memory returns to idle after a model is unloaded. [EXP-019](experiments.md#exp-019--license-plates-ocr--format-rules-vs-a-dedicated-plate-reader) waits for legal review of the plate reader's weights. [EXP-020](experiments.md#exp-020--entity-resolution-enum-constrained-ids-vs-fuzzy-matching-afterwards) was added.

### 2026-10-15 · Team size changed to one person

- **What:** The project became a solo build. Updated [phased-plan.md](phased-plan.md): the summary now reads *8 weeks, 1 person*; the Person A / Person B role table was removed, as was the `Owner` column from all four phase tables (34 rows). The "stubs keep people unblocked" working rule was reworded. README no longer says "for 2 people".
- **Decision:** Scope, phases, deliverables, exit criteria, cut order, and the risk register are **unchanged by explicit decision** — only the people count changed.
- **Open item:** 8 weeks × 2 people was 16 person-weeks. The same scope solo at the same weekly rate does not fit 8 calendar weeks, so either the calendar or the cut order absorbs the difference. Not resolved here; the weekly benchmark remains the forcing function.
- **Next:** The `cpu` profile stubs ([D-020](decisions.md#d-020--cpu-profile-with-recorded-model-outputs-for-ci)) carry more weight now. They existed so Person A wasn't blocked on Person B; solo, they are what keeps GPU bring-up from blocking check work.

---

## Entry Template

```markdown
### YYYY-MM-DD · <what happened, in a few words>

- **What:** what was done (command, change, or test).
- **Result:** the measured outcome, with units and source.
- **Problem / fix:** what broke, the root cause, and the fix (if anything broke).
- **Next:** follow-up, with links to EXP-0XX or D-0XX entries.
```
