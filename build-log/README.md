# Build Log

The living engineering record of how the Netflix Narrative Intelligence Pipeline (`nip`) is actually being built. It sits next to the design spec in [`docs/`](../docs/), which is the original, **read-only** design: that spec says what we planned, this folder says what we did, what we measured, what failed, what replaced it, and where reality differed from the plan.

The point of the record is that every detail can be told credibly later (for example in an interview): what was tried, what did not work as well as expected, what replaced it, with numbers, technique changes and the evidence behind them.

## Files

| File | What it holds | Read it when you want |
|---|---|---|
| [journal.md](journal.md) | Dated, chronological entries (`### YYYY-MM-DD · title`), newest at the bottom, same style as [docs/journal.md](../docs/journal.md). Commands run, measured numbers with their source, what broke and why, "tried X, result, switched to Y" | the story of the build in order |
| [decisions.md](decisions.md) | Numbered build decisions `B-001` to `B-121`: context, options considered, choice, consequence, link to the deliverable and commit. Includes the controller's rulings | why something is built the way it is |
| [experiments.md](experiments.md) | Per-experiment entries. Formal experiments (EXP-001 done; EXP-002 partly run, result provisional) plus a set of build-time comparisons (`C-001` to `C-019`) with real numbers | measurement-backed "X vs Y" stories |
| [doc-corrections.md](doc-corrections.md) | Every place the implemented system or measured reality differs from `docs/*.md`: file and section, what the docs say, what is true, evidence | what in the design spec is now stale or wrong |
| [review-findings.md](review-findings.md) | Per deliverable: what the independent code review found (Critical, Important, Minor), how it was fixed, and the deferred minors | "the review caught X, we fixed it by Y" |

## How the files relate

- A **journal** entry tells what happened and links to the **decision** (`B-xxx`) it produced and to the **experiment** or build-time comparison (`C-xxx`) that measured it.
- A **decision** links back to the journal entry that holds its evidence, and to the commit where it landed.
- A **doc correction** exists because of a decision or a measurement; its Evidence column names the notes file or review it came from.
- A **review finding** links to the decision or journal entry that records the fix.
- The design's own decisions (`D-xxx`) and planned experiments (`EXP-xxx`) stay in `docs/`; build decisions are `B-xxx` so the two never collide. Build-time comparisons are `C-xxx` and are explicitly not formal experiments.

## Rules this folder follows

