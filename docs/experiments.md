# Experiment Log

Every comparison we run (X vs Y) is written down here **before** it runs, then completed with measured results. Failed and inconclusive experiments stay in the log: knowing what didn't work is part of the record.

Related logs: decisions an experiment led to are in [decisions.md](decisions.md); day-to-day events and fixes are in [journal.md](journal.md).

---

## How We Run Experiments

1. **Write the entry first** (status `planned`): the question, the variants, the single variable being changed, the metrics, the success bar, the benchmark set, and the Plan.
2. **Run each variant** on the same commit and Plan, changing only the variable under test:
   ```bash
   nip eval run --set mvp --exp EXP-009 --variant same_setup --seeds 1,2,3
   ```
   Every run is logged to MLflow with its commit, Plan fingerprint, model variants, prompt versions, thresholds, and seed.
3. **Generate the results table**, and paste it unedited:
   ```bash
   nip eval compare --exp EXP-009 --md
   ```
   It reports mean ± standard deviation across seeds, with the MLflow run IDs behind every number.
4. **Write the takeaway** and link the decision it led to (`D-0XX`). Set status to `done` or `inconclusive`.

### Rules

- One variable per experiment. Everything else (commit, benchmark set, Plan, seeds) stays fixed.
- At least 3 seeds whenever error injection or sampling is random.
- Model calls use temperature 0 unless the experiment is about sampling.
- **Numbers come only from `nip eval compare` output.** Nothing in a results table is typed by hand.
- Results are reported for the Plan they were measured on; a laptop result is never presented as a cloud result.

---

## Index

