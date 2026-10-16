# Doc Corrections

Every place where the implemented system or measured reality differs from the design docs in `docs/`. The docs are the original design spec and are **read-only** (user instruction), so none of these have been applied to them. This file is the record. Each row names the doc and section, what the doc says, what is true, and the evidence (deliverable, notes file or commit). Where the docs contradict each other, that is called out as "doc vs doc".

How to read the "Status" column: **Implemented** = the code follows the corrected behaviour; **Measured** = a number from a real run that differs from the doc's figure; **Open** = the discrepancy is recorded but not resolved.

Related: [decisions.md](decisions.md) (the decision behind each deviation) · [journal.md](journal.md) · [review-findings.md](review-findings.md).

## docs/tech-stack.md

| Section | Docs say | What is true | Evidence | Status |
|---|---|---|---|---|
| Platform Components, Experiment tracking row | MLflow "pinned at setup" | The client is `mlflow-skinny` 3.17.1 (`uv.lock`); the server image is `ghcr.io/mlflow/mlflow:v3.17.1` | 1.1 notes; 1.5 notes; B-003 | Implemented |
| Build notes, TorchCodec bullet (and the phased-plan risk row "TorchCodec needs a newer torch than the vLLM image ships") | Risk: TorchCodec may need a newer torch than the vLLM image ships | vLLM 0.30.0 pins `torch==2.13.0`; torchcodec 0.17 accepts torch >= 2.11, so they are compatible (checked 2026-10-15). The risk row can be closed | 1.1 notes (decision 1 and doc corrections); B-001 | Implemented |
| Build notes, TorchCodec bullet | (no Windows detail) | On Windows the PyPI wheel is `torchcodec 0.17.0+cpu`; it loads FFmpeg shared DLLs added with `os.add_dll_directory` (`nip.ingest.media.load_ffmpeg`, directory from `NIP_FFMPEG_DIR` or `models/ffmpeg/`), and the directory must be added before `torchcodec` is imported. Use `num_ffmpeg_threads=0`: the default of 1 was 4.7x slower on 1080p H.264 (92.9 vs 433.0 fps decode + resize) | 1.8 notes; C-001; B-025, B-028 | Measured |
| Media row (and D-027) | FFmpeg shared build is LGPL-2.1 | The Windows dev build is BtbN `n8.1 win64-lgpl-shared` (ffmpeg n8.1.3), configured `--enable-version3` with no `--enable-gpl`: **LGPL-3.0**. The future license gate should say LGPL-3.0. The Linux image uses apt ffmpeg 6.1.1 (a separate build) | 1.8 notes (decision 1); 1.5 notes; B-025 | Open (license gate not built) |
| Build notes, ttconv bullet | (describes ttconv as the TTML parser) | ttconv 1.2.3 also drops a `<div begin=...>` that has no `end` when its children's relative end is before the div's begin, with no logged error. Handled only by a test of the working case; reviewer minor M-1 | 1.3 notes; 1.3 review M-1 | Open (not handled) |
| Single-Node Service Layout, mlflow row (also project-structure.md `mlflow.Dockerfile` row) | MLflow image adds `psycopg2-binary` | The image ships SQLAlchemy 2.1.4, which maps `postgresql://` to psycopg 3 (error `No module named 'psycopg'`). The image installs `psycopg[binary]` and `boto3`; the server needs `--workers 1`, `--allowed-hosts mlflow:5000,localhost:5000,127.0.0.1:5000` (otherwise 403 "Invalid Host header") and `MLFLOW_SERVER_ENABLE_JOB_EXECUTION=false` (idle RAM 2.223 GiB -> 364 MiB) | 1.5 notes; C-002; B-033 | Implemented |
| Single-Node Service Layout, ray-head | (no command given beyond the Serve plan) | The command is `ray start --head --block` until `nip runtime head` exists; use `restart: on-failure:3`: the first start after the image build took 49 s and Ray's client server times out at 50 s (warm start 14 s) | 1.5 notes (things that broke, no. 4) | Implemented |
| Single-Node Service Layout, Keycloak port mapping | `8180:8080` on all interfaces | Bound to `127.0.0.1:8180` because the dev realm ships a known password (the reviewer states the docs use the all-interfaces form). Every published port in compose is loopback-bound and a unit test enforces it | 1.5 notes (decision 5); 1.5 review | Implemented |
| Model Catalog Defaults | (sizes and KV figures listed as defaults) | hf-mem 0.5.6 cannot estimate CTranslate2 (faster-whisper has no safetensors) or compressed-tensors INT4 checkpoints with `kv_cache_dtype=auto`. hf-mem's KV disagrees with the doc's KV: Qwen3.5-4B 128 vs 60 MiB per 1k tokens, Qwen3.8-27B 256 vs 160 (cause not verified). Catalog keeps the doc's values; a measured calibration replaces them | 1.6 notes; C-003; B-043 | Open (EXP-001) |
| Build notes, Label Studio bullet ("projects use frame rate 23.976023976") | Label Studio frame rate 23.976023976 | Correct only for NTSC-rate media. Sintel and Tears of Steel are exactly 24 fps (`r_frame_rate 24/1`), so their projects use `24`. Rule: never pass a fraction, always the decimal of the probed rate. Also: Label Studio 1.23 needs Personal Access Tokens (legacy token auth is disabled), and local-files serving needs a document-root mount and `LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true`; its first start takes about 2 to 3 minutes | 1.9 notes; C-010; B-048 | Measured |
| Build notes, Fountain bullet (and D-027 below) | screenplay-tools "passed a Fountain test including dual dialogue" | True, but it also mis-parses `FADE IN:` as a scene heading and mangles single-line boneyards; ingest works around both | 1.3 notes; B-023 | Implemented |

