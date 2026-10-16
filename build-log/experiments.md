# Build Experiments

Per-experiment record, alongside the design's planned experiments in [docs/experiments.md](../docs/experiments.md) (read-only). Two kinds of entries live here:

1. **Formal experiments** (`EXP-xxx`), written to the design's rules: one variable, numbers only from `nip eval compare` output, results reported for the Plan they were measured on. As of this writing no formal experiment has completed. Entries for EXP-001 and EXP-002 are in-progress stubs; results will be added when the runs finish.
2. **Build-time comparisons** (`C-xxx`): small "tried X, measured, switched to Y" comparisons made while building Phase 1 deliverables. They are not formal experiments (single runs, no seed sweep, synthetic data where stated) and they are labelled that way, but every number is a real measurement with its source. They are the raw material for interview stories about measurement-driven changes.

Related: [decisions.md](decisions.md) · [journal.md](journal.md) · [doc-corrections.md](doc-corrections.md).

## Index

| ID | Question | Phase | Status | Result | Decision |
|----|----------|:-----:|--------|--------|----------|
| [EXP-001](#exp-001--vllm-memory-headroom-on-the-laptop) | vLLM memory headroom on the laptop | 1 | in progress | pending | pending |
| [EXP-002](#exp-002--shot-detection-transnetv2-vs-pyscenedetect) | Shot detection: TransNetV2 vs PySceneDetect | 1 | in progress | pending | pending |
| [C-001](#c-001--decode-threads-for-torchcodec-1-vs-4-vs-8-vs-auto) | TorchCodec decode threads | 1 (1.8A) | done (build-time, synthetic clip) | 92.9 -> 433.0 fps | [B-028](decisions.md#b-028--num_ffmpeg_threads0-for-both-decoders) |
| [C-002](#c-002--mlflow-idle-memory-workers-and-memory-limit-vs-disabling-the-job-runner) | MLflow idle memory | 1 (1.5) | done | 2.223 -> 0.364 GiB | [B-033](decisions.md#b-033--mlflow-job-runner-off-one-worker-memory-limits) |
| [C-003](#c-003--hf-mem-kv-estimates-vs-the-docs-kv-figures) | hf-mem KV vs docs | 1 (1.6) | done (disagreement, unresolved) | 128 vs 60, 256 vs 160 MiB/1k | [B-043](decisions.md#b-043--hf-mem-is-used-only-for-missing-sizes-and-never-for-the-shipped-catalog) |
| [C-004](#c-004--planner-throughput-greedy-literal-vs-refined) | Planner throughput greedy | 1 (1.6) | done | 9b-fp8 -> 27b-int4 on 48 GB | [B-039](decisions.md#b-039--throughput-greedy-scoring-jump-moves-and-a-climb-back-pass) |
| [C-005](#c-005--independent-judge-vs-judge-reuse-in-throughput-mode) | Judge independence cost | 1 (1.6) | done | text 8k -> 16k, asr turbo -> large-v3 | [B-038](decisions.md#b-038--judge-selection-independent-family-else-reuse-and-in-throughput-mode-the-judge-must-not-downgrade-others) |
| [C-006](#c-006--free-vram-on-the-laptop-idle-doc-vs-desktop-apps-open) | Free VRAM: doc vs measured | 1 (1.6) | done | 7.15 -> 6.13 GB | [B-044](decisions.md#b-044--the-laptop-cannot-plan-an-llm-at-613-gb-free-exp-001-runs-before-the-walking-skeleton) |
| [C-007](#c-007--greedy-vs-optimal-flag-label-matching) | Greedy vs optimal matching | 1 (1.11) | done (constructed case) | 1 match vs 2 | [B-052](decisions.md#b-052--match-score-is-one-plus-overlap) |
| [C-008](#c-008--tp-attribution-label-side-only-vs-per-side) | TP attribution | 1 (1.11) | done (review) | inflated precision removed | [B-054](decisions.md#b-054--tp-attribution-is-per-side-for-equivalent-checks) |
| [C-009](#c-009--ways-to-guard-schemamigration-drift) | Schema drift guard | 1 (1.1) | done | 4/4 injected drifts caught | [B-005](decisions.md#b-005--migration-0001-is-frozen-raw-ddl-schemapy-is-core-drift-is-a-catalog-diff) |
| [C-010](#c-010--the-24-fps-surprise-is-23976-the-right-rate-for-the-test-films) | Frame rate of the test films | 1 (1.9) | done | 24/1, not 24000/1001 | [B-048](decisions.md#b-048--label-studio-frame-rate-is-templated-from-the-probed-rate-24-fps-films) |

---

# Formal experiments

## EXP-001 · vLLM memory headroom on the laptop

| | |
|--|--|
| **Question** | Which `gpu_memory_utilization` lets `qwen3.5-4b-awq` start reliably on the RTX 4060 while leaving the most KV cache? (from docs/experiments.md) |
| **Variants** | `gpu_memory_utilization` 0.75 · 0.80 · 0.83 · 0.86 · an exact KV-cache budget (`--kv-cache-memory-bytes`) sized by the planner |
| **Metrics** | Successful starts out of 10 · peak GPU memory (MiB) · maximum concurrent sequences at 8k context · tokens/s on a fixed prompt set · GPU memory after teardown (must return to idle) |
| **Success bar** | Highest setting with 10/10 starts becomes the laptop calibration; planner switches to exact KV budgets if they start as reliably and give at least as much KV cache |
| **Status** | **In progress.** Being run alongside deliverable 1.7 (Ray Serve + vLLM). No results yet; results, takeaway and decision link will be added here when the runs finish. |

**Why this is now the most urgent experiment (inputs already measured in completed Phase 1 work, not results of EXP-001):**

- The design's reference figure is 7,321 MiB free of 8,188 MiB at idle (docs journal, 2026-10-06), which the planner reads as 7.15 GB free.
- The 1.6 hardware probe on this laptop with normal desktop apps open read **6.44 GB, then 6.13 GB free** (about 1.5 GB held by roughly 40 Windows desktop apps; `nvidia-smi` showed 1,466 MiB used / 6,491 MiB free at the same moment). With the compose stack idle, nvidia-smi showed 1,507 MiB used before `up` and 1,515 MiB with the full stack up (1.5 deliverable), so the stack itself does not hold the GPU.
- At 6.13 GB free (usable 5.63 GB after the 0.5 GB margin), the planner skips text_llm, vlm and judge_llm: `qwen3.5-4b-awq` at 8k needs 6.14 GB (4.0 weights + 0.94 KV for 2 sequences + 1.2 overhead). The overhead (1.2 GiB), KV (60 MiB per 1k tokens, the doc's figure), `CONCURRENCY = 2` and margin (0.5 GB) are all unmeasured estimates ([B-036](decisions.md#b-036--planner-workload-units-and-the-concurrency-constant), [B-044](decisions.md#b-044--the-laptop-cannot-plan-an-llm-at-613-gb-free-exp-001-runs-before-the-walking-skeleton)). The reviewer showed `CONCURRENCY = 1` alone gives 4.0 + 0.47 + 1.2 = 5.67 GiB, still above 5.63.
- Open questions this experiment should settle: the real overhead, whether fp8 KV or exact KV budgets close the gap, and whether free VRAM read inside WSL/Docker matches the Windows host reading (not yet checked).
- The container side is ready: the `vllm/vllm-openai:v0.30.0` image is pulled (21.6 GB on disk; 1,168 s pull) and `nip:dev` builds on it (B-034), with ray-head configured with the WSL2 settings from the docs (`shm_size: 8gb`, `VLLM_WSL2_ENABLE_PIN_MEMORY=1`, `CUDA_DEVICE_ORDER=PCI_BUS_ID`).

## EXP-002 · Shot detection: TransNetV2 vs PySceneDetect

| | |
|--|--|
| **Question** | Is TransNetV2 accurate enough to justify a model over PySceneDetect's classical detectors? (from docs/experiments.md) |
| **Variants** | TransNetV2 · PySceneDetect `ContentDetector` (default threshold) · PySceneDetect `AdaptiveDetector` |
| **Metrics** | Cut-detection F1 with +-2-frame tolerance against hand-labelled cuts · seconds of processing per minute of video on the laptop |
| **Success bar** | Keep TransNetV2 only if its F1 beats the best PySceneDetect variant by >= 0.02; otherwise use the simpler one |
| **Status** | **In progress.** The detector, scorer and labelled data are being produced by deliverable 1.8 part B. No results yet; results will be added here. |

**What is already in place (completed deliverables, not results of EXP-002):**

- TransNetV2 pipeline from 1.8A: decode through TorchCodec exact mode with a 27x48 `Resize`, TransNetV2 from the `transnetv2-pytorch` 1.0.5 wheel, cuts and shots per [B-026](decisions.md#b-026--shot-boundary-semantics). Synthetic sanity checks only: cuts exactly at frames 60, 180, 228, 324 of a 424-frame clip; one 1 s `xfade` dissolve gave one cut at its middle frame (108). Speed: 1,030 fps and 198 MB peak VRAM on the RTX 4060 Laptop; decode 6.0 s per video-minute cold, 2.4 s warm after `num_ffmpeg_threads=0` ([C-001](#c-001--decode-threads-for-torchcodec-1-vs-4-vs-8-vs-auto)). The real-film speed per video-minute for the comparison is still to be measured.
- Known unmeasured risk: TransNetV2 was trained on `ffmpeg -s 48x27` input (bicubic), while TorchCodec's decoder `Resize` uses swscale bilinear + antialias; the effect is untested.
- PySceneDetect `ContentDetector` / `AdaptiveDetector` / fade detector: not built in 1.8 part A ([B-029](decisions.md#b-029--smaller-part-a-choices-on-keyframes-pillow-and-decode-tests)).
- Corpus (1.9): Sintel 1080p (21,312 frames at 24/1, 888.032 s) and Tears of Steel 720p (734.17 s at 24/1). The films are 24 fps, not 23.976 ([C-010](#c-010--the-24-fps-surprise-is-23976-the-right-rate-for-the-test-films)).
- Labels: the user does not know how to hand-label cuts, so labels are provisional agent labels by frame inspection, stored with `labeller: agent` ([B-051](decisions.md#b-051--provisional-agent-labels-for-exp-002)); a Label Studio project (15 sixty-second all-intra clips for Sintel) is prepared for a later human spot-check ([B-050](decisions.md#b-050--label-studio-project-design-all-intra-clips-with-overlap-and-local-files-serving)). **Consequence for interpretation:** the F1 will be biased by the labeller until a human check; the run must be repeated after it.
- Scoring: cuts are not Flags, so `eval/metrics.py` does not score them; 1.8 part B owns a cut-F1 scorer with a +-2 frame tolerance ([B-049](decisions.md#b-049--cut-labels-are-a-separate-json-file-not-flags)).

---

# Build-time comparisons

Each entry: what was compared, the numbers, what was chosen. Single runs unless stated. These are not formal experiments.

## C-001 · Decode threads for TorchCodec: 1 vs 4 vs 8 vs auto

- **Deliverable / source:** 1.8 part A, `notes/1.8.md`, commit `829a3b3`.
- **Setup:** synthetic 1080p H.264 clip (testsrc2, 2880 frames at 24000/1001, 77.7 MB, `-crf 23 -preset veryfast`), 600-frame timing loop, RTX 4060 Laptop host, TorchCodec exact seek mode. One run each; noise roughly +-10%.
- **Variable:** `num_ffmpeg_threads` (TorchCodec's default is 1).

| `num_ffmpeg_threads` | decode + `Resize` to 27x48 (fps) | full-resolution decode (fps) |
|---|---:|---:|
| 1 (default) | 92.9 | 114.2 |
| 4 | 404.6 | 361.1 |
| 8 | 452.8 | 491.4 |
| 0 (auto) | 433.0 | 416.7 |

- **End to end** (120.1 s of video): 1 thread 31.22 s (92.3 fps, 15.6 s per video-minute); auto 12.06 s cold (238.9 fps, 6.0 s per video-minute) and 4.73 s on a second call (608 fps, 2.4 s per video-minute; warm file cache). TransNetV2 itself ran at 1,030 fps (2.8 s for 2880 frames), peak VRAM 198 MB, model load 1.8 s.
- **Takeaway:** the default of 1 thread was 4.7x slower on this clip than auto. 8 threads was marginally faster than auto in this run (452.8 vs 433.0 fps, within noise), so auto was chosen. Extrapolation, not measurement: a 2 h film would take roughly 5 to 17 min of decode plus about 2 min of model time. testsrc2 is not film content; real numbers come with EXP-002.
- **Decision:** [B-028](decisions.md#b-028--num_ffmpeg_threads0-for-both-decoders).

## C-002 · MLflow idle memory: workers and memory limit vs disabling the job runner

- **Deliverable / source:** 1.5, `notes/1.5.md`, commit `1d1b9f9`. Measured with `docker stats`, idle.

| Variant | mlflow RAM |
|---|---:|
| Default image | 2.223 GiB |
| `--workers 1` + `mem_limit: 1g` (the controller's suggestion) | 1,015 MiB (of 1 GiB; cgroup `memory.events max` fired 4,322 times, no OOM kill) |
| `MLFLOW_SERVER_ENABLE_JOB_EXECUTION=false` + `--workers 1` + `mem_limit: 768m` | **364 MiB** |

- **Root cause found by looking in `/proc`:** MLflow 3.x's background job runner starts about 6 `huey_consumer` processes at about 220 MiB RSS each; it is not gunicorn workers, so the suggested `--workers 1` could not help.
- **Result:** about 6x lower idle memory. Whole stack idle after the change: ray-head 1.133 GiB, keycloak 833 MiB, mlflow 364 MiB, objectstore 155 MiB, api 113 MiB, postgres 35 MiB (about 2.6 GiB total); host `vmmemWSL` working set 4.7 GB.
- **Decision:** [B-033](decisions.md#b-033--mlflow-job-runner-off-one-worker-memory-limits).

## C-003 · hf-mem KV estimates vs the docs' KV figures

- **Deliverable / source:** 1.6, `notes/1.6.md`. hf-mem 0.5.6 with `experimental=True, max_model_len=1024, batch_size=1`, bf16 KV; 18 repos tried, 16 worked, 0.5 to 2.6 s each, no weights downloaded.
- **Comparison:**

| Model | docs KV (MiB per 1k tokens) | hf-mem KV (MiB per 1k tokens) |
|---|---:|---:|
| Qwen3.5-4B | 60 | 128 |
| Qwen3.8-27B | 160 | 256 |
| gemma-4-31B | not given | 960 (looks high) |

- **Hypothesis (not verified):** Qwen3.5/3.8 mix linear-attention and full-attention layers and hf-mem counts every layer as full attention; gemma-4 has sliding-window layers. hf-mem also failed on faster-whisper (CTranslate2, no safetensors) and RedHatAI/Qwen3.8-27B-INT4 (refuses `kv_cache_dtype=auto` for compressed-tensors).
- **Takeaway / decision:** keep the docs' 60 and 160 where given, use hf-mem only where the docs give nothing ([B-043](decisions.md#b-043--hf-mem-is-used-only-for-missing-sizes-and-never-for-the-shipped-catalog)). A measured peak after first load (EXP-001, calibration) will replace all of these. Until then the laptop KV term is the unmeasured one.

## C-004 · Planner throughput greedy: literal vs refined

- **Deliverable / source:** 1.6, `notes/1.6.md`, commit `28e859f`. Inventory: 1x 48 GB, objective throughput.

| Version of the greedy | Result for text_llm | Why |
|---|---|---|
| Literal (smallest quality loss per GiB freed, step to the next candidate only) | stuck, then `qwen3.5-9b-fp8` + ministral | only about 1 GB was missing, but dropping text_llm to 4b frees 18 GB and so "costs" least per GB; climb-back stopped at 9b-fp8 |
| Next-candidate-only moves | got stuck | candidates are ordered by quality not memory, so the next candidate can be bigger (27b-int4@8k -> 35b-a3b@32k) |
| Divisor `min(freed, shortfall)` + jump to any lower candidate + climb-back | **`qwen3.8-27b-int4`** (rank 65 instead of 45) with whisper turbo, embedding 0.6b, ministral | counts only the GiB that help |

- The 8x 80 GB throughput result did not change (the sum already fits there; GPU count binds). Hand check: 24.5 + 6.51 + 11.7 = 42.71 <= 43.19 usable.
- **Decision:** [B-039](decisions.md#b-039--throughput-greedy-scoring-jump-moves-and-a-climb-back-pass).

## C-005 · Independent judge vs judge reuse in throughput mode

- **Deliverable / source:** 1.6 review I-1 (reviewer ran both) and fix `3cf18c7`. Inventory 1x 48 GB, throughput.

| | text_llm | asr | judge |
|---|---|---|---|
| Independent judge in the greedy (original) | qwen3.8-27b-int4 at **8k** | whisper-turbo | ministral-3-3b-fp8 |
| Judge variants removed (reuse) / after the controller ruling | qwen3.8-27b-int4 at **16k** (gmu 0.57) | whisper large-v3 | reuses text_llm (`independent_family: false`) |

- **Takeaway:** the independent judge cost text_llm half its context and cost asr its better variant. The docs' step 7 forbade that, while the docs' own example did it, so the spec contradicted itself; the controller picked step 7 over the example.
- **Decision:** [B-038](decisions.md#b-038--judge-selection-independent-family-else-reuse-and-in-throughput-mode-the-judge-must-not-downgrade-others). The follow-up test `test_throughput_judge_never_pushes_other_slots_down` compares every non-judge slot with and without judge variants across all three inventories.

## C-006 · Free VRAM on the laptop: idle (doc) vs desktop apps open

| Source | Free VRAM |
|---|---:|
| docs journal 2026-10-06 (idle) | 7,321 MiB of 8,188 MiB = 7.15 GB |
| 1.6 probe, first run, 2026-10-16 | 6.44 GB |
| 1.6 probe, later run, 2026-10-16 | 6.13 GB (`nvidia-smi`: 1,466 MiB used, 6,491 MiB free, held by about 40 desktop apps) |

- **Takeaway:** the planner's laptop result flips from "staged with a 4b model" to "no LLM fits" between the two figures. Free VRAM inside WSL/Docker is not yet measured. Feeds EXP-001; see [B-044](decisions.md#b-044--the-laptop-cannot-plan-an-llm-at-613-gb-free-exp-001-runs-before-the-walking-skeleton).

## C-007 · Greedy vs optimal flag-label matching

- **Deliverable / source:** 1.11, `test_matching_is_optimal_not_greedy`. A constructed case where greedy-by-best-overlap finds 1 match and `linear_sum_assignment` finds 2.
- **Second comparison (reasoned, then fixed before coding):** maximising the plain sum of overlap scores can drop a match for a high-overlap pair; scoring each valid pair `1 + overlap` maximises match count first.
- **Decision:** [B-052](decisions.md#b-052--match-score-is-one-plus-overlap). Not a measurement on real data: no real benchmark flags exist yet.

## C-008 · TP attribution: label-side only vs per-side

- **Deliverable / source:** 1.11 review I-1 and fix `159b005`. A `cont.prop_text` flag matching a `plot.prop_provenance` label was booked as a TP only under `plot.prop_provenance`: that check's precision rose (cont.* flags counted for it) and `cont.prop_text` showed no TP and no FP. After the fix each pair books a precision-side TP under the flag's check and a recall-side `found` under the label's check; global P and R are unchanged. Test: `test_equivalence_match_is_attributed_per_side`.
- **Side effect:** per-check recall for `cont.prop_text` now reads 0.0 even though its flag was a TP (intended; documented in the review).
- **Decision:** [B-054](decisions.md#b-054--tp-attribution-is-per-side-for-equivalent-checks).

## C-009 · Ways to guard schema/migration drift

- **Deliverable / source:** 1.1 fix round, commit `c1a8853`.

| Approach | Catches | Verdict |
|---|---|---|
| Table-name comparison (original CI) | missing/extra tables only | insufficient (review Important) |
| Parse columns out of the offline SQL | names and types; no constraints | needs a DDL parser, rejected |
| `compare_metadata(compare_server_default=True)` | columns, types, defaults | still blind to CHECK, identity ALWAYS vs BY DEFAULT, EXCLUDE; rejected |
| Diff two real Postgres catalogs (`alembic upgrade head` vs `metadata.create_all`) | columns, defaults, identity, every constraint, every index, extensions | chosen |

- **Proof the guard has teeth:** four injected drifts, each caught: changed server default (`episode.timeline_source` -> `'picture'`) and identity ALWAYS -> BY DEFAULT ("only in migration: columns"), changed CHECK (`BETWEEN 1 AND 6`) and dropped `fact_consolidated_no_overlap` ("only in migration: constraints"). The unmodified pair already matched on the first run (1 passed in 11.95 s).
- **Decision:** [B-005](decisions.md#b-005--migration-0001-is-frozen-raw-ddl-schemapy-is-core-drift-is-a-catalog-diff).

## C-010 · The 24 fps surprise: is 23.976 the right rate for the test films?

- **Deliverable / source:** 1.9, `ffprobe` on the downloaded files.
- **Docs' assumption:** the test films run at 23.976 fps (Label Studio config `23.976023976`; the `loc.drift` injector's 25025/24000 rescale).
- **Measured:** Sintel `r_frame_rate=24/1`, `avg_frame_rate=24/1`, 21,312 frames, 888.032 s. Tears of Steel `24/1`, 734.17 s (h264 1280x534).
- **Why it matters:** a 25 fps subtitle confusion against 24 fps picture is 25/24 = 4.17%, not the 4.27% the docs derived for 23.976; and Label Studio would read 23.976 as 24 and shift labels (the phased-plan risk row rated High if unnoticed).
- **Cross-check on the label mapping:** for global frame 3000, PSNR of the clip's LS-frame-122 against source frames 2999/3000/3001 was 31.7 / 38.2 / 32.1 dB, so the offset arithmetic is exact.
- **Decision:** [B-048](decisions.md#b-048--label-studio-frame-rate-is-templated-from-the-probed-rate-24-fps-films).