- `docs/` is never edited, moved or deleted. Corrections are collected here instead.
- Numbers are exactly as measured, with their source (a notes file, a report, a review or a commit). Nothing is estimated and presented as measured; where a figure is an extrapolation or a hypothesis, the text says so.
- Dates in journal headings are the dates in the implementing agents' notes; the commit date in `git log` can be a day later.
- Commit SHAs for Phase 1 refer to the local branch `phase-1` (base `a679f9a`, the design-doc baseline), which is not pushed; the same commits carry other SHAs on `origin/phase-2`. Phase 2 SHAs refer to `phase-2`, pushed to origin on 2026-11-06 after its commit messages were rewritten once ([B-127](decisions.md#b-127--phase-2s-commit-messages-were-rewritten-once-before-the-first-push-to-drop-claude-co-author-trailers)).
- Source material is the agents' notes, reports, reviews and the controller ledger in the git-ignored workspace `.superpowers/sdd/phased-plan/` (kept, not deleted).

## Phase status

Last updated at the end of Phase 1 (2026-10-16). Branch `phase-1`, head `09c87f8` (the closeout) before this log's own commit. Nothing is pushed.

### Phase 1 (Weeks 1 to 2): Foundation: **complete**, exit criteria PASS with caveats

| Deliverable | What | Status | Commits | Review |
|---|---|---|---|---|
| 1.1 | Scaffolding, CI, contracts v1, schema v1 + migrations | **Done** | `7ce7da1`, `c1a8853` | 1 Important, fixed |
| 1.2 | Timecode library | **Done** | `f6390db` | clean |
| 1.3 | Parsers + validation | **Done** | `7e5c20a`, `abd1108`, `056655d`, `993e381` | 2 Important, fixed |
| 1.4 | Script-estimate timeline, flag emission, report JSON | **Done** | `172e19e` | clean (4 minors) |
| 1.5 | `compose.yaml`, nip and MLflow images, API skeleton, Keycloak | **Done** | `1d1b9f9`, `56cc74b` | 4 Important, fixed |
| 1.6 | Hardware probe, model catalog, planner v1 | **Done** | `28e859f`, `3cf18c7` | 2 Important, fixed |
| 1.7 | Ray Serve deployments, LLM client + stubs, EXP-001 | **Done** | `f35045e`, `33fe525`, `989e0ed` (EXP files in `6854081`) | 2 Important, fixed |
| 1.8 | Media probe, TorchCodec, TransNetV2, keyframes; real-film run and EXP-002 | **Done** (part B's EXP-002 result is provisional) | `829a3b3`, `72a7ea5`; `6854081`, `be9daac` | 3 Important (A), 3 Important (B), fixed |
| 1.9 | Corpus manifest + downloader, injector skeleton, Label Studio cut labelling | **Done** | `d4cb1c2`, `dab96fc` | 4 Important, fixed |
| 1.10 | Walking skeleton: `loc.readability` end to end, verification, `nip run` | **Done** | `77257b6`, `2d0bf6a` | clean (7 minors, 3 fixed) |
| 1.11 | Eval metrics, MLflow logging, `nip eval run` / `compare` | **Done** | `a329f4a`, `159b005` | 2 Important, fixed |
| Closeout | Load-bearing minors (KV unit, KV budget > 0, `init: true`, timecode strictness, ...) and exit-criteria verification | **Done** | `09c87f8` | n/a |
| EXP-001 | vLLM memory headroom on the laptop | **Done** (see [experiments.md](experiments.md#exp-001--vllm-memory-headroom-on-the-laptop)) | | decision: exact KV budgets ([B-083](decisions.md#b-083--exact-kv-budgets-on-single-gpu-engines-sized-by-the-planner-from-probed-free-vram)) |
| EXP-002 | Shot detection: TransNetV2 vs PySceneDetect | **Partly run, provisional** (see [experiments.md](experiments.md#exp-002--shot-detection-transnetv2-vs-pyscenedetect)) | | decision: keep TransNetV2 as a cost/risk call ([B-093](decisions.md#b-093--exp-002-decision-keep-transnetv2-provisionally-as-a-costrisk-call-not-a-result)) |

Review totals across all eleven deliverables: **0 Critical, 23 Important (all fixed and re-reviewed), 91 Minor** (the load-bearing ones fixed, the rest deferred and listed in [review-findings.md](review-findings.md)).

**Exit criteria** (docs/phased-plan.md; verified by running the commands against `09c87f8`, details in the [journal](journal.md#2026-10-16--phase-1-exit-criteria-verified-against-09c87f8)):

| # | Criterion | Result | Caveat |
|---|---|---|---|
| 1 | Corpus film + script + Spanish subs ingest into a timeline with shots and keyframes | **PASS** | Sintel: 2 script-estimate scenes (first-minute script only), 162 shots, 398 keyframes, 52 cues; the picture stage was reused from the cached 1.8B run, not re-run live; probe says 21,313 frames, decoder 21,312 |
| 2 | `loc.readability` flags in report JSON with resolvable evidence | **PASS** | 6 flags, evidence 11/11 resolved; evidence is in `flags.jsonl` next to `report.json` by design |
| 3 | Planner expected Plan for 1x8 GB, 1x48 GB, 8x80 GB, table-driven | **PASS** | 6 table cases + 5 KV-byte cases |
| 4 | CI green without a GPU | **PASS (locally)** | 304 passed, 1 skipped; migration test 1 passed; the GitHub Actions workflow itself was not run |
| 5 | Experiment entries complete and journal up to date | **PASS with caveats** | EXP-002's decision is provisional (agent labels, Sintel only); the journal half is closed by this log |
| 6 | `nip --help` lists all sub-apps; `nip plan` on the real probe | **PASS with findings** | `nip doctor`, `models`, `ingest`, `eval inject` documented but not wired (not Phase 1 deliverables) |

Open at the end of Phase 1: human verification of the Sintel cut labels and Tears of Steel labels (EXP-002); lowering `timeline.shots.threshold` to 0.2 (proposed, not applied); the stale-probe risk of exact KV budgets until Phase 4's OOM amendment; Sintel 21,313 vs 21,312 frames; Cosmos Laundromat license (CC-BY-4.0 vs 3.0); the seconv-lint oracle (the 1.00 walking-skeleton score is circular); Phase 2 must add `nip run --show/--episodes` backed by the store.

Headline facts (details in the journal): the laptop's free VRAM is 5.9 to 7.8 GB depending on the Windows desktop, and CUDA inside WSL2 always says 6.93 GiB, so the laptop Plan uses a planner-sized exact KV budget (8k at gmu 0.77 became 16k with 2,170 MiB KV); gmu 0.75 and 0.83 started 0/3 with Windows VRAM in use while exact KV started 13/13; shot detection's verdict flips with threshold tuning (+0.037, then +0.021 the other way, held out +0.016); the test films are 24 fps, not 23.976; MLflow idle memory went from 2.223 GiB to 364 MiB; TorchCodec decode went from 92.9 to 433.0 fps with `num_ffmpeg_threads=0`; the `nip` CLI starts in 1.1 s instead of 10.9 s; 23 Important review findings (0 Critical) were all fixed and re-reviewed.

### Phases 2 to 4

| Phase | Weeks | Status |
|---|---|---|
| 2 Knowledge + deterministic checks | 3 to 4 | Not started (plan with rulings R1 to R15 adopted, [B-120](decisions.md#b-120--phase-2-plan-rulings-r1-to-r15-adopted)) |
| 3 Vision + LLM checks | 5 to 6 | Not started |
| 4 Review, scale-out, hardening | 7 to 8 | Not started |

## Interview highlights

Each bullet is problem, what was tried, the numbers, and what was chosen, with a link to the detailed entry. All numbers are as measured and sourced there.

1. **The vLLM setting that works at idle and fails under load** ([EXP-001](experiments.md#exp-001--vllm-memory-headroom-on-the-laptop), [B-083](decisions.md#b-083--exact-kv-budgets-on-single-gpu-engines-sized-by-the-planner-from-probed-free-vram)). *Problem:* which `gpu_memory_utilization` starts the 4B model reliably on an 8 GB laptop sharing the GPU with Windows. *Tried:* 0.75, 0.80, 0.83, 0.86 and an exact KV budget, 10 trials each, then with 1.5 GiB of Windows VRAM actively held. *Numbers:* all 10/10 at idle (4.36x to 6.86x sequences at 8k); under pressure 0.75 and 0.83 started 0/3, 0.86 3/3 at only 1.52x, exact KV 3/3 at 2.64x. Cause: CUDA inside WSL2 reports a constant 6.93 GiB free, so vLLM's startup check never fails, then vLLM counts Windows' memory as its own (6.15 vs 4.25 GiB) and starves KV. *Chose:* a planner-sized exact KV budget from the host NVML probe; the laptop Plan went from 8k at gmu 0.77 to 16k with 2,170 MiB KV. The written success bar said 0.86; the controller overruled it and the reviewer listed what the evidence did not prove.
2. **A verdict that flips with tuning, on labels I could not get from a human** ([EXP-002](experiments.md#exp-002--shot-detection-transnetv2-vs-pyscenedetect), [B-093](decisions.md#b-093--exp-002-decision-keep-transnetv2-provisionally-as-a-costrisk-call-not-a-result)). *Problem:* is TransNetV2 worth a model over PySceneDetect? *Numbers:* at defaults TransNetV2 F1 0.917 vs Adaptive 0.880 (+0.037, bar met); tuned on the same labels Adaptive 0.967 vs 0.946 (+0.021 the other way); held out by halves 0.944 vs 0.927 (+0.016). Speed 3.3 to 4.4 s per video-minute, no separation. A resize-filter worry was tested and closed (at most 0.007 F1). *Chose:* keep TransNetV2 as a cost/risk call, explicitly not an experiment result, and re-run on human labels. Two rationales that were first written were withdrawn after review because no run supported them.
3. **Making ground truth when nobody can label** ([EXP-002 labels](experiments.md#where-the-labels-came-from-and-how-they-are-biased), [B-092](decisions.md#b-092--provisional-labels-by-candidate-union-and-contact-sheets-with-a-committed-verification-record)). *Tried:* union of three detectors at low thresholds plus a frame-difference scan, 646 events, every one inspected as a contact sheet. *Numbers:* 183 cuts; the labels were found at seeding time by Adaptive 182/183, TransNetV2 179/183, Content 107/183, the scan 0, so recall is capped and the labels flatter the adaptive detector; precision 1.00 partly reflects anchoring. A rate-limit episode produced a blind first draft that was discarded and redone. *Chose:* label them agent-provisional, mask dissolves, ambiguous spots and the end credits (20 windows; the credits alone are 16 % of the film), commit the per-cut verification record, and never claim more than the bias allows.
4. **Finding the zombie only the real run could show** ([C-012](experiments.md#c-012--unload-time-331-s-down-to-40-s-the-zombie-enginecore), [B-087](decisions.md#b-087--stop-always-kills-the-process-group-and-liveness-ignores-zombies)). *Problem:* the review found that `stop()` skipped killing the vLLM process group if the main process had exited, orphaning VRAM. *Fix:* always kill the group. *Real run:* unload took 33.1 s instead of 4 s: the orphan was a zombie under the container's PID 1, which never reaps it, so a liveness probe kept succeeding. *Chose:* read `/proc/*/stat` and ignore state Z; 4.0 s; later `init: true` on ray-head.
5. **Memory and speed problems found by looking, not guessing** ([C-002](experiments.md#c-002--mlflow-idle-memory-workers-and-memory-limit-vs-disabling-the-job-runner), [C-001](experiments.md#c-001--decode-threads-for-torchcodec-1-vs-4-vs-8-vs-auto), [C-013](experiments.md#c-013--nip-cli-startup-109-s-down-to-11-s-lazy-imports)). MLflow used 2.223 GiB idle; the suggested `--workers 1` gave 1,015 MiB; `/proc` showed about 6 `huey_consumer` job-runner processes at about 220 MiB each; turning the job runner off gave **364 MiB**. TorchCodec's default of 1 decode thread: 92.9 fps vs 433.0 with `num_ffmpeg_threads=0` (4.7x). The `nip` CLI took 10.9 s to start because torch (3.94 s) and mlflow (3.84 s) were imported eagerly; lazy imports gave 1.1 s.
6. **A benchmark that scores 1.00 and what it does not mean** ([C-018](experiments.md#c-018--walking-skeleton-benchmark-prf1-100-on-planted-readability-errors-and-why-it-proves-little)). The walking skeleton planted 18 readability errors (3 seeds x 6) in a Spanish track and found all of them with resolvable evidence (P/R/F1 1.00 +- 0.00; 11/11 evidence items on the real run). *But:* the injector and the check read the same rule pack, labels are ref-only, and the native labels are machine-triaged, so it validates plumbing, not rule correctness. *Chose:* disclose it in the report, the notes and the review, and keep the independent seconv-lint oracle as the real check still to build.
7. **The docs were wrong in measurable ways, and the log says where** ([doc-corrections.md](doc-corrections.md), [C-010](experiments.md#c-010--the-24-fps-surprise-is-23976-the-right-rate-for-the-test-films), [C-006](experiments.md#c-006--free-vram-on-the-laptop-idle-doc-vs-desktop-apps-open), [C-017](experiments.md#c-017--kv-cost-per-token-docs-60-hf-mem-128-measured-about-45)). The test films are 24 fps, not 23.976 (so a 25-fps confusion is 4.17 %, not 4.27 %); free VRAM was 6.13 GB with apps open, not the doc's 7.15 GB; KV per token was about 45.8 MiB per 1,024 tokens, against the docs' 60 and hf-mem's 128. Because `docs/` is read-only, every correction is recorded with its evidence instead of silently applied.
8. **Planner decisions driven by measurement, not intuition** ([C-004](experiments.md#c-004--planner-throughput-greedy-literal-vs-refined), [C-005](experiments.md#c-005--independent-judge-vs-judge-reuse-in-throughput-mode), [B-038](decisions.md#b-038--judge-selection-independent-family-else-reuse-and-in-throughput-mode-the-judge-must-not-downgrade-others)). The literal greedy got stuck on a 1 GB shortfall and picked a 9B model; counting only the GiB that help gave the 27B INT4 (rank 65 vs 45). An independent judge in throughput mode cost the text model half its context (8k vs 16k) and the ASR its better variant, because the spec contradicted itself; the controller picked the rule over the example.
9. **Reviews that caught tests that could not fail** ([review-findings.md](review-findings.md)). Across 11 deliverables: 0 Critical, 23 Important, all fixed and re-reviewed. The recurring class: a test or justification that would pass either way (a frame-exactness test that passes with a uniform seek offset; a numbered-PDF test blind to a separate-x number; a CPS test on a 16-character string that proved neither the boundary nor the line-break rule). Each fix included showing the new test fails on the old code. Schema/migration drift (two hand-written copies) is guarded by diffing two real Postgres catalogs, with four injected drifts as proof ([C-009](experiments.md#c-009--ways-to-guard-schemamigration-drift)).
10. **Process under parallel agents** ([journal](journal.md#2026-10-16--process-wave-2-incidents-swept-files-a-rate-limit-edits-under-running-jobs), [B-070](decisions.md#b-070--parallel-agents-on-disjoint-paths-with-path-scoped-commits), [B-121](decisions.md#b-121--commit-by-explicit-file-paths-not-directory-pathspecs)). Several agents shared one checkout and one GPU. Shared-index sweeps happened twice; a pathspec commit fixed staged files, then a directory pathspec swept untracked ones (1.8B's commit contained 1.7's experiment files), so the rule became explicit file paths. A rate limit mid-labelling produced work done without seeing the images; it was discarded rather than patched.

## Source discrepancies resolved in this log

- **Held-out TransNetV2 F1:** the 1.8B report says 0.928; the MLflow runs and the notes give 0.9274 (the two folds are 0.933 and 0.922). This log uses **0.927**.
- **Cut-label labeller value:** the 1.9/1.8B rulings and the wave-1 log said `labeller: agent`; the stored value is `agent-provisional` ([B-089](decisions.md#b-089--cut-labels-use-the-pull-object-format-the-masks-go-in-a-separate-sidecar)).
- **KV per token:** 44.6 MiB per 1,000 tokens in the first calibration, restated as 45.8 per 1,024 tokens in the closeout ([B-115](decisions.md#b-115--kv-calibration-restated-per-1024-tokens-446---458)); the EXP-001 table keeps the original 44.6 to 44.7 as measured.
- **Startup peak attribution:** the first 1.7 notes called the 6.25 GiB peak "profiling" and said exact KV skips profiling; vLLM's source shows it still profiles, so the peak is before KV allocation and about 1.8 GiB of it is unattributed (EXP-001 "Peak attribution").
- **Where the new KV field lives:** the ledger says `Plan.kv_cache_bytes`; the field is `SlotDecision.kv_cache_bytes` ([B-086](decisions.md#b-086--additive-contract-and-catalog-fields-slotdecisionkv_cache_bytes-variantstartup_peak_gb)).
- **EXP-001 bar vs ruling:** by the written bar the laptop calibration is gmu 0.86; the ruling chose exact KV budgets. Both are recorded.
- **Still open, not resolved by any source:** Sintel 21,313 vs 21,312 frames (cause identified by 1.8B, code not changed); Cosmos Laundromat license CC-BY-4.0 vs 3.0.