## docs/decisions.md

| Section | Docs say | What is true | Evidence | Status |
|---|---|---|---|---|
| D-027, Fountain row | screenplay-tools is adequate for Fountain | Needs the two workarounds above (strip boneyards first, re-classify unanchored "headings"); emphasis markers also need stripping | 1.3 notes | Implemented |
| D-027, SRT/WebVTT row; also architecture.md, Ingest validation ("report malformed cues with line numbers") | pysubs2 handles malformed cues | pysubs2 silently accepts a single-dash timing arrow and silently drops a block with no arrow, so line-numbered errors come from an own line pre-scan around pysubs2. Reviewer minor M-2: that pre-scan also rejects valid cue text such as `A -> B` | 1.3 notes; 1.3 review | Implemented (M-2 open) |
| D-027, ffmpeg license | LGPL shared FFmpeg | See tech-stack Media row above: the chosen Windows build is LGPL-3.0 | 1.8 notes | see above |
| D-028 | Label Studio frame rate 23.976023976 | See tech-stack Label Studio row: 24 for the test films | 1.9 notes | Measured |

## docs/architecture.md

| Section | Docs say | What is true | Evidence | Status |
|---|---|---|---|---|
| Timeline, Keyframes | "middle frame of each shot, plus one every 2 s for shots longer than 4 s" | Frames at `in + k x 2 s` for shots longer than 4 s (strictly), skipping any within 1 s of the middle frame (half an interval); a shot of exactly 4.0 s gets the middle only. Keys `timeline.keyframes.{long_shot_s, interval_s, jpeg_quality}` | 1.8 notes (decision 3); B-027 | Implemented |
| Timeline (Unknown or variable frame rate -> reject) | Reject VFR and unknown frame rate | Correct, and now implemented in `nip.ingest.media` (`MediaRejected`), after the review found the first version only flagged it. fps comes from `r_frame_rate`; `avg_frame_rate` is only used for the VFR check (0.05% tolerance) | 1.8 review I-1, I-2; B-030 | Implemented |
| Report order (localization: wrong names, spoilers, then readability; plot holes high to low confidence) | Check-level ordering inside a section | Implemented as severity then confidence only; the check-level rank is left until a second localization check exists | 1.4 review M2; B-065 | Open |

## docs/data-model.md

