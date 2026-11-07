# Review Findings

Every Phase 1 deliverable (wave 1 and wave 2: 1.1 to 1.11), and every Phase 2 deliverable from 2.0 to the Phase 2 closeout, was reviewed by an independent reviewer agent that did not write the code (spec compliance first, then code quality), and anything rated Important was sent back to the implementer as a fix round and then re-reviewed. This file records, per deliverable: what the review found, how it was fixed, and the minor findings that were deliberately deferred. It is the "the review caught X, we fixed it by Y" material.

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
| 1.7 Ray Serve, clients, EXP-001 | `f35045e`, `33fe525`, `989e0ed` (EXP files in `6854081`) | pass | approved | 0 | 2 | 9 | `989e0ed` | addressed |
| 1.8 part A Media, shots, keyframes | `829a3b3`, `72a7ea5` | pass (one gap) | changes needed | 0 | 3 | 8 | `72a7ea5` | addressed |
| 1.8 part B Real film, EXP-002 | `6854081`, `be9daac` | pass (one gap) | changes needed | 0 | 3 | 7 | `be9daac` | addressed |
| 1.9 Corpus, injectors, Label Studio | `d4cb1c2`, `dab96fc` | pass | changes needed | 0 | 4 | 6 | `dab96fc` | addressed |
| 1.10 Walking skeleton | `77257b6`, `2d0bf6a` | pass | approved | 0 | 0 | 7 | `2d0bf6a` (3 minors) | addressed |
| 1.11 Eval metrics, MLflow | `a329f4a`, `159b005` | pass | approved | 0 | 2 | 9 | `159b005` | addressed |
| **Total** | | | | **0** | **23** | **91** | 10 fix rounds (the 1.10 round fixed Minors only) | all Important addressed |