| ID | Question | Phase | Status | Result | Decision |
|----|----------|:-----:|--------|--------|----------|
| [EXP-001](#exp-001--vllm-memory-headroom-on-the-laptop) | vLLM memory headroom on the laptop | 1 | planned | — | — |
| [EXP-002](#exp-002--shot-detection-transnetv2-vs-pyscenedetect) | Shot detection: TransNetV2 vs PySceneDetect | 1 | planned | — | — |
| [EXP-003](#exp-003--speech-to-text-whisper-large-v3-vs-large-v3-turbo) | Speech-to-text: Whisper large-v3 vs turbo | 2 | planned | — | — |
| [EXP-004](#exp-004--script-to-transcript-alignment-method) | Script-to-transcript alignment method | 2 | planned | — | — |
| [EXP-005](#exp-005--fact-extraction-context-8k-vs-32k-tokens) | Fact extraction context: 8k vs 32k | 2 | planned | — | D-015 |
| [EXP-006](#exp-006--grounding-validator-threshold) | Grounding validator threshold | 2 | planned | — | D-005 |
| [EXP-007](#exp-007--story-order-rules-only-vs-rules--llm) | Story order: rules only vs rules + LLM | 2 | planned | — | D-006 |
| [EXP-008](#exp-008--keyframe-density-for-on-screen-text) | Keyframe density for on-screen text | 2 | planned | — | — |
| [EXP-017](#exp-017--ocr-engine-vs-reading-text-with-the-vision-model) | OCR engine vs vision model for on-screen text | 2 | planned | — | — |
| [EXP-018](#exp-018--kv-cache-precision-on-the-laptop) | KV-cache precision on the laptop | 2 | planned | — | — |
| [EXP-020](#exp-020--entity-resolution-enum-constrained-ids-vs-fuzzy-matching-afterwards) | Entity resolution: enum IDs vs fuzzy matching afterwards | 2 | planned | — | D-025 |
| [EXP-009](#exp-009--continuity-pre-filter-adjacent-shots-vs-same-setup-shots) | Continuity pre-filter: adjacent vs same-setup | 3 | planned | — | D-010 |
| [EXP-010](#exp-010--setup-clustering-dinov2-vs-siglip-2) | Setup clustering: DINOv2 vs SigLIP 2 | 3 | planned | — | D-018 |
| [EXP-011](#exp-011--logo-channel-detector-gated-vs-every-keyframe) | Logo channel: detector-gated vs every keyframe | 3 | planned | — | — |
| [EXP-012](#exp-012--locgender-prompt-direct-question-vs-structured-extraction) | `loc.gender` prompt: direct vs structured | 3 | planned | — | — |
| [EXP-013](#exp-013--judge-same-family-vs-different-family) | Judge: same family vs different family | 3 | planned | — | D-008 |
| [EXP-014](#exp-014--structured-output-json-schema-decoding-vs-prompt-only) | Structured output: schema decoding vs prompt-only | 3 | planned | — | — |
| [EXP-019](#exp-019--license-plates-ocr--format-rules-vs-a-dedicated-plate-reader) | License plates: OCR + format rules vs a plate reader | 3 | planned (blocked on legal review) | — | D-026 |
| [EXP-015](#exp-015--planner-objective-on-a-cloud-node-quality-vs-throughput) | Planner objective on a cloud node | 4 | planned | — | D-002 |
| [EXP-016](#exp-016--same-commit-laptop-vs-cloud) | Same commit: laptop vs cloud | 4 | planned | — | D-002 |

---

## Phase 1

### EXP-001 · vLLM memory headroom on the laptop

| | |
|--|--|
| **Question** | Which `gpu_memory_utilization` lets `qwen3.5-4b-awq` start reliably on the RTX 4060 while leaving the most KV cache? |
| **Background** | Idle free VRAM measured at 7,321 MiB of 8,188 MiB on 2026-10-06 ([journal](journal.md#2026-10-06--measured-idle-vram-on-the-dev-laptop)). vLLM aborts at startup if free memory is below what it requests. |
| **Variants** | `gpu_memory_utilization` 0.75 · 0.80 · 0.83 · 0.86 · an exact KV-cache budget (`--kv-cache-memory-bytes`) sized by the planner |
| **Metrics** | Successful starts out of 10 · peak GPU memory (MiB) · maximum concurrent sequences at 8k context (from vLLM's startup log) · tokens/s on a fixed prompt set · GPU memory after the deployment is deleted (`nvidia-smi`: must return to the idle level, or the next stage group can't load) |
| **Success bar** | The highest setting with 10/10 successful starts becomes the laptop calibration; the planner switches to exact KV budgets if they start as reliably and give at least as much KV cache. Memory must return to idle after every teardown |
| **Set / Plan** | Serving test, no benchmark set · laptop |
| **Status** | planned |

### EXP-002 · Shot detection: TransNetV2 vs PySceneDetect

| | |
|--|--|
| **Question** | Is TransNetV2 accurate enough to justify a model over PySceneDetect's classical detectors? |
| **Variants** | TransNetV2 · PySceneDetect `ContentDetector` (default threshold) · PySceneDetect `AdaptiveDetector` |
| **Metrics** | Cut-detection F1 with ±2-frame tolerance against hand-labelled cuts · seconds of processing per minute of video on the laptop |
| **Success bar** | Keep TransNetV2 only if its F1 beats the best PySceneDetect variant by ≥ 0.02; otherwise use the simpler one |
| **Set / Plan** | Sintel and Tears of Steel with hand-labelled cuts · laptop |
| **Status** | planned |

---

## Phase 2

### EXP-003 · Speech-to-text: Whisper large-v3 vs large-v3-turbo

| | |
|--|--|
| **Question** | Can the laptop use the faster turbo model without losing transcript quality? |
| **Variants** | `faster-whisper-large-v3-int8` · `faster-whisper-large-v3-turbo-int8` |
| **Metrics** | Word error rate against human-corrected transcripts · real-time factor · peak VRAM |
| **Success bar** | Turbo becomes the laptop default if its WER is within +1.0 point and it is ≥ 1.5× faster |
| **Set / Plan** | English dialogue in `mvp` · laptop |
| **Status** | planned |

### EXP-004 · Script-to-transcript alignment method

| | |
|--|--|
| **Question** | Which alignment places script lines on the right frames most often? |
| **Variants** | Token-level monotonic alignment · line-level fuzzy matching (rapidfuzz) |
| **Metrics** | Share of script lines whose aligned start is within ±12 frames (0.5 s at 24 fps) of a hand-marked start |
| **Success bar** | ≥ 95% within tolerance |
| **Set / Plan** | 3 titles with hand-marked line starts · laptop |
| **Status** | planned |

### EXP-005 · Fact extraction context: 8k vs 32k tokens

| | |
|--|--|
| **Question** | Does giving the extractor neighbouring scenes improve facts enough to matter, given the laptop is capped at 8k context? |
| **Variants** | 8k (scene + bible entries) · 32k (scene + two neighbours on each side + bible entries), same model, on a GPU where 32k fits |
| **Metrics** | Fact precision and recall against hand-labelled facts (3 episodes) · downstream recall of the Layer 1 `plot.*` rules |
| **Success bar** | Keep 8k everywhere if 32k improves fact recall by less than 2 points |
| **Set / Plan** | 3 Beverly Hillbillies episodes with labelled facts · workstation or cloud |
| **Status** | planned |

### EXP-006 · Grounding validator threshold

| | |
|--|--|
| **Question** | How strict should the quote check be before a fact is dropped? |
| **Variants** | Fuzzy-match threshold 85 · 90 · 95 (rapidfuzz partial ratio) |
| **Metrics** | Share of true facts wrongly dropped · share of hallucinated facts kept, on a hand-labelled sample of 300 extracted facts |
| **Success bar** | ≤ 2% true facts dropped and ≤ 1% hallucinated facts kept; choose the highest threshold that meets both |
| **Set / Plan** | Extraction output from EXP-005's episodes · laptop |
| **Status** | planned |

### EXP-007 · Story order: rules only vs rules + LLM

| | |
|--|--|
| **Question** | Does sending ambiguous scene transitions to the LLM improve story order enough to justify the calls? |
| **Variants** | Rules only · rules + LLM for ambiguous transitions |
| **Metrics** | Pairwise order agreement (Kendall tau) against hand-labelled story order · precision of `plot.knowledge_order` and `plot.dead_acts` |
| **Success bar** | Keep the LLM step if rule precision rises by ≥ 3 points |
| **Set / Plan** | 6 Beverly Hillbillies episodes + the synthetic show · laptop |
| **Status** | planned |

### EXP-008 · Keyframe density for on-screen text

| | |
|--|--|
| **Question** | How many keyframes per shot does the clearance scanner need to catch on-screen text? |
| **Variants** | 1 per shot · 1 per shot + 1 every 2 s in shots over 4 s · 1 per shot + 1 every 1 s |
| **Metrics** | Recall of `clr.phone`, `clr.url`, `clr.email`, `clr.address`, `clr.plate`, `clr.brand_text` · keyframes per minute (drives OCR cost) |
| **Success bar** | A denser policy is kept only if recall rises ≥ 5 points for ≤ 50% more keyframes |
| **Set / Plan** | `mvp` · laptop |
| **Status** | planned |

### EXP-017 · OCR engine vs reading text with the vision model

| | |
|--|--|
| **Question** | Is a dedicated OCR model worth running when the vision model can read text too? |
| **Variants** | `pp-ocrv6-medium` · `qwen3.5-4b-awq` reading each keyframe |
| **Metrics** | Recall of the on-screen text checks · GPU-seconds per content-hour |
| **Success bar** | Keep PP-OCR unless the vision model's recall is ≥ 10 points higher |
| **Set / Plan** | `mvp` · laptop |
| **Status** | planned |

### EXP-018 · KV-cache precision on the laptop

| | |
|--|--|
| **Question** | Can an FP8 KV cache let the laptop run 16k context without hurting extraction? |
| **Variants** | Default KV cache at 8k · FP8 KV cache at 8k · FP8 KV cache at 16k |
| **Metrics** | Largest context that starts reliably · fact precision and recall |
| **Success bar** | Adopt FP8 if F1 drops by ≤ 0.01 and context doubles |
| **Set / Plan** | EXP-005's episodes · laptop |
| **Status** | planned |


### EXP-020 · Entity resolution: enum-constrained IDs vs fuzzy matching afterwards

| | |
|--|--|
| **Question** | Is it better to let the model pick registry IDs during extraction ([D-025](decisions.md#d-025--structured-extraction-instructor--our-quote-check-registry-ids-as-an-enum)) or to resolve free-text names afterwards? |
| **Variants** | Registry IDs as an enum in the extraction schema · free-text names resolved afterwards with rapidfuzz against the alias table |
| **Metrics** | Resolution accuracy against hand-labelled mentions (nicknames, titles, descriptions such as "the informant") · precision of the Layer 1 `plot.*` rules |
| **Success bar** | Keep the enum if its accuracy is at least as high and rule precision doesn't drop |
| **Set / Plan** | 3 Beverly Hillbillies episodes + the synthetic show, mentions labelled in Label Studio · laptop |
| **Status** | planned |

---

## Phase 3

### EXP-009 · Continuity pre-filter: adjacent shots vs same-setup shots

| | |
|--|--|
| **Question** | Does comparing same-setup shots ([D-010](decisions.md#d-010--continuity-compares-same-setup-shots-not-adjacent-shots)) beat the old adjacent-shot filter? |
| **Variants** | Adjacent-shot embedding distance (old design) · same-setup comparison |
| **Metrics** | `cont.visual` precision, recall, F1 · vision-model calls per episode |
| **Success bar** | Same-setup recall ≥ adjacent recall, with ≤ 50% of the calls |
| **Set / Plan** | `mvp` with visual injections · laptop, repeated on cloud in Phase 4 |
| **Status** | planned |

### EXP-010 · Setup clustering: DINOv2 vs SigLIP 2

| | |
|--|--|
| **Question** | Which image embedder groups shots by camera setup more accurately ([D-018](decisions.md#d-018--dinov2-for-camera-setup-similarity))? |
| **Variants** | `dinov2-large` · SigLIP 2 so400m |
| **Metrics** | Adjusted Rand index against hand-labelled setups (≈ 40 scenes from 2 films) · downstream `cont.visual` F1 |
| **Success bar** | Keep DINOv2 unless SigLIP 2 is ≥ 0.05 ARI better |
| **Set / Plan** | Sintel + Tears of Steel with labelled setups · laptop |
| **Status** | planned |

### EXP-011 · Logo channel: detector-gated vs every keyframe

| | |
|--|--|
| **Question** | How much recall does gating the vision model behind the cheap detector cost? |
| **Variants** | Vision model only on keyframes where the detector proposes candidates · vision model on every keyframe |
| **Metrics** | Recall of `clr.logo` and `clr.artwork` · vision-model calls · GPU-seconds per content-hour |
| **Success bar** | Gating keeps ≥ 90% of the ungated recall at ≤ 30% of the calls |
| **Set / Plan** | `mvp` with logo injections · laptop |
| **Status** | planned |

### EXP-012 · `loc.gender` prompt: direct question vs structured extraction

| | |
|--|--|
| **Question** | With small models, is it better to ask the question directly or extract structure and let a rule decide? |
| **Variants** | (A) Ask whether the translation assigns the wrong gender · (B) Model lists each referent and the gender the translation marks; a rule compares with the registry |
| **Metrics** | Precision, recall, F1 per language (es, fr, de) · invalid-output rate |
| **Success bar** | Adopt B if F1 improves by ≥ 0.05 on the laptop Plan |
| **Set / Plan** | `mvp` localization injections · laptop |
| **Status** | planned |

### EXP-013 · Judge: same family vs different family

| | |
|--|--|
| **Question** | Does an independent-family judge ([D-008](decisions.md#d-008--judge-from-a-different-model-family)) remove more false positives without losing true ones? |
| **Variants** | Laptop: judge reuses `qwen3.5-4b-awq` · `ministral-3-3b-fp8`. Workstation: Qwen judge · `gemma-4-12b-qat` |
| **Metrics** | Share of false positives dropped · share of true positives wrongly dropped |
| **Success bar** | Independent judge adopted if it drops more false positives while losing ≤ 5% of true positives |
| **Set / Plan** | `mvp` · laptop and workstation |
| **Status** | planned |

### EXP-014 · Structured output: JSON-schema decoding vs prompt-only

| | |
|--|--|
| **Question** | How much does constrained decoding reduce invalid model outputs, and what does it cost? |
| **Variants** | JSON-schema `response_format` · instructions-only JSON with validation and repair |
| **Metrics** | Invalid-output rate · repair attempts per 1,000 calls · F1 · latency per call |
| **Success bar** | Schema decoding stays the default if invalid outputs fall ≥ 90% with < 15% latency increase |
| **Set / Plan** | `mvp` · laptop |
| **Status** | planned |


### EXP-019 · License plates: OCR + format rules vs a dedicated plate reader

| | |
|--|--|
| **Question** | Does a dedicated plate detector find plates that general OCR plus plate-format rules miss ([D-026](decisions.md#d-026--clearance-text-detection-presidio--gliner--urlextract))? |
| **Variants** | PP-OCR text + Presidio plate-format recognizers · fast-alpr (only after legal approves how its weights were trained) |
| **Metrics** | `clr.plate` recall and precision · GPU-seconds per content-hour |
| **Success bar** | Add fast-alpr only if recall rises by ≥ 15 points |
| **Set / Plan** | `mvp` with plate injections · laptop |
| **Status** | planned (blocked on legal review) |

---

## Phase 4

### EXP-015 · Planner objective on a cloud node: quality vs throughput

| | |
|--|--|
| **Question** | On an 8× 80 GB node, how much quality does the faster objective give up? |
| **Variants** | `quality` (Qwen3.5-397B FP8, staged) · `throughput` (Qwen3.5-122B Int4 replicas, resident) |
| **Metrics** | F1 per check · GPU-seconds per content-hour · wall time per 45-minute episode |
| **Success bar** | Make `throughput` the cloud default if mean F1 drops by ≤ 0.02 |
| **Set / Plan** | `mvp` · cloud node |
| **Status** | planned |

### EXP-016 · Same commit: laptop vs cloud

| | |
|--|--|
| **Question** | What does each hardware Plan actually deliver, from the identical release? This is the headline hardware-adaptation result. |
| **Variants** | Laptop Plan · cloud Plan, same commit and config; the Plans differ only by what the probe found |
| **Metrics** | F1 per check · GPU-seconds and wall time per content-hour |
| **Success bar** | None: a measurement, reported as is. Required by the [Phase 4 exit criteria](phased-plan.md#phase-4--review-scale-out-hardening-weeks-78) |
| **Set / Plan** | `mvp` · laptop and cloud |
| **Status** | planned |

---

## Entry Template

````markdown
### EXP-0XX · <question in a few words>

| | |
|--|--|
| **Question** | What we want to know, as one question |
| **Variants** | X · Y (only one variable differs) |
| **Metrics** | What is measured, and against which ground truth |
| **Success bar** | The result that would change what we do |
| **Set / Plan** | Benchmark set · Plan it runs on |
| **Status** | planned / running / done / inconclusive |

**Results** (pasted from `nip eval compare --exp EXP-0XX --md`):

| Variant | Runs (MLflow) | Seeds | Precision | Recall | F1 | GPU-s / content-hour | Wall time |
|---------|---------------|-------|-----------|--------|----|----------------------|-----------|

**Takeaway.** One or two sentences: what we learned, including surprises.

**Decision.** D-0XX, or "no change".
````