| Section | Docs say | What is true | Evidence | Status |
|---|---|---|---|---|
| Schema | `CREATE INDEX ON ...` statements are unnamed | The migration names them `ix_script_line_frames`, `ix_shot_episode_frames`, `ix_transcript_segment_episode_frames`, `ix_subtitle_cue_track_frames`, `ix_fact_subject_predicate_story`, `ix_fact_subject_predicate_screen` so Core metadata can match them | 1.1 notes | Implemented |
| Flag and Evidence | Fields as in the JSON example | Evidence items also carry `frames` (the half-open source of truth), `lang` and `scene`; `id` is absent until the flag is persisted; `verification` defaults to all `n/a` | 1.1 notes (decision 8); B-008 | Implemented |
| Flag and Evidence, field rules | In script-estimate mode `tc_in`/`tc_out` are replaced by `scene` | That applies to **estimated** objects (scenes) only. Subtitle cues and shots keep real timecodes in script-estimate mode. Suggested text: "evidence on an estimated object (a scene) carries `"scene": "S01E03 · Sc 12 (script estimate)"` instead of `tc_in`/`tc_out`" | 1.4 notes (decision 5); B-061 | Implemented (controller-accepted) |
| Time | `round(ms x fps_num / (1000 x fps_den))` with no tie rule | Ties resolve half-up (`floor(x + 1/2)`), not Python's half-even. Frame middles are exact ties and map to n+1; they are seek targets, not fed back into conversion | 1.2 notes; B-015 | Implemented |
| Subtitle conversion / source_file (not an error) | Declared TTML rate compared to the picture | The parser only records the declared rate (`Fraction \| None`); the "declared frameRate differs from picture" warning needs the probed rate and belongs to the timeline stage | 1.3 notes (P-2); B-018 | Open (later stage) |

## docs/hardware-adaptation.md

