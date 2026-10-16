# Build Log

The living engineering record of how the Netflix Narrative Intelligence Pipeline (`nip`) is actually being built. It sits next to the design spec in [`docs/`](../docs/), which is the original, **read-only** design: that spec says what we planned, this folder says what we did, what we measured, what failed, what replaced it, and where reality differed from the plan.

The point of the record is that every detail can be told credibly later (for example in an interview): what was tried, what did not work as well as expected, what replaced it, with numbers, technique changes and the evidence behind them.

## Files

| File | What it holds | Read it when you want |
|---|---|---|
| [journal.md](journal.md) | Dated, chronological entries (`### YYYY-MM-DD · title`), newest at the bottom, same style as [docs/journal.md](../docs/journal.md). Commands run, measured numbers with their source, what broke and why, "tried X, result, switched to Y" | the story of the build in order |
| [decisions.md](decisions.md) | Numbered build decisions `B-001` onward: context, options considered, choice, consequence, link to the deliverable and commit. Includes the controller's rulings | why something is built the way it is |
| [experiments.md](experiments.md) | Per-experiment entries. Formal experiments (EXP-001 and EXP-002 are in-progress stubs) plus a set of build-time comparisons (`C-001` onward) with real numbers | measurement-backed "X vs Y" stories |
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
- Commit SHAs refer to branch `phase-1` (base `a679f9a`, the design-doc baseline). Nothing has been pushed.
- Source material is the agents' notes, reports, reviews and the controller ledger in the git-ignored workspace `.superpowers/sdd/phased-plan/` (kept, not deleted).

## Phase status

Last updated after wave 1 of Phase 1 (2026-10-16). Branch `phase-1`.

### Phase 1 (Weeks 1 to 2): Foundation

| Deliverable | What | Status | Commits | Review |
|---|---|---|---|---|
| 1.1 | Scaffolding, CI, contracts v1, schema v1 + migrations | **Done** | `7ce7da1`, `c1a8853` | 1 Important, fixed |
| 1.2 | Timecode library | **Done** | `f6390db` | clean |
| 1.3 | Parsers + validation | **Done** | `7e5c20a`, `abd1108`, `056655d`, `993e381` | 2 Important, fixed |
| 1.4 | Script-estimate timeline, flag emission, report JSON | **Done** | `172e19e` | clean (4 minors) |
| 1.5 | `compose.yaml`, nip and MLflow images, API skeleton, Keycloak | **Done** | `1d1b9f9`, `56cc74b` | 4 Important, fixed |
| 1.6 | Hardware probe, model catalog, planner v1 | **Done** | `28e859f`, `3cf18c7` | 2 Important, fixed |
| 1.7 | Ray Serve deployments, stub backends (with EXP-001) | In progress | none yet | not covered here |
| 1.8 | Media probe, TorchCodec, TransNetV2, keyframes | Part A **done**; part B (real film, EXP-002) in progress | `829a3b3`, `72a7ea5` | 3 Important, fixed (part A) |
| 1.9 | Corpus manifest + downloader, injector skeleton, Label Studio cut labelling | **Done** | `d4cb1c2`, `dab96fc` | 4 Important, fixed |
| 1.10 | Walking skeleton: `loc.readability` end to end | Not started (waits on 1.7 and 1.8B) | none | n/a |
| 1.11 | Eval metrics, MLflow logging, `nip eval run` / `compare` | **Done** | `a329f4a`, `159b005` | 2 Important, fixed |
| EXP-001 | vLLM memory headroom on the laptop | In progress (see [experiments.md](experiments.md#exp-001--vllm-memory-headroom-on-the-laptop)) | | |
| EXP-002 | Shot detection: TransNetV2 vs PySceneDetect | In progress (see [experiments.md](experiments.md#exp-002--shot-detection-transnetv2-vs-pyscenedetect)) | | |

Open integration work after wave 1: wiring each deliverable's Typer sub-app into `src/nip/cli.py` ([B-067](decisions.md#b-067--cli-wiring-is-a-separate-integration-step)).

Headline facts from wave 1 (details in the journal): free VRAM on the laptop with desktop apps open is 6.13 GB, which leaves the planner with no LLM; the test films are 24 fps, not 23.976; MLflow idle memory went from 2.223 GiB to 364 MiB; TorchCodec decode went from 92.9 to 433.0 fps with `num_ffmpeg_threads=0`; 18 Important review findings (0 Critical) were all fixed and re-reviewed.

### Phases 2 to 4

| Phase | Weeks | Status |
|---|---|---|
| 2 Knowledge + deterministic checks | 3 to 4 | Not started |
| 3 Vision + LLM checks | 5 to 6 | Not started |
| 4 Review, scale-out, hardening | 7 to 8 | Not started |
