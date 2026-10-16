# Review Findings

Every Phase 1 wave 1 deliverable was reviewed by an independent reviewer agent that did not write the code (spec compliance first, then code quality), and anything rated Important was sent back to the implementer as a fix round and then re-reviewed. This file records, per deliverable: what the review found, how it was fixed, and the minor findings that were deliberately deferred. It is the "the review caught X, we fixed it by Y" material.

Severity used by the reviewers: **Critical** (breaks the deliverable or the spec), **Important** (a real defect or spec gap that should be fixed before others depend on it), **Minor** (style, hardening, test gaps, edge cases; may be deferred).

Sources: `.superpowers/sdd/phased-plan/reports/*-review.md`, `*-rereview.md`, `*-report.md`, and the controller ledger `progress.md`. A reviewer ran targeted checks against the checkout where noted; most test counts are the implementer's, not re-run by the reviewer unless stated.

Related: [decisions.md](decisions.md) · [journal.md](journal.md) · [doc-corrections.md](doc-corrections.md).

## Summary

| Deliverable | Commits | Spec | Quality | Critical | Important | Minor | Fix round | Re-review |
|---|---|---|---|---:|---:|---:|---|---|
| 1.1 Scaffolding, CI, contracts, schema | `7ce7da1`, `c1a8853` | pass | approved | 0 | 1 | 9 | `c1a8853` | addressed |
| 1.2 Timecode | `f6390db` | pass | approved | 0 | 0 | 4 | none needed | n/a |
| 1.3 Ingest parsers | `7e5c20a`, `abd1108`, `056655d`, `993e381` | pass (one partial) | changes needed | 0 | 2 | 11 | `056655d`, `993e381` | addressed |
| 1.4 Timeline, check interface, report | `172e19e` | pass | approved | 0 | 0 | 4 | none needed | n/a |
| 1.5 Compose stack, API skeleton | `1d1b9f9`, `56cc74b` | fail (error envelope) | changes needed | 0 | 4 | 9 | `56cc74b` | addressed |
| 1.6 Probe, catalog, planner | `28e859f`, `3cf18c7` | pass | approved | 0 | 2 | 8 | `3cf18c7` | addressed |
| 1.8 part A Media, shots, keyframes | `829a3b3`, `72a7ea5` | pass (one gap) | changes needed | 0 | 3 | 8 | `72a7ea5` | addressed |
| 1.9 Corpus, injectors, Label Studio | `d4cb1c2`, `dab96fc` | pass | changes needed | 0 | 4 | 6 | `dab96fc` | addressed |
| 1.11 Eval metrics, MLflow | `a329f4a`, `159b005` | pass | approved | 0 | 2 | 9 | `159b005` | addressed |
| **Total** | | | | **0** | **18** | **68** | 7 fix rounds | all Important addressed |

Counts are as stated in the reviews and the ledger. No re-review found a new Critical or Important finding in a fix diff. The 1.2 and 1.4 reviews found nothing Important.

### What the pattern says (good interview framing)

- **Tests that could not fail.** Three of the Important findings were tests or justifications that did not discriminate: the 1.8 frame-exactness test (would pass with a uniform seek offset), the 1.3 numbered-PDF test (number and heading written as one string, so it could not see a separate-x number), and the 1.11 claim that a shared-ref match was "strictly stricter than IoU" (an extra OR-path can only add matches). In each case the fix included proving the new test fails on the old code.
- **Two hand-maintained copies drift** (1.1 schema vs migration): fix was a real-database catalog diff, with four injected drifts as proof.
- **Specs that contradict themselves** (1.6 step 7 vs the docs' own worked example; 1.9's cut labels vs the Flag format) were escalated for a controller ruling instead of silently picking one.
- **Observed behaviour beat assumptions** (1.5 `KC_IMPORT_REALM` ignored by Keycloak 26.6; 1.9 Label Studio exporting only annotated tasks unless `download_all_tasks=true`), which is why live verification was part of the fix rounds.

---

## 1.1 Scaffolding, CI, contracts, schema