| Section | Docs say | What is true | Evidence | Status |
|---|---|---|---|---|
| The Plan (example) | Plan JSON without `pins`; always has `plan_id` | The Plan also carries `pins` (default `{}`); `plan_id` is absent until stored. `gpu_fraction` values are computed as `vram_gb / vram_total` (for example 0.38 for whisper on 8 GB), not 0.5 or 0.2; `text_llm` gets `gpu_fraction` too. `max_pixels` and `images_per_prompt` come from the catalog. The warning reads `text_llm context reduced 32768 -> 8192` (ASCII arrow, no "to fit ... usable VRAM") | 1.1 notes; 1.6 notes | Implemented |
| Worked examples, laptop | quality, staged, 5 groups, gmu 0.83 | 5 groups is right; **gmu is 0.77** (its own need, 6.14/8.0), not 0.83 (all usable memory) | 1.6 review table | Implemented |
| Worked examples, 24 GB (untested in the repo) | staged, 3 groups (9B FP8 + Gemma-12B) | **4 groups**: `timeline+vision_prep, text_prep, vlm+llm, judge`, qwen3.5-9b-fp8 at 16k + gemma-4-12b-qat at 8k. text_prep's best-alone actors (qwen3-embedding-8b 15.1 + gliner-x-large 3.7 = 18.8 GiB) cannot share 21.6 GiB usable with the 19.0 GiB shared model. Found by the reviewer | 1.6 review, 1.6 notes | Open (doc not corrected) |
| Worked examples, 48 GB quality | 2 groups, Gemma-12B judge | **3 groups**, judge gemma-4-31b-qat at 8k (40.8 <= 43.19 and it ranks higher, so best-alone picks it). Two groups would need actors (26.7) beside the shared model (42.5). Caveat: the 960 MiB/1k KV figure for gemma is an hf-mem number thought to be about 2x high; calibration may change the context, not the variant | 1.6 notes; 1.6 review | Implemented |
| Worked examples, 48 GB throughput | Qwen3.8-27B INT4 + Gemma-12B | **Resident, qwen3.8-27b-int4 at 16k, judge reuses text_llm (`independent_family: false`)**. The doc is wrong twice: arithmetic (24.5 + 17.8 + the smallest actor set 9.9 = 52.2 > 43.19 GiB usable) and step 7 (even ministral at 8k would push text_llm 16k -> 8k and asr large-v3 -> turbo) | 1.6 notes; 1.6 review; B-038 | Implemented (controller ruling) |
| Worked examples, 8x 80 GB quality | 2 groups | **3 groups**: a tp=8 engine takes all 8 GPUs whole, so the actors cannot co-reside | 1.6 notes; 1.6 review | Implemented |
| Worked examples, 8x 80 GB throughput | several 122B INT4 replicas | **Resident, qwen3.5-397b-a17b-int4 tp4 x1 + 4 gemma-4-31b replicas.** The doc's own greedy picks 397B-int4 because it frees about 210 GiB for 5 rank points. If replica count should matter, change the objective; this is not a planner bug | 1.6 notes; 1.6 review | Implemented |
| Algorithm, step 4 (throughput) | Greedy downgrade | Score = rank loss / useful GiB with useful = `min(freed, shortfall)` (plain `freed` when the sum fits), context shrinks first, moves may jump to any lower candidate, then a climb-back pass | 1.6 notes (decision 7); C-004 | Implemented |
| Algorithm, step 5 | Replicas across every GPU that can hold it | At most one replica of a deployment per GPU (H100 quality had given 58 to 59 replicas of small actors) | 1.6 notes | Implemented |
| Algorithm, step 7 (judge) | "without pushing any slot below its best-alone choice" | In throughput mode: "below the choice it gets when the judge reuses text_llm". The doc's own 48 GB example violated its own rule | 1.6 notes; B-038 | Implemented (controller ruling) |
| Memory model | `concurrency` undefined; units "GB" | `CONCURRENCY = 2`; all sizes are GiB (the doc's 8,188 MiB -> "8.0 GB" is GiB). With 2 the laptop lands on 8k context | 1.6 notes; B-036 | Implemented |
| Windows/WSL2 notes, Free VRAM | 7,321 MiB free at idle (7.15 GB) | On the Windows host with desktop apps open the probe read **6.44 GB, then 6.13 GB free** (about 1.5 GB held by C+G apps). At 6.13 GB the planner skips text_llm, vlm and judge_llm. Not yet measured inside WSL/Docker | 1.6 notes; C-006; B-044 | Measured (EXP-001 pending) |
| Probe, "re-probed on membership change", RAM visible to containers | RAM in a container is the WSL VM's memory | `SC_PHYS_PAGES` ignores cgroup limits, so this is only true without `mem_limit` or Kubernetes limits | 1.6 review M-8 | Open |
| Tests path | `tests/unit/planner/` | Planner tests are in `tests/unit/runtime/` (brief) | 1.6 report | Implemented |

## docs/api-contracts.md

| Section | Docs say | What is true | Evidence | Status |
|---|---|---|---|---|
| System / health | `GET /healthz` under `{NIP_PUBLIC_URL}/api/v1` | `/healthz` and `/readyz` are served both at the root and under `/api/v1`. `/readyz` returns `503 CLUSTER_UNAVAILABLE` with the failing dependency in `details` | 1.5 notes | Implemented |
| Auth | (no `/me` route) | Added `GET /api/v1/me` (sub + roles from the token); additive. Document it | 1.5 notes (decision 3); B-031 | Implemented |
| Report | `counts`, `id`, `primary_tc` | `counts` includes suppressed flags even when they are not listed; `id` is null for flags not yet persisted; `primary_tc` may be a script-estimate scene label instead of SMPTE | 1.4 notes | Implemented |
| GET /system/hardware vs hardware-adaptation.md (doc vs doc) | The API example omits `fingerprint` | `HardwareInventory.fingerprint` is required (hardware-adaptation.md wins). Reviewer minor | 1.1 review minor 4 | Open |
| Plan `groups` (doc vs doc) | api-contracts shows `groups` as a list of strings | `Plan.groups` is `list[StageGroup]` objects (hardware-adaptation.md wins) | 1.1 review minor 4 | Open |
| Errors | `{"error": {"code","message","details"}}` with `UNAUTHORIZED` and `CLUSTER_UNAVAILABLE` | Correct, and the first API skeleton violated it (returned `{"detail": ...}`); fixed after review. 500s outside handled errors still return Starlette's plain body | 1.5 review; 1.5 rereview minor 2 | Open (500s) |

## docs/project-structure.md

| Section | Docs say | What is true | Evidence | Status |
|---|---|---|---|---|
| Repository Layout | No `alembic.ini` | Add `alembic.ini` at the repo root (`script_location = nip.store:migrations`, URL from `NIP_DATABASE_URL`) | 1.1 notes | Implemented |
| Repository Layout, `src/nip/contracts/` comment | Flag, Evidence, Fact, Plan, HardwareInventory | Also `Timeline`, `Span` and `Report` (`timeline.py`, `report.py`) | 1.4 notes; B-057, B-058 | Implemented (controller-accepted) |
| Repository Layout, `src/nip/timeline/` and `ingest/` | (shape not listed) | `timeline/` has `estimate.py`, `shots.py`, `keyframes.py`, `picture.py`; `ingest/media.py` is the probe; `config/pipeline.yaml` currently holds only `timeline.shots.threshold` and `timeline.keyframes.*` | 1.8 notes; 1.4 notes | Implemented |
| Tests | Unit tests run as shown | `uv run pytest -m "not gpu and not integration"`; the Postgres migration test needs `NIP_TEST_DATABASE_URL` (a database role that can create databases: it builds two scratch databases) | 1.1 notes; 1.1 fix | Implemented |
| CLI table | `nip eval run --set ... --seeds 1,2,3` | `nip eval run` takes `--flags`, `--labels` and one `--seed` per invocation (scoring an existing flags file); the seed loop belongs to the pipeline-driving wrapper (1.10) | 1.11 notes; B-056 | Implemented |
| CLI table | `nip eval corpus fetch --set`, `nip eval labels push/pull` | Also `labels prepare`, `labels verify-clip` and `labels config`; `pull` takes `--allow-partial` and `--labeller` | 1.9 notes; 1.9 report | Implemented (not yet wired, B-067) |
| Layout, eval labels | `eval/labels/<set>/<title>.jsonl` for planted errors | Hand-labelled cuts are `eval/labeling/labels/<title>_cuts.json` (one JSON object; `_cuts.provisional.json` when the labeller is not `human`). Cuts are not Flags | 1.9 report (fix round); B-049 | Implemented |
| First run | UI at 8080 | Until the UI exists (4.1) the API is at `http://localhost:8000`; Keycloak admin is `admin` / `${KEYCLOAK_ADMIN_PASSWORD}`; dev user `dev`/`dev` (dev realm import is opt-in: `NIP_KEYCLOAK_DEV_REALM=true`) | 1.5 notes; B-032 | Implemented |
| Labeling profile (lines 155 and 226 per the 1.9 review) | `docker compose --profile labeling up` on :8081 | The 1.9 README starts Label Studio with a hand-written `docker run`; no `labeling` service exists in compose.yaml (deferred from 1.5) | 1.9 review M6; B-031 | Open |

## docs/evaluation.md

| Section | Docs say | What is true | Evidence | Status |
|---|---|---|---|---|
| Corpus table, Sintel script | "Script: Free (CC BY)", `script.zip` on durian.blender.org | No such file exists (404). Only the 2009 "1st minute script" PDF is published; the full script is not available | 1.9 notes; B-047 | Measured |
| Corpus, manifest URLs | `https://download.blender.org/durian/movies/` | Returns HTTP 403 (a 61 KB HTML page) to automated clients; files are fetched from the official mirror `ftp.halifax.rwth-aachen.de/blender/demo/movies/` (Sintel md5 `377aa3357df96a9ae085169a74d2a3bf` matches the official one). The Tears of Steel 1080p `.mov` there is a zip archive under a `.mov` name, so ToS is used at 720p | 1.9 notes; B-045, B-046 | Measured |
| Corpus, Cosmos Laundromat license (line 23 per the 1.9 review) | CC BY 3.0 | The 1.9 manifest says `CC-BY-4.0`. Neither the notes nor the reviewer say which is right; one file needs correcting | 1.9 review spec note | **Open (unresolved)** |
| `loc.drift` injector | Rescale factors assume 23.976 picture (25025/24000) | Sintel and Tears of Steel are 24 fps; a 25 fps confusion is 25/24 (4.17%). The `loc.offset.v1` skeleton injector still hardcodes 24000/1001 and writes "at 23.976 fps" into the label (reviewer M1: +12 frames is 500.5 ms where 500 ms is correct at 24 fps) | 1.9 notes; 1.9 review M1 | Open |
| Reports and MLflow, Params row | Params list thresholds, rule-pack versions, benchmark-set version | In Phase 1 these arrive through `--param k=v`; per-agent and per-slot cost, cache-hit rate, the Plan side-by-side layout, wall time per 45-minute episode and the LLM-call-traces artifact are not produced (no pipeline) | 1.11 notes; 1.11 review gaps | Open (later) |
| Corpus, Label Studio | (hand labelling described) | The README click path was verified in the real Label Studio 1.23.2 UI (task 1 `_verify.mp4`, counter box `100 of 240`, hotkey 1 for the Cut label, double-click on the highlighted current-frame strip); a UI-created annotation exports as `ranges:[{start:92,end:92}]` | 1.9 report (fix round) | Measured |

## docs/phased-plan.md (risk register)

| Row | Docs say | What is true | Evidence |
|---|---|---|---|
| TorchCodec needs a newer torch than the vLLM image ships | risk | Not a risk: vLLM 0.30.0 pins torch 2.13.0 and torchcodec 0.17 accepts torch >= 2.11 | 1.1 notes |
| Label Studio reads 23.976 as 24 (rated High if unnoticed) | risk, with the config at 23.976023976 | The test films are exactly 24 fps; `push` probes the clips and refuses mixed or VFR rates, so the risk is mitigated by construction | 1.9 notes; 1.9 re-review |
| FFmpeg frame-extraction fallback | fallback if TorchCodec is unusable | Not needed; TorchCodec works on Windows with the BtbN shared build | 1.8 notes |

## Non-doc files that the docs describe

| File | Docs / state | Correction | Evidence |
|---|---|---|---|
| `.env.example` (project-structure.md Configuration block) | Comments inline after values | Comments are on their own lines (some `.env` readers keep inline text as part of an empty value such as `NIP_PIN_TEXT_LLM=`) | 1.1 notes (decision 15) |
| `.env.example` | no `NIP_FFMPEG_DIR` | Add `NIP_FFMPEG_DIR=` (directory with the FFmpeg shared libs; blank means `models/ffmpeg/`) | 1.8 notes |
| `.env.example` | no `POSTGRES_PASSWORD`, `KEYCLOAK_ADMIN_PASSWORD`; `NIP_RAY_ADDRESS` comment | Add both (compose defaults them to `change_me`, which `NIP_DATABASE_URL` embeds, so a change must be made in several places); `NIP_RAY_ADDRESS` is "auto on the Ray head, `ray-head:6379` elsewhere" (compose overrides it per service); `NIP_OIDC_ISSUER_BASE` (new in compose) is not listed and can drift from `NIP_OIDC_ISSUER`, which gives every token a 401 | 1.5 notes; 1.5 review minors 4 and 5 |
| `.env.example` line 63 | `NIP_KEYCLOAK_DEV_REALM=true` shipped | Copying the template to a cloud host's `.env` would enable the dev realm; ship it commented out before Phase 4 | 1.5 rereview minor 1 |

## Counts

- Corrections that are implemented in code, or measured numbers that differ from the docs: the large majority of the rows above.
- Open or unresolved: Cosmos Laundromat license, the `loc.offset.v1` fixed fps, the 24 GB worked example text, the two doc-vs-doc API inconsistencies, the `labeling` compose profile, 500s outside the error envelope, and everything marked Open in the status columns.
