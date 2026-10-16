# Build Decisions

Choices made while implementing the design, where the docs in `docs/` were silent, ambiguous or wrong. Format and spirit follow [docs/decisions.md](../docs/decisions.md), but IDs are `B-xxx` ("build") so they never collide with the design's `D-xxx`. Entries are never deleted; a reversed decision is marked **Superseded**. Entries that came from the controller (the agent coordinating the build and the user's instructions) are marked **Controller ruling**.

Every entry names the deliverable (from [docs/phased-plan.md](../docs/phased-plan.md)) and the commit where the choice landed. Evidence for the numbers quoted is in [journal.md](journal.md) and [experiments.md](experiments.md). Source material: the agents' notes and the controller ledger in the git-ignored `.superpowers/sdd/phased-plan/`.

## Index

| ID | Deliverable | Decision |
|----|-------------|----------|
| [B-001](#b-001--torch-and-the-media-stack-are-main-dependencies-torch-pinned-to-vllm-0300s-version) | 1.1 | Torch and the media stack are main dependencies, torch pinned to vLLM's version |
| [B-002](#b-002--serve-extra-is-linux-only-and-kept-in-the-lock) | 1.1 | `serve` extra (Ray, vLLM) is Linux-only and kept in the lock |
| [B-003](#b-003--mlflow-skinny-as-the-client) | 1.1 | `mlflow-skinny` as the client |
| [B-004](#b-004--schema-v1-contains-all-26-tables) | 1.1 | Schema v1 contains all 26 tables |
| [B-005](#b-005--migration-0001-is-frozen-raw-ddl-schemapy-is-core-drift-is-a-catalog-diff) | 1.1 | Migration 0001 frozen raw DDL, `schema.py` Core, drift guarded by a catalog diff |
| [B-006](#b-006--sqlalchemy-core-not-the-orm) | 1.1 | SQLAlchemy Core, not the ORM |
| [B-007](#b-007--eval-is-packaged-as-a-top-level-package) | 1.1 | `eval/` packaged as a top-level package |
| [B-008](#b-008--contract-field-choices-the-docs-left-open) | 1.1 | Contract field choices the docs left open |
| [B-009](#b-009--typing-and-test-tooling-defaults) | 1.1 | mypy strict, importlib test mode, strict markers |
| [B-010](#b-010--database_url-rewriting-and-a-separate-test-database-variable) | 1.1 | `database_url()` rewriting and `NIP_TEST_DATABASE_URL` |
| [B-011](#b-011--gitignore-anchoring-and-envexample-comment-style) | 1.1 | `.gitignore` anchoring and `.env.example` comment style |
| [B-012](#b-012--pre-commit-hooks-are-local-and-not-installed-into-git) | 1.1 | pre-commit hooks are local and not installed into git |
| [B-013](#b-013--ci-items-deferred-from-11) | 1.1 | CI items deferred |
| [B-014](#b-014--uv-lock-covers-only-windows-and-linux) | 1.1 | uv lock covers only win32 and linux |
| [B-015](#b-015--half-up-rounding-for-ms-to-frame-conversion) | 1.2 | Half-up rounding for ms to frame conversion |
| [B-016](#b-016--smpte-labels-count-at-the-nominal-rate-and-other-timecode-edge-rules) | 1.2 | SMPTE labels at nominal rate, no start offset, no 24 h wrap |
| [B-017](#b-017--parse-results-carry-data-errors-and-warnings-parsers-never-raise-on-bad-input) | 1.3 | `Parsed[T]` result object, parsers never raise on bad input |
| [B-018](#b-018--cue-times-are-integer-ms-and-the-ttml-rate-is-a-fraction-or-none) | 1.3 | Cue times in integer ms, TTML rate `Fraction \| None` |
| [B-019](#b-019--required-columns-for-the-glossary-and-clearance-log) | 1.3 | Required columns for glossary and clearance log |
| [B-020](#b-020--bible-schema-leniency) | 1.3 | Bible schema leniency |
| [B-021](#b-021--script-model-and-scene-numbering) | 1.3 | Script model and scene numbering |
| [B-022](#b-022--pdf-screenplay-reader-is-an-indent-heuristic) | 1.3 | PDF reader is an indent heuristic |
| [B-023](#b-023--third-party-parser-defects-are-wrapped-not-forked) | 1.3 | Third-party parser defects are worked around, not forked |
| [B-024](#b-024--no-cli-in-the-ingest-deliverable) | 1.3 | No CLI in the ingest deliverable |
| [B-025](#b-025--lgpl-shared-ffmpeg-81-from-btbn-for-torchcodec-on-windows) | 1.8A | LGPL shared FFmpeg 8.1 from BtbN for TorchCodec on Windows |
| [B-026](#b-026--shot-boundary-semantics) | 1.8A | Shot boundary semantics |
| [B-027](#b-027--keyframe-policy-made-concrete) | 1.8A | Keyframe policy made concrete |
| [B-028](#b-028--num_ffmpeg_threads0-for-both-decoders) | 1.8A | `num_ffmpeg_threads=0` for both decoders |
| [B-029](#b-029--smaller-part-a-choices-on-keyframes-pillow-and-decode-tests) | 1.8A | Smaller part A choices |
| [B-030](#b-030--variable-or-unknown-frame-rate-is-rejected-and-fps-comes-from-r_frame_rate) | 1.8A | VFR rejected, fps from `r_frame_rate` (review fix) |
| [B-031](#b-031--compose-service-wiring-commands-ports-and-endpoints) | 1.5 | Compose commands, ports, endpoints, deferred services |
| [B-032](#b-032--keycloak-realm-import-binding-and-the-opt-in-dev-realm) | 1.5 | Keycloak realm, loopback binding, opt-in dev realm |
| [B-033](#b-033--mlflow-job-runner-off-one-worker-memory-limits) | 1.5 | MLflow job runner off, one worker, memory limits |
| [B-034](#b-034--the-nip-image-installs-into-the-vllm-images-python) | 1.5 | nip image installs into the vLLM image's Python |
| [B-035](#b-035--api-hardening-from-review-strict-jwt-claims-error-envelope-lf-attributes) | 1.5 | Strict JWT claims, error envelope, LF attributes |
| [B-036](#b-036--planner-workload-units-and-the-concurrency-constant) | 1.6 | Workload as `dict[Slot, int]`, GiB everywhere, `CONCURRENCY = 2` |
| [B-037](#b-037--catalog-numbers-that-the-docs-do-not-give) | 1.6 | Catalog ranks, overheads and actor sizes chosen by the implementer |
| [B-038](#b-038--judge-selection-independent-family-else-reuse-and-in-throughput-mode-the-judge-must-not-downgrade-others) | 1.6 | Judge selection, and the throughput-mode ruling |
| [B-039](#b-039--throughput-greedy-scoring-jump-moves-and-a-climb-back-pass) | 1.6 | Throughput greedy scoring, jump moves, climb-back pass |
| [B-040](#b-040--packing-replicas-and-plan-field-conventions-for-ray-serve) | 1.6 | Ray-shaped packing, one replica per GPU, Serve field rule |
| [B-041](#b-041--resident-group-fingerprint-and-catalog-hash) | 1.6 | `resident` group, fingerprint, catalog hash |
| [B-042](#b-042--vlm-image-caps-come-from-the-catalog-589824-px-2-images) | 1.6 | vlm image caps come from the catalog |
| [B-043](#b-043--hf-mem-is-used-only-for-missing-sizes-and-never-for-the-shipped-catalog) | 1.6 | hf-mem only for missing sizes, cached |
| [B-044](#b-044--the-laptop-cannot-plan-an-llm-at-613-gb-free-exp-001-runs-before-the-walking-skeleton) | 1.6 | Laptop cannot plan an LLM at 6.13 GB free |
| [B-045](#b-045--corpus-files-come-from-the-rwth-aachen-blender-mirror) | 1.9 | Corpus from the RWTH Aachen mirror |
| [B-046](#b-046--sintel-at-1080p-tears-of-steel-at-720p) | 1.9 | Sintel 1080p, Tears of Steel 720p |
| [B-047](#b-047--sintel-script-is-the-first-minute-only) | 1.9 | Sintel script is the first minute only |
| [B-048](#b-048--label-studio-frame-rate-is-templated-from-the-probed-rate-24-fps-films) | 1.9 | Label Studio frame rate templated from the probed rate |
| [B-049](#b-049--cut-labels-are-a-separate-json-file-not-flags) | 1.9 | Cut labels are a separate JSON file, not Flags |
| [B-050](#b-050--label-studio-project-design-all-intra-clips-with-overlap-and-local-files-serving) | 1.9 | Label Studio project design |
| [B-051](#b-051--provisional-agent-labels-for-exp-002) | 1.9/EXP-002 | Provisional agent labels for EXP-002 |
| [B-052](#b-052--match-score-is-one-plus-overlap) | 1.11 | Match score is one plus overlap |
| [B-053](#b-053--native-labels-raise-precision-only) | 1.11 | Native labels raise precision only |
| [B-054](#b-054--tp-attribution-is-per-side-for-equivalent-checks) | 1.11 | TP attribution per side (review fix) |
| [B-055](#b-055--overlap-rules-iou-for-timed-labels-ref-match-for-script-labels-context-ignored) | 1.11 | Overlap rules (review fix) |
| [B-056](#b-056--smaller-metric-and-logging-conventions) | 1.11 | Smaller metric and logging conventions |
| [B-057](#b-057--the-timeline-read-model-is-a-new-contract-in-nipcontractstimeline) | 1.4 | Timeline read model is a new contract |
| [B-058](#b-058--the-report-shape-is-a-contract-with-its-builder-beside-it) | 1.4 | Report shape is a contract |
| [B-059](#b-059--estimates-are-not-scaled-to-the-pictures-length) | 1.4 | Estimates are not scaled to picture length |
| [B-060](#b-060--page-length-from-a-screenplay-format-line-count) | 1.4 | Page length from a line count |
| [B-061](#b-061--script-estimate-display-rules-apply-per-object-not-per-episode) | 1.4 | Display rules per object |
| [B-062](#b-062--sub-frame-cues-keep-one-frame-and-shot-refs-use-the-list-index) | 1.4 | Sub-frame cues keep one frame, shot ref = index |
| [B-063](#b-063--check-interface-requires-units-run) | 1.4 | Check interface |
| [B-064](#b-064--emit-enforces-evidence-or-nothing-and-assigns-the-tier) | 1.4 | `emit` enforces D-005 and assigns the tier |
| [B-065](#b-065--report-ranking-sections-in-consequence-order-then-severity-and-confidence) | 1.4 | Report ranking |
| [B-066](#b-066--duplicate-timeline-refs-are-rejected) | 1.4 | Duplicate timeline refs are rejected |
| [B-067](#b-067--cli-wiring-is-a-separate-integration-step) | process | CLI wiring is a separate integration step |
| [B-068](#b-068--compose-ownership-15-owns-composeyaml-including-mlflow) | process | 1.5 owns `compose.yaml` including MLflow |
| [B-069](#b-069--agents-write-notes-a-later-step-merges-them-into-build-log) | process | Agents write notes, a later step merges them into `build-log/` |
| [B-070](#b-070--parallel-agents-on-disjoint-paths-with-path-scoped-commits) | process | Parallel agents with path-scoped commits |
| [B-071](#b-071--sdd-workspace-is-kept-not-deleted) | process | SDD workspace is kept |
| [B-072](#b-072--the-planner-follows-the-algorithm-where-the-docs-worked-examples-disagree) | 1.6 | Planner follows the algorithm over the docs' worked examples |

---

## 1.1 Scaffolding, CI, contracts, schema

### B-001 · Torch and the media stack are main dependencies, torch pinned to vLLM 0.30.0's version

- **Date / commit:** 2026-10-15 · `7ce7da1` · deliverable 1.1
- **Context:** the brief asked where GPU/ML packages that work on Windows should live.
- **Options:** (a) main dependencies; (b) a dependency group or extra that is off by default; (c) leave it to 1.8.
- **Choice:** (a). `torch==2.13.0`, `torchcodec==0.17.0`, `transnetv2-pytorch`, `scenedetect==0.7.1` go in `[project].dependencies`; `[tool.uv.sources]` takes torch from the `pytorch-cu130` index on `win32` only. torch is pinned to 2.13.0 because vLLM 0.30.0 pins exactly that.
- **Why:** the shot_detector actor needs them at runtime in the image; an off-by-default extra would be uninstalled by any other agent's plain `uv sync` in the shared venv.
- **Consequence:** Linux CI downloads PyPI's CUDA torch (several GB; `setup-uv` caching is on). Upgrade path if CI time hurts: a CPU-index source for CI (the 1.1 reviewer suggested `--no-install-package torch`).

### B-002 · `serve` extra is Linux-only and kept in the lock

- **Date / commit:** 2026-10-15 · `7ce7da1` · 1.1
- **Choice:** `serve` extra = `ray[serve]==2.58.0` + `vllm==0.30.0`, both marked `sys_platform == 'linux'`, kept in the lock.
- **Why:** being in the lock means a torch conflict between vLLM and our media stack fails at `uv lock` time instead of at image build. The Windows venv never installs them.

### B-003 · `mlflow-skinny` as the client

- **Date / commit:** 2026-10-15 · `7ce7da1` · 1.1
- **Context:** tech-stack says "MLflow ... pinned at setup".
- **Choice:** `mlflow-skinny` locked at 3.17.1 for the client. Full `mlflow` pulls the server stack (Flask, pandas, pyarrow, ...); the server runs in its own image.
- **Consequence:** 1.11 may `uv add mlflow` if the skinny client lacks something (it did not need to: MLflow with a sqlite store worked, see [journal](journal.md#2026-10-15--111-eval-metrics-assignment-instead-of-greedy-matching-and-a-justification-that-turned-out-to-be-wrong)).

### B-004 · Schema v1 contains all 26 tables

- **Date / commit:** 2026-10-15 · `7ce7da1` · 1.1
- **Context:** the brief said "tables Phase 1 needs" but also "include pgvector column types where specified"; the only vector column is `scene_chunk` (Phase 2).
- **Choice:** all 26 tables of data-model.md. The doc schema is the agreed contract, and one baseline migration is simpler than many small ones.
- **Not included:** pgvector HNSW indexes (need a fixed dimension per embedder; added when an embedder ships) and the `audit_event` append-only GRANTs (need the application role name that 1.5's compose defines).

### B-005 · Migration 0001 is frozen raw DDL, `schema.py` is Core, drift is a catalog diff

- **Date / commit:** 2026-10-15 · `7ce7da1`, fix `c1a8853` · 1.1
- **Context:** the schema exists twice: query-side SQLAlchemy Core tables and the database-side migration.
- **Options for the migration:** call `metadata.create_all` (rewrites history when `schema.py` changes); `op.create_table` (same duplication, less readable against the doc); raw DDL (1:1 reviewable against data-model.md). Chose raw DDL. The doc's unnamed `CREATE INDEX ON` statements got explicit names `ix_<table>_<columns>` so the Core metadata can match them.
- **Options for guarding drift** (after the review called it Important): parse the offline SQL (needs a DDL parser, misses constraints); `compare_metadata(compare_server_default=True)` (still blind to CHECK, identity, EXCLUDE); diff two real Postgres catalogs. Chose the catalog diff.
- **Consequence:** CI's `check` job needs a Postgres service from now on. Migrations stay frozen history; `schema.py` stays the query-side source. Four injected drifts were all caught ([journal](journal.md#2026-10-15--11-fix-round-the-schema-and-the-migration-are-two-hand-written-copies-so-ci-now-diffs-the-real-database-catalogs)).

### B-006 · SQLAlchemy Core, not the ORM

- **Date / commit:** 2026-10-15 · `7ce7da1` · 1.1. tech-stack says "SQLAlchemy 2 (Core)"; followed as written.

### B-007 · `eval/` is packaged as a top-level package

- **Date / commit:** 2026-10-15 · `7ce7da1` · 1.1
- **Choice:** `eval/` stays at the repo root (project-structure.md) and is packaged as `eval` via `[tool.hatch.build.targets.wheel] packages = ["src/nip", "eval"]`, so `nip eval ...` can import it inside the image.

### B-008 · Contract field choices the docs left open

- **Date / commit:** 2026-10-15 · `7ce7da1` · 1.1
- `Flag.id`, `Plan.plan_id` and `Fact.id` are optional (None until persisted): emitters and the pure planner have no ids.
- `Flag.verification` defaults to all `"n/a"` (values `pass | fail | n/a`, plus `judge_variant` from the DB comment); `status` defaults to `open`; `disposition` to None; `tier` stays required.
- `Evidence` gets `frames: [in, out)` (the source of truth per data-model; the JSON example shows only display `tc_in`/`tc_out`), `lang`, and `scene` (the script-estimate display string).
- `ProducedBy.model_variant` is nullable (deterministic checks such as `loc.readability` have no model) but has no default; `plan_id` is required. (The reviewer's Minor 2 asked for a default of None; deferred.)
- `Fact` mirrors the `fact` table (integer ids, `screen`/`story` as `[lower, upper)` with `None` = open-ended), not the API's display form.
- `SlotDecision` is the union of the fields in the doc examples, all optional except `variant`.
- `Plan.skipped_slots: list[Slot]` (the reason is always `no hardware for <slot>`); `pins` added (stored in the `plan` table); no separate `judge_independent` field: it is `decisions["judge_llm"].independent_family`. `Amendment.from` is `from_` in Python and `"from"` in JSON.
- `HardwareInventory.probed_at` is optional (in the API view, not the probe JSON); `Autoscaling.node_type` and `Node.gpus` have defaults.
- All contracts reject unknown fields (`extra="forbid"`).

### B-009 · Typing and test tooling defaults

- **Date / commit:** 2026-10-15 · `7ce7da1` · 1.1
- mypy `strict` with the pydantic plugin and `ignore_missing_imports = true` (several parser libraries ship no types), `files = ["src", "eval"]` so CI runs plain `uv run mypy`. The reviewer's Minor 1 asks for per-module overrides instead of the global setting (deferred).
- Tests use `--import-mode=importlib` (no `__init__.py` in test dirs; same-named test files in different folders do not collide). Markers `gpu` and `integration` are registered with `--strict-markers`.

### B-010 · `database_url()` rewriting and a separate test-database variable

- **Date / commit:** 2026-10-15 · `7ce7da1`, test added in `c1a8853` · 1.1
- `nip.store.db.database_url()` rewrites `postgresql://` to `postgresql+psycopg://` (SQLAlchemy would pick psycopg2 for the doc's URL); unset gives a host-less URL, enough for offline SQL.
- The destructive integration test uses its own variable `NIP_TEST_DATABASE_URL`, so it can never drop tables in the database named by `NIP_DATABASE_URL`.

### B-011 · `.gitignore` anchoring and `.env.example` comment style

- **Date / commit:** 2026-10-15 · `7ce7da1` · 1.1
- `models/` and `data/` became `/models/` and `/data/` (unanchored they would also ignore `tests/fixtures/data/` or a `runtime/models/` package). The reviewer noted this is a modification of an existing entry; benign. Added `.ruff_cache/`, `.coverage`, `.superpowers/`.
- `.env.example` puts comments on their own lines: the doc puts them inline after values, and some `.env` readers keep inline text as part of an empty value such as `NIP_PIN_TEXT_LLM=`. It contains the whole doc block including the non-`NIP_` variables (AWS_*, MLFLOW_DISABLE_TELEMETRY, HF_HUB_OFFLINE, TLDEXTRACT_*, POSTGRE_PASSWORD).

### B-012 · pre-commit hooks are local and not installed into git

- **Date / commit:** 2026-10-15 · `7ce7da1` · 1.1
- **Context / evidence:** the remote hook environment crashed pip with exit 0xC0000005 twice ([journal](journal.md#2026-10-15--11-pre-commit-the-remote-hook-environment-crashed-pip-on-windows-switched-to-local-hooks)).
- **Choice:** all four hooks are `repo: local, language: system` calling `uv run ...`; hook versions now come from `uv.lock`. `pre-commit install` is deferred until after the parallel waves, because an installed hook would run on every other agent's commit.

### B-013 · CI items deferred from 1.1

- **Date / commit:** 2026-10-15 · `7ce7da1` · 1.1. Deferred (in project-structure.md's CI description but not in the 1.1 brief): import-linter contracts, the pip-licenses gate (needs `config/licenses.yaml`), coverage reporting, the cpu-profile integration job (the Postgres drift job was added later in `c1a8853`), `nightly.yml`, `release.yml`. The GitHub Actions workflow has never run (nothing is pushed).

### B-014 · uv lock covers only Windows and Linux

- **Date / commit:** 2026-10-15 · `7ce7da1` · 1.1. `[tool.uv] environments = [win32, linux]`: the lock only covers the platforms we run on.

## 1.2 Timecode

### B-015 · Half-up rounding for ms to frame conversion

- **Date / commit:** 2026-10-15 · `f6390db` · 1.2
- **Context:** data-model.md says `round(...)` with no tie rule; Python's `round()` is half-even.
- **Choice:** half-up (`floor(x + 1/2)`): monotone, conventional, deterministic. A Hypothesis counterexample (frame middle at frame 0, 24000/1001) forced the tie question into the open.
- **Consequence:** exact ties (frame middles, sub-ms-fps edge cases) go to the later frame. Postgres `round(numeric)` is half away from zero, which agrees for non-negative values (reviewer note; not checked against other layers).

### B-016 · SMPTE labels count at the nominal rate, and other timecode edge rules

- **Date / commit:** 2026-10-15 · `f6390db` · 1.2
- SMPTE labels count at nominal = `round(fps)` (24 for 23.976, 30 for 29.97); non-drop 29.97 therefore drifts from wall clock (01:00:00:00 NDF = 108000 frames vs DF 107892).
- Start timecode offset is not a parameter; callers add the frame offset before `frame_to_smpte` (the docs say "added only for display").
- No wrap at 24 h; the hours field is not capped.
- Frame to ms round-trip is exact only for fps <= 1000 (tested up to 60 fps).
- The module is `__init__.py` only: the whole library is about 60 lines.

## 1.3 Ingest parsers

### B-017 · Parse results carry data, errors and warnings, parsers never raise on bad input

- **Date / commit:** 2026-10-15 · `7e5c20a` · 1.3
- **Context:** the API error `INPUT_REJECTED` carries `details {line, reason}`, and warnings are a list of strings.
- **Options:** raise per failure, or return a result object. **Choice:** `Parsed[T]` with `errors: list[Issue(reason, line)]`, `warnings: list[str]` and `.rejection(message)` building the INPUT_REJECTED body from the first error.
- **Consequence:** all errors of a file are collected at once; the API layer decides what to surface. The reviewer found that "never raise" was not fully true (`csv.Error` mid-iteration, unguarded ttconv calls: M-3, deferred).

### B-018 · Cue times are integer ms, and the TTML rate is a Fraction or None

- **Date / commit:** 2026-10-15 · `7e5c20a` · 1.3
- `Cue.start_ms/end_ms: int`; `SubtitleTrack.frame_rate` is None for SRT/VTT and for TTML without `ttp:frameRate` (ttconv's silent 30 fps default is not reported as declared). Frame conversion is done later with `nip.timecode.ms_to_frame(ms, fps)` using the picture's rate, and the "declared frameRate differs from picture" warning needs the probed rate, so the parser does not emit it.
- Reviewer minor M-9: ttconv still silently applies its 30 fps default to frame-based timing in a file with no declared rate; deferred.

### B-019 · Required columns for the glossary and clearance log

- **Date / commit:** 2026-10-15 · `7e5c20a` · 1.3
- The docs say "missing required columns are errors" without naming them. Required = `term, lang, approved_rendering` (glossary) and `item, kind, status` (clearance log); `notes` and `scope` are optional. Header names match case-insensitively after stripping. `status` must be cleared|pending|denied (stored lower-case); `lang` must have a BCP 47 shape (no registry lookup); `kind` and `scope` are free text. Duplicates are warnings.

### B-020 · Bible schema leniency

- **Date / commit:** 2026-10-15 · `7e5c20a` · 1.3
- pydantic models with `extra="allow"`; unknown keys at any depth become warnings (`Unknown key 'characters[0].height'`). `S\d+E\d+` is enforced on `identity_hidden_until`, `revealed_on_screen` and relationship `from`; relationships must reference declared character ids; duplicate character/secret ids are errors. `story_overrides[].scene` is free text. YAML line numbers are reported only for syntax errors (PyYAML drops them for valid documents). The field `register` is named `register_` (alias `register`) because pydantic warns that it shadows a parent attribute.

### B-021 · Script model and scene numbering

- **Date / commit:** 2026-10-15 · `7e5c20a` · 1.3
- `Script(title, scenes)`, `Scene(number, heading, elements)` with derived `time_of_day` (text after the last ` - `, only for headings matching INT/EXT/EST/I/E) and `text_hash` (sha256 of heading + element texts), `Element(kind in dialogue|action|parenthetical|transition, text, speaker)`.
- Scene number = explicit (`#12A#` in Fountain, `Number` attribute in FDX, leading or trailing number in PDF), else its 1-based position; duplicates warn. Content before the first heading is dropped with a warning. `(V.O.)`/`(CONT'D)` are removed from `speaker`. Lyrics map to dialogue; notes, sections, synopses and page breaks are ignored.
- `text_hash` and `time_of_day` are conveniences; later extraction work may redefine them. Reviewer minors: FDX `Shot` paragraphs become scenes (M-5), `time_of_day` is a heuristic (M-8).

### B-022 · PDF screenplay reader is an indent heuristic

- **Date / commit:** 2026-10-15 · `7e5c20a`, fix `056655d` · 1.3
- Classification by x-indent from the page-wide minimum x0 (action margin): under 36 pt action/heading/transition, under 94 dialogue, under 137 parenthetical, under 250 character, else right-aligned transition; transitions are also recognised by text (`... TO:`, `FADE IN/OUT`). Page numbers and `(MORE)`/`(CONTINUED)` lines are skipped; consecutive dialogue/action lines with a gap under 4 pt are joined.
- Ceiling: non-standard indents, dual-dialogue columns, scene numbers other than digits(+letter) misclassify; accuracy on real screenplay PDFs is untested (one synthetic fixture).
- The review fix (gutter scene numbers shifting the margin) is described in [review-findings.md](review-findings.md#13-ingest-parsers).

### B-023 · Third-party parser defects are wrapped, not forked

- **Date / commit:** 2026-10-15 · `7e5c20a`, `abd1108` · 1.3
- **Context / evidence:** screenplay-tools 0.0.10 turns `FADE IN:` into a scene heading and mangles boneyards; pysubs2 1.9.0 accepts malformed SRT arrows; ttconv 1.2.3 prunes some `<div>` cues (table in the [journal](journal.md#2026-10-15--13-ingest-parsers-three-third-party-libraries-each-had-a-defect-that-needed-a-workaround)).
- **Choice:** keep the libraries named by D-027 and add small pre- and post-processing around them (strip boneyards, re-classify unanchored headings, own SRT line pre-scan) instead of replacing them. `tests/fixtures/ingest/.gitattributes` marks `*.pdf binary` and `*.srt -text` so `autocrlf` cannot corrupt the PDF xref table or the deliberately-CRLF SRT.
- **Consequence:** "Passed a Fountain test including dual dialogue" (D-027) was true but not sufficient; see [doc-corrections.md](doc-corrections.md).

### B-024 · No CLI in the ingest deliverable

- **Date / commit:** 2026-10-15 · `7e5c20a` · 1.3. The brief asks for parsers and validation only; `nip ingest` needs the store and object storage. The library entry point is `nip.ingest.parse(fmt, data, kind)`.

## 1.8 Part A: media, shots, keyframes

### B-025 · LGPL shared FFmpeg 8.1 from BtbN for TorchCodec on Windows

- **Date / commit:** 2026-10-15 · `829a3b3` · 1.8A
- **Context:** TorchCodec on Windows loads FFmpeg shared DLLs; the FFmpeg on PATH is gyan.dev's static GPL build (no shared libs); D-027 and tech-stack require LGPL.
- **Options:** BtbN `win64-lgpl-shared` build; gyan.dev `release-full-shared` (GPL); conda-forge. **Choice:** BtbN `ffmpeg-n8.1-latest-win64-lgpl-shared-8.1.zip` (80,983,242 bytes) in git-ignored `models/ffmpeg/`, loaded by `os.add_dll_directory` from `$NIP_FFMPEG_DIR` or `models/ffmpeg/**/avcodec-*.dll`.
- **Consequence:** the build is `--enable-version3` = LGPL-3.0, while the docs say LGPL-2.1; the future license gate (`config/licenses.yaml`) must say LGPL-3.0. The Linux image needs its own shared build (the vLLM image path installs apt ffmpeg 6.1.1, see B-034). The download source (GitHub, BtbN) is not named in the docs.

### B-026 · Shot boundary semantics

- **Date / commit:** 2026-10-15 · `829a3b3` · 1.8A
- TransNetV2 flags the last frame of the outgoing shot. Each run of flagged frames [s, e] gives one cut (the first frame of the next shot) at `(s + e + 2) // 2`: a 1-frame run at i cuts at i + 1, a dissolve cuts at its middle. Shots are contiguous half-open ranges covering `[0, n_frames)`. A run touching frame 0 or the last frame cannot separate two shots and is ignored.
- **Rejected:** the wheel's `predictions_to_scenes` leaves transition frames in no shot, which is unusable for a frame axis.

### B-027 · Keyframe policy made concrete

- **Date / commit:** 2026-10-15 · `829a3b3` · 1.8A
- architecture.md says "middle frame of each shot, plus one every 2 s for shots longer than 4 s". Implemented: always `mid = in + (out - in) // 2`; for shots strictly longer than `long_shot_s`, also frames at `in + k * interval` (k >= 1, inside the shot) except those within half an interval of `mid`. A 10 s shot gives 2 s, 5 s, 8 s; a shot of exactly 4.0 s gets the middle only. Interval in frames = `round(fps * interval_s)`. Config keys `timeline.keyframes.{long_shot_s, interval_s, jpeg_quality}` in `config/pipeline.yaml`. EXP-008 may change it.
- Files are named by shot index `<out>/<shot_index>_<n>.jpg` with records `{shot, n, frame, file}`, because shot ids do not exist until the store writes `shot` rows.

### B-028 · `num_ffmpeg_threads=0` for both decoders

- **Date / commit:** 2026-10-15 · `829a3b3` · 1.8A
- **Evidence:** TorchCodec's default of 1 thread gave 92.9 fps decode+resize on 1080p H.264; 4 threads 404.6; 8 threads 452.8; 0 (auto) 433.0 (one run each, +-10%). End to end, 31.22 s became 12.06 s cold and 4.73 s warm for 120 s of video (table in the [journal](journal.md#2026-10-15--18-part-a-shot-detection-pipeline-decode-tuning-and-measured-speeds)).
- **Choice:** 0 (auto) rather than the marginally faster 8, so the setting adapts to the host.

### B-029 · Smaller part A choices on keyframes, pillow and decode tests

- **Date / commit:** 2026-10-15 · `829a3b3` · 1.8A
- **PySceneDetect fade detector is not built in part A.** tech-stack lists it next to TransNetV2; it belongs with EXP-002, which compares TransNetV2 with ContentDetector/AdaptiveDetector. The 1 s dissolve in the synthetic clip was caught by TransNetV2 alone.
- **`pillow` is a direct dependency** (JPEG writing; it was already in the lock through transnetv2-pytorch).
- **Decode tests skip themselves** (`media_ok` fixture) when ffmpeg is not on PATH or TorchCodec cannot load shared libs. GitHub's `ubuntu-latest` has no shared FFmpeg libs by default, so the cpu CI job skips them unless CI installs ffmpeg/libav*. Pure-logic tests (cut post-processing, keyframe policy, ffprobe JSON parsing) always run. The real-model test is `@pytest.mark.gpu`; pipeline tests use a frame-difference stand-in model. (Reviewer minor: the skip is over-broad.)

### B-030 · Variable or unknown frame rate is rejected, and fps comes from `r_frame_rate`

- **Date / commit:** 2026-10-16 · `72a7ea5` · 1.8A (review fix)
- **Context:** architecture.md says "Unknown or variable frame rate -> reject". The first version only set a `vfr` flag (`r_frame_rate != avg_frame_rate`) and took fps from `avg_frame_rate`.
- **Evidence:** the reviewer probed avg `2997/125` against r `24000/1001`: fps came out as `2997/125` with `vfr=True` (a false VFR flag and an inexact rate), and `0/0` rates raised `ZeroDivisionError`.
- **Choice:** fps is the exact `r_frame_rate` Fraction; `avg_frame_rate` is used only for the VFR check, with a 0.05% tolerance (below the 0.1% gap between 24 and 24000/1001); `0/0` or missing rates raise `MediaRejected("unknown frame rate")`; cover-art (attached-picture) streams are skipped; `nip timeline picture` prints `INPUT_REJECTED: ...` and exits 1.

## 1.5 Compose stack and API skeleton

### B-031 · Compose service wiring: commands, ports and endpoints

- **Date / commit:** 2026-10-16 · `1d1b9f9` · 1.5
- API and Ray head commands in compose are `uvicorn nip.api.app:create_app --factory` and raw `ray start --head --block`, not `nip api` / `nip runtime head`, because the root CLI is off limits and unwired (B-067). When those subcommands exist, change the two `command:` lines.
- The API is published on `127.0.0.1:8000` (no `ui` service until 4.1, which will own 8080 and proxy `/api`). `/healthz` and `/readyz` are served at root and under `/api/v1`.
- `GET /api/v1/me` (sub + roles from the token) was added: not in api-contracts.md, additive; it is the only authenticated route in Phase 1 and lets the OIDC wiring be tested end to end. No role-hierarchy helper yet, because the docs' role table is ambiguous (is `operator` a superset of `legal`? only `legal` may disposition clearance flags).
- Services deferred because they are not in the 1.5 plan row: `ui`, `prometheus`, `grafana`, `label-studio`.
- Readiness checks Ray through the dashboard's `/api/gcs_healthz` over HTTP, so there is no `ray.init` inside the API process.
- An extra bucket `nip-models` is created beside `nip-media`, `nip-artifacts`, `nip-mlflow` (for the `NIP_MODEL_SOURCE=s3://nip-models` mirror).
- `/readyz` returns `CLUSTER_UNAVAILABLE` for any dependency being down, since the doc's error table has no other 503 code.

### B-032 · Keycloak realm import, binding, and the opt-in dev realm

- **Date / commit:** 2026-10-16 · `1d1b9f9`, `56cc74b` · 1.5
- **Realm:** `deploy/keycloak/nip-realm.json` is not described in the docs but is required for `NIP_OIDC_ISSUER=.../realms/nip`, audience `nip-api`, claim `roles`: realm roles viewer/reviewer/legal/operator; public client `nip-ui` (code + PKCE, plus password grant for tests; redirect `http://localhost:8080/*`); audience mapper to `nip-api`; realm-role mapper to a flat `roles` claim; one dev user `dev`/`dev` with all four roles. `KC_HOSTNAME=http://localhost:8180` makes tokens carry the browser URL.
- **Binding:** Keycloak is bound to `127.0.0.1:8180` (the docs say `8180:8080` on all interfaces) because the realm ships a known dev password.
- **Controller ruling (after review Important 3):** the dev realm import is opt-in by an environment value only (`NIP_KEYCLOAK_DEV_REALM=true`), with no separate compose file, following Phase 4's "only environment values differ" rule. Cost if wrong: the laptop setup needs one extra environment variable.
- **Tried first:** `KC_IMPORT_REALM` (not honoured by Keycloak 26.6, realm 404). **Implemented:** a bash entrypoint that appends `--import-realm` only when the value is exactly `true` (`false`, empty, unset and `True` all fail closed).
- **Open (deferred minor):** `.env.example:63` ships `NIP_KEYCLOAK_DEV_REALM=true`; copying it to a cloud host's `.env` would enable the dev realm, so fix before Phase 4.

### B-033 · MLflow job runner off, one worker, memory limits

- **Date / commit:** 2026-10-16 · `1d1b9f9` · 1.5
- **Evidence:** idle 2.223 GiB; `--workers 1` + `mem_limit: 1g` still 1,015 MiB with the memory-events counter fired 4,322 times; root cause was about 6 `huey_consumer` processes at about 220 MiB each from MLflow 3.x's job runner.
- **Choice:** `MLFLOW_SERVER_ENABLE_JOB_EXECUTION=false` (nip uses no MLflow jobs) + `--workers 1` + `mem_limit: 768m`, giving 364 MiB idle, about 6x lower. The final limits are in the [journal](journal.md#2026-10-16--15-mlflow-memory-22-gib-idle-down-to-036-gib).
- **Related additions:** `psycopg[binary]` + `boto3` in the MLflow image, and `--allowed-hosts mlflow:5000,localhost:5000,127.0.0.1:5000` (see doc corrections).

### B-034 · The nip image installs into the vLLM image's Python

- **Date / commit:** 2026-10-16 · `1d1b9f9` · 1.5
- `nip.Dockerfile` is `FROM` the pinned `vllm/vllm-openai:v0.30.0` and uses `uv pip install` into its system Python (no venv): it reuses the image's torch and vLLM (no roughly 3 GB duplicate torch) and keeps one interpreter for vLLM. ffmpeg 6.1.1 from apt is included for TorchCodec. A root `.dockerignore` was added (not in the brief's file list; the build needs it).
- Reviewer minor: nip's dependencies resolve from `pyproject.toml` here, not from `uv.lock`, which is looser than the "image digests pinned; uv.lock" security statement.

### B-035 · API hardening from review: strict JWT claims, error envelope, LF attributes

- **Date / commit:** 2026-10-16 · `56cc74b` · 1.5 (all four were review Important findings)
- `.gitattributes` forces LF on files that are bind-mounted or executed in Linux containers (`*.sh`, `*Dockerfile`, `compose.yaml`, `deploy/keycloak/*.json`); `eol=lf` is independent of `core.autocrlf`.
- `jwt.decode(..., options={"require": ["exp","iat","sub","iss","aud"]})`; every `PyJWTError`/`ValueError`/`TypeError`/`KeyError` is a 401 with `WWW-Authenticate: Bearer`; the 401 text no longer echoes PyJWT's message; `roles` must be a list of strings.
- `src/nip/api/errors.py` produces the documented `{"error": {"code","message","details"}}` envelope for 401, 503, HTTP errors and validation errors (400 `VALIDATION_FAILED`).

## 1.6 Hardware probe, catalog, planner

### B-036 · Planner workload units and the concurrency constant

- **Date / commit:** 2026-10-16 · `28e859f` · 1.6
- The workload is `dict[Slot, int]` of work units (required slots = slots with units > 0). The docs say only "agents, units" and "demand = work units x cost_hint". Resolving agents and checks into slot units is left to the controller. A richer Workload model has no consumer yet.
- All `*_gb` are GiB, the unit NVML-derived free memory is in (the doc's 8,188 MiB -> "8.0 GB" is GiB). Catalog sizes copied from tech-stack are read as GiB, which slightly overstates memory (the safe direction).
- `CONCURRENCY = 2`: the memory model's `concurrency` (sequences per replica the KV budget covers) has no documented value. With 2 the laptop lands on 8k context as the doc's example says. EXP-001 / EXP-005 should revisit it.

### B-037 · Catalog numbers that the docs do not give

- **Date / commit:** 2026-10-16 · `28e859f` · 1.6
- **Ranks:** text 4b-awq 30 < 9b-awq 40 < 9b-fp8 45 < 35b-a3b 55 < 27b-int4 65 (doc) < 27b-fp8 70 < 122b 80 < 397b-int4 90 < 397b-fp8 95; judges 20/40/60; actors base 50, large/8b 60, whisper turbo 40.
- **Other estimates:** `overhead_gb` 1.0 to 6.0 scaled by size; actor `vram_gb` = hf-mem weights + 0.5 GiB, 15.1 for the 8B embedder, 1.0 for OCR and 0.5 for TransNetV2 as plain guesses; contexts Qwen 32k/8k and judges 16k/8k; `tp_options` from size (attention-head divisibility not checked); `min_compute_capability` "8.0" for all FP8; `min_vllm` "0.30" for every vllm variant; `cost_hint` 1 to 10 by size. `base_model` was left out for whisper turbo and PP-OCRv6 because the repo id was uncertain (needed later by `nip models pull`, 4.6).
- **Consequence:** the Plans shift when calibration (EXP-001 and the benchmark) replaces these.

### B-038 · Judge selection: independent family else reuse, and in throughput mode the judge must not downgrade others

- **Date / commit:** 2026-10-16 · `28e859f`, fix `3cf18c7` · 1.6 · **Controller ruling** on review Important I-1
- **Rule (hardware-adaptation step 7):** prefer a judge from a different family than text_llm's best-alone variant; otherwise reuse text_llm with `independent_family=false`. A reusing judge appears in the `llm` group with `shared_with: [text_llm]`, and text_llm's `shared_with` includes `judge_llm`.
- **Problem found by the reviewer:** in throughput mode the independent judge was an ordinary slot in the greedy, so it forced text_llm 16k -> 8k and asr large-v3 -> turbo on 1x 48 GB. The doc's own 48 GB example also had text_llm below best-alone, so the spec contradicted itself.
- **Ruling:** the judge gets its own engine only if that downgrades no other slot, otherwise it reuses text_llm. Implemented as: choose the other slots first with the judge reusing text_llm (greedy + climb-back), then let the judge climb last to the best independent variant that still packs. "No downgrade" means relative to the reuse set, not relative to best-alone. Quality mode is unchanged (staged gives the judge its own group). A pinned judge keeps the old behaviour.
- **Cost if wrong:** lower judge independence on 48 GB throughput Plans.

### B-039 · Throughput greedy scoring, jump moves and a climb-back pass

- **Date / commit:** 2026-10-16 · `28e859f` · 1.6
- Score = rank loss / useful GiB, where useful = `min(freed, shortfall vs total usable memory)`, or plain `freed` when the sum already fits and packing is the problem. Context shrinks cost 0 rank, so they go first. Moves may jump to any lower candidate (candidates are ordered by quality, not memory). After the set packs, each slot climbs back to the best candidate that still packs. If not even the smallest set packs, the Plan is staged with the best-alone choices.
- **Evidence for each refinement:** see the "tried -> result -> changed" list in the [journal](journal.md#2026-10-16--16-planner-v1-six-things-tried-each-changed-after-a-result): the literal greedy ended at `qwen3.5-9b-fp8` on 48 GB; the refined one ended at `qwen3.8-27b-int4`.

### B-040 · Packing, replicas and Plan field conventions for Ray Serve

- **Date / commit:** 2026-10-16 · `28e859f` · 1.6
- A tp>1 replica takes tp whole, untouched, same-name GPUs on one node (Ray cannot give `num_gpus > 1` fractionally, so nothing co-resides). A tp=1 engine takes an engine-free GPU if there is one (best fit), else shares one. Actors are best-fit into leftover memory. At most one replica of a deployment per GPU; replicas <= work units.
- Engines carry `gpus_per_replica = tp`, `context` and `gpu_memory_utilization = ceil2(per_gpu_gb / vram_total)`. tp=1 engines also get `gpu_fraction` (= gmu) and actors get `gpu_fraction`. **Rule for Serve:** `num_gpus = gpu_fraction` if set, else `gpus_per_replica`. A tp=1 engine must request a fraction, otherwise actors and a second engine could never share its GPU in Ray. Secondary slots of a shared deployment carry only `variant` + `shared_with`.
- Reviewer minor M-5: the per-fraction round-up can push the summed `gpu_fraction` on one GPU above 1.0 when `NIP_GPU_MEM_UTILIZATION` is about 0.95 or higher; not reachable at the 0.90 default.
- The vlm slot rides on text_llm's deployment whenever text_llm's chosen variant serves vlm, unless vlm is pinned. Limit: a vlm-only variant ranked above the shared one is ignored (none exists in the default catalog).

### B-041 · Resident group, fingerprint and catalog hash

- **Date / commit:** 2026-10-16 · `28e859f` · 1.6
- Resident Plans have one group named `resident` holding every slot, so the scheduler can iterate groups the same way in both modes. A staged group that cannot pack on its own is split into one group per slot (`<group>:<slot>`). Merged groups are named `a+b`, as in the doc's `vlm+llm`.
- Fingerprint = sha256 over each node's (cpus, ram_gb, [GPU name, total, cc]), sorted. Node ids (they change on restart) and free memory (changes every probe) are excluded, so the benchmark baseline per Plan fingerprint stays stable on the same machine.
- `catalog_sha256` = sha256 of the variant list after hf-mem filling (what the planner saw), not of the file bytes.
- Catalog validation (`validate(catalog, vllm_version, licenses)`) excludes variants with a reason for license and `min_vllm`; compute capability is checked per GPU inside the planner. `config/licenses.yaml` does not exist (not owned by 1.6), so `nip plan` performs no license check. `probe()` covers this machine; `probe_node(node_id)` is the per-node function the controller runs as a Ray task.
- `nip plan` is a `typer.Typer()` callback in `planner.py` with `--objective`, `--simulate inventory.json`, `--units N` (default 100), `--catalog`; it reads `NIP_PIN_<SLOT>`, `NIP_PROFILE`, `NIP_GPU_MEM_UTILIZATION`.

### B-042 · vlm image caps come from the catalog (589824 px, 2 images)

- **Date / commit:** 2026-10-16 · `3cf18c7` · 1.6 · **Controller ruling** on review Important I-2
- **Context:** the doc's Plan example sets `vlm.max_pixels = 589824` (about 1024x576) and `images_per_prompt = 2`, and Serving says the planner sets vLLM's `--mm-processor-kwargs max_pixels` and `--limit-mm-per-prompt.image`, but no rule derives them.
- **Options:** a rule from VRAM (none documented); leave unset (1.7 would run on vLLM defaults, which can blow the laptop budget); catalog defaults.
- **Choice:** two optional `Variant` fields `max_pixels` / `images_per_prompt`, set to the doc's laptop values on all 9 vlm variants (overridable per variant); the planner copies them into the Plan's vlm decision, including the shared secondary decision. Test: overridden values 1003520 / 4 reach the Plan on 8x 80 GB.
- **Cost if wrong:** big GPUs are under-used (small images, 2 per prompt) until Phase 3 tuning. Note for 1.7: when vlm shares text_llm's engine the caps live on `decisions[vlm]`, not on text_llm's decision.

### B-043 · hf-mem is used only for missing sizes and never for the shipped catalog

- **Date / commit:** 2026-10-16 · `28e859f` · 1.6
- Variants missing `weights_gb`/`kv_mb_per_1k_tokens` (vllm) or `vram_gb` (actor) get an hf-mem estimate cached per repo in `$HF_HOME/hf-mem-cache.json`; the shipped catalog has every size filled, so it needs no network (a test asserts `hf_mem` is not imported). The catalog keeps the docs' KV figures (60 and 160 MiB/1k) and uses hf-mem's (128 and 256) only where the docs give none; reasons and the full table are in the [journal](journal.md#2026-10-16--16-model-catalog-hf-mem-disagrees-with-the-docs-kv-figures).
- Reviewer minor M-2: an hf-mem-filled actor gets `vram_gb = weights` without the 0.5 GiB activation allowance the YAML header promises (underestimates, the unsafe direction); deferred.

### B-044 · The laptop cannot plan an LLM at 6.13 GB free, EXP-001 runs before the walking skeleton

- **Date / commit:** 2026-10-16 · `28e859f` · 1.6 · risk decision
- **Evidence:** at 6.13 GB free (usable 5.63) the planner skips text_llm, vlm and judge_llm; qwen3.5-4b-awq at 8k needs 6.14 GB, ministral-3-3b-fp8 needs 6.51 GB. The reviewer reproduced it on both objectives, and showed the suggested fallback `CONCURRENCY = 1` alone does not rescue it (4.0 + 0.47 + 1.2 = 5.67 GiB, still above 5.63).
- **What would fix it:** measured overhead below 1.2 GiB (EXP-001), fp8 KV, a smaller margin, or freeing desktop VRAM.
- **Choice:** keep the algorithm as the spec prescribes (a slot without a candidate is skipped with reason `no hardware for <slot>`), test the laptop Plan with the doc's 7.15 GB idle figure, and run EXP-001 before the walking skeleton. The 6.13 GB case is not yet a regression test (reviewer M-6).

### B-072 · The planner follows the algorithm where the docs' worked examples disagree

- **Date / commit:** 2026-10-16 · `28e859f`, `3cf18c7` · 1.6 · **Controller ruling**
- **Context:** the reviewer reproduced every worked-example disagreement and found the planner correct in each case: laptop gmu 0.77 not 0.83; 48 GB quality 3 groups with gemma-4-31b not 2 groups with Gemma-12B; 48 GB throughput arithmetic (24.5 + 17.8 + the smallest actor set 9.9 = 52.2 > 43.19 GiB usable); 8x 80 GB tp=8 takes all 8 GPUs so 3 groups; 8x 80 GB throughput picks 397B-int4 because the greedy frees 210 GiB for 5 rank points; 24 GB quality 4 groups not 3.
- **Choice:** the documented algorithm beats the example tables. The corrections are listed in [doc-corrections.md](doc-corrections.md). If the user wants replica count to matter on big nodes, that is a change to the objective, not a bug.

## 1.9 Corpus and labelling

### B-045 · Corpus files come from the RWTH Aachen Blender mirror

- **Date / commit:** 2026-10-16 · `d4cb1c2` · 1.9
- **Context:** `download.blender.org` returns HTTP 403 to automated clients, including the URLs named in docs/evaluation.md.
- **Options:** browser-driven download, or a mirror. **Choice:** `ftp.halifax.rwth-aachen.de/blender/demo/movies/` (the official mirror listed on the Sintel download page). The Sintel md5 matches the official one. Manifest `picture` URLs name the mirror.

### B-046 · Sintel at 1080p, Tears of Steel at 720p

- **Date / commit:** 2026-10-16 · `d4cb1c2` · 1.9
- The docs specify no resolution; the "<= 1080p" rule was applied. Sintel 1080p is 1.17 GB (picture 1920x818). The ToS 1080p file is only offered as a zip on the mirror (and the plain `.mov` name serves that zip), so ToS uses the 720p QuickTime file (372 MB, 1280x534). Zip extraction was skipped (YAGNI); revisit if Phase 2 clearance work needs ToS at 1080p for on-screen text. A downloader guard rejects a `PK` download when the URL does not end in `.zip`.

### B-047 · Sintel script is the first minute only

- **Date / commit:** 2026-10-16 · `d4cb1c2` · 1.9
- The only published Sintel script file found is the 2009 "1st minute script" PDF (the docs' `script.zip` returns 404). The manifest points at it with a comment. EXP-004 (script-to-transcript alignment) must obtain the full script another way (manually from Blender Studio) or derive it with the derived-assets pipeline.

### B-048 · Label Studio frame rate is templated from the probed rate (24 fps films)

- **Date / commit:** 2026-10-16 · `d4cb1c2`, fix `dab96fc` · 1.9
- **Evidence:** `ffprobe` gives `r_frame_rate=24/1` for both films; the docs assume 23.976023976.
- **Choice:** the Label Studio config is a template (`{framerate}`); `ls_framerate()` always emits a decimal ("24", "23.976023976", never "24000/1001"). After review Important I1 the `--fps` option was removed from `push`: it probes every clip and the verify clip with `nip.ingest.media.probe`, refuses mixed rates and stores the rate in every task. Rule: never pass a fraction, always the decimal of the probed rate.

### B-049 · Cut labels are a separate JSON file, not Flags

- **Date / commit:** 2026-10-16 · `d4cb1c2`, fix `dab96fc` · 1.9 · **Controller ruling** on review Important I4
- **Context:** `eval/metrics.py` reads `label_id` and `target.frames`; a cuts row raised `KeyError: 'label_id'` (reviewer check). Shot cuts are not planted errors and not Flags.
- **Ruling:** shot cuts are not Flags, so they are not scored by `eval/metrics.py`; 1.8B owns the cut-F1 scorer with a +-2 frame tolerance (the IoU >= 0.3 rule on `[f, f+1)` could not give that tolerance anyway); 1.9 documents the cut label format. Cost if wrong: two label formats to maintain.
- **Final format** (replaced the first proposal of JSONL rows under `eval/labels/cuts/`): one JSON object per film `{title, check: "shot.cut", fps: "24/1", labeller, frame_convention, unlabelled_clips, cuts: [...]}` at `eval/labeling/labels/<title>_cuts.json` (`<title>_cuts.provisional.json` when `--labeller` is not `human`). A cut is the 0-based global index of the first frame of the new shot, which matches `src/nip/timeline/shots.py`.

### B-050 · Label Studio project design: all-intra clips with overlap, and local-files serving

- **Date / commit:** 2026-10-16 · `d4cb1c2` · 1.9
- TimelineLabels with one `Cut` label, marked as a one-frame range on the first frame of the new shot; media served through Label Studio's local-files storage (no separate HTTP server). Whatever compose service runs the `labeling` profile needs `LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true`, `LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=/label-studio/files` and `-v ./data:/label-studio/files`.
- 60 s clips (1,440 frames), 640 wide, all-intra (`-g 1`) so every frame is seekable in the browser; clips after the first start one frame early so a boundary cut stays visible (LS frame 1 is ignored on pull). The clip count and mapping check are in the [journal](journal.md#2026-10-16--19-label-studio-cut-labelling-project-verified-against-a-real-label-studio-1232-container).
- Still open (reviewer minor): the README starts Label Studio with a hand-written `docker run`, whereas docs/project-structure.md specifies `docker compose --profile labeling up` on :8081, and `push` is not idempotent (a rerun creates a duplicate project).

### B-051 · Provisional agent labels for EXP-002

- **Date / commit:** 2026-10-16 (ledger preflight) · 1.9 / 1.8B · **Controller ruling**
- **Context:** the user does not know how to label shot cuts by hand.
- **Ruling:** an agent produces provisional cut labels by frame inspection, documented as agent-labelled (`labeller: agent`), and the Label Studio project is prepared so the user can spot-check later.
- **Cost if wrong:** the EXP-002 F1 is biased by the labeller; it must be re-run after a human check.

## 1.11 Eval metrics and MLflow

### B-052 · Match score is one plus overlap

- **Date / commit:** 2026-10-15 · `a329f4a` · 1.11
- **Context:** the docs say "optimal one-to-one on overlap scores" without defining the objective.
- **Options:** maximise the plain sum of overlaps (a single high-overlap pair can outscore two lower-overlap pairs and lose a match); score each valid pair `1 + overlap`. **Choice:** `1 + overlap` through `scipy.optimize.linear_sum_assignment`, per (episode, check) block. Match count first, quality second; it never trades a match for overlap quality. A test builds a case where greedy finds 1 match and the assignment finds 2.

### B-053 · Native labels raise precision only

- **Date / commit:** 2026-10-15 · `a329f4a` · 1.11
- After injected-label matching, unmatched flags are matched against `*.native.jsonl` labels. A hit is a native TP and raises precision's numerator only. Native labels are not in the recall denominator (they are not planted errors) and are never counted as FN.

### B-054 · TP attribution is per side for equivalent checks

- **Date / commit:** 2026-10-15 original, `159b005` fix · 1.11 (review Important I-1)
- **Problem:** a `cont.prop_text` flag matching a `plot.prop_provenance` label was booked only under the label's check, inflating `plot.prop_provenance` precision and showing no TP for `cont.prop_text`; both checks have separate MVP precision targets.
- **Choice:** a matched pair books `tp` under the flag's check and lang (precision side) and `found` under the label's check and lang (recall side). Precision = (tp + native_tp) / (tp + native_tp + fp); recall = found / (found + fn). Global P and R are unchanged (each pair adds one tp and one found). `native_tp` and `found` are now logged as metrics.
- **Consequence:** per-check precision and recall diverge for equivalence-mapped checks (cont.prop_text shows recall 0.0 even though its flag is a TP). Intended and tested; report readers need the note.

### B-055 · Overlap rules: IoU for timed labels, ref match for script labels, context ignored

- **Date / commit:** 2026-10-15 original, `159b005` fix · 1.11 (review Important I-2)
- **Problem:** the first version let a shared `ref` match even when frames were disjoint, and considered context evidence. The implementer's justification ("strictly stricter than IoU, so cannot over-match") was wrong: an extra OR-path can only add matches. A loc.gender flag whose context evidence lay on another label's cue could score a TP for that label.
- **Choice:** the episode must be equal; lang is compared only when both sides set it; `context` evidence is ignored (claim, contradiction, setup, payoff, expected still count); a label with `frames` is a timed target and matches only by temporal IoU >= 0.3 on half-open ranges; a label without `frames` is a script target and matches by a shared `ref`/`scene` string (score 1.0). A zero-width union is guarded.

### B-056 · Smaller metric and logging conventions

- **Date / commit:** 2026-10-15 · `a329f4a` · 1.11
- Zero denominators give 0.0 (like sklearn `zero_division=0`). Std is the sample standard deviation (`statistics.stdev`) across seeds; a single run prints the mean only.
- Verification effect = share of FPs (resp. TPs) among all flags where any of evidence / rule_recheck / judge is `"fail"`; it requires the pipeline to emit dropped flags as `suppressed`.
- Noise = shown FPs per content-hour (overall and per agent), needs `--content-hours`; cost metrics = `--gpu-seconds` / `--wall-seconds` per content-hour. Per-slot and per-agent cost and cache-hit rate are not computed (no pipeline telemetry yet).
- MLflow metric keys: `{shown|all}/{precision|recall|f1|tp|fp|fn}/{all|check/<id>|lang/<code>}`, `verification/{fp,tp}_dropped_rate`, `noise/fp_per_hour[/agent/<agent>]`, `cost/{gpu,wall}_s_per_hour`, `coverage`.
- One MLflow run = one (variant, seed). `nip eval run` takes one flags file and `--seed` (tag only; labels are not filtered by the label `seed` field). `compare` groups runs by the `variant` tag (runs without one are their own column) and takes mean +- std over the group.
- Tags: `commit, seed, baseline, flags_sha256, labels_sha256, exp, variant` and, with `--plan`, `plan_fingerprint` (sha256 of catalog_sha256 + sorted slot->variant, first 16 hex), `objective, mode, plan_sha256`. Params: `variant.<slot>`, `prompt_version.<check>`, plus `--param k=v`.
- Output dir `eval/<benchmark_run_id>/` (`<set>-s<seed>-<UTC timestamp>`) holds `report.md`, `report.json`, `flags.jsonl` and `plan.json`; it is also logged as MLflow artifacts. It is not git-ignored (needs an integration step).

## 1.4 Timeline, check interface, report

### B-057 · The timeline read model is a new contract in `nip.contracts.timeline`

- **Date / commit:** 2026-10-16 · `172e19e` · 1.4 · **Controller ruling** (accepted in principle)
- **Context:** checks and verification must read the timeline, but project-structure.md forbids `agents` and `verification` from importing `nip.timeline`; in the full design they read it from the store, and Phase 1 has no store-backed timeline.
- **Options:** (a) a Protocol in `base.py` with per-check duck typing; (b) a read model in `nip.store`; (c) a Pydantic contract. **Choice:** (c): `Span` and `Timeline` in contracts, built by `nip.timeline.estimate`; display strings (`tc_in`/`tc_out`/`scene`) are precomputed so consumers need no timecode math.
- **Ruling:** accept the two new contract files as additive (existing Flag, Evidence, Fact, Plan, HardwareInventory unchanged). Cost if wrong: move two modules later. Phase 2's store loader should produce the same `Timeline` from the `scene`/`shot`/`subtitle_cue` tables.
- **Deferred minor M1:** `_by_ref` is built only in `model_post_init`, so `model_copy(update=...)` leaves a stale index; Phase 2 alignment is where someone would copy-with-update.

### B-058 · The report shape is a contract, with its builder beside it

- **Date / commit:** 2026-10-16 · `172e19e` · 1.4. The API (which may only depend on contracts and store) must serve this shape, so the model is a contract. `build_report` depends only on contracts, so it lives in the same file instead of a new module. `RunStatus` is a `Literal` of the six statuses in api-contracts.md. The api-contracts example round-trips byte-for-byte as JSON.

### B-059 · Estimates are not scaled to the picture's length

- **Date / commit:** 2026-10-16 · `172e19e` · 1.4
- With a probe, scenes use the probed fps but keep page-based lengths; scenes are clipped at the picture's end, and a scene that starts past the end keeps its ref (still citable, shown as the script-estimate label) with `frames=None`. Without a probe: 24 fps, duration = the end of the last scene or cue, whichever is later.
- **Why:** scripts can cover only part of the picture (Sintel's covers the first minute of a 14.8-minute film); scaling would stretch it over the whole film.

### B-060 · Page length from a screenplay-format line count

- **Date / commit:** 2026-10-16 · `172e19e` · 1.4
- Fountain and FDX have no pages and the PDF parser discards page breaks, so one layout estimate serves all three formats. Widths (action/heading/transition 60 columns, dialogue 35, parenthetical 25) and 55 lines per page are module constants in `estimate.py`, not `config/pipeline.yaml` (owned by another agent, and it states "only keys that code reads"). Calibration: one sample (Sintel: 54 lines = 0.98 page for a file labelled "1st minute script"); uncalibrated beyond that.

### B-061 · Script-estimate display rules apply per object, not per episode

- **Date / commit:** 2026-10-16 · `172e19e` · 1.4 · **Controller ruling** (one of three accepted deviations)
- data-model.md says that in script-estimate mode `tc_in/tc_out` are replaced by `scene`. Implemented only for estimated objects (scenes) as `"{ep} · Sc {no} (script estimate)"`; subtitle cues and shots have real times and keep SMPTE `tc_in`/`tc_out` (start TC added, drop-frame from the probe). `tc_out` is the exclusive out frame (EDL convention; matches the doc example's 6.2 s for 00:12:04:08 to 00:12:10:13).
- **Cost if wrong:** re-tiering or re-labelling change in Phase 2/4. The reviewer called it sensible.

### B-062 · Sub-frame cues keep one frame, and shot refs use the list index

- **Date / commit:** 2026-10-16 · `172e19e` · 1.4
- A sub-frame cue keeps one frame, `frames = (in, max(out, in + 1))`, because half-open ranges must be non-empty (contract validator). Readability checks that need sub-frame precision must recompute duration from the cue's ms (the reviewer notes ms durations are not kept on `Span`).
- Shot ref id = index in the shot list (`{ep}/shot/{i}`), the same as `keyframes.py`'s shot index; the store will map indices to DB ids when shots are persisted.

### B-063 · Check interface: requires, units, run

- **Date / commit:** 2026-10-16 · `172e19e` · 1.4
- `Check` declares `check: CheckId` and `requires: frozenset[Input]` (the activation-matrix columns; `active(available)` is a subset test). `units(tl)` returns `WorkUnit(key, spans)`: the key is `work_unit.unit_key`, the spans are exactly what the unit reads (ready for cache-key hashing). `run(unit, tl)` returns `Finding`s. Only the cue-window unit generator exists (`cue_windows`, default 20 cues, from the doc's `S01E03/es-419/200-219` example); scene and shot-pair generators arrive with the checks that need them.

### B-064 · `emit` enforces evidence-or-nothing and assigns the tier

- **Date / commit:** 2026-10-16 · `172e19e` · 1.4 · **Controller ruling** (accepted deviation: tier set at emission)
- D-005 is enforced at the source: every evidence ref must resolve to a timeline span of the same kind, otherwise the finding is dropped with a WARNING (`dropped <check> finding: evidence <ref> does not resolve`). Resolved evidence gets the span's `frames` and display fields (the timeline wins over anything the check set). Quote matching is verification step 1's job, not `emit`'s.
- Non-timeline kinds (`fact`, `clearance_item`, `detection`, `keyframe`, `script_line`, `transcript_segment`) do not resolve yet, so findings citing them are dropped until those objects exist (reviewer M4: the next check that needs facts must extend `emit` rather than bypass it).
- `Flag.tier` is required, so `emit` assigns it from confidence with `NIP_TIER_MUST_REVIEW` (0.90) and `NIP_TIER_REVIEW_RECOMMENDED` (0.70), read from the environment on each call. Verification routing may re-assign later; the clearance pending/denied -> `must_review` rule is not implemented (no clearance checks in Phase 1).

### B-065 · Report ranking: sections in consequence order, then severity and confidence

- **Date / commit:** 2026-10-16 · `172e19e` · 1.4 · **Controller ruling** (accepted deviation)
- Sections in consequence order clearance -> continuity -> localization -> plot_hole (always all four, empty lists allowed, as in the doc example); within a section severity descending, then confidence descending. The finer "wrong names, spoilers, then readability" order inside localization is left to severity. `counts` always lists all three tiers and includes suppressed flags; suppressed flags appear in sections only with `include_suppressed=True`. `FlagSummary.id` is `None` until persistence assigns `flg_...` ids. `primary_tc` = the first `claim` evidence's `tc_in`, else its `scene` label.
- **Cost if wrong:** re-sorting later. Reviewer M2: add a per-check rank when the second localization check lands.

### B-066 · Duplicate timeline refs are rejected

- **Date / commit:** 2026-10-16 · `172e19e` · 1.4
- A script with two scenes numbered the same (the 1.3 parser only warns; auto-numbering can collide with explicit numbers) makes `{ep}/sc/{no}` ambiguous, so `Timeline` raises `ValueError("duplicate timeline refs: ...")`. The alternative (suffixing) would invent refs. **Consequence:** such a script cannot run until renumbered. Reviewer M3: a raw `ValueError` is a poor user-facing failure; the better home is ingest validation, carried into the 1.10 dispatch.

## Process decisions

### B-067 · CLI wiring is a separate integration step

- **Date:** 2026-10-15 · **Controller ruling** (ledger preflight)
- **Context:** `src/nip/cli.py` is touched by nearly every deliverable. **Ruling:** wave-1 agents do not edit it; each ships a `typer.Typer()` sub-app and states the one `app.add_typer(...)` line, and wiring is done in wave 2. Cost if wrong: one extra integration step. Wiring lines pending: `picture.app` as `timeline` (1.8), `planner.app` as `plan` (1.6), `eval_app` as `eval` with `corpus` and `labels` sub-apps (1.11, 1.9).

### B-068 · Compose ownership: 1.5 owns compose.yaml including MLflow

- **Date:** 2026-10-15 · **Controller ruling.** 1.5 owns `compose.yaml` including the MLflow service; 1.11 owns the eval run/compare code and tests it on a local MLflow file/sqlite store. (1.11's MLflow behaviour against the compose Postgres plus SeaweedFS backend is therefore unexercised.)

### B-069 · Agents write notes, a later step merges them into `build-log/`

- **Date:** 2026-10-15 and 2026-10-16 · **Controller rulings**
- Agents write `notes/<id>.md` (journal entries, decision proposals, doc corrections, numbers) because concurrent writes to shared logs would collide. A docs agent merges after each wave.
- After the user made `docs/` read-only (2026-10-16), the record goes to the new committed folder `build-log/` (journal, decisions, experiments, doc-corrections, review-findings) instead of the original docs. Cost if wrong: the user may later want it merged into `docs/` themselves.

### B-070 · Parallel agents on disjoint paths with path-scoped commits

- **Date:** 2026-10-15; commit rule changed 2026-10-16 · **Controller ruling**
- **Context:** the review skill says "never parallel implementers"; the user instruction said to deploy multiple agents. The user's instruction wins; agents run in parallel only on disjoint paths.
- **Process fix after two index sweeps:** the commit rule became `git add <own files>` then `git commit -m ... -- <paths>`, which commits only those paths even when another agent has staged files. Agents never `git add -A`, `git stash`, `git reset` or `git checkout -- .`, and never push. See the [journal](journal.md#2026-10-16--process-shared-index-sweeps-between-agents-and-the-fix).

### B-071 · SDD workspace is kept, not deleted

- **Date:** 2026-10-16 · **Controller ruling.** The git-ignored `.superpowers/` workspace holds the agents' notes, reports and reviews that are source material for this folder, and the user said not to delete things; it stays.