Counts are as stated in the reviews and the ledger (initial reviews; the re-reviews' extra minors are listed per deliverable). No re-review found a new Critical or Important finding in a fix diff. The 1.2, 1.4 and 1.10 reviews found nothing Important. Across all eleven deliverables: 0 Critical, 23 Important, 91 Minor.

### What the pattern says (good interview framing)

- **Tests that could not fail.** Three of the Important findings were tests or justifications that did not discriminate: the 1.8 frame-exactness test (would pass with a uniform seek offset), the 1.3 numbered-PDF test (number and heading written as one string, so it could not see a separate-x number), and the 1.11 claim that a shared-ref match was "strictly stricter than IoU" (an extra OR-path can only add matches). In each case the fix included proving the new test fails on the old code.
- **Two hand-maintained copies drift** (1.1 schema vs migration): fix was a real-database catalog diff, with four injected drifts as proof.
- **Specs that contradict themselves** (1.6 step 7 vs the docs' own worked example; 1.9's cut labels vs the Flag format) were escalated for a controller ruling instead of silently picking one.
- **The real run found what the review and the unit tests could not** (wave 2): the zombie EngineCore that made unload 33.1 s instead of 4 s only appeared when the I2 fix ran against real vLLM (1.7); the shared-GPU premise in the ledger was checked against the packer and found wrong, so it was pinned with a test instead of "fixed" (closeout).
- **Overclaiming caught in prose, not code** (1.8B): two decision rationales that no run supported ("adds fades/dissolves handling", "no tuning knob to overfit") and a lead sentence that hid a verdict flip; the fix was to withdraw them and put the flip first. The 1.10 CPS test and its "17/18 CPS" claim are the same class as the wave-1 tests that could not fail.
- **Reviewers re-derived numbers from raw artifacts**, not from the notes: 1.7's reviewer recomputed the KV arithmetic and the planner's laptop examples by hand; 1.8B's re-queried the MLflow DB, recomputed TransNetV2's false negatives from the saved probabilities and re-scored with widened masks; 1.10's cross-checked flag counts independently.
- **A written bar can be wrong about the world** (EXP-001): by its own success criterion the answer was gmu 0.86; the evidence (0/3 under pressure at 0.75 and 0.83, a mechanism visible in vLLM's log) led to a controller ruling for exact KV budgets, with the reviewer listing what the evidence did not prove.
- **Observed behaviour beat assumptions** (1.5 `KC_IMPORT_REALM` ignored by Keycloak 26.6; 1.9 Label Studio exporting only annotated tasks unless `download_all_tasks=true`), which is why live verification was part of the fix rounds.

## Phase 2 summary (2.0 to 2.9A, W-int, W-serve, closeout)

Phase 2 followed the same process. One difference: several re-reviews found a new Important problem in the fix itself, which then needed another round; those are counted separately in brackets. 2.9B-1 had no independent review before this log was written (its report and a controller review of the stopped work are in the [journal](journal.md#2026-11-06--29b-1-stage-cache-incremental-re-runs-and-get-runsiddiff)).

| Deliverable | Commits | Spec | Quality | Critical | Important | Minor | Fix round | Re-review |
|---|---|---|---|---:|---:|---:|---|---|
| 2.0 Store spine | `f6c3506`, `5989485`, `870c54b`, `0a086a1`, `9d0727d` | pass | changes needed | 0 | 3 (+1 in re-review) | 9 | `0a086a1`, `9d0727d` | addressed (two re-reviews) |
| 2.1 Fact extraction, grounding, resolution, consolidation (+ EXP-006, EXP-020 W1) | `38fa323`, `6b2ddf4`, `608c5a1` | pass | approved with fixes | 0 | 2 (+1 new in re-review: N-1) | 10 | `6b2ddf4`, `608c5a1` | addressed (re-review 1 found N-1; re-review 2 addressed) |
| 2.1B Runaway guard, argument checks, EXP-005/006/018/020 on real models | `b8d320b`, `bbf653a`, `dc4e6fc`, `bb68eac`, `22074b9`, `8a5d5bd`, `11d03c4`, `962512f`, `dd557fe` | pass (⚠️ two decision records) | acceptable, 3 Important follow-ups | 0 | 3 (+3 new in re-review: N1–N3) | 9 | `22074b9`, `8a5d5bd`, `11d03c4`; `962512f`; `dd557fe` | addressed after 3 rounds (round 1 found N1–N3; round 2 N3 partial; round 3 N3 addressed) |
| 2.2 Story order and story days | `6ad9a53`, `ad1b1b9` | partial (3 gaps) | good, with defects | 0 | 3 | 7 | `ad1b1b9` (also M1-M3) | addressed |
| 2.2B EXP-007 ambiguous-transitions variant and harness | `11354bc`, `23f13d4`, `6dc6ba8` | pass | good, approve with minors | 0 | 1 | 6 | `6dc6ba8` (also M3, M5) | addressed |
| 2.3 Script Critic Layer 1 | `35a33ca`, `3aa1594` | pass (one integration gap) | approved with fixes | 0 | 2 | 7 | `3aa1594` (also M-4, M-5, M-6) | addressed |
| 2.4 Cue alignment, loc.term/shot_change/drift/offset | `fa1f18c`, `313ccd0` | fail (3 spec gaps) | approved with fixes | 0 | 4 | 6 | `313ccd0` (injector follow-up `be494b4` in W-int) | addressed |
| 2.5 ASR + script-transcript alignment, EXP-003/004 | `7c20c54`, `bd74e53`, `abadd4c`, `0440e1d`, `051534b`, `fa47838` | pass (with gaps) | approved with fixes | 0 | 3 | 9 | `0440e1d`, `051534b`, `fa47838` | addressed |
| 2.6 OCR channel + Presidio recognizers | `9b6787a`, `1507da1`, `eafce85`, `9c3bf5a`, `fa95853`, `3c1a5de` | pass (with caveats) | approved with fixes | 0 | 3 (+1 in re-review) | 13 | `fa95853`, `3c1a5de` | addressed (2 rounds) |
| 2.7 Clearance matching, occurrences, CSV, clr.* flags; EXP-008, EXP-017 | `4c131c1`, `2407222`, `e464917`, `e778928`, `f324627`, `cda802e` | fail (pending rulings) | approved with fixes | 0 | 6 (+1 in re-review) | 8 (+4 in re-review) | `f324627`, `cda802e` | addressed (round 1 raised N1; round 2 addressed, no new findings) |
| 2.8 Scene vector index, hybrid retrieval | `300b09b`, `7a664c1` | pass | good | 0 | 0 | 9 | none needed | n/a |
| 2.9A Injectors, synthetic show, sidecars | `2e3cb6e`, `2894fdd` | pass (deviations recorded) | approved | 0 | 3 | 7 | `2894fdd` | addressed |
| W-int Wiring, integration fixes, image smoke, end-to-end runs | `be494b4`, `3d66622`, `ff7b038` | pass | approved | 0 | 1 | 5 | `c02a542` (in W-serve) | verified by the W-serve review |
| W-serve Real models for `nip run` (staged serving in ray-head) | `c02a542`, `dff0f7f` | pass (caveats) | approved with fixes | 0 | 3 | 7 | `dff0f7f` | addressed |
| 2.close Phase 2 closeout | `d5ef357`, `5f65199`, `d2a8fa3`, `7532221`, `ddf6206`, `c0988ee`, `cf6724e` | pass | good | 0 | 2 | 7 | `ddf6206`, `c0988ee`, `cf6724e` | addressed |
| **Total** | | | | **0** | **39 (+7 in re-reviews)** | **119** | 14 deliverables needed fix rounds | all Important addressed |

Counts are the initial reviews' (the bracketed Important findings were raised by re-reviews of a fix; 2.7's re-review also added 4 minors that are not in the total). 2.8 was the only deliverable with nothing Important. Across Phase 2: 0 Critical, 46 Important (39 + 7), 119 Minor.

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

## 1.7 Ray Serve deployments, clients, EXP-001

**Review:** spec pass (every item compliant, with one integration blocker outside 1.7's file ownership, I1), quality approved with two Important items. Critical 0, Important 2, Minor 9. Reviewer checks (read-only): `ruff check` on the 1.7 files clean; `pytest tests/unit/runtime/test_serving.py test_clients.py` 12 passed in 4.2 s; `stub_instance` over every Pydantic model in `nip.contracts`: 13 ok, 2 fail (`Fact`, `Flag`, custom validators). No GPU, Docker or MLflow access.

**Critical: none.** The reviewer examined the failure path specifically: a failed vLLM start stops its process group before raising, `run` tears the whole group down in `finally` (including the app that failed and any earlier ones), `max_constructor_retry_count=1` stops Serve's 20-attempt default, and the 6 real failed starts (the active-pressure trials) all returned to idle (66/66 in total).

**Important**
1. **I1 With the stock catalog the laptop Plan served the bf16 base model.** `Variant.repo` is `checkpoint or base_model`, and `config/catalog.yaml` had no `checkpoint` for `qwen3.5-4b-awq`, so `apps()` would pass the 8.68 GiB bf16 repo to `vllm serve` on an 8 GB GPU and every real laptop run would fail at the LLM group. EXP-001 and the integration test both overrode the checkpoint in code, so **no real run had ever used the shipped path**, and a unit test even asserted the base model. **Fixed** (`989e0ed`, [B-082](decisions.md#b-082--checkpoint-for-qwen35-4b-awq-is-cyankiwiqwen35-4b-awq-4bit-in-the-catalog)): checkpoint added to the catalog, the assertion flipped, the overrides removed, and a new `--setting plan` arm runs the true shipped path (probe, planner, `apps`).
2. **I2 `VllmServer.stop()` skipped the process-group kill when the main process had already exited.** The group exists because EngineCore is a separate child; if the API server dies but EngineCore survives, the orphan keeps its VRAM and the replica restart that the architecture relies on then fails for memory. **Fixed** ([B-087](decisions.md#b-087--stop-always-kills-the-process-group-and-liveness-ignores-zombies)): always SIGTERM the group, wait, SIGKILL after 30 s. **The first real run of the fix found a second problem the review could not see**: unload took 33.1 s because the orphan became a zombie under the container's PID 1; liveness now ignores zombies and unload is 4.0 s ([C-012](experiments.md#c-012--unload-time-331-s-down-to-40-s-the-zombie-enginecore)).

**The EXP-001 evidence review (evidence only; the controller rules)**
- **Traceability:** the table is the output of `table` over MLflow runs tagged `exp=EXP-001`, with all 66 run IDs listed; pilots tagged separately; backfilled metrics trace to logged artifacts, not edits. Internal arithmetic checks (960 MiB = 1,006,632,960 B; 2.64x = 2 x 60 / 44.6).
- **Success bar as written:** highest 10/10 setting is 0.86; exact KV gives less KV, so by the bar the planner does not switch. The implementer reported this correctly.
- **Proposal 1 (exact KV instead):** *partly supported*; for and against are listed in the [EXP-001 takeaway](experiments.md#takeaway) (synthetic pressure with n = 3; gmu 0.86 also survived at 1.52x; the planner would already skip the LLM at 6.04 to 6.07 GiB free unless the desktop grows after probing; about 47 MiB device headroom and tokens/s about 82 under pressure; variant (c) unmeasured).
- **Proposal 3 (AWQ repo):** supported (served in all 66 trials plus the integration test); third-party, provenance not verified.
- **KV 44.6 MiB/1k:** supported to about +-1.5 % (range 44.0 to 44.7 per 1,000; marginal slope across the gmu settings about 44.0).
- **Startup peak 6.25 GiB:** the number is supported (6,397 +- 9 and 6,400 +- 2 MiB, idle desktop); **the attribution was inconsistent** (called "profiling" while also saying exact KV skips profiling), and the steady estimate for exact KV (4.43 + 0.94 GiB) is about 5.4 GiB, so about 0.9 GiB came from some other warmup step. The fix round corrected the attribution from vLLM's source and left about 1.8 GiB explicitly unattributed.
- **Background caveat:** the 10/10 trials ran at 7,643 to 7,743 MiB free (desktop holding about 450 MiB), an unusually idle laptop.

**Re-review: both ADDRESSED; the ruling is implemented correctly.** The reviewer re-derived the planner's units (GiB throughout), checked that the margin is subtracted once and that `plan()` stays pure, reproduced the laptop worked examples by hand (7.15 free: usable 6.65, 16k needs max(5.92, 6.25), gmu 0.79, KV 2,170 MiB; 7.6 free 2,631; 8.0 free 2,734; 6.6 free skipped), and confirmed the 48 GB case is not starved ([C-019](experiments.md#c-019--exact-kv-budget-vs-the-old-gmu-sizing-on-big-gpus)). New Critical/Important: none. The reviewer read `/proc/<pid>/stat` handling (split on the last `)`), and the zombie-aware liveness as correct. Verdict: "1.7 can close; N1, N2 and N4 are worth a one-line follow-up before EXP-015."

**Deferred minors**
- M1 (the teardown error masked the deploy error): **fixed**. M3 (`assert` for input validation, vanishes under `-O`): **fixed** (`ServingError`). M4 (a bench exception skipped teardown and MLflow in an EXP trial): **fixed**. M7 (every non-PNG image labelled JPEG): **fixed** (sniffs PNG/GIF/WebP). M8 (truncated `pyproject.toml` comment): **fixed**.
- M2 (each group re-measures its own idle, so small leaks compound; or desktop growth aborts a run): **declined** with a reason ([B-077](decisions.md#b-077--teardown-waits-for-vram-to-return-to-idle-plus-256-mib-measured-per-group)).
- M5 (stub gaps: `exclusiveMinimum + 1` can exceed `maximum`, `uniqueItems`, `pattern`/`maxLength` ignored; `Fact` and `Flag` need a hand-made stub): recorded for Phase 2.
- M6 (`LLMClient` does not go through `instructor` as D-025 says): deferred to 2.1.
- M9 (the fifth laptop load, the judge, is never exercised; the staged loop is verified on 4 of 5 loads): open until the ministral weights are pulled (4.6).
- **Re-review minors:** N1 (1k = 1,000 in the calibration vs 1,024 in the planner, about 2.4 % low): **fixed in the closeout** ([B-115](decisions.md#b-115--kv-calibration-restated-per-1024-tokens-446---458)). N2 (on a GPU shared with actors the exact budget absorbs the leftover): premise checked and found wrong, **pinned with a test** ([B-117](decisions.md#b-117--shared-gpu-exact-kv-the-premise-was-wrong-pinned-with-a-test-instead-of-changed)). N3 (table tests do not assert `kv_cache_bytes`): **fixed** (`test_expected_kv_budgets`). N4 (`kv_cache_bytes` accepts 0): **fixed** ([B-116](decisions.md#b-116--the-kv-budget-must-be-positive-zero-is-rejected-not-ignored)). N5 (`stop()` breaks after SIGKILL without waiting for the group to die): open. N6 (the GPU integration test skips when the probe leaves no room for the LLM, so a busy desktop can make it pass vacuously; the group-order assertion was also dropped): open. N7 (docs not updated): in [doc-corrections.md](doc-corrections.md).

**Could not be verified by the reviewer:** that MLflow "EXP-001" holds the 66 runs with the tabled values (Postgres in a Docker volume, stack down); the integration run output and timings (only the notes); whether `serve.delete` of an app that never reached the controller is a no-op in Ray Serve 2.58; vLLM 0.30 with TP > 1 in a fractional or multi-GPU Serve replica; that the stack was left down.

**Process note:** the EXP files went into 1.8B's commit through that agent's directory pathspec (not a 1.7 fault; [B-121](decisions.md#b-121--commit-by-explicit-file-paths-not-directory-pathspecs)).

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

## 1.8 part B: real-film run and EXP-002

**Review:** spec pass with one gap (S1), quality **changes needed**. Critical 0, Important 3, Minor 7. Checks (read-only): `pytest tests/unit/eval/test_exp002_shots.py` 3 passed; the reviewer queried `data/mlflow/mlflow.db` (9 default runs, per-run F1, precision, recall and seconds equal the notes); recomputed TransNetV2's 28 false negatives from the saved probabilities (8 in frames 1,036 to 1,572, 15 in 13,104 to 14,455, median 0.22, 7 below 0.1, 10 in 0.1 to 0.3, 11 in 0.3 to 0.5; median 0.93 on found cuts), all matching the notes; recomputed with mask windows widened by the tolerance (only TransNetV2 changes, 0.917 to 0.921); the label file is 183 cuts, sorted, unique. The scorer was judged correct (a maximum matching for a uniform window, no reuse, inclusive +-2).

**Important**
1. **I1 The ground truth's provenance was not in the repo.** The per-event decisions and contact sheets were in git-ignored `data/exp002/labelling/` and the label header said nothing about how cuts were verified (the brief required it). **Fixed** (`be9daac`): `sintel_cuts.provisional.verification.json` and `sintel_cuts.provisional.decisions.txt` committed next to the labels, generated by `label_sheets.py verification` ([B-092](decisions.md#b-092--provisional-labels-by-candidate-union-and-contact-sheets-with-a-committed-verification-record)).
2. **I2 The notes overclaimed and buried the flip.** The decision text said TransNetV2 "adds fades/dissolves handling" (every dissolve was masked, so there is no evidence) and has "no tuning knob to overfit as badly as AdaptiveDetector" (while the same paragraph recommended tuning TransNetV2's threshold); and the lead sentence "bar met" hid that the same-label tuned comparison (+0.021 for Adaptive) is above the bar in the other direction. **Fixed:** both rationales withdrawn, the flip stated first in the notes and Takeaway, and the keep-TransNetV2 call reworded as cost/risk ([B-093](decisions.md#b-093--exp-002-decision-keep-transnetv2-provisionally-as-a-costrisk-call-not-a-result)).
3. **I3 The tuned numbers were not in MLflow.** The Takeaway's headline numbers (tuned 0.946 / 0.891 / 0.967, held-out, resize F1s) existed only as stdout in git-ignored logs; only the defaults traced to MLflow. **Fixed:** `sweep`, tuned selection, `split` and `resize-test` log to MLflow (24 + 3 + 6 + 8 runs), reruns replace their own earlier runs, and the notes have a "where every number comes from" table.

**Re-review: all three ADDRESSED**, with the MLflow query reconciling the tuned, held-out, sweep and resize values. New minors from the fix: the report says held-out TransNetV2 **0.928** where the runs give 0.9274 (0.927 is used in this log); the labels header does not link the verification file; the verification file is *reconstructed* (hard-coded zoom set `{26, 41, 209, 211, 212, 574}` plus frame 15867; `first_pass_sheet` computed as `event // ROWS`), so it records the agent's recollection, not a trace; `_clear` builds a client per point; the report's header still says "bar met at defaults" above the appended correction.

**Deferred minors**
- M1 (precision 1.00 is also seed-dependent through anchoring): written into the bias section. M2 (`shown/*` naming), M4 (`run` defaults to `repeat=1` while the timings are 3 repeats), M6 (`split` order dependence): docstring notes. M3 (mask edges not widened by the tolerance, 5 labels, +0.004): recorded as a known limit. M7 (only 3 tests): a randomized brute-force check against scipy added (200 cases).
- M5 (`label_sheets.sheets()` duplicates `_render`): left open as a one-off helper.

**Could not be verified by the reviewer:** that the agent actually inspected each of the 646 events (the rate-limit episode and the redo; the sheets are not in the diff); part A real-film numbers beyond the Sintel default runs; the resize and sweep tables (not recomputed); label positions against Label Studio's numbering (these labels bypass `pull`); that nothing from the blind draft survives. Treat the 183 cuts and 20 masks as unverified until a human pass.

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

## 1.10 Walking skeleton: `loc.readability` end to end

**Review:** spec pass, quality **approved**. **Critical 0, Important 0, Minor 7.** The reviewer checked every requirement (rules, rule-pack values, tag fallback, activation, severity, verification not importing agents, pipeline, CLI wiring, real Sintel run, tests, both exit criteria) and then adjudicated the implementer's four self-reported concerns: (a) the circular 1.00 is real and slightly worse than stated (ref-only labels mean a flag for the wrong rule on a planted cue still scores TP), acceptable for a skeleton because disclosed, but the number must not be cited as check quality until the seconv-lint oracle exists; (b) gap-closing as 15 of 20 flags all `must_review` is documented behaviour and a product decision, not a defect; (c) the file-based `nip run` is an accepted deviation (the documented form needs the store); (d) the 9 s startup is real and owned by other modules' eager imports.

**Minor** (no Important, so the fix round took only the load-bearing ones)
- M1 **fixed** (`2d0bf6a`): the rule-pack path `parents[4]/config/languages` would break in the non-editable Docker install, so every language would be rejected with "no rule pack"; the same pattern was in `picture.py` and `catalog.py`; one shared `config_dir()` ([B-112](decisions.md#b-112--nip_config_dir-with-auto-detection)). The reviewer's point that this wants one shared fix, not per-module patches, is why it is a helper.
- M2 **fixed**: the CPS test text was 16 characters, not 17, so it passed whether or not line breaks were counted and never exercised the 17-CPS boundary (and had a dead no-op expression); the notes' claim "17/18 CPS with spaces counted and line breaks not" was inaccurate. Now two assertions that each fail under the wrong rule, with the lengths asserted. This is another "test that could not fail" finding.
- M5 **fixed**: eager torch/mlflow/scipy imports gave every `nip` call a 9 s startup; `nip --help` 10.4 to 10.9 s to 1.1 to 1.2 s ([C-013](experiments.md#c-013--nip-cli-startup-109-s-down-to-11-s-lazy-imports)).
- M3 **accepted:** `nip run` occupies the documented command name with an incompatible signature; Phase 2 must replace it (a breaking CLI change); kept as a doc correction ([B-103](decisions.md#b-103--srcnippipelinepy-is-the-phase-1-composition-root-and-nip-run-takes-files)).
- M4 **disclosed:** benchmark scoring is self-referential (shared rule pack, ref-only labels, machine-triaged native labels with `reviewed: false` where evaluation.md requires a person); needs human sign-off and the D-030 oracle before any number is quoted ([C-018](experiments.md#c-018--walking-skeleton-benchmark-prf1-100-on-planted-readability-errors-and-why-it-proves-little)).
- M6 open: a last-cue overrun is dropped into `dropped.jsonl` by the "inside the episode" rule rather than reported (spec-consistent; worth a dedicated "cue outside picture" finding later).
- M7 open: robustness nits (`ev.quote not in span.text` with `span.text is None`, `--picture` lacks `dir_okay=False`, a `--script` with a subtitle extension crashes with AttributeError instead of `INPUT_REJECTED`).

**Re-review (scoped to M1, M2, M5): all three ADDRESSED**, no new Critical or Important. The reviewer grep-checked that no repo-relative config path remains (only `media.py:20`'s FFmpeg lookup, not config and overridable by `NIP_FFMPEG_DIR`), verified Dockerfile `WORKDIR /app`, `COPY config ./config` and `ENV NIP_CONFIG_DIR=/app/config` agree and nothing in compose masks `/app/config`, showed with `importtime` that `import nip.cli` pulls in no torch, mlflow or scipy, and confirmed the edit to 1.8's `test_shots.py` (patch moved to `shots.detect_shots`) kept its assertions. New minors: `load_catalog` is not exercised under `NIP_CONFIG_DIR`; anyone importing `detect_shots` from `nip.timeline.picture` would break (no caller found).

**Could not be verified by the reviewer:** test counts (not re-run); that the Sintel `picture.json` (produced by a scratch conversion from 1.8B artefacts) matches `analyze_picture` output beyond the reported 398/398 keyframes and 162 shots; the real-run numbers; M1's Docker failure was inferred from the install command and not run (the image was not built).

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

**Later (2.0, `5989485`):** the run-id collision, `--subset` validation, the unescaped `exp` filter and the grouping guard were fixed ([B-149](decisions.md#b-149--nip-eval-compare-prints-every-logged-metric-and-refuses-mixed-groups-r10)); `--md` is still a no-op.

**Could not be verified:** the Label `seed` field is ignored by `load_labels` and `run` (if 1.9's injectors write several seeds into one directory, recall is computed against all seeds' labels at once); field compatibility between `eval/injectors/base.py` `Label` and `eval.metrics.Label` (the integration step should run `load_labels` over a real inject output); behaviour against the 1.5 compose MLflow (only sqlite was exercised); that about 12 metrics per scope times 60+ scopes stays under MLflow's batch limits (the reviewer's estimate, not a measurement).

## 2.0 Store spine

**Review:** spec pass (the per-episode report key, refusing replacements, the `run-files` rename and refs built in `load.py` accepted as documented deviations), quality **changes needed**. **Critical 0, Important 3, Minor 9.** The reviewer ran ruff and mypy on the 2.0 files (clean) and one read-only query on the dev Postgres (runs 1 and 2 each have 6 flags with 6 distinct fingerprints, the sets identical, run 2 `previous_run_id=1`). The problems were in the conventions the five W1 deliverables would build on and in what a failed run leaves behind.

**Important**
1. *I1 The stage contract could not record a content stage's units or gaps, and stages could not see the Plan.* `coverage()` raised `KeyError` on a non-check unit, `stage_checks` would double-insert units a stage wrote, and the only way for a stage to signal failure was to fail the whole run, contrary to architecture.md's coverage-gap rule. **Fixed** (`0a086a1`): `EpisodeRun.plan` is the real `Plan`; `with ep.unit(...)` records `done` / `failed` and a failure is a gap; units inserted once per episode; coverage counts check units only ([B-140](decisions.md#b-140--run-lifecycle-and-the-stage-contract-epunit-gaps-coverage-from-check-units)). A latent `executemany` bug (columns from the first row dropped the `error` text) was found by the new test and fixed.
2. *I2 Run artifacts were published before the transaction committed,* so a failed run left "completed" reports listing flag ids that were rolled back and never exist. **Fixed** (`0a086a1`): `publish()` after `conn.commit()`; `test_failed_run_publishes_no_artifacts` ([B-141](decisions.md#b-141--artifacts-are-published-only-after-the-commit-the-whole-run-is-one-transaction)).
3. *I3 The R13 fingerprint collapsed for flags whose evidence is only `fact/` / `asr/` refs:* every such flag of a check, across episodes, shared one fingerprint, so dispositions and run diffs would merge them. **Fixed** (`0a086a1`) by controller ruling: at least one stable ref per flag, `fingerprint` raises, `require_stable_refs` drops and counts ([B-147](decisions.md#b-147--every-flag-must-carry-at-least-one-stable-evidence-ref)).

**Re-review 1 (`2.0-rereview.md`): I1, I2, I3, m1 addressed; one new Important.**
- *N1 `ep.unit()` had no savepoint:* a failed unit's partial rows were committed with a `completed_with_gaps` run, and a DB error inside a unit aborted the Postgres transaction so every later unit failed with `InFailedSqlTransaction` and the run died with a misleading error. **Fixed** (`9d0727d`): `conn.begin_nested()` per unit ([B-148](decisions.md#b-148--each-work-unit-runs-in-a-savepoint-a-malformed-evidence-ref-is-a-counted-drop)); test `test_failed_unit_rolls_back_its_rows_and_does_not_poison_the_next`.
- Minor m-a (a malformed evidence ref crashed the run instead of dropping the flag) **fixed** in the same commit. Deferred: m-b (stable-ref drops carry no `verification` results), m-c (drops are not persisted to the DB or S3 report), m-d (an S3 upload failure after commit leaves a `completed` run with no report; accepted as the lesser failure), m-e (`unit()` now also swallows exceptions from `emit`; noted as a behaviour change).

**Re-review 2 (`2.0-rereview2.md`): N1 and m-a addressed**, no new Critical or Important. `KeyboardInterrupt` / `SystemExit` still abort through `run_store`'s rollback. Residual: a raise from the savepoint RELEASE itself would fail the run rather than count a gap (practically unreachable); a body that calls `conn.commit()` itself would break the savepoint (no stage does). The reviewer ran `tests/unit/test_pipeline.py` (10 passed); the integration test was read, not run.

**Minors (original review)**
- m1 **fixed** (`0a086a1`): the report's advice of repeated `STAGES.insert(0, ...)` would reverse the stage order; `add_stage(name, fn, before="timeline")`.
- m2 **fixed**: `code_version` showed no dirty tree (the dev DB runs recorded the deps commit `1507da1` while running uncommitted 2.0 code); `-dirty` suffix added.
- m3 **fixed**: `previous_run_id` depended on `--episodes` order; stored and compared sorted.
- m4 **fixed**: show slug unvalidated though it goes into S3 keys; now `[a-z0-9][a-z0-9_-]*`.
- m5 **deferred**: `analyze_picture` runs inside the open ingest transaction (matters for an uncached feature film).
- m6 **fixed**: `--picture` for an already-ingested video is now warned about.
- m7 **fixed**: `_bind` bound by the first slot only; now raises when an app's slots resolve to different actor classes.
- m8 **not changed**: `POSTGRE_PASSWORD` in `.env.example` is Label Studio's own variable name, not a typo.
- m9 passed to the controller: 2.6's `clients/ocr.py` / `ner.py` hard-code `SERVE_URL = "http://127.0.0.1:8000"` instead of `NIP_SERVE_URL`.

**Could not be verified by the reviewer:** the Sintel done-criterion numbers (6 flags identical to the 1.10 run, 614 spans, 48.4 s / 11.7 s) beyond the fingerprint identity and run rows in the dev DB; the test counts (not re-run); `lint-imports` and the `uv.lock` resolution (rich 15.0.0 → 14.3.4); `compose.dev.yaml` end to end with SeaweedFS auth and Serve on 8001; whether `scene_lines` can return 0 for a scene.

## 2.1 Fact extraction, grounding, entity resolution, consolidation

**Review:** spec pass, quality **approved with fixes**. Critical 0, Important 2, Minor 10. The reviewer checked every done criterion against data-model.md › Knowledge layer, D-005, D-025, tech-stack's build notes and 2.0's stage contract; ran the 27 unit tests; confirmed instructor 1.17's `Mode.JSON_SCHEMA` sends a native `json_schema` `response_format`; probed rapidfuzz; recomputed EXP-006's kept rate (140/150 = 0.933 at every threshold) and spot-checked 14 hallucination labels; checked EXP-020 candidate crediting (0 of 271 free-text candidate arguments credited to a registry truth id); and showed consolidation satisfies the `fact_consolidated_no_overlap` EXCLUDE constraint by construction (merge key = the constraint's key, half-open overlap test, no empty ranges, NULL-object facts merged by value).

**Important**
1. **I-1 Entity resolution false-merged any name containing a short registered name.** WRatio with `score_cutoff=90` (inclusive) returns `partial_ratio × 0.9` when the length ratio is ≥ 1.5, so any containment scores exactly 90: "tomato" → Tom, "Dover Street" → Dov, "Ruins" → Rui; no candidate was created, so the review queue never saw the error. The synthetic names are disjoint, so EXP-020 could not catch it; raising the threshold alone would break "Ada" → "Ada Kovac". **Fixed** (`6b2ddf4`): whole-word subset with at least half the words, else `ratio`; the reviewer's `token_set_ratio` rejected (reverse containment). Tests `tests/unit/knowledge/test_entities.py` (4). See [B-161](decisions.md#b-161--names-match-on-whole-words-subset-with-at-least-half-the-words-an-exact-name-scores-101), [C-22](experiments.md#c-22--entity-name-scorer-wratio-vs-whole-word-subset-vs-exact-first).
2. **I-2 Fact ids churned on every consolidation**, so earlier flags' `fact/{id}` evidence stopped resolving (`load_timeline` resolves active facts only) and every re-run added the whole show's facts as superseded rows. Flags still carried stable line refs, so no evidence was lost, but D-005's "evidence must resolve" was defeated for fact refs. **Fixed** (`6b2ddf4`): identity diff, unchanged facts keep their ids, `supersedes` set on replacements; integration assertions (no-op re-run adds 0 rows; ≥ 80 % of S01E01 ids survive S01E02). See [B-158](decisions.md#b-158--consolidation-re-runs-show-wide-and-keeps-the-ids-of-unchanged-facts).

**Re-review 1** (`2.1-rereview.md`, unit tests 74 passed; integration not re-run, no DB): I-1 and I-2 **ADDRESSED**, with a probe table of 21 surfaces. **New Important N-1:** an exact name tied with subset matches at 100, so ambiguous surfaces minted a new candidate on every mention (four "Vale" calls → candidates 100–103; three "Ada Kovac" calls → 104–106), fragmenting facts across duplicates and leaving "ADA KOVAC" speakers NULL when "Ada Maria Kovac" exists. **Fixed** (`608c5a1`): exact normalized name scores 101; whitespace collapsed. New minors: M-a `supersedes` lineage keeps only the last id when several old facts share (predicate, subject, object); M-b episode-1 flags citing a fact later closed by episode 2 stop resolving.

**Re-review 2** (`2.1-rereview2.md`): N-1 **ADDRESSED**; no new Critical or Important. Minor: a bare surname candidate ("Vale") absorbs every later bare "Vale" (intended reuse).

**Minor, fixed in `6b2ddf4`:** M-4 one-word quotes grounded any invented event (`score("a", …) == 100`); M-6 EXP write-up caveats; M-8 object-less holds/owns treated as one object; M-9 silent stub fallback; M-10 an integration assertion that held only by coincidence (`sum(raw learns) == len(quotes)`).

**Deferred minors**
- M-1 raw events uploaded to S3 inside the stage (against 2.0's artifacts-after-commit rule) → done by W-int (item 4a, `EpisodeRun.artifacts` uploaded by `publish`).
- M-2 `fact_event.work_unit_id` NULL (accepted; linking left to 2.9B).
- M-3 `ruff format` over the shared `src/nip/knowledge/` directory (formatting only, self-reported, cannot be verified).
- M-5 `config/pipeline.yaml` `knowledge:` keys not added (controller ruling kept constants) → moved by W-int (`3d66622`).
- M-7 registry key collisions (`kind:name` proposal, not built).
- Re-review M-a, M-b (above); recall costs of the matcher: honorifics, possessives on one-word names, lone middle names go to candidates.
- Controller items: untracked `mlruns/` in the checkout (origin unknown); the dev DB migrated to 0002 with `synthetic-show` ingested; `fact_correction` retractions not carried into re-consolidation (Phase 4).

**Could not be verified by the reviewers:** the I-2 integration assertions in both re-reviews (no `NIP_TEST_DATABASE_URL`; taken from the report); M-3's formatting scope.

## 2.1B Runaway guard, argument type checks, knowledge experiments on real models

**Review:** spec pass (⚠️ on two decision records and lock hygiene), quality **acceptable with three Important follow-ups**. Critical 0, Important 3, Minor 9. The reviewer traced every headline number to an active MLflow run (read-only sqlite: RUNAWAY-2.1B, EXP-006, EXP-020-rules / -clean, EXP-018's 40 runs, EXP-005), re-derived EXP-006 counts from the replayed events, checked the runaway guard against truth on the shipped-pass events (zero-confidence and duplicate drops removed 0 truth events; argument-type drops removed 11 / 16 / 6 events, all with a wrong object), and ran `pytest tests/unit/knowledge` (78 passed).

**Important**
1. **I1 Multi-paragraph action lines were rendered under one number; the model cited the second paragraph as the next line, so prop events were dropped**, and the notes' diagnosis ("props not in the registry") missed this pipeline cause. Also: the two_places lines name no place, a design gap a derived `present_at` could cover. **Fixed** (`22074b9`, fixtures `8a5d5bd`): one printed line per `script_line`; derived speaker presence (D-2.1B-1); re-measured on real facts: enum found 1 → 10 of 36, free text 0 → 9 (17 with the holds vocabulary). See [B-169](decisions.md#b-169--the-prompt-prints-one-numbered-line-per-script_line), [B-170](decisions.md#b-170--resolved-dialogue-speakers-are-present-at-the-headings-location-d-21b-1), [C-26](experiments.md#c-26--one-printed-line-per-script_line-quote-drops-before-and-after).
2. **I2 A candidate's guessed kind became a hard type constraint for every later event** (order-dependent drops). **Fixed** (`22074b9`): candidate kinds provisional; test `test_a_candidates_guessed_kind_does_not_drop_later_events`. See [B-171](decisions.md#b-171--a-candidate-entitys-guessed-kind-is-provisional).
3. **I3 EXP-020 recorded as "done, keep the enum" without discriminating evidence** (both arms at the precision floor; enum accuracy partly by construction; 0 alias-only arguments). **Fixed** (notes rewritten): inconclusive, D-025 stands by default; EXP-018's reason restated (M4). See [B-180](decisions.md#b-180--exp-020-inconclusive-d-025-registry-ids-as-an-enum-stands-by-default), [B-179](decisions.md#b-179--exp-018-do-not-adopt-the-fp8-kv-cache).

**Minor (original review)**
- M1 duplicate detection counted dropped events (a confidence-0 copy shadowed the good event) → **fixed** (`22074b9`).
- M2 one remaining lock-leak path (`nvidia-smi` wait loop outside the `try`; a failing `down` released without confirmed idle) → **fixed** with `gpu_session` (`22074b9`).
- M3 `exp020_rules extract` did not take the lock itself → **fixed** (`22074b9`).
- M4 EXP-018 bar applied to differences below the measured noise → notes restated (wording still flagged in re-review m3).
- M5 EXP-006 drop counts double-counted quote failures (89 → 82) → **fixed**, run re-logged.
- M6 hard-coded cap in the harness → **fixed**. M7 `ARG_KINDS` widenings and a `no subject` reason → **fixed** / documented.
- M8 recall effect of the schema change not measured → recorded as not measured.
- M9 EXP-006's "one real pass" reports fact P/R, not EXP-006 metrics → stated in the notes.

**Re-review 1** (`2.1B-rereview.md`; unit tests 81 passed; MLflow, reply caches, `docker image ls` and a `git diff` of the two images' build inputs checked): I1, I2, I3, M2, M3 **ADDRESSED**; all 24 `EXP-020-rules` run ids active, means recompute exactly; the image mix is not a material confound. **Three new Important:**
- **N1** `gpu_session` ran teardown and `release()` when it did not hold the lock (an exception during the wait loop deletes every Serve app on the shared ray-head and the other holder's lock). **Fixed** (`962512f`): ownership token in `owner.txt`, teardown and release only when held; `tests/unit/eval/test_exp018_lock.py`.
- **N2** the catch-all "any other verb → use" (`remove` → use, a regression against `consolidate.END`; acquisitions → use; free-text F1 0.122 → 0.103; tuned in-sample). **Fixed** (`962512f`, controller ruling): prompt verbs only, others dropped and counted. See [B-172](decisions.md#b-172--holdsowns-values-are-mapped-only-from-the-prompts-vocabulary-other-verbs-are-dropped-and-counted-d-21b-2).
- **N3** derived presence placed V.O. and phone speakers at the heading's location (0.9 confidence, above the review threshold), which `plot.two_places` would report on a phone call intercut with the caller's own scene. **Partly fixed** (`962512f`, parentheticals only), **fixed** in round 3 (`dd557fe`).
- New minors: m1 MLflow commit tags on the `+holds` runs name another deliverable's commit; m2 the free-text arm is itself split across images (104 / 382); m3 EXP-018 wording; m4 `HOLDS_EVENTS` restated instead of derived; m5 ownerless-lock window in `acquire`.

**Re-review 2** (`2.1B-rereview2.md`; 83 unit tests passed): N1 and N2 **ADDRESSED**; **N3 NOT ADDRESSED for real scripts, partial** (the cue extension is stripped at ingest, so the `OFFSCREEN.search(line.speaker)` branch was dead code); the skip-intercut revert judged correct against architecture.md and evaluation.md; all 12 r2 run ids active, means recompute; a report cell mixed clean and injected false positives (corrected in round 3).

**Re-review 3** (`2.1B-rereview3.md`, scoped; `tests/unit/ingest` + `tests/unit/knowledge` 141 passed; the Postgres integration test not run): N3 **ADDRESSED**, with a consumer audit of every reader of `script_line.speaker`; m5 fixed (atomic rename). One new Minor (M-new1).

**Deferred minors**
- M-new1: `render` printed the raw cue (`ADA (V.O.): ...`) into the prompt, so an unregistered speaker could become a candidate named with the extension → fixed later by 2.9B-1 (`e2bab95`, the prompt renders `speaker_name(...)`).
- m3: the notes still say −0.023 is "within the 0.013 single-pass noise" (it is 1.8x) and one line still says "Status done (bar not met at 16k…)".
- Re-review 2: `take`, `get`, `gets` are dropped rather than mapped (loses acquisitions on real scripts; enforce the prompt's value vocabulary in the schema, 2.3 / prompt v2); `OFFSCREEN` also matches "(picks up the phone)" (only loses a derived presence).
- Re-review 3 nits: `OFFSCREEN` runs on the name part too (`RADIO OPERATOR`, `PHONE GUY` treated as off-screen); a parenthetical on `MAYA` no longer carries to a later `MAYA (CONT'D)` cue (PDF only).
- Ledger: about 29 prop_provenance false positives per show (lower-tier proposal to 2.3); knowledge_order 0/9 (prompt v2); r2 runs tagged with the parent commit; the agent's one `git stash` (disclosed, restored).
- Not covered by the lock code (inherent): a hard kill leaves the lock held.

**Could not be verified by the reviewers:** full-suite counts (the implementer's); which event created the "tide tables" candidate in I2 (scratch DBs gone); the round-3 Postgres integration test; real-script behaviour of the derived presence (the synthetic shows have no V.O. or phone lines).

## 2.2 Story order and story days

**Review:** spec **partial** (3 gaps in "overrides always win" and marker coverage), quality good, with defects. Critical 0, Important 3, Minor 7. The reviewer probed `derive` on small inputs without writing files and did not re-run the tests ("the code and tests read consistent with the report"). P1 (unknown-day flashbacks ranked first) was judged a reasonable decision beyond the docs; the notes' doc corrections were checked accurate to the code.

**Important**
1. **I1 Marker and flashback cues read only from the heading's last " - " segment** (`story.py:157` `_tail`). `INT. HOUSE - FLASHBACK - NIGHT` and `FLASHBACK - INT. B - DAY` became present scenes, and the next scene then looked like a NIGHT → DAY regression (a spurious ambiguous next day); the same for DREAM/INTERCUT/LATER in earlier segments. **Fixed** (`ad1b1b9`): `_tail` reads every segment except the location plus every parenthetical; tests `test_markers_are_read_from_any_heading_segment` (6 forms; the prefix form built as a `SceneIn` because Fountain does not parse it as a heading) and `test_location_names_are_not_markers`. See [B-190](decisions.md#b-190--markers-stored-in-the-data-model-set-cues-read-from-every-heading-segment-except-the-location).
2. **I2 An LLM verdict could overwrite an override** (`story.py:356-377`). A markers-only override did not skip the ambiguous branch: override `continuous` on NIGHT → DAY plus verdict `earlier` gave markers `(continuous, flashback)`, day -2, `source=llm`. **Fixed** (`ad1b1b9`): for an overridden scene `earlier` / `simultaneous` are ignored and only the unset day may be filled; test `test_markers_only_override_is_never_overwritten_by_the_llm`. See [B-188](decisions.md#b-188--bible-overrides-always-win-including-over-the-llm).
3. **I3 Override `story_day` on a dream/vision/intercut scene ignored for ordering** (`story.py:329-331`, `_rank`). Day 9 with seq 1 next to a day-1 scene with seq 2. **Fixed** (`ad1b1b9`): a stated day makes the scene its own rank unit; test `test_override_day_on_a_sharing_scene_decides_its_seq` (day 9 gives seq 3). See [B-188](decisions.md#b-188--bible-overrides-always-win-including-over-the-llm).

**Minors fixed in the same round:** M1 an override flashback with no day is `inferred=true` (test renamed `test_override_flashback_without_a_day_is_first_and_still_inferred`); M2 `Verdict.reason` `max_length=300` dropped (with `max_tokens=300` a longer reason failed validation, one retry, then a gap); M3 the `_VERDICTS` memo keyed per model variant.

**Re-review: I1, I2, I3 and M1 addressed** (probes re-run; `test_story.py` 39 passed). Evidence: `INT. HOUSE - FLASHBACK - NIGHT`, `FLASHBACK - INT. B - DAY`, `INT. C - DAY - FLASHBACK` all give a flashback with no spurious ambiguity; override `continuous` with an `earlier` verdict keeps markers `(continuous,)`, day 2, source `override`; day 9 between day 1 and NEXT MORNING gives days 1, 9, 2 and seqs 1, 3, 2. New minor: an unoverridden dream/intercut scene right after an override-day sharing scene shares that scene's day and seq (day 9); rare, not worth a round.

**Deferred minors**
- M4 unit attribution: a stage re-derives the whole show, so other episodes' transitions are recorded as the current episode's units (known, P4).
- M5 lead-in scanning is loose: every transition of the previous scene counts, and any short all-caps action line is scanned for DREAM/VISION/MEANWHILE (`THE VISION BLURS.` marks a vision).
- M6 override markers are lower-cased but not validated against `MARKERS`.
- M7 the synthetic show cannot discriminate EXP-007's arms (documented; became 2.2B's variant).
- The re-review's day-9 inheritance edge above.

**Could not be verified by the reviewer:** the test counts and tau (not re-run in the first review; the re-review ran the 39 unit tests).

## 2.2B EXP-007 ambiguous-transitions variant and harness

**Review:** spec ✅, quality good, approve with minors. Critical 0, Important 1, Minor 6. The reviewer recomputed every reported number from the 30 active MLflow runs (read-only sqlite; 42 deleted runs are superseded reruns), checked file mtimes under `data/exp007/`, read `story.derive`, `layer1_oracle.py` and `serving.teardown`, and ran `test_exp007.py` + `test_synthetic.py` on CPU (16 passed). Spec checks passed: the variant is ambiguous for the rules (identical heading signal for flashback, cross-cut and next day; rules-only flashback and simultaneous recall 0.00) and resolvable from text (regex cue reader tau 1.0 on seed 1); truth correct (truth arm 12/12); 2.9A determinism byte-identical; fact set fixed; ownership respected (no edits to `story.py` before the ruling).

**Important**
1. **I1 The "held-out" label overstated independence.** v2's mtime is about 4 minutes after v1's verdicts existed for all three seeds, and the failure analysis v2 answers is aggregated over the three seeds, so "written from seed-1 verdicts" cannot be verified; v2's example cues are the generator's templates, identical across seeds, so seeds 2-3 test sampling variability only; the regex cue reader already reaches tau 1.0, so the variant cannot show the LLM beating a regex. Seeds 2+3 alone still meet the bar (0.60 → 0.857, +25.7 points). **Fixed** (`6dc6ba8`): notes Takeaway and Decision drop "held out" and call +26 to +30 a ceiling for explicit cues on this generator, real-script generalisation untested; the decision (keep v2) stands. With the same round the **controller ruling** switched `story.PROMPT` to v2 ([B-195](decisions.md#b-195--storyprompt-is-v2)).

**Minors fixed:** M5 the prompt version is now an MLflow param (`story_prompt`) for llm arms; M3 (documented only) `down` deletes every Serve app, safe only under `data/gpu.lock`, said in its docstring.

**Re-review: I1, M5, M3 addressed**, no new breakage. `story.py:57` is `PROMPT = "knowledge.story.v2.md"`; v1 still reachable via `derive --arm llm`; v2 has the same `$` fields; `test_story.py` + `test_exp007.py` 45 passed (the prompt-content test passes on v2).

**Deferred minors**
- M1 `later_unstated` truth is not resolvable from text (4 scenes per seed with no prose cue; affects only `day_acc_present`).
- M2 `story/day_acc_present` is poor in every arm (v2 0.48 / 0.06 / 0.42; rules 0.03-0.23); tau and the four rules are blind to it.
- M4 `ambiguate` has hard sample caps that hold only for seeds 1-3.
- M6 `verdict_acc` compares against the truth's last present scene, not the deriver's, so after a v1 cascade it is slightly off; 1 unmatched scene per seed in `asked/other`.
- Re-review: no test pins `story.PROMPT`.
- Observation, not a defect: per-call LLM time varied about 3x between the two sessions (2.45 vs 7.15 s median), cause unknown.

**Could not be verified by the reviewer:** that v2 was written from seed-1 verdicts only (artifacts contradict the timing).

## 2.3 Script Critic Layer 1

**Review:** spec ✅ with one integration gap (I-1), quality approved with fixes. Critical 0, Important 2, Minor 7. The reviewer checked the fact contract against 2.1's `consolidate.py`, `extract.py` and extraction prompt, 2.2's marker vocabulary and shared seq, `eval/synthetic/rules.py` (oracle circularity) and `schema.scene.markers` NULL behaviour; SQL injection clean. Tests not re-run in the first review (no DB URL documented for review). Spec ⚠️ items to ratify: only `references` is checked for "references or acts on a secret"; "never obtained" read as nobody held/owned; `two_places` flashback exemption; pair orientation (recorded as doc corrections).

**Important**
1. **I-1 "Used after lost" never fired on real 2.1 output** (`plot.prop_provenance.sql:35`; 2.1 `consolidate.py:49,154`). `lost` was in 2.1's `END`, not `TERMINAL`, so a `state: lost` event started no fact, and `holds` lose/drop events started none; they were in no `source_event_ids`, so the rule (events of active facts) could not see them. The oracle benchmark hid it (2.3's own consolidation). **Fixed** by a **controller ruling** ([B-206](decisions.md#b-206--lost-is-handled-like-destroyed-21-builds-state-lost-facts)): 2.1 builds `state: lost` facts from lose/lost/drop; 2.3 (`3aa1594`) handles `lost` like `destroyed`, documents it in the SQL header, and adds the `oracle-facts-lost` variant; tests `test_prop_used_after_loss_without_pickup_is_flagged[destroyed|lost]`, `test_prop_picked_up_again_after_loss_is_clean[destroyed|lost]`.
2. **I-2 `after_gone` picked the earliest loss before the use** (`plot.prop_provenance.sql:53-58`), so obtain 1 → lost 2 → found 3 → lost 4 → use 5 was not flagged. **Fixed** (`3aa1594`): `ORDER BY d.story_seq DESC, d.fact_id` (the latest loss); test `test_prop_lost_found_and_lost_again_is_flagged_against_the_latest_loss` flags line 5.2 against sc 4.

**Minors fixed:** M-4 the fixture's no-op `retract(use + 0)` replaced by an asserted loss-without-pickup case; M-5 the MLflow runs behind the 1.00 (SQL from before the confidence change) deleted and re-scored; M-6 `consolidate()` in `layer1_oracle.py` documented as a stand-in for 2.1's.

**Re-review: I-1 (2.3 side and oracle) and I-2 addressed** (49 tests re-run against compose Postgres, passed). 2.1's working-tree `consolidate.py:142-143` emits `state: lost` for lose/lost/drop, so the contract matches, not run end to end. `DESC` cannot lose an earlier loss's flag. No new Critical or Important; the SQL header line 8 exceeds 100 columns (comment only).

**Deferred minors**
- M-1 every spoken line of a dead character is its own flag (a ghost in a 10-line scene = 10 flags with distinct fingerprints); V.O./O.S. narration by a dead narrator is flagged too.
- M-2 `two_places` uses `scene.id` as the within-episode order (equals script order only because ingest inserts in order).
- M-3 the re-check passes when the claim line is still a row for any reason (decision 7, ratify).
- M-7 the 0.85 factor default is duplicated in `consolidate.py`, `story.py` and `layer1.py`; a `nip.config` constant would remove it.
- Report concern 3 was stale: 2.1's `extract.py:295` already fills `script_line.speaker_entity_id`.

**Could not be verified by the reviewer:** that the rules work on 2.1's real facts (the 1.00 is a rules-only ceiling on 2.3's own consolidation); the first review's test counts.

## 2.4 Cue alignment; loc.term, loc.shot_change, loc.drift, loc.offset

**Review:** spec ❌ (three Important spec gaps, two of them disclosed as proposals), quality ✅ with fixes. Critical 0, Important 4, Minor 6. The reviewer measured the signed distances of official es cue edges to the EXP-002 cuts (spread over -12..+12 frames, no peak at +-1: the raw shot_change flags are mostly real violations) and sampled the MLflow runs (commit tag of `bd74e53`, two commits before 2.4's).

**Important**
1. *shot_change flagged the out point that keeps the 2-frame gap.* The compliant position (cut - 2) was flagged, and ending on the cut draws a readability gap flag, so a compliant track could not be flag-free; the offending out points (-1, -2) were labelled native truth. **Fixed** (`313ccd0`): `min_gap_frames` read from the readability pack, out points at cut - 2 .. cut pass; planted tables at both rates; the pair `(100, 238), (240, 300)` clean for both checks ([B-216](decisions.md#b-216--shot_change-passes-an-out-point-at-cut---2--cut-and-flags-points-on-either-side-of-a-cut)).
2. *drift/offset required the picture against the activation matrix* (picture ◐; "Timing checks without picture skip shot-change rules"), leaving subtitles-only deliveries with no sync check. **Fixed** (`313ccd0`): picture dropped from `requires`; rate-pair causes and seconds-only offsets without a picture ([B-210](decisions.md#b-210--drift-and-offset-run-without-a-picture-and-say-less)).
3. *Observed standard per episode and verbatim only*, so the spec's own "Reyezuelo in E3" example was undetectable and stale rows stayed. **Fixed** (`313ccd0`): show-wide standard from the store, one-word translated renderings, episode switch at 0.80, `term.stage` recomputes ([B-213](decisions.md#b-213--observed-standard-over-the-whole-show-recomputed-every-run)).
4. *Benchmark numbers did not trace to committed code* (driver git-ignored, runs tagged with another commit, uncommitted check code). **Fixed** (`313ccd0`): `eval/exp/loc_bench.py` + unit test, 12 runs re-run (`exp=2.4r1`), natives renamed SELF-LABELLED ([B-217](decisions.md#b-217--the-benchmark-driver-lives-in-evalexploc_benchpy-and-runs-at-a-committed-sha)).

**Re-review: addressed.** The re-reviewer read the code at the fix commit, queried MLflow (12 `exp=2.4r1` runs, all after the commit time, per-run `flags_sha256`/`labels_sha256` present) and ran the 154 unit tests of the touched files (all pass). Checked that a constant shift cannot turn into drift without a picture. New minors:
- M-a an exact tie of rate-pair ratios names only the first pair;
- M-b an entry approved in one language keeps a stale observed row in another;
- M-c the 12 old runs and one more were still active in `loc-2.4` (**done in W-int**: soft-deleted);
- M-d "has a picture" = "has shots", so a failed shot stage reads as no picture (visible in the flag text);
- M-e an out point at cut - 1 passes shot_change while readability flags the 1-frame gap (recorded with M-4);
- M-f 2.0's `test_pipeline.py` / `test_store.py` edited again;
- M-g integration tests not re-run by the reviewer.

**Minors of the first review:** M-2, M-3, M-5 fixed; M-1 (2.0's test file edited), M-4 (either-side flagging) and M-6 (0.80 for a missing approved rendering) recorded as decisions ([B-216](decisions.md#b-216--shot_change-passes-an-out-point-at-cut---2--cut-and-flags-points-on-either-side-of-a-cut), [B-211](decisions.md#b-211--locterm-matching-rules)).

**Follow-up outside the fix round:** the 2.9A injector planted the now-compliant cut - 2 out point (Sintel recall 0.83); fixed in W-int (`be494b4`), Sintel recall 1.00 ([C-31](experiments.md#c-31--localization-checks-on-the-29a-injected-sintel-and-tears-of-steel-rounds-0-1-and-the-w-int-re-run)).

**Could not be verified by the reviewer:** no test run in the first review (read-only gate); the ffsubsync oracle (D-030, optional) was not run by the implementer.

## 2.5 Speech-to-text and script-to-transcript alignment (EXP-003, EXP-004)

**Review:** spec ✅ (with gaps), quality approved with fixes. Critical 0, Important 3, Minor 9. The reviewer recomputed WER and sub+del from the saved run-1 JSON, located every insertion per model and config, re-scored EXP-004 on CPU (0.676 / 0.514), varied the line variant's lookahead (400 / 1,500 / 100,000 chars) and checked the saved alignments for frameless scenes (none).

**Important**
1. *EXP-003's conclusion rested on a non-default decoding setting, and the notes misstated the confidence filter.* `temperature=0.0` disabled faster-whisper's fallback; large-v3's extra ToS WER (insertions 117 vs 38) was confident repetition loops that `min_prob 0.5` keeps. **Fixed** (`0440e1d`, `fa47838`): three fallback arms for both models, S/D/I per film, round-1 claims retracted, decision re-based on equal-config arms ([EXP-003](experiments.md#exp-003--speech-to-text-whisper-large-v3-vs-large-v3-turbo), [B-221](decisions.md#b-221--decoding-no-vad-temperature-fallback-min_prob-05-superseded-by-b-222-for-the-fallback-and-the-filter)).
2. *No pipeline stage; persistence bypassed 2.0's `ep.unit`.* **Fixed** (`0440e1d`): `timeline.asr` / `timeline.align` stages on `ep.unit`, `persist_transcript` split out, end-to-end test through `pipeline.run_store`.
3. *The Timeline labelled in-cut frameless scenes "not in cut"*, contradicting `scene.in_cut`. **Fixed** (`0440e1d`): "(unplaced)" when in cut; unit test.

**Controller note (layering):** `nip.timeline` imported `nip.pipeline`; **fixed** (`051534b`) with a `StageEpisode` Protocol ([B-226](decisions.md#b-226--timeline-stages-type-the-episode-with-a-protocol-instead-of-importing-nippipeline)).

**Re-review: addressed.** No new Critical or Important. The re-reviewer queried MLflow (48 active runs in `exp003-asr`, all reported means matched), ran `tests/unit/timeline` (68 passed) and `lint-imports` (7 kept), and confirmed faster-whisper accepts a YAML list for `temperature`. New minors:
- N-1 the notes overstated the fallback's gain and the uniqueness of `fb-p50` (`novad-hst` also meets the bar; ToS turbo transcripts byte-identical; the -1.2 margin is inside turbo's spread). This finding led to the controller ruling for `novad-hst` ([B-222](decisions.md#b-222--asr-decoding-default-is-the-deterministic-novad-hst-arm)); `notes/2.5.md:26` was corrected in W-int;
- N-2 idle VRAM differed between sessions (1,128-1,577 vs about 505-520 MiB), so the RTF cost is not an interleaved comparison;
- N-3 the notes still list the old `persist_alignment` signature;
- N-4 `backend()` is cached per variant, so a long-lived worker needs a restart to pick up `pipeline.yaml` edits.

**Minors of the first review:** M1, M4, M5, M6, M7, M8 fixed; deferred and recorded: M2 (3 real-script labels reuse Sintel cue starts: 102 distinct targets in 105), M3 (VAD mis-timing cause unexamined, a revisit trigger in [B-221](decisions.md#b-221--decoding-no-vad-temperature-fallback-min_prob-05-superseded-by-b-222-for-the-fallback-and-the-filter)), M9 (in-cut scenes outside the anchored range get no frames; doc correction).

**Could not be verified by the reviewer:** the integration tests `test_asr_persist.py` (Postgres) and `test_asr_gpu.py` (GPU) were not re-run; the Serve `Actor` is untested under Ray; RTF depends on uncontrolled CPU load from other agents. Done-when "suite green" was met for 2.5's files only (other owners' failures at the time).

## 2.6 OCR channel and Presidio recognizers (GLiNER, urlextract)

**Review:** spec ✅ (with caveats), quality approved with fixes. Critical 0, Important 3, Minor 13. The reviewer verified Presidio's default regex flags in its source, gliner's `transformers<5.17.0` in its METADATA, that tldextract reads its env var at import, the gliner-x-base snapshot's Apache-2.0 license, and the license of every new dependency by hand (`config/licenses.yaml` does not exist).

**Important**
1. *Plate patterns over-matched on-screen captions* (Presidio's default `IGNORECASE`; month-year cards, "100 MPH", "UP TO 50"). **Fixed** (`fa95853`): case-sensitive, narrower US/DE patterns, negative cases.
2. *GB Ofcom drama ranges correct but incomplete* (7 ranges from memory). **Fixed** (`fa95853`): the 01xx `496` blocks, 028 9649 6xxx and 029 2018 0xxx from a reproduction of Ofcom's table (Ofcom's page 403); three unverified blocks added, then removed in `3c1a5de` ([B-239](decisions.md#b-239--gb-drama-ranges-from-a-secondary-source-of-ofcoms-table-unverifiable-blocks-removed)).
3. *gliner caps transformers for the whole environment, including the vLLM image.* **Addressed as a decision** (`fa95853`, DP-2.6-9, [B-237](decisions.md#b-237--gliners-cap-transformers5170-is-accepted-for-now)); the vLLM smoke was assigned to W-int by controller ruling and passed there.

**Re-review 1:** I-1, I-2, I-3 addressed; **new Important N-1**: the narrowed patterns missed common real plates ("ABC 1234", "ABC 123", "123 ABC", "B AB 1234"). **Fixed** (`3c1a5de`): one space allowed with caption stop-lists; positive and negative cases added ([B-238](decisions.md#b-238--plate-patterns-are-case-sensitive-allow-one-space-and-exclude-caption-words-by-name)). Minors: M-a upper-case spaced ccTLD hosts missed (accepted); M-b remove the three unverified GB blocks (done in `3c1a5de`); M-c Ofcom itself still unfetched.

**Re-review 2: addressed.** No new Critical or Important. Probe: 16/16 plate shapes, 26/50 caption-shaped strings still match ([C-34](experiments.md#c-34--plate-regexes-over-three-rounds-captions-vs-real-plates)); acceptable as a Phase 2 baseline (over-flag side, EXP-019 owns precision). Minor recommendations: do not grow the stop-lists by hand; consider a score tier; the stop-list literals are duplicated inside two long regexes.

**Deferred minors (first review)**
- M-1 the NANP rule is keyed by region US/CA rather than country code 1;
- M-2 `reserved()` re-parses with the first region that yields a valid number;
- M-3 `opencv-python-headless` beside `opencv-python` (both own `cv2/`, same class as the onnxruntime shadowing);
- M-4 numpy on win32 lowered 2.5.4 → 2.3.5 with the gliner cap, not mentioned in the report;
- M-5 private APIs under `>=` pins (`_blank_languages`; `RapidOCR._load_det_model()` and the rec-on-CPU mutation, unguarded);
- M-6 no `revision=` pin on the gliner snapshot (license drift risk);
- M-7 `HF_HOME` and `TLDEXTRACT_PUBLIC_SUFFIX_LIST_URLS` set with `setdefault` too late if the libraries were imported earlier;
- M-8 an unknown shot index stores `shot_id=NULL`; `insert_detections` is not idempotent;
- M-10 the OCR bench driver is not committed, so the throughput/VRAM numbers cannot be reproduced from the repo;
- M-11 blocking OCR/GLiNER calls inside `async __call__`;
- M-12 a commit trailer naming another model (moot: every Claude trailer was stripped before the first push, [B-127](decisions.md#b-127--phase-2s-commit-messages-were-rewritten-once-before-the-first-push-to-drop-claude-co-author-trailers));
- M-13 license check done by hand (no policy file).
M-9 (ccTLD case) was fixed with I-1.

**Could not be verified by the reviewer:** the GPU run of `tests/integration/test_ocr_text.py` under the lock at review time (later run by the implementer: 1 passed in 62.8 s on the pre-fix rule set; the post-fix rule sets were checked on CPU with the real models); the vLLM smoke on the downgraded lock (done in W-int); Ofcom's own table.

## 2.7 Clearance matching, occurrences, CSV and clr.* flags (EXP-008, EXP-017)

**Review:** spec ❌ (passes once the controller rules on DP-2.7-9, DP-2.7-1 and DP-2.7-6), quality approved with fixes. **Critical 0, Important 6, Minor 8.** The reviewer re-scored `data/exp008/runs/1-per-shot+2s-s1`'s shown FPs with `eval.metrics.match` (61 shown, 10 matched, 51 FP) and computed `nip.store.runs.fingerprint` over the flags of three seeds; nothing in the checkout was changed. Confirmed: five statuses each tested; 555-0100..0199 fictional under any area code; gap-boundary test; tier override (nothing downstream re-tiers); pending/denied never hidden at every tested confidence for exact reads; CSV columns exactly api-contracts.md:241 with a round-trip test; e2e store runs equal the harness.

**Important**
1. **I1 · EXP-008 decision contradicted the bar's text.** The bar names no incumbent; read against 1 per shot, +50 points for +139 % keyframes fails the cost clause, so the literal outcome is 1 per shot; keeping 4 s / 2 s is an override justified by the 0.85 MVP recall target, a spec conflict to escalate rather than a reading of the bar. **Fixed** (`f324627`): controller ruling recorded as an override, "per the bar" withdrawn, `config/pipeline.yaml` comment rewritten ([B-251](decisions.md#b-251--exp-008-keep-the-4-s--2-s-keyframe-policy-as-a-recorded-override-of-the-bar)).
2. **I2 · R13 fingerprints collided for 38 % of clr flags** (41 of 109 per seed in 17 groups; one group mixed `must_review` "EFRO" with "City of Amsterdam"); every unknown item on one keyframe set shared one identity. **Fixed** (`f324627`): per-occurrence `clr/occ-<hash>` stable ref; 253 flags, 253 fingerprints, 0 colliding; unit test with two unknown URLs on one keyframe ([B-249](decisions.md#b-249--each-occurrence-has-its-own-stable-ref-so-r13-fingerprints-separate-distinct-items), [C-38](experiments.md#c-38--fingerprint-collisions-among-clr-flags-41-of-109-per-seed--0-of-253)).
3. **I3 · An OCR slip of a pending/denied identifier was hidden.** Exact matching plus plate score 0.4 with no floor: a one-character slip (O/0, I/1, B/8) becomes `unknown` and `suppressed` while still matching the label, which the system target forbids (not observed on this set). **Fixed** (`f324627`, controller ruling): a <= 1-edit near match of a pending/denied phone/plate takes that status with `near=True`, so `must_review`; tests over 5 identifiers x 7 confidences, and two edits or a cleared neighbour stay unknown ([B-250](decisions.md#b-250--a-one-edit-ocr-slip-of-a-pendingdenied-phone-or-plate-escalates-to-must_review)).
4. **I4 · Claim width was a constant matched to the injector.** 4 s keyframe windows: a label longer than about 13.3 s could never match; the claim differed from the occurrence range the CSV reports; stored `kf` ranges would break re-verification. **Fixed** (`f324627`, controller ruling): the claim is a `clr/occ-` span with the occurrence's range; keyframe as context with its single frame; recall unchanged; a 60 s label vs a 4 s occurrence does not match ([B-248](decisions.md#b-248--the-claim-is-the-occurrences-frame-range-as-a-clrocc-hash-span), [C-36](experiments.md#c-36--claim-span-for-an-occurrence-shot-span-vs-keyframe-cell-vs-occurrence-range)).
5. **I5 · Precision/noise claims and filter tuning.** The 113/h is not the spec's noise metric (clean runs, human triage); real credits URLs are true `unknown` detections and should be native labels, while brand_text errors are real FPs; the dense-card and person rules were fitted on seed-1 flags with non-independent seeds, and the dense rule's recall cost on text-rich in-scene frames was unmeasured. **Fixed** (`f324627`, controller ruling): precision reported against injected labels only; rules (own title / bible names, credit words, title-case NER, OCR >= 0.8, 3-letter brands); measured on seeds 2 to 3 (P 0.21, 41 FP); dense-rule cost measured (in-scene cost not measurable on these films); agent-provisional native URL labels ([B-254](decisions.md#b-254--credits-urls-are-correct-unknown-flags-precision-is-reported-against-injected-labels-only-junk-is-dropped-by-rule), [C-35](experiments.md#c-35--scanner-rules-on-unlogged-credits-text-shown-false-positives-95--29-and-89--24)).
6. **I6 · `pipeline.py` edits outside the grant.** Two `add_stage`, `STAGE_SLOTS`, `FEEDS`, `MODEL_SLOTS`, an unconditional NER pin, `test_cli.py`; content needed and correct except the pin (contradicts tech-stack "large on big GPUs"); the GPU `nip run` had never run. **Fixed** (`f324627`, controller ruling): slot-table edits ratified, pin removed, the shipped `nip run --in-cluster` run once on Sintel (exit 0, 43 flags, text_llm still fits) ([B-256](decisions.md#b-256--no-ner-pin-in-code-the-plannercatalog-decides-the-ner-variant), [B-257](decisions.md#b-257--pipelinepy-two-stages-and-the-slot-tables-beyond-the-one-sanctioned-add_stage)).

**Re-review 1** (`f324627`): I1 to I6 **addressed** (the reviewer re-ran `collisions`, re-read the MLflow runs, and probed `matching.match` and `TextScanner` before and after the diff; clearance unit tests 78 passed, `tests/unit` 834 passed with 1 failure and 8 errors attributed to another task's uncommitted edits). **New Important N1:** the new junk rules ran before the clearance log, so logged pending/denied brands/addresses containing a title or bible word, or made of credit words, vanished (no flag, no CSV row). **Fixed** (`cda802e`): the log is matched first; deny-list hits bypass the junk drops; test with three logged items at confidence 0.2 → three `must_review` flags and CSV rows ([B-255](decisions.md#b-255--the-clearance-log-is-matched-before-any-junk-rule)). New minors: N2 (`www.sintel.org`, the production's own site, labelled as a third-party native; native frames are seed 1's own ranges) **fixed** in `cda802e` (12 natives, stated next to the numbers); N3 (an exact read of a cleared number one edit from a denied one stays cleared) **verified and pinned by a test**, kept by design; N4 (credit vocabulary partly lifted from these films' credits; the 0.8 OCR floor's in-scene recall cost unmeasured) disclosed; N5 (`stage.py` imports `episode_occurrences` inside the function; the claim span exists only if stage and check compute identical occurrences, which they do: same function, 43 = 43) disclosed.

**Re-review 2** (`cda802e`): N1 to N3 **addressed**, no new Critical or Important; 72 clearance/matching tests passed. The reviewer traced Presidio deny list → person/role overlap → `_dropped` → `inside(fixed)` → `match` → `_analyze` and found no other path that drops a logged item, except a pre-existing minor (a logged brand/address overlapping a phone/URL/e-mail/plate span is dropped in favour of that finding).

**Deferred minors**
- M1 fixed (the journal line that said 2.6's `ocr_text.py` was untouched). M2 fixed (EXP-017 seconds tagged `seconds_are`, called stage wall seconds).
- M3: sharpness stored as a `detection` row whose `confidence` is a Laplacian variance (300+); fix is `attrs jsonb` in a 0003 ([B-259](decisions.md#b-259--crop-sharpness-is-stored-as-a-companion-detection-row)).
- M4: `nip clearance report --run run_N` recomputes occurrences from today's registry and detections.
- M5: OCR variants of one unknown item stay separate occurrences and flags.
- M6: cells capped at 4 s split a continuous sign across two adjacent long shots under 1 per shot.
- M7: unknown plates always <= 0.4 and `suppressed`; now stated as a decision ([B-260](decisions.md#b-260--unknown-plates-stay-at-their-recognizer-score-and-suppressed)).
- M8: `ruff format eval/exp` touched 2.1/2.1B's uncommitted files (formatting only); `tests/integration/test_clearance_report_pg.py` and `tests/unit/test_cli.py` are outside the brief's file list (listed in the report).
- From the ledger: the logged-brand overlap drop above; credit vocabulary partly informed by these films; the OCR 0.8 floor and dense-card recall cost unmeasured; no single end-to-end test from scanner to match to CSV (each link is tested with the same strings); clean-run human noise triage not done.

**Could not be verified / handed on:** the shipped GPU path ran with OCR on the container's CPU (no CUDA execution provider) and `timeline.asr` failing on `libcublas.so.12`, so GPU OCR in the container was not exercised; a fresh `load_timeline` lacks `clr/occ-` spans (2.9B re-verification); the occurrence ref borrows the show-wide `clr/` kind. These went to the Phase 2 closeout (progress.md line 217).

## 2.8 Scene vector index and hybrid retrieval

**Review:** spec PASS, quality GOOD. **Critical 0, Important 0, Minor 9.** No fix round. The reviewer verified on a scratch DB on the compose Postgres (6,000 random 1,024-d chunks, ANALYZE, the exact query text of `retrieve`) that the planner picks `Index Scan using ix_scene_chunk_hnsw_qwen3_embedding_0_6b` with `Order By: embedding::vector(1024) <=> ...` through the joins, that the variant predicate is absorbed only because it is inlined, and that an `episode_ids` filter seq-scans (correct and cheap). Also checked: migration up/down and the extended drift test; idempotence by stored text and variant (a deviation in mechanism from `text_hash`, same semantics); the deterministic tie-break `(-score, scene_id)`; the stub; `Actor` fits `_bind`; both controller rulings applied; variant regex-checked before inlining; `set_config(..., true)` is transaction-local; layering respected.

**Minor** (all deferred)
1. `retrieve` reloads the whole show's facts per call and the `ANY(source_event_ids)` join cannot use an index: O(scenes x facts) when Layer 2 loops over scenes; add a `ponytail:` comment or a cached entity map before Phase 3.
2. Weight 1.0 lets the overlap term dominate the narrow cosine band; tuned and evaluated on the same 3 planted pairs with truth facts; re-sweep with 2.1's real facts ([C-39](experiments.md#c-39--scene-retrieval-vector-only-vs-hybrid-vector--entity-overlap)).
3. The shared-entity candidate pool is unbounded (nearly every scene with a high-df entity); cap it later.
4. Episodes ingested before 0002 keep `speaker = NULL` and re-ingest is a no-op; backfill for 2.9B.
5. `schema.HNSW_VARIANTS` duplicates the migration's list and nothing checks catalog `text_embedder` variants ⊆ it.
6. `schema.py` carries about 120 lines of unrelated `ruff format` churn in the feature commit (merge-conflict risk; disclosed).
7. `Actor.__call__` runs blocking `encode` in an async handler and has no test.
8. `scene_chunk` has no cleanup when a scene is replaced (2.9B's job; `index_scenes` leaves orphan chunks).
9. Skipping is driven by the stored chunk text, not `scene.text_hash`; the brief and notes should say so.

**Could not be verified by the reviewer:** the "668 passed, 3 failed" CPU suite and its attribution to 2.4's uncommitted work (not re-run); the real-model throughput and rank numbers (model, GPU and 150-scene run not re-run; the DB-side planner check was); the doc corrections were only proposed in the notes, for the controller to apply.

## 2.9A Injectors, synthetic show, sidecars

**Review:** spec **PASS with deviations** (D-A to D-J recorded), quality **approved**. **Critical 0, Important 3, Minor 7.** The reviewer ran a 40-seed synthetic/plot consistency check, a mention-coverage count on `build(1)`, a `phonenumbers` validity check and a Presidio `PhoneRecognizer` leniency check, and adjudicated the implementer's concern 1: `test_committed_labels_validate` is correctly scoped; 2.5's `eval/labels/exp004/*.jsonl` are in the wrong directory and the test must not be loosened ([B-280](decisions.md#b-280--evallabels-is-reserved-for-label-format-files-exp-004-ground-truth-moves-out)).

**Important**
1. *I1 Film labels used `episode = <title slug>`,* but the 2.0 store accepts only `SxxEyy` and `metrics.overlap` returns 0 when episodes differ, so no film flag would ever match a film label (inherited from 1.9/1.10, mass-produced here). **Fixed** (`2894fdd`) by controller ruling: films are `S01E01` under `show=<slug>`; injectors, label ids, the 1.10 native labels and the readability test updated; a new test runs the injected track through `build_timeline(label.episode)` and the real check and matches every planted label ([B-279](decisions.md#b-279--a-film-is-showslug-episodes01e01)).
2. *I1b The N9X phone positives cannot be detected by the project's detector* (`is_valid_number` False; Presidio's default leniency VALID rejects them), so each film had a structural clr.phone false negative; the doc's own recipe. **Fixed** (`2894fdd`) by controller ruling: valid 555 numbers outside 0100-0199; a test checks every sidecar phone row and every negative ([B-273](decisions.md#b-273--phone-positives-must-be-valid-numbers-outside-the-fiction-range), [C-42](experiments.md#c-42--phone-positives-nanp-expansion-area-codes-vs-555-numbers-outside-the-fiction-range)).
3. *I2 The synthetic `truth.json` mentions covered characters and Kappa Cola only* (189 location, 24 prop, 4 org lines and 4 "the informant" surfaces unrecorded), which would score legitimate extractor mentions as unmatched in EXP-020. **Fixed** (`2894fdd`): `find_mentions` over every entity surface, 483 → 704 records, independent scan test ([B-281](decisions.md#b-281--mention-truth-records-every-entity-surface-in-a-line), [C-43](experiments.md#c-43--synthetic-show-mention-truth-template-bookkeeping-vs-scanning-every-surface)).

**Re-review (`2.9A-rereview.md`): all three ADDRESSED**, no new Critical or Important. The reviewer verified `FILM_EPISODE` through every injector and `inject.py`, re-ran the phone validity check over all sidecar logs, recounted 704 = 473 character + 189 location + 24 prop + 14 brand + 4 org, and ran `uv run pytest tests/unit/eval` (111 passed, 1 deselected). New minors: two build-log rows still use the old `sintel` episode naming; `generate.py` `_fill` keeps unused `kind` strings; `ruff format eval` also touched 2.5's untracked `eval/exp/*`.

**Deferred minors (original review)**
- M1 `inject.py`: `--only` not validated (`--only locs` silently does nothing); `_title` raises a bare `StopIteration` when a title with `clr` has no picture.
- M2 `loc_term.py` variants can contain the approved rendering (`Thom` → `Thomas`), which a substring-based checker would miss; `variants(e)` recomputed per cue.
- M3 labels are written to `<out>/<set>/seed<N>/labels/<title>.jsonl`, not the spec's `eval/labels/<set>/<title>.jsonl`; the run/report layer needs a mapping (now a doc-correction row).
- M4 clearance byte-identity is proven on one machine; libx264 frame-threading does not guarantee it across core counts or ffmpeg builds.
- M5 the title is not part of the seed, so Sintel and ToS pick correlated positions; `loc_readability.py` still seeds with the bare seed.
- M6 `loc.shot_change` yields 2 labels for Sintel and 1 per language for ToS (k = 3 requested); a data-volume limit.
- M7 `loc.readability` still renumbers and rewrites line endings through pysubs2 (harmless for the 1..n LF corpus files, last in the stack).

**Could not be verified by the reviewer:** that the sidecars parse and the 57 tests pass in the final checkout (not re-run in the first review); the decoder-vs-probe frame gap (21,312 vs 21,313) for late-film windows (all windows sit well inside the first 21,312 frames); whether 2.7/2.1 resolve to the same film episode ids (settled by the ruling); the NANP N9X "reserved for expansion" status (taken from the doc).

## W-int Wiring, integration fixes, image smoke, end-to-end store runs

**Review:** spec ✅ (two items ✅ with ⚠️: the stage order differs from the brief, and the config is read at import time), quality approved with one Important. **Critical 0, Important 1, Minor 5, Watch 5.** Read-only, CPU only; controller rulings were honoured (the real-LLM gap W-5 → W-serve and the clearance OCR stage → 2.7 were not re-raised). The reviewer checked the MLflow DB (`data/mlflow/mlflow.db`: 12 active `exp=wint-sc` runs at the injector commit, 7 soft-deleted partial runs, all 12 `exp=2.4` runs soft-deleted including the one beyond the brief), the novad-hst kwargs against `exp003_asr.py:53` and `clients/asr.py:98`, the vLLM flag spelling and its engine-config print, and that the CI file set has no other env-gated test.

**Important**
1. **I-1 A wired content stage whose Plan slot is missing was invisible in the run summary and report.** `timeline.asr` and `knowledge.index` returned with no unit; `knowledge.extract` and `knowledge.story` substituted `StubLLM` / rules-only even on a hardware Plan; the run reported `completed` and script_critic coverage read 1.0 over 0 facts; the only trace was `plan.warnings` inside the published `plan.json`. W-int's film runs were exactly this case (text_llm skipped, 0 events, `completed`). Breaks "No silent gaps" (architecture.md:63). It applies whenever the planner drops a slot, on any hardware, not only to the serving question. Optional: on a non-cpu profile `text_llm()` should not return the replay stub, because replayed fixture facts can land in a real show's fact table (541 events on the synthetic show came from test recordings). **Fixed in W-serve** (`c02a542`, [B-296](decisions.md#b-296--a-skipped-slots-stages-are-skipped-by-one-guard-in-run_store-and-the-checks-they-feed-are-gaps)), which owned `pipeline.py`: a skipped slot's stages are not called and are recorded, `knowledge.story` runs on rules only and says so, `plot.*` move to `skipped` (script_critic coverage 0.0, `completed_with_gaps`), `ReportPlan` gains `skipped_slots` and `warnings`; test with a non-stub Plan lacking text_llm.

**Re-review:** no separate W-int re-review; the W-serve review checked the fix against this finding (spec row "W-int I-1": ✅) and noted the stub fallback in `extract.py:276-279` remains in code but is unreachable from `nip run` on a hardware Plan.

**Deferred minors** (no fix recorded)
- M-1 `pipeline_config()` says "read on every call" but its four callers read it at import time; a `NIP_CONFIG_DIR` whose `pipeline.yaml` lacks `knowledge:` makes `import nip.knowledge.*` raise `KeyError`, reached by `wire()`, so any `nip run` fails; config changes after import are ignored.
- M-2 Two readers of `pipeline.yaml` (`timeline_config()` and `pipeline_config()`).
- M-3 An asr workload is requested even for script-only shows; on one 8 GB GPU in resident mode it competes with text_llm for a stage that does nothing.
- M-4 `# type: ignore[no-any-return]` in `timeline/asr.py _video_key` (nit).
- M-5 `extract.PROMPT_VERSION` became user-editable config although it versions the in-code template and is part of the recording and cache identity.
- **Watch items:** W-a the stage order differs from the brief and architecture.md (doc correction recorded); W-b `superseded` will cover two meanings once the fact-correction loop exists; W-c the unconditional ASR pin's behaviour when turbo cannot be placed is unexercised; W-d two unexplained native crashes at process exit (`nip eval run` 0xC0000005, `nip ingest` SIGSEGV), data intact, keep `PYTHONFAULTHANDLER=1`; W-e about 2.8 GB of HF downloads left in `C:\Users\pc872\.cache\huggingface\hub`, the user's call, W-7 worth ruling on (ruled: [B-298](decisions.md#b-298--importing-nip-defaults-hf_home-to-the-repos-model-cache)).

**Could not be verified by the reviewer:** anything on the GPU or in Docker (review was CPU only); the image-smoke and end-to-end numbers are the implementer's.

## W-serve Real models for `nip run` (staged serving in ray-head)

**Review:** spec ✅ with ⚠️ (the demo item: the shipped path was BLOCKED-ON-VRAM and the end-to-end real run used a monkeypatched margin; the gpu test had only ever skipped), quality approved with fixes. **Critical 0, Important 3, Minor 7.** The reviewer re-ran `pytest tests/unit/test_pipeline.py tests/unit/test_config.py tests/unit/contracts/test_report.py tests/unit/runtime` (92 passed) and `ruff check` on the changed files; no Postgres or GPU re-run (no Docker). Checked only the named risks outside the diff (`serving.teardown`, `planner._placements`, `extract.text_llm`, compose HF env, `ReportPlan` consumers: none in UI/TS). The three files outside the brief's list were judged justified.

**Important**
1. **I-1 A serving error in a group discarded the whole run.** A deploy `ServingError` escaped `run_store`, rolling back every episode's work and marking the run `failed`; with 20 to 50 MiB of planner headroom a load OOM from desktop drift is likely, and the spec makes GPU OOM a retry/downgrade and failed work a coverage gap. The post-work teardown check also raised if VRAM was not within 256 MiB of the pre-load idle, while the desktop moved 604 MiB in 25 minutes, so a finished 14-minute extraction could be rolled back because a desktop app grew. **Fixed** (`dff0f7f`, [B-302](decisions.md#b-302--a-serve-group-that-fails-to-deploy-is-a-coverage-gap-vram-drift-after-the-work-is-a-warning)): a deploy failure degrades the group's slots into recorded skips (`completed_with_gaps`, error kept in `serving[]`); post-work drift is `serving[].warning` with a 1,024 MiB tolerance. Tests: `test_a_group_that_fails_to_deploy_is_a_gap_not_a_failed_run` (Postgres), `test_group_teardown_drift_after_the_work_is_a_warning_not_an_error` (unit).
2. **I-2 No margin knob: the one-command real-model run worked only by code injection** (`python -c "…p.MARGIN_GB = 0.25…"`), while hardware-adaptation.md calls 0.5 the "default" and `current_plan` already read `NIP_GPU_MEM_UTILIZATION` from the environment. **Fixed** (`dff0f7f`, controller ruling [B-300](decisions.md#b-300--nip_vram_margin_gb-default-05-the-8-gb-laptop-may-set-025)): `NIP_VRAM_MARGIN_GB`, default 0.5, passed to the planner and `no_fit`; `.env.example` documents 0.25 for the laptop. Test: with the env at 0.25 text_llm is placed at 6.70 GiB free.
3. **I-3 Multi-episode results depended on where the run executed.** In-cluster runs were segment-major, host/cpu runs per-episode, so the same input gave different `plot.*` flags for earlier episodes, and the host path is the test and CI proxy for the cluster. **Fixed** (`dff0f7f`, controller ruling [B-301](decisions.md#b-301--one-execution-order-everywhere-each-stage-over-all-episodes-before-the-next-stage)): stage-major everywhere. Test: `test_host_and_cluster_runs_give_identical_flags_on_two_episodes`, 6 identical flags on both paths. The parity test also found `FakeS3.get_object` missing (added).

**Re-review: I-1, I-2, I-3 all ADDRESSED**, no new Critical or Important. The reviewer re-ran the cpu unit subset (122 passed), ruff, mypy (3 files) and lint-imports, and `tests/integration/test_store.py` against the live Postgres (18 passed, including the 3 new or changed tests), and checked that single-transaction semantics hold under stage-major order: one connection, one commit or rollback, per-unit savepoints strictly sequential; a deploy failure touches no DB state; an unexpected exception outside a unit still rolls back the whole run, now with serving timings logged (M-5).

**Deferred minors**
- Fixed in the fix round: M-1 (`need_gb` re-implemented `planner._kv_gb`), M-2 (`no_fit` could print a negative shortfall), M-5 (serving records lost when a run fails; now logged).
- M-3 `slot_reason` finds the reason by parsing warning strings; a wording change silently degrades it to `no <slot> in the Plan` (structured `{slot: reason}` is the upgrade path).
- M-4 Coverage 0.0 for a lost script_critic looks the same as the "not applicable" 0.0 of loc checks without subtitles; list lost checks per agent in the report when the contract is next touched.
- M-6 `asr.backend.cache_clear()` + `gc.collect()` before a group loads is unexercised (script-only demos); CTranslate2 freeing VRAM on GC is unmeasured.
- M-7 `nip.config` mutates the environment at import and now runs for every `import nip.contracts`, sidestepping the contracts layer's import-linter ban; say so in the contract comment (`pyproject.toml`, not this deliverable's file).
- Re-review notes: a stale comment at `tests/unit/test_pipeline.py:271` ("today's per-episode order"); `rec["error"]` keeps only the first line, losing the teardown-also-failed note; the drift `warning` is not logged and not in `plan.warnings` or report.json; the summary's top-level `plan` is the original Plan (the deploy-failure reason is in `serving[]`, per-episode `skipped_stages` and report.json).

**Could not be verified by the reviewer:** the Postgres and GPU tests (not re-run in the first review); the real-run numbers (implementer's). The ⚠️ list: the shipped path had never run the real LLM at review time (fixed in the fix round: the gpu test passed at 0.5 with a light desktop); story's LLM path made 0 asks on S01E01, so it is unexercised with a live model; 2/25 extraction units hit max_tokens (owner 2.1B); extraction is single-stream (W2 / 2.9B).

## 2.close Phase 2 closeout

**Review:** spec **PASS** with justified deviations (no cuDNN wheel; no OCR image change), quality **GOOD**. **Critical 0, Important 2, Minor 7.** Read-only and CPU only; Docker, GPU and test numbers are the implementer's, cross-checked against the notes. The reviewer judged the cuBLAS-12-beside-13 setup correct and minimal, the uv cache root cause correct, the catalog numbers traceable (2,577 MiB = 2.52 GiB rounded up to 2.6; 1,347 MiB = 1.32 GiB rounded up to 1.4), the planner golden changes consistent, and the edits outside the brief's file list justified.

**Important**
1. *I1 Occurrence refs were not stable under registry changes:* the hash included `who` = `clr/{item.id}` once matched, so logging a previously unknown item (the normal workflow, and exactly 2.9B's re-verification case) changed the rebuilt ref and `verify` dropped the stored flag; changes to the fictional-name list or clearance thresholds could also shift occurrences; only the unchanged-registry round trip was tested. **Fixed** (`ddf6206`) by controller ruling: the hash is episode, check, normalized first read and first keyframe; unit and Postgres tests for a registry change; the status-changed flag is still dropped by the rule re-check, a disclosed decision left to 2.9B ([B-307](decisions.md#b-307--the-occurrence-hash-uses-registry-independent-fields-only)).
2. *I2 The planner default changed to `gliner-x-large` with no scored EXP-008 re-run;* the evidence was one film read by hand, and large producing a strict subset of base's candidates means recall can only fall or stay equal. **Fixed** (`c0988ee`, `cf6724e` for a mypy import) by controller ruling (keep only if recall ≥ base): the NER A/B on replayed OCR, recall 1.00 for both in every check and seed, FP/h 90.99 → 86.55 ([C-54](experiments.md#c-54--ner-ab-on-replayed-ocr-gliner-x-large-vs-gliner-x-base-on-the-exp-008-end-to-end-benchmark), [B-305](decisions.md#b-305--gliner-x-large-stays-the-planners-pick-on-the-8-gb-laptop-measured-no-pin)); the notes state the published 2.7 numbers are with base.

**Minor**
- M1 **done**: the NVIDIA wheels' licence (proprietary redistributable, same class as the base image's CUDA libraries) recorded and accepted ([B-304](decisions.md#b-304--cuda-12-cublas-only-on-ldconfig-and-the-uv-cache-dir-fixed)).
- M2 deferred: the Dockerfile hardcodes `/usr/local/lib/python3.12/dist-packages/nvidia/cublas/lib`; if the base image's Python path moves, `ldconfig` succeeds silently and ASR breaks at runtime (suggested guard: `ldconfig -p | grep -q libcublas.so.12`; needs a rebuild to verify).
- M3 deferred: vLLM smoke 134.6 / 165.5 tok/s vs 175 to 189 earlier; "machine noise" plausible but unverified; an A/B against `nip:pre-close` under the lock would settle it ([C-55](experiments.md#c-55--vllm-smoke-on-the-new-image-vs-earlier-runs)).
- M4 deferred: `store/load.py` lazily imports `agents.clearance.checks` (store → agents inversion, allowed by lint-imports); every `load_timeline` caller pays one extra detection query when OCR rows exist (0.07 s on Sintel); keyframe span `text` changes for non-clearance agents (looks benign).
- M5 **done** (`c0988ee`): stale `NIP_PIN_NER` references removed from the `pipeline.py` docstring and `exp008_e2e.py run-cluster`; `run-cpu` still pins base deliberately so the published numbers stay reproducible.
- M6 accepted: the Dockerfile and image are covered only by manual verification (CPU CI cannot run it).
- M7 deferred as a doc correction: docs/tech-stack.md names CTranslate2 4.8.2; the lock and image have 4.8.3.

**Re-review (`2.close-rereview.md`): I1, I2, M1, M5 ADDRESSED**, 0 Critical, 0 Important. The reviewer ran `pytest tests/unit/agents tests/integration/test_clearance_report_pg.py` (339 passed, 4 skipped) and read `data/mlflow/mlflow.db` directly: the runs are in experiment `mvp` (id 10) with tag `exp=2.7-e2e` (no experiment is literally named `2.7-e2e`); 18 finished `e2e-ner-*` runs; large recall 1.00 / 1.00 / 1.00 and precision 0.204 / 0.22 / 0.22 over seeds 1 to 3, base recall 1.00 and precision 0.196 / 0.212 / 0.212; per-check shown FN 0 for large. Not addressed / residual: the untracked `mlruns/` directory in the working tree (stray artifacts from the default tracking URI).

**Could not be verified by the reviewer:** all Docker, GPU and image-size numbers (not re-run); the new Postgres test for I1 (no `NIP_TEST_DATABASE_URL` in the reviewer's run); the NER variant of each A/B run read back from outputs (`model_variant` is null in the flags; it rests on the code and the differing flag counts).
