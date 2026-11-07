# Build Experiments

Per-experiment record, alongside the design's planned experiments in [docs/experiments.md](../docs/experiments.md) (read-only). Two kinds of entries live here:

1. **Formal experiments** (`EXP-xxx`), written to the design's rules: one variable, numbers only from `nip eval compare` output, results reported for the Plan they were measured on. Both Phase 1 experiments have been run, and Phase 2 ran EXP-003 to EXP-008, EXP-017, EXP-018 and EXP-020 (the knowledge ones on the synthetic show, ruling R3; EXP-005's 32k arm deferred, R4). EXP-001 is done; EXP-002 is partly run and its result is provisional (agent-made labels, Sintel only). Each entry below states what was measured, where the evidence is, and what changed in the code because of it.
2. **Build-time comparisons** (`C-xxx`): small "tried X, measured, switched to Y" comparisons made while building deliverables (C-001 to C-019 in Phase 1, C-020 onward in Phase 2). They are not formal experiments (single runs, no seed sweep, synthetic data where stated) and they are labelled that way, but every number is a real measurement with its source. They are the raw material for interview stories about measurement-driven changes.

Related: [decisions.md](decisions.md) · [journal.md](journal.md) · [doc-corrections.md](doc-corrections.md).

## Index

| ID | Question | Phase | Status | Result | Decision |
|----|----------|:-----:|--------|--------|----------|
| [EXP-001](#exp-001--vllm-memory-headroom-on-the-laptop) | vLLM memory headroom on the laptop | 1 | done | gmu 0.75/0.83 start 0/3 under Windows VRAM pressure, 0.86 3/3 at 1.52 seqs, exact KV 3/3 at 2.64 seqs; idle: all 10/10 | [B-083](decisions.md#b-083--exact-kv-budgets-on-single-gpu-engines-sized-by-the-planner-from-probed-free-vram) (controller ruling: exact KV, against the written bar) |
| [EXP-002](#exp-002--shot-detection-transnetv2-vs-pyscenedetect) | Shot detection: TransNetV2 vs PySceneDetect | 1 | partly run (Sintel, agent labels) | F1 0.917 / 0.839 / 0.880 at defaults; verdict flips with tuning (TransNetV2 +0.037 at defaults, Adaptive +0.021 tuned and +0.016 held out) | [B-093](decisions.md#b-093--exp-002-decision-keep-transnetv2-provisionally-as-a-costrisk-call-not-a-result) (provisional) |
| [EXP-003](#exp-003--speech-to-text-whisper-large-v3-vs-large-v3-turbo) | Speech-to-text: Whisper large-v3 vs large-v3-turbo | 2 | done (2 rounds + controller ruling on decoding) | round 1 unfair (T=0 loops: 0.815 vs 0.574); equal decoding: parity (fb-p50 0.555 vs 0.543, novad-hst 0.604 vs 0.606), turbo 2.3-3.2x faster, about half the VRAM | [B-220](decisions.md#b-220--laptop-asr-default-is-faster-whisper-large-v3-turbo-int8), [B-222](decisions.md#b-222--asr-decoding-default-is-the-deterministic-novad-hst-arm) (controller ruling: novad-hst) |
| [EXP-004](#exp-004--script-to-transcript-alignment-token-level-monotonic-vs-rapidfuzz-line-level) | Script-to-transcript alignment: token vs line-level | 2 | done, bar not met (agent labels from SRT cue starts) | within +-12 f: token 0.68 vs line 0.51 with the first-word cap (0.46 vs 0.37 without); bar 0.95 | [B-223](decisions.md#b-223--token-level-alignment-is-the-default-with-a-03-s-first-word-cap) |
| [EXP-005](#exp-005--fact-extraction-context-8k-vs-32k-tokens) | Fact extraction context: 8k vs 32k | 2 | inconclusive (8k arm only; 32k deferred, R4) | 8k: fact P 0.75 ± 0.03, R 0.77 ± 0.04, plot-rule recall 0.03 (0.28 after 2.1B fix round 1) | [B-182](decisions.md#b-182--exp-005-8k-arm-only-inconclusive-until-the-32k-arm-runs) |
| [EXP-006](#exp-006--grounding-validator-threshold) | Grounding validator threshold | 2 | done, bar not met | 85/90/95: hallucinated kept 0.93, true dropped 0.00; + argument checks: 0.27 / 0.007 | [B-163](decisions.md#b-163--exp-006-first-wave-keep-threshold-90-the-bar-is-not-met-by-any-threshold), [B-181](decisions.md#b-181--exp-006-ship-the-argument-checks-the-bar-is-still-not-met) |
| [EXP-007](#exp-007--story-order-rules-only-vs-rules--llm) | Story order: rules only vs rules + LLM | 2 | done on synthetic (real content deferred, R3) | ambiguous variant: pooled P(dead_acts + knowledge_order) 0.60 rules / 0.78 v1 / 0.90 v2, tau 0.870 / 0.892 / 0.983; v1 dead_acts recall 0.56; base show: 0 LLM calls, all 1.00; v2 = ceiling for templated cues | [B-196](decisions.md#b-196--exp-007-decision-keep-the-llm-step-with-prompt-v2-bible-overrides-first), [B-195](decisions.md#b-195--storyprompt-is-v2) (controller ruling: v2) |
| [EXP-008](#exp-008--keyframe-density-for-on-screen-text) | Keyframe density for on-screen text | 2 | done | shown recall 0.50 / 1.00 / 1.00 at 11.17 / 26.74 / 53.93 kf/min; bar selects 1 per shot, kept 4 s / 2 s as an override (0.50 < 0.85 MVP) | [B-251](decisions.md#b-251--exp-008-keep-the-4-s--2-s-keyframe-policy-as-a-recorded-override-of-the-bar) (controller ruling, against the written bar) |
| [EXP-017](#exp-017--ocr-engine-vs-reading-text-with-the-vision-model) | OCR engine vs vision model for on-screen text | 2 | done | recall 1.00 both; stage s/h 1,470 vs 1,907; vision model 16.1 % failed reads; keep PP-OCR | [B-252](decisions.md#b-252--exp-017-keep-the-dedicated-ocr-engine-pp-ocrv6-medium-via-rapidocr) |
| [EXP-018](#exp-018--kv-cache-precision-on-the-laptop) | KV-cache precision on the laptop | 2 | done for starts, inconclusive for F1 | all 4 arms 10/10 incl. FP8 32k; FP8 −21 % tok/s; ΔF1 −0.010 / −0.023 at n = 1 | [B-179](decisions.md#b-179--exp-018-do-not-adopt-the-fp8-kv-cache) (not adopted) |
| [EXP-020](#exp-020--entity-resolution-enum-constrained-ids-vs-fuzzy-matching-afterwards) | Entity resolution: enum IDs vs fuzzy matching afterwards | 2 | inconclusive; D-025 stands by default | accuracy 0.95 vs 0.97 (W1), 1.00 vs 0.96 with checks (partly by construction); plot rules found 1/36 vs 0/36, then 10/36 vs 17/36 after fixes; 0 alias-only arguments | [B-180](decisions.md#b-180--exp-020-inconclusive-d-025-registry-ids-as-an-enum-stands-by-default) |
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
| [C-011](#c-011--first-vllm-start-335-s-down-to-85-s) | First vLLM start time | 1 (1.7) | done | 335.3 -> 212.8 s cold, about 85 s warm | [B-081](decisions.md#b-081--exp-001-method-interleaved-rounds-one-start-per-trial-exact-kv-gate-fixed-length-decoding) |
| [C-012](#c-012--unload-time-331-s-down-to-40-s-the-zombie-enginecore) | Unload time, zombie EngineCore | 1 (1.7) | done | 33.1 -> 4.0 s | [B-087](decisions.md#b-087--stop-always-kills-the-process-group-and-liveness-ignores-zombies) |
| [C-013](#c-013--nip-cli-startup-109-s-down-to-11-s-lazy-imports) | `nip` CLI startup | 1 (1.10) | done | 10.9 -> 1.1 s | [B-113](decisions.md#b-113--lazy-torch-mlflow-and-scipy-imports-in-the-cli-superseding-b-111) |
| [C-014](#c-014--transnetv2-input-resize-filter-torchcodec-bilinear-vs-ffmpeg-bicubic) | TransNetV2 resize filter | 1 (1.8B) | done (Sintel, provisional labels) | F1 0.910-0.920, no effect | [B-094](decisions.md#b-094--no-change-to-part-a-after-exp-002-and-where-the-experiment-files-live) |
| [C-015](#c-015--decode-backend-and-keyframe-cost-on-real-film) | Decode backend, keyframe cost | 1 (1.8B) | done | ffmpeg CLI 22-24 s vs TorchCodec 35-38 s; keyframes 80 ms each | [B-094](decisions.md#b-094--no-change-to-part-a-after-exp-002-and-where-the-experiment-files-live) |
| [C-016](#c-016--which-awq-checkpoint-for-qwen35-4b-awq) | AWQ checkpoint | 1 (1.7) | done | 3.78 GiB chosen of 4 candidates | [B-082](decisions.md#b-082--checkpoint-for-qwen35-4b-awq-is-cyankiwiqwen35-4b-awq-4bit-in-the-catalog) |
| [C-017](#c-017--kv-cost-per-token-docs-60-hf-mem-128-measured-about-45) | KV per token: docs vs hf-mem vs measured | 1 (1.7) | done | 60 / 128 / 45.8 per 1,024 | [B-084](decisions.md#b-084--exp-001-calibration-applied-to-the-catalog-and-the-awq-checkpoint-added), [B-115](decisions.md#b-115--kv-calibration-restated-per-1024-tokens-446---458) |
| [C-018](#c-018--walking-skeleton-benchmark-prf1-100-on-planted-readability-errors-and-why-it-proves-little) | Walking-skeleton benchmark | 1 (1.10) | done (circular) | P/R/F1 1.00 on 18 planted errors | [B-108](decisions.md#b-108--the-locreadabilityv1-injector-isolated-cues-one-kind-per-pick-ref-based-labels) |
| [C-019](#c-019--exact-kv-budget-vs-the-old-gmu-sizing-on-big-gpus) | Exact KV vs gmu sizing on big GPUs | 1 (1.7) | done (review) | at most -2 % on 48 GB quality | [B-088](decisions.md#b-088--exact-kv-applies-to-every-single-gpu-engine-leftover-goes-to-kv-only-when-the-engine-is-alone-on-its-gpu) |
| [C-020](#c-020--stage-cache-cold-run-vs-a-one-line-scene-edit) | Stage cache: cold run vs a one-line scene edit | 2 (2.9B-1) | done (stub Plan) | hit rate 0.9242, 61 of 66 keyed units cached | [B-123](decisions.md#b-123--every-check-units-cache-key-includes-the-unit-key) |
| [C-21](#c-21--store-backed-nip-run-vs-the-110-file-run-on-sintel) | Store-backed `nip run` vs the 1.10 file run | 2 (2.0) | done | identical 6 flags, 614 spans equal; ingest 48.4 s, re-ingest 11.7 s, run 8.7 s | [B-140](decisions.md#b-140--run-lifecycle-and-the-stage-contract-epunit-gaps-coverage-from-check-units) |
| [C-22](#c-22--entity-name-scorer-wratio-vs-whole-word-subset-vs-exact-first) | Entity name scorer | 2 (2.1) | done (review probes) | false merges ("tomato" → Tom) removed; duplicate candidates fixed by exact-first | [B-161](decisions.md#b-161--names-match-on-whole-words-subset-with-at-least-half-the-words-an-exact-name-scores-101) |
| [C-23](#c-23--runaway-guard-21s-schema-vs-a-per-line-cap-vs-cap--line-enum) | Runaway guard | 2 (2.1B) | done | failed scenes 8/75 → 2/150 (cap) → 0/150 (cap + line enum) | [B-165](decisions.md#b-165--runaway-guard-at-most-4-events-per-scene-line-enforced-by-the-grammar) |
| [C-24](#c-24--derived-speaker-presence-with-without-and-skipping-intercut-scenes) | Derived speaker presence | 2 (2.1B) | done (ablation) | two_places 0 → 9/9 in both arms; skipping intercut → 0/9 | [B-170](decisions.md#b-170--resolved-dialogue-speakers-are-present-at-the-headings-location-d-21b-1) |
| [C-25](#c-25--holdsowns-values-as-written-vs-any-verb--use-vs-prompt-verbs-only) | holds/owns value mapping | 2 (2.1B) | done (CPU re-score) | prop_provenance 0 → 8/9; FP per show 92.3 (any verb) → 63.3 (prompt verbs) | [B-172](decisions.md#b-172--holdsowns-values-are-mapped-only-from-the-prompts-vocabulary-other-verbs-are-dropped-and-counted-d-21b-2) |
| [C-26](#c-26--one-printed-line-per-script_line-quote-drops-before-and-after) | One printed line per `script_line` | 2 (2.1B) | done | quote drops 28.7 → 3.7 (free text), 57.3 → 4.3 (enum) | [B-169](decisions.md#b-169--the-prompt-prints-one-numbered-line-per-script_line) |
| [C-27](#c-27--story-order-on-the-base-synthetic-show-rules-only-vs-rules--bible-and-stress-variants) | Story order on the base synthetic show | 2 (2.2) | done | tau 1.0000 with bible, 0.9998 rules only; 141/150 → 150/150 days after the one-morning rule | [B-186](decisions.md#b-186--flashbacks-with-an-unknown-day-rank-first-in-the-show-and-are-inferred), [B-191](decisions.md#b-191--an-ambiguous-transitions-synthetic-variant-so-exp-007-can-discriminate) |
| [C-28](#c-28--experiment-teardown-delete-by-re-planning-vs-delete-by-serve-status) | Experiment teardown: re-plan vs Serve status | 2 (2.2B) | done | 120 s timeout at 7822 MiB → 18.9 s, 7651 → 343 MiB | [B-197](decisions.md#b-197--the-experiments-down-deletes-serve-apps-by-status-under-the-gpu-lock) |
| [C-29](#c-29--layer-1-rules-on-oracle-facts-prf1-100-a-rules-only-ceiling) | Layer 1 rules on oracle facts | 2 (2.3) | done (ceiling) | P/R/F1 1.00 all four checks, 3 seeds, both oracle variants; clean show 0 flags | [B-205](decisions.md#b-205--the-oracle-facts-loader-lives-in-evalexplayer1_oraclepy-tagged-plot-l1), [B-206](decisions.md#b-206--lost-is-handled-like-destroyed-21-builds-state-lost-facts) |
| [C-30](#c-30--cue-alignment-rank-pairing-vs-shifted-rank-pairing-vs-rank-free-onset-coincidence) | Cue alignment fit: rank pairing vs onset coincidence | 2 (2.4) | done (synthetic stress tracks) | 0/916 exact links → 916/916 | [B-207](decisions.md#b-207--cue-alignment-fits-one-line-per-track-by-onset-coincidence-then-measures-overlap-on-that-line) |
| [C-31](#c-31--localization-checks-on-the-29a-injected-sintel-and-tears-of-steel-rounds-0-1-and-the-w-int-re-run) | Localization checks on 2.9A injected Sintel/ToS | 2 (2.4) | done (3 seeds; self-labelled natives) | term/drift/offset 1.00/1.00; shot_change R 1.00 → 0.83 → 1.00, raw P 0.12-0.14 / 0.03 | [B-214](decisions.md#b-214--native-labels-for-shot_change-come-from-the-clean-run-and-are-a-regression-guard-not-truth), [B-216](decisions.md#b-216--shot_change-passes-an-out-point-at-cut---2--cut-and-flags-points-on-either-side-of-a-cut) |
| [C-32](#c-32--ocr-backends-on-sintels-398-keyframes-paddleocr-gpu-vs-rapidocr-variants) | OCR backends on 398 Sintel keyframes | 2 (2.6) | done | Paddle 5.24 kf/s (cannot lock) vs RapidOCR shipped 1.29 kf/s, 1,569 MiB | [B-229](decisions.md#b-229--the-ocr-slot-uses-rapidocr-onnx-runtime-with-pp-ocrv6-medium-the-catalog-id-pp-ocrv6-medium-is-kept) |
| [C-33](#c-33--onnx-runtime-cuda-detector-and-recognizer-where-each-runs) | ORT CUDA detector/recognizer placement | 2 (2.6) | done (30 keyframes) | rec 5.3 s GPU vs 0.5 s CPU; det-GPU/rec-CPU 5.89 kf/s | [B-230](decisions.md#b-230--ocr-detection-on-the-gpu-recognition-on-the-cpu) |
| [C-34](#c-34--plate-regexes-over-three-rounds-captions-vs-real-plates) | Plate regexes: captions vs real plates | 2 (2.6) | done (review probes) | final: 16/16 plates, 26/50 captions still match | [B-238](decisions.md#b-238--plate-patterns-are-case-sensitive-allow-one-space-and-exclude-caption-words-by-name) |
| [C-35](#c-35--scanner-rules-on-unlogged-credits-text-shown-false-positives-95--29-and-89--24) | Scanner rules on unlogged credits text | 2 (2.7) | done (tuned on seed 1) | shown FP 95 → 29, 89 → 24 (seed 1); P 0.17 → 0.21 (0.44 with natives) | [B-253](decisions.md#b-253--credits-and-title-cards-give-no-gliner-brand-or-address-guesses), [B-254](decisions.md#b-254--credits-urls-are-correct-unknown-flags-precision-is-reported-against-injected-labels-only-junk-is-dropped-by-rule) |
| [C-36](#c-36--claim-span-for-an-occurrence-shot-span-vs-keyframe-cell-vs-occurrence-range) | Claim span: shot vs keyframe cell vs occurrence range | 2 (2.7) | done | shot claims cap recall at 20/32; occurrence range 1.00 | [B-248](decisions.md#b-248--the-claim-is-the-occurrences-frame-range-as-a-clrocc-hash-span) |
| [C-37](#c-37--end-to-end-through-the-store-vs-the-file-harness-and-the-in-cluster-gpu-run) | End to end through the store vs harness; in-cluster run | 2 (2.7) | done | e2e = harness (P 0.21, R 1.00); 32/32 pending/denied shown; cluster run exit 0, 43 flags | [B-257](decisions.md#b-257--pipelinepy-two-stages-and-the-slot-tables-beyond-the-one-sanctioned-add_stage) |
| [C-38](#c-38--fingerprint-collisions-among-clr-flags-41-of-109-per-seed--0-of-253) | Fingerprint collisions among clr flags | 2 (2.7) | done (review) | 41 of 109 per seed → 0 of 253 | [B-249](decisions.md#b-249--each-occurrence-has-its-own-stable-ref-so-r13-fingerprints-separate-distinct-items) |
| [C-39](#c-39--scene-retrieval-vector-only-vs-hybrid-vector--entity-overlap) | Scene retrieval: vector-only vs hybrid | 2 (2.8) | done (3 pairs, tuned on them) | setup in top 5: 1/3 → 3/3 (qwen3-0.6b) | [B-265](decisions.md#b-265--hybrid-score--cosine--weight-x-idf-weighted-entity-overlap-weight-10) |
| [C-40](#c-40--scene-embedding-throughput-cpu-vs-gpu-qwen3-embedding-06b) | Embedding throughput CPU vs GPU | 2 (2.8) | done | 5.8-6.0 vs 242.5-280.8 scenes/s | [B-266](decisions.md#b-266--cpu-is-the-in-process-embedding-default-the-serve-actor-uses-cuda) |
| [C-41](#c-41--low-motion-threshold-for-clearance-overlay-windows) | Low-motion threshold for clearance overlays | 2 (2.9A) | done | threshold 1.0, ≥ 84 frames: Sintel 21 stretches, ToS 11 | [B-272](decisions.md#b-272--clearance-text-is-an-overlay-plate-over-a-still-stretch) |
| [C-42](#c-42--phone-positives-nanp-expansion-area-codes-vs-555-numbers-outside-the-fiction-range) | Phone positives: N9X vs 555 outside the fiction range | 2 (2.9A) | done (review) | N9X `is_valid_number` False → structural FN; replaced by 4 valid 555 numbers | [B-273](decisions.md#b-273--phone-positives-must-be-valid-numbers-outside-the-fiction-range) |
| [C-43](#c-43--synthetic-show-mention-truth-template-bookkeeping-vs-scanning-every-surface) | Synthetic mention truth coverage | 2 (2.9A) | done | 483 → 704 mention records | [B-281](decisions.md#b-281--mention-truth-records-every-entity-surface-in-a-line) |
| [C-44](#c-44--locshot_change-recall-after-the-injector-stops-planting-a-compliant-out-point) | `loc.shot_change` recall after the injector fix | 2 (W-int) | done | Sintel recall 0.83 ± 0.29 → 1.00 ± 0.00; ToS unchanged | — (injector fix) |
| [C-45](#c-45--vllm-on-the-rebuilt-image-transformers-5161-lock-vs-the-phase-1-image-smoke) | vLLM on the transformers 5.16.1 image vs the Phase 1 smoke | 2 (W-int) | done (n = 1) | PASS; load 85.4 → 197.7 s, 188.6 → 119.0 tok/s, not attributed | [B-290](decisions.md#b-290--the-vllm-image-smoke-is-re-run-on-the-new-lock-with-a-forced-exact-kv-setting) |
| [C-46](#c-46--end-to-end-store-runs-cpu-stub-plan-vs-the-laptop-plan-real-asr-and-embedder-no-llm) | End-to-end store runs, cpu stubs vs laptop Plan | 2 (W-int) | done | 3 titles, 0 gaps; Sintel 17.5 / 44.8 s, ToS 8.5 / 32.3 s, synthetic 7.2 / 46.4 s; no LLM ran | [B-292](decisions.md#b-292--a-w-serve-step-before-w2-nip-run-inside-ray-head-with-staged-serving-and-an-hf_home-default) |
| [C-47](#c-47--free-vram-seen-inside-ray-head-nvml-cuda-vs-the-hosts-nvidia-smi) | Free VRAM inside ray-head vs host | 2 (W-serve) | done | NVML free truthful; used +238 MiB; CUDA constant 6.93 GiB | [B-297](decisions.md#b-297--a-vram-skip-says-free-vs-needed-from-the-planners-own-formula) |
| [C-48](#c-48--real-model-nip-run---in-cluster-on-synthetic-s01e01-planner-margin-05-vs-025) | Real-model in-cluster run, margin 0.5 vs 0.25 | 2 (W-serve) | done | 0.5: short 0.02-0.21 GiB; 0.25: 774-852 s, load 255-272 s, peak 7,585-7,792 MiB, 112 facts | [B-300](decisions.md#b-300--nip_vram_margin_gb-default-05-the-8-gb-laptop-may-set-025) |
| [C-49](#c-49--does-xgrammars-disable_any_whitespace-stop-the-extraction-runaway) | Does `disable_any_whitespace` stop the runaway? | 2 (W-serve) | done | no: 2/25 scenes at 2,048 tokens; enumeration loop in valid JSON | [B-303](decisions.md#b-303--the-extraction-runaway-and-single-stream-throughput-are-handed-on-not-fixed-in-w-serve) |
| [C-50](#c-50--nip-image-size-the-wheel-then-the-uv-cache-mount-that-was-never-used) | nip image size and the unused uv cache mount | 2 (2.close) | done | 26.48 → 28.65 → 25.11 GB | [B-304](decisions.md#b-304--cuda-12-cublas-only-on-ldconfig-and-the-uv-cache-dir-fixed) |
| [C-51](#c-51--faster-whisper-in-the-container-missing-libcublasso12-scratch-fix-shipped-image) | faster-whisper in the container | 2 (2.close) | done | missing libcublas.so.12 → turbo RTF 0.0188 to 0.0201, +1.29 GiB | [B-304](decisions.md#b-304--cuda-12-cublas-only-on-ldconfig-and-the-uv-cache-dir-fixed) |
| [C-52](#c-52--rapidocr-in-the-container-cuda-provider-vs-cpu-and-the-041-kfs-that-was-not-reproduced) | RapidOCR CUDA vs CPU in the container | 2 (2.close) | done | 1.11 / 1.22 kf/s GPU vs 0.55 CPU; 2.7's 0.41 not reproduced | [B-308](decisions.md#b-308--nothing-changed-in-the-image-for-ocr-the-cpu-fallback-stays) |
| [C-53](#c-53--gliner-x-base-vs-gliner-x-large-size-latency-and-candidates-on-sintels-stored-ocr) | gliner-x-base vs x-large size, latency, candidates | 2 (2.close) | done | peak 1,347 vs 2,578 MiB (catalog 3.7 → 2.6 GiB); 78 vs 63 candidates, 0 only-large | [B-305](decisions.md#b-305--gliner-x-large-stays-the-planners-pick-on-the-8-gb-laptop-measured-no-pin) |
| [C-54](#c-54--ner-ab-on-replayed-ocr-gliner-x-large-vs-gliner-x-base-on-the-exp-008-end-to-end-benchmark) | NER A/B on replayed OCR (extends EXP-008) | 2 (2.close) | done (18 MLflow runs) | recall 1.00 both; FP/h 90.99 → 86.55; +native P 0.44 → 0.46 | [B-305](decisions.md#b-305--gliner-x-large-stays-the-planners-pick-on-the-8-gb-laptop-measured-no-pin) |
| [C-55](#c-55--vllm-smoke-on-the-new-image-vs-earlier-runs) | vLLM smoke on the new image | 2 (2.close) | done (2 trials) | starts and tears down; 134.6 / 165.5 tok/s vs 175 to 189 earlier, unexplained | [B-304](decisions.md#b-304--cuda-12-cublas-only-on-ldconfig-and-the-uv-cache-dir-fixed) |

---

# Formal experiments

## EXP-001 · vLLM memory headroom on the laptop

| | |
|--|--|
| **Question** | Which `gpu_memory_utilization` lets `qwen3.5-4b-awq` start reliably on the RTX 4060 while leaving the most KV cache? (from docs/experiments.md) |
| **Variants** | `gpu_memory_utilization` (gmu) 0.75 · 0.80 · 0.83 · 0.86 · an exact KV-cache budget (`--kv-cache-memory-bytes`) sized by the planner (`kv-planner`). Added by the experimenter, not in the design: three desktop-pressure arms (see Method) and, in the fix round, a `plan` arm that runs the shipped path (probe, planner, `serving.apps`) |
| **Metrics** | Successful starts out of 10 · peak GPU memory (MiB) · maximum concurrent sequences at 8k context (from vLLM's startup log) · tokens/s on a fixed prompt set · GPU memory after teardown (must return to idle) |
| **Success bar (as written)** | The highest setting with 10/10 starts becomes the laptop calibration; the planner switches to exact KV budgets only if they start as reliably and give at least as much KV cache. Memory must return to idle after every teardown |
| **Status** | **Done** (2026-10-16). 66 tagged trials plus 2 pilots in MLflow experiment `EXP-001` (tag `exp=EXP-001`), then 2 `plan` verification runs after the fix round |
| **Result in one line** | Every setting up to gmu 0.86 starts 10/10 on an idle desktop. With about 2 GB of Windows VRAM in active use gmu 0.75 and 0.83 start 0/3, gmu 0.86 starts 3/3 but with 1.52 sequences at 8k, and the exact KV budget starts 3/3 with 2.64 sequences every time. By the written bar the answer is gmu 0.86; the controller instead ruled for exact KV budgets ([B-083](decisions.md#b-083--exact-kv-budgets-on-single-gpu-engines-sized-by-the-planner-from-probed-free-vram)) |
| **Source** | `notes/1.7.md` (results, fix round 1), `reports/1.7-review.md`, `reports/1.7-rereview.md`; code `eval/exp/exp001_vllm_headroom.py` (landed in commit `6854081`), calibration in `989e0ed`, closeout `09c87f8` |

### Why this ran first

Inputs already measured in earlier deliverables (not results of EXP-001): the design's 7,321 MiB free (7.15 GB) at idle; the 1.6 probe with desktop apps open read 6.13 to 6.44 GB free, at which the planner skips every LLM slot ([C-006](#c-006--free-vram-on-the-laptop-idle-doc-vs-desktop-apps-open), [B-044](decisions.md#b-044--the-laptop-cannot-plan-an-llm-at-613-gb-free-exp-001-runs-before-the-walking-skeleton)); the planner's overhead (1.2 GiB), KV (60 MiB per 1k tokens, the doc's figure) and margin were unmeasured estimates ([C-003](#c-003--hf-mem-kv-estimates-vs-the-docs-kv-figures)).

### Setup

- **Software and hardware:** `qwen3.5-4b-awq` (checkpoint `cyankiwi/Qwen3.5-4B-AWQ-4bit`, see [C-016](#c-016--which-awq-checkpoint-for-qwen35-4b-awq)), 8,192 context, `--enforce-eager`, 2 images x 589,824 px, vLLM 0.30.0 in the `nip:dev` image under Docker Desktop/WSL2, RTX 4060 Laptop 8 GB (8,188 MiB), driver 610.62, started through `runtime.serving` (Ray Serve 2.58).
- **Stack:** only `ray-head` and `mlflow` (plus postgres, objectstore, objectstore-init), started with `docker compose -f compose.yaml -f eval/exp/exp001.compose.yaml up -d --wait ray-head mlflow` in 30 s. The override file bind-mounts `./models:/models`, `./src`, `./eval`, `./tests`, `./config` (so no 23 GB image rebuild per code change) and sets `HF_HUB_OFFLINE=1`. `compose.yaml` itself was not touched.
- **Download:** the catalog had no AWQ repo, so the checkpoint was fetched into `models/hf` in 132 s (3.8 GB).
- **Method:** one vLLM start per trial (Serve retries off), rounds interleaved across settings (each round runs every setting once, so desktop drift hits all settings alike), the GPU checked free of other compute processes before each trial (no waits were needed). `kv-planner` = `--kv-cache-memory-bytes 1006632960` (the planner's 60 MiB/1k x 8k x 2 sequences = 960 MiB) with gmu 0.5 as vLLM's startup gate only. Tokens/s = 8 fixed prompts in flight, 128 tokens each (`ignore_eos`), through the Serve route. "Peak (ours)" = NVML peak (0.2 s sampling) during the trial minus NVML used at its start, so desktop drift makes it approximate; vLLM's own accounting rows are exact. The table below is the unedited output of `python -m eval.exp.exp001_vllm_headroom table` over MLflow, split into three tables for width.
- **Desktop-pressure arms (added after the main 50 trials):** the main trials ran while the Windows desktop held only about 430 to 450 MiB from round 3 on, not the 1.4 to 2.0 GB that 1.6 measured with apps open. To test that condition the experimenter held 1.5 GiB on the host with a torch allocation, in two forms: an **idle holder** (allocated once, then sleeping; tag `@host1.5G`) and an **active holder** (touches the buffer every 0.1 s like a busy app; tag `@host1.5G-active`; NVML used stayed about 1.89 to 1.92 GB).
- **Backfill:** metrics the log parser learned after the first trials (CUDA free, vLLM's memory accounting) were added afterwards by re-parsing each run's logged vLLM log artifact (`backfill`); it only adds metrics a run lacks and sets the `failure` tag. Run inside ray-head it took 11 s for 50 runs; the same command from the Windows host hung for more than 10 minutes on artifact download while listing worked.

### Pilots: why the first start took 335 s ([C-011](#c-011--first-vllm-start-335-s-down-to-85-s))

Two pilots, tagged `EXP-001-pilot` and kept out of the tables, showed that a start is dominated by things other than the memory setting: Hub calls, a 9P bind mount, engine init. Setting `HF_HUB_OFFLINE=1` cut the first load from 335.3 s to 212.8 s, and warm starts in the same container took about 85 to 88 s, which is the load time in the tables.

### Results 1: idle desktop (10 trials per setting)

| Metric | gmu-0.75 | gmu-0.80 | gmu-0.83 | gmu-0.86 | kv-planner |
|---|---|---|---|---|---|
| Successful starts | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| Free VRAM at start (NVML), MiB | 7643 ± 304 | 7657 ± 272 | 7680 ± 176 | 7742 ± 10 | 7743 ± 9 |
| Peak GPU memory (ours), MiB | 6397 ± 9 | 6589 ± 67 | 6816 ± 145 | 7132 ± 1 | 6400 ± 2 |
| Peak device used, MiB | 6941 ± 305 | 7119 ± 207 | 7323 ± 31 | 7577 ± 9 | 6844 ± 10 |
| CUDA free at start (vLLM), GiB | 6.93 ± 0.00 | 6.93 ± 0.00 | 6.93 ± 0.00 | 6.93 ± 0.00 | 6.93 ± 0.00 |
| vLLM weights + non-torch, GiB | 4.25 ± 0.00 | 4.25 ± 0.00 | 4.25 ± 0.00 | 4.25 ± 0.00 | — |
| vLLM peak activation, GiB | 0.18 ± 0.00 | 0.18 ± 0.00 | 0.18 ± 0.00 | 0.18 ± 0.00 | — |
| vLLM KV cache, GiB | 1.56 ± 0.00 | 1.96 ± 0.00 | 2.20 ± 0.00 | 2.44 ± 0.00 | — |
| KV cache, tokens | 35746 ± 0 | 45056 ± 0 | 50641 ± 0 | 56226 ± 0 | 21597 ± 0 |
| Max concurrent seqs at 8k | 4.36 ± 0.00 | 5.50 ± 0.00 | 6.18 ± 0.00 | 6.86 ± 0.00 | 2.64 ± 0.00 |
| Tokens/s (8 prompts x 128) | 152.1 ± 39.4 | 144.9 ± 40.6 | 156.9 ± 16.8 | 156.8 ± 27.1 | 151.1 ± 33.8 |
| Load s | 88.5 ± 7.6 | 86.8 ± 5.8 | 87.7 ± 6.2 | 85.2 ± 3.6 | 84.8 ± 3.2 |
| Back to idle after teardown | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| VRAM after teardown, MiB | 529 ± 272 | 505 ± 175 | 443 ± 12 | 444 ± 10 | 448 ± 6 |
| Failures | — | — | — | — | — |

### Results 2: with 1.5 GiB held on the host, idle holder (2 + 1 + 1 trials)

The first trial of the idle holder showed that Windows (WDDM) **evicts idle VRAM of another process** when the container needs it: NVML used went 2,015, 1,217, 397 MiB across the next trials, so these arms are not real pressure. They are kept because they are in MLflow.

| Metric | gmu-0.75@host1.5G | gmu-0.83@host1.5G | gmu-0.86@host1.5G |
|---|---|---|---|
| Successful starts | 2/2 | 1/1 | 1/1 |
| Free VRAM at start, MiB | 6778 ± 1194 | 6739 | 7562 |
| Peak GPU memory (ours), MiB | 6134 ± 344 | 6698 | 7015 |
| Peak device used, MiB | 7543 ± 850 | 8146 | 7640 |
| CUDA free at start (vLLM), GiB | 6.93 ± 0.00 | 6.93 | 6.93 |
| vLLM weights + non-torch, GiB | 4.25 ± 0.00 | 4.25 | 4.25 |
| vLLM peak activation, GiB | 0.18 ± 0.00 | 0.18 | 0.18 |
| vLLM KV cache, GiB | 1.56 ± 0.00 | 2.20 | 2.44 |
| KV cache, tokens | 35746 ± 0 | 50641 | 56226 |
| Max concurrent seqs at 8k | 4.36 ± 0.00 | 6.18 | 6.86 |
| Tokens/s | 90.5 ± 12.1 | 115.7 | 115.2 |
| Load s | 115.5 ± 2.8 | 106.5 | 101.5 |
| Back to idle after teardown | 2/2 | 1/1 | 1/1 |
| VRAM after teardown, MiB | 990 ± 645 | 633 | 564 |

### Results 3: with 1.5 GiB actively held on the host (3 trials per setting)

This is the condition 1.6 measured (apps open, about 2 GB used), reproduced on purpose.

| Metric | gmu-0.75@host1.5G-active | gmu-0.83@host1.5G-active | gmu-0.86@host1.5G-active | kv-planner@host1.5G-active |
|---|---|---|---|---|
| **Successful starts** | **0/3** | **0/3** | **3/3** | **3/3** |
| Free VRAM at start, MiB | 6047 ± 24 | 6068 ± 7 | 6066 ± 3 | 6041 ± 4 |
| Peak GPU memory (ours), MiB | — | — | 6018 ± 21 | 5995 ± 15 |
| Peak device used, MiB | — | — | 8139 ± 19 | 8141 ± 12 |
| CUDA free at start (vLLM), GiB | — | — | 6.93 ± 0.00 | 6.93 ± 0.00 |
| vLLM weights + non-torch, GiB | — | — | **6.15 ± 0.02** | — |
| vLLM peak activation, GiB | — | — | 0.18 ± 0.00 | — |
| vLLM KV cache, GiB | — | — | 0.54 ± 0.02 | — |
| KV cache, tokens | — | — | 12412 ± 215 | 21597 ± 0 |
| Max concurrent seqs at 8k | — | — | 1.52 ± 0.03 | 2.64 ± 0.00 |
| Tokens/s | — | — | 119.6 ± 30.7 | 82.1 ± 11.8 |
| Load s | — | — | 101.1 ± 13.7 | 151.9 ± 99.8 |
| Back to idle after teardown | 3/3 | 3/3 | 3/3 | 3/3 |
| VRAM after teardown, MiB | 2118 ± 3 | 2121 ± 8 | 2118 ± 21 | 2142 ± 9 |
| Failures (tag) | `no_kv_memory` | `kv_below_one_seq` | — | — |

Details of the failures from vLLM's log: gmu 0.75 printed "Available KV cache memory: -0.34 / -0.78 GiB" then "No available memory for the cache blocks"; gmu 0.83 had KV 0.31 to 0.32 GiB, below the 0.35 GiB one 8,192-token sequence needs. The exact budget (960 MiB) started 3/3 at 21,597 tokens (2.64x), tokens/s 68.4 / 88.8 / 89.0, load 267.0 s (first start in a recreated container) then 99.4 / 89.4 s. The "VRAM after teardown" of about 2,120 MiB in this table is consistent with the holder (NVML used stayed about 1.89 to 1.92 GB) plus the desktop; it is not a leak because the teardown check compares with an idle level measured with the holder already present.

MLflow run IDs (first 8 characters) per column, as logged by `table`: gmu-0.75 e833dd5e a32f987c 7685c5df 97c8dd7f d3498ec0 734a068f 5fa0293e 4839a939 b895b2a5 4ac44eac · gmu-0.80 c9747712 44731b39 07d0a193 3ca2fb0e fb35672a 00cf780e 0038b053 3f517231 8d505032 7d14f989 · gmu-0.83 6bd1a3ac b173bf7f 364dd49a 0217a769 9693bade 856dc5e6 a420d35b 617afb9f 5664fe3e bdc451f7 · gmu-0.86 a2c98dca 822fcd6d be306b82 2f30596a a301691a 947d3d43 d755c600 89be8de2 ffd07968 729fd144 · kv-planner d95d9b8d e451091c d914da28 9c390a40 10dd2516 1225592b b8a23fc9 5964a91f c7b535e3 dc974fc2 · gmu-0.75@host1.5G e8876c28 519c6b6b · gmu-0.75@host1.5G-active 27bd78d6 6f5648fb d80136ee · gmu-0.83@host1.5G 2e67d84d · gmu-0.83@host1.5G-active 78f3b698 59b109ff d427c496 · gmu-0.86@host1.5G 6f5248fa · gmu-0.86@host1.5G-active d3338a95 68921e17 fa045521 · kv-planner@host1.5G-active 757d8a31 9299ed5f 348a9603.

### Derived numbers (arithmetic on the rows above, from the notes)

- **KV per 1k tokens:** 1.56 GiB / 35,746 tokens = **44.7 MiB** per 1,000 tokens (gmu 0.75); 0.94 GiB / 21,597 = **44.6 MiB** (kv-planner). The catalog had 60; hf-mem said 128 ([C-017](#c-017--kv-cost-per-token-docs-60-hf-mem-128-measured-about-45)). The reviewer found 44.0 to 44.7 per 1,000 (about +-1.5 %); the closeout later restated the unit as per 1,024 tokens, 45.8.
- **vLLM's non-KV footprint:** 4.25 + 0.18 = **4.43 GiB** (the catalog's estimate was weights 4.0 + overhead 1.2 = 5.2 GiB).
- **Startup peak of our processes:** **6,397 to 6,400 MiB (6.25 GiB)** for both gmu 0.75 and the exact 960 MiB budget, so it does not include the KV cache. The planner's own per-GPU estimate had been 6.14 GiB.
- **Teardown:** VRAM returned to idle in **66/66** tagged trials (and both pilots); unload took 3 to 6 s.
- **Tokens/s:** all idle settings are within noise, about 145 to 157 mean. The noise is large (standard deviation 17 to 41): one first trial (44.3) ran while the experimenter ran the host's whole unit-test suite, and two outliers (38.3 at gmu 0.80 trial 3, 89.3 at gmu 0.86 trial 9) have no known cause. Means are reported as they are.
- **The mechanism, as arithmetic (mine, from the table):** vLLM sizes KV as `gmu x total - (weights + non-torch) - activation`. Idle, gmu 0.86: 0.86 x 8.0 = 6.88 - 4.25 - 0.18 = 2.45 GiB (table: 2.44). Active holder, gmu 0.86: 6.88 - 6.15 - 0.18 = 0.55 (table: 0.54); gmu 0.83: 6.64 - 6.15 - 0.18 = 0.31 (log: 0.31 to 0.32); gmu 0.75: 6.00 - 6.33 = -0.33 (log: -0.34).

### What was found (the story)

1. **At idle, nothing is wrong.** All five settings start 10/10, KV grows with gmu (4.36x to 6.86x at 8k) and tokens/s does not change. By the written bar this alone makes gmu 0.86 the winner, and exact KV budgets lose (21,597 vs at least 35,746 tokens).
2. **CUDA inside the container does not see the Windows desktop.** `torch.cuda.mem_get_info` and vLLM's own log read **6.93 GiB free of 8.0** in every trial whose log reached that line (60 of the 66 tagged trials plus both pilots), while NVML free on the same GPU ranged **5,934 to 7,767 MiB** over the runs. Under WSL2 the CUDA free figure did not follow what Windows apps held.
3. **So vLLM's startup check cannot protect the launch.** The check (gmu x total must be at most CUDA free = 6.93 GiB) passes for any gmu up to 0.866, whatever Windows holds. Then, with Windows memory in active use, vLLM's profiler counts that memory as its own "non-torch" memory (weights + non-torch **6.15 GiB instead of 4.25**) and sizes KV from what is left. gmu 0.75 and 0.83 had no room for even one sequence (0/3 each); gmu 0.86 squeezed through at 1.52 sequences.
4. **An exact KV budget removes the dependency.** With `--kv-cache-memory-bytes` vLLM skips the memory *measurement* and reserves the amount asked, so the KV size was identical in all 13 trials (10 idle + 3 under pressure), 2.64x at 8k. It still runs the dummy profile forward pass (see Peak attribution).
5. **The probe that sizes it must be truthful.** NVML (on the host, and in the container) does report Windows usage truthfully, unlike CUDA's constant 6.93 GiB. A budget computed from the NVML probe gives more KV when the desktop is idle and less under load, and is predictable.

### Peak attribution, corrected in the fix round

The first notes called the 6.25 GiB peak "profiling" and also said an exact KV budget "skips profiling". The code (`vllm/v1/worker/gpu_worker.py` around lines 541 to 545) shows that with `kv_cache_memory_bytes` set vLLM still calls `profile_run()` ("still need a profile run which compiles the model for max_num_batched_tokens") and skips only the memory measurement. So the dummy forward pass runs in both modes, and both peak at the same NVML value (6,397 vs 6,400 MiB) although their KV differs by 0.62 GiB: the peak happens before the KV cache is allocated. vLLM's accounting explains 4.43 GiB of it. The other **about 1.8 GiB is outside that accounting and is not attributed**; unchecked candidates are the multimodal dummy encoder pass (3 images at 589,824 px), allocator caching and the API server process's CUDA context.

### Takeaway

On an idle laptop the gmu path works and gives the most KV, but on WSL2 it is fragile in exactly the condition 1.6 measured (apps open, about 2 GB used): vLLM sees a constant 6.93 GiB "free", passes its startup check, then counts the Windows apps' memory as its own. The exact KV budget started in all 13 trials with the same 2.64x each time. The written bar did not anticipate the desktop-pressure result, so the experimenter proposed amending it, and the controller ruled for it.

Independent review (`1.7-review.md`) judged the proposal **partly supported**. For: exact KV is the only setting whose KV size was identical in every trial and the log shows the mechanism directly. Against, as the reviewer listed: (1) the pressure is synthetic (a torch buffer touched every 0.1 s, n = 3 per setting), not real desktop apps; (2) gmu 0.86 also started 3/3 under that pressure (at 1.52x); (3) at 6.04 to 6.07 GiB free at start the 1.6 planner would already skip the LLM slots at plan time, so "gmu 0.77 fails under a busy desktop" only matters if the desktop gets busy *after* probing, which is plausible in staged mode where the LLM group loads last but was not argued in the notes; (4) device peak under pressure with exact KV was 8,141 of 8,188 MiB (about 47 MiB headroom) and tokens/s dropped to about 82, so "reliable" is marginal; (5) variant (c), an exact budget sized to fill the usable memory, which could meet both halves of the bar, was not measured. The 10/10 trials also ran at 7,643 to 7,743 MiB free (desktop holding about 450 MiB), well above the 6.13 to 6.44 GB 1.6 measured, so they describe an unusually idle laptop.

### Decision

**Controller ruling** ([B-083](decisions.md#b-083--exact-kv-budgets-on-single-gpu-engines-sized-by-the-planner-from-probed-free-vram)): on single-GPU engines the planner emits an exact KV budget sized from the probed free VRAM; gmu stays as vLLM's startup gate only. Cost if wrong, as ruled: the probe is taken at plan time; in staged mode the LLM group loads last, so if the desktop grows between probe and deploy the budget can exceed what is physically free, vLLM's check cannot catch it (it sees 6.93 GiB), and the start fails or WDDM pages memory until Phase 4's OOM-amendment path re-plans. Mitigation available: re-probe at group boundaries. Also ruled: apply the measured calibration to the catalog ([B-084](decisions.md#b-084--exp-001-calibration-applied-to-the-catalog-and-the-awq-checkpoint-added)), treat the startup peak as a fit floor ([B-085](decisions.md#b-085--the-startup-peak-is-a-fit-floor-not-subtracted-from-the-kv-budget)).

### What changed in the code because of it

| | Before EXP-001 | After (commit `989e0ed`, unit fix `09c87f8`) |
|---|---|---|
| Laptop Plan at the docs' 7.15 GB free | text_llm 8k, gmu 0.77 | **16k context, gmu 0.79, KV 2,170 MiB** |
| LLM memory control on one GPU | `--gpu-memory-utilization` | `--kv-cache-memory-bytes` from `SlotDecision.kv_cache_bytes`; gmu only gates the start |
| `qwen3.5-4b-awq` catalog | KV 60 MiB/1k, overhead 1.2 GiB, no `checkpoint` | KV 44.6 (then 45.8 per 1,024 tokens, [B-115](decisions.md#b-115--kv-calibration-restated-per-1024-tokens-446---458)), overhead 0.53 GiB, `startup_peak_gb` 6.25, `checkpoint: cyankiwi/Qwen3.5-4B-AWQ-4bit` |
| Per-GPU fit | `weights/tp + KV/tp + overhead` | `max(weights/tp + KV(ctx x 2)/tp + overhead, startup_peak_gb)` |
| `stop()` | skipped the group kill if `vllm serve` had already exited | always SIGTERMs the process group, zombie-aware ([C-012](#c-012--unload-time-331-s-down-to-40-s-the-zombie-enginecore)) |

Why 16k and not 32k on the laptop at 7.15 GB free: usable = min(0.9 x 8.0, 7.15 - 0.5) = 6.65 GiB. 32k needs 4.53 + 2.79 = 7.32 GiB, which does not fit; 16k needs max(4.53 + 1.39, 6.25) = 6.25 GiB, which does. KV = 6.65 - 4.53 = 2.12 GiB = 2,170 MiB. At 7.6 and 8.0 GB free the budget is 2,631 and 2,734 MiB. At 6.6 GB free (usable 6.1, below the 6.25 floor) the LLM slots are skipped. On a 24 GB GPU the budget is capped at 44.6 x 32 x 2 = 2,854 MiB (2,931 MiB after the unit fix). A live `nip plan` at 7,749 MiB free in the closeout gave 2,600 MiB.

### Real re-verification on the stock catalog (fix round)

Stack up in 28 s, no code overrides. Probe inside ray-head: 7.5 GiB free. The planner gave a resident {text_llm, vlm} at 16k, gmu 0.79, KV 2,651,848,704 B. Two `--setting plan` trials (runs 63c9fdf3, da1f1928, variant `plan`):

| Metric | plan |
|---|---|
| Successful starts | 2/2 |
| Free VRAM at start, MiB | 7718 ± 53 |
| Peak GPU memory (ours), MiB | 7284 ± 88 |
| Peak device used, MiB | 7754 ± 35 |
| CUDA free at start (vLLM), GiB | 6.93 ± 0.00 |
| KV cache, tokens | 66829 ± 1219 |
| Max concurrent seqs (here at 16,384 tokens) | 4.08 ± 0.07 |
| Tokens/s (8 prompts x 128) | 175.6 ± 0.9 |
| Load s | 131.0 ± 65.9 (177.6 cold container, 84.4 warm) |
| Back to idle after teardown | 2/2 |
| VRAM after teardown, MiB | 362 ± 11 |

KV budgets were 2,529 and 2,600 MiB (from the free VRAM probed at each trial). The predicted steady footprint (4.53 + KV) was 7,168 and 7,240 MiB; measured 7,222 and 7,347, so the overhead is underestimated by 54 to 107 MiB, inside the 0.5 GiB margin. At 16k vLLM fit 65,967 to 67,691 tokens into 2.47 to 2.54 GiB, about 38 MiB per 1k: the planner's 44.6 (measured at 8k) is conservative at 16k (the model is hybrid, so a per-sequence state is plausible). `tests/integration/test_serving.py` with the stock catalog and the probed Plan: 2 passed in 136.95 s.

### Open items

- **Stale probe at deploy time** (the ruling's own cost): re-probe at group boundaries is not built; Phase 4's OOM amendment is the backstop.
- **Real, not synthetic, desktop pressure** was never measured on the exact-KV arm with actual applications; n = 3.
- Variant (c) of the notes' proposal (an exact budget that fills the usable memory) is in effect what the planner now computes (usable minus weights minus overhead, capped at context x 2), but it was never run as a ten-trial arm: it is evidenced only by the 2 `plan` runs, and its direct comparison with gmu 0.86 at idle was not run.
- **About 1.8 GiB of the 6.25 GiB startup peak is unattributed.**
- `--kv-cache-dtype fp8` not set (left to EXP-018). Judge (the fifth laptop load) is unexercised until the ministral weights are pulled (4.6).
- The reviewer could not open MLflow (stack down) to confirm the tabled values; arithmetic and run-ID traceability were checked, contents not. Table values were produced by `table` over MLflow.
- KV/token is about 38 MiB per 1k at 16k vs 45.8 in the catalog (conservative), and the unit (1,000 vs 1,024) mismatch was fixed in the closeout ([B-115](decisions.md#b-115--kv-calibration-restated-per-1024-tokens-446---458)).
- Docs not updated (read-only): see [doc-corrections.md](doc-corrections.md) rows for `docs/experiments.md` and `docs/hardware-adaptation.md`.

## EXP-002 · Shot detection: TransNetV2 vs PySceneDetect

| | |
|--|--|
| **Question** | Is TransNetV2 accurate enough to justify a model over PySceneDetect's classical detectors? (from docs/experiments.md) |
| **Variants** | TransNetV2 (threshold 0.5) · PySceneDetect `ContentDetector()` (threshold 27, `min_scene_len` 15, HSV delta weights, MERGE filter) · PySceneDetect `AdaptiveDetector()` (`adaptive_threshold` 3.0, `min_scene_len` 15, window 2, `min_content_val` 15). PySceneDetect 0.7.1, OpenCV 5.0.0 |
| **Metrics** | Cut-detection F1 with +-2-frame tolerance against hand-labelled cuts · seconds of processing per video-minute on the laptop |
| **Success bar (as written)** | Keep TransNetV2 only if its F1 beats the best PySceneDetect variant by at least 0.02; otherwise use the simpler one |
| **Status** | **Partly run, result provisional.** Sintel only, against 183 agent-made, detector-seeded labels; Tears of Steel timed but not labelled; dissolves and credits masked out |
| **Result in one line** | The verdict of the bar **flips with threshold tuning**: TransNetV2 wins by +0.037 at defaults; tuned on the same labels the adaptive detector wins by +0.021; held out by halves it wins by +0.016. Speed does not separate them (3.3 to 4.4 s per video-minute) |
| **Source** | `notes/1.8B.md`, `reports/1.8B-report.md`, `reports/1.8B-review.md`, `reports/1.8B-rereview.md`; code `eval/exp/exp002_shots.py`, `eval/exp/label_sheets.py`; commits `6854081`, `be9daac` |

### Setup and method

- **Hardware:** the dev laptop (RTX 4060 Laptop 8 GB, Ryzen 7 7840HS, 31 GB RAM, Windows 11). Films from 1.9: Sintel 1080p mkv (1920x818, 21,312 frames at 24/1, 888.0 s) and Tears of Steel 720p mov (1280x534, 17,620 frames, 734.2 s), both exactly 24/1 ([C-010](#c-010--the-24-fps-surprise-is-23976-the-right-rate-for-the-test-films)).
- **Cut convention:** the 0-based frame index of the first frame of the new shot, the same as `nip.timeline.shots` and the labelling README. PySceneDetect scene starts are exactly that; TransNetV2's cut is `(s + e + 2) // 2` ([B-026](decisions.md#b-026--shot-boundary-semantics)).
- **Scorer:** `match_cuts` / `cut_metrics`: one-to-one matching of predicted and labelled cut frames within +-2 frames (a single sweep over both sorted lists, a maximum matching when every window has the same width), P/R/F1 from TP/FP/FN. `eval/metrics.py` was not reusable (it scores `Flag`s against `label_id` rows by IoU), as the controller ruled ([B-049](decisions.md#b-049--cut-labels-are-a-separate-json-file-not-flags)). Tests: `tests/unit/eval/test_exp002_shots.py`, 4 tests including a randomized check of 200 cases against scipy's maximum bipartite matching.
- **Process isolation and speed:** each (film, variant) runs in its own subprocess so peak RAM is that run's own; three timing repeats per cell (warm file cache for everything but the very first Sintel read). Seconds per video-minute is the wall time of the full detector including decode (TransNetV2: TorchCodec decode + resize + model + model load; PySceneDetect: OpenCV decode). Detectors are deterministic, so the +- on F1 across repeats is 0.00 by construction; only the seconds rows have real spread. All runs go to MLflow (`sqlite:///data/mlflow/mlflow.db`, experiment `exp002-shots`) with metric names that `eval.report.compare_table` reads, so `nip eval compare --exp EXP-002-sintel` prints the table.
- **Headline metric is masked** (dissolves, ambiguous spots and credits ignored for predictions and labels); the unmasked F1 is always reported next to it ([B-090](decisions.md#b-090--the-exp-002-headline-metric-is-masked-the-unmasked-f1-is-always-reported)).

### Where the labels came from, and how they are biased

The user cannot hand-label cuts, so the labels are **agent labels made by looking at frames** ([B-051](decisions.md#b-051--provisional-agent-labels-for-exp-002), [B-092](decisions.md#b-092--provisional-labels-by-candidate-union-and-contact-sheets-with-a-committed-verification-record)). They are stored in `eval/labeling/labels/sintel_cuts.provisional.json` (183 cuts, `labeller: "agent-provisional"`, the exact `pull` object format) plus a masks sidecar of 20 windows. The experiment must be re-run when a human verifies them in the Label Studio project from 1.9.

Method (`exp002_shots.py candidates`, `label_sheets.py`):
1. **Candidates from the union of all three detectors at deliberately low thresholds:** TransNetV2 at probability 0.05 (251 cuts), `ContentDetector(threshold=8, min_scene_len=1)` (662 cuts), `AdaptiveDetector(adaptive_threshold=1.2, min_scene_len=1, min_content_val=4)` (544 cuts): 1,089 distinct frames.
2. **Fixed-window scan for cuts no detector flagged:** mean absolute luma difference between consecutive frames at 208x89, normalised by the median of the 25 surrounding frames; in every 240-frame window the 2 biggest peaks not within 2 frames of a candidate were added (43 extra candidate frames).
3. Candidates within 3 frames were merged into **646 events**.
4. **Every event was inspected as a contact sheet:** 6 consecutive frames (f-3..f+2, 208x89 each) with a red line between f-1 and f, 12 events per sheet = 54 sheets, then a second pass of 17 sheets for the 195 candidate rows that fell outside the shown frames (of 275 such member frames), plus 8-frame strips at 300 px for doubtful events (7 cuts are flagged as zoomed in the verification record). The label frame is the first frame after the red line when the picture changes completely.
5. **Result: 183 cuts** (hard cuts, including the cut to black at 2429 and to the credits at 17858) and 20 masked windows: 12 dissolves or fades, 5 ambiguous spots (a black cloak or fur streak fills the frame, a very fast whip at 14111-14115, a framing jump at 1334), the title-card dissolve, the slow fade-in from black after 2429, and the **end credits (frames 17858 to 21312, 16 % of the film)**. Other candidates were judged not cuts: fast motion with blur, objects crossing the lens, light changes, slow camera moves, a flash.

**Provenance in the repo** (added after review finding I1): `sintel_cuts.provisional.verification.json` (method text, `n_events` 646, per cut the event id, first-pass sheet, which detector families proposed it, zoom flag) and `sintel_cuts.provisional.decisions.txt` (236 lines of per-event decisions). The verification file is *reconstructed* by `label_sheets.py verification`: `first_pass_sheet` is `event // ROWS` and the zoomed set is hard-coded, so it records the agent's recollection, not a live trace.

**The quantified bias (computed, not guessed):**
- **Seeding bias.** The 183 labelled cuts were found at seeding time by TransNetV2@0.05 **179**, `AdaptiveDetector`@1.2 **182**, `ContentDetector`@8 **107** (weak at `min_scene_len=1`: in action scenes its content value stays above 8 for long runs and the MERGE filter collapses a run into one cut), diff-scan **0**. Recall is measured against a ceiling set by the union of low-threshold detectors; the labels depend most on the adaptive detector (182/183) and then TransNetV2 (179/183), so **they flatter `AdaptiveDetector` at low thresholds**, and every method's recall is probably overestimated by an unknown number of cuts nobody saw. The scan finding nothing new is weak evidence that few exist.
- **Precision 1.00 is seed-dependent too.** TransNetV2@0.5 and Adaptive@3.0 have 0 FP, but every cut they report was also a candidate the labeller saw first on a contact sheet; a detector's confident cut is what the labeller was primed to accept (anchoring). So the default F1 gaps are driven by recall (0.85 vs 0.79 vs 0.89), and "precision 1.00" should be read as "no obvious false positive to a single agent".
- **Mask edges are not widened by the tolerance:** a prediction 1 to 2 frames off a label that sits next to a mask edge is dropped while its label stays (5 labels: 2429, 14109, 15384, 16169, 16426). Widening the masks moves TransNetV2 from 0.917 to 0.921 and changes no ranking; numbers left as run.
- **Offsets are not independent:** label frames equal a detector candidate frame for 183/183 cuts, so "mean offset 0.00 frames" is not a localisation measurement.
- One agent, one pass, small thumbnails: cuts between two similar shots and cuts hidden by motion blur are the likeliest errors in both directions. **Not human-verified.**
- **Dissolves and fades were masked, so EXP-002 has no evidence at all about how the detectors handle them.** The only related evidence is one synthetic 1 s `xfade` in 1.8A where TransNetV2 flagged the middle frame.

**Process failure worth recording:** in the first labelling pass the image reader returned "media removed: request limit" instead of images for the first sheets, and the agent kept writing decisions without having seen them. When the coordinator said the limit had reset, those decisions were discarded (kept as `decisions.invalid-first-draft.txt` and `decisions.contaminated-*.txt`) and every sheet without a real view was redone. The committed decisions contain only decisions made on images actually shown: all 54 first-pass sheets, the 17 second-pass sheets and the zoom strips were re-viewed after the reset ([journal](journal.md#2026-10-16--18b-the-provisional-labels-method-bias-and-a-blind-first-draft)).

### Results 1: part A on the two real films (not part of the bar)

| | Sintel (1080p mkv) | Tears of Steel (720p mov) |
|---|---|---|
| Frames decoded (TorchCodec, exact seek) | 21,312 | 17,620 |
| Decode + resize to 48x27 | 53.4 s = **399 fps** (cold file cache, first run) | 17.4 s = **1,013 fps** |
| TransNetV2 inference (CUDA) | 10.0 s (about 2,140 fps), load 0.38 s | 8.1 s (about 2,160 fps), load 0.26 s |
| Cuts / shots found (threshold 0.5) | 161 / 162 | 139 / 140 |
| Keyframes written (full-res JPEG q90) | 398 in 31.8 s (80 ms each), 92 MB | 325 in 5.3 s (16 ms each), 41 MB |
| Whole `analyze_picture`-equivalent wall time | 99.5 s = **6.72 s per video-minute** | 35.3 s = **2.89 s per video-minute** |
| Peak RAM (process) | 1,926 MB | 1,520 MB |
| Peak VRAM (allocated / reserved) | 327 / 382 MB | 299 / 354 MB |

Warm-cache repeat runs of the detector only: decode + resize on Sintel 34.6 to 37.7 s (565 to 615 fps), 14.95 to 17.7 s on Tears of Steel (995 to 1,178 fps); TransNetV2 model time 9.2 to 9.7 s and 7.9 to 8.5 s. Extrapolation, not measured: a 2 h film at the Sintel rate is about 13 minutes including keyframes. See also [C-015](#c-015--decode-backend-and-keyframe-cost-on-real-film) for the decoder and keyframe-cost finding.

### Results 2: defaults (Sintel, +-2 frames, masked, 3 timing repeats)

| Metric | TransNetV2 (0.5) | ContentDetector (27) | AdaptiveDetector (3.0) |
|---|---|---|---|
| P / R / **F1** (masked, headline) | 1.00 / 0.85 / **0.917** | 0.79 / 0.89 / **0.839** | 1.00 / 0.79 / **0.880** |
| TP / FP / FN | 154 / 0 / 28 | 162 / 42 / 20 | 143 / 0 / 39 |
| F1 unmasked | 0.901 | 0.817 | 0.875 |
| F1 at +-0 / +-5 frames | 0.917 / 0.917 | 0.819 / 0.845 | 0.880 / 0.880 |
| Cuts reported | 161 | 216 | 146 |
| Seconds per video-minute (mean of 3; range) | 3.33 (3.26-3.44) | 3.43 (3.32-3.58) | 4.36 (3.74-5.01) |
| Peak RAM (MB) | 1,241 | 224 | 223 |
| Peak VRAM (MB) | 327 | 0 | 0 |

- **Bar at defaults:** 0.917 - 0.880 = **+0.037**, so the bar is met.
- **Speed is a wash:** 3.3 to 4.4 s per video-minute (about 0.055 to 0.07x real time). TransNetV2's time is about 70 % decode (TorchCodec decode + resize), 20 % model; PySceneDetect's is OpenCV decode of the same file on the CPU, so the model is not the cost.
- **TransNetV2's misses are not random:** of its 28 false negatives at 0.5, 23 lie in two fast-action stretches (8 in frames 1,036-1,572, 15 in 13,104-14,455), with raw probabilities 0.00 to 0.50 (median 0.22; 7 below 0.1, 10 in 0.1-0.3, 11 in 0.3-0.5). The model is under-confident on rapid cuts in stylised CGI where neighbouring shots look alike; its median probability on the cuts it does find is 0.93. (The reviewer recomputed these from the saved probabilities: all match.)
- `ContentDetector` at default over-fires (42 FP) in fast action; `min_scene_len=15` means PySceneDetect cannot report two cuts closer than 15 frames (0.6 s). Setting it to 2 raised content@27 recall from 0.890 to 0.951 but precision fell from 0.794 to 0.653.

**Tears of Steel: speed only (no labels, so no F1)**

| | TransNetV2 | ContentDetector | AdaptiveDetector |
|---|---|---|---|
| Cuts reported | 139 | 155 | 129 |
| Seconds per video-minute (3 runs) | 2.29 (2.17-2.48) | 1.94 (1.75-2.26) | 2.20 (2.00-2.39) |
| Peak RAM (MB) | 1,220 | 151 | 151 |
| Peak VRAM (MB) | 299 | 0 | 0 |

The cut counts are ordered as on Sintel (TransNetV2 between the two PySceneDetect variants). The "hand-labelled" half of the experiment for Tears of Steel is **not done**.

### Results 3: tuning (exploratory, tuned on the same labels, so optimistic)

Masked F1 on Sintel (`exp002_shots.py sweep`, 24 settings, each logged to MLflow):

| detector | setting | cuts | TP | FP | FN | P | R | F1 |
|---|---|---|---|---|---|---|---|---|
| TransNetV2 | 0.05 | 251 | 178 | 28 | 4 | 0.864 | 0.978 | 0.918 |
| | 0.1 | 223 | 174 | 12 | 8 | 0.935 | 0.956 | **0.946** |
| | 0.2 | 196 | 168 | 5 | 14 | 0.971 | 0.923 | **0.946** |
| | 0.3 | 183 | 165 | 3 | 17 | 0.982 | 0.907 | 0.943 |
| | 0.4 | 172 | 161 | 0 | 21 | 1.000 | 0.885 | 0.939 |
| | **0.5 (default)** | 161 | 154 | 0 | 28 | 1.000 | 0.846 | 0.917 |
| | 0.7 | 143 | 141 | 0 | 41 | 1.000 | 0.775 | 0.873 |
| | 0.9 | 100 | 99 | 0 | 83 | 1.000 | 0.544 | 0.705 |
| Content | 10 | 165 | 79 | 64 | 103 | 0.552 | 0.434 | 0.486 |
| | 20 | 218 | 141 | 63 | 41 | 0.691 | 0.775 | 0.731 |
| | **27 (default)** | 216 | 162 | 42 | 20 | 0.794 | 0.890 | 0.839 |
| | 35 | 173 | 155 | 11 | 27 | 0.934 | 0.852 | **0.891** |
| | 45 | 135 | 129 | 2 | 53 | 0.985 | 0.709 | 0.824 |
| | 27, `min_scene_len` 2 | 288 | 173 | 92 | 9 | 0.653 | 0.951 | 0.774 |
| Adaptive | **1.5** | 197 | 178 | 8 | 4 | 0.957 | 0.978 | **0.967** |
| | 2.0 | 179 | 170 | 1 | 12 | 0.994 | 0.934 | 0.963 |
| | **3.0 (default)** | 146 | 143 | 0 | 39 | 1.000 | 0.786 | 0.880 |
| | 5.0 | 88 | 87 | 0 | 95 | 1.000 | 0.478 | 0.647 |

Tuning moves every detector by 0.03 to 0.09 F1, which is more than the 0.037 gap at defaults. TransNetV2 gains 0.03 by lowering the threshold from 0.5 to 0.1-0.2 (the default is conservative on this film). `AdaptiveDetector` gains 0.087 from 3.0 to 1.5-2.0 and then sits **above** TransNetV2's best. `ContentDetector` reaches 0.891 at 35. That ordering is not trustworthy because the labels were seeded by `AdaptiveDetector`@1.2, so adaptive@1.5 sits next to the seed configuration. Sweep-run seconds (3.6 to 5.2) are single runs and noisier than the 3-repeat defaults, so only the defaults are used for speed claims.

### Results 4: held-out check against tuning on the test labels (2-fold by film half)

Pick each family's best setting on one half of the film, score the other half, both directions (`exp002_shots.py split`; logged as `*-heldout`):

| family | tuned on | chosen | F1 on tune half | F1 on held-out half |
|---|---|---|---|---|
| TransNetV2 | first / second half | thr 0.3 / 0.1 | 0.959 / 0.963 | 0.922 / 0.933 |
| Content | first / second | 35 / 35 | 0.884 / 0.899 | 0.899 / 0.884 |
| Adaptive | first / second | 2.0 / 1.5 | 0.995 / 0.969 | 0.921 / 0.966 |

Held-out means: TransNetV2 **0.9274**, Content 0.8915, Adaptive 0.9435. **Discrepancy resolved:** the 1.8B report's original paragraph says held-out TransNetV2 "0.928" (and Content "0.891"); the MLflow runs and the notes give 0.9274 (0.927). This build log uses 0.927, as the re-review and the ledger direct. Adaptive's spread between halves is large (0.921 vs 0.966), inside the noise of 183 cuts and a single agent's labels.

### Results 5: does the resize filter matter? ([C-014](#c-014--transnetv2-input-resize-filter-torchcodec-bilinear-vs-ffmpeg-bicubic))

TransNetV2 was trained on `ffmpeg -s 48x27` input (bicubic), while TorchCodec's decoder `Resize` uses swscale bilinear with antialias. Four filters, same model, masked F1 at threshold 0.5 / 0.3: TorchCodec Resize 0.917 / 0.943; ffmpeg bilinear 0.920 / 0.946; ffmpeg bicubic 0.910 / 0.943; ffmpeg area 0.917 / 0.943. Maximum per-frame difference in output probability 0.052 to 0.072; cuts found differ by 1 to 2 of about 160. Conclusion: at most 0.007 F1, within what one cut changes (0.003 to 0.006). **No change to part A**; the concern raised in the part A report is closed.

### The bar's verdict flips (read this first)

| Comparison | TransNetV2 | Best PySceneDetect | Gap | Against the 0.02 bar |
|---|---|---|---|---|
| Defaults | 0.917 | Adaptive 0.880 | **+0.037** TransNetV2 | met: keep TransNetV2 |
| Tuned on the same labels | 0.946 (thr 0.1-0.2) | Adaptive 0.967 (thr 1.5) | **+0.021** Adaptive | met in the other direction: switch |
| Held out by halves (2-fold mean) | 0.927 | Adaptive 0.944 | **+0.016** Adaptive | below the bar either way |

### Takeaway

The robust, interview-ready statement: **the three detectors are within a few points of each other on a stylised CGI film; TransNetV2 is the most accurate out of the box, but its default threshold is conservative (recall 0.85; it misses fast-action cuts at probabilities 0.2 to 0.5) and a tuned `AdaptiveDetector` is as good or better on these labels.** Speed and resources do not separate them (TransNetV2 needs 0.3 GB VRAM and 1.2 GB RAM, PySceneDetect 0.2 GB RAM). The resize-filter worry is closed. What the experiment cannot say: anything about dissolves or fades, anything not seeded by the labeller's candidates, anything beyond one stylised film.

### Decision (provisional)

Keep TransNetV2 for Phase 1 **only because** it is already pinned in the docs and integrated and tested in part A, and swapping on a 0.016 to 0.021 gap measured on detector-seeded agent labels would not be justified. That is a cost/risk argument, **not an EXP-002 result** ([B-093](decisions.md#b-093--exp-002-decision-keep-transnetv2-provisionally-as-a-costrisk-call-not-a-result)). Two rationales the implementer first wrote were **withdrawn** after review because no run supports them: that TransNetV2 "adds fades/dissolves handling" (dissolves were masked) and that it has "no tuning knob to overfit" (it has one, the threshold, and the same decision proposes tuning it). Also proposed, **not applied** (`config/pipeline.yaml` unchanged): lower `timeline.shots.threshold` from 0.5 to 0.2 pending human labels (full-film F1 0.943 to 0.946 for thresholds 0.1 to 0.3, held-out halves 0.922 to 0.933; at 0.2 recall 0.92 with 5 FP). Re-run with human-verified labels (Sintel and Tears of Steel) before treating it as final; by the experiment's own rule, if human labels put a tuned `AdaptiveDetector` at least 0.02 above a tuned TransNetV2, switch to the simpler detector.

### What changed in the code because of it

- No change to `src/nip/timeline/` (no bug found; the resize and decode findings are findings only).
- Added `eval/exp/exp002_shots.py` (experiment, scorer, `run`, `table`, `sweep`, `split`, `resize-test`, `candidates`, `run-one`), `eval/exp/label_sheets.py` (contact sheets, strips, verification record), the label files and masks sidecar, and the scorer tests.
- 1.10's walking skeleton reuses the cached 1.8B "picture" run for Sintel (161 cuts at threshold 0.5, 398 keyframe JPEGs), see [the journal](journal.md#2026-10-16--110-walking-skeleton-nip-run-on-sintel-with-real-numbers).

### Review that shaped it

The 1.8B review (0 Critical, 3 Important, 7 Minor) is why this entry reads as it does: it caught the verdict flip being buried, two unsupported rationales, tuned numbers that existed only in local logs, and a labels provenance that was not in the repo. See [review-findings.md](review-findings.md#18-part-b-real-film-run-and-exp-002).

### Open items

- **Human verification of the Sintel labels** (Label Studio project from 1.9) and a rerun; the user's spot-check is the ledger's standing condition.
- **Tears of Steel labels** do not exist; half the experiment is open (needs the user's labels or a second agent pass).
- **No evidence on dissolves and fades** (masked); a labelled set with gradual transitions is needed before TransNetV2's supposed advantage there can be claimed.
- `timeline.shots.threshold` 0.5 to 0.2 not applied.
- The labels header does not link `verification.json` (reviewer minor); verification file is reconstructed; mask-edge widening (+0.004); `label_sheets.sheets()` duplicates `_render` (M5, left open).
- `probe().duration_frames` for Sintel reads 21,313 while the decoder gives 21,312 (container duration pads a fraction of a frame; `round(888.032 x 24)`); the decoder is the truth for the frame axis. Not fixed (`src/nip/ingest/media.py`).

---

## EXP-003 · Speech-to-text: Whisper large-v3 vs large-v3-turbo

| | |
|--|--|
| **Question** | Can the laptop use the faster turbo model without losing transcript quality? (from docs/experiments.md) |
| **Variants** | `faster-whisper-large-v3-int8` (Systran/faster-whisper-large-v3) · `faster-whisper-large-v3-turbo-int8` (mobiuslabsgmbh/faster-whisper-large-v3-turbo), faster-whisper 1.2.1, CTranslate2 4.8.3, int8 compute. Added by the experimenter: 8 decoding configurations, each run for both models (VAD on/off, a VAD threshold, `hallucination_silence_threshold`, a word-probability filter, temperature fallback, faster-whisper's full defaults) |
| **Metrics** | WER against the normalized official en SRT (R6: no human-corrected transcripts exist) · substitutions+deletions over reference words ("sub+del") and per-film S/D/I (added after review) · real-time factor (excluding model load) · peak VRAM = device-wide NVML peak (20 ms sampling) minus the idle level read before load · model load time |
| **Success bar (as written)** | Turbo becomes the laptop default if its WER is within +1.0 point and it is at least 1.5x faster |
| **Status** | **Done** (2026-10-16), in two rounds plus a controller ruling on the shipped decoding. MLflow experiment `exp003-asr`: 48 active runs (8 configs x 2 models x 3 runs), checked by the re-reviewer |
| **Result in one line** | The first comparison was unfair: at temperature 0 large-v3 fell into confident repetition loops (WER 0.815 vs turbo 0.574). With equal decoding the two are at parity on WER (fb-p50 0.555 vs 0.543; novad-hst 0.604 vs 0.606), turbo has equal or lower sub+del in every no-VAD arm, is 2.3x to 3.2x faster and needs about half the VRAM: turbo is the default, with the deterministic `novad-hst` decoding by controller ruling ([B-220](decisions.md#b-220--laptop-asr-default-is-faster-whisper-large-v3-turbo-int8), [B-222](decisions.md#b-222--asr-decoding-default-is-the-deterministic-novad-hst-arm)) |
| **Source** | `notes/2.5.md` (EXP-003, Round 2), `reports/2.5-review.md`, `reports/2.5-rereview.md`, `progress.md` (ruling), `notes/2.Wint.md` (2b); `nip eval compare --exp EXP-003 --md` output saved at `data/exp003/compare_EXP-003.md` (git-ignored); code `eval/exp/exp003_asr.py`; commits `bd74e53`, `0440e1d`, `fa47838`, `3d66622` |

### Setup

- **Set:** Sintel (888.03 s, 110 reference words) + Tears of Steel (734.10 s, 334 reference words), English audio track 0, language forced `en`, the same wav for both models, reference = the official en SRT normalized the same way as the hypothesis (word-level Levenshtein with S/D/I bookkeeping, checked by the reviewer).
- **Plan:** laptop (RTX 4060 Laptop 8 GB), host Windows process, not the nip image and not Ray. 3 fresh-process runs per (model, config) under `data/gpu.lock`.
- **Reference bias (R6):** the SRT omits the credits song and shouts, so insertions there count for both models. On Sintel the words after the last cue (the credits song "I Move On") are 131 (large-v3) and 138 (turbo) in the run-1 `novad-p50` transcripts, which drives Sintel's WER above 1 for both; read WER next to sub+del.

### Results 1: round 1 (VAD, then temperature 0 with a probability filter)

- **VAD on** mis-timed segments by up to 234 s ("I have failed.", SRT 445.85 s, came back at 211.75 / 212.0 s in both models' transcripts) and deleted 45-95 words per film: rejected for frame placement. `vad03` (threshold 0.3) has the same timing failure.
- **VAD off at temperature 0** gets the times right but inserts words over music; a mean-word-probability filter `min_prob 0.5` cut insertions 248 → 200 (turbo) and 336 → 293 (large-v3).
- **Round-1 headline (`novad-p50`):** WER large-v3 0.815 vs turbo 0.574, sub+del 0.155 vs 0.124, RTF 0.0339 vs 0.0139 (2.44x), peak VRAM 2.32 vs 1.29 GiB. The agent's explanation ("large-v3 hallucinates more over music"; "hallucinated segments sit at p 0.05-0.56") was wrong.

### What the review found

The reviewer located the insertions in the saved transcripts: the ToS gap (insertions 117 vs 38) was large-v3 repeating lines at high confidence ("We're out of time, we're out of time!" x5 at 415-426 s, p 0.91-0.99; "Hmmmm..." p 0.95; "Oh, my God." x6+ on Sintel, p 0.72-0.96). `temperature=0.0` disables faster-whisper's temperature fallback (retry on compression ratio > 2.4 or average log-probability < -1.0), the mechanism meant for these loops, and `min_prob 0.5` keeps them ("Thanks for watching!" at 0.61 and "To be continued" at 0.55 also pass). The round-1 headline compared one model with its safety net removed (finding I-1).

### Results 2: every arm, equal footing (means over 3 runs; each cell large-v3 / turbo)

From `notes/2.5.md` (4-decimal means checked against MLflow by the re-reviewer); VRAM and load from `data/exp003/compare_EXP-003.md`.

| config | WER | sub+del | Sintel S/D/I | ToS S/D/I | RTF | peak VRAM over idle (MiB) | what it showed |
|---|---|---|---|---|---|---|---|
| `vad` (VAD on) | 0.396 / 0.381 | 0.374 / 0.358 | 2/48/0, 2/47/0 | 21/95/10, 18/92/10 | 0.0131 / 0.0054 | 2,345 / 1,323 | times wrong, 48-95 deletions: rejected |
| `vad03` (threshold 0.3) | 0.367 / 0.356 | 0.333 / 0.324 | 0/45/0, 0/45/0 | 24/79/15, 24/75/14 | 0.0119 / 0.0056 | 2,368 / 1,282 | same timing failure: rejected |
| `novad` (T=0, no filter) | 0.908 / 0.673 | 0.151 / 0.115 | 4/1/210, 4/1/199 | 36/26/126, 36/10/49 | 0.0363 / 0.0143 | 2,339 / 1,321 | right times; large-v3 loops (ToS ins 126) |
| `novad-hst` (T=0, hallucination_silence 2 s) | 0.604 / 0.606 | 0.122 / 0.115 | 2/2/187, 4/1/180 | 25/25/27, 36/10/38 | 0.0372 / 0.0161 | 2,338 / 1,321 | no large-v3 loop on ToS (ins 27); deterministic; **shipped by ruling** |
| `novad-p50` (round-1 ship: T=0 + p >= 0.5) | 0.815 / 0.574 | 0.155 / 0.124 | 4/1/176, 4/1/162 | 38/26/117, 34/16/38 | 0.0339 / 0.0139 | 2,379 / 1,321 | round-1 headline; large-v3 handicapped |
| `fb` (temperature fallback) | 0.618 / 0.661 | 0.138 / 0.113 | 2/1/171, 3/1/194 | 33/25/42, 36/10/49 | 0.0783 / 0.0236 | 3,695 / 1,422 | loops gone; without the filter turbo is 4.3 points worse |
| `fb-p50` (fallback + p >= 0.5) | 0.555 / 0.543 | 0.149 / 0.124 | 4.7/1.3/147, 4/1/149 | 33/27/33, 34/16/37 | 0.0705 / 0.0219 | 3,448 / 1,605 | lowest WER for both; shipped by 2.5, then superseded |
| `fb-cond` (all faster-whisper defaults) | 0.863 / 0.893 | 0.121 / 0.119 | 2/0/182, 6/1/188 | 43/8/148, 31/15/155 | 0.1614 / 0.0380 | 3,744 / 1,383 | unstable (WER SD 0.23-0.26): rejected |

Model load (s), `novad-hst`: 6.60 / 3.78; `fb-p50`: 10.4 / 5.0. Fallback arms: WER SD 0.003-0.018 over 3 runs (the T=0 arms: SD 0), 1.6-2.1x slower per the notes (the re-reviewer computed 2.16x for large-v3 `fb`).

MLflow runs for the two decision arms (from the compare output): `novad-hst` large-v3 `b14fe7f3…`, `9a403820…`, `5348f6db…`, turbo `fd9c2ae5…`, `23e5df58…`, `c09f0cc9…`; `fb-p50` large-v3 `654eaad6…`, `bcb29ef9…`, `dd9c0c4c…`, turbo `2d2180e7…`, `e890574a…`, `9b66b60f…`.

### The bar, per arm (derived from the table)

| Arm | WER gap turbo - large-v3 | Speed-up (RTF ratio) | Bar met |
|---|---|---|---|
| `fb-p50` | -1.2 points | 3.2x | yes |
| `novad-hst` | +0.2 points (0.6059 vs 0.6036) | 2.3x | yes |
| `novad-p50` | -24.1 points | 2.44x | yes, but large-v3 handicapped |
| `fb` | +4.3 points | 3.3x | **no** |

### What the re-review added

- For turbo the fallback gains nothing measurable on these films: the ToS turbo run-1 transcripts of `fb-p50` and `novad-p50` are byte-identical, sub+del is identical (0.1239), EXP-004 is identical; the 3.1-point WER gap is Sintel insertions in the credits song and the "Scales!" region (162 at T=0 vs 157 / 147 / 144 over the three fallback runs). Run 1 alone gives 0.563 vs 0.574.
- The -1.2-point margin at `fb-p50` is inside turbo's run spread (0.529-0.563), so "parity", not "turbo ahead".
- Measurement conditions changed between rounds: idle device VRAM 1,128-1,577 MiB in the fallback runs vs about 505-520 MiB in the round-1 runs; peak is measured over idle, so the VRAM deltas stand, but the fallback's RTF cost compares an afternoon session with a morning one, not an interleaved re-run.

### Takeaway and decision

- The round-1 gap (0.815 vs 0.574) came from large-v3 repeating lines with the temperature fallback disabled, not from a tendency to hallucinate over music. With equal decoding the models are at WER parity; turbo wins on speed and memory, and its sub+del is equal or lower in every no-VAD arm. **Turbo-int8 is the laptop default** ([B-220](decisions.md#b-220--laptop-asr-default-is-faster-whisper-large-v3-turbo-int8)).
- **Decoding:** 2.5 shipped `fb-p50` ([B-221](decisions.md#b-221--decoding-no-vad-temperature-fallback-min_prob-05-superseded-by-b-222-for-the-fallback-and-the-filter)); after the re-review the controller ruled for the deterministic `novad-hst` (bar met at +0.2 points, best turbo sub+del of the deterministic arms, RTF 0.0161, same transcript every run) ([B-222](decisions.md#b-222--asr-decoding-default-is-the-deterministic-novad-hst-arm)). Cost: a rare repetition loop is not retried.
- **Caveats:** English only, 2 films, 444 reference words in total (sum of the two films); the reference is subtitle text, not a human transcript; RTF is sensitive to CPU load from other agents (a round-1 run overlapping ruff/pytest gave large-v3 RTF 0.0595 +- 0.0208; the table uses clean re-runs); fallback arms' RTF and VRAM spread with the number of retried segments (large-v3 VRAM SD up to 336 MiB); the VAD mis-timing cause was not examined (likely faster-whisper 1.2.1's chunk-timestamp restore with array input and word timestamps). In the nip image later, 2.close measured turbo RTF 0.019 at 1.29 GiB (outside this experiment).

## EXP-004 · Script-to-transcript alignment: token-level monotonic vs rapidfuzz line-level

| | |
|--|--|
| **Question** | Which alignment places script lines on the right frames most often? (from docs/experiments.md) |
| **Variants** | Token-level monotonic alignment (difflib `SequenceMatcher` blocks, per-line clusters in script order) · line-level fuzzy matching (rapidfuzz `partial_ratio_alignment`, forward-only cursor, 400-char lookahead). Added: the line start rule, first matched word `f_in` vs a 0.3 s first-word cap (`EXP-004` vs `EXP-004-cap`) |
| **Metrics** | Share of labelled lines whose aligned start is within +-12 frames of the marked start (an unplaced line is a miss), per film; share placed; median offset |
| **Success bar (as written)** | At least 95 % within tolerance |
| **Status** | **Done, bar not met** (2026-10-16). Deterministic: one run per variant (seed 1). MLflow experiment `exp004-align` |
| **Result in one line** | Token-level wins both ways: 0.68 vs 0.51 within +-12 frames with the first-word cap (shipped start rule), 0.46 vs 0.37 without; 16 % of labelled lines are never placed (short exclamations the ASR missed) ([B-223](decisions.md#b-223--token-level-alignment-is-the-default-with-a-03-s-first-word-cap)) |
| **Source** | `notes/2.5.md` (EXP-004), `reports/2.5-review.md`; outputs `data/exp003/compare_EXP-004*.md`, `data/exp003/exp004_matrix.txt` (git-ignored); code `eval/exp/exp004_align.py`, `exp004_scripts.py`; labels `eval/exp/exp004_labels/`; commits `bd74e53`, `0440e1d` |

### Set and labels (R5, [B-225](decisions.md#b-225--exp-004-ground-truth-derived-as-broadcast-scripts-labels-outside-evallabels))

- Derived as-broadcast scripts: Sintel 26 labelled lines, Tears of Steel 76 (one line per official en cue, start = cue start frame at the probed 24/1), plus 3 lines of Sintel's real first-minute script paired to cues 7, 8 and 10: **105 labels, 102 distinct targets** (the 3 real-script labels reuse cue starts already in the Sintel set; review M2). `labeller: agent`. "3 titles with hand-marked line starts" (the doc) did not exist.
- **Is the reference fair?** An agent energy-onset spot-check on 4 Sintel lines found the cue starts 0.15-0.35 s after the audible onset and Whisper's first word 0.1-0.7 s before it, so the labels measure agreement with subtitle timing, not speech onset.
- Input: EXP-003 run-1 turbo transcripts, `fb-p50` (2.5's shipped config at the time); the round-1 `novad-p50` transcript gives the same 0.676 / 0.514.

### Results

`EXP-004` (line start = first word `f_in`):

| Metric | token | line |
|---|---|---|
| labelled_lines | 105 | 105 |
| placed | 0.84 | 0.67 |
| within_12f | **0.46** | **0.37** |
| within_12f_sintel | 0.12 | 0.15 |
| within_12f_sintel-real-script | 0.00 | 0.33 |
| within_12f_tears-of-steel | 0.59 | 0.45 |
| median_abs_offset_f | 11.00 | 10.00 |
| median_offset_f | -7.00 | -4.00 |

`EXP-004-cap` (first-word cap 0.3 s, the shipped start rule):

| Metric | token | line |
|---|---|---|
| labelled_lines | 105 | 105 |
| placed | 0.84 | 0.67 |
| placed_sintel / real-script / tears-of-steel | 0.92 / 0.67 / 0.82 | 0.69 / 1.00 / 0.64 |
| within_12f | **0.68** | **0.51** |
| within_12f_sintel | 0.77 | 0.46 |
| within_12f_sintel-real-script | 0.67 | 1.00 |
| within_12f_tears-of-steel | 0.64 | 0.51 |
| median_abs_offset_f | 7.00 | 7.00 |
| median_offset_f | 0.50 | 2.50 |

MLflow runs per the notes: `EXP-004` token `336d91ed7ce943e1a28458a8cc86cf41`, line `f461a6e1329d48e1b25628b4a0bfc76f`; `EXP-004-cap` token `54eab44b3db5483281f7431d35e9da7b`, line `8e1ab790289c4fd2b34c09c72363a718`. The compare files in `data/exp003` show the same values with other run ids (`aabaed7c…` / `7374f6a9…`; `a08eb10c…` / `f3fabb05…`), presumably the re-run on the `fb-p50` transcripts; not checked against MLflow.

**Sensitivity to the ASR transcript** (token, turbo, with the cap; `EXP-004-asr-input`, `exp004_matrix.txt`): vad 0.41, vad03 0.40, novad 0.69, novad-hst 0.68, novad-p50 0.68, fb 0.69, fb-p50 0.68, fb-cond 0.63. VAD's mis-timing costs alignment directly (token 0.41 vs 0.68).

**With large-v3 transcripts** (`EXP-004-largev3-cap`): the notes give token 0.54 / line 0.52; the saved compare output shows 0.53 / 0.48 (runs `ac1fb4fe…` / `c4204ff5…`), which matches the matrix's large-v3 `fb-p50` rows (0.533 / 0.476), while 0.54 / 0.52 match its `novad-p50` rows (0.543 / 0.524). Both are below turbo (0.68 / 0.51).

### Takeaway and decision

- Token-level wins with and without the cap; the cap (a line's start is at most 0.3 s before its first word ends) moves token from 0.46 to 0.68. **Bar (95 %) not met.** Where the points go: 16 % of labelled lines are never placed (short exclamations: "Whoaaa!", "Cut!", "Scales!"); among placed lines about 81 % are within tolerance. ToS offsets are centred (median +3.5 frames), Sintel's sit about -9 frames. The real-script set is 3 lines (2 of 3 within tolerance, token): anecdotal.
- **Decision:** `timeline.align.variant: token`, `first_word_cap_s: 0.3`; rapidfuzz stays selectable ([B-223](decisions.md#b-223--token-level-alignment-is-the-default-with-a-03-s-first-word-cap)). Reaching 95 % needs hand-marked starts and an ASR that catches short exclamations (open question to the controller: is a human-marked subset wanted?).
- **Under the shipped `novad-hst` decoding** ([B-222](decisions.md#b-222--asr-decoding-default-is-the-deterministic-novad-hst-arm)) the token result is unchanged (0.676); the matrix shows the line variant at 0.590 there (vs 0.514 on `fb-p50` / `novad-p50`), so the token-vs-line margin narrows to about 0.09 but keeps its sign. W-int's notes say "token 0.676 / line 0.514, same as novad-p50"; the line figure in that sentence is the `novad-p50` value.
- **The line variant's lookahead is load-bearing** (reviewer check): widening it from 400 chars drops line from 0.514 to 0.286, because a far false match strands every later line. The window holds the line variant up, so the verdict stands.

## EXP-005 · Fact extraction context: 8k vs 32k tokens

| | |
|--|--|
| **Question** | Does giving the extractor neighbouring scenes improve facts enough to matter? (from docs/experiments.md, which adds "given the laptop is capped at 8k context") |
| **Variants** | 8k (scene + bible entries) · 32k (scene + two neighbours on each side + bible entries). Only the 8k arm ran |
| **Metrics** | Fact precision and recall · downstream recall of the Layer 1 `plot.*` rules |
| **Success bar (as written)** | Keep 8k everywhere if 32k improves fact recall by less than 2 points |
| **Status** | **Inconclusive.** 8k arm run on the laptop (2026-10-17, re-measured 2026-10-18 after fix round 1); 32k arm deferred to the Phase 4 cloud (ruling R4, [B-120](decisions.md#b-120--phase-2-plan-rulings-r1-to-r15-adopted)) |
| **Result in one line** | 8k arm: fact precision 0.75 ± 0.03, recall 0.77 ± 0.04 (3 seeds), plot-rule recall 0.03 ± 0.05; after 2.1B's fix round 1: P 0.647, R 0.737, plot-rule recall 0.28. The bar cannot be judged without the 32k arm |
| **Source** | `notes/2.1B.md` (EXP-005, EXP-005 note), `reports/2.1B-report.md`, `reports/2.1B-review.md`; harness `eval/exp/exp020_rules.py`; commits `b8d320b`, `22074b9`, `8a5d5bd` |

### Setup

- **Set (deviation, R3):** synthetic show seeds 1–3 (clean twins), not 3 Beverly Hillbillies episodes; truth = generator facts (`labeller: generator`), not hand labels.
- **Arm:** enum arm, shipped schema and checks, scene + bible entries, default KV cache at `--max-model-len 8192`, qwen3.5-4b-awq (`cyankiwi/Qwen3.5-4B-AWQ-4bit`), vLLM 0.30 in ray-head, xgrammar with `disable_any_whitespace`, `NIP_VRAM_MARGIN_GB=0.25`, temperature 0, thinking off. 4 calls in flight.
- **Fact metric:** extracted facts matched to generator truth by exact line (predicate, subject, object).
- **Calls:** 486 over 3 seeds (clean + injected), 0 failed.

### Results

| Run | Fact P | Fact R | Plot-rule recall | Source |
|---|---|---|---|---|
| 8k, first 2.1B passes, seed 1 / 2 / 3 | 0.753 / 0.723 / 0.774 | 0.770 / 0.733 / 0.818 | — | MLflow d3d30fa1…, ca6c3ff9…, 43199af5… |
| 8k, first 2.1B passes, mean ± sd | **0.75 ± 0.03** | **0.77 ± 0.04** | **0.03 ± 0.05** (1 of 36 planted, `EXP-020-rules` enum) | `nip eval compare --exp EXP-005 --md` |
| 8k after fix round 1, without derived presence (`enum-r1-nopresence`) | 0.728 | 0.737 | 0.03 | `EXP-020-facts` |
| 8k after fix round 1, shipped (`enum-r1`) | 0.647 | 0.737 | **0.28** | `EXP-020-facts`, `EXP-020-rules` |

The fix-round-1 drop in precision is the derived speaker presence being scored against truth that puts `present_at` on the action line ([C-24](#c-24--derived-speaker-presence-with-without-and-skipping-intercut-scenes)); recall is unchanged by it.

### Takeaway

Per-scene prompts are about 1.5k tokens, so 8k vs 16k changes nothing in what the model sees; only the 32k variant is a different input. The 8k arm's facts are good enough to measure (P about 0.75), but the Layer 1 rules found almost nothing on them until 2.1B's fix round 1 (0.03 → 0.28), so the bottleneck at this stage was the pipeline and the predicate choice, not context. The R4 premise "laptop capped at 8k" was outdated: the shipped planner places the model at 16k with the default KV cache, and FP8 KV starts at 32k 10/10 ([EXP-018](#exp-018--kv-cache-precision-on-the-laptop)).

### Decision

[B-182](decisions.md#b-182--exp-005-8k-arm-only-inconclusive-until-the-32k-arm-runs): inconclusive until the 32k arm runs (Phase 4 cloud, or on the laptop with an FP8 confound if the controller wants it before Phase 4).

### What changed in the code because of it

Nothing in the extraction context. The numbers above were produced through the shipped path, including 2.1B's guard and checks.

### Review that shaped it

The 2.1B reviewer re-derived the per-seed P/R from MLflow (d3d30fa1, ca6c3ff9, 43199af5: all match) and accepted the inconclusive status. Their note to the controller: R4's "laptop capped at 8k" is outdated and the 32k arm could run on the laptop with the FP8 confound.

### Open items

- The 32k arm (the whole bar).
- Hand-labelled facts on real episodes (R3); the generator truth is synthetic template text, one model, one seed per show.
- Fact precision is understated by derived presence (scored as false positives) and by unlabelled flavour holds ([EXP-020](#exp-020--entity-resolution-enum-constrained-ids-vs-fuzzy-matching-afterwards)).

## EXP-006 · Grounding validator threshold

| | |
|--|--|
| **Question** | How strict should the quote check be before a fact is dropped? (from docs/experiments.md) |
| **Variants** | rapidfuzz `partial_ratio` threshold 85 · 90 · 95 (first wave, 2.1). Added in the second wave (2.1B): `t90-checks` = threshold 90 plus the argument type, zero-confidence and duplicate drops |
| **Metrics** | Share of true facts wrongly dropped (`true_dropped_rate`) · share of hallucinated facts kept (`hallucinated_kept_rate`), on a labelled sample of 300 extracted events |
| **Success bar (as written)** | ≤ 2 % true facts dropped and ≤ 1 % hallucinated facts kept; choose the highest threshold that meets both |
| **Status** | **Done, bar not met** (2026-10-16 first wave; 2026-10-17 second wave; drop counts corrected in fix round 1) |
| **Result in one line** | The threshold makes no difference (true dropped 0.00, hallucinated kept 0.93 at 85, 90 and 95): quotes are verbatim or cite the wrong line, and the hallucinations are wrong arguments with correct quotes. Adding argument kinds per predicate cuts hallucinated kept to 0.27 at 0.007 true dropped, still above the bar |
| **Source** | `notes/2.1.md` (EXP-006), `notes/2.1B.md` (EXP-006 follow-up, fix round 1 M5), `reports/2.1-review.md`, `reports/2.1B-review.md`; code `eval/exp/exp006_grounding.py`, labels `eval/exp/exp006_labels.jsonl`; commits `38fa323`, `6b2ddf4`, `b8d320b`, `22074b9` |

### Setup

- **Sample:** 300 raw events sampled with seed "exp006/1" from the EXP-020 enum pass (qwen3.5-4b-awq, synthetic show seed 1, 150 scenes, 564 raw events).
- **Labels:** 134 from `truth.json` (generator), 166 by the implementing agent. `true` = the line supports the predicate, subject and object; `hallucinated` = it does not; value ignored. Result: 150 true, 150 hallucinated.
- **Deviation (review M-6):** the spec's set is "Extraction output from EXP-005's episodes" (Beverly Hillbillies); the brief and R3 put it on the synthetic show. The labels are not hand labels by a person.
- **Second wave:** the same 300 event ids, re-scored on the replayed raw events (`exp020_resolution extract --replay` with the shipped `save_events`, then `exp006_grounding sweep`), no model calls.

### Results 1: thresholds (2.1, first wave)

Table from `nip eval compare --exp EXP-006 --md` (the re-sweep after 2.1's fix round 1; every number unchanged from the first sweep; the fixed P/R/F1, noise, cost and coverage rows print "—" and are left out):

| Metric | t85 | t90 | t95 |
|---|---|---|---|
| Seeds (n) | 1 | 1 | 1 |
| hallucinated_kept_rate | 0.93 | 0.93 | 0.93 |
| kept_rate | 0.97 | 0.97 | 0.97 |
| n_generator_labels | 134.00 | 134.00 | 134.00 |
| n_hallucinated | 150.00 | 150.00 | 150.00 |
| n_true | 150.00 | 150.00 | 150.00 |
| true_dropped_rate | 0.00 | 0.00 | 0.00 |
| MLflow runs | 8e982f65c5784d148268bebbb1508d39 | f289e6c01f8d408d9b6342ba94f3931b | aaa308e89a984dd59b23bc2f2054c7f7 |

- Grounding scores over all 564 enum events: 544 at 100, 20 below 85 (26 to 52), none in [85, 100). The reviewer recomputed `rates()`: 140/150 = 0.933 hallucinated kept at every threshold.
- The 10 hallucinated events the check did drop were all citations of the neighbouring line, each with a wrong object.

### Results 2: argument type checks (2.1B, second wave)

Table from `nip eval compare --exp EXP-006 --md` (`data/exp2.1b/exp006.md`; the 2.1B re-logged runs):

| Metric | t85 | t90 | t95 | t90-checks |
|---|---|---|---|---|
| hallucinated_kept_rate | 0.93 | 0.93 | 0.93 | **0.27** |
| true_dropped_rate | 0.00 | 0.00 | 0.00 | **0.01** (1/150) |
| kept_rate | 0.97 | 0.97 | 0.97 | 0.63 |
| hallucinated_dropped_argument_type | — | — | — | 89 (first count; 82 above the threshold, see below) |
| hallucinated_dropped_zero_confidence | — | — | — | 17 |
| hallucinated_dropped_duplicate | — | — | — | 2 (first count; 0 above the threshold) |
| true_dropped_argument_type | — | — | — | 1 |
| n_true / n_hallucinated | 150 / 150 | 150 / 150 | 150 / 150 | 150 / 150 |
| MLflow runs | 54a3a4ba… | 890e7a87… | 74081b1e… | 21c7fc2a… |

- Reviewer re-derivation from the file: hallucinated kept 0.2733 (41/150), true dropped 0.0067 (1/150), on the same 300 seeded positions.
- **Drop-count correction (review M5, fix round 1):** the replay called `save_events(..., threshold=0)`, so 9 hallucinated events whose quote already scored below 90 were also tagged `argument type`. Counted above the threshold only: argument type **82**, zero confidence 17, duplicate 0, so the checks' net effect is 99 of 150. The 0.27 / 0.007 headline is unchanged; the MLflow run was re-logged (new run id not recorded in the notes).
- The one true event dropped: `mentions dov → Quill Archive`, a place; by the prompt's definition mentions are organizations, brands or products, so the agent label "true" is itself debatable.
- The 41 hallucinated events still kept are type-correct but wrong: relationship 12 (pairs guessed from "X and Y argue quietly"), state 11, learns 9, mentions 3, references 3, decision 2, holds 1.
- On the whole enum arm (564 events) the checks dropped argument type 164 (holds 103, learns 23, references 14, mentions 11, present_at 5, state 5, wearing 3), zero confidence 41, duplicate 3; 356 kept. Free-text arm (653): argument type 27, duplicate 1; 625 kept.

### What was found

1. **On real output the threshold is irrelevant.** The model copies quotes verbatim (544/564 score 100) or cites the wrong line (scores 26–52). Nothing falls between 85 and 100.
2. **The quote check bounds quotation, not truth.** 0 % of true events are dropped, but 93 % of hallucinated events are kept: they are wrong arguments or predicates with correct quotes (`holds dov → ada` for "share a thermos"; `learns` on a line where the speaker reveals the secret; the reviewer's spot check of 14 agreed, e.g. `mentions ada → Brightwave` on "Ask me after another cup").
3. **Part of the hallucination set is an enum artifact.** 55 of the 150 hallucinated events are `holds` with a character as object (the implementer's count by raw `object` key; the reviewer counted 61). Props are not in the registry and the enum arm used `UNKNOWN` for 3 of 564 arguments, so it picks a valid but wrong key.
4. **Argument kinds catch wrong-argument errors, not wrong-predicate or invented-relation errors** (the 41 survivors).

### Takeaway

D-005's quote check guarantees that the quote is in the cited line and nothing more. A deterministic check of argument kinds per predicate, taken from the prompt's own definitions, removes about two thirds of the hallucinations (net 99 of 150) at a cost of 1 debatable true event. The remaining errors need a different lever (prompt, or a model-side check).

### Decision

First wave: keep 90 and propose argument checks ([B-163](decisions.md#b-163--exp-006-first-wave-keep-threshold-90-the-bar-is-not-met-by-any-threshold), [B-155](decisions.md#b-155--grounding-normalized-partial_ratio--90-ratio-for-over-long-quotes-two-word-minimum)). Second wave: ship the checks; status done, bar not met ([B-181](decisions.md#b-181--exp-006-ship-the-argument-checks-the-bar-is-still-not-met), [B-167](decisions.md#b-167--post-model-drops-zero-confidence-duplicates-argument-kinds-per-predicate)).

### What changed in the code because of it

| | Before | After |
|---|---|---|
| Drop reasons in `save_events` | quote only | quote, zero confidence, duplicate, argument type, no subject (and from fix round 2 unknown holds value) |
| Argument kinds | none (data-model lists predicates only) | `entities.ARG_KINDS` per predicate, from the prompt's definitions |
| Candidates | created during resolution | created only for kept events (`lookup` / `typed` / `ensure`); kinds provisional ([B-171](decisions.md#b-171--a-candidate-entitys-guessed-kind-is-provisional)) |
| Quote length | any | at least two words unless the whole line ([B-155](decisions.md#b-155--grounding-normalized-partial_ratio--90-ratio-for-over-long-quotes-two-word-minimum)) |
| Threshold | 90 (constant) | 90 (`config/pipeline.yaml`, moved by W-int) |

### Review that shaped it

2.1 review (M-6): state the enum-forced `holds` → character share, the single labeller and the templated note shared by all 150 `hallucinated` labels (so per-event judgement cannot be audited from the file), and the set deviation. 2.1B review: verified the 0.27 / 0.007 on the same sample (re-derived from the file), found the drop-count double count (M5), and noted that the "one real pass" asked by the brief reports fact P/R (EXP-020 / EXP-005), not hallucinated-kept / true-dropped, because the shipped pass has no EXP-006 labels (M9).

### Open items

- The bar is not met (0.7 % true dropped is inside 2 %, 27 % hallucinated kept is far above 1 %).
- Labels by one agent with one templated note for all hallucinations; no person checked them.
- One model, one pass at temperature 0, synthetic template text; the spec's real-episode set (R3) is not done.
- The new `t90-checks` run id after the M5 re-log is not in the notes.

## EXP-007 · Story order: rules only vs rules + LLM

| | |
|--|--|
| **Question** | Does sending ambiguous scene transitions to the LLM improve story order enough to justify the calls? (from docs/experiments.md) |
| **Variants** | Rules only · rules + LLM for ambiguous transitions. As run: `rules` (no LLM, no bible), `rules+llm` (prompt v1, `knowledge.story.v1.md`), `rules+llm-v2` (prompt v2), plus two reference arms added by the experimenter: `rules+bible` (the bible's `story_overrides`) and `truth` (the generator's order, a sanity check) |
| **Metrics** | Kendall tau-b against the generator's story order (ties = shared seq) · precision of `plot.knowledge_order` and `plot.dead_acts` (downstream, from the four Layer 1 rules on oracle facts). Added: P/R/F1 of all four plot rules, `story/day_acc_present`, flashback and simultaneous recall/precision, `story/ambiguous`, `story/llm_calls`, `story/llm_seconds`, `story/verdict_acc` |
| **Success bar (as written)** | Keep the LLM step if rule precision rises by ≥ 3 points |
| **Set / Plan** | Docs: 6 Beverly Hillbillies episodes + the synthetic show, laptop. As run (R3): the synthetic show in two variants (as generated; ambiguous transitions) x seeds 1-3, oracle facts fixed; laptop RTX 4060 8 GB, qwen3.5-4b-awq |
| **Status** | **Done on the synthetic sets** (2026-10-17); real-content check deferred with R3. 30 active MLflow runs (2 variants x 5 arms x 3 seeds) in experiment `exp007-story`, tag `exp=EXP-007` |
| **Result in one line** | On the base show the LLM is never asked (0 ambiguous transitions) and every arm ties at 1.00 (tau 0.9998). On the ambiguous variant prompt v1 is net harmful (verdict accuracy 0.29, planted dead_acts recall 1.00 → 0.56) although pooled precision rises 0.60 → 0.78; prompt v2 raises pooled precision of dead_acts + knowledge_order 0.60 → 0.90 (+30 points, bar +3) with all 18 planted flags found and tau 0.870 → 0.983. v2 was written after seeing v1's runs and names the generator's own cue templates, so +30 is a ceiling for explicit cues on this generator ([B-196](decisions.md#b-196--exp-007-decision-keep-the-llm-step-with-prompt-v2-bible-overrides-first)) |
| **Source** | `notes/2.2B.md` (Results, Takeaway, Decision), `reports/2.2B-report.md`, `reports/2.2B-review.md`, `reports/2.2B-rereview.md`; `notes/2.2.md` ("For EXP-007"); code `eval/exp/exp007_story.py`, `eval/synthetic/ambiguous.py`, `config/prompts/knowledge.story.v2.md`; commits `11354bc`, `23f13d4`, `6dc6ba8`; tables `nip eval compare --exp EXP-007 --md --subset all` (`data/exp007/compare_all.md`, git-ignored) |

### Why a new variant was needed

2.2 measured the base synthetic show: rules only tau 0.9998, rules + bible 1.0000; stripping every "NEXT MORNING" gives 14 ambiguous transitions and the next-day default still gets all 150 days right ([C-27](#c-27--story-order-on-the-base-synthetic-show-rules-only-vs-rules--bible-and-stress-variants)). A regression in that generator is always a next day, so an LLM cannot improve on the default there. The controller ruled that 2.2B add an "ambiguous transitions" variant with truth ([B-191](decisions.md#b-191--an-ambiguous-transitions-synthetic-variant-so-exp-007-can-discriminate)).

### The ambiguous variant (`eval/synthetic/ambiguous.py`)

Story time is moved out of what the rules read (heading, previous scene's transitions, all-caps opening super) into ordinary prose; truth (`story_day`, `story_seq`, `marker`) is recomputed; deterministic per seed. Seed 1 counts (seeds 2 and 3 in `data/exp007/ambiguous/seed<n>/notes.json`):

| kind | what changes | truth | seed 1 scenes |
|---|---|---|---|
| `loose_next_day` | every NEXT MORNING heading becomes MORNING | the next day (what the rules default to) | 38 |
| `later_unstated` | 4 NEXT MORNING headings become LATER | next day (the rules read LATER as the same day and never ask) | 4 |
| `flashback_unmarked` | the 2 casualty flashbacks lose "(FLASHBACK)" and "Years earlier."; 4 chat scenes, and 2 chat scenes after a death (one character replaced by the casualty), become memories; each opens with "<N> years ago." (N 3..10, distinct); heading time of day set earlier than the previous scene's | flashback, `story_day` = preceding present day - 365 N, ranked first | 8 |
| `simultaneous_unmarked` | each SAME TIME scene loses "(SAME TIME)" and opens with "At the same moment," / "Meanwhile," / "Across the harbor, at that very moment,"; time of day set earlier than its pair's | shares the seq of the scene before it | 6 |

Silent cases (heading cannot regress, so the rules never ask): seed 1 none; seed 2 two simultaneous + two flashback; seed 3 two simultaneous. Checks: the reviewer confirmed the discriminating cue is prose only (rules-only flashback and simultaneous recall 0.00 in MLflow) and the truth is clean (`violations(show) == []`, truth arm 12/12); a regex cue reader solves seed 1 (tau 1.0). `later_unstated` scenes have no prose cue at all (review M1), so they are not resolvable from text.

### Setup

- **Fixed fact set:** oracle facts from `truth.json` loaded by `eval.exp.layer1_oracle.consolidate` (2.3's stand-in for 2.1's consolidation), identical in every arm; only `scene.story_seq`, `markers`, `story_inferred` differ ([B-192](decisions.md#b-192--exp-007-holds-the-facts-fixed-oracle-facts-only-the-story-columns-vary-between-arms)). The four Layer 1 SQL rules run in a throwaway Postgres database (`nip_exp007`, created and dropped per arm); labels = the injected show's 12 plot labels per seed (the four 2.9A plot-L1 injectors stacked); P/R/F1 through `eval.report.run`.
- **Model and serving:** qwen3.5-4b-awq (`cyankiwi/Qwen3.5-4B-AWQ-4bit`) via the shipped serving path in the `ray-head` container (`docker compose -f compose.yaml -f compose.dev.yaml -f eval/exp/exp001.compose.yaml`), `NIP_VRAM_MARGIN_GB=0.25`; Plan from the probe: 16384 context, gmu 0.79, `--enforce-eager`, xgrammar structured outputs; host-side `LLMClient` at `NIP_SERVE_URL=http://127.0.0.1:8001`; temperature 0; `data/gpu.lock` held while the model was up.
- **Verdict scoring:** a verdict is right when its relation equals the truth relation of that scene to the last present scene before it in the truth (review M6: not the deriver's own last present scene, so after a v1 cascade the comparison is slightly off; 1 unmatched scene per seed lands in `asked/other`).

### Results 1: base variant (as generated)

The LLM is never asked (0 ambiguous transitions), so the four non-truth arms produce the same flags (`rules` has 2 `story_inferred` scenes, the two flashbacks without a day; `rules+bible` none).

| Metric | base-rules | base-rules+llm | base-rules+llm-v2 | base-rules+bible |
|---|---|---|---|---|
| overall / each of the 4 checks P / R / F1 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| story/tau (3 seeds) | 0.9998 | 0.9998 | 0.9998 | 1.0000 |
| story/ambiguous, llm_calls | 0, 0 | 0, 0 | 0, 0 | 0, 0 |

### Results 2: ambiguous variant (3 seeds, mean ± sample std; a cell with no spread has none)

From `nip eval compare --exp EXP-007 --md --subset all`, rows trimmed as in the notes:

| Metric | ambiguous-rules | ambiguous-rules+llm (v1) | ambiguous-rules+llm-v2 | ambiguous-rules+bible | ambiguous-truth |
|---|---|---|---|---|---|
| Seeds (n) | 3 | 3 | 3 | 3 | 3 |
| overall P / R / F1 | 0.69 / 0.75 / 0.72 | 0.79 ± 0.21 / 0.64 ± 0.10 / 0.70 ± 0.14 | 0.94 ± 0.10 / 0.81 ± 0.05 / 0.87 ± 0.04 | 1.00 / 0.75 / 0.86 | 1.00 / 1.00 / 1.00 |
| plot.dead_acts P / R / F1 | 0.43 / 1.00 / 0.60 | 0.83 ± 0.29 / 0.56 ± 0.38 / 0.63 ± 0.32 | 0.87 ± 0.23 / 1.00 / 0.92 ± 0.14 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| plot.knowledge_order P / R / F1 | 1.00 / 1.00 / 1.00 | 0.83 ± 0.29 / 1.00 / 0.89 ± 0.19 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| plot.prop_provenance P / R / F1 | 1.00 / 1.00 / 1.00 | 0.76 ± 0.21 / 0.89 ± 0.19 / 0.81 ± 0.17 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| plot.two_places P / R / F1 | 0.00 / 0.00 / 0.00 | 0.33 ± 0.58 / 0.11 ± 0.19 / 0.17 ± 0.29 | 0.67 ± 0.58 / 0.22 ± 0.19 / 0.33 ± 0.29 | 0.00 / 0.00 / 0.00 | 1.00 / 1.00 / 1.00 |
| story/tau | 0.87 ± 0.01 | 0.89 ± 0.03 | 0.98 ± 0.03 | 1.00 | 1.00 |
| story/day_acc_present | 0.10 ± 0.11 | 0.20 ± 0.05 | 0.32 ± 0.23 | 0.11 ± 0.11 | 1.00 |
| story/flashback_recall | 0.00 | 0.96 ± 0.07 | 0.88 ± 0.22 | 1.00 | 1.00 |
| story/flashback_precision | 0.00 | 0.23 ± 0.13 | 1.00 | 1.00 | 1.00 |
| story/simultaneous_recall | 0.00 | 0.06 ± 0.10 | 0.44 ± 0.19 | 0.00 | 1.00 |
| story/ambiguous (transitions the rules could not settle) | 25.0 ± 1.7 | 52.7 ± 14.6 | 26.0 ± 2.0 | 18.3 ± 0.6 | 0 |
| story/llm_calls | 0 | 52.7 ± 14.6 | 26.0 ± 2.0 | 0 | 0 |
| story/verdict_acc | n/a | 0.29 ± 0.16 | 0.82 ± 0.07 | n/a | n/a |

### Results 3: pooled counts over the 3 seeds (12 planted flags per seed; tau is the mean)

| variant | dead_acts TP/FP | knowledge_order TP/FP | pooled precision (both) | two_places found of 9 | tau |
|---|---|---|---|---|---|
| ambiguous-rules | 9/12 | 9/0 | 18/30 = 0.60 | 0 | 0.870 |
| ambiguous-rules+llm (v1) | 5/1 | 9/3 | 14/18 = 0.78 | 1 | 0.892 |
| ambiguous-rules+llm-v2 | 9/2 | 9/0 | 18/20 = 0.90 | 2 | 0.983 |
| ambiguous-rules+bible | 9/0 | 9/0 | 18/18 = 1.00 | 0 | 1.000 |
| ambiguous-truth | 9/0 | 9/0 | 18/18 = 1.00 | 9 | 1.000 |
| base-rules (= +llm = +llm-v2) | 9/0 | 9/0 | 18/18 = 1.00 | 9 | 0.9998 |

The reviewer recomputed these from the 30 active runs: pooled TP/FP rules 18/12, v1 14/4, v2 18/2, bible 18/0, truth 18/0; tau means 0.870 / 0.892 / 0.983; rules-only tau per seed 0.877 / 0.871 / 0.863.

**Per seed, v2 on the ambiguous show:** dead_acts P/R 1.00/1.00 (seed 1), 0.60/1.00 (seed 2: 3 of 8 flashbacks missed, among them the silent ones), 1.00/1.00 (seed 3); flashback recall 1.00 / 0.62 / 1.00 (review: 0.625), precision 1.00 on all; simultaneous recall 0.67 / 0.33 / 0.33 (6 scenes each, 2 silent on seeds 2 and 3); two_places found 1 / 1 / 0 of 3 planted; verdict accuracy 25/28, 19/24, 20/26 = 0.893 / 0.792 / 0.769; `day_acc_present` 0.48 / 0.06 / 0.42 (rules 0.03-0.23, review M2).

**Seeds 2 + 3 only** (review, derived from the same runs): rules 12/20 = 0.60, v2 12/14 = 0.857 (+25.7 points); seed 2 alone 0.60 → 0.75 (+15), seed 3 0.60 → 1.00 (+40); tau 0.867 → 0.976. These are not held out in any strong sense (see Prompt v2 below).

### Prompt v1: why it failed

Over the 158 v1 verdicts: 22 of 22 unmarked flashbacks right, but 84 present scenes called `earlier` (32 + 18 `loose_next_day`, 34 follow-ups) and 1 of the 16 asked simultaneous scenes right (13 `earlier`, 2 `next_day`); reasons confabulated, `days` 1; verdict accuracy 0.29 (per seed 0.47 / 0.20 / 0.19). Each wrong `earlier` leaves the day counter in place, so the next scene of the same morning is asked again: 36 / 59 / 63 asks per show against the rules' 26 / 23 / 26. Each false flashback also hides real violations: planted `dead_acts` recall falls to 0.56 (0.33 on two seeds), and `knowledge_order` and `prop_provenance` gain false positives (precision 0.83 and 0.76, mean of seeds).

### Prompt v2: what changed, and how independent its test is

v2 (`config/prompts/knowledge.story.v2.md`, [B-194](decisions.md#b-194--prompt-v2-a-regressing-time-of-day-is-normally-the-next-day)) says a regressing time of day is normally the next day; `earlier`, `simultaneous`, `later_days` only when the second scene's own text says so; checked in that order; default `next_day`. Its wrong verdicts (14 over three seeds): 8 `same_day` truths answered `next_day` (no order effect) and 6 `simultaneous` truths answered `next_day` (5) or `same_day` (1), lost for `two_places`.

Independence, after the review (I1): one v2 version only, no iteration after seeing its results; but v2's file was written about 4 minutes after v1's verdicts existed for all three seeds and the failure analysis it answers is aggregated over them, so "written from seed-1 verdicts" cannot be verified; its example cues ("eight years ago", "at the same moment", "meanwhile") are the generator's templates, identical across seeds; and the regex cue reader already reaches tau 1.0 on seed 1. Seeds 2-3 therefore test sampling variability, not wording, and the LLM was not compared with a regex.

### Cost

| | Session 1 (v1) | Session 2 (v2) |
|---|---|---|
| Model load | 469.9 s (`up` 8 m 35 s wall) | 384.2 s |
| VRAM idle / model up, MiB | 1102 / 7371 | 812 / 7558 |
| LLM calls (3 ambiguous shows) | 158 | 78 |
| Median s per call | 2.45 | 7.15 |
| Summed call time | 385 s (6 m 29 s wall) | 548 s |
| Window | not timestamped | 2026-10-17 01:03:41 → 01:29:59 (after about 2 h waiting for the lock) |

v2's replies were shorter (72 vs 110 characters of `reason`) and its prompt 15% longer (1955 vs 1696 characters); the 3x per-call difference with the same model and arguments has no identified cause (session 2's ray-head had been started by 2.1B two hours earlier; GPU clocks and desktop load not recorded). Read the cost as 2.4 to 7 s per ambiguous transition, 24-28 calls per 150-scene show with v2. `story.derive` on the rules arms: 2-17 ms per show; scoring about 17 s per (variant, seed, arm).

### Takeaway

- On the **base show** the LLM step does nothing: 0 ambiguous transitions, 0 calls, precision, recall and tau equal rules only (tau 0.9998; the only miss is the order of the two flashbacks, which the bible fixes). Precision change 0.0 points, cost 0.
- On the **ambiguous show**, prompt v1 makes the story step a source of false flashbacks (verdict accuracy 0.29, planted dead_acts recall 0.56, two more checks gain false positives). With v2 (same model, only the prompt changed) pooled precision of `plot.knowledge_order` + `plot.dead_acts` rises 0.60 → 0.90, tau 0.870 → 0.983, all 18 planted flags of those two checks still found, two_places 0 → 2 of 9.
- Bible overrides for the flashbacks give precision 1.00 with no call, but no intercut marker (two_places 0 of 9) and no help with `later_unstated` day counts; the LLM step is the fallback for what the bible does not carry.
- Neither arm reaches `silent` cases or the day count after a LATER with no number: `day_acc_present` is 0.10 (rules) / 0.32 (v2) because one missed day shifts every later day. Tau and the four rules are blind to that; anything downstream that reads `story_day` is not covered.
- **Limits:** the +26 to +30 points are a ceiling for explicit, templated cues on this generator; generalisation to real scripts is untested; 3 seeds with 8 flashbacks and 6 simultaneous scenes each; one 4B model; Beverly Hillbillies not available (R3). The bar's verdict for v1 (+18, numerically above +3) was overridden by a recall criterion that is not in the written bar, and that is disclosed.

### Decision

Keep the LLM step with **prompt v2**, not v1; prefer bible overrides where the bible has them ([B-196](decisions.md#b-196--exp-007-decision-keep-the-llm-step-with-prompt-v2-bible-overrides-first)). **Controller ruling:** `story.PROMPT` names `knowledge.story.v2.md` ([B-195](decisions.md#b-195--storyprompt-is-v2)); cost if wrong, as ruled: v2 overfit to templated ambiguity.

### What changed in the code because of it

| | Before EXP-007 | After |
|---|---|---|
| `story.PROMPT` | `knowledge.story.v1.md` | `knowledge.story.v2.md` (`6dc6ba8`) |
| Synthetic generator | `build(seed)` only | `build(seed, ambiguous=True)` adds the variant; default output unchanged (`11354bc`) |
| Experiment teardown | `down` re-planned and deleted nothing with the model loaded | deletes every app in `serve.status()` and waits for idle (`23f13d4`, [C-28](#c-28--experiment-teardown-delete-by-re-planning-vs-delete-by-serve-status)) |
| MLflow params | prompt version only in the arm name | `story_prompt=knowledge.story.<v>` logged for llm arms (`6dc6ba8`; earlier runs lack it) |

### Review that shaped it

`2.2B-review.md`: spec ✅, 1 Important (I1, "held out" overstated) and 6 Minor; every number reproduced from MLflow. The fix round rewrote the Takeaway and Decision to the ceiling reading above; the controller's ruling text still says "held-out seeds" ([review-findings](review-findings.md#22b-exp-007-ambiguous-transitions-variant-and-harness)).

### Open items

- Real-content check (multi-episode real scripts) deferred with R3.
- A regex cue-reader arm was never run as an EXP-007 arm, so whether the LLM beats a regex is unmeasured.
- Silent cases are never asked (P4); cascade guard (P3) and the `Verdict.days` cap (P5) not changed ([B-198](decisions.md#b-198--three-story-step-improvements-proposed-and-left-undone)).
- `later_unstated` has no prose cue; `day_acc_present` is low in every arm.
- The 3x per-call latency difference between sessions is unexplained.
- `ambiguate` sample sizes hold for seeds 1-3 only (review M4).
- Past MLflow runs lack the `story_prompt` param.

## EXP-008 · Keyframe density for on-screen text

| | |
|--|--|
| **Question** | How many keyframes per shot does the clearance scanner need to catch on-screen text? (from docs/experiments.md) |
| **Variants** | `1-per-shot` (middle frame) · `1-per-shot+2s` (+ one per 2 s in shots > 4 s: the current B-027 policy) · `1-per-shot+1s` (+ one per 1 s in shots > 1 s). Nested frame sets, each frame read once. Added by the experimenter: `+native` (the same flags scored with the agent-provisional native URL labels) and `@all-positives` (scored against every rendered positive, cleared items included) |
| **Metrics** | Recall of `clr.phone`, `clr.url`, `clr.email`, `clr.address`, `clr.plate`, `clr.brand_text` · keyframes per minute. Also logged: precision, shown FP per content hour, read seconds per content hour |
| **Success bar (as written)** | A denser policy is kept only if recall rises >= 5 points for <= 50 % more keyframes |
| **Status** | **Done** (2026-10-17), laptop, 3 seeds, both films. Final scoring after fix round 2 (`cda802e`): MLflow experiment `EXP-008` (27 runs in fix round 1, re-scored again in fix round 2 after 57 older runs were soft-deleted) |
| **Result in one line** | Shown recall 0.50 / 1.00 / 1.00 at 11.17 / 26.74 / 53.93 keyframes per minute. By the bar's text the policy is 1 per shot (its recall gain from 1 per shot to the current policy costs +139 % keyframes), but 0.50 fails the 0.85 MVP recall target, so the **controller ruled to keep 4 s / 2 s as an override of the bar** ([B-251](decisions.md#b-251--exp-008-keep-the-4-s--2-s-keyframe-policy-as-a-recorded-override-of-the-bar)) |
| **Source** | `notes/2.7.md` (EXP-008 Results, DP-2.7-9, Fix rounds 1 and 2), `reports/2.7-report.md`, `reports/2.7-review.md` (answer 1), `reports/2.7-rereview.md`; tables `data/exp008/compare-exp008.md` (round 0), `compare-exp008-r2.md` (final); code `eval/exp/exp008_keyframes.py`; commits `4c131c1`, `2407222`, `e464917`, `f324627`, `cda802e` |

### Setup and method

- **Set:** the two films' `clr.text.v1` injections from 2.9A (`nip eval inject --set mvp --seed N --only clr --out data/inject-clr`), seeds 1, 2, 3. Labelled pending/denied items 10 / 11 / 11 = **32 labels**; 48 rendered positives including the cleared ones. Negatives: 555-0100..0199 numbers, RFC 2606 domains, bible-fictional brands. Overlays are 72 to 96 frames (3 to 4 s) in low-motion stretches, which in these films are long shots (3.5 to 34 s).
- **Pipeline:** only the frame set differs; everything after the read is production code (`stage.scan_image`, the six `ClearanceText` checks, `verify`), scored by `nip eval run`, tables from `nip eval compare --exp EXP-008 --md --tracking-uri sqlite:///data/mlflow/mlflow.db`.
- **Reader:** RapidOCR (PP-OCRv6 medium) **on the CPU** under heavy machine load, because 2.1B / 2.2B held `data/gpu.lock` from 22:42 to 06:12 ([journal](journal.md#2026-10-17--27-running-the-experiments-with-the-gpu-held-by-other-agents)); 4,374 frames in about 3.5 h. Final candidates were recomputed from the cached CPU reads by the final scanner (`rescan`, tags `cpu4`, then `cpu5`). NER: `gliner-x-base` (pinned per run).
- **Precision basis:** "shown" flags; precision counts every unlabelled shown flag as an FP, so it is precision against injected labels only (controller ruling, [B-254](decisions.md#b-254--credits-urls-are-correct-unknown-flags-precision-is-reported-against-injected-labels-only-junk-is-dropped-by-rule)), not the spec's clean-run noise metric.

### Results

Final rows (after fix round 2), copied from `data/exp008/compare-exp008-r2.md`, mean ± sample SD over 3 seeds:

| Metric | 1-per-shot | 1-per-shot+2s (current) | 1-per-shot+1s |
|---|---|---|---|
| overall P / R / F1, injected labels only | 0.40 ± 0.05 / 0.50 ± 0.12 / 0.44 ± 0.08 | 0.21 ± 0.01 / 1.00 ± 0.00 / 0.34 ± 0.01 | 0.20 ± 0.01 / 1.00 ± 0.00 / 0.33 ± 0.01 |
| overall P / R / F1, `+native` | 0.40 ± 0.05 / 0.50 ± 0.12 / 0.44 ± 0.08 | 0.44 ± 0.01 / 1.00 ± 0.00 / 0.61 ± 0.01 | 0.42 ± 0.01 / 1.00 ± 0.00 / 0.59 ± 0.01 |
| clr.address R | 0.00 ± 0.00 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| clr.brand_text R | 0.89 ± 0.19 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| clr.email R | 0.44 ± 0.51 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| clr.phone R | 0.50 ± 0.71 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| clr.plate R | 0.56 ± 0.51 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| clr.url R | 0.67 ± 0.33 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| detection recall incl. cleared (`all/recall/all`) | 0.50 ± 0.12 | 1.00 ± 0.00 | 1.00 ± 0.00 |
| keyframes (both films, one seed) | 302 | 723 | 1,458 |
| keyframes per minute | 11.17 | 26.74 | 53.93 |
| shown FP per content hour (injected runs) | 17.75 | 90.99 (64.36 `+native`) | 95.43 (68.80 `+native`) |
| read s per content hour (CPU wall under load, see caveats) | 837.71 ± 66.63 | 3,558.80 ± 433.01 | 7,185.80 ± 907.85 |

- Per-check recall rests on 1 to 3 labels per check and seed; read the overall row (the per-check SDs are what one label moving does).
- `@all-positives` shown recall is 0.67 ± 0.04 for the current policy: the 16 cleared items are rendered and detected but `suppressed` by design (derived: 32 of 48).
- **Round 0** (before the review; `data/exp008/compare-exp008.md`): recall identical (0.50 ± 0.12 / 1.00 / 1.00); precision 0.35 ± 0.05 / 0.17 ± 0.01 / 0.17 ± 0.01; current policy 113.18 shown FP per content hour.
- **Bar arithmetic** (derived from the keyframe row): current vs 1 per shot +0.50 recall for +139 % keyframes (723 / 302); dense vs current +0.00 for +101.7 % (1,458 / 723).

### Takeaway

A policy must put a keyframe inside a 3 to 4 s overlay. 1 per shot does that for 50 % of the labelled items; one every 2 s in long shots catches all 32 labels and all 48 rendered positives; one every 1 s adds nothing for twice the frames.

### Decision

- **How the bar was read, twice.** The first round compared denser arms against the current policy (reading A): dense +0.00 for +101.7 % → rejected, 4 s / 2 s "kept per the bar". The reviewer: the bar names no incumbent and lists variants sparse → dense; "kept" applies to the existing denser policy having to justify itself, so the text supports reading B (against 1 per shot): +0.50 for +139 % fails the cost clause, and the literal outcome is **1 per shot**. Reading A came from the brief calling the middle arm "current", not from the doc.
- **Controller ruling:** keep 4 s / 2 s as a recorded override of the bar, because 1 per shot's recall (0.50) fails evaluation.md's 0.85 MVP recall target for the six `clr.*` checks; cost if wrong: +139 % keyframes ([B-251](decisions.md#b-251--exp-008-keep-the-4-s--2-s-keyframe-policy-as-a-recorded-override-of-the-bar)). `config/pipeline.yaml` says "OVERRIDDEN here (controller ruling)". Cost noted by the agent: +700 % OCR time on the policy frames (1,470 vs 180 s per content hour on the GPU scans).

### Caveats (measured or stated)

- **The set favours density.** 2.9A's overlays last 3 to 4 s inside long shots; a real storefront sign usually stays for the whole shot, where the middle frame would catch it. The result does not transfer to persistent signage.
- **Read seconds are CPU wall time under load**, logged under the `GPU-s per content-hour` column of `nip eval compare`; they scale with keyframes (the point) but are not a measurement of the shipped GPU path. The seed-1 GPU scan ran at 1.12 / 1.06 kf/s on the 723 policy frames (2.6 measured 1.29 kf/s on 398 Sintel frames).
- **Precision is not independent of the data:** the scanner rules (person filter, credits-card rule, brand length, credit vocabulary) were written while looking at seed-1 flags, and the films' credits are identical in every seed. Precision on seeds 2 to 3 alone in fix round 1 was 0.21 ± 0.00 (seed 1 gives the same).
- **Native labels are agent-provisional**, URLs only, `reviewed` false, with frames copied from seed 1's own occurrences.

### Open items / later

- A set with persistent signage (and in-scene text-heavy frames, to measure the dense-card rule's recall cost) to revisit the override.
- Clean-run triage by a person and reviewed `*.native.jsonl` labels, to measure the spec's noise metric (<= 10 shown FP per content hour on clean runs).
- **NER variant A/B on this set (Phase 2 closeout, 2026-10-18):** all published EXP-008 / EXP-017 / e2e numbers above were produced with `gliner-x-base`; the closeout re-ran the e2e scoring with replayed OCR and `gliner-x-large` (now the laptop default): recall 1.00 for both (= base), shown FP per content hour 90.99 → 86.55, 18 MLflow runs; large kept as the default. See [C-54](experiments.md#c-54--ner-ab-on-replayed-ocr-gliner-x-large-vs-gliner-x-base-on-the-exp-008-end-to-end-benchmark).

## EXP-017 · OCR engine vs reading text with the vision model

| | |
|--|--|
| **Question** | Is a dedicated OCR model worth running when the vision model can read text too? (from docs/experiments.md) |
| **Variants** | `pp-ocrv6-medium` (RapidOCR PP-OCRv6 medium, 2.6's fallback for PaddleOCR; detection on GPU, recognition on CPU) · `qwen3.5-4b-awq` reading each keyframe (vLLM in ray-head via `serving.group`; structured output `{"lines": [{"text", "box" 0-1000 grid}]}`, T=0, thinking off, `max_tokens` 600, 8 requests at once, constant line confidence 0.9) |
| **Metrics** | Recall of the six on-screen text checks · GPU-seconds per content hour (see caveats: logged as stage wall seconds). Also: precision, shown FP per content hour |
| **Success bar (as written)** | Keep PP-OCR unless the vision model's recall is >= 10 points higher |
| **Status** | **Done** (2026-10-17), laptop, 3 seeds, both films; R7 gate met (EXP-001 10/10 starts, W-serve real runs). MLflow experiment `EXP-017` (18 runs in fix round 1, re-scored in fix round 2) |
| **Result in one line** | Recall 1.00 for both; **keep PP-OCR** ([B-252](decisions.md#b-252--exp-017-keep-the-dedicated-ocr-engine-pp-ocrv6-medium-via-rapidocr)). The vision model costs 1.30x the stage seconds plus a 156.6 s load to 7.9 GB, and its lower false-positive count comes from 349 of 2,169 reads (16.1 %) failing on dense credits cards |
| **Source** | `notes/2.7.md` (EXP-017 Results, Fix rounds 1 and 2), `reports/2.7-report.md`, `reports/2.7-review.md` (M2); tables `data/exp017/compare-exp017.md` (round 0), `compare-exp017-r2.md` (final); code `eval/exp/exp017_vlm.py`, `exp017_serve.py`, `exp017_session.py`; commit `e778928` |

### Setup and method

- Same frames as EXP-008's current policy (723 keyframes per seed for both films), same `TextScanner`, matching, checks and scoring. NER `gliner-x-base`.
- **Serving** (one session under `data/gpu.lock`, 06:14 to 07:10, `NIP_VRAM_MARGIN_GB=0.25`): load **156.6 s** (VRAM 938 → **7,904 MiB**), unload **16.1 s** (back to 801 MiB). Reads: 398 / 325 frames of Sintel / Tears of Steel per seed in 409 to 442 s at concurrency 8.
- **OCR arm timing:** the seed-1 GPU scan (`data/exp008/scans/gpu-*-s1.pkl`, 1.12 / 1.06 kf/s on the 723 frames), copied to all seeds (one measurement, so its SD is 0 by construction), GLiNER included. The vision-model arm's seconds are the wall time of the read phase at 8 requests at once, GLiNER excluded (run on the CPU in scoring). After review M2 the runs carry a `seconds_are` tag and the figure is called stage wall seconds, not GPU-seconds.

### Results

Final rows (after fix round 2), `data/exp017/compare-exp017-r2.md`, mean ± SD over 3 seeds, shown flags:

| Metric | qwen3.5-4b-awq | pp-ocrv6-medium |
|---|---|---|
| overall P / R / F1, injected labels only | 0.32 ± 0.01 / 1.00 ± 0.00 / 0.48 ± 0.01 | 0.21 ± 0.01 / 1.00 ± 0.00 / 0.34 ± 0.01 |
| overall P / R / F1, `+native` | 0.35 ± 0.01 / 1.00 ± 0.00 / 0.52 ± 0.01 | 0.44 ± 0.01 / 1.00 ± 0.00 / 0.61 ± 0.01 |
| per-check R (address, brand_text, email, phone, plate, url) | all 1.00 ± 0.00 | all 1.00 ± 0.00 |
| detection recall incl. cleared (`all/recall/all`) | 1.00 ± 0.00 | 1.00 ± 0.00 |
| shown FP per content hour (injected runs) | 50.30 ± 1.28 | 90.99 ± 0.00 |
| stage seconds per content hour (logged as GPU-s) | 1,906.62 ± 15.73 | 1,470.49 ± 0.00 |
| native URLs found (of 12) | 1 | 12 |

- On the overlay frames the vision model read the exact injected text on 106 of 107 keyframes (1 failed read), PP-OCR on 107 of 107.
- **Failed reads:** 349 of 2,169 vision-model reads (16.1 %) hit `max_tokens` (600) on dense credits cards: 54, 61, 56, 61, 56, 61 per film-seed, deterministic at T=0. Those frames gave no lines, so no candidates: that, not better reading, is why the vision model shows fewer FPs (22.7 vs 51.0 shown per seed in round 0) and finds 1 of the 12 credits URLs.
- **Round 0:** P 0.32 ± 0.01 vs 0.17 ± 0.01, R 1.00 / 1.00, shown FP per content hour 50.30 ± 1.28 vs 113.18 ± 0.00. **Fix round 1** (13 natives): with natives 0.38 vs 0.46, the vision model found 2 of 13 native URLs.

### Takeaway and decision

Recall is identical, so by the bar PP-OCR stays. The cost side also favours it: 1.30x stage seconds for the vision model (at 8 requests at once against one at a time), plus a 156.6 s load that displaces everything else on the 8 GB card (7.9 GB used), where the OCR actor needs 1.5 GiB. **Decision: keep `pp-ocrv6-medium` (RapidOCR)** ([B-252](decisions.md#b-252--exp-017-keep-the-dedicated-ocr-engine-pp-ocrv6-medium-via-rapidocr)).

### Caveats

- One prompt, not tuned; a larger `max_tokens` would change the failed-read count and the FP comparison.
- The vision model's line confidence is a constant 0.9 (an assumption that only moves unlogged items between tiers).
- The two arms' seconds are not like for like (GLiNER in one, concurrency 8 in the other); the decision rests on recall, so it is unaffected.
- NER was `gliner-x-base` (see EXP-008 Open items).

## EXP-018 · KV-cache precision on the laptop

| | |
|--|--|
| **Question** | Can an FP8 KV cache let the laptop run 16k context without hurting extraction? (from docs/experiments.md) |
| **Variants** | default KV at 8k · FP8 KV at 8k · FP8 KV at 16k (the brief's three) plus **FP8 KV at 32k**, added because the shipped planner already runs the default cache at 16k, so "context doubles" means 32k |
| **Metrics** | Largest context that starts reliably (10 starts per arm, as EXP-001) · fact precision and recall |
| **Success bar (as written)** | Adopt FP8 if F1 drops by ≤ 0.01 and context doubles |
| **Status** | **Done for starts** (all arms 10/10); **inconclusive for F1** (one pass per arm). FP8 not adopted |
| **Result in one line** | Every arm started 10/10 and returned to idle 10/10, FP8 at 32k included; FP8 holds 1.60x the KV tokens at 8k but runs 21 % slower (133.8 vs 169.7 tok/s); ΔF1 −0.010 (fp8-8k) and −0.023 (fp8-16k) from single passes whose own noise is at the bar's width |
| **Source** | `notes/2.1B.md` (EXP-018, decision restated), `reports/2.1B-report.md`, `reports/2.1B-review.md` (M4), `reports/2.1B-rereview.md` (m3); code `eval/exp/exp018_kv.py`; commits `b8d320b`, `bbf653a`, `dc4e6fc`, `bb68eac`, `22074b9` |

### Setup

- **Arms:** the shipped Plan with `NIP_VRAM_MARGIN_GB=0.25` (W-serve's knob), context and `--kv-cache-dtype` overridden; KV budget = the planner's exact `--kv-cache-memory-bytes`, about 2.7 to 2.9 GB. Every `up` here reported `planned_context: 16384`.
- **Starts:** 10 rounds of one trial per arm, interleaved (`eval.exp.exp018_kv drive`); each trial = deploy → 8 × 128-token unconstrained bench → teardown with VRAM back to idle. Round 1 2026-10-17 02:39–02:58; rounds 2–10 09:12–10:51, the lock released after every round with a 150 s gap; the driver waited 5 times while the desktop held more than 1,500 MiB. Round 2's first attempt recorded nothing (the desktop held 2,838 to 3,069 MiB and the planner refused every arm), which is why the driver waits.
- **Facts:** one extraction pass per arm, enum, synthetic seed-1 clean, 150 scenes, 0 failed; 4 calls in flight.
- **Hardware:** RTX 4060 Laptop 8 GB, qwen3.5-4b-awq, vLLM 0.30 in ray-head, xgrammar `disable_any_whitespace`.

### Results 1: starts (10 trials per arm)

Table from `nip eval compare --exp EXP-018 --md` (`data/exp2.1b/exp018.md`), mean ± sd:

| Metric | default-8k | fp8-8k | fp8-16k | fp8-32k |
|---|---|---|---|---|
| Successful starts | **10/10** | **10/10** | **10/10** | **10/10** |
| Back to idle after teardown | 10/10 | 10/10 | 10/10 | 10/10 |
| KV cache, tokens | 60,509 ± 2,187 | 96,548 ± 0 | 122,135 ± 2,355 | 142,282 ± 0 |
| KV cache bytes | 2.82e9 ± 1.0e8 | 2.87e9 ± 0 | 2.85e9 ± 5.8e7 | 2.87e9 ± 0 |
| Max concurrency at the arm's context (vLLM) | 7.39 | 11.79 | 7.46 | 4.34 |
| Peak device used, MiB | 7,820 ± 40 | 7,677 ± 72 | 7,692 ± 149 | 7,684 ± 165 |
| Load s | 164 ± 122 | 118 ± 38 | 120 ± 28 | 118 ± 29 |
| Tokens/s (8 prompts × 128, unconstrained) | **169.7 ± 19.8** | 133.8 ± 12.5 | 130.8 ± 14.1 | 135.7 ± 9.2 |
| MLflow runs | 10 (866c86a9…) | 10 (308b1876…) | 10 | 10 |

Highest single peak: 8,150 MiB of 8,188 (fp8-32k, round 1). Load times include the first load of a fresh container (498 s); warm loads are 96 to 207 s. The reviewer confirmed 40 runs, all `started=1` and `returned_to_idle=1`, and recomputed the tok/s means (169.7 / 133.8).

### Results 2: facts (one pass per arm)

Table from `nip eval compare --exp EXP-018-facts --md` (`data/exp2.1b/exp018-facts.md`):

| Arm | Precision | Recall | F1 | ΔF1 vs default | knowledge_order FPs (clean) | MLflow |
|---|---|---|---|---|---|---|
| default-8k | 0.7534 | 0.7699 | 0.7615 | — | 16 | f319f445… |
| fp8-8k | 0.7294 | 0.7753 | 0.7517 | −0.0098 | 17 | b4ab7a9d… |
| fp8-16k | 0.7165 | 0.7616 | 0.7384 | −0.0231 | 18 | 83f2cf90… |

fp8-32k has no fact pass. These passes predate 2.1B's fix round 1 (render fix), so their absolute F1 is not comparable with later EXP-020 numbers.

### What was found

1. **FP8 doubles the reachable context on the laptop.** In the same bytes FP8 holds 96.5k vs 60.5k tokens at 8k (1.60x, not 2x; the notes attribute the rest to the model's linear-attention state, an explanation, not measured) and starts at 32k 10/10, double the planner's 16k.
2. **It costs throughput:** 133.8 vs 169.7 tok/s unconstrained (−21 %).
3. **The F1 cost cannot be resolved with one pass per arm.** fp8-8k and fp8-16k differ only in max-model-len, which does not change a ~1.5k-token scene prompt, yet their F1 differs by 0.013 (batch-order nondeterminism at temperature 0 with 4 calls in flight, as W-serve saw with scene 25).

### Takeaway

The context half of the bar is met (32k starts 10/10), but per-scene extraction does not need the context, and the speed cost is real. With n = 1 per arm the F1 half is neither met nor failed.

### Decision

Do not adopt FP8 now ([B-179](decisions.md#b-179--exp-018-do-not-adopt-the-fp8-kv-cache)); `serving.vllm_args`, the planner's KV term and the catalog are unchanged. Revisit when EXP-005's 32k arm needs 32k on the laptop, with 3 seeds per arm.

### What changed in the code because of it

No serving or planner change. The harness gained the lock hygiene in [B-174](decisions.md#b-174--all-gpu-work-in-the-exp-harnesses-goes-through-gpu_session-which-releases-only-a-lock-it-owns) because of this experiment's driver crash.

### Review that shaped it

The first notes said the 16k arm "misses the bar (−0.023)". The 2.1B review (M4) said the bar was applied to differences at the width of the measured noise, that fp8-32k (the arm that actually doubles 16k) had no F1, and that the 16k baseline rests on planner output, not start trials (`default-16k` is in `ARMS` but was never run); "don't adopt" is still justified by −21 % tok/s and no context need. The notes were restated. The re-review (m3) then found the restatement still wrong in wording: −0.023 is not "within the 0.013 single-pass noise" (it is 1.8x it, the reviewer's arithmetic), the defensible claim is "unresolved at n = 1", and one line still ended "Status done (bar not met at 16k…)". That m3 wording was not corrected in the notes afterwards; this entry uses the reviewer's reading.

### Open items

- F1 with 3 seeds per arm, including fp8-32k.
- `default-16k` start trials (the baseline the notes rely on).
- Throughput under real load: the pass wall times (627 to 2,348 s for the same 150 calls) are unusable because other agents loaded the CPU.

## EXP-020 · Entity resolution: enum-constrained IDs vs fuzzy matching afterwards

| | |
|--|--|
| **Question** | Is it better to let the model pick registry IDs during extraction (D-025) or to resolve free-text names afterwards? (from docs/experiments.md) |
| **Variants** | `enum`: registry keys as an enum plus `UNKNOWN` in the schema · `free-text`: names as strings, resolved afterwards with the shipped `Resolver` (rapidfuzz). Same prompt except the ids rule; same model, scenes, temperature 0 and scorer. Added in 2.1B: `enum + secret-in-scene` (not shipped) and fix-round variants (`−presence`, `+holds`, r2) |
| **Metrics** | Resolution accuracy against generator mention truth · fact precision/recall · precision (and recall) of the Layer 1 `plot.*` rules on injected shows and their clean twins |
| **Success bar (as written)** | Keep the enum if its accuracy is at least as high and rule precision doesn't drop |
| **Status** | **Inconclusive; D-025 stands by default** (2026-10-18, after review I3). First wave 2026-10-16 (2.1), rule half 2026-10-17, re-measured after two fix rounds 2026-10-18 (2.1B) |
| **Result in one line** | Resolution accuracy 0.95 vs 0.97 in the first wave (within noise); with the argument checks 1.00 vs 0.96, partly by construction. Plot rules on extracted facts: 1/36 vs 0/36 planted violations at first, 10/36 (enum) vs 17/36 (free text) after the fixes, at 12.7 vs 64.3 false positives per clean show. The arms trade failure modes; neither answers the resolution question, and 0 alias-only arguments exist in the set |
| **Source** | `notes/2.1.md` (EXP-020), `notes/2.1B.md` (EXP-020, fix rounds 1–2), `reports/2.1-review.md`, `2.1-rereview.md`, `reports/2.1B-review.md`, `2.1B-rereview.md`, `2.1B-rereview2.md`; code `eval/exp/exp020_resolution.py`, `eval/exp/exp020_rules.py`; commits `38fa323`, `6b2ddf4`, `608c5a1`, `b8d320b`, `bbf653a`, `22074b9`, `8a5d5bd`, `11d03c4`, `962512f` |

### Setup

- **First wave (2.1):** the synthetic show (seed 1, 150 scenes), both arms through the shipped path (deploy in ray-head, host-side extraction), scored over events with a grounded quote (≥ 90). Truth: generator facts and mentions. qwen3.5-4b-awq at the planner's 16k, sequential calls.
- **Rule half (2.1B):** 2.9A plot-L1 injected shows, seeds 1–3, 12 planted labels each (3 per check: knowledge_order, dead_acts, two_places, prop_provenance; 36 in all, 9 per check), and their clean twins (every flag on a clean twin is a false positive). Real extraction with the shipped schema (default KV, 8k), `save_events` with all checks, shipped consolidation, **truth story order** (as 2.3's oracle benchmark), the four 2.3 rules with verification (`eval.exp.exp020_rules`). 4 calls in flight; a throwaway DB per show; replies cached by call key. Tables from `nip eval compare --exp EXP-020-rules --md --subset all` (injected), `--exp EXP-020-rules-clean`, `--exp EXP-020-facts`. Oracle facts on the same shows (2.3): P = R = 1.00, 0 flags on the clean shows.
- **Fairness (2.1 review):** only `IDS_RULE` and the subject/object type differ between arms; no free-text candidate is credited as a registry entity (0 of 271 grounded free-text candidate arguments map to a registry truth id).

### Results 1: resolution (2.1, first wave)

Table from `nip eval compare --exp EXP-020 --md`, as re-scored in 2.1's fix round 1 (`extract --replay` with the whole-word scorer and the two-word quote rule; no new model calls):

| Metric | enum | free-text |
|---|---|---|
| Seeds (n) | 1 | 1 |
| acc_alias | 0.00 | 0.00 |
| acc_implicit | 0.70 | 1.00 |
| acc_name | 0.96 | 0.97 |
| events_grounded | 542.00 | 629.00 |
| events_raw | 564.00 | 653.00 |
| fact_precision | 0.59 | 0.60 |
| fact_recall | 0.70 | 0.86 |
| failed_scenes | 8.00 | 7.00 |
| mention_recall_description | 0.29 | 0.43 |
| mention_recall_name | 0.74 | 0.77 |
| mention_recall_nickname | 0.00 | 1.00 |
| n_args | 553.00 | 654.00 |
| n_args_alias | 0.00 | 0.00 |
| n_args_implicit | 10.00 | 8.00 |
| n_args_name | 542.00 | 646.00 |
| n_mentions_description | 7.00 | 7.00 |
| n_mentions_name | 597.00 | 619.00 |
| n_mentions_nickname | 1.00 | 1.00 |
| resolution_accuracy | 0.95 | 0.97 |
| s_per_scene | 17.90 | 17.63 |
| MLflow runs | 1cf682ca4b1949f58de8ed1abb2713c2 | efd1a28bb8304bea87252c074f8f91b4 |

- The WRatio version is kept in `events.wratio.jsonl`. The fix-round-1 re-score changed 41 free-text arguments (grounded 631 → 629, recall 0.863 → 0.858, name-mention recall 0.81 → 0.77, accuracy stays 0.966); fix round 2's exact-name rule changed 8 more mappings with metrics identical to 4 decimals (0.9664 / 0.5985 / 0.8575 / 629), so these runs stand.
- Accuracy 0.949 vs 0.966 is about 1.4 SE on about 550 arguments and 1 seed (review M-6).

### Results 2: resolution re-scored with the argument checks (2.1B)

Same raw events as Results 1, from `nip eval compare --exp EXP-020 --md` (`data/exp2.1b/exp020-resolution.md`):

| Metric | enum (W1) | free-text (W1) | enum-checks | free-text-checks |
|---|---|---|---|---|
| events_grounded (kept) | 542 | 629 | 354 | 603 |
| fact_precision | 0.59 | 0.60 | **0.86** | 0.61 |
| fact_recall | 0.70 | 0.86 | 0.70 | 0.86 |
| resolution_accuracy | 0.95 | 0.97 | 1.00 | 0.97 |
| MLflow runs | 1cf682ca… | efd1a28b… | 2325a2ce… | 5035a4db… |

- The type check removes the enum's typical error (a valid but wrong key when the right entity is not in the registry: a thermos → `ada`), so enum precision rises at unchanged recall; its 1.00 accuracy is partly by construction.
- Free-text precision stays about 0.6 because of the truth set: 102 of its 114 "false" holds are `holds … thermos/watches` from flavour lines ("Rui and Sasha share a thermos", "Dov and Rui check their watches") that `truth.json` does not label (the 2.1B reviewer counted 120 of 145 free-text holds on seed-1 clean as such flavour holds).

### Results 3: plot rules on extracted facts, first 2.1B passes

Means ± sd over 3 seeds (extraction calls: enum 162 + 324, free text 162 + 324, all 0 failed):

| Metric | enum | free-text | enum + secret-in-scene (not shipped) |
|---|---|---|---|
| Injected: overall P / R / F1 | 0.02 ± 0.03 / 0.03 ± 0.05 / 0.02 ± 0.04 | 0.00 / 0.00 / 0.00 | 0.07 ± 0.12 / 0.03 ± 0.05 / 0.04 ± 0.07 |
| Injected: planted found (of 12) | 0.33 ± 0.58 (one dead_acts, seed 1) | 0 | 0.33 ± 0.58 |
| Injected: false positives | 15.67 ± 1.15 (all knowledge_order) | 27.00 ± 7.81 | 3.33 ± 0.58 |
| Clean twin: flags (all false positives) | **16.00 ± 1.00** (all knowledge_order) | **27.67 ± 6.43** | 3.67 ± 0.58 |
| Recall knowledge_order / dead_acts / two_places / prop_provenance | 0 / 0.11 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0.11 / 0 / 0 |
| Fact precision / recall (clean twin) | 0.75 ± 0.03 / 0.77 ± 0.04 | 0.57 ± 0.03 / 0.86 ± 0.01 | — |
| Resolution accuracy | 1.00 ± 0.00 | 0.96 ± 0.01 | — |
| Events raw / kept | 861 / 476 | 761 / 675 | — |
| Dropped: argument type / zero confidence / quote | 206 / 99 / 57 | 42 / 14 / 29 | — |
| MLflow runs (injected) | 982113df…, c7a2d458…, 6443e30d… | 9c225fec…, 9e658a5e…, b56372f9… | daff2f8b…, 5a894dc5…, cc4a127a… |
| MLflow runs (clean) | e1930199…, 39d91658…, 455e0738… | fa72ab40…, 7e3afc35…, e4be1045… | dcc6accc…, 8e3c1df7…, 1d87f8d9… |

Per seed (reviewer, from MLflow): enum injected FP 17 / 15 / 15, clean 16 / 17 / 15, found 1 / 0 / 0; free text injected FP 36 / 22 / 23, clean 35 / 23 / 25, found 0; secret variant 4 / 3 / 3 and 4 / 3 / 4. The notes do not state whether the "Events raw / kept" and "Dropped" rows are per show or summed; they are copied as tabled.

### Results 4: before → after the fixes (2.1B fix round 1)

Means over seeds 1–3, 36 planted (9 per check). Variants: **before** = the first 2.1B passes; **r1** = new passes with the one-line-per-`script_line` render fix plus the I2/M1 code; **r1 −presence** = the same replies with derived speaker presence removed (ablation); **r1 +holds** = r1 plus the first holds-value vocabulary (any other verb → use).

| Variant | Overall P / R / F1 | Recall: knowledge_order / dead_acts / two_places / prop_provenance | Planted found (of 36) | FP per injected show | Flags on clean show (all FP) | Fact P / R (clean) | MLflow (injected) |
|---|---|---|---|---|---|---|---|
| enum, before | 0.02 / 0.03 / 0.02 | 0 / 0.11 / 0 / 0 | 1 | 15.7 | 16.0 | 0.750 / 0.774 | 982113df, c7a2d458, 6443e30d |
| enum r1 −presence | 0.02 / 0.03 / 0.02 | 0 / 0.11 / 0 / 0 | 1 | 13.3 | 12.7 | 0.728 / 0.737 | 2b93a95b, 9ff13b02, e3d0818d |
| **enum r1** | **0.20 / 0.28 / 0.23** | 0 / 0.11 / **1.00** / 0 | **10** | 13.3 | 12.7 | 0.647 / 0.737 | 55efce12, eb30bc6d, e556bb42 |
| enum r1 +holds | 0.20 / 0.28 / 0.23 | 0 / 0.11 / 1.00 / 0 | 10 | 13.3 | 12.7 | 0.647 / 0.737 | 401b804c, 20cab085, a82a7e87 |
| free text, before | 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 | 27.0 | 27.7 | 0.565 / 0.860 | 9c225fec, 9e658a5e, b56372f9 |
| free text r1 −presence | 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 | 34.7 | 35.3 | 0.562 / 0.887 | 21606a51, 2bcb051b, 8506d49c |
| **free text r1** | **0.08 / 0.25 / 0.12** | 0 / 0 / **1.00** / 0 | **9** | 34.7 | 35.3 | 0.543 / 0.887 | 5f5d2442, c220df1a, 71b80fb4 |
| free text r1 +holds | 0.06 / 0.47 / 0.10 | 0 / 0 / 1.00 / **0.89** | **17** | **92.3** | **94.7** | 0.543 / 0.887 | 19f9ecd7, 3f2e14cd, a7c3ea6c |

The re-reviewer confirmed all 24 run ids are active and the means recompute exactly (including prop_provenance FP 58.3 injected / 60.0 clean for free text +holds). The `+holds` runs carry an MLflow commit tag of a closeout commit (old SHA `fbdf3b8` / `8f612d5`, now `c0988ee` / `ddf6206`): they ran from 2.1B's uncommitted tree that became `11d03c4` 7 minutes later (re-review m1).

### Results 5: re-score with the principled holds mapping (2.1B fix round 2, no GPU)

`nip eval compare --exp EXP-020-rules / -clean / EXP-020-facts --md` on the fix-round-1 replies; means over seeds:

| Variant | Overall P / R / F1 | Recall: k_order / dead_acts / two_places / prop_prov | Found (of 36) | FP per injected show (prop_provenance) | FP per clean show | Fact P / R (clean) | MLflow (injected / clean) |
|---|---|---|---|---|---|---|---|
| free text r1 (before the holds vocabulary) | 0.08 / 0.25 / 0.12 | 0 / 0 / 1.00 / 0 | 9 | 34.7 (0.7) | 35.3 | 0.543 / 0.887 | 5f5d2442, 71b80fb4, c220df1a / 17abe15a, 4e47c5a7, b38f60f7 |
| free text r1 +holds (any verb → use) | 0.06 / 0.47 / 0.10 | 0 / 0 / 1.00 / 0.89 | 17 | 92.3 (58.3) | 94.7 | 0.543 / 0.887 | 19f9ecd7, 3f2e14cd, a7c3ea6c / 8b5af36c, 8f4f46cd, b234fe50 |
| **free text r2 (prompt verbs only)** | **0.08 / 0.47 / 0.14** | 0 / 0 / 1.00 / **0.89** | **17** | **63.3 (29.3)** | **64.3** | **0.602 / 0.887** | 49953a24, 93a1df6b, b44e01c9 / 3958bf2e, 3f64d8f7, a1e2f93f |
| enum r1 | 0.20 / 0.28 / 0.23 | 0 / 0.11 / 1.00 / 0 | 10 | 13.3 (0) | 12.7 | 0.647 / 0.737 | 55efce12, e556bb42, eb30bc6d / 507f5033, ac34ae1b, bef4e32a |
| **enum r2** | 0.20 / 0.28 / 0.23 | 0 / 0.11 / 1.00 / 0 | 10 | 13.3 (0) | 12.7 | 0.647 / 0.737 | 228a64fc, a42be607, a705c08a / 2acfdc81, 33dbe380, ae56bf33 |

Free text r2 clean-show prop_provenance FP: 29.7. The re-reviewer confirmed all 12 r2 run ids active and the means (free text r2 P 0.082, R 0.472, F1 0.140). The r2 runs are tagged with commit `11d03c4` (old `150256a`, the parent); they ran from the tree that became `962512f`. Fix round 3 (cue extensions) changed no number: the synthetic shows have no cue extensions.

### What was found

1. **Resolution accuracy cannot separate the arms on this set.** First wave 0.949 vs 0.966 (about 1.4 SE, 1 seed); with the checks 1.00 vs 0.96, but the enum's 1.00 is what the type check leaves after removing its mis-resolved arguments. The spec's interesting cases (nicknames, titles, descriptions) are absent: the generator never puts a fact on an alias-only line (`n_args_alias = 0`; only 1 nickname and 7 description mentions fall on lines with events).
2. **The enum's typical error** is a valid but wrong key when the right entity is not in the registry (props are not in the bible, so "thermos" or "signal flare" became `ada`, or a location key filled a subject); the enum arm almost never uses `UNKNOWN` (3 of 564 arguments).
3. **The near-zero rule recall was largely the pipeline, not the model.** Two paragraphs printed under one line number made the model cite the prop line as the next line, and grounding dropped it (review I1); the two_places lines name no place, so a quoted `present_at` cannot exist. After the render fix and derived speaker presence, two_places went 0 → 9/9 in both arms (entirely from presence: the −presence rows stay at 0), and free-text prop_provenance went 0 → 8/9 once the holds values were read in the prompt's vocabulary.
4. **The arms trade failure modes.** The enum cannot express props at all (prop_provenance 0 vs 8/9: it picks a character key, e.g. `holds rui → ada` for "share a thermos", which the type check drops), but raises fewer knowledge_order false positives (12.7 vs 34.7 per clean show after fix round 1). Free text names props but fires prop_provenance on every untracked personal prop (29.3 false positives per injected show after fix round 2).
5. **knowledge_order stayed 0/9 in every variant:** the model emits `learns` and `references` together on the planted "I have known for a long time" line (a `learns` at the same story position counts as learned), and emits `references` on lines with no secret (37 of 55 kept learns/references events on the clean seed-1 show; 8 with swapped predicates). dead_acts: 1/9 (enum), 0/9 (free text); it needs the earlier death as a `state: dead` fact and the speaker resolved.
6. **Fact precision against generator truth is a biased instrument here:** it scores derived presence as false positives (truth puts `present_at` on the action line) and misses unlabelled flavour holds.

### Takeaway

The question the experiment asks (is resolution better with enum IDs or afterwards?) is not answered by this set: there are no alias-only arguments, and the rule-precision gap comes from predicate choice and from what each arm can express, not from resolution. What the experiment did produce is the evidence that moved the Layer 1 rules on extracted facts from 1/36 to 10/36 (enum) and 17/36 (free text): a rendering bug, a design gap for presence, and a value vocabulary mismatch, each isolated by an ablation on identical replies.

### Decision

**Inconclusive; D-025 stands by default** ([B-180](decisions.md#b-180--exp-020-inconclusive-d-025-registry-ids-as-an-enum-stands-by-default)). The first-wave decision was "none yet" ([B-164](decisions.md#b-164--exp-020-first-wave-no-decision-until-the-rule-precision-half)); the first 2.1B reading "done, keep the enum" was withdrawn after review I3.

### What changed in the code because of it

| | Before | After |
|---|---|---|
| Scene rendering in the prompt | `script_line` text verbatim (second paragraph unnumbered) | one numbered line per `script_line`, whitespace collapsed ([B-169](decisions.md#b-169--the-prompt-prints-one-numbered-line-per-script_line)) |
| `present_at` for speakers | only if the model quotes one | derived for resolved dialogue speakers at the heading's location, confidence 0.9, not for off-screen voices ([B-170](decisions.md#b-170--resolved-dialogue-speakers-are-present-at-the-headings-location-d-21b-1)) |
| holds/owns values | value text as given (`check`, `share`, …) | prompt verbs only; others dropped as `unknown holds value` ([B-172](decisions.md#b-172--holdsowns-values-are-mapped-only-from-the-prompts-vocabulary-other-verbs-are-dropped-and-counted-d-21b-2)) |
| Argument checks, candidate kinds | none | `ARG_KINDS`; candidate kinds provisional ([B-167](decisions.md#b-167--post-model-drops-zero-confidence-duplicates-argument-kinds-per-predicate), [B-171](decisions.md#b-171--a-candidate-entitys-guessed-kind-is-provisional)) |
| `script_line.speaker` | clean name | cue as written ([B-173](decisions.md#b-173--script_linespeaker-stores-the-character-cue-as-written-d-21b-3)) |
| Enum vs free text in the shipped stage | enum (D-025) | unchanged |

### Review that shaped it

- **2.1 review:** fairness and candidate-crediting checked; the 0.018 accuracy gap is about 1.4 SE, phrase it "not shown ≥", not "fails" (M-6).
- **2.1B review:** I1 found the rendering bug by reading the saved events against truth (all 20 free-text prop `holds` on seed-1 clean cite `.2` with line `.1`'s quote, scores 26–41) and the presence design gap; I3 withdrew "keep the enum" (rule precision 1 true flag in 51 vs 0 in 81, both at the floor). It also asked that the rule half be re-run after I1 before concluding anything about predicate choice (controller instruction, [B-184](decisions.md#b-184--fix-round-1-must-re-measure-the-plot-rules-on-real-facts-later-rounds-re-score-without-the-gpu)).
- **2.1B re-review:** the `+holds` mapping was tuned and evaluated on the same replies (in-sample recall 0.47), with a catch-all that turned `remove` into a use (N2, ruled: prompt verbs only); derived presence would misplace V.O./phone voices on real scripts (N3); the image mix (afd27c67 / dd67ae7b, same vLLM 0.30.0 and xgrammar 0.2.8) is not a material confound, and the two attributions are ablations on identical replies.
- **2.1B re-review 2:** the skip-intercut variant would remove the rule's own true positives; the revert is correct.

### Open items

- A set with alias-only mentions (Beverly Hillbillies, R3, or a 2.9A generator change); the spec's Label Studio mention labels do not exist.
- Prompt v2 for learns vs references ([B-177](decisions.md#b-177--prompt-v2-for-learns-vs-references-proposed-not-built)); knowledge_order is 0/9.
- About 29 prop_provenance false positives per show on never-obtained personal props (tier proposal to 2.3, [B-178](decisions.md#b-178--prop_provenance-on-never-obtained-personal-props-lower-tier-proposed-to-23)).
- Real scripts: the derived presence, the off-screen regex and the holds vocabulary were measured only on synthetic template text; `take` / `get` acquisitions are now dropped.
- Truth story order was used; the rule half has not been measured with 2.2's story stage in the loop.
- 4 calls in flight vs the shipped stage's 1; one model; temperature 0 with batch nondeterminism.

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
- **Update (EXP-001):** measured 44.7 MiB per 1,000 tokens (45.8 per 1,024) for qwen3.5-4b-awq, so the docs' 60 was 31 % high and hf-mem's 128 was about 2.8x high; see [C-017](#c-017--kv-cost-per-token-docs-60-hf-mem-128-measured-about-45).

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

- **Takeaway:** the planner's laptop result flips from "staged with a 4b model" to "no LLM fits" between the two figures. Free VRAM inside WSL/Docker is not yet measured. **Update (EXP-001):** inside the container CUDA reads a constant 6.93 GiB free of 8.0 in every trial while NVML on the same GPU ranged 5,934 to 7,767 MiB, so the two views disagree and only NVML follows Windows. Feeds EXP-001; see [B-044](decisions.md#b-044--the-laptop-cannot-plan-an-llm-at-613-gb-free-exp-001-runs-before-the-walking-skeleton).

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

## C-011 · First vLLM start: 335 s down to 85 s

- **Deliverable / source:** 1.7 (EXP-001 pilots), `notes/1.7.md`. Two pilot trials tagged `EXP-001-pilot`, kept out of the EXP-001 tables.
- **Pilot 1** (gmu 0.75, run 5b01a47a, weights on a Windows bind mount): load **335.3 s**. From the vLLM log: 36 s to "Resolved architecture" (imports plus Hub calls, with an "unauthenticated requests to the HF Hub" warning), multimodal warmup 28.1 s, **weights 91.96 s for 3.76 GiB** ("Filesystem type for checkpoints: 9P ... Auto-prefetch is disabled"), engine init (profile + KV + warmup) 100.5 s. Tokens/s 126.5.
- **Changed:** `HF_HUB_OFFLINE=1` (all weights are local, so every Hub call is wasted).
- **Pilot 2** (e14e220f, fresh container): load **212.8 s** (weights 47.15 s, engine init 87.7 s). Later warm starts in the same container took about **85 to 88 s**, which is the load figure in the EXP-001 tables.
- **Takeaway:** on this laptop a cold first start of a 4B model is dominated by Hub calls, a 9P file mount and engine init, not by the memory setting. Weights from a Windows bind mount load over 9P at about 41 MB/s cold (3.76 GiB in 92 s) and about 82 MB/s warmer (47 s) (arithmetic from the figures above). A VM-local volume would be faster but contradicts the "weights on D:" rule (1.7 report concern 4).

## C-012 · Unload time: 33.1 s down to 4.0 s (the zombie EngineCore)

- **Deliverable / source:** 1.7 fix round 1 (review Important I2), commit `989e0ed`.
- **Finding:** `VllmServer.stop()` now always SIGTERMs the process group (vLLM's EngineCore is a separate child, so killing only the main process orphans it and its VRAM). On the first real run of the new code unload took **33.1 s** instead of 4 s. `ps` in ray-head showed `934 1 794 ZN python3`: the orphaned EngineCore had become a zombie under the container's PID 1 (`ray`), which never reaps it, so `kill(-pgid, 0)` kept succeeding until the 30 s timeout.
- **Fix:** `_group_running(pgid)` reads `/proc/*/stat` and ignores state `Z` (a zombie holds no GPU memory). Re-run: unload **4.0 s** (4.1 s in the integration test). The zombies stay until the container restarts (2 seen after two starts); closeout added `init: true` to ray-head in `compose.yaml` (tini reaps them, [B-118](decisions.md#b-118--closeout-hygiene-ray-head-init-true-laptop-only-dev-realm-gitignore-pattern-and-timecode-strictness)).
- **Reviewer's check of the fix:** `/proc/<pid>/stat` is split on the last `)` so a command name with parentheses is safe; a vanished pid raises `ProcessLookupError`; a group holding only zombies makes the loop exit; the kernel keeps the pgid reserved while a zombie member exists, so it cannot be reused.

## C-013 · `nip` CLI startup: 10.9 s down to 1.1 s (lazy imports)

- **Deliverable / source:** 1.10 and its fix round (review Minor M5), commit `2d0bf6a`.
- **Before:** wiring the sub-apps into the root CLI made every `nip` invocation, including `--help`, import torch (3.94 s, via `nip.timeline.shots`) and mlflow (3.84 s, via `eval.report`) from `python -X importtime`. `nip --help`: **10.92 / 10.54 / 10.45 s** (3 warm runs, `.venv\Scripts\nip.exe`, PowerShell `Measure-Command`); the whole Sintel `nip run` took 10.8 s of which about 9.1 s was import.
- **Tried, in two steps:** import `shots` (torch) inside `analyze_picture`, and mlflow inside `eval.report.run/compare` (`import nip.cli`: 9.12 s to 1.82 s); then scipy in `eval.metrics` too (to 0.69 s).
- **After:** `nip --help` **1.12 / 1.21 / 1.15 s**; the closeout's Sintel `nip run` took 1.3 s wall. One existing test had to change (1.8's picture CLI test now patches `shots.detect_shots`); the reviewer confirmed its assertions were not weakened.
- **Decision:** [B-113](decisions.md#b-113--lazy-torch-mlflow-and-scipy-imports-in-the-cli-superseding-b-111) (supersedes the "accepted for now" of B-111).

## C-014 · TransNetV2 input resize filter: TorchCodec bilinear vs ffmpeg bicubic

- **Deliverable / source:** 1.8 part B (EXP-002 side study), `exp002_shots.py resize-test`, MLflow `EXP-002-sintel-resize` (8 runs). Concern raised by the 1.8A report: TransNetV2 was trained on `ffmpeg -s 48x27` (bicubic) input; TorchCodec's `Resize` is swscale bilinear with antialias.

| Resize path | Masked F1 at thr 0.5 | at thr 0.3 |
|---|---:|---:|
| TorchCodec Resize (current) | 0.917 | 0.943 |
| ffmpeg bilinear | 0.920 | 0.946 |
| ffmpeg bicubic | 0.910 | 0.943 |
| ffmpeg area | 0.917 | 0.943 |

- **Per-frame effect:** maximum difference in output probability 0.052 to 0.072; cuts found differ by 1 to 2 of about 160. One cut is 0.003 to 0.006 F1.
- **Takeaway:** at most 0.007 F1, within one cut. The "trained on bicubic" worry did not hold up on this film; the bicubic path is not better than the current one. No code change (Sintel only, provisional labels).

## C-015 · Decode backend and keyframe cost on real film

- **Deliverable / source:** 1.8 part B, real-film run and resize test.
- **Decoder:** the ffmpeg CLI decode + scale of Sintel took **22 to 24 s (about 900 to 950 fps)**, against **35 to 38 s (565 to 615 fps, warm)** for TorchCodec exact-seek decode + `Resize`. TorchCodec is therefore not the fastest option. Not changed: exact seek and the frame axis are the reason TorchCodec is used ([B-025](decisions.md#b-025--lgpl-shared-ffmpeg-81-from-btbn-for-torchcodec-on-windows), [B-028](decisions.md#b-028--num_ffmpeg_threads0-for-both-decoders), [B-094](decisions.md#b-094--no-change-to-part-a-after-exp-002-and-where-the-experiment-files-live)).
- **Keyframes are not free:** 398 full-resolution JPEGs on Sintel took 31.8 s (80 ms each), a third of the 99.5 s pipeline wall time; on Tears of Steel (720p) 16 ms each. Random access plus exact seek per frame, then JPEG. Not optimised; EXP-008 (keyframe density) should account for it.
- **Memory:** about 1.2 GB peak RAM for the detector alone (1.9 GB with keyframes) is far above the roughly 90 MB of 48x27 frames; the rest is torch, the CUDA context and TorchCodec buffers, dominated by the Python process, not the film length. 8 GB of VRAM is not a constraint (0.33 GB), so TransNetV2 can share the GPU with vLLM later.

## C-016 · Which AWQ checkpoint for qwen3.5-4b-awq?

- **Deliverable / source:** 1.7, HF API figures on 2026-10-16 (sizes from the API, not from measured runs); review Important I1.
- **Problem:** the catalog had `base_model: Qwen/Qwen3.5-4B` (8.68 GiB bf16) and no AWQ repo, so `apps()` would have handed the bf16 model to `vllm serve` on an 8 GB GPU.

| Candidate | Size | Note |
|---|---:|---|
| `Qwen/Qwen3.5-4B` (the catalog's base) | 8.68 GiB | bf16; does not fit with KV on 8 GB |
| `cyankiwi/Qwen3.5-4B-AWQ-4bit` | 3.78 GiB (one 4,040,461,440-byte shard) | compressed-tensors W4 g32, 233,713 downloads, Apache-2.0; **chosen**: matches tech-stack's 4.0 GB |
| `QuantTrio/Qwen3.5-4B-AWQ` | 5.68 GiB | keeps linear_attn/self_attn/visual unquantized |
| `sanskar003/Qwen3.5-4B-AWQ` | 4.72 GiB | |

- **Evidence it works:** it loaded and served in all 66 trials plus the integration test; vLLM reports 4.25 GiB for weights plus non-torch. It is a third-party quantization; licence and provenance are as reported on the Hub and the reviewer did not verify them.
- **Decision:** [B-082](decisions.md#b-082--checkpoint-for-qwen35-4b-awq-is-cyankiwiqwen35-4b-awq-4bit-in-the-catalog).

## C-017 · KV cost per token: docs 60, hf-mem 128, measured about 45

- **Deliverable / source:** EXP-001 (1.7), closing the comparison opened in [C-003](#c-003--hf-mem-kv-estimates-vs-the-docs-kv-figures).

| Source | MiB per 1k tokens (qwen3.5-4b-awq) |
|---|---:|
| docs / first catalog | 60 |
| hf-mem 0.5.6 (every layer counted as full attention) | 128 |
| EXP-001, per 1,000 tokens (1.56 GiB / 35,746; 0.94 GiB / 21,597) | 44.7 / 44.6 (reviewer: 44.0 to 44.7, marginal slope about 44.0) |
| EXP-001, per 1,024 tokens (closeout restatement) | **45.8** (45.76 and 45.64 from the two rows) |
| EXP-001 `plan` runs at 16k context | about 38 |

- **Takeaway:** the measurement settled C-003 in favour of the docs' direction (the real figure is below 60, so hf-mem's 128 is about 2.8x high; this is consistent with, but not proof of, the C-003 hypothesis that hf-mem counts every layer of the hybrid linear-attention model as full attention). The 1,000-versus-1,024 mismatch between the calibration and the planner was a 2.4 % underestimate of KV per token, found by the re-review (N1) and fixed in the closeout ([B-115](decisions.md#b-115--kv-calibration-restated-per-1024-tokens-446---458)). The 45.8 comes from vLLM's two-decimal GiB figures, so it is good to about 1 %.

## C-018 · Walking-skeleton benchmark: P/R/F1 1.00 on planted readability errors, and why it proves little

- **Deliverable / source:** 1.10, `notes/1.10.md`; no EXP id (MLflow tag `exp=WS-1.10`, local store `data/runs/1.10/mlflow.db`).
- **Setup:** Sintel Spanish track (26 cues). Injector `loc.readability.v1`, seeds 1 to 3, 6 planted cues per seed (one of each kind: reading speed, min duration, max duration, chars per line, gap, lines). `nip run` on each injected copy, then `nip eval run --set walking-skeleton --variant readability-v1 --seed N`, then `nip eval compare --runs <3 ids>`.

| Metric | readability-v1 (3 seeds) |
|---|---|
| loc.readability P / R / F1 | 1.00 ± 0.00 / 1.00 ± 0.00 / 1.00 ± 0.00 |
| TP / FP / FN per seed | 6 / 0 / 0; native TP 5 / 5 / 6 (an injection on cue 11 replaced its native CPS problem in seeds 1 and 2) |
| Noise: shown FP per content-hour | 0.00 ± 0.00 |
| Verification: FPs / TPs dropped | 0.00 / 0.00 |
| Wall s per content-hour | 1.69 ± 0.66 (pipeline stage time only, excluding CLI import) |
| Coverage | 1.00 ± 0.00 |

- Flags kept per seed 11 / 11 / 12 (0 dropped), evidence 17/17, 17/17, 18/18 resolved. Clean-run scored against native labels only: 6 native TP, 0 FP.
- **Takeaway: the 1.00 is plumbing, not rule correctness.** The injector and the check read the same rule pack, 18 planted errors is a small sample, labels are ref-only so a flag on the planted cue for the wrong rule would still score a TP (review M4), and the 6 native labels are machine-triaged. The doc's seconv-lint oracle (D-030) is the real independent check and is not set up. The number must not be quoted as check quality.
- **A second finding:** on the clean Sintel tracks 15 of 20 flags (es 6, fr 8, de 6) are gap-closing ones, all `must_review` (confidence 1.0, pure rules). That is documented behaviour (the rule pack says gaps of 3 to 11 frames are closed to 2), not a defect, but a product decision on tier or severity is open ([B-100](decisions.md#b-100--gap-closing-is-part-of-locreadability-severity-2-tier-follows-confidence)).

## C-019 · Exact KV budget vs the old gmu sizing on big GPUs

- **Deliverable / source:** 1.7 re-review, a scratch script over the three table inventories x both objectives; arithmetic checked by hand. Concern: applying exact KV to every single-GPU engine caps KV at 2 full-context sequences.

| Inventory / objective | Engine | ctx | KV now (GiB) | KV(ctx x 2) | gmu-implied before |
|---|---|---:|---:|---:|---:|
| 1x48GB quality | qwen3.8-27b-fp8 | 32768 | 10.00 (cap) | 10.0 | 10.21 |
| 1x48GB quality | gemma-4-31b-qat (judge) | 8192 | 17.39 | 15.0 | 15.47 |
| 1x48GB throughput (resident) | qwen3.8-27b-int4 | 16384 | 7.99 | 5.0 | 5.35 |
| 8x80GB both | gemma-4-31b-qat x8 / x4 | 16384 | 30.00 (cap) | 30.0 | 30.75 |
| 8x80GB both | qwen3.5-397b tp8 / tp4 | 32768 | None (gmu kept) | – | – |

- **Takeaway:** no big-GPU case is starved (every engine gets at least KV(ctx x 2)); the only loss is about 2 % on 48 GB quality, from the cap; elsewhere the budget stays the same or grows. One caveat (N2): on a GPU shared with actors the exact budget absorbs the leftover (qwen 7.99 GiB instead of its own 5.0 on 1x48GB throughput), which the closeout checked and found the planner already reserves actor sizes first ([B-117](decisions.md#b-117--shared-gpu-exact-kv-the-premise-was-wrong-pinned-with-a-test-instead-of-changed)). Revisit with EXP-015.

## C-020 · Stage cache: cold run vs a one-line scene edit

- **Deliverable / source:** 2.9B-1 demo (`.superpowers/sdd/phased-plan/notes/2.9B.md`) and `tests/integration/test_rerun.py`. Host run, `NIP_PROFILE=cpu` stub Plan with replayed extraction; synthetic show seed 1, S01E01 + S01E02 scripts, bible, en/es subtitles, dev store (Postgres 127.0.0.1:54432, SeaweedFS 127.0.0.1:8333). Not a formal experiment.
- **Change between the runs:** S01E01 scene 3, one dialogue line, "I counted gulls ..." → "I counted ships ..." (an edit, not an insert), re-ingested as a new script draft (`src_68` → `src_74`).

| Run | Units | Cached | Keyed units | Hit rate | Re-run |
|---|---:|---:|---:|---:|---:|
| `run_51` cold | 74 | 0 | 66 | 0.0 | 74 |
| `run_52` scene 3 edited | 74 | 61 | 66 | **0.9242** | 13 |

- **What re-ran in `run_52`:** 5 keyed units: `knowledge.extract S01E01/sc/3` (1 of 50 scenes), and `plot.dead_acts` + `plot.two_places` for both episodes (they read `present_at` / `state` facts show-wide, which the edited scene's extraction changed). Plus the 8 unkeyed units (consolidate, index, cue_align, `loc.observed`, 2 each). Cached: the 49 other scenes, all 8 localization units, `plot.knowledge_order`, `plot.prop_provenance`.
- **The integration test adds:** an unchanged re-run hits 1.0; `--force` hits 0; every `stage_cache` row has hits ≥ 1; a draft that drops a scene deletes it and its chunk.
- **Takeaway:** a one-line edit reuses 92.4 % of keyed units. The misses are the edited scene and the show-wide rules that depend on its facts, which is the intended invalidation. With stubs this measures cache correctness, not GPU time saved; the time saved with real models is unmeasured, and `knowledge.story` (uncached) would re-run in full.

## C-21 · Store-backed `nip run` vs the 1.10 file run on Sintel

- **Deliverable / source:** 2.0, `notes/2.0.md` (Measured, Done-criterion checks), `reports/2.0-report.md`. Single runs on the laptop (`time`), dev DB on pgvector 0.8.2-pg18, SeaweedFS 4.47; input = Sintel first-minute PDF, en + es SRT, the 1.17 GB mkv, the cached 1.10 `picture.json`. Not a formal experiment.

| What | Store path (2.0) |
|---|---:|
| First `nip ingest`, 4 files incl. the 1,172,428,172-byte mkv upload | 48.4 s |
| Re-ingest of the same 4 files (hash only, `stored: []`) | 11.7 s |
| `nip run` whole CLI process (incl. NVML probe, catalog load) | 8.7 s |
| Stage timeline (load from Postgres) | 0.075 s |
| Stage checks | 0.009 s |
| Stage verification | 0.0009 s |
| Stage flags (persist) | 0.083 s |
| Stage report | 0.036 s |

| Equality check against the 1.10 file run | Result |
|---|---|
| `load_timeline` vs `build_timeline` spans | equal over 614 spans (scene 2, shot 162, keyframe 398, subtitle_cue 52, + 16 script lines) |
| `loc.readability` flags (title, ref minus episode prefix, frames, role, severity, tier) | 6 = 6 identical; all evidence and rule re-check pass |
| Fingerprints, run 1 vs run 2 | identical sorted lists (6 = 6) |
| Rows added by re-ingest | 0 |

- **Takeaway:** the store path reproduces the file run exactly. For reference only (different process and command, not a controlled comparison), the 1.10 file run's stages were timeline 0.0047 s, loc.readability 0.0006 s, verification 0.0004 s, report 0.0002 s; loading from Postgres and persisting flags are the new costs, both under 0.1 s on this input.

## C-22 · Entity name scorer: WRatio vs whole-word subset vs exact-first

- **Deliverable / source:** 2.1 review I-1, re-reviews 1 and 2 (`reports/2.1-review.md`, `2.1-rereview.md`, `2.1-rereview2.md`): probes of `entities.score` and a DB-less `Resolver` with the names Tom, Dov, Ada Kovac, Ada Maria Kovac, Tomas Vale, Mira Vale and one secret description naming Tomas. Not a formal experiment; resolve threshold 90.

| Surface | WRatio (first version) | Subset-or-ratio (`6b2ddf4`) | + exact name 101 (`608c5a1`) |
|---|---|---|---|
| tomato | 90 → Tom (false merge) | 66.7 → candidate | candidate |
| Dover Street | 90 → Dov (false merge) | 40 → candidate | candidate |
| Ruins | 90 → Rui (false merge) | — | — |
| Ada / ADA / Kovac | resolves (the same exact-90 path) | 100 → Ada Kovac | Ada Kovac |
| Tomas | — | 100 → Tomas Vale (the secret description does not compete: half rule) | Tomas Vale |
| Tomas Vael / T0mas Vale / Tomas Va1e | — | 90 → Tomas Vale | Tomas Vale |
| Tornas Vale | — | 85.7 → none | none |
| Captain Ada Kovac / Captain Kovac / Ms. Kovac | — | 69.2 / 72.7 / 66.7 → none | none |
| Tom's / Tommy / Maria | — | 75 / 75 / 50 → none | none |
| Vale (shared surname), repeated | WRatio 90 vs 100 for the exact candidate: reused the first candidate | TIE → a new candidate on every call (100, 101, 102, 103) | same candidate each time |
| Ada Kovac (with Ada Maria Kovac) | 85.5 vs exact: resolved | TIE → new candidate each call (104, 105, 106) | Ada Kovac |
| "ada  kovac" (double space) | — | — | Ada Kovac (whitespace collapsed) |

- **Also rejected:** `token_set_ratio` (the reviewer's suggestion): accepts "Dov Street" → Dov and "Captain Ada Kovac" → Ada (reverse containment). The subset rule without the "at least half the words" condition made every dialogue speaker NULL in the integration test ("TOMAS" tied between "Tomas Vale" and the secret description).
- **Effect on EXP-020** (replayed, no model calls): free-text arm 41 arguments changed, grounded 631 → 629, recall 0.863 → 0.858, accuracy 0.966 unchanged; then 8 more mappings changed with identical metrics.
- **Takeaway:** the synthetic names are disjoint, so EXP-020's 0.97 said nothing about the false merges; the probes did. Titles, possessives and middle names now fail closed into the candidate queue. Decision: [B-161](decisions.md#b-161--names-match-on-whole-words-subset-with-at-least-half-the-words-an-exact-name-scores-101).

## C-23 · Runaway guard: 2.1's schema vs a per-line cap vs cap + line enum

- **Deliverable / source:** 2.1B, `notes/2.1B.md` (Runaway rate), `nip eval compare --exp RUNAWAY-2.1B --md` (`data/exp2.1b/runaway.md`); the reviewer matched every column to MLflow. Enum arm, synthetic seed-1 clean show, default KV at 8k, 4 calls in flight on a contended host. `before` was stopped after S01E01–E03 (75 scenes), so the first three columns compare those 75 scenes.

| Metric | before | cap | shipped | cap-all | shipped-all |
|---|---|---|---|---|---|
| scenes | 75 | 75 | 75 | 150 | 150 |
| failed_scenes | 8 | 2 | 0 | 2 | 0 |
| failed_rate | 0.11 | 0.03 | 0.00 | 0.01 | 0.00 |
| failed_timeout (3 × 600 s) | 3 | 0 | 0 | 0 | 0 |
| failed_max_tokens | 3 | 0 | 0 | 0 | 0 |
| failed_line_outside_scene | 2 | 2 | 0 | 2 | 0 |
| capped_scenes | 0 | 8 | 7 | 16 | 18 |
| events_raw | 335 | 426 | 429 | 864 | 884 |
| events_zero_confidence | 15 | 55 | 72 | 106 | 149 |
| max_events_per_scene | 11 | 16 | 16 | 16 | 16 |
| call_s_failed_sum | 9,442 | 122 | 0 | 122 | 0 |
| call_s_sum (contended host) | 15,760 | 3,106 | 5,344 | 8,528 | 9,186 |
| MLflow runs | 34c717ea… | 297d807e… | cf35c54b… | faa875e4… | 55eb4e3d… |

- **Before:** 8/75 = 10.7 % of scenes failed, and failures held 60 % of the pass's call-seconds (derived: 9,442 / 15,760). Earlier measurements of the same schema: 8/150 (2.1 first wave, sequential, before `disable_any_whitespace`) and 2/25 (W-serve, sequential, with it).
- **Timeouts:** the 3 timeout failures took 1,801 to 1,803 s each (600 s × the SDK's 2 retries); fixed by `max_retries=0` ([B-168](decisions.md#b-168--the-openai-sdk-under-instructor-runs-with-max_retries0)).
- **Grammar probe:** `maxItems: 3` on "ten fruits" returned `["Apple", "Banana", "Orange\", "]` with `finish_reason=stop`.
- **Takeaway:** the runaway is an unbounded enumeration and the timeout retries tripled its cost; the cap ends it (shipped 0/150, 18 scenes capped, 149 confidence-0 events dropped). The "line outside the scene" failures were the rendering bug, not the model ([B-169](decisions.md#b-169--the-prompt-prints-one-numbered-line-per-script_line)). The `call_s` columns are unusable for timing (host CPU 94 to 98 %). **Not measured** (review M8): the recall effect of the cap and the line enum; no fact P/R exists for `before` / `cap` (the reviewer's per-event check found no true fact lost by the drops). Decisions: [B-165](decisions.md#b-165--runaway-guard-at-most-4-events-per-scene-line-enforced-by-the-grammar), [B-166](decisions.md#b-166--line-is-an-enum-of-the-scenes-line-numbers).

## C-24 · Derived speaker presence: with, without, and skipping intercut scenes

- **Deliverable / source:** 2.1B fix rounds 1–2, `notes/2.1B.md`; ablations on identical replies (the r1 caches), 3 seeds, 9 planted two_places violations; MLflow ids in [EXP-020](#exp-020--entity-resolution-enum-constrained-ids-vs-fuzzy-matching-afterwards) Results 4.

| Variant | two_places recall (enum / free text) | Flags on clean show (enum / free text) | Fact P (clean, enum / free text) |
|---|---|---|---|
| r1 without derived presence | 0 / 0 | 12.7 / 35.3 | 0.728 / 0.562 |
| r1 with derived presence | **1.00 / 1.00** | 12.7 / 35.3 | 0.647 / 0.543 |
| r2 with presence, skipping `intercut` scenes (tried, reverted; runs deleted) | 0 / 0 (0/9) | not recorded | not recorded |

- **Takeaway:** two_places on extracted facts comes entirely from derived presence; the planted lines name no place. Presence costs measured fact precision only because truth puts `present_at` on the action line. Skipping intercut scenes removes the rule's own true positives, because `intercut` also marks SAME TIME scenes. Decision: [B-170](decisions.md#b-170--resolved-dialogue-speakers-are-present-at-the-headings-location-d-21b-1).

## C-25 · holds/owns values: as written vs any verb → use vs prompt verbs only

- **Deliverable / source:** 2.1B fix rounds 1–2; free-text arm, 3 seeds, 9 planted prop_provenance violations; same replies in every row (CPU re-scores). Value distribution of 417 kept free-text holds on the injected shows: `check` 186, `share` 171, `use` 24, `obtain` 20, `lose` 13, `take` 3.

| Mapping | prop_provenance recall | Overall P / R / F1 | FP per injected show (prop_provenance) | Fact P / R (clean) | Dropped as `unknown holds value` |
|---|---|---|---|---|---|
| as written (r1) | 0 | 0.08 / 0.25 / 0.12 | 34.7 (0.7) | 0.543 / 0.887 | — |
| any other verb → use (`11d03c4`) | 0.89 | 0.06 / 0.47 / 0.10 | 92.3 (58.3) | 0.543 / 0.887 | — |
| prompt verbs only (`962512f`, controller ruling) | 0.89 | 0.08 / 0.47 / 0.14 | 63.3 (29.3) | 0.602 / 0.887 | 174 (171 `share`, 3 `take`); enum 136 |

- **CPU what-if on 2.3's rule (not shipped):** dropping the "never obtained anywhere" case removes all prop_provenance false positives on the clean shows (58 / 67 / 55 → 0, measured with the any-verb mapping) but keeps only 3 of the 8 true flags (seeds 1–3: 2, 0, 1).
- **Takeaway:** `check → use` follows the prompt's own definition ("picks up, carries, uses or checks"); `share → use` and the catch-all were fitted to these replies and doubled the false positives. The principled mapping keeps the recall and halves the prop_provenance noise; what remains are uses of personal props nobody obtains. Decisions: [B-172](decisions.md#b-172--holdsowns-values-are-mapped-only-from-the-prompts-vocabulary-other-verbs-are-dropped-and-counted-d-21b-2), [B-178](decisions.md#b-178--prop_provenance-on-never-obtained-personal-props-lower-tier-proposed-to-23).

## C-26 · One printed line per `script_line`: quote drops before and after

- **Deliverable / source:** 2.1B review I1 (evidence from the saved events) and re-review (MLflow `EXP-020-facts`, means over 3 seeds).

| Arm | Quote drops per show, before → after | Fact recall (clean), before → after |
|---|---|---|
| free text | 28.7 → 3.7 | 0.860 → 0.887 |
| enum | 57.3 → 4.3 | 0.774 → 0.737 (the enum's later recall also reflects the new passes and the I2 code; not attributable to the render alone) |

- **What the bug looked like:** on seed-1 clean, all 18 truth `holds`, 3 `setup`, 3 `payoff` and 3 of 5 `state` facts sit in the second paragraph of a two-paragraph action line; all 20 free-text prop `holds` cited line `.2` with the quote of line `.1`'s second paragraph and scored 26 to 41.
- **Takeaway:** a prompt-rendering detail, not the model, was behind zero prop recall and the "line outside the scene" failures. Decision: [B-169](decisions.md#b-169--the-prompt-prints-one-numbered-line-per-script_line).

## C-27 · Story order on the base synthetic show: rules only vs rules + bible, and stress variants

- **Deliverable / source:** 2.2 (`notes/2.2.md`, `reports/2.2-report.md`); `pytest tests/unit/knowledge/test_story.py -s` (printed per seed) and ad hoc runs of the same `derive` on seed 1; commit `6ad9a53`. Not a formal experiment.

| seed | arm | Kendall tau-b | scene days correct | `story_inferred` |
|------|-----|---------------|--------------------|------------------|
| 1, 2, 3 | rules + bible overrides | 1.0000 | 150/150 (seed 1) | 0 |
| 1, 2, 3 | rules only (no bible) | 0.9998 | 148/150 (seed 1) | 2 (the flashbacks) |

Stress variants of seed 1 (ad hoc, not committed):

| variant | ambiguous transitions | tau | days correct | inferred |
|---------|-----------------------|-----|--------------|----------|
| as generated | 0 | 1.0 | 150/150 | 0 |
| "NEXT MORNING" -> "MORNING" | 14 | 1.0 | 150/150 | 14 |
| time of day removed from every heading | 0 | 1.0 | 8/150 | 141 |

- **Tried X → Y:** the first day rule advanced a day on every NEXT MORNING heading; the generator writes it on every scene of a morning, so 141 of 150 days were wrong from scene 8 on. Treating two NEXT-cue scenes in a row with the same time of day as one morning gave 150/150.
- **Also measured:** through Postgres (6 episodes and the bible ingested, the stage run from one episode) all 150 `story_seq` / `story_day` equal `truth.json`, tau 1.0; synthetic tau unchanged after the review fixes.
- **Takeaway:** rules-only misses one pair of 11,175 (the two flashbacks' order, which the bible fixes). A regression in this generator is always a next day, so the default is already right and the show cannot separate EXP-007's arms; that led to [B-191](decisions.md#b-191--an-ambiguous-transitions-synthetic-variant-so-exp-007-can-discriminate). Without any time of day the order survives and the days do not.

## C-28 · Experiment teardown: delete by re-planning vs delete by Serve status

- **Deliverable / source:** 2.2B (`notes/2.2B.md` "What broke" 3, `reports/2.2B-review.md`); commit `23f13d4`. Not a formal experiment; single observations.

| `down` version | Apps found | Outcome | VRAM after |
|---|---|---|---|
| Re-plan to rebuild the app list (first version; same pattern as `exp020_resolution.down`) | none: with the model loaded the planner no longer fits it | `teardown` waited 120 s and raised "VRAM used 7822 MiB after teardown, idle was 1102" (twice); session ended by stopping the container | 578 MiB after the container stop |
| Delete every app in `serve.status().applications`, wait for idle | all | 18.9 s wall | 7651 → 343 MiB |

- **Takeaway:** a teardown must not depend on the planner, whose answer changes once the model holds the memory. The by-status version deletes every Serve app, so it is safe only under `data/gpu.lock` ([B-197](decisions.md#b-197--the-experiments-down-deletes-serve-apps-by-status-under-the-gpu-lock)).

## C-29 · Layer 1 rules on oracle facts: P/R/F1 1.00, a rules-only ceiling

- **Deliverable / source:** 2.3 (`notes/2.3.md`, `reports/2.3-report.md` incl. fix round 1, `reports/2.3-review.md`); `eval/exp/layer1_oracle.py`; `nip eval run --set plot-l1 --exp PLOT-L1 --variant oracle-facts[-lost] --seed N`; table from `nip eval compare --exp PLOT-L1 --md --subset all`; MLflow `sqlite:///data/mlflow/mlflow.db`. Commits `35a33ca`, `3aa1594`. Not a formal experiment.
- **Set:** the 2.9A plot-L1 injected synthetic show (`nip eval inject --set mvp --seed N --only plot`), 12 labels per seed = 3 per check, seeds 1-3; facts = `truth.json` loaded by 2.3's own consolidation stand-in.

| check | precision | recall | F1 (3 seeds, mean) |
|---|---|---|---|
| plot.knowledge_order | 1.00 | 1.00 | 1.00 |
| plot.dead_acts | 1.00 | 1.00 | 1.00 |
| plot.two_places | 1.00 | 1.00 | 1.00 |
| plot.prop_provenance | 1.00 | 1.00 | 1.00 |
| overall | 1.00 | 1.00 | 1.00 |

- tp 12 / fp 0 / fn 0 per seed; the clean (un-injected) show raises 0 flags on seeds 1-3; rule wall time 0.03-0.11 s per check for all 6 episodes of a seed. After the fix round both `oracle-facts` and `oracle-facts-lost` (every destroyed prop written as `lost`) score 1.00 on all checks and overall; the first three MLflow runs had used the SQL from before the confidence change and were deleted and re-scored (review M-5).
- **What the 1.00 does not show** (review "oracle circularity"): there is no shared helper code with the label source (labels are recorded by the 2.9A injector at plant time), but the store is loaded by 2.3's own `consolidate()`, which makes a state fact for any state value, so the "lost never fires on 2.1's facts" gap (I-1) was invisible; and the generator plants only one `destroyed` per prop, so the earliest-vs-latest-loss bug (I-2) was never exercised. Both were found by reading code, not by this benchmark.
- **Takeaway:** a ceiling for EXP-007 and EXP-020: with exact facts and exact story order the rules are right. Real rates are bounded by 2.1's extraction and 2.2's story order; the 0.80 recall / 0.85 precision MVP targets concern extracted facts. For contrast (2.1B's numbers, not this deliverable's): the ledger records the plot rules on real extracted facts at P/R 0.02/0.03, then 0.20/0.28 after 2.1B's fix round (`progress.md` line 242).

## C-30 · Cue alignment: rank pairing vs shifted rank pairing vs rank-free onset coincidence

- **Deliverable / source:** 2.4 (`notes/2.4.md`), stress driver `scratchpad/a24/stress24.py` (not committed), unit tests `tests/unit/timeline/test_cue_align.py`. Synthetic tracks; single runs; not a formal experiment.

| Method | Test | Result |
|---|---|---|
| Rank pairing + nearest-start rounds + Theil-Sen | first unit tests (every 10th pair merged, every 7th cue split) | locked onto a line one cue off (offset 3.2 s, slope 0); 15 of 18 tests failed |
| Rank pairing shifted -5..+5 cues, most starts within 0.4 s | 900-cue stress track, 12-25 % merges/splits, 4 % drift | unit tests passed; **0 / 916** exact links |
| **Onset coincidence (FFT over slope x offset) + Theil-Sen (adopted)** | 900 cues, 12-25 % merged/split, +-0.25 s jitter | ratio 1.0427 → 916/916; 1.001 with +0.5 s → 912/912; 25/24 with +2 s → 905/905; 0.96 → 492/492; 1.25 (30 fps timing on 24) → 887/887; 30-cue track at 25/24 → 30/30 |
| Same, coarse start only | 5-cue identical track (store integration test) | reported a +29-frame offset; a 1.2 x identity + 2 hysteresis did not help; fixed by also refining a "same timing" start |

- **Cost:** 1.3-1.7 s per 900-cue track (single thread); 0.04-0.15 s per Sintel/ToS track (26 / 76 cues); in the store run `timeline.cue_align` 0.12-0.15 s for 3 Sintel target tracks. "4 s for 3 tracks x 900 cues on a 45-minute episode" is an extrapolation, not measured.
- **Takeaway:** ranks wander by about sqrt(n x p) = 10+ cues on a long track with splits and merges, so any rank-based pairing fails; matching onsets in time does not. Decision: [B-207](decisions.md#b-207--cue-alignment-fits-one-line-per-track-by-onset-coincidence-then-measures-overlap-on-that-line).

## C-31 · Localization checks on the 2.9A injected Sintel and Tears of Steel: rounds 0, 1 and the W-int re-run

- **Deliverable / source:** 2.4 (`notes/2.4.md`, both rounds), `notes/2.Wint.md` (re-run). 2.9A `--only loc` copies, seeds 1-3, scored by `nip eval run`, MLflow experiment `loc-2.4`; tables from `nip eval compare`. Driver `eval/exp/loc_bench.py` from round 1. Not a formal experiment (agent and self labels; see caveats).

Round 0 (tag `exp=2.4`, runs carry the commit tag of `bd74e53` with uncommitted 2.4 code; superseded and soft-deleted). P / R mean over 3 seeds; counts tp / fp / fn totalled over seeds:

| check | Sintel P / R | Sintel counts | ToS P / R | ToS counts |
|---|---|---|---|---|
| loc.term | 1.00 / 1.00 | 12 / 0 / 0 | 1.00 / 1.00 | 24 / 0 / 0 |
| loc.shot_change (with natives) | 0.95 +- 0.08 / 1.00 | 5 / 2 / 0 (33 native) | 0.99 +- 0.01 / 1.00 | 8 / 2 / 0 (236 native) |
| loc.shot_change (raw) | 0.12 +- 0.03 / 1.00 | 5 / 35 / 0 | 0.03 +- 0.01 / 1.00 | 8 / 238 / 0 |
| loc.drift | 1.00 / 1.00 | 3 / 0 / 0 | 1.00 / 1.00 | 3 / 0 / 0 |
| loc.offset | 1.00 / 1.00 | 3 / 0 / 0 | 1.00 / 1.00 | 3 / 0 / 0 |

Round 1 (tag `exp=2.4r1`, 12 runs, commit tag of `313ccd0`; after the I-1 out-point change):

| check | Sintel P / R | ToS P / R |
|---|---|---|
| loc.term | 1.00 / 1.00 (12 tp) | 1.00 / 1.00 (24 tp) |
| loc.shot_change, raw (the precision) | 0.12 +- 0.04 / 0.83 +- 0.29 (4 tp, 30 fp, 1 fn) | 0.03 +- 0.01 / 1.00 (8 tp, 226 fp, 0 fn) |
| loc.shot_change, regression (clean-copy flags labelled native) | 0.94 +- 0.10 / 0.83 (28 native, 2 fp) | 0.99 +- 0.01 / 1.00 (224 native, 2 fp) |
| loc.drift | 1.00 / 1.00 (3 tp) | 1.00 / 1.00 (3 tp) |
| loc.offset | 1.00 / 1.00 (3 tp) | 1.00 / 1.00 (3 tp) |

W-int re-run of shot_change after the injector fix (tag `exp=wint-sc`, commit tag of `be494b4`, `loc_bench --checks loc.shot_change`):

| loc.shot_change | regression-sintel | raw-sintel | regression-tears-of-steel | raw-tears-of-steel |
|---|---|---|---|---|
| P / R / F1 | 0.94 +- 0.10 / **1.00 +- 0.00** / 0.97 +- 0.05 | 0.14 +- 0.04 / 1.00 / 0.24 +- 0.06 | 0.99 +- 0.01 / 1.00 / 1.00 | 0.03 +- 0.01 / 1.00 / 0.07 +- 0.03 |
| tp / fp per seed | 1.67 / 0.67 | 1.67 / 10.00 | 2.67 / 0.67 | 2.67 / 75.33 |

- **Clean copies:** round 0 Sintel 39, ToS 121 shot_change flags; after I-1 **33** and **115** (unchanged by the W-int re-run); 0 term, drift and offset flags on every clean track. Official tracks of other languages (file-level check): nl/no/ru/it 40-41 shot_change flags each.
- **Sintel recall 1.00 → 0.83 → 1.00:** round 1's single miss was a planted out point 2 frames before a cut, which I-1 made compliant; W-int stopped planting it.
- **Caveats:** drift and offset at 1.00 rest on 3 labels per title and check, all seeds drew 25/24 (+4.169 % Sintel, +4.167 % ToS) and offsets of +-12 frames; other ratios and shifts are unit-tested, not benchmarked; no 24000/1001 film. Every language of the official tracks is timed identically, so alignment is trivially 1:1 and term recall is about the matcher, not alignment quality. Natives are untriaged self-labels; the cuts are EXP-002 detector output. The remaining 2 + 2 regression fps are cues the readability injector edited (4-9 frames from a cut).
- **Takeaway:** term, drift, offset and shot_change recall meet the MVP targets on these sets; shot_change has no honest precision figure (raw 0.12-0.14 / 0.03 is mostly real violations in non-cut-aware official subtitles, per the reviewer). Decisions: [B-214](decisions.md#b-214--native-labels-for-shot_change-come-from-the-clean-run-and-are-a-regression-guard-not-truth), [B-216](decisions.md#b-216--shot_change-passes-an-out-point-at-cut---2--cut-and-flags-points-on-either-side-of-a-cut), [B-217](decisions.md#b-217--the-benchmark-driver-lives-in-evalexploc_benchpy-and-runs-at-a-committed-sha).

## C-32 · OCR backends on Sintel's 398 keyframes: PaddleOCR GPU vs RapidOCR variants

- **Deliverable / source:** 2.6 (`notes/2.6.md` journal 5-9), bench driver `ocr_bench.py` (scratchpad, not committed; review M-10). Laptop, `data/gpu.lock` held, one warm-up call, whole-GPU NVML sampled every 20 ms. Single runs.

| Backend | kf/s | seconds | VRAM peak delta | lines | frames with text |
|---|---:|---:|---|---:|---:|
| **RapidOCR det-GPU / rec-CPU (shipped)** | **1.29** | 309.1 | **1,569 MiB** (589 → 2,158) | 1,607 | 183 |
| RapidOCR CPU only | 0.80 | 499.7 | 7 MiB | 1,610 | 184 |
| RapidOCR with the CPU `onnxruntime` shadowing the GPU build (the bug) | 0.60 (EXHAUSTIVE 0.47) | 666.6 (847.0) | 2,512 MiB | 1,606 | 183 |
| PaddleOCR 3.7.0 GPU, PP-OCRv6_medium (rejected: lock conflict) | 5.24 | 75.9 | 1,300 MiB | 1,640 | n/a |

- Mean OCR confidence 0.972 over 1,607 lines; 93 lines below 0.80. GPU vs CPU RapidOCR text differs on 24 of 398 frames (numeric noise). The shipped VRAM delta includes torch's CUDA context (imported only to share its DLLs) and ORT's arena. 2.close later measured 1.11 GiB in the nip image and 1.22 kf/s on its GPU (catalog comment, `progress.md`).
- **Takeaway:** the shipped backend is about 4x slower than Paddle; Paddle cannot share the environment ([B-229](decisions.md#b-229--the-ocr-slot-uses-rapidocr-onnx-runtime-with-pp-ocrv6-medium-the-catalog-id-pp-ocrv6-medium-is-kept)). Whether OCR time matters is left to EXP-008.

## C-33 · ONNX Runtime CUDA detector and recognizer: where each runs

- **Deliverable / source:** 2.6 (`notes/2.6.md` journal 8). 30 Sintel keyframes (100-129). Single runs.

| Setting | det (s) | rec (s) | kf/s |
|---|---:|---:|---:|
| det GPU / rec GPU | 0.7 | 5.3 | n/a |
| det CPU / rec CPU | 6.0 | 0.5 | n/a |
| GPU, `cudnn_conv_algo_search` DEFAULT | | | 0.7 |
| GPU, EXHAUSTIVE (ORT's default, slowest at scale) | | | 1.04 |
| GPU, rec batches padded to multiples of 160 px | | 5.9-6.5 | |
| **det GPU / rec CPU (shipped, HEURISTIC kept)** | | | **5.89** |

- **Takeaway:** variable line widths give the recognizer new input shapes, so on CUDA it is about 10x slower than on CPU; detection is the other way round. Decision: [B-230](decisions.md#b-230--ocr-detection-on-the-gpu-recognition-on-the-cpu). Cells left empty were not reported separately in the notes.

## C-34 · Plate regexes over three rounds: captions vs real plates

- **Deliverable / source:** 2.6 review, re-review and re-review 2 (`reports/2.6-review.md`, `2.6-rereview.md`, `2.6-rereview2.md`), the reviewers' direct probes of the yaml regexes; `tests/fixtures/clearance/cases.yaml`. Constructed strings, not frames.

| Round | Rule | Real plates | Caption-shaped strings |
|---|---|---|---|
| Initial (`9c3bf5a`) | yaml "upper case", but Presidio's default `IGNORECASE`; US `[A-Z]{3}[ -]?\d{3,4}`, `\d{3}[ -]?[A-Z]{3}`; DE with `[- ]` | match | "MAY 1985", "DEC 2019", "100 MPH", "300 BCE", "BOX 123" match as US; "UP TO 50", "GO TO 5" as DE |
| Fix 1 (`fa95853`) | case-sensitive; spaced US forms dropped; DE needs the hyphen | "ABC 1234", "ABC 123", "123 ABC", "B AB 1234" **missed** (new Important N-1) | listed captions rejected; "MAY-1985", "JAN-2024", "USA-123", "FBI-1234" still match |
| Fix 2 (`3c1a5de`) | one space allowed; named stop-lists in negative lookaheads | **16 / 16** probes match | **26 / 50** still match (e.g. "NYC 2024", "NBA 2023", "ISO 9001", "TOP 100", "500 YDS"; DE "A B 1234", "GET UP 123", "MR X 1999"); stop-listed ones rejected |

- **Takeaway:** shape alone cannot separate a plate from an acronym plus a number; the shipped baseline errs toward extra candidates, which is the safe side for clearance. Precision on real frames is EXP-019's. Decision: [B-238](decisions.md#b-238--plate-patterns-are-case-sensitive-allow-one-space-and-exclude-caption-words-by-name).

## C-35 · Scanner rules on unlogged credits text: shown false positives 95 → 29 and 89 → 24

- **Deliverable / source:** 2.7 (`notes/2.7.md` Precision and Fix round 1 I5; `reports/2.7-review.md` answer 2). EXP-008's `1-per-shot+2s` arm, shown flags, matched with `eval.metrics.match` against the official labels. Seed 1 is the development seed. Not a formal experiment.
- **Problem:** 507 of Sintel's 2,485 and 608 of Tears of Steel's 2,792 candidates came from the 80 to 95 credits keyframes (>= 12 OCR lines), where GLiNER tags names, roles and software as organizations / products at 0.5 to 0.9.

| Scanner (round 0, seed 1) | Sintel shown FP (P) | Tears of Steel shown FP (P) |
|---|---:|---:|
| GLiNER organization/product guesses everywhere (first run) | 95 (0.04) | 89 (0.06) |
| + a person / job-title GLiNER reading removes an overlapping brand or address | 77 (0.05) | 89 (0.06) |
| + a keyframe with >= 8 OCR lines is a credits card: no GLiNER guesses in it | 29 (0.12) | 24 (0.20) |
| + a brand span needs 3 letters | (in the 3-seed numbers below) | |

| Stage (3 seeds, current policy) | P injected-only | P `+native` | R |
|---|---:|---:|---:|
| Round 0 (rules above) | 0.17 ± 0.01 | n/a | 1.00 |
| Fix round 1 (own title / bible names, credit words, title-case NER, OCR >= 0.8, 13 natives) | 0.21 | 0.46 | 1.00 |
| Fix round 2 (log first; 12 natives) | 0.21 ± 0.01 | 0.44 ± 0.01 | 1.00 |

- **Round-0 FP breakdown** (153 shown FPs over 6 film-seeds): 143 original-film text (credits, title cards, sponsor logos, real URLs), 10 overlap an injected window, 0 negatives flagged.
- **The reviewer's re-score of seed 1** (round 0: 61 shown, 10 matched, 51 FP): `clr.url` 16 FP, nearly all real third-party URLs in the credits (true `unknown` detections by architecture.md's rule); `clr.brand_text` 35 FP, mostly genuine errors (credit roles, person names the filter missed, the films' own titles, OCR junk) with a minority of real organizations.
- **Fix-round-1 measurement on seeds 2 to 3 only:** recall 1.00 ± 0.00, precision 0.21 ± 0.00 (41 FP), url 0.16, brand_text 0.07.
- **Dense-card rule cost** (`exp008_keyframes dense-cost --seed 2`, same OCR lines, with and without the rule): Sintel 3 keyframes with 8 to 11 lines and 95 with 12+, the rule removes 14 and 424 GLiNER address/brand candidates; Tears of Steel 10 and 81 frames, 13 and 496 removed. The notes state every one of the 21 frames with 8 to 11 lines is a credits or sponsor card. No in-scene text-heavy keyframe exists in these films, so the rule's recall cost on a newsstand or storefront row is **not measurable** here.
- **What is left as FP after fix round 2 (28 per the notes):** real organizations in credits and sponsor cards (Blender Foundation, Netherlands Film Fund, City of Amsterdam, Google, Ford), a few person names the NER missed, OCR junk (EFRO, ROBOT HAND, PLAYBACK, MANGO). `clr.brand_text` P stays 0.07 ± 0.03; `clr.url` P 0.12 ± 0.06 injected-only, 0.78 ± 0.01 with natives.
- **Takeaway:** the remaining FPs are mostly real text the clearance log does not know; whether a legal reviewer wants "Dell Computers" or "blender.org" from the credits as unknown items is a product call. The rules are generic in kind but were written while looking at seed-1 flags, so the gains are not shown to generalise. Decisions: [B-253](decisions.md#b-253--credits-and-title-cards-give-no-gliner-brand-or-address-guesses), [B-254](decisions.md#b-254--credits-urls-are-correct-unknown-flags-precision-is-reported-against-injected-labels-only-junk-is-dropped-by-rule).

## C-36 · Claim span for an occurrence: shot span vs keyframe cell vs occurrence range

- **Deliverable / source:** 2.7 (`notes/2.7.md` Problem 1 and Fix round 1 I4; `reports/2.7-report.md` Deviations; `reports/2.7-review.md` answer 3). Labels are 72 to 96 frames (3 to 4 s); eval matching needs IoU >= 0.3 between a non-context evidence's frames and the label's.
- **Shot length containing a labelled item (seed 1):** Sintel 4.1, 14.8, 24.0, 10.8, 7.0, 8.3, 3.5 (positives) and 12.3 s; Tears of Steel 15.2, 3.5, 5.5, 5.0, 7.9, 9.7, 20.8, 3.8 s. A 12 s shot against a 3.3 s label is IoU 0.28.

| Claim | Shown recall (32 labels, current policy) | Problem |
|---|---|---|
| Shot span(s) (brief) | capped at 20/32 (report) | long shots dilute IoU below 0.3 |
| Keyframe cell, capped at 4 s (round 0) | 1.00 | width tuned to the injector: a label > about 13.3 s can never match; differs from the CSV's range; stored `kf` ranges break re-verification |
| Occurrence range as `clr/occ-` span (fix round 1, controller ruling) | 1.00 ± 0.00 (1 per shot 0.50 ± 0.12) | a fresh `load_timeline` lacks the span (re-verification must run `clearance.ocr` first or resolve `clr/occ-` from the store) |

- A unit test shows a 60 s label against a 4 s occurrence (IoU 0.07) does not match; not measurable on this set (every label is 72 to 96 frames).
- **Takeaway:** the occurrence range keeps recall and makes the flag's claim equal the CSV row; the remaining limit (single-keyframe occurrences are `cell_cap_s` wide) is stated, not tuned. Decisions: [B-247](decisions.md#b-247--a-keyframe-span-stands-for-its-cell-the-flags-claim-is-the-keyframes-superseded-by-b-248) (superseded), [B-248](decisions.md#b-248--the-claim-is-the-occurrences-frame-range-as-a-clrocc-hash-span).

## C-37 · End to end through the store vs the file harness, and the in-cluster GPU run

- **Deliverable / source:** 2.7 (`notes/2.7.md` "2.7 end to end", Fix rounds 1 and 2; `data/exp008/compare-e2e*.md`). Each film and seed ingested as its own show and run through the wired `run_store`; scored with `nip eval run` under MLflow tags `2.7-e2e` (6 film-seeds, CPU models, `CUDA_VISIBLE_DEVICES=-1`) and `2.7-e2e-cluster` (Sintel seed 1, `nip run --in-cluster` in ray-head). Not a formal experiment.

| Run | Flags | Shown P injected-only | P `+native` | R | Shown FP / content h (injected runs) |
|---|---|---:|---:|---:|---:|
| e2e CPU, round 0 | 51 to 57 per run | 0.17 ± 0.01 | n/a | 1.00 ± 0.00 | 113.18 |
| EXP-008 harness, round 0, same flags | | 0.17 ± 0.01 | n/a | 1.00 ± 0.00 | 113.18 |
| e2e CPU, after fix round 2 | 42 to 43 per run | 0.21 ± 0.01 | 0.44 ± 0.01 | 1.00 ± 0.00 | 90.99 (64.36 `+native`) |
| In-cluster, Sintel s1, after fix round 2 | 43 | 0.14 | 0.39 | 1.00 | 97.29 (68.92 `+native`) |

- **Routing:** the 32 pending/denied flags are all `must_review`, the 16 cleared all `suppressed`, 0 hidden ("pending/denied detected but not shown" = 0).
- **Timings:** CPU e2e `clearance.ocr` 561 / 500 / 604 / 319 / 332 / 272 s for 398 / 325 keyframes (0.7 kf/s at the start, machine under load); in-cluster `clearance.ocr` 967 s for 398 keyframes (0.41 kf/s; 2.7 attributed it to OCR on the CPU, which the closeout did not reproduce: [C-52](experiments.md#c-52--rapidocr-in-the-container-cuda-provider-vs-cpu-and-the-041-kfs-that-was-not-reproduced)); llm group load 238.4 s, unload 7.1 s (887 → 7,654 → 491 MiB); `timeline.asr` failed (`libcublas.so.12`), so the run is `completed_with_gaps`.
- **Takeaway:** the stage + store + checks path reproduces the file-level harness exactly on the same flags. The FP-per-hour figures are from injected runs and count unlabelled real credits text; they are not the spec's clean-run noise metric (target <= 10), which is unmeasured. The in-cluster run proved the shipped path end to end, not GPU OCR in the container. Decisions: [B-254](decisions.md#b-254--credits-urls-are-correct-unknown-flags-precision-is-reported-against-injected-labels-only-junk-is-dropped-by-rule), [B-257](decisions.md#b-257--pipelinepy-two-stages-and-the-slot-tables-beyond-the-one-sanctioned-add_stage).

## C-38 · Fingerprint collisions among clr flags: 41 of 109 per seed → 0 of 253

- **Deliverable / source:** 2.7 review I2 (`reports/2.7-review.md`, the reviewer computed `nip.store.runs.fingerprint` over `1-per-shot+2s-s{1,2,3}`) and fix round 1 (`python -m eval.exp.exp008_keyframes collisions`, re-run by the re-reviewer).

| Version | Flags | Distinct fingerprints | Colliding |
|---|---:|---:|---|
| Round 0 (`kf` + `shot` refs only), per seed | 109 | | 41 flags in 17 groups (38 %) |
| Fix round 1 (`clr/occ-<hash>` per occurrence), 3 seeds x 2 films | 253 (43+42+42+42+42+42) | 253 | 0 |

- **Example round-0 collisions:** orange/peach.blender.org; BLENDER FOUNDATION / NETHERLANDS FILM FUND / SINTEL HAS; one group mixed a `must_review` "EFRO" with "City of Amsterdam". A disposition or run diff on one flag would have applied to all of its group.
- **Takeaway:** the implementer had called the collision "rare"; the measurement said 38 %. Decision: [B-249](decisions.md#b-249--each-occurrence-has-its-own-stable-ref-so-r13-fingerprints-separate-distinct-items).

## C-39 · Scene retrieval: vector-only vs hybrid (vector + entity overlap)

- **Deliverable / source:** 2.8 (`notes/2.8.md`, `reports/2.8-report.md`). Synthetic show seed 1 (6 episodes, 150 scenes) with 3 planted setup/payoff pairs; for each payoff scene's query, the rank of its setup scene among the other 149. Command: `NIP_INDEX_REAL=cpu pytest -s tests/integration/test_index_pg.py -k "real or lift"`. Pair order: prop_folder (S01E05 → S01E01), prop_watch (S01E04 → S01E02), prop_lantern (S01E04 → S01E03). Facts are the generator's planted facts, not 2.1's extraction. Not a formal experiment.

| Scoring | folder | watch | lantern | setup in top 5 |
|---|---:|---:|---:|---|
| stub embedder, vector only | 41 | 9 | 79 | 0/3 |
| stub embedder, hybrid w=0.5 | 11 | 3 | 20 | 1/3 |
| qwen3-0.6b, vector only (w=0) | 6 | 2 | 22 | 1/3 |
| qwen3-0.6b, w=0.25 | 3 | 1 | 11 | 2/3 |
| qwen3-0.6b, w=0.5 | 2 | 1 | 6 | 2/3 |
| qwen3-0.6b, w=1.0 (default) | 2 | 1 | 3 | 3/3 |

- **Takeaway:** the structured arm helps on every pair, with the stub and with the real model. Ranks above 1 are other scenes sharing the same prop (obtain, use, destroy scenes), which is correct. The default weight 1.0 was chosen from this sweep on the same 3 pairs, so 3/3 is a tuned, small-sample number; the reviewer added that it partly measures the planted facts. Re-sweep with 2.1's real facts and more pairs. Decision: [B-265](decisions.md#b-265--hybrid-score--cosine--weight-x-idf-weighted-entity-overlap-weight-10).

## C-40 · Scene embedding throughput: CPU vs GPU (qwen3-embedding-0.6b)

- **Deliverable / source:** 2.8 (`notes/2.8.md`; a scratchpad bench script). 150 synthetic scenes = 7,759 tokens (mean 51.7, max 69 tokens per scene); 3 runs after a warm-up, best shown; model load 14.9 to 21.3 s. The CPU runs were taken while other agents were using the CPU; the GPU runs held `data/gpu.lock`. Not a formal experiment.

| Device | Batch | Best | Scenes/s | Tokens/s |
|---|---:|---:|---:|---:|
| CPU (fp32) | 16 | 26.04 s | 5.8 | 298 |
| CPU (fp32) | 32 | 24.93 s | 6.0 | 311 |
| RTX 4060 Laptop (fp16) | 16 | 0.62 s | 242.5 | 12,544 |
| RTX 4060 Laptop (fp16) | 32 | 0.53 s | 280.8 | 14,524 |

- Peak GPU memory allocated 1.42 GiB (catalog: 1.6). End to end `index_scenes` for the 150 scenes on CPU (embedding plus DB writes): 25.1 s.
- **Takeaway:** the GPU is about 42 to 47x faster (the notes' figure), but on the 8 GB laptop it is shared with vLLM and a 1.6 GiB actor does not fit beside a resident LLM; CPU stays the in-process default. The per-episode (about a minute) and per-season (about 10 minutes) CPU times in the notes are extrapolations from an assumed 60 scenes x 300 tokens, not measurements. Decision: [B-266](decisions.md#b-266--cpu-is-the-in-process-embedding-default-the-serve-actor-uses-cuda).

## C-41 · Low-motion threshold for clearance overlay windows

- **Deliverable / source:** 2.9A, `notes/2.9A.md` (Measured, Tried → switched). Sintel decoded at 48x27 gray; still stretch = consecutive frames whose mean frame-to-frame difference stays under the threshold. Exploratory runs before the injector existed; not a formal experiment.

| Threshold (gray levels) | Sintel runs ≥ 72 frames (incl. runs from frame 0) |
|---:|---:|
| 0.5 | 28 |
| 1.0 | 39 |
| 2.0 | 48 |
| 3.0 | 53 |

| Shipped setting: threshold 1.0, ≥ 84 frames, stretch from frame 0 dropped | Sintel (1080p) | Tears of Steel (720p) |
|---|---:|---:|
| Still stretches | 21 (3,343 frames) | 11 (1,290 frames) |
| Scan decode time | 21 to 23 s | 5.8 s |
| Items rendered (positives / negatives) | 12 (8 / 4) | 11 (8 / 3; capped by the 11 stretches) |
| Clearance labels (cleared items and negatives unlabelled) | 4 | 6 |

- **Takeaway:** 1.0 was chosen so a window cannot straddle a cut (a cut makes the difference large), which removes the need for cached shots per title; ToS has few still stretches, which caps its rendered items at 11. The overlay plate makes OCR easier than real signage, so recall measured on these items is an upper bound ([B-272](decisions.md#b-272--clearance-text-is-an-overlay-plate-over-a-still-stretch)).

## C-42 · Phone positives: NANP expansion area codes vs 555 numbers outside the fiction range

- **Deliverable / source:** 2.9A review I1b (`reports/2.9A-review.md`, reviewer's own `phonenumbers` and Presidio checks), re-review (`reports/2.9A-rereview.md`), `notes/2.9A.md` fix round. Not a formal experiment.

| Number | Source of the recipe | `is_possible_number` | `is_valid_number` | Matches at Presidio's default leniency (VALID) |
|---|---|---|---|---|
| (290) 482-7716 | docs: N9X "reserved for expansion" | True | **False** | no |
| (390) 731-2208 | docs: N9X | True | **False** | no |
| (212) 555-0234, (415) 555-2671, (310) 555-0287, (212) 555-0963 | 555 outside 0100-0199 | — | True (each) | yes (valid) |
| 555-0100 / 555-0199 under each `NEG_AREAS` code (negatives) | fiction range | — | True, inside the fiction range | must not be flagged |

- **Takeaway:** the design's own positive recipe produced numbers the project's detector rejects by construction, so one phone positive per film would have been a structural false negative unrelated to OCR. Replaced by valid numbers ([B-273](decisions.md#b-273--phone-positives-must-be-valid-numbers-outside-the-fiction-range)); the doc's NANP-reservation claim was taken from the doc and not re-verified against NANPA by either agent.

## C-43 · Synthetic-show mention truth: template bookkeeping vs scanning every surface

- **Deliverable / source:** 2.9A review I2 (`reports/2.9A-review.md`), fix round (`notes/2.9A.md`), re-review count (`reports/2.9A-rereview.md`); `build(1)`, seed 1.

| Mention records on `build(1)` | Before (template bookkeeping) | After (`find_mentions`) |
|---|---:|---:|
| Total | 483 | **704** |
| Character (names / descriptions / nickname) | characters only, plus Kappa Cola | 473 (463 / 9 / 1) |
| Location | 0 (189 lines unrecorded) | 189 |
| Prop | 0 (24 lines unrecorded) | 24 |
| Brand | Kappa Cola only | 14 |
| Org | 0 (4 lines unrecorded) | 4 |
| "the informant" inside secret descriptions | 4 unrecorded | recorded, all Ada / description |

- **Takeaway:** EXP-020's resolution-accuracy truth now includes the location, prop and org mentions a registry-enum extractor will emit; generated scripts are byte-for-byte unchanged (same random stream). The before-split of the 483 by kind is not in the sources.

## C-44 · `loc.shot_change` recall after the injector stops planting a compliant out point

- **Deliverable / source:** W-int item 4c (2.4 review I-1). `eval/exp/loc_bench.py --checks loc.shot_change`, 3 seeds, MLflow experiment `loc-2.4`, tag `exp=wint-sc`, runs tagged with the injector commit (`be494b4` today). Table from `nip eval compare --exp wint-sc --md --tracking-uri sqlite:///data/mlflow/mlflow.db` (`notes/2.Wint.md` › Experiment results). The reviewer confirmed 12 active `exp=wint-sc` runs, 3 per variant × 4.
- **Change:** the 2.9A injector no longer plants an out point 1 or 2 frames before a cut (2.4 made cut−2 the compliant position). One label changed: Sintel seed 3, cue 16.

| loc.shot_change | regression-sintel | raw-sintel | regression-tears-of-steel | raw-tears-of-steel |
|---|---|---|---|---|
| P / R / F1 | 0.94 ± 0.10 / **1.00 ± 0.00** / 0.97 ± 0.05 | 0.14 ± 0.04 / 1.00 / 0.24 ± 0.06 | 0.99 ± 0.01 / 1.00 / 1.00 | 0.03 ± 0.01 / 1.00 / 0.07 ± 0.03 |
| tp / fp per seed | 1.67 / 0.67 | 1.67 / 10.00 | 2.67 / 0.67 | 2.67 / 75.33 |

- **Before:** Sintel recall 0.83 ± 0.29 in 2.4's round 1 (`2.4r1`, commit `313ccd0`); the miss was the planted compliant cut−2 out point.
- **MLflow runs:** regression-sintel 7769bbc1…, be686985…, 1f57eee2…; raw-sintel 911ea3dd…, b17764ed…, 61df3d92…; regression-tears-of-steel 6cd3c7d2…, b7dfe57a…, 3547e087…; raw-tears-of-steel 21e884f2…, 5675b396…, 7a8a8f9e….
- **Takeaway:** Sintel now meets the MVP recall target (≥ 0.98); Tears of Steel unchanged; clean-copy natives unchanged (Sintel 33, ToS 115). The measured 0.83 was a labelling error in the benchmark, not a check miss. No decision entry: the change is an injector fix ([journal](journal.md#2026-10-16--w-int-cross-deliverable-fixes-raw-events-after-commit-superseded-facts-a-vllm-whitespace-flag-ci-the-shot_change-injector)). The same re-run is tabulated with 2.4's rounds 0 and 1 in [C-31](experiments.md#c-31--localization-checks-on-the-29a-injected-sintel-and-tears-of-steel-rounds-0-1-and-the-w-int-re-run).

## C-45 · vLLM on the rebuilt image (transformers 5.16.1 lock) vs the Phase 1 image smoke

- **Deliverable / source:** W-int image smoke (`notes/2.Wint.md`), compared with the Phase 1 image smoke (`notes/image-smoke.md`, 2026-10-16). n = 1 start each. Not a formal experiment.

| | Phase 1 image smoke | W-int image smoke |
|---|---|---|
| Image size | 24,550,106,451 B (+1.43 GB vs `nip:pre-lock`) | 26,484,426,619 B (+1.93 GB vs `nip:pre-wint`) |
| Build | 66 s (`--no-cache`, warm uv cache) | 98 s (warm uv cache) |
| Packages changed vs previous image | 75 | 46 (transformers 5.20.0 → 5.16.1, huggingface_hub 2.2.0 → 1.33.0, openai 3.31.0 → 3.3.0, …) |
| `pip check` | 6 lines (5 lmcache, 1 nccl) | the same 6 + `faster-whisper requires onnxruntime` (VAD off, so unused) |
| `test_serving.py` in ray-head | 2 passed (263.9 s cold, 137.8 s warm) | 1 failed, 1 skipped; after `ff7b038` 1 passed, 1 skipped (6.73 s) |
| Start setting | stock `--setting plan` (probe → planner → `serving.apps`) | forced EXP-001 `kv-planner` (`--kv-cache-memory-bytes 1006632960`, 8k), planner refused text_llm |
| Load | 85.4 s | 197.7 s (weights 43.56 s) |
| KV | 69,416 tokens (4.24x at 8k) | 21,597 tokens (2.64x at 8k) |
| tok/s (EXP-001 `_bench`, concurrent) | 188.6 | 119.0 |
| Unload | 4.0 s | 4.0 s |
| VRAM idle before → after | 362 → 332 MiB | 1,333 → 1,299 MiB |
| Device peak | 7,824 MiB | 7,692 MiB |

- **Takeaway:** the lock change did not break serving, chat completions or xgrammar guided JSON (PASS). Load 2.3x slower and throughput 0.63x, n = 1, first container on a new image, desktop using the GPU at 8 to 9 %; **not attributed**. The KV rows are not comparable (different settings). Decision: [B-290](decisions.md#b-290--the-vllm-image-smoke-is-re-run-on-the-new-lock-with-a-forced-exact-kv-setting).

## C-46 · End-to-end store runs: cpu stub Plan vs the laptop Plan (real ASR and embedder, no LLM)

- **Deliverable / source:** W-int item 6 (`notes/2.Wint.md` › End-to-end store runs). One run per cell; process walls. Pass B is the re-run with `HF_HOME=models/hf` offline (the first attempt, which downloaded to C:, is discarded).

| Title | Pass A (`NIP_PROFILE=cpu`) | Pass B (laptop Plan) | asr wall A / B | index wall A / B | Flags (both passes) | Lines placed (B) |
|---|---:|---:|---|---|---|---|
| Sintel S01E01 | 17.5 s, 45 units | 44.8 s, 46 units | 13.35 s (stub: download + audio extract) / 28.51 s (incl. 6.1 s download) | 0.03 / 10.58 s | 53 | 23 of 26 (2.5: 24) |
| Tears of Steel S01E01 | 8.5 s, 65 units | 32.3 s, 66 units | 4.08 / 16.98 s (incl. 1.9 s download) | < 0.03 / 9.06 s | 211 | 64 of 76 (2.5: 62) |
| Synthetic S01E01-06 | 7.2 s, 6 × 31 units | 46.4 s, 6 × 31 units | no unit (script-only) | 0.11 (hash stub) / 37.6 s | 19 (all `plot.knowledge_order`, false positives) | n/a |

- **Takeaway:** all three titles run through the store with 0 gaps; flags are identical between passes because no LLM ran in either and the loc checks read cue and shot timing. The pass B index walls are mostly model load. What this does not show: any real-LLM behaviour ([B-292](decisions.md#b-292--a-w-serve-step-before-w2-nip-run-inside-ray-head-with-staged-serving-and-an-hf_home-default)).

## C-47 · Free VRAM seen inside ray-head (NVML, CUDA) vs the host's `nvidia-smi`

- **Deliverable / source:** W-serve brief item 2 (`notes/2.Wserve.md`). Each row: host `nvidia-smi`, then pynvml + `torch.cuda.mem_get_info` in ray-head, then host again.

| Time | Host used / free before (MiB) | Container NVML used / free | Container CUDA free | Host used / free after |
|---|---|---|---|---|
| 17:35:36 | 1099 / 6858 | 1337 / 6850 | 7096 | 1123 / 6834 |
| 17:35:40 | 1123 / 6834 | 1354 / 6833 | 7096 | 1109 / 6848 |
| 17:35:43 | 1109 / 6848 | 1339 / 6848 | 7096 | 1118 / 6839 |

- **Takeaway:** container NVML **free** always falls between the two host readings around it, so it is truthful; container NVML **used** is about 238 MiB higher (it is total − free, which includes ~231 MiB the host lists as neither used nor free); CUDA reports a constant 6.93 GiB, as in EXP-001. The probe plans from NVML free. Decision: [B-297](decisions.md#b-297--a-vram-skip-says-free-vs-needed-from-the-planners-own-formula).

## C-48 · Real-model `nip run --in-cluster` on synthetic S01E01: planner margin 0.5 vs 0.25

- **Deliverable / source:** W-serve demo and fix round (`notes/2.Wserve.md`; `data/wserve/run1.json`, `run2.json`, `run3.json`, `run2-vllm.log`, `vram-poll.log`). qwen3.5-4b-awq, 16k context when placed. VRAM columns are NVML used inside the container; one run per row.

| Run | Margin | Free at probe | Outcome | Wall | Load | VRAM idle → up → after (MiB) | Unload | Extract units | Facts (events / active) | Flags |
|---|---|---|---|---:|---:|---|---:|---|---|---|
| Run 1 (17:36) | 0.5 shipped | 6.70 GiB | text_llm skipped, short 0.05 GiB; `completed_with_gaps` | 39.4 s | — | — | — | skipped | — | plot checks skipped |
| gpu test (17:38) | 0.5 | 6.54 GiB | skipped, short 0.21 GiB | 3.26 s | — | — | — | — | — | — |
| Best poll reading (17:37-18:02) | 0.5 | 6.73 GiB (6,892 MiB) | would skip, short 0.02 GiB | — | — | — | — | — | — | — |
| Run 2 (18:02) | 0.25 monkeypatched | 6.54 GiB | `completed_with_gaps` | 852 s | 254.9 s | 1,495 → 7,585 → 951 | 6.0 s | 23 done, 2 failed | 117 / 112 | 8 (5 / 1 / 2) |
| Run 3 (18:39) | 0.25 via `NIP_VRAM_MARGIN_GB` | 7.10 GiB | `completed_with_gaps` | 774.2 s | 272.0 s | 930 → 7,792 → 597 | 5.0 s | 23 done, 2 failed | 117 / 112 | 8 (5 / 1 / 2) |
| gpu test (18:52) | 0.5 shipped | desktop 388 MiB used, 7,569 free (host) | 1 passed | 629.06 s | 159.3 s | 608 → 7,764 → 561 | 4.0 s | 29 units done, 2 failed (all stages) | — | — |

- **Detail:** run 2 KV 1,889,533,952 B (46,996 tokens, 2.87x at 16k; vLLM weights 41.96 s, engine init 126.0 s), run 3 KV 2,490,368,000 B; extract 559.8 s (run 2) and 459.7 s (run 3); generation one request in flight, 14 to 24 tok/s. Story made 0 LLM asks in both.
- **Takeaway:** the 0.5 margin works when the desktop holds about 1,045 MiB or less; 0.25 covers its usual 1.1 to 1.3 GB, with a device peak of 7,585 to 7,792 of 8,188 MiB. Runs 2 and 3 are identical in facts and flags, so this episode is deterministic at T = 0. Every real run was `completed_with_gaps` because of the 2 runaway scenes. Decision: [B-300](decisions.md#b-300--nip_vram_margin_gb-default-05-the-8-gb-laptop-may-set-025).

## C-49 · Does xgrammar's `disable_any_whitespace` stop the extraction runaway?

- **Deliverable / source:** W-int 4d (flag added), W-serve runs 2 and 3 and the `runaway.py` reproduction (`notes/2.Wserve.md`; `data/wserve/runaway.json`). Hypothesis from 2.1's notes: ~5 % of scenes emit whitespace until max_tokens.

| Evidence | Flag | Scenes at the 2,048-token limit | Detail |
|---|---|---|---|
| 2.1 extraction (notes/2.1.md, as quoted in the ledger) | off | ~5 % | attributed to whitespace |
| W-serve run 2 | on | 2 / 25 (`sc/7`, `sc/25`) | failed units mean 109.4 s |
| W-serve run 3 | on | 2 / 25 (same scenes) | 89.1 s each on average |
| Reproduction, `sc/7` alone | on | fails | 2,048 tokens, 5,747 chars valid JSON; 42 events, 7 distinct; 40 `wearing` at `confidence: 0.0`, one quoted line, cycling subject × object pairs |
| Reproduction, `sc/25` alone | on | passes | 37 events |

- **Takeaway:** **no.** The runaway is an enumeration loop inside a schema-valid, unbounded `events` array, not whitespace; the flag only fixes separators. `sc/25`'s dependence on the preceding scene is the agent's explanation (batch / prefix-cache non-invariance at T = 0), not separately tested. Handed to 2.1B ([B-303](decisions.md#b-303--the-extraction-runaway-and-single-stream-throughput-are-handed-on-not-fixed-in-w-serve)), which measured runaway 8/75 → 0/150 with its guard (2.1B record).

## C-50 · nip image size: the wheel, then the uv cache mount that was never used

- **Deliverable / source:** 2.close, `notes/2.close.md` (Image size), `reports/2.close-report.md`; `docker image` sizes, `du`, `find -newermt` in the image.

| Image | Size (bytes) | `uv pip install` layer | Note |
|---|---:|---:|---|
| Old `nip:dev` (kept as `nip:pre-close`) | 26,484,426,619 | 4.84 GB | wheels duplicated in `/opt/uv/cache` inside the layer |
| + `nvidia-cublas-cu12` + ldconfig (first rebuild, 6 min 43 s) | 28,651,740,906 (+2.17 GB) | 7.01 GB | `dist-packages` grew only 1,033 MB |
| + `UV_CACHE_DIR=/root/.cache/uv UV_LINK_MODE=copy` (shipped) | **25,113,912,896 (−1.37 GB vs old)** | 3.47 GB | CUDA 12 libs +1.03 GB, cache duplication −2.4 GB |

- **Takeaway:** the base image's `UV_CACHE_DIR=/opt/uv/cache` meant the Dockerfile's build-cache mount at `/root/.cache/uv` was never used, so each build stored all wheels a second time in the layer and no build was ever cache-warm. Found only because a +1.03 GB change cost +2.17 GB. `pip freeze` differs by exactly the two added packages ([B-304](decisions.md#b-304--cuda-12-cublas-only-on-ldconfig-and-the-uv-cache-dir-fixed)).

## C-51 · faster-whisper in the container: missing `libcublas.so.12`, scratch fix, shipped image

- **Deliverable / source:** 2.close, `notes/2.close.md` (ASR); in-process in ray-head under `data/gpu.lock`, Sintel audio 888.0 s (16 kHz mono), VRAM = NVML whole-GPU over idle.

| Setup | Variant | Load | Transcribe | RTF | Segments (words) | VRAM over idle |
|---|---|---:|---:|---:|---|---:|
| Old image | turbo int8 | — | — | `RuntimeError: libcublas.so.12 not found` | — | — |
| Old image + scratch `pip --target` cu12 + `LD_LIBRARY_PATH` | turbo int8 | 17.8 s | 25.8 s | 0.029 | 60 (279) | 1,330 MiB |
| Shipped image, run 1 (cold) | turbo int8 | 30.4 s | 17.9 s | **0.0201** | 60 (279) | 1,294 MiB |
| Shipped image, run 2 | turbo int8 | 12.3 s | 16.7 s | **0.0188** | 60 (279) | 1,295 MiB |
| Shipped image | large-v3 int8 | 41.0 s | 24.2 s | 0.0273 | 53 (372) | 2,382 MiB |
| Windows host (EXP-003 shipped config), reference | turbo | | | 0.01 | | 1,321 MiB |

- **Takeaway:** only cuBLAS 12 was missing; no cuDNN is loaded on Linux. Catalog sizes turbo 1.5 / large-v3 3.0 GiB against 1.26 / 2.33 GiB measured over idle (torch not imported). In the full in-cluster run `timeline.asr` took 36.5 s (62 segments) and the run ended `completed` instead of 2.7's `completed_with_gaps`.

## C-52 · RapidOCR in the container: CUDA provider vs CPU, and the 0.41 kf/s that was not reproduced

- **Deliverable / source:** 2.close, `notes/2.close.md` (OCR); all 398 cached Sintel keyframes through `RapidOcrBackend` (det on CUDA, rec on CPU), warm-up frame excluded.

| Container / mode | Wall | Keyframes/s | Lines | VRAM over idle |
|---|---:|---:|---:|---:|
| Old image, `cuda=True` | 357.0 s | **1.11** | 1,607 | 1,147 MiB |
| Old image, `cuda=False` (CPU only) | 717.4 s | 0.55 | 1,610 | 100 MiB |
| New image, `cuda=True` | 325.6 s | **1.22** | 1,607 | 1,141 MiB |
| Windows host, 2.6 (reference) | | 1.29 | | 1,569 MiB (incl. torch's context) |
| `clearance.ocr` stage in the full in-cluster run (new image) | 448.5 s | 0.89 | | |
| Stage scan loop only (OCR + `gliner-x-base`, no DB) | 370 s | 1.08 | (68 candidates) | |
| 2.7's in-cluster run (whole stage, machine loaded) | 967 s | 0.41 | | |

- **Takeaway:** the CUDA provider loaded in the old image already (GPU twice the CPU rate); the "No registered plugin EP device" line is a benign ORT 1.31 warning. 0.41 kf/s was a whole-stage figure under load and could not be reproduced ([B-308](decisions.md#b-308--nothing-changed-in-the-image-for-ocr-the-cpu-fallback-stays)).

## C-53 · `gliner-x-base` vs `gliner-x-large`: size, latency and candidates on Sintel's stored OCR

- **Deliverable / source:** 2.close, `notes/2.close.md` (Catalog); harness on the Windows host (torch imported first, `GlinerBackend(cuda=True)`, 12 OCR-like lines in en/es/fr/de x 5 labels, 5 passes = 60 calls after warm-up, NVML whole-GPU peak over idle); candidates from the stage's `TextScanner` on `clr-sintel-s1-b`'s stored OCR lines (199 keyframes with text, 1,634 lines, `lang=en`).

| Variant | Load | ms/call (mean / median) | VRAM after load | Peak over idle | Catalog before → now |
|---|---:|---:|---:|---:|---|
| gliner-x-base (run 1) | 35.5 s | 35.7 / 35.1 | 1,287 MiB | **1,347 MiB** | 2.3 → **1.4 GiB** (2.6 had measured 22 s, 24 ms, 1,347 MiB) |
| gliner-x-large (run 1) | 46.3 s | 64.8 / 63.6 | 2,505 MiB | **2,578 MiB** | 3.7 (hf-mem estimate) → **2.6 GiB** |
| gliner-x-large (run 2) | 33.7 s | 58.1 / 56.8 | 2,505 MiB | 2,577 MiB | |

| Candidates on Sintel's stored OCR | url | brand_text | address | plate | phone | email | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| base | 27 | 39 | 7 | 2 | 2 | 1 | 78 |
| large | 27 | 28 | 3 | 2 | 2 | 1 | 63 |

- **Overlap:** 63 common, 0 only-large; the 15 only-base candidates are credit-roll names and titles, read as false positives by the agent (not scored). The shipped in-cluster run: 34 flags vs 2.7's 43 (phone 1 / url 11 / email 1 / plate 2 identical).
- **Takeaway:** the hf-mem estimate was high by about 1.2 GiB (3.7 vs 2.52 GiB), so the planner's choice was never a fit problem. This comparison alone did not score recall; that is [C-54](#c-54--ner-ab-on-replayed-ocr-gliner-x-large-vs-gliner-x-base-on-the-exp-008-end-to-end-benchmark).

## C-54 · NER A/B on replayed OCR: `gliner-x-large` vs `gliner-x-base` on the EXP-008 end-to-end benchmark

- **Deliverable / source:** 2.close fix round (review I2), `notes/2.close.md` (I2), `reports/2.close-rereview.md` (reviewer's read of `data/mlflow/mlflow.db`); `eval/exp/exp008_e2e.py` `ocr-lines`, `run-ner --cpu --ner <variant>`, unchanged `score`; MLflow experiment `mvp` (id 10), tag `exp=2.7-e2e`; full table `data/exp008/compare-e2e-ner.md`. **Extends [EXP-008](experiments.md#exp-008--keyframe-density-for-on-screen-text)** (written from 2.7); recorded here as a build-time comparison, not a formal re-run of EXP-008.
- **Setup:** OCR text replayed from each show's stored snapshot (1,390 to 1,634 lines per show) by a stub reader keyed by keyframe image hash, so only `Slot.NER` differs; real `pipeline.run_store` (checks, verification, flags); keyframe policy `1-per-shot+2s`, tag b; 3 seeds x 2 films = 6 shows; GLiNER on the CPU (base 55 to 82 s per show, large 360 to 973 s). **18 finished MLflow runs** of `e2e-ner-*` (variants base, large, `+native` and `@all-positives` views, seeds 1 to 3).

| `nip eval compare --exp 2.7-e2e`, shown flags, 3 seeds | e2e-cpu (published 2.7, base) | e2e-ner-base (replay) | e2e-ner-large |
|---|---|---|---|
| P / R / F1, injected labels only | 0.21 ± 0.01 / 1.00 ± 0.00 / 0.34 ± 0.01 | 0.21 ± 0.01 / 1.00 ± 0.00 / 0.34 ± 0.01 | 0.21 ± 0.01 / 1.00 ± 0.00 / 0.35 ± 0.01 |
| P / R / F1, natives counted correct (`+native`) | 0.44 ± 0.01 / 1.00 / 0.61 ± 0.01 | 0.44 ± 0.01 / 1.00 / 0.61 ± 0.01 | 0.46 ± 0.01 / 1.00 / 0.63 ± 0.01 |
| Shown FP per content-hour | 90.99 | 90.99 | **86.55** |
| Recall per check (address, brand_text, email, phone, plate, url) | all 1.00 | all 1.00 | all 1.00 |
| clr.brand_text P | 0.07 ± 0.03 | 0.07 ± 0.03 | 0.07 ± 0.03 |

| Per seed (re-review, from MLflow) | Seed 1 | Seed 2 | Seed 3 |
|---|---:|---:|---:|
| large shown recall | 1.00 | 1.00 | 1.00 |
| large shown precision | 0.204 | 0.22 | 0.22 |
| base shown recall | 1.00 | 1.00 | 1.00 |
| base shown precision | 0.196 | 0.212 | 0.212 |

| Flags kept per show | sintel s1 | tears s1 | sintel s2 | tears s2 | sintel s3 | tears s3 |
|---|---:|---:|---:|---:|---:|---:|
| base | 43 | 42 | 42 | 42 | 42 | 42 |
| large | 34 | 36 | 33 | 36 | 33 | 36 |

- **Also:** `@all-positives` recall is 0.625 to 0.6875 for both variants (the alternative keyframe policy, identical for both, so it does not bear on base vs large). The reviewer could not read the NER variant back from run outputs (`model_variant` is null in the flags); that only NER differs rests on the code and the differing flag counts.
- **Takeaway:** the controller's bar (recall ≥ base) holds: recall 1.00 in every check and seed for both; large is marginally cleaner (FP/h 90.99 → 86.55, +native P 0.44 → 0.46), its extra drops being credit-roll names neither injections nor natives label. The positives are regex-found (phone, url, email, plate, address, brand), so NER-driven checks are barely exercised: this bounds "no recall loss" and does not show large is better ([B-305](decisions.md#b-305--gliner-x-large-stays-the-planners-pick-on-the-8-gb-laptop-measured-no-pin)). The published 2.7 EXP-008 numbers were produced with base.

## C-55 · vLLM smoke on the new image vs earlier runs

- **Deliverable / source:** 2.close, `notes/2.close.md` (vLLM smoke), `reports/2.close-review.md` M3; `python3 -m eval.exp.exp001_vllm_headroom trial --setting plan --pilot --note close-smoke`, qwen3.5-4b-awq, throwaway file MLflow store. Two trials; not a formal experiment.

| Run | Free VRAM at start | Load | tok/s | KV tokens (x at 8k) | Unload | VRAM after |
|---|---:|---:|---:|---|---:|---:|
| Trial 1 (new image) | 7,587 MiB | 112.4 s | 134.6 | 63,380 (3.87x) | 4.0 s | 496 MiB |
| Trial 2 (new image) | 7,687 MiB | 92.4 s | 165.5 | 65,967 (4.03x) | 4.0 s | 284 MiB |
| Phase 1 image smoke (reference) | | 85.4 s | 188.6 | 69,416 | | |
| EXP-001 `plan` arm (reference) | | | 175 to 176 | | | |

- **Takeaway:** function is proven (start, generate, teardown, return to idle). Throughput 134.6 to 165.5 against 175 to 189 earlier; the agent attributes it to machine noise (EXP-001 noise ±17 to 41 tok/s; the desktop held 500 to 600 MiB at start vs 332 earlier), and trial 1 is below that band. Not investigated; the reviewer's suggested A/B against `nip:pre-close` under the lock was deferred.
