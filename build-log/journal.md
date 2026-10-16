# Build Journal

A dated, chronological record of what was built, measured, tried and abandoned while implementing the design in `docs/`. Newest entries are at the bottom. Numbers are measurements or verified facts, with their source named in the entry. Style follows [docs/journal.md](../docs/journal.md).

Related: [decisions.md](decisions.md) (build decisions B-xxx) · [experiments.md](experiments.md) · [doc-corrections.md](doc-corrections.md) · [review-findings.md](review-findings.md).

Dates are the dates written in the implementing agents' notes; the git commit dates (`git log`) can be a day later. Commit SHAs refer to branch `phase-1`, base `a679f9a` (the design-doc baseline). Where a test count is for "the whole repo", it includes other agents' tests that were in the checkout at that moment, so counts are not comparable across deliverables.

---

### 2026-10-15 · Phase 1 starts: one branch, parallel agents, shared checkout

- **What:** Phase 1 (deliverables 1.1 to 1.11, plus EXP-001 and EXP-002) is built on branch `phase-1` from `a679f9a`. Task 1.1 (scaffolding, CI, contracts, schema) runs alone first because every other deliverable consumes its contracts. Wave 1 (1.2, 1.3, 1.5, 1.8 part A, 1.9) is then dispatched in parallel, followed by 1.6 and 1.11 once 1.1 had been reviewed.
- **Preflight scan of shared surfaces** (controller ledger): `src/nip/cli.py` is touched by almost every deliverable, `compose.yaml` by 1.5 and 1.11, corpus media by 1.8 and 1.9, and the docs logs by everyone. Rulings: [B-067](decisions.md#b-067--cli-wiring-is-a-separate-integration-step), [B-068](decisions.md#b-068--compose-ownership-15-owns-composeyaml-including-mlflow), [B-069](decisions.md#b-069--agents-write-notes-a-later-step-merges-them-into-build-log), [B-070](decisions.md#b-070--parallel-agents-on-disjoint-paths-with-path-scoped-commits).
- **Hardware and environment** (from the agents' global brief): RTX 4060 Laptop 8 GB (driver 610.62), Ryzen 7 7840HS, 31 GB RAM, Windows 11, Docker Desktop on WSL2. Python 3.12 through uv (never the system 3.14). Linux-only parts (Ray Serve, vLLM) run in Docker; Windows-side code and tests must work with no GPU and no Docker (the `cpu` profile).

### 2026-10-15 · 1.1 Repo scaffolding: the torch/vLLM version question is closed, and CUDA torch lands on the laptop

- **What:** Checked every doc-pinned version against PyPI before writing `pyproject.toml`: pysubs2 1.9.0, ttconv 1.2.3, screenplay-tools 0.0.10, nvidia-ml-py 13.615.71, torchcodec 0.17.0, scenedetect 0.7.1, ray 2.58.0 and vllm 0.30.0 all exist. Newer releases exist (ray 2.59.0, vllm 0.31.0, scenedetect 0.7.2); the doc pins were kept.
- **Finding:** `vllm 0.30.0` pins `torch==2.13.0` (plus torchvision 0.28.0, torchaudio 2.11.0, `torchcodec>=0.14`). TorchCodec's compatibility table lists 0.12 to 0.17 as accepting torch `>=2.11`, so torch 2.13.0 + torchcodec 0.17.0 is a valid pair. This closes the phased-plan risk row "TorchCodec needs a newer torch than the vLLM image ships": it does not.
- **Result:** The PyTorch cu130 index has `torch-2.13.0+cu130-cp312-cp312-win_amd64.whl`, so the Windows venv gets a CUDA build while Linux resolves the same 2.13.0 from PyPI. `uv lock` resolved 281 packages in 5.0 s (including the Linux-only `serve` extra with ray[serve] + vllm), then 283 after adding `pre-commit-hooks`. Cold `uv sync` took 6 min 29 s, dominated by the torch cu130 download; `.venv` is 3.4 GB. uv used the existing CPython 3.12.10, not the system 3.14. In the venv: `torch 2.13.0+cu130`, `torch.cuda.is_available() = True`, device NVIDIA GeForce RTX 4060 Laptop GPU. (The first cold `import torch` exceeded the 120 s tool timeout and finished in the background; not timed.)
- **Decisions:** [B-001](decisions.md#b-001--torch-and-the-media-stack-are-main-dependencies-torch-pinned-to-vllm-0300s-version) to [B-003](decisions.md#b-003--mlflow-skinny-as-the-client).
- **Source:** `.superpowers/sdd/phased-plan/notes/1.1.md`; commit `7ce7da1`.

### 2026-10-15 · 1.1 Contracts v1 and schema v1

- **What:** Contracts in `src/nip/contracts/`: `flag.py` (Flag, Evidence, Crop, ProducedBy, Verification, Disposition plus enums Agent, Category, CheckId with all 27 check IDs, Tier, FlagStatus, EvidenceKind, EvidenceRole, DispositionAction), `fact.py`, `plan.py` (Plan, StageGroup, SlotDecision, Amendment, Slot, Objective, Mode), `inventory.py` (HardwareInventory, Node, Gpu, Autoscaling) and `_base.py`. Validation enforced in the model: severity 1 to 5, confidence 0 to 1, at least one `claim` evidence item, at least two evidence items for `plot.motivation` / `plot.unresolved_setup`, check-ID prefix must match agent and category, an `overridden` disposition needs a note, half-open ranges must be non-empty, crop box has exactly 4 numbers, unknown fields rejected.
- **Schema v1:** all 26 tables of `docs/data-model.md` as SQLAlchemy Core tables (`src/nip/store/schema.py`) plus a frozen raw-DDL Alembic revision `0001`, both extensions (`vector`, `btree_gist`), 6 GiST indexes and the `fact_consolidated_no_overlap` exclusion constraint. `alembic upgrade head --sql` (offline) renders 27 `CREATE TABLE` statements (26 + `alembic_version`).
- **Integration check:** Against `pgvector/pgvector:0.8.2-pg18` in a throwaway Docker container on 127.0.0.1:55432: `alembic upgrade head` applied cleanly, Alembic's `compare_metadata` (Core tables vs migrated DB) returned 0 differences, `downgrade base` dropped everything. To prove the check has teeth, a column was added to `show` and `episode.season` was changed to Text in memory: `compare_metadata` reported both (`add_column`, `modify_type`).
- **Numbers:** `uv run pytest -m "not gpu and not integration"` gave 21 passed, 1 deselected in 3.56 s; with `NIP_TEST_DATABASE_URL` set, 22 passed in 4.34 s. `ruff check .` clean, strict `mypy` clean on 20 source files.
- **Decisions:** [B-004](decisions.md#b-004--schema-v1-contains-all-26-tables), [B-005](decisions.md#b-005--migration-0001-is-frozen-raw-ddl-schemapy-is-core-drift-is-a-catalog-diff), [B-008](decisions.md#b-008--contract-field-choices-the-docs-left-open).
- **Source:** `notes/1.1.md`, `reports/1.1-report.md`; commit `7ce7da1`.

### 2026-10-15 · 1.1 pre-commit: the remote hook environment crashed pip on Windows, switched to local hooks

- **Tried:** the standard `pre-commit/pre-commit-hooks` v6.0.0 remote repo for end-of-file and trailing-whitespace checks. `pre-commit run` failed twice (also after `pre-commit clean`) while building that hook's virtualenv: pip's build-dependency subprocess exited with code 3221225477 (0xC0000005, access violation) right after installing setuptools 84.0.0.
- **Root cause:** not pinned down; looks environmental (a native crash in pip's isolated build env on this Python 3.12.10).
- **Switched to:** `pre-commit-hooks` as a dev dependency and all four hooks (`end-of-file-fixer`, `trailing-whitespace-fixer`, `ruff check --fix`, `mypy`) as `repo: local, language: system` hooks calling `uv run ...`. All four pass. Side benefit: hook versions now come from `uv.lock`, the same as CI. [B-012](decisions.md#b-012--pre-commit-hooks-are-local-and-not-installed-into-git).
- **Next:** `pre-commit install` was deliberately not run, because an installed git hook would run on every other agent's commit in the shared checkout. Install after the parallel waves.

### 2026-10-15 · 1.2 Timecode library: a failing property test exposed the tie rule

- **What:** Pure, stdlib-only functions in `src/nip/timecode/__init__.py` (about 60 lines): `ms_to_frame`, `frame_to_ms`, `frame_middle_seconds`, `frame_to_smpte(frame, fps, drop=False)`, `smpte_to_frame(tc, fps)`. Frame rates are exact `Fraction` values (for example `Fraction(24000, 1001)`). Drop-frame uses the standard SMPTE algorithm (2 labels skipped per minute at 30000/1001, 4 at 60000/1001, except every 10th minute). The parser picks drop-frame from the `;` separator and rejects dropped labels (`00:01:00;01`), a frame field at or above the nominal rate, and drop-frame at other rates.
- **Tried -> failed -> fixed:** asserted `ms_to_frame(frame_middle_ms) == frame`. It failed: Hypothesis found the counterexample frame 0 at 24000/1001, where the result was frame + 1. Root cause: `round(ms * fps / 1000)` snaps to the nearest frame start, and a frame middle is an exact tie, which half-up rounding resolves to n+1. It is not a bug: the middle is a player seek target and is never fed back into cue conversion. The test now asserts the tie explicitly ([B-015](decisions.md#b-015--half-up-rounding-for-ms-to-frame-conversion)).
- **Numbers:** `uv run pytest tests/unit/timecode -q` gave 10 passed in 2.43 s. Known values asserted: 29.97 drop-frame `00:01:00;02` = frame 1800, `00:10:00;00` = 17982, `01:00:00;00` = 107892; 23.976 `01:00:00:00` = 86400. Hypothesis properties: NDF and DF round-trips over 8 frame rates up to 24 h, DF never emits a dropped label, DF strictly increasing, ms<->frame monotone and exact, frame middle lies inside its frame.
- **Independent check by the reviewer:** iterating 3 h of frames at 29.97 and 59.94 DF, the only discontinuities in the labels are exactly the 162 non-10th-minute boundaries per rate (180 minutes minus 18 tenth-minutes); `10:00;00` falls at frame 17982 and 35964 respectively.
- **Source:** `notes/1.2.md`, `reports/1.2-review.md`; commit `f6390db`.

### 2026-10-15 · 1.1 Fix round: the schema and the migration are two hand-written copies, so CI now diffs the real database catalogs

- **Review finding:** `schema.py` (Core) and migration 0001 (raw DDL) are maintained by hand. CI compared only table names; Alembic's `compare_metadata` skips server defaults, CHECK constraints, identity kind and exclusion constraints.
- **Options considered:** (a) parse column names and types out of the offline SQL in a unit test (needs a DDL parser, still misses constraints); (b) `compare_metadata(compare_server_default=True)` (still blind to CHECK, identity, EXCLUDE); (c) build both schemas in real Postgres and diff the catalogs. Chose (c).
- **Built:** two scratch databases, one from `alembic upgrade head`, one from `metadata.create_all`. The test diffs the catalogs as sets: columns (`format_type`, NOT NULL, default, identity), constraints (name + `pg_get_constraintdef`), indexes (`indexdef`) and extensions. CI runs it against a `pgvector/pgvector:0.8.2-pg18` service in the same job (one `uv sync`).
- **Result:** the first run passed (1 passed in 11.95 s): the two copies already matched, including Postgres-generated constraint names (`show_slug_key`, `flag_severity_check`, `episode_show_id_fkey`). Four drifts were then injected one at a time and each was caught: a changed server default and identity ALWAYS -> BY DEFAULT ("only in migration: columns"), a changed CHECK (`severity BETWEEN 1 AND 6`) and a dropped exclusion constraint ("only in migration: constraints"). Unit suite afterwards: 34 passed, 1 deselected in 6.62 s (includes other agents' tests).
- **Source:** `reports/1.1-report.md`, `reports/1.1-rereview.md`; commit `c1a8853`. See [review-findings.md](review-findings.md#11-scaffolding-ci-contracts-schema).

### 2026-10-15 · 1.3 Ingest parsers: three third-party libraries each had a defect that needed a workaround

Built `src/nip/ingest/` with `common.py` (Issue, `Parsed[T]`, `decode_text`), `script.py` (Fountain via screenplay-tools 0.0.10, own FDX reader), `pdf.py` (own reader on pdfplumber), `subtitles.py` (SRT/VTT via pysubs2 1.9.0, TTML via ttconv 1.2.3), `bible.py` (pyyaml + pydantic), `tables.py` (glossary and clearance log CSVs) and the `parse(fmt, data, kind)` dispatch. No new dependencies. 33 tests in `tests/unit/ingest` (2.8 s warm, 28 s cold when the host was busy).

What broke and what replaced it:

| Problem found | Root cause | Fix |
|---|---|---|
| screenplay-tools turns `FADE IN:` into a bogus scene 1 | its heading regex is `^\s*(INT\|EXT\|...)\|(FADE IN:\s*)`; the second alternative is unanchored | accept a library heading only if forced (`.`) or matching our own anchored INT/EXT/EST/I/E regex; otherwise it becomes a transition (dropped with a warning before the first heading) |
| screenplay-tools mangles boneyards: `/* ... */` followed by a transition gave an action `'/*\nCUT TO:'` and lost the transition | library bug | strip `/*...*/` (DOTALL) before handing text to the library |
| Fountain emphasis (`*x*`, `**x**`, `_x_`) stays in element text | library leaves it | strip with one regex, because quote grounding compares against plain text |
| pysubs2 accepts `00:00:03,000 -> 00:00:04,000` (single-dash arrow) and silently drops a block with no arrow | pysubs2 is lenient; docs require "report malformed cues with line numbers" | own line pre-scan: any timing-looking line that fails the strict regex is an error with its line number; a cue-count mismatch after parsing is also an error |
| ttconv prunes a `<div begin="10s">` that has no `end` when its children's relative end (2 s) is before the div's begin; the cue vanishes with no logged error | ttconv behaviour | not fixed (exotic; Netflix TTML puts timing on `<p>`); the working case (`begin` + `end` on the div) is covered by a test. Recorded as reviewer minor M-1 |
| PDF fixture printed `o'clock` with a typographic apostrophe | Type1 StandardEncoding maps 0x27 to quoteright | fixture font now declares `/Encoding /WinAnsiEncoding` (fixture only) |
| `ruff format` writes CRLF on this Windows host; the repo is LF with `autocrlf=true`; `screenplay.pdf` (pure ASCII, no NUL) could be CRLF-converted and corrupt its xref table | git autocrlf | files normalised to LF; `tests/fixtures/ingest/.gitattributes` marks `*.pdf binary` and `*.srt -text` (the SRT fixture is deliberately CRLF) |

- **TTML timing check:** with `ttp:frameRate="24"` + `ttp:frameRateMultiplier="1000 1001"`, SMPTE `00:00:03:12` gives exactly 7007/2000 s, rounded to 3504 ms (3503.5 ms; error under 0.5 ms against a 41.7 ms frame). `00:00:01:00` gives 1001 ms.
- **Numbers:** 7 modules (excluding `media.py`); the fixture PDF is 1,639 bytes, 2 pages, 3 scenes, generated by `tests/fixtures/ingest/make_screenplay_pdf.py` (hand-written PDF 1.4, Courier, no PDF library).
- **Tooling lesson:** patching regexes containing backslashes through shell heredocs corrupted `\r` and `\1` (double escaping); edits to those lines were made with the editor tools instead.
- **Honest caveat:** PDF reader accuracy is verified only on a synthetic standard-layout fixture, not on real screenplay PDFs.
- **Source:** `notes/1.3.md`; commits `7e5c20a`, `abd1108`. Decisions [B-017](decisions.md#b-017--parse-results-carry-data-errors-and-warnings-parsers-never-raise-on-bad-input) to [B-024](decisions.md#b-024--no-cli-in-the-ingest-deliverable).

### 2026-10-15 · 1.8 part A: TorchCodec on Windows needs shared FFmpeg DLLs, so an LGPL shared build was fetched

- **Tried:** `VideoDecoder("t.mp4")` in the 1.1 venv (torchcodec 0.17.0+cpu wheel, torch 2.13.0+cu130). **Result:** `OSError: Could not load this library: ...\torchcodec\libtorchcodec_core{4,5,...}.dll`. TorchCodec probes FFmpeg majors 8 down to 4 and finds none, because the `ffmpeg` on PATH is gyan.dev's static GPL build with no `avcodec-*.dll`.
- **Switched to:** BtbN `FFmpeg-Builds` asset `ffmpeg-n8.1-latest-win64-lgpl-shared-8.1.zip` (80,983,242 bytes), unzipped to the git-ignored `models/ffmpeg/ffmpeg-n8.1-latest-win64-lgpl-shared-8.1/` (ffmpeg n8.1.3: `avcodec-62.dll`, `avformat-62.dll`, `avutil-60.dll`, `avfilter-11.dll`, `swscale-9.dll`, ...). Its configure line has `--enable-version3` and no `--enable-gpl`, no libx264/x265, so it is LGPL-3.0 (the docs say LGPL-2.1; see [B-025](decisions.md#b-025--lgpl-shared-ffmpeg-81-from-btbn-for-torchcodec-on-windows)).
- **Result:** `os.add_dll_directory(<that>/bin)` before the first TorchCodec use is enough: `VideoDecoder` opens H.264 in `exact` seek mode and `d[0].shape == [3, 360, 640]`, no PATH change. The documented FFmpeg frame-extraction fallback (risk register) was not needed.
- **Gotcha:** the directory must be added before `torchcodec` is imported. In a pytest fixture, importing `VideoDecoder` first and calling the loader afterwards skipped every media test with a misleading "JSON object must be str ... not tuple" error until the order was fixed. `nip.ingest.media.load_ffmpeg()` reads `$NIP_FFMPEG_DIR`, else `<repo>/models/ffmpeg/**/avcodec-*.dll`, and is a no-op off Windows.

### 2026-10-15 · 1.8 part A: shot detection pipeline, decode tuning and measured speeds

- **Pipeline:** `VideoDecoder(exact, NHWC, transforms=[Resize((27,48))])` -> uint8 `[N,27,48,3]` -> `TransNetV2.predict_frames` (weights ship inside the `transnetv2-pytorch` 1.0.5 wheel, no HF download) -> per-frame probabilities -> cuts. TorchCodec's `Resize` runs swscale (bilinear + antialias) inside FFmpeg in the decode threads. The original model was trained on `ffmpeg -s 48x27`, which is bicubic; the effect of the difference is untested and is part of EXP-002.
- **Decode tuning** (1080p H.264 synthetic clip, testsrc2, 2880 frames at 24000/1001, 77.7 MB, `-crf 23 -preset veryfast`; 600-frame timing loop, decode with `Resize` to 27x48):

  | `num_ffmpeg_threads` | decode + resize fps | full-resolution decode fps |
  |---|---:|---:|
  | 1 (TorchCodec default) | 92.9 | 114.2 |
  | 4 | 404.6 | 361.1 |
  | 8 | 452.8 | 491.4 |
  | 0 (auto) | 433.0 | 416.7 |

  One run each, noise roughly +-10%. Switched to `num_ffmpeg_threads=0` ([B-028](decisions.md#b-028--num_ffmpeg_threads0-for-both-decoders)).
- **End to end on that clip** (2880 frames = 120.1 s of video): `small_frames` took 31.22 s = 92.3 fps = 15.6 s per video-minute with 1 thread; with threads=0 it took 12.06 s (first call, 238.9 fps, 6.0 s per video-minute) and 4.73 s (second call, 608 fps, 2.4 s per video-minute; warm file cache). TransNetV2 on the RTX 4060 Laptop: 2.8 s for 2880 frames = 1,030 fps, peak VRAM 198 MB (`torch.cuda.max_memory_allocated`), model load 1.8 s. Keyframes: 58 to 59 full-resolution JPEGs in 1.6 to 3.0 s. `probe()` 0.12 s. Extrapolation, not measured: a 2 h film is roughly 5 to 17 min of decode plus about 2 min of model time. testsrc2 is not film content; real numbers come with part B.
- **Accuracy sanity** on a synthetic 5-shot clip (hard cuts at frames 60, 180, 228, 324 of 424; shots from testsrc2/rgbtestsrc/smptebars/mandelbrot/testsrc; GOP 48 so cuts fall between key frames): TransNetV2 returned cuts exactly at 60, 180, 228, 324 (offset 0; test tolerance +-2). A 1 s `xfade=fade` dissolve over frames 96..119 produced one cut at frame 108 (its middle). These are sanity checks, not an accuracy claim; EXP-002 measures accuracy.
- **Memory ceiling:** all 27x48x3 frames are held in RAM (about 4 KB/frame): about 0.7 GB for a 2 h film.
- **Frame axis truth:** decoder frame count is the truth; `probe().duration_frames` is a cross-check. They agreed (2880/2880 on the 1080p clip, 120/120 in the probe test). See the Sintel 21,312 vs 21,313 discrepancy in the 1.4 entry below.
- **Frame exactness:** a clip whose luma is `mod(N,180)+20`, encoded `-qp 0`: random-access `get_frames_at([100,3,77,119,0,45])` equals the sorted-access batch and luma rises with frame number. The reviewer later showed this test could not detect a uniform seek offset; it was rewritten with an independent oracle (see the 1.8 fix entry).
- **Source:** `notes/1.8.md`, `reports/1.8-report.md`; commit `829a3b3`. Decisions [B-026](decisions.md#b-026--shot-boundary-semantics) to [B-029](decisions.md#b-029--smaller-part-a-choices-on-keyframes-pillow-and-decode-tests).

### 2026-10-15 · 1.11 Eval metrics: assignment instead of greedy matching, and a justification that turned out to be wrong

- **What:** `eval/metrics.py` (label loader, `overlap`, `match`, `score`, `prf`, `evaluate`), `eval/report.py` (report writer, MLflow logging, `run` and `compare` Typer commands), tests `test_metrics.py` (8) and `test_report.py` (3). 11 passed (about 21 to 39 s; the MLflow import and sqlite store creation dominate).
- **Matching:** `scipy.optimize.linear_sum_assignment`, run per (episode, canonical check) block so matrices stay small (exact, because nothing outside a block can match). `test_matching_is_optimal_not_greedy` constructs a case where greedy-by-best-overlap finds 1 match and the assignment finds 2.
- **Tried -> reasoned -> changed before coding it up:** maximising the plain sum of overlap scores lets one high-overlap pair outscore two lower-overlap pairs and lose a match. Switched to scoring each valid pair `1 + overlap`, which maximises match count first and overlap quality second ([B-052](decisions.md#b-052--match-score-is-one-plus-overlap)).
- **MLflow local check:** MLflow 3.17.1 (`mlflow-skinny`) works with a `sqlite:///` tracking URI in the cpu profile. Gotcha: with a sqlite store the default artifact root is `./mlruns` relative to the cwd; the first test run littered `mlruns/` in the repo root. Fixed with an autouse test fixture that chdirs to `tmp_path` (the stray directory, which held only test artifact folders, was deleted).
- **Tracing:** nothing in `eval/` enables MLflow tracing or autologging, so the "tracing only on benchmark runs" rule holds by construction. The LLM-call-traces artifact from docs/evaluation.md is not produced (no pipeline exists in Phase 1).
- **Later found wrong (review I-1, I-2):** equivalence-mapped true positives were booked only under the label's check (inflating `plot.prop_provenance` precision), and a shared ref bypassed the IoU >= 0.3 rule. The original justification ("strictly stricter than IoU, so cannot over-match") was wrong: an extra OR-path can only add matches. Fixed in the 1.11 fix entry.
- **Source:** `notes/1.11.md`; commit `a329f4a`.

### 2026-10-16 · 1.3, 1.11 and 1.8 fix rounds land

- **1.11 (`159b005`):** per-side TP attribution (flag side for precision, label side for recall) and strict IoU for timed labels; context-role evidence is ignored. 13 passed in 60.62 s. Details in [review-findings.md](review-findings.md#111-eval-metrics-and-mlflow-logging).
- **1.3 (`056655d`, `993e381`):** PDF margin no longer shifts when scene numbers sit in the gutter, and TTML cue errors carry `<p>` line numbers. 35 passed, 1 warning in 2.67 s. The old PDF code on the new test page misclassified action as dialogue and dialogue as parenthetical, so the new test fails on the old code and passes on the new.
- **1.8 (`72a7ea5`):** VFR and unknown frame rates are rejected, fps comes exactly from `r_frame_rate`, and the frame-exactness test now uses a lossless ramp clip as an independent oracle. 27 passed (22 s, includes the GPU test); whole cpu profile 165 passed, 6 deselected.
- **Source:** the three `-rereview.md` reports.

### 2026-10-16 · 1.5 Single-node Compose stack: Postgres+pgvector, SeaweedFS, Ray head, API, Keycloak, MLflow

- **Images** (all pinned `tag@sha256:index-digest` except MLflow): `pgvector/pgvector:0.8.2-pg18` (445 MB), `chrislusf/seaweedfs:4.47` (532 MB), `quay.io/keycloak/keycloak:26.6` (474 MB), `ghcr.io/mlflow/mlflow:v3.17.1` (929 MB; version = `mlflow-skinny` in `uv.lock`), `vllm/vllm-openai:v0.30.0` (21.6 GB on disk). Built locally: `nip:dev` (23.1 GB) and `nip-mlflow:dev` (975 MB).
- **Pull and build times:** the vLLM image took 1,168 s wall (19 layers). Small-image pull times were not measured because an earlier attempt's background shell died with its tool call (the retry reported 10 s and 1 s on resumed layers). Lesson: run `docker pull` as a real background task, not `... &` inside a tool call. Builds: `nip-mlflow` 54 s; `nip:dev` 81 s (apt ffmpeg + `uv pip install ray[serve]==2.58.0 .`; uv downloads about 56 s, the Ray wheel alone about 43 s). The image's own torch 2.13.0+cu130 and vLLM 0.30.0 were kept (uv saw them satisfied). In the built image: torch 2.13.0+cu130, torchcodec 0.17.0+cu130, vllm 0.30.0, ray 2.58.0, ffmpeg 6.1.1, Python 3.12.3.
- **Startup:** `docker compose up -d --wait` for the whole stack with warm images: 69 s to everything healthy (Keycloak is the slow one). `ray-head` alone restarts in 14 s warm.
- **Smoke test** (`tests/integration/test_compose_stack.py`, 4 passed in 3.6 s against the live stack): all services healthy; `/readyz` reports postgres, object_storage and ray ok; a Keycloak password-grant token (issuer `http://localhost:8180/realms/nip`, audience `nip-api`, roles viewer/reviewer/legal/operator) is accepted by `GET /api/v1/me` while the API fetched keys from `keycloak:8080` (D-019 verified end to end); `/api/v1/me` without a token is 401. By hand: an MLflow run with an artifact logged and read back through `mlflow:5000` into SeaweedFS bucket `nip-mlflow`. SeaweedFS S3 auth: right keys list the 4 buckets, a wrong secret gives `SignatureDoesNotMatch`, an unknown key gives `InvalidAccessKeyId`. `alembic upgrade head` run from inside the `api` container reached `0001 (head)`.
- **GPU not held:** VRAM used (nvidia-smi) was 1,507 MiB before `up` and 1,515 MiB with the full stack idle; Ray sees `0.0/1.0 GPU`, 6 CPUs, 18.55 GiB memory, 7.95 GiB object store. The roughly 1.5 GB baseline is the Windows desktop, not the stack.
- **Healthchecks:** postgres `pg_isready`; objectstore `wget` on `127.0.0.1:9333/cluster/status`; keycloak raw `/dev/tcp` HTTP on management port 9000 `/health/ready` (the image has no curl or wget); mlflow, api and ray-head use `python urllib` against `/health`, `/healthz`, `/api/gcs_healthz`. `objectstore-init` (one-shot, `weed shell s3.bucket.create` x4) exits 0 and is idempotent.
- **Tests:** `uv run pytest tests/unit/api` gave 14 passed (7 API, 7 static compose checks).

### 2026-10-16 · 1.5 MLflow memory: 2.2 GiB idle down to 0.36 GiB

- **Measured before any change** (`docker stats`, idle): mlflow 2.223 GiB, keycloak 773 MiB, objectstore 130 MiB, postgres 67 MiB.
- **Tried:** `--workers 1` plus `mem_limit: 1g`, as the controller suggested. **Result:** mlflow still at 1,015 MiB / 1 GiB; the cgroup `memory.events max` counter had fired 4,322 times, with no OOM kill. `/proc` showed why: MLflow 3.x's background job runner spawns about 6 `huey_consumer` processes at about 220 MiB RSS each. It is not gunicorn workers.
- **Switched to:** `MLFLOW_SERVER_ENABLE_JOB_EXECUTION=false` (nip uses no MLflow jobs) + `--workers 1` + `mem_limit: 768m`. **Result:** 364 MiB idle, healthy, run and artifact round trip still work. About 6x lower than the original.
- **Final idle RAM, whole stack** (`docker stats`): ray-head 1.133 GiB, keycloak 833 MiB, mlflow 364 MiB, objectstore 155 MiB, api 113 MiB, postgres 35 MiB (about 2.6 GiB total). `mem_limit`s: postgres 1g, objectstore 1g, keycloak 1536m, mlflow 768m, api 2g; ray-head unlimited. Host `vmmemWSL` working set at that moment: 4.7 GB. [B-033](decisions.md#b-033--mlflow-job-runner-off-one-worker-memory-limits).

### 2026-10-16 · 1.5 Things that broke while bringing the stack up

1. **MLflow `ModuleNotFoundError: No module named 'psycopg'`.** The docs say to add `psycopg2-binary`; the image ships SQLAlchemy 2.1.4, which maps a bare `postgresql://` URL to psycopg 3. Fix: install `psycopg[binary]` + `boto3` (the same driver nip uses).
2. **MLflow 403 `Invalid Host header - possible DNS rebinding attack detected`** on `http://mlflow:5000`. MLflow 3.x validates the Host header. Fix: `--allowed-hosts mlflow:5000,localhost:5000,127.0.0.1:5000`.
3. **SeaweedFS healthcheck refused:** `wget localhost:9333` resolves to `::1`, but `weed` binds IPv4 only. Use `127.0.0.1`.
4. **Ray head exited 1 on its first start after the image build:** Ray took 49 s to start (cold 21 GB image, Docker busy) and its client server (port 10001) times out waiting for node info after 50 s, which makes `ray start --block` exit. Warm start is 14 s. Mitigation: `restart: on-failure:3`.
5. One transient Docker Desktop `500 Internal Server Error` from `docker compose up` while the 21 GB image was extracting; a retry worked.

### 2026-10-16 · 1.5 Fix round: four Important review findings, one failed first attempt

- **CRLF on the Postgres init script:** `.gitattributes` with `text eol=lf` for `*.sh`, `*Dockerfile`, `compose.yaml`, `deploy/keycloak/*.json` (no `text=auto` for the rest of the repo).
- **JWT:** `options={"require": ["exp","iat","sub","iss","aud"]}`; every `PyJWTError`/`ValueError`/`TypeError`/`KeyError` becomes a 401; a non-list `roles` claim is a 401. Before, a token without `exp` never expired and a token without `sub` produced a 500.
- **Dev realm opt-in:** **Tried first:** the `KC_IMPORT_REALM` environment variable. **Result:** not honoured by Keycloak 26.6 (realm returned 404 with it set to true). **Switched to:** a bash `entrypoint` that adds `--import-realm` only when `NIP_KEYCLOAK_DEV_REALM=true` (default `false`). Verified on the live stack: `true` gives 200 on `/realms/nip/.well-known/openid-configuration` and the token test passes; `false` gives 404.
- **Error envelope:** new `src/nip/api/errors.py` produces `{"error": {"code","message","details"}}` for 401 `UNAUTHORIZED`, 503 `CLUSTER_UNAVAILABLE` (readyz), Starlette HTTP errors and request validation (400 `VALIDATION_FAILED`).
- **Stale-image lesson:** the first live run exposed a stale `nip:dev` image still returning the old error format. Rebuilt with `docker compose build`; rebuild after API code changes.
- **Numbers:** `uv run pytest tests/integration/test_compose_stack.py tests/unit/api -q` against the live stack gave 28 passed in 5.74 s.
- **Source:** `reports/1.5-report.md`; commit `56cc74b`.

### 2026-10-16 · 1.6 Hardware probe: the laptop has 6.13 GB free, not 7.15

- **What:** `probe_node()` reads GPUs through `pynvml` (nvidia-ml-py 13.615.71): name, total and free memory in GiB (2 decimals), compute capability. CPUs from `os.cpu_count()`, RAM from `sysconf` on Linux or `GlobalMemoryStatusEx` via ctypes on Windows. If `nvmlInit` raises `NVMLError` (no driver, CPU-only CI) the node has no GPUs. Tests use a fake NVML built from the doc's numbers: 8,188 MiB total and 7,321 MiB free come out as 8.0 / 7.15 GB, the same as the doc's probe JSON.
- **Real probe** (Windows host, not Docker): `node_id "Pratham"`, 16 CPUs, 31.2 GB RAM, GPU "NVIDIA GeForce RTX 4060 Laptop GPU", total 8.0 GB, free 6.44 GB, compute capability 8.9, fingerprint `sha256:203f676d41dc386e2e90aa4677b0902162f22a178a26fd63f9d2d37fc08ecb1a`. First call 6.8 s wall (cold `uv run` + imports); a later probe took 0.393 s and read 6.13 GB free. `nvidia-smi` at the same time: 1,466 MiB used, 6,491 MiB free, held by about 40 Windows desktop apps (Edge WebView, Teams, Docker Desktop, Claude, ChatGPT, NVIDIA Overlay, ...; all type C+G, per-process memory N/A).
- **Consequence, measured:** with normal desktop apps open, free VRAM was 6.1 to 6.4 GB, not the 7.15 GB the doc measured at idle. `nip plan` at 6.13 GB free (usable = 6.13 - 0.5 = 5.63 GB) skips `text_llm`, `vlm` and `judge_llm` ("no hardware for ..."): `qwen3.5-4b-awq` at its 8k minimum needs 6.14 GB (4.0 weights + 0.94 KV for 2 sequences + 1.2 overhead) and `ministral-3-3b-fp8` needs 6.51 GB. The overhead and KV figures are estimates; EXP-001 measures the real ones. [B-044](decisions.md#b-044--the-laptop-cannot-plan-an-llm-at-613-gb-free-exp-001-runs-before-the-walking-skeleton).

### 2026-10-16 · 1.6 Model catalog: hf-mem disagrees with the docs' KV figures

- **What:** `config/catalog.yaml` holds 24 variants: 9 Qwen text_llm+vlm, 3 judges (ministral-3-3b-fp8, gemma-4-12b-qat, gemma-4-31b-qat), whisper large-v3 and turbo, pp-ocrv6-medium, llmdet base and large, dinov2-large, qwen3-embedding 0.6b and 8b, gliner-x base and large, transnetv2, and the stub. All defaults are from tech-stack.md.
- **hf-mem 0.5.6** (`hf_mem.run(repo, experimental=True, max_model_len=1024, batch_size=1)`; reads safetensors headers and config.json, downloads no weights; each call took 0.5 to 2.6 s). Results (weights in GiB, KV in MiB per 1,024 tokens at bf16, batch 1):

  | repo | weights GiB | KV MiB/1k |
  |------|------------:|----------:|
  | Qwen/Qwen3.5-4B | 8.68 | 128 |
  | Qwen/Qwen3.5-9B | 17.98 | 128 |
  | Qwen/Qwen3.8-27B | 51.75 | 256 |
  | Qwen/Qwen3.6-35B-A3B | 66.97 | 80 |
  | Qwen/Qwen3.5-122B-A10B | 232.99 | 96 |
  | Qwen/Qwen3.5-397B-A17B | 751.39 | 120 |
  | mistralai/Ministral-3-3B-Instruct-2512 | 4.35 | 52 |
  | google/gemma-4-12B-it | 22.28 | 384 |
  | google/gemma-4-31B-it | 58.25 | 960 |
  | facebook/dinov2-large | 1.13 | n/a |
  | Qwen/Qwen3-Embedding-0.6B | 1.11 | 112 |
  | Qwen/Qwen3-Embedding-8B | 14.10 | 144 |
  | knowledgator/gliner-x-base | 1.84 | n/a |
  | knowledgator/gliner-x-large | 3.22 | n/a |
  | iSEE-Laboratory/llmdet_base | 0.87 | n/a |
  | iSEE-Laboratory/llmdet_large | 1.28 | n/a |
  | RedHatAI/Qwen3.8-27B-INT4 | error: hf-mem refuses `kv_cache_dtype=auto` for compressed-tensors `quantization_config` | |
  | Systran/faster-whisper-large-v3 | error: no safetensors (CTranslate2 `model.bin`) | |

  16 of 18 repos worked. Base-model weights are bf16, so for quantised LLM variants the catalog keeps tech-stack's measured checkpoint sizes and uses hf-mem only for KV.
- **Disagreement with the docs:** Qwen3.5-4B 128 vs 60 MiB/1k in the doc, and Qwen3.8-27B 256 vs 160. These Qwen models mix linear-attention and full-attention layers and hf-mem probably counts every layer as full attention (an assumption, not checked). The catalog keeps the doc's 60 and 160 and uses hf-mem's figures only where the doc gives none. Gemma-4's 960 MiB/1k (31B) looks high for the same reason (sliding-window layers). Calibration (measured peak after first load) replaces all of these.
- **What went wrong:** the first hf-mem run hung for about 5 minutes with no output. The cause was a stray `cat > file` with no stdin blocking before Python started (an own shell mistake). After killing it, every lookup finished in about 2 s.
- **Loader:** variants missing `weights_gb`/`kv_mb_per_1k_tokens` (vllm) or `vram_gb` (actor) get an hf-mem estimate, cached per repo in `$HF_HOME/hf-mem-cache.json`. `hf_mem` is imported only then, and the shipped catalog never needs it (a test asserts this). Tested with a fake estimator: called once per repo, and the second load comes from the cache.

### 2026-10-16 · 1.6 Planner v1: six things tried, each changed after a result

`plan(inventory, catalog, workload, objective, pins, *, stub, gpu_memory_utilization, margin_gb) -> Plan` is pure and deterministic (asserted by calling it twice) and implements every step of hardware-adaptation.md's algorithm. Expected Plans are table-driven in `tests/unit/runtime/test_planner.py` (typical episode workload of 400/200/100/60/600/600/600/120/300/4 units):

| Inventory | Objective | Mode, groups | text_llm + vlm | judge |
|---|---|---|---|---|
| 1x 8 GB (7.15 free) | quality | staged: timeline, vision_prep, text_prep, vlm+llm, judge | qwen3.5-4b-awq, 8k, gmu 0.77 | ministral-3-3b-fp8, 8k (independent) |
| 1x 8 GB | throughput | same (not even the smallest set packs) | same | same |
| 1x 48 GB | quality | staged: timeline+vision_prep+text_prep, vlm+llm, judge | qwen3.8-27b-fp8, 32k, gmu 0.89 | gemma-4-31b-qat, 8k |
| 1x 48 GB | throughput | resident | qwen3.8-27b-int4, 16k | reuses text_llm (after fix round 1; before: ministral-3-3b-fp8 8k with text at 8k and whisper turbo) |
| 8x 80 GB H100 | quality | staged: timeline+vision_prep+text_prep, vlm+llm, judge | qwen3.5-397b-a17b-fp8 tp8, 32k | gemma-4-31b-qat x8 |
| 8x 80 GB H100 | throughput | resident | qwen3.5-397b-a17b-int4 tp4 x1, 32k | gemma-4-31b-qat x4 |

Hand checks against the memory model: laptop text 4.0 + 60*8*2/1024 + 1.2 = 6.14 GiB, and 6.14/8.0 = 0.77. 48 GB text 30 + 160*32*2/1024 + 2.5 = 42.5, within usable min(0.9*47.99, 47.4-0.5) = 43.19. H100 text (403 + 7.5)/8 + 6 = 57.3, so 0.72. 48 GB throughput total 24.5 + 6.51 + 11.7 = 42.71, within 43.19.

Tried -> result -> changed:

1. The shared text_llm+vlm decision was attached to `vlm` because the merged group lists vlm first. Fix: deployment slot lists are sorted in Slot order, so `text_llm` carries the deployment.
2. Replicas were capped only by work units and memory: H100 quality gave 58 to 59 replicas of OCR/detector/DINOv2 on 8 GPUs and the laptop got 2 whisper replicas on one GPU. Changed to at most one replica per deployment per GPU. Now 8 per actor (shot_detector 4, capped by its 4 units) and 1 per actor on the laptop.
3. The literal greedy (smallest quality loss per GiB freed) on 1x 48 GB throughput ended at `qwen3.5-9b-fp8` + ministral. Only about 1 GB was missing, but dropping text_llm to 4b frees 18 GB and so "costs" least per GB; the climb-back then stopped at 9b-fp8. Changed the divisor to the GiB that count, `min(freed, shortfall)` (plain `freed` when the sum fits and packing is the problem). Result: `qwen3.8-27b-int4` (rank 65 instead of 45) with whisper turbo, embedding 0.6b and ministral. The H100 result did not change (the sum fits there; GPU count binds).
4. A greedy that stepped only to the next candidate got stuck, because candidates are ordered by quality, not memory, so the next one can be bigger (27b-int4@8k -> 35b-a3b@32k). Moves may now jump to any lower candidate.
5. The context-reduced warning used the doc's arrow character, which crashed the Windows console (cp1252) with `UnicodeEncodeError`. Switched to `->`.
6. `test_compute_capability_gates_fp8` first used a T4 (15 GB, cc 7.5) expecting gemma-4-12b as judge. The planner correctly gave judge reuse: gemma-12b@8k needs 17.8 GB and ministral is FP8, which needs cc 8.0. The test now uses a 48 GB cc-7.5 card, which gets qwen3.8-27b-int4 where the 48 GB Ada card gets 27b-fp8.

**Numbers:** `uv run pytest tests/unit/runtime` gave 23 passed in 1.63 s (slowest test 0.04 s); whole cpu profile 155 passed, 2 deselected in 75.41 s (includes other agents' tests). `ruff check .` and strict `mypy` (44 files) clean. Commit `28e859f`.

### 2026-10-16 · 1.6 Fix round: judge independence and vlm image caps (controller rulings)

- **I-1, throughput judge:** measured on 1x 48 GB throughput by the reviewer: with judge variants in the catalog, text_llm got `qwen3.8-27b-int4` at 8k and asr got whisper-turbo; with the judge variants removed (reuse), text_llm got 16k and asr got large-v3. So the independent judge cost text_llm half its context and cost asr its better variant. The controller ruled that the judge gets its own engine only if that downgrades no other slot ([B-038](decisions.md#b-038--judge-selection-independent-family-else-reuse-and-in-throughput-mode-the-judge-must-not-downgrade-others)). After the fix: `qwen3.8-27b-int4` 16k (gmu 0.57), whisper large-v3, judge reuses text_llm (`independent_family: false`). The laptop and 8x 80 GB throughput rows are unchanged (on 8x 80 GB, gemma-4-31b still fits after the others are placed: 4 replicas).
- **I-2, vlm caps:** the Plan example in the docs carries `max_pixels: 589824` and `images_per_prompt: 2`, but no rule derives them. Ruling: put the doc's laptop values on all 9 vlm variants in the catalog (overridable per variant) and copy them into the Plan ([B-042](decisions.md#b-042--vlm-image-caps-come-from-the-catalog-589824-px-2-images)).
- **Numbers:** `uv run pytest tests/unit/runtime -q` gave 25 passed in 1.24 s; ruff and mypy (44 files) clean. Commit `3cf18c7`.

### 2026-10-16 · 1.9 Corpus manifest and downloader: four things that broke on the first real downloads

Built `eval/corpus/manifest.yaml` (12 titles; sets `smoke: [sintel]`, `mvp: [sintel, tears-of-steel]`; every title has license, attribution, source URLs, sha256 map, restrictions) and `eval/corpus/downloader.py` (stdlib `urllib`, resumable `.part` download, sha256 verify and record, Typer sub-app `fetch --set|--title [--no-media]`). The checksum is written back by editing only the title's `sha256:` line so the YAML comments survive (a PyYAML dump would drop them).

Real runs (laptop to the RWTH Aachen Blender mirror):
- Sintel 1080p mkv: 1,172,428,172 bytes in 104.4 s (11.2 MB/s). Its md5 `377aa3357df96a9ae085169a74d2a3bf` equals the official `Sintel.2010.1080p.mkv.md5` published on the mirror.
- Sintel first-minute script PDF 20,541 bytes; en/es/fr/de srt 1,514 / 1,554 / 1,618 / 1,652 bytes (0.2 to 0.6 s each).
- Tears of Steel 720p mov: 372,178,639 bytes in 56.2 s (6.6 MB/s); en/es/fr/de/nl/it/ru/no srt 4.5 to 9.9 KB. ffprobe: h264 1280x534, 24/1 fps, 734.17 s.

What broke:
1. `download.blender.org` answered HTTP 403 (a 61 KB HTML page) to every automated request (curl with and without a browser User-Agent), including the URLs named in docs/evaluation.md. Switched to the official mirror `ftp.halifax.rwth-aachen.de/blender/demo/movies/` (listed on the Sintel download page); same bytes (md5 match). The `durian.blender.org/.../subtitles/sintel_*.srt` URLs work unchanged.
2. Tears of Steel `tears_of_steel_1080p.mov` on that mirror is silently a zip archive served under the `.mov` name (the directory index lists only `...1080p.mov.zip`; the plain-name URL returns the same 583,774,281 bytes, magic `PK`). All 583 MB were downloaded (121.3 s) before ffprobe said "moov atom not found". Fix: switched to `tears_of_steel_720p.mov` (a genuine QuickTime file) and added a downloader guard that rejects a download starting with `PK` when the URL does not end in `.zip` (unit-tested). Cost: 121 s, 584 MB, and a wrong sha256 briefly recorded in the manifest (reset and re-recorded before commit).
3. YAML parsed the Norwegian subtitle key `no:` as boolean `False`, producing a file named `False_TOS-no.srt`. Fixed by quoting `"no"`; a test now asserts every asset key is a string.
4. The docs say the Sintel script is `script.zip (CC BY)` on durian.blender.org; no such file exists (404 on every guess; the site's download page links none). The only published script file found is the 2009 "1st minute script" PDF, so the full script is not available.

### 2026-10-16 · 1.9 Sintel and Tears of Steel are exactly 24 fps, not 23.976 (new finding that contradicts the docs)

- `ffprobe` on both downloaded files: `r_frame_rate=24/1`, `avg_frame_rate=24/1`. Sintel has 21,312 frames (888.032 s); Tears of Steel is 734.17 s long.
- The docs (tech-stack.md Build notes, decisions.md D-028, phased-plan.md risk row) and the 1.9 brief describe the Label Studio project as "frame rate 23.976023976", which is correct only for NTSC-rate media.
- **Consequences built in:** the Label Studio config is a template (`{framerate}`); `push` takes the real rate probed with ffprobe (24/1 gives `framerate="24"`); `ls_framerate()` always emits a decimal (24 -> "24", 24000/1001 -> "23.976023976", never "24000/1001"). Anything else that assumes Sintel is 23.976 is wrong, for example the `loc.drift` injector's 25025/24000 rescale (on 24 fps Sintel a 25 fps confusion is 25/24, 4.17%). Frame indexes from TransNetV2 or PySceneDetect at 24 fps are unaffected. [B-048](decisions.md#b-048--label-studio-frame-rate-is-templated-from-the-probed-rate-24-fps-films).

### 2026-10-16 · 1.9 Label Studio cut-labelling project, verified against a real Label Studio 1.23.2 container

- **Design:** unit of work = 60 s clips (1,440 frames) transcoded from the 1080p source to 640-wide all-intra H.264 (`-g 1`, so the browser can seek to every frame exactly), constant frame count (`-fps_mode passthrough`), `-video_track_timescale = fps_num*1000` so pts spacing is exactly 1/24 s or 1001/24000 s. **First attempt** used `24000*1000//1001 = 23976`; ffprobe then reported 2997/125 = 23.976 exactly, i.e. wrong; corrected before any real use. Clips after the first start one frame early (overlap) so a cut on a clip boundary stays visible; LS frame 1 of those clips is ignored on pull. A cut = first frame of the new shot, stored as a 0-based global frame index.
- **Numbers:** Sintel gives 15 clips (frame counts 1440, 13 x 1441, 1153), 116 MB, 50.0 s to produce. Frame mapping check: for global frame 3000, PSNR of the clip's LS-frame-122 against source frames 2999/3000/3001 (scaled to 640 wide) was 31.7 / **38.2** / 32.1 dB, so the offset arithmetic is exact. Burned-in verify clips (`ffmpeg drawtext`, `%{frame_num}`, `start_number=1`) were generated for 24/1 and 24000/1001 (240 frames each, ffprobe r_frame_rate 24/1 and 24000/1001); frame index 99 shows "100".
- **Real Label Studio** (`heartexlabs/label-studio:1.23.2`, throw-away container, removed afterwards): `push` created the project, the local-files storage and 15 tasks; the video is served at `/data/local-files/?d=...` (200 video/mp4, 5.5 MB; 401 without credentials); the browser `<video>` duration of a clip is 60.041667 s = 1441.0 frames at 24 fps. TimelineLabels annotations posted through the API were exported correctly by `pull` (clip 0 frame 35 -> global 34; clip 1 frames {1, 2} -> only 1440).
- **Things that broke:** (a) Label Studio 1.23 rejects legacy tokens ("legacy token authentication has been disabled for this organization"); only Personal Access Tokens work, exchanged at `POST /api/token/refresh` for a Bearer access token; the PAT is shown in full only when created (`GET /api/token` returns it truncated, which cost several debugging round trips). (b) An XML comment containing `--` made the label config "not well-formed". (c) Git Bash rewrote `-e LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=/label-studio/files` into `C:/Program Files/Git/label-studio/files` and Label Studio rejected the path; the README says to use cmd or PowerShell. (d) The first Label Studio start takes about 2 to 3 minutes (DB migrations) before `/health` is UP.
- **Injector framework skeleton:** `eval/injectors/base.py` (pydantic `Label` and `Target`, abstract `Injector.inject(src, dst, seed) -> list[Label]`, deterministic per seed, `REGISTRY`/`@register`/`get`, `write_labels` JSONL) and one example injector `loc.offset.v1` (shifts all cues of an SRT by a seeded constant of -24/-12/12/24/36 frames at 23.976 fps).
- **Tests:** 20 passed in 4.7 s (corpus 7, inject 5, label 8). Commit `d4cb1c2`.

### 2026-10-16 · 1.9 Fix round: four Important findings, one of them hidden by Label Studio's export behaviour

- `push` no longer has an `--fps` option: it probes every clip and the verify clip with `nip.ingest.media.probe` and refuses mixed rates (the old default of 24/1 would silently write wrong ground truth on 23.976 media).
- `pull` now fails on partially labelled projects (prints `n/m clips labelled`, exits 1 unless `--allow-partial`). While verifying against the real Label Studio the implementer found that its JSON export returns only annotated tasks unless `download_all_tasks=true`; without that the new check would have reported `0/0` forever. The export URL now sets it and a test asserts it.
- The verify clip is task 1 of the project, and the README now gives an exact click path, which was exercised in the real UI: task 1 `_verify.mp4`; the counter box `100 of 240` shows burned-in 100; hotkey 1 selects Cut; double-click on the highlighted current-frame strip makes a one-frame mark. A UI-created annotation exported as `ranges:[{start:92,end:92}]`, which confirmed the result shape that the first review listed as unverified.
- Cut labels are documented as a separate JSON file, not Flags ([B-049](decisions.md#b-049--cut-labels-are-a-separate-json-file-not-flags)).
- **Numbers:** 25 passed in 8.5 s (corpus 7, inject 5, label 13). Real LS check: `push` -> "project 1: verify task + 15 clip tasks, fps 24/1"; `pull --allow-partial --labeller agent` -> "1/15 clips labelled", "1 cuts"; `pull` without the flag exited 1. Commit `dab96fc`.

### 2026-10-16 · 1.4 Script-estimate timeline, shared flag emission, report JSON

- **What:** four modules: `src/nip/timeline/estimate.py` (`scene_lines`, `scene_bounds`, `build_timeline`), `src/nip/contracts/timeline.py` (`Span`, `Timeline`), `src/nip/agents/base.py` (`Input`, `WorkUnit`, `Finding`, `Check` ABC, `cue_windows`, `tier_for`, `emit`, `run_check`), `src/nip/contracts/report.py` (`Report` and friends, `summarize`, `build_report`).
- **Estimate math:** each scene is laid out in standard screenplay format (Courier 12 pt; action, heading and transition 60 columns, dialogue 35, parenthetical 25 including the parentheses; one blank line before every block; a character-cue line plus blank at the start of each speech), 55 lines per page, one page = 60,000 ms. Frame boundaries come from cumulative line counts through `nip.timecode.ms_to_frame`, so rounding never accumulates across scenes. Known values in tests: 55 lines = 1440 frames at 24 fps and 1500 at 25; 400 lines at 24000/1001 = 10462 frames.
- **Real-corpus run** (Sintel, script `1stminute_script_11-61.pdf`, 2 PDF pages; media `Sintel.2010.1080p.mkv`; en/es/de/fr SRTs), by a scratch script calling `parse_pdf`, `probe`, `parse_srt` x4, `build_timeline`:
  - probe: fps 24/1 (not 23.976, as 1.9 found), 21,313 frames, start TC 0.
  - parser: 2 scenes (warning: 3 elements before the first heading ignored).
  - estimate: scene 1 = 30 lines, frames [0, 785); scene 2 = 24 lines, frames [785, 1414). Total 54 lines = 0.98 page = **58.9 s**, matching the file's own label "1st minute script".
  - cues: 26 per language; first cue frames [2574, 2652) = 00:01:47:06, last ends 00:10:29:19. The script's estimated minute and the first subtitle are about 48 s apart; nothing in Phase 1 compares them (Phase 2 alignment replaces scene estimates).
  - 106 spans, timeline JSON 18,432 bytes. One warm run: `parse_pdf` 0.220 s, `probe` 0.064 s, 4 SRTs 0.005 s, `build_timeline` 0.0019 s.
- **Frame count discrepancy:** the 1.9 deliverable measured Sintel as 21,312 frames (888.032 s at 24/1), while the 1.4 probe reported 21,313 frames. 888.032 s x 24 = 21,312.77, which rounds to 21,313; the sources do not say which field produced 21,313, but the likely explanation (not verified) is that for MKV `probe().duration_frames` falls back to `round(duration*fps)` when `nb_frames` is absent, exactly the case the 1.8 reviewer flagged as an unchecked cross-check (Minor 3). The decoder frame count is the truth for the frame axis.
- **Tests:** `uv run pytest tests/unit/timeline/test_estimate.py tests/unit/agents tests/unit/contracts -q` gave 49 passed in 1.28 s (30 new: estimate 9, base 14, report 7). Full cpu profile 212 passed, 6 deselected in 81.5 s.
- **Broke along the way:** a `python - <<EOF || uv run python ...` one-liner hung (the system `python` waited on stdin) and hit the 120 s tool timeout; no code impact.
- **Source:** `notes/1.4.md`, `reports/1.4-report.md`; commit `172e19e`. Decisions [B-057](decisions.md#b-057--the-timeline-read-model-is-a-new-contract-in-nipcontractstimeline) to [B-065](decisions.md#b-065--report-ranking-sections-in-consequence-order-then-severity-and-confidence).

### 2026-10-16 · Process: shared-index sweeps between agents, and the fix

- **Incident 1:** commit `056655d` (1.3's fix) swept 1.8's staged `pillow` change from `pyproject.toml`/`uv.lock` into itself through the shared git index (the 1.3 reviewer noted `pillow>=12.3.0` appearing "with no stated reason"). Net effect harmless: `pillow>=12.3.0` is in HEAD, and 1.8's own commit therefore contains no dependency change.
- **Incident 2:** commit `dab96fc` (1.9's fix) swept 1.5's in-progress `compose.yaml` and `.gitattributes` into itself. 1.5's fix commit `56cc74b` reconciled them (final content of both is in `56cc74b`).
- **Incident 3 (own slip):** the 1.8 agent ran `ruff check . --fix` over the whole repo once (3 auto-fixes, files unknown); the 1.1 agent ran `git add -N .` and `git reset -q` to feed untracked files to pre-commit. Both were disclosed; the 1.1 index and status were identical before and after.
- **Fix:** the commit rule in the agents' brief was changed to a pathspec commit, `git commit -m ... -- <paths>`, which commits only the named paths even when another agent has staged files ([B-070](decisions.md#b-070--parallel-agents-on-disjoint-paths-with-path-scoped-commits)).

### 2026-10-16 · User rules added mid-phase

- The user instructed (2026-10-16): continue through all phases 1 to 4 one by one; never modify, move or delete anything under `docs/`; never delete anything outside this project; never touch system files or configs (for example `%UserProfile%\.wslconfig`, registry, drivers, global git config, PATH).
- **Consequence:** since `docs/` is read-only, the documentation record moved to this folder, `build-log/`, and doc corrections are collected in [doc-corrections.md](doc-corrections.md) instead of being applied to the docs. Verified by the controller: no commit or working-tree change under `docs/` since `a679f9a`. The agent workspace `.superpowers/` is kept, not deleted ([B-071](decisions.md#b-071--sdd-workspace-is-kept-not-deleted)).

### 2026-10-16 · Wave 1 status

Complete: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8 part A, 1.9, 1.11, each with an independent review and (where it found Important issues) a fix round and a re-review. In progress and not covered here: 1.7 (Ray Serve, vLLM clients, with EXP-001), 1.8 part B (real-film run with EXP-002) and 1.10 (walking skeleton). Review outcomes and deferred minors per deliverable are in [review-findings.md](review-findings.md). Next: wave 2 integration (CLI wiring, [B-067](decisions.md#b-067--cli-wiring-is-a-separate-integration-step)), then the walking skeleton.
