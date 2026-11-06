# Build Experiments

Per-experiment record, alongside the design's planned experiments in [docs/experiments.md](../docs/experiments.md) (read-only). Two kinds of entries live here:

1. **Formal experiments** (`EXP-xxx`), written to the design's rules: one variable, numbers only from `nip eval compare` output, results reported for the Plan they were measured on. Both Phase 1 experiments have been run. EXP-001 is done; EXP-002 is partly run and its result is provisional (agent-made labels, Sintel only). Each entry below states what was measured, where the evidence is, and what changed in the code because of it.
2. **Build-time comparisons** (`C-xxx`): small "tried X, measured, switched to Y" comparisons made while building Phase 1 deliverables. They are not formal experiments (single runs, no seed sweep, synthetic data where stated) and they are labelled that way, but every number is a real measurement with its source. They are the raw material for interview stories about measurement-driven changes.

Related: [decisions.md](decisions.md) · [journal.md](journal.md) · [doc-corrections.md](doc-corrections.md).

## Index

| ID | Question | Phase | Status | Result | Decision |
|----|----------|:-----:|--------|--------|----------|
| [EXP-001](#exp-001--vllm-memory-headroom-on-the-laptop) | vLLM memory headroom on the laptop | 1 | done | gmu 0.75/0.83 start 0/3 under Windows VRAM pressure, 0.86 3/3 at 1.52 seqs, exact KV 3/3 at 2.64 seqs; idle: all 10/10 | [B-083](decisions.md#b-083--exact-kv-budgets-on-single-gpu-engines-sized-by-the-planner-from-probed-free-vram) (controller ruling: exact KV, against the written bar) |
| [EXP-002](#exp-002--shot-detection-transnetv2-vs-pyscenedetect) | Shot detection: TransNetV2 vs PySceneDetect | 1 | partly run (Sintel, agent labels) | F1 0.917 / 0.839 / 0.880 at defaults; verdict flips with tuning (TransNetV2 +0.037 at defaults, Adaptive +0.021 tuned and +0.016 held out) | [B-093](decisions.md#b-093--exp-002-decision-keep-transnetv2-provisionally-as-a-costrisk-call-not-a-result) (provisional) |
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