**Review:** spec pass, quality approved. Critical 0, Important 1, Minor 9. The reviewer compared contracts and schema field by field with the docs: all 27 check IDs, all 26 tables, GiST indexes and the exclusion constraint matched; no column-level deviation.

**Important**
1. *Schema/migration drift unguarded.* `schema.py` (Core) and migration 0001 (raw DDL) are hand-maintained; CI compared table names only, and `compare_metadata` skips server defaults, CHECK, identity ALWAYS vs BY DEFAULT and exclusion constraints. **Fixed** (`c1a8853`): a real-Postgres catalog diff (alembic upgrade vs `metadata.create_all`) in CI with a pgvector 0.8.2-pg18 service; four injected drifts each caught; first run 1 passed in 11.95 s. See [B-005](decisions.md#b-005--migration-0001-is-frozen-raw-ddl-schemapy-is-core-drift-is-a-catalog-diff) and [C-009](experiments.md#c-009--ways-to-guard-schemamigration-drift).

**Re-review: addressed.** New minors from the fix: the vacuity guard is only on columns (constraint/index/extension sets could be empty on both sides and still pass); the test silently skips if `NIP_TEST_DATABASE_URL` is unset (CI sets it, but a typo would pass); it now needs a CREATEDB role and fixed database names (`nip_test_migrated`, `nip_test_core`), not xdist-safe; the CI step is unverified on GitHub; `# fmt: skip` is slightly ugly.

**Deferred minors (original review)**
- `ignore_missing_imports = true` is global under `strict`; prefer per-module overrides.
- `ProducedBy.model_variant` is required-but-nullable (no default).
- `Crop.box` documented as normalised but not range-checked.
- `HardwareInventory.fingerprint` is required while api-contracts omits it; `Plan.groups` is objects while api-contracts shows strings (doc vs doc, see [doc-corrections.md](doc-corrections.md)).
- `Plan.skipped_slots: list[Slot]` has no field for the reason.
- CI installs the full CUDA torch on Linux just to run tests that never import torch (slow, disk pressure; use `--no-install-package torch` if it hurts).
- `schema.py` style is not `ruff format` output and has no `# fmt: skip`.
- `database_url()` untested (a unit test was added in the fix round).
- Process: the implementer ran `git add -N .` and `git reset -q`, which the rules forbid; disclosed, index identical before and after, commit contains only the intended 32 paths.
- Ledger adds: `.gitignore` rewrite of `models/` `data/` to anchored form; implementer-disclosed deviations.

**Could not be verified by the reviewer:** a real GitHub Actions run (never pushed), action versions, runner disk, `uv.lock` resolution of vllm/ray against torch 2.13.0 on Linux, static-ffmpeg TorchCodec behaviour (later solved in 1.8).

## 1.2 Timecode

**Review:** spec pass, quality approved. Critical 0, Important 0, Minor 4. The reviewer independently iterated 3 h of frames at 29.97 and 59.94 drop-frame: the only label discontinuities are exactly the 162 non-10th-minute boundaries per rate, and `10:00;00` falls at frames 17982 and 35964.

**Deferred minors**
1. No runtime guard against a non-`Fraction` fps (a float silently gives inexact results; mypy catches it statically).
2. `\d` in the timecode regex matches Unicode digits; `[0-9]` would be stricter.
3. Drop-frame known values at 59.94 are thin (only `00:01:00;04` = 3600); add `00:10:00;00` = 35964 and a contiguity property. The implementation is correct; the gap is test strength.
4. `ms_to_frame` accepts negative ms and returns a negative frame, while `frame_to_smpte` rejects negative frames.

**Could not be verified:** oracle cross-checks against OpenTimelineIO and the `timecode` package (D-030) are not in this deliverable; half-up tie behaviour against other layers (SQL, UI) was not checked.

## 1.3 Ingest parsers

**Review:** spec pass (partial on I-2), quality changes needed. Critical 0, Important 2, Minor 11. The reviewer ran three targeted checks (TTML edge cases, an SRT arrow-in-text case, a scene-numbered PDF).

**Important**
1. **I-1 A scene-numbered PDF misclassified every non-heading line.** `pdf.py` took `margin = min(x0)` over all lines; with the scene number left of the heading (the normal shooting-script layout), the number's x0 became the margin and action lines landed in the dialogue band. Checked: `12` at x=72 and `INT. HOUSE - DAY` at x=108 gave `Maya waits.` as dialogue and `Hello there.` as parenthetical. The existing numbered-heading test wrote number and heading as one string at x=108, so it could not see this. **Fixed** (`056655d`): `_text_x0` uses the x of the first heading glyph when a leading scene number precedes a heading match; the new test uses a separate-x number (x=72, heading x=108, trailing number x=500) plus a `12A` case, and fails on the old code.
2. **I-2 TTML cue errors carried no line number**, although the docs require line numbers. ElementTree does not expose element lines. **Fixed** (`056655d`): an expat pass records the start-tag line of every `<p>`; cue errors carry it. If the `<p>` count differs from ttconv's cue count (ttconv pruned one) lines are left None rather than misattributed; ttconv log errors get a line only when exactly one cue is bad. The test asserts lines 5/6/7, cue lines `[4, 7]` and the one-bad-cue case (5). The follow-up `993e381` fixed ruff import order and line length.

**Re-review: addressed**, no new Critical/Important. New minors: `pillow>=12.3.0` appeared in `pyproject.toml`/`uv.lock` with no reason in the report (it was another agent's staged change swept in through the shared index, see the [journal](journal.md#2026-10-16--process-shared-index-sweeps-between-agents-and-the-fix)); `_text_x0` indexes glyphs by non-space character count (wrong only for odd spacing or ligatures); one `type: ignore[list-item]`.

**Deferred minors (M-1 to M-11)**
- M-1 ttconv `<div begin>` without `end` silently drops cues (a file where every cue is like that is rejected as "no cues", which is misleading).
- M-2 False reject of valid SRT: the timing-line pre-scan also runs on cue text, so `A -> B` rejects the file.
- M-3 Parsers can still raise: `csv.Error` mid-iteration (200,000-char field), unguarded `ttconv.to_model` and `FrameRateAttribute.extract`.
- M-4 ttconv log capture attaches a handler to a process-global logger: not thread-safe under concurrent API parses.
- M-5 FDX `Shot` paragraphs become scenes (fabricates scenes and shifts numbers).
- M-6 `parse()` raises a bare `KeyError` for an unknown `fmt` or a missing CSV `kind`.
- M-7 Inconsistent `data` on error (`parse_bible` returns data with errors; the others return None).
- M-8 `time_of_day` is a heuristic (`INT. HOUSE - DAY - CONTINUOUS` gives `CONTINUOUS`).
- M-9 TTML frame-based timing with no declared rate is silently converted at ttconv's 30 fps default.
- M-10 Untrusted-input hardening: no size or expansion limits on `ET.fromstring`, `yaml.safe_load` aliases, pdfplumber; the API layer should cap uploads.
- M-11 Style: an awkward `ruff format` wrap in `pdf.py` and a `type: ignore[arg-type]` that hides an untyped `Raw.kind`.

**Could not be verified:** accuracy on real screenplay PDFs (Final Draft, Highland, Fade In exports; dual dialogue, scene numbers on both sides, `(CONT'D)`), real FDX variants, real-world TTML (IMSC1.1, EBU-TT-D) beyond one SMPTE fixture.

## 1.4 Timeline, check interface, report

**Review:** spec pass, quality approved. Critical 0, Important 0, Minor 4. Targeted run: 30 passed in 1.07 s. Documented deviations that needed a controller ruling (all accepted, see [B-061](decisions.md#b-061--script-estimate-display-rules-apply-per-object-not-per-episode), [B-064](decisions.md#b-064--emit-enforces-evidence-or-nothing-and-assigns-the-tier), [B-065](decisions.md#b-065--report-ranking-sections-in-consequence-order-then-severity-and-confidence)): display rule per object, intra-section ordering, tier assigned at emission rather than by verification routing. There was no fix round and no re-review.

**Deferred minors**
- **M1 Stale index on copy.** `Timeline._by_ref` is built only in `model_post_init`; verified that `model_copy(update={"spans": [...]})` keeps the old index (`resolve` of a new ref returns None) and `tl.spans.append(dup)` bypasses the duplicate check. Cheapest fix: a docstring warning or rebuild via the constructor. Matters in Phase 2 when alignment replaces estimates.
- **M2** Report sorting ignores check-level consequence inside a section.
- **M3** Duplicate scene numbers crash with a raw `ValueError` while the 1.3 parser only warns (the parser's auto-numbering `str(len(scenes) + 1)` can collide with explicit numbers); better handled in ingest validation. Carried into the 1.10 dispatch.
- **M4** Non-timeline evidence kinds are always dropped, so the first check citing a fact must extend `emit`.

**Could not be verified:** the 212-test full run, the Sintel numbers (scratch script not committed), whether the 1.10 readability check needs sub-frame cue durations, and cues extending past the picture's duration (kept unclipped; relies on a verification step that does not exist yet).

## 1.5 Compose stack, API skeleton

**Review:** spec **fail** (one documented-convention gap: the error envelope), quality changes needed. Critical 0, Important 4, Minor 9. Everything else in the spec matched: image versions, digest pins, WSL2 settings, loopback-bound ports (enforced by a unit test), D-019 issuer/JWKS split.

**Important**
1. **CRLF could break the Postgres init script on a fresh Windows checkout.** No `.gitattributes`; with `core.autocrlf=true` a fresh clone converts the bind-mounted script to CRLF, so `set -e\r` fails, the `mlflow` database is never created and mlflow cannot start. **Fixed:** `.gitattributes` forces `eol=lf` on `*.sh`, `*Dockerfile`, `compose.yaml`, `deploy/keycloak/*.json` (checked with `git ls-files --eol`).
2. **JWT hardening gaps.** `exp` not required (a signed token with no `exp` never expires); a token with no `sub` gave a 500 through `claims["sub"]`. **Fixed:** `require` = `exp, iat, sub, iss, aud`; every PyJWT/Value/Type/Key error is a 401 with `WWW-Authenticate: Bearer`; non-list `roles` is a 401; tests drop each claim in turn, plus a foreign signing key.
3. **A known-credential, all-roles dev realm was auto-imported by the one compose file the docs say is also used on cloud VMs** (user `dev`/`dev` with all four roles, password grant on a public client, `sslRequired: none`). **Fixed** (controller ruling [B-032](decisions.md#b-032--keycloak-realm-import-binding-and-the-opt-in-dev-realm)): import only when `NIP_KEYCLOAK_DEV_REALM=true`. The first attempt (`KC_IMPORT_REALM`) was not honoured by Keycloak 26.6; a bash entrypoint adds `--import-realm` only on an exact `true` (`false`, empty, unset and `True` all fail closed; reviewer ran the expansion in bash).
4. **Error envelope** did not follow api-contracts.md (returned FastAPI's `{"detail": ...}`). **Fixed:** `src/nip/api/errors.py` with the documented envelope for 401, 503 `CLUSTER_UNAVAILABLE`, HTTP errors and `VALIDATION_FAILED`.

**Re-review: all four addressed**, no new Critical/Important.

**Deferred minors**
1. IdP unreachable gives 401 "invalid token" rather than 503 (`PyJWKClientConnectionError` is a `PyJWTError`).
2. `include_router(system)` twice gives duplicate OpenAPI operation IDs and warnings.
3. Supply chain looser than "digests pinned; uv.lock": the MLflow image has no digest, `pip install psycopg[binary] boto3` is unpinned, `uv pip install ... .` resolves from pyproject not `uv.lock`; the digest test covers only three images.
4. `NIP_OIDC_ISSUER_BASE` is new in compose, not in `.env.example`, and can drift from `NIP_OIDC_ISSUER` (a mismatch gives every token a 401).
5. `.env.example` lacks `POSTGRES_PASSWORD`/`KEYCLOAK_ADMIN_PASSWORD`; `change_me` is duplicated in three places.
6. The MLflow backend URI (with the DB password) is on the command line, visible in `docker inspect`.
7. The objectstore healthcheck hits the master (9333), not the S3 gateway (8333): a small startup race.
8. `postgres-init.sh` runs only on an empty volume; an old `pg-data` volume has no `mlflow` database and mlflow fails with no hint.
9. Test gaps: no `alg=none`/HS256 confusion case; the real `PyJWKClient` path is covered only by the live-stack test; an unneeded `# noqa: S310`.
- From the re-review: `.env.example:63` ships `NIP_KEYCLOAK_DEV_REALM=true` (fix before Phase 4 cloud); 500s outside handled errors still return Starlette's plain body; `VALIDATION_FAILED` details through `jsonable_encoder` may serialise `ctx` oddly; the dev-realm unit test checks the command string only (shell behaviour verified by hand).

**Could not be verified from the diff:** that each digest matches its tag, pull/build/startup/RAM/VRAM numbers (they come from the implementer's live run), `docker compose config` validity, SeaweedFS S3 auth behaviour and Keycloak mappers (asserted from a live run).

## 1.6 Hardware probe, catalog, planner

**Review:** spec pass (every algorithm step, probe field, catalog format and memory-model line implemented; 24 spec items checked), quality approved. Critical 0, Important 2, Minor 8. The reviewer ran three targeted checks: the laptop at its measured 6.13 GB free, 1x 48 GB throughput with and without judge variants, and the untested 24 GB doc example.

**Important**
1. **I-1 In throughput mode the independent judge pushed other slots below what reuse would give.** Measured on 1x 48 GB: text_llm at 8k and asr whisper-turbo with an independent judge, versus text_llm at 16k and asr large-v3 with judge reuse. The spec contradicted itself (the doc's own 48 GB example did the same). **Controller ruling** ([B-038](decisions.md#b-038--judge-selection-independent-family-else-reuse-and-in-throughput-mode-the-judge-must-not-downgrade-others)): the judge gets its own engine only if no other slot is downgraded. **Fixed** (`3cf18c7`): other slots are chosen first with the judge reusing text_llm, then the judge climbs last. New test `test_throughput_judge_never_pushes_other_slots_down` checks all three inventories with and without judge variants.
2. **I-2 The vlm decision never set `max_pixels` / `images_per_prompt`**, which the doc's Plan example, the laptop worked example and the Serving section all show, and which 1.7 needs for vLLM's flags. **Controller ruling** ([B-042](decisions.md#b-042--vlm-image-caps-come-from-the-catalog-589824-px-2-images)). **Fixed** (`3cf18c7`): catalog defaults 589824 / 2 on all 9 vlm variants, copied into the Plan, with an override test (1003520 / 4).

**Re-review: both addressed**, 25 passed. New minors: a loop-local `others` shadows the greedy block's `others` (`planner.py:359`); the stub path sets no vlm caps (1.7 must not assume non-None under `NIP_PROFILE=cpu`); when vlm shares text_llm's engine the caps live on `decisions[vlm]` (1.7 must read them there); "no downgrade" is implemented relative to the reuse set, not to best-alone.

**Escalation recorded by the reviewer:** the laptop at 6.13 GB free plans no LLM (see [B-044](decisions.md#b-044--the-laptop-cannot-plan-an-llm-at-613-gb-free-exp-001-runs-before-the-walking-skeleton)); `CONCURRENCY = 1` alone does not rescue it (5.67 GiB > 5.63). EXP-001 should run before the walking skeleton. Also: the reviewer checked every worked-example disagreement and found the planner right each time ([B-072](decisions.md#b-072--the-planner-follows-the-algorithm-where-the-docs-worked-examples-disagree)).

**Deferred minors (M-1 to M-8)**
- M-1 `independent_family = not judge_reuses` never compares families: a pinned judge in text_llm's family, or a text_llm downgraded into another family, is still reported as independent.
- M-2 An hf-mem-filled actor gets `vram_gb = weights` without the 0.5 GiB activation allowance (underestimate, the unsafe direction).
- M-3 hf-mem result checked with an `assert` (stripped by `-O`, opaque for non-safetensors repos).
- M-4 Compute-capability exclusions are filtered silently; `nip plan` never prints `validate()`'s excluded reasons.
- M-5 Per-fraction round-up can push the summed `gpu_fraction` on one GPU above 1.0 at `NIP_GPU_MEM_UTILIZATION` of about 0.95 or more.
- M-6 The measured laptop state (LLMs skipped, actors planned, judge without text_llm) has no regression test.
- M-7 `test_planner.py` / `test_catalog.py` read the developer's real `$HF_HOME/hf-mem-cache.json` at import.
- M-8 The 24 GB worked-example correction was missing from the notes (added later); `probe.py` uses `SC_PHYS_PAGES`, which ignores cgroup limits.

**Could not be verified:** hf-mem attribute names against 0.5.6 (tests use a fake; the notes' run was ad hoc), `tp_options` against attention-head divisibility, probe results inside WSL/Docker, catalog sizes/ranks/overheads (implementer estimates), license policy (no `config/licenses.yaml`), multi-node packing (only single-node inventories tested).

## 1.8 part A: Media probe, shots, keyframes

**Review:** spec pass with one gap, quality changes needed. Critical 0, Important 3, Minor 8. The reviewer verified shot-run arithmetic (cuts strictly increasing, never 0 or N, never zero-length) and ran `parse_probe` on edge-case input.

**Important**
1. **VFR / unknown frame rate was flagged but never rejected**, although architecture.md says to reject. A VFR file would produce a silently untrustworthy frame axis. **Fixed** (`72a7ea5`): `MediaRejected(ValueError)`; `nip timeline picture` prints `INPUT_REJECTED: ...` and exits 1; a real VFR mp4 (ffmpeg `select` + `-fps_mode vfr`) is tested through `probe()` and the CLI.
2. **fps source and VFR flag were fragile.** fps came from `avg_frame_rate` and `vfr` meant `r != avg`: probing avg `2997/125` against r `24000/1001` returned fps `2997/125` with `vfr=True` (a false flag and an inexact rate, violating "exact rational"); `0/0` raised `ZeroDivisionError`. **Fixed:** fps is the exact `r_frame_rate`; avg is only a VFR check with a 0.05% tolerance (below the 0.1% gap between 24 and 24000/1001); `0/0`, `0/1`, empty and missing rates reject as unknown; cover-art streams are skipped. Tests cover both sides of the tolerance.
3. **The frame-exactness test was weaker than its claim.** It proved random access equals sorted access and that luma rises with the index, but never that frame N has luma N; a uniform seek offset (the D-027 failure mode) would pass. **Fixed:** a lossless ramp clip (`geq lum=16+3.6*N`) as an independent oracle; decoded frame N must match its gray level (one frame off shifts it by at least 4.2 levels, tolerance 1.5), for unsorted random access across key frames at 0 and 30 and for all 60 frames in sequence; a second test checks each extracted keyframe JPEG carries the gray level of the frame its record claims.

**Re-review: all three addressed**; non-GPU run 26 passed, 1 deselected, 0 skipped (real-ffmpeg tests ran); `ruff check` and `ruff format --check` clean (9 files). Open from the re-review: an unknown average rate (`0/0`) skips the VFR check; `r_frame_rate` plausibility is not checked; the 0.05% tolerance could falsely reject very short MKV clips with millisecond-rounded timestamps.

**Deferred minors (original eight)**
1. (Partly fixed in the fix round: `ZeroDivisionError` and cover art.)
2. `probe()` raises `CalledProcessError` on a corrupt file, not an INPUT_REJECTED-style error.
3. `duration_frames` from the probe is never cross-checked against the decoder's `len(dec)`; for MKV (no `nb_frames`) it is `round(duration * fps)` and can disagree. (Possibly related to the 21,312 vs 21,313 Sintel frame-count difference, see the [journal](journal.md#2026-10-16--14-script-estimate-timeline-shared-flag-emission-report-json).)
4. `ruff format --check` failed on `picture.py` (fixed in the fix round).
5. `model or load_model()` should be `is None` (fixed in the fix round).
6. `media_ok` swallows every Exception into `pytest.skip`, hiding real regressions; all decode tests skip in a Linux cpu CI without shared FFmpeg libs.
7. `ffmpeg_dir()` returns None silently when `$NIP_FFMPEG_DIR` has no `avcodec-*.dll` and re-globs on every `load_ffmpeg()` (`@cache` it).
8. Nits: a pointless assertion (`json.dumps(m.fps.numerator) == "24000"`); a wrong comment ("96 frames = 4.0 s, not longer than 4 s" is 4.004 s); a keyframe batch of 64 full-resolution NHWC frames is about 0.4 GB at 1080p and 1.6 GB at 4K.

**Could not be verified:** real-film behaviour and TransNetV2 on gradual transitions (EXP-002), the PySceneDetect fade detector (absent), Linux/Docker FFmpeg libs, the LGPL claim beyond the quoted configure line, the decode/VRAM/fps numbers (implementer's runs).

## 1.9 Corpus, injectors, Label Studio

**Review:** spec pass, quality changes needed. Critical 0, Important 4, Minor 6. The reviewer ran a cross-task check: a real cuts row raises `KeyError: 'label_id'` in `eval/metrics.py` `load_labels`.

**Important**
1. **I1 `push` did not tie `--fps` to the clips.** It defaulted to 24/1 and never probed the clips: on 23.976 media it would silently yield wrong ground truth (the phased-plan High-rated risk row). **Fixed** (`dab96fc`): the option was removed; `push` probes every clip and the verify clip, refuses mixed or VFR rates, and stores the rate in every task. Tests: probe-and-verify-first, refuse mixed rates with no API call.
2. **I2 `pull` accepted partially labelled projects silently**, so unlabelled clips would count as false positives in EXP-002. **Fixed:** `pull` prints `n/m clips labelled` and exits 1 unless `--allow-partial`. While verifying against the real Label Studio the implementer found its JSON export omits unannotated tasks unless `download_all_tasks=true`; without that the check would have reported `0/0` forever. The export URL sets it and a test asserts it.
3. **I3 README step 4 (frame-number check) could not be followed by a non-expert**: it referred to a throw-away project, but `push` only uploaded `data/labeling/<title>/*.mp4` and `verify_24.mp4` was written one level up; no command printed the config; no click path. **Fixed:** the verify clip is now task 1; a `config` command prints the rendered config; the README has an explicit click path that was exercised in the real Label Studio 1.23.2 UI (a UI-created annotation exported as `ranges:[{start:92,end:92}]`, which confirmed the result shape the first review listed as unverified).
4. **I4 The cuts label format was undocumented and not consumable by `eval/metrics.py`.** **Controller ruling** ([B-049](decisions.md#b-049--cut-labels-are-a-separate-json-file-not-flags)): cuts are not Flags; 1.8B owns a +-2 frame cut-F1 scorer; 1.9 documents the format. Also fixed M3 (LS frame 1 is ignored for every clip; before, a mark at frame 1 of clip 0 would produce a cut at global frame 0 and an empty shot).

**Re-review: all four addressed**; 13 passed in `test_label.py` (25 across the three eval test files). The fix commit also swept in 1.5's in-progress `compose.yaml` and `.gitattributes` (see the [journal](journal.md#2026-10-16--process-shared-index-sweeps-between-agents-and-the-fix)); the 1.5 fix commit reconciled them. The new output path `eval/labeling/labels/` is not in docs/evaluation.md. Not verifiable in the re-review: the README click path in a real UI (the implementer then did exercise it).

**Deferred minors**
- M1 `loc_offset.py` hardcodes `FPS = 24000/1001` and writes "at 23.976 fps" into the label; the films are 24 fps, so "+12 frames" is 500.5 ms where 500 ms is correct, and the test encodes the same assumption.
- M2 `loc_offset.py` sets `title=src.stem` (`sintel_en` where the docs have `sintel`), leaves `lang=None` and has no timed `target.frames`; the shift in frames exists only in the description string, which the test parses.
- M4 `push` is not idempotent: a rerun creates a duplicate project and storage.
- M5 The downloader only checks zip magic bytes: an HTTP 200 HTML error page would be hashed and recorded as the trusted checksum (the first checksum is trust-on-first-use, and Tears of Steel has no published md5 to cross-check like Sintel's); an unknown `--set`/`--title` raises a raw `KeyError`.
- M6 The README runs everything through `uv run python -c "from ... import app; app()"` (a short `python -m eval.labeling.labeling` / `lbl` form was added in the fix round) and starts Label Studio with a hand-written `docker run` where project-structure.md specifies `docker compose --profile labeling up` on :8081.
- Spec note: the manifest lists Cosmos Laundromat as `CC-BY-4.0` where docs/evaluation.md line 23 says `CC BY 3.0`; no note explains it (see [doc-corrections.md](doc-corrections.md), unresolved).

**Could not be verified:** frame mapping beyond the single PSNR point (global frame 3000), the real downloads and timings, the Label Studio container run, and whether `compose.yaml` provides a `labeling` profile (it does not; deferred from 1.5).

## 1.11 Eval metrics and MLflow logging

**Review:** spec pass with documented, acceptable gaps (all "no pipeline in Phase 1"), quality approved with two Important to fix or consciously accept. Critical 0, Important 2, Minor 9.

**Important**
1. **I-1 Equivalence-mapped TPs were booked under the label's check, distorting per-check precision.** A `cont.prop_text` flag matching a `plot.prop_provenance` label counted as a TP only under `plot.prop_provenance`, inflating that check's precision and showing `cont.prop_text` with no TP; both checks have separate MVP precision targets (docs/evaluation.md:195 and :197), and native TPs were booked under the flag's check, so attribution was also inconsistent. **Fixed** (`159b005`, [B-054](decisions.md#b-054--tp-attribution-is-per-side-for-equivalent-checks)): `tp` under the flag's check (precision side), `found` under the label's check (recall side); global P/R unchanged; `native_tp` and `found` logged as metrics. New test `test_equivalence_match_is_attributed_per_side`.
2. **I-2 The ref-match path bypassed the IoU >= 0.3 rule, and context evidence could match.** `{ev.ref, ev.scene} & set(label.refs)` returned 1.0 even when frames were disjoint, and context-role evidence was considered. The implementer's note that this was "strictly stricter than IoU" was wrong: an extra OR-path only adds matches. A loc.gender flag whose context evidence lay on another label's cue could score a TP. **Fixed** ([B-055](decisions.md#b-055--overlap-rules-iou-for-timed-labels-ref-match-for-script-labels-context-ignored)): context evidence skipped; a label with `frames` matches only by IoU; ref matching only for labels without `frames`; zero-width `_iou` guard. New test `test_ref_does_not_bypass_iou_and_context_evidence_is_ignored`.

**Re-review: both addressed**, no new Critical/Important; the report states 13 passed in 60.62 s. New minors: a label carrying both `frames` and `refs` now matches by IoU only (confirm 1.9 injectors emit one or the other); per-check recall and precision now diverge for equivalence-mapped checks (readers need the note).

**Deferred minors**
- `benchmark_run_id` has second resolution and omits the variant, and `out.mkdir(parents=True)` has no `exist_ok`: two runs with the same set and seed in the same second raise `FileExistsError`.
- (Fixed in the fix round: `native_tp` is now emitted.)
- `--md` is a no-op flag defaulting to True; `--subset` is not validated (a typo silently yields an empty table).
- `exp` is interpolated unescaped into the MLflow filter string.
- Runs are grouped by the `variant` tag only: duplicate seeds, or runs on different flags/plan fingerprints under one variant, are silently averaged ("Seeds (n)" makes it visible but there is no guard).
- `eval/<run_id>/` output dirs are not git-ignored.
- (Fixed in the fix round: `_iou` zero-width union; `import mlflow` moved to the top of the test file.)
- Test gaps: `--runs` with a nonexistent ID or an empty `--exp` result (exit-1 path).

**Could not be verified:** the Label `seed` field is ignored by `load_labels` and `run` (if 1.9's injectors write several seeds into one directory, recall is computed against all seeds' labels at once); field compatibility between `eval/injectors/base.py` `Label` and `eval.metrics.Label` (the integration step should run `load_labels` over a real inject output); behaviour against the 1.5 compose MLflow (only sqlite was exercised); that about 12 metrics per scope times 60+ scopes stays under MLflow's batch limits (the reviewer's estimate, not a measurement).
