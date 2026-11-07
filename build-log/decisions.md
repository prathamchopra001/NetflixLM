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
| [B-073](#b-073--one-serve-app-per-variant-vllm-as-a-child-process-group-placeholders-for-actor-slots) | 1.7 | One Serve app per variant, vLLM as a child process group, actor placeholders |
| [B-074](#b-074--max_constructor_retry_count1-on-every-app) | 1.7 | `max_constructor_retry_count=1` |
| [B-075](#b-075----enforce-eager-on-gpus-of-16-gib-or-less-fp8-kv-not-set) | 1.7 | `--enforce-eager` on GPUs of 16 GiB or less, fp8 KV not set |
| [B-076](#b-076--serve-http-on-00008000-clients-default-to-1270018000) | 1.7 | Serve HTTP on 0.0.0.0:8000, clients on 127.0.0.1 |
| [B-077](#b-077--teardown-waits-for-vram-to-return-to-idle-plus-256-mib-measured-per-group) | 1.7 | Teardown waits for idle + 256 MiB, per group |
| [B-078](#b-078--deploys-inside-a-group-are-sequential) | 1.7 | Deploys inside a group are sequential |
| [B-079](#b-079--only-the-llm-client-in-phase-1-stubs-are-minimal-valid-schema-instances-instructor-deferred) | 1.7 | Only the LLM client in Phase 1, minimal-valid stubs, instructor deferred |
| [B-080](#b-080--dev-compose-override-instead-of-editing-composeyaml-openai-added-unpinned) | 1.7 | Dev compose override, `openai` unpinned |
| [B-081](#b-081--exp-001-method-interleaved-rounds-one-start-per-trial-exact-kv-gate-fixed-length-decoding) | 1.7 | EXP-001 method |
| [B-082](#b-082--checkpoint-for-qwen35-4b-awq-is-cyankiwiqwen35-4b-awq-4bit-in-the-catalog) | 1.7 | AWQ checkpoint in the catalog (controller ruling) |
| [B-083](#b-083--exact-kv-budgets-on-single-gpu-engines-sized-by-the-planner-from-probed-free-vram) | 1.7 | **Exact KV budgets sized from probed free VRAM** (controller ruling, EXP-001 decision) |
| [B-084](#b-084--exp-001-calibration-applied-to-the-catalog-and-the-awq-checkpoint-added) | 1.7 | EXP-001 calibration applied to the catalog (controller ruling) |
| [B-085](#b-085--the-startup-peak-is-a-fit-floor-not-subtracted-from-the-kv-budget) | 1.7 | Startup peak is a fit floor (controller ruling) |
| [B-086](#b-086--additive-contract-and-catalog-fields-slotdecisionkv_cache_bytes-variantstartup_peak_gb) | 1.7 | Additive fields `kv_cache_bytes`, `startup_peak_gb` (controller ruling) |
| [B-087](#b-087--stop-always-kills-the-process-group-and-liveness-ignores-zombies) | 1.7 | `stop()` kills the process group, zombie-aware |
| [B-088](#b-088--exact-kv-applies-to-every-single-gpu-engine-leftover-goes-to-kv-only-when-the-engine-is-alone-on-its-gpu) | 1.7 | Exact KV on every single-GPU engine (controller ruling) |
| [B-089](#b-089--cut-labels-use-the-pull-object-format-the-masks-go-in-a-separate-sidecar) | 1.8B | Cut labels in `pull` format, masks in a sidecar |
| [B-090](#b-090--the-exp-002-headline-metric-is-masked-the-unmasked-f1-is-always-reported) | 1.8B | Masked headline metric, unmasked always reported |
| [B-091](#b-091--seconds-per-video-minute-is-the-wall-time-of-the-full-detector-one-process-3-repeats-defaults) | 1.8B | Seconds per video-minute definition |
| [B-092](#b-092--provisional-labels-by-candidate-union-and-contact-sheets-with-a-committed-verification-record) | 1.8B | Provisional labels: candidate union, contact sheets, verification record |
| [B-093](#b-093--exp-002-decision-keep-transnetv2-provisionally-as-a-costrisk-call-not-a-result) | 1.8B | EXP-002: keep TransNetV2 provisionally (cost/risk) |
| [B-094](#b-094--no-change-to-part-a-after-exp-002-and-where-the-experiment-files-live) | 1.8B | No part A change; file locations |
| [B-095](#b-095--tears-of-steel-is-not-labelled-so-half-of-exp-002-is-open) | 1.8B | Tears of Steel not labelled |
| [B-096](#b-096--one-flag-per-cue) | 1.10 | One flag per cue |
| [B-097](#b-097--gap-and-overlap-rules-belong-to-the-later-cue) | 1.10 | Gap and overlap rules belong to the later cue |
| [B-098](#b-098--durations-cps-and-gaps-are-measured-in-frames-not-milliseconds) | 1.10 | Frames, not milliseconds |
| [B-099](#b-099--rule-pack-layout-section-wise-merge-no-silent-fallback-to-another-language) | 1.10 | Rule pack layout |
| [B-100](#b-100--gap-closing-is-part-of-locreadability-severity-2-tier-follows-confidence) | 1.10 | Gap-closing: severity 2, tier follows confidence |
| [B-101](#b-101--requires--source_subs-target_subs-no-source-track-means-the-check-is-skipped) | 1.10 | `requires` and skip without a source track |
| [B-102](#b-102--verification-is-nipverificationverify-with-the-re-check-injected-dropped-flags-are-kept-apart) | 1.10 | Verification with injected re-check; drops kept apart |
| [B-103](#b-103--srcnippipelinepy-is-the-phase-1-composition-root-and-nip-run-takes-files) | 1.10 | `pipeline.py` composition root, `nip run` takes files |
| [B-104](#b-104--no-plan-for-the-walking-skeleton-run) | 1.10 | No Plan for the walking skeleton |
| [B-105](#b-105--keyframes-live-on-the-timeline-as-one-frame-spans) | 1.10 | Keyframes as timeline spans |
| [B-106](#b-106--duplicate-scene-numbers-are-rejected-at-ingest-not-as-a-timeline-crash) | 1.10 | Duplicate scene numbers rejected at ingest |
| [B-107](#b-107--the-walking-skeleton-benchmark-set-and-the-machine-triaged-native-labels) | 1.10 | Benchmark set name, machine-triaged native labels |
| [B-108](#b-108--the-locreadabilityv1-injector-isolated-cues-one-kind-per-pick-ref-based-labels) | 1.10 | `loc.readability.v1` injector |
| [B-109](#b-109--the-sintel-picture-stage-is-reused-from-the-cached-18b-run) | 1.10 | Sintel picture stage reused from the cached run |
| [B-110](#b-110--cli-wiring-executed) | 1.10 | CLI wiring executed |
| [B-111](#b-111--cli-import-cost-accepted-for-now-superseded-by-b-113) | 1.10 | CLI import cost accepted (**Superseded** by B-113) |
| [B-112](#b-112--nip_config_dir-with-auto-detection) | 1.10 | `NIP_CONFIG_DIR` with auto-detection |
| [B-113](#b-113--lazy-torch-mlflow-and-scipy-imports-in-the-cli-superseding-b-111) | 1.10 | Lazy imports in the CLI |
| [B-114](#b-114--the-closeout-fixes-only-the-load-bearing-minors-everything-else-is-deferred-and-listed) | closeout | Closeout fixes only load-bearing minors |
| [B-115](#b-115--kv-calibration-restated-per-1024-tokens-446---458) | closeout | KV calibration per 1,024 tokens (44.6 -> 45.8) |
| [B-116](#b-116--the-kv-budget-must-be-positive-zero-is-rejected-not-ignored) | closeout | KV budget must be positive |
| [B-117](#b-117--shared-gpu-exact-kv-the-premise-was-wrong-pinned-with-a-test-instead-of-changed) | closeout | Shared-GPU exact KV: pinned, not changed |
| [B-118](#b-118--closeout-hygiene-ray-head-init-true-laptop-only-dev-realm-gitignore-pattern-and-timecode-strictness) | closeout | Closeout hygiene |
| [B-119](#b-119--phase-1-is-closed-with-caveats-after-an-exit-criteria-check-run-against-the-commit) | closeout | Phase 1 closed with caveats |
| [B-120](#b-120--phase-2-plan-rulings-r1-to-r15-adopted) | process | Phase 2 plan rulings R1 to R15 adopted |
| [B-121](#b-121--commit-by-explicit-file-paths-not-directory-pathspecs) | process | Commit by explicit file paths |
| [B-122](#b-122--cache-objects-are-gzip-json-not-zstd) | 2.9B-1 | Stage-cache objects are gzip JSON, not zstd |
| [B-123](#b-123--every-check-units-cache-key-includes-the-unit-key) | 2.9B-1 | Check cache keys include the unit key |
| [B-124](#b-124--a-clearance-status-change-shows-in-the-run-diff-as-resolved--new) | 2.9B-1 | Clearance status change = resolved + new in the run diff |
| [B-125](#b-125--changed_inputs-labels-a-source-by-version-label-else-src_id) | 2.9B-1 | `changed_inputs` source labels |
| [B-126](#b-126--reading-a-run-is-open-to-every-authenticated-role) | 2.9B-1 | Run reads open to every authenticated role |
| [B-127](#b-127--phase-2s-commit-messages-were-rewritten-once-before-the-first-push-to-drop-claude-co-author-trailers) | process | phase-2 messages rewritten once to drop Claude trailers before the first push |
| [B-128](#b-128--tests-force-typers-plain-non-rich-terminal-output) | CI | Tests force Typer's plain output |
| [B-129](#b-129--tests-that-need-local-data-files-are-marked-integration-ci-is-replayed-locally-before-a-push) | CI | Local-data tests are integration; replay CI locally before a push |
| [B-130](#b-130--nip-ingest-takes-tagpath-positionals) | 2.0 | `nip ingest` takes `[TAG=]PATH` positionals |
| [B-131](#b-131--episode_seq--season--1000--number) | 2.0 | `episode_seq = season * 1000 + number` |
| [B-132](#b-132--frames-at-ingest-a-non-24-fps-picture-after-24-fps-rows-is-refused) | 2.0 | Frames at ingest; a non-24 fps picture after 24 fps rows is refused |
| [B-133](#b-133--replacing-an-episodes-source-is-refused-show-level-files-are-upserted) | 2.0 | Replacing an episode's source is refused; show-level files upserted (superseded in part by 2.9B-1) |
| [B-134](#b-134--bible-mapping-to-entity-and-entity_alias) | 2.0 | Bible mapping to `entity` / `entity_alias` |
| [B-135](#b-135--script_lineseq-is-1-based-within-its-scene) | 2.0 | `script_line.seq` is 1-based within its scene |
| [B-136](#b-136--line-asr-fact-and-clearance-refs-are-built-in-nipstoreload) | 2.0 | Line/ASR/fact/clr refs built in `nip.store.load` |
| [B-137](#b-137--fact-spans-carry-their-source-quotes-clearance-item-spans-carry-the-item-name) | 2.0 | Fact spans carry source quotes; clearance spans the item name |
| [B-138](#b-138--the-checks-construction-convention) | 2.0 | The `CHECKS` construction convention |
| [B-139](#b-139--run-artifacts-are-per-episode) | 2.0 | Run artifacts are per episode |
| [B-140](#b-140--run-lifecycle-and-the-stage-contract-epunit-gaps-coverage-from-check-units) | 2.0 | Run lifecycle and the stage contract (`ep.unit()`, gaps, coverage from check units) |
| [B-141](#b-141--artifacts-are-published-only-after-the-commit-the-whole-run-is-one-transaction) | 2.0 | Artifacts published after commit; whole run one transaction (controller ruling) |
| [B-142](#b-142--a-store-run-plans-with-current_plan) | 2.0 | A store run plans with `current_plan({})` |
| [B-143](#b-143--the-file-mode-cli-is-renamed-nip-run-files-nip-run-is-the-store-command) | 2.0 | File-mode CLI renamed `nip run-files` |
| [B-144](#b-144--keyframe-object-keys-use-the-shot-index) | 2.0 | Keyframe object keys use the shot index |
| [B-145](#b-145--script_linespeaker-is-added-by-28-in-migration-0002) | 2.0 | `script_line.speaker` added by 2.8 in 0002 (controller ruling) |
| [B-146](#b-146--a-serve-client-module-is-named-after-its-slot-clientstext_embedderpy) | 2.0 | Serve client module named after its slot (controller ruling) |
| [B-147](#b-147--every-flag-must-carry-at-least-one-stable-evidence-ref) | 2.0 | Every flag carries a stable evidence ref (controller ruling) |
| [B-148](#b-148--each-work-unit-runs-in-a-savepoint-a-malformed-evidence-ref-is-a-counted-drop) | 2.0 | Work units run in a savepoint; malformed refs are counted drops |
| [B-149](#b-149--nip-eval-compare-prints-every-logged-metric-and-refuses-mixed-groups-r10) | 2.0 | `nip eval compare` prints every metric, refuses mixed groups (R10) |
| [B-150](#b-150--the-store-integration-tests-go-into-ci-in-w-int) | 2.0 | Store integration tests go into CI in W-int (controller ruling) |
| [B-151](#b-151--knowledge-thresholds-stay-module-constants-until-configpipelineyaml-is-free) | 2.1 | Knowledge thresholds stay module constants until pipeline.yaml is free (controller ruling) |
| [B-152](#b-152--llmclient-goes-through-instructor-and-returns-a-plain-instance-parsed-from-the-final-reply) | 2.1 | `LLMClient` through instructor, plain instance re-parsed from the reply |
| [B-153](#b-153--recorded-llm-stub-keyed-by-sha256variant-system-prompt-schema) | 2.1 | Recorded LLM stub keyed by sha256(variant, system, prompt, schema) |
| [B-154](#b-154--registry-keys-are-bible-id-or-canonical-name-candidates-are-not-in-the-enum) | 2.1 | Registry keys are bible id or canonical name; candidates not in the enum |
| [B-155](#b-155--grounding-normalized-partial_ratio--90-ratio-for-over-long-quotes-two-word-minimum) | 2.1 | Grounding: `partial_ratio` ≥ 90, `ratio` for long quotes, two-word minimum |
| [B-156](#b-156--raw-events-were-uploaded-inside-the-stage-deviation-moved-by-w-int) | 2.1 | Raw events uploaded inside the stage (moved to `publish` by W-int) |
| [B-157](#b-157--fact_eventwork_unit_id-stays-null) | 2.1 | `fact_event.work_unit_id` stays NULL |
| [B-158](#b-158--consolidation-re-runs-show-wide-and-keeps-the-ids-of-unchanged-facts) | 2.1 | Consolidation re-runs show-wide and keeps unchanged fact ids |
| [B-159](#b-159--interval-choices-the-docs-left-open) | 2.1 | Interval choices the docs left open |
| [B-160](#b-160--fact-shapes-shared-with-23-and-state-lost-from-losedrop-events) | 2.1 | Fact shapes shared with 2.3; `state: lost` from lose/drop (controller ruling) |
| [B-161](#b-161--names-match-on-whole-words-subset-with-at-least-half-the-words-an-exact-name-scores-101) | 2.1 | Whole-word name matching, exact name scores 101 |
| [B-162](#b-162--object-less-holdsownswearing-events-are-not-stored) | 2.1 | Object-less holds/owns/wearing not stored |
| [B-163](#b-163--exp-006-first-wave-keep-threshold-90-the-bar-is-not-met-by-any-threshold) | 2.1/EXP-006 | Keep threshold 90; no threshold meets the bar |
| [B-164](#b-164--exp-020-first-wave-no-decision-until-the-rule-precision-half) | 2.1/EXP-020 | No decision until the rule-precision half |
| [B-165](#b-165--runaway-guard-at-most-4-events-per-scene-line-enforced-by-the-grammar) | 2.1B | Runaway guard: at most 4 events per scene line |
| [B-166](#b-166--line-is-an-enum-of-the-scenes-line-numbers) | 2.1B | `line` is an enum of the scene's line numbers |
| [B-167](#b-167--post-model-drops-zero-confidence-duplicates-argument-kinds-per-predicate) | 2.1B | Drop zero-confidence, duplicate and mistyped events (`ARG_KINDS`) |
| [B-168](#b-168--the-openai-sdk-under-instructor-runs-with-max_retries0) | 2.1B | OpenAI SDK `max_retries=0` |
| [B-169](#b-169--the-prompt-prints-one-numbered-line-per-script_line) | 2.1B | One printed line per `script_line` |
| [B-170](#b-170--resolved-dialogue-speakers-are-present-at-the-headings-location-d-21b-1) | 2.1B | Derived `present_at` for resolved dialogue speakers, not for off-screen voices |
| [B-171](#b-171--a-candidate-entitys-guessed-kind-is-provisional) | 2.1B | Candidate kinds are provisional |
| [B-172](#b-172--holdsowns-values-are-mapped-only-from-the-prompts-vocabulary-other-verbs-are-dropped-and-counted-d-21b-2) | 2.1B | holds/owns values only from the prompt's verbs (controller ruling) |
| [B-173](#b-173--script_linespeaker-stores-the-character-cue-as-written-d-21b-3) | 2.1B | `script_line.speaker` keeps the cue as written (controller ruling) |
| [B-174](#b-174--all-gpu-work-in-the-exp-harnesses-goes-through-gpu_session-which-releases-only-a-lock-it-owns) | 2.1B | `gpu_session`: the lock is released only by its owner |
| [B-175](#b-175--exp-harness-down-deletes-serve-apps-by-status) | 2.1B | EXP harness `down` deletes Serve apps by status |
| [B-176](#b-176--secret-in-scene-check-for-learnsreferences-measured-not-shipped) | 2.1B | Secret-in-scene check measured, not shipped |
| [B-177](#b-177--prompt-v2-for-learns-vs-references-proposed-not-built) | 2.1B | Prompt v2 for learns vs references proposed, not built |
| [B-178](#b-178--prop_provenance-on-never-obtained-personal-props-lower-tier-proposed-to-23) | 2.1B | Lower tier for never-obtained props proposed to 2.3 |
| [B-179](#b-179--exp-018-do-not-adopt-the-fp8-kv-cache) | 2.1B/EXP-018 | Do not adopt the FP8 KV cache |
| [B-180](#b-180--exp-020-inconclusive-d-025-registry-ids-as-an-enum-stands-by-default) | 2.1B/EXP-020 | Inconclusive; D-025 stands by default |
| [B-181](#b-181--exp-006-ship-the-argument-checks-the-bar-is-still-not-met) | 2.1B/EXP-006 | Ship the argument checks; bar still not met |
| [B-182](#b-182--exp-005-8k-arm-only-inconclusive-until-the-32k-arm-runs) | 2.1B/EXP-005 | 8k arm only; inconclusive until 32k |
| [B-183](#b-183--exp020_rules-is-the-harness-for-future-extraction-experiments) | 2.1B | `exp020_rules` is the extraction-experiment harness |
| [B-184](#b-184--fix-round-1-must-re-measure-the-plot-rules-on-real-facts-later-rounds-re-score-without-the-gpu) | 2.1B | Re-measure plot rules on real facts; later rounds re-score without the GPU (controller ruling) |
| [B-185](#b-185--a-pure-derive-with-the-marker-lexicon-as-module-constants-the-llm-only-for-ambiguous-transitions) | 2.2 | Pure `derive`, lexicon as module constants, LLM only for ambiguous transitions |
| [B-186](#b-186--flashbacks-with-an-unknown-day-rank-first-in-the-show-and-are-inferred) | 2.2 | Unknown-day flashbacks rank first and are inferred |
| [B-187](#b-187--flashback-spans-a-heading-cue-marks-one-scene-a-lead-in-cue-marks-until-the-present-returns) | 2.2 | Flashback spans: heading cue = one scene, lead-in cue = until the present returns |
| [B-188](#b-188--bible-overrides-always-win-including-over-the-llm) | 2.2 | Bible overrides always win, including over the LLM (review fix) |
| [B-189](#b-189--the-stage-re-derives-the-whole-show-for-every-episode-verdicts-memoised-per-variant) | 2.2 | Stage re-derives the whole show per episode; verdict memo per variant |
| [B-190](#b-190--markers-stored-in-the-data-model-set-cues-read-from-every-heading-segment-except-the-location) | 2.2 | Data-model marker set; cues from every heading segment except the location (review fix) |
| [B-191](#b-191--an-ambiguous-transitions-synthetic-variant-so-exp-007-can-discriminate) | 2.2B | Ambiguous-transitions synthetic variant (controller ruling) |
| [B-192](#b-192--exp-007-holds-the-facts-fixed-oracle-facts-only-the-story-columns-vary-between-arms) | 2.2B | EXP-007 holds oracle facts fixed; only story columns vary |
| [B-193](#b-193--how-the-variant-hides-story-time-prose-cues-a-regressing-heading-silent-cases-kept) | 2.2B | How the variant hides story time; silent cases kept |
| [B-194](#b-194--prompt-v2-a-regressing-time-of-day-is-normally-the-next-day) | 2.2B | Prompt v2: a regressing time of day is normally the next day |
| [B-195](#b-195--storyprompt-is-v2) | 2.2B | `story.PROMPT` is v2 (controller ruling) |
| [B-196](#b-196--exp-007-decision-keep-the-llm-step-with-prompt-v2-bible-overrides-first) | 2.2B | EXP-007 decision: keep the LLM step with v2, bible first |
| [B-197](#b-197--the-experiments-down-deletes-serve-apps-by-status-under-the-gpu-lock) | 2.2B | Experiment `down` deletes Serve apps by status, under the GPU lock |
| [B-198](#b-198--three-story-step-improvements-proposed-and-left-undone) | 2.2B | Cascade guard, silent-case trigger, `Verdict.days` cap: proposed, not done |
| [B-199](#b-199--one-parameterized-sql-file-per-rule-claim-on-the-script-line-one-flag-per-claim-line) | 2.3 | One SQL file per rule; claim on the script line; one flag per claim line |
| [B-200](#b-200--severities-4--3--3--2-the-inferred-story-factor-applied-once-on-raw-event-confidence) | 2.3 | Severities 4/3/3/2; inferred factor applied once on raw event confidence |
| [B-201](#b-201--the-fact-contract-the-rules-assume-and-what-21-must-emit) | 2.3 | Fact contract the rules assume (use = `holds` event with `event: use`) |
| [B-202](#b-202--marker-exemptions-dead_acts-and-two_places-skip-flashbackdreamvision-the-other-two-do-not) | 2.3 | Marker exemptions per rule |
| [B-203](#b-203--two_places-orients-a-pair-by-screen-order-so-it-is-flagged-once-in-the-later-episode) | 2.3 | `two_places` orients pairs by screen order |
| [B-204](#b-204--the-re-check-re-runs-the-rules-sql-and-compares-only-the-claim-line) | 2.3 | Re-check re-runs the SQL, compares only the claim line |
| [B-205](#b-205--the-oracle-facts-loader-lives-in-evalexplayer1_oraclepy-tagged-plot-l1) | 2.3 | Oracle-facts loader in `eval/exp/layer1_oracle.py`, tag `PLOT-L1` |
| [B-206](#b-206--lost-is-handled-like-destroyed-21-builds-state-lost-facts) | 2.3 | `lost` like `destroyed`; 2.1 builds `state: lost` facts (controller ruling) |
| [B-207](#b-207--cue-alignment-fits-one-line-per-track-by-onset-coincidence-then-measures-overlap-on-that-line) | 2.4 | Cue alignment fits one line per track by onset coincidence, then overlap on that line |
| [B-208](#b-208--links-are-persisted-by-the-stage-the-checks-recompute-them) | 2.4 | Links persisted by the stage; checks recompute them |
| [B-209](#b-209--drift-and-offset-require-the-picture-superseded-by-b-210) | 2.4 | drift and offset require the picture (**Superseded** by B-210) |
| [B-210](#b-210--drift-and-offset-run-without-a-picture-and-say-less) | 2.4 | drift and offset run without a picture: rate-pair causes, offset in seconds |
| [B-211](#b-211--locterm-matching-rules) | 2.4 | loc.term matching rules (phrase integrity, common-noun inflection, confidences) |
| [B-212](#b-212--observed-standard-per-episode-names-kept-verbatim-only-superseded-by-b-213) | 2.4 | Observed standard per episode, verbatim only (**Superseded** by B-213) |
| [B-213](#b-213--observed-standard-over-the-whole-show-recomputed-every-run) | 2.4 | Observed standard over the whole show, recomputed every run |
| [B-214](#b-214--native-labels-for-shot_change-come-from-the-clean-run-and-are-a-regression-guard-not-truth) | 2.4 | shot_change natives from the clean run are a regression guard; raw column is the precision |
| [B-215](#b-215--the-tos-it-offset-injection-runs-in-process) | 2.4 | ToS `it` offset injection runs in-process |
| [B-216](#b-216--shot_change-passes-an-out-point-at-cut---2--cut-and-flags-points-on-either-side-of-a-cut) | 2.4 | shot_change passes out points at cut - 2 .. cut; flags either side of a cut |
| [B-217](#b-217--the-benchmark-driver-lives-in-evalexploc_benchpy-and-runs-at-a-committed-sha) | 2.4 | Benchmark driver in `eval/exp/loc_bench.py`, run at a committed SHA |
| [B-218](#b-218--24-follow-ups-assigned-to-w-int) | 2.4 | Injector fix and stale MLflow runs assigned to W-int (controller ruling) |
| [B-219](#b-219--faster-whispers-own-audio-decoder-is-bypassed-nip-reads-a-16-khz-wav) | 2.5 | faster-whisper's PyAV decoder bypassed; nip reads a 16 kHz wav |
| [B-220](#b-220--laptop-asr-default-is-faster-whisper-large-v3-turbo-int8) | 2.5 | Laptop ASR default is large-v3-turbo-int8 |
| [B-221](#b-221--decoding-no-vad-temperature-fallback-min_prob-05-superseded-by-b-222-for-the-fallback-and-the-filter) | 2.5 | No VAD + temperature fallback + min_prob 0.5 (**Superseded** by B-222) |
| [B-222](#b-222--asr-decoding-default-is-the-deterministic-novad-hst-arm) | 2.5 | ASR decoding default is the deterministic `novad-hst` arm (controller ruling) |
| [B-223](#b-223--token-level-alignment-is-the-default-with-a-03-s-first-word-cap) | 2.5 | Token-level alignment default with a 0.3 s first-word cap |
| [B-224](#b-224--not_in_cut-needs-at-least-8-unplaced-dialogue-words) | 2.5 | `not_in_cut` needs at least 8 unplaced dialogue words |
| [B-225](#b-225--exp-004-ground-truth-derived-as-broadcast-scripts-labels-outside-evallabels) | 2.5 | EXP-004 ground truth from derived scripts, labels in `eval/exp/exp004_labels/` (controller ruling) |
| [B-226](#b-226--timeline-stages-type-the-episode-with-a-protocol-instead-of-importing-nippipeline) | 2.5 | Timeline stages typed by a Protocol, no `nip.pipeline` import |
| [B-227](#b-227--exp-003-logs-substitutionsdeletions-and-per-film-sdi-next-to-wer) | 2.5 | EXP-003 logs sub+del and per-film S/D/I next to WER |
| [B-228](#b-228--no-transcript-spans-on-the-timeline-yet) | 2.5 | No transcript spans on the Timeline yet |
| [B-229](#b-229--the-ocr-slot-uses-rapidocr-onnx-runtime-with-pp-ocrv6-medium-the-catalog-id-pp-ocrv6-medium-is-kept) | 2.6 | `ocr` slot uses RapidOCR (ONNX Runtime) with PP-OCRv6 medium |
| [B-230](#b-230--ocr-detection-on-the-gpu-recognition-on-the-cpu) | 2.6 | OCR detection on GPU, recognition on CPU |
| [B-231](#b-231--the-cpu-onnxruntime-is-excluded-from-the-lock) | 2.6 | CPU `onnxruntime` excluded from the lock |
| [B-232](#b-232--fiction-reserved-phone-numbers-are-matched-on-the-national-significant-number) | 2.6 | Fiction-reserved numbers matched on the national significant number |
| [B-233](#b-233--555-01000199-is-fiction-reserved-under-every-area-code) | 2.6 | 555-0100..0199 reserved under every area code (controller ruling) |
| [B-234](#b-234--reserved-domains-are-filtered-in-code) | 2.6 | Reserved domains filtered in code |
| [B-235](#b-235--textscanner-takes-one-language-fictional-and-deny-listed-brands-are-constructor-arguments) | 2.6 | `TextScanner` takes one language; fictional/deny-listed brands as arguments |
| [B-236](#b-236--presidio-without-gpl-spacy-models-gliner-carries-names-gliner-with-its-own-word-splitter-and-no-extra-weights) | 2.6 | Presidio without GPL spaCy; GLiNER for names, own word splitter, no extra weights |
| [B-237](#b-237--gliners-cap-transformers5170-is-accepted-for-now) | 2.6 | gliner's transformers<5.17 cap accepted; vLLM smoke in W-int (controller ruling) |
| [B-238](#b-238--plate-patterns-are-case-sensitive-allow-one-space-and-exclude-caption-words-by-name) | 2.6 | Plate patterns case-sensitive, one space, caption stop-lists |
| [B-239](#b-239--gb-drama-ranges-from-a-secondary-source-of-ofcoms-table-unverifiable-blocks-removed) | 2.6 | GB drama ranges from a secondary source of Ofcom's table; unverifiable blocks removed |
| [B-240](#b-240--ocr-and-ner-clients-read-nip_serve_url) | 2.6 | OCR/NER clients read `NIP_SERVE_URL` |
| [B-241](#b-241--ocr-url-cleanup-joins-a-spaced-dot-only-before-a-known-tld-cctlds-only-in-lower-case) | 2.6 | OCR URL cleanup: known TLDs only after a spaced dot; ccTLDs lower case |
| [B-242](#b-242--gliner-spans-that-overlap-a-structured-finding-are-not-second-findings) | 2.6 | GLiNER spans overlapping a phone/URL/email are not second findings |
| [B-243](#b-243--identifiers-match-exactly-names-fuzzily-the-strictest-status-wins) | 2.7 | Identifiers match exactly, names fuzzily; strictest status wins |
| [B-244](#b-244--pendingdenied-are-must_review-and-cleared-suppressed-whatever-the-confidence) | 2.7 | Pending/denied `must_review`, cleared `suppressed`, whatever the confidence |
| [B-245](#b-245--candidate-confidence--ocr-confidence-x-maxrecognizer-score-certainty-floor) | 2.7 | Confidence = OCR x max(recognizer score, certainty floor) |
| [B-246](#b-246--occurrences-merge-by-a-2-s-gap-between-keyframe-cells-scene-boundaries-are-not-used) | 2.7 | Occurrences merge by a 2 s gap between keyframe cells, not by scene |
| [B-247](#b-247--a-keyframe-span-stands-for-its-cell-the-flags-claim-is-the-keyframes-superseded-by-b-248) | 2.7 | Keyframe-cell claims (**Superseded** by B-248) |
| [B-248](#b-248--the-claim-is-the-occurrences-frame-range-as-a-clrocc-hash-span) | 2.7 | Claim = occurrence frame range as a `clr/occ-` span (controller ruling) |
| [B-249](#b-249--each-occurrence-has-its-own-stable-ref-so-r13-fingerprints-separate-distinct-items) | 2.7 | Per-occurrence stable ref; 0 fingerprint collisions |
| [B-250](#b-250--a-one-edit-ocr-slip-of-a-pendingdenied-phone-or-plate-escalates-to-must_review) | 2.7 | One-edit slip of a pending/denied phone or plate escalates (controller ruling) |
| [B-251](#b-251--exp-008-keep-the-4-s--2-s-keyframe-policy-as-a-recorded-override-of-the-bar) | 2.7 | EXP-008: keep 4 s / 2 s keyframes as an override of the bar (controller ruling) |
| [B-252](#b-252--exp-017-keep-the-dedicated-ocr-engine-pp-ocrv6-medium-via-rapidocr) | 2.7 | EXP-017: keep the OCR engine over the vision model |
| [B-253](#b-253--credits-and-title-cards-give-no-gliner-brand-or-address-guesses) | 2.7 | Credits and title cards give no GLiNER brand/address guesses |
| [B-254](#b-254--credits-urls-are-correct-unknown-flags-precision-is-reported-against-injected-labels-only-junk-is-dropped-by-rule) | 2.7 | Credits URLs are native labels; precision vs injected labels only; junk by rule (controller ruling) |
| [B-255](#b-255--the-clearance-log-is-matched-before-any-junk-rule) | 2.7 | The clearance log is matched before any junk rule |
| [B-256](#b-256--no-ner-pin-in-code-the-plannercatalog-decides-the-ner-variant) | 2.7 | No NER pin in code; planner decides (controller ruling) |
| [B-257](#b-257--pipelinepy-two-stages-and-the-slot-tables-beyond-the-one-sanctioned-add_stage) | 2.7 | `pipeline.py`: two stages and slot tables beyond the one sanctioned line (ratified) |
| [B-258](#b-258--clearance-csv-per-run-and-episode-cli-now-api-route-later) | 2.7 | Clearance CSV per run and episode; CLI now, API route in 4.1 |
| [B-259](#b-259--crop-sharpness-is-stored-as-a-companion-detection-row) | 2.7 | Crop sharpness as a companion `detection` row |
| [B-260](#b-260--unknown-plates-stay-at-their-recognizer-score-and-suppressed) | 2.7 | Unknown plates stay at their score and `suppressed` |
| [B-261](#b-261--the-embedder-client-module-is-clientstext_embedderpy) | 2.8 | Embedder module named `clients/text_embedder.py` (controller ruling) |
| [B-262](#b-262--script_linespeaker-text-in-migration-0002-holds-the-raw-character-cue) | 2.8 | `script_line.speaker` in migration 0002 (controller ruling) |
| [B-263](#b-263--unique-scene_id-kind-embedder_variant-on-scene_chunk-the-writer-is-an-upsert) | 2.8 | `UNIQUE (scene_id, kind, embedder_variant)`; upsert writer |
| [B-264](#b-264--one-hnsw-partial-expression-index-per-catalog-embedder-variant-with-the-variant-inlined) | 2.8 | One HNSW partial index per catalog embedder variant, variant inlined |
| [B-265](#b-265--hybrid-score--cosine--weight-x-idf-weighted-entity-overlap-weight-10) | 2.8 | Hybrid = cosine + 1.0 x IDF-weighted entity overlap |
| [B-266](#b-266--cpu-is-the-in-process-embedding-default-the-serve-actor-uses-cuda) | 2.8 | CPU in-process embedding default; Serve actor on CUDA |
| [B-267](#b-267--no-instruction-prompt-scene-text-is-heading-plus-speaker-text-truncated-at-1024-tokens) | 2.8 | No instruction prompt; scene text format, 1,024-token cut |
| [B-268](#b-268--the-index-stage-is-a-no-op-without-a-text_embedder-decision-never-a-silent-stub) | 2.8 | Index stage is a no-op without a `text_embedder` decision |
| [B-269](#b-269--the-synthetic-show-is-a-template-generator-with-truth-by-construction-a-script-line-is-a-fountain-element) | 2.9A | Synthetic show: template generator, truth by construction, line = Fountain element |
| [B-270](#b-270--label-conventions-per-target-kind) | 2.9A | Label conventions per target kind |
| [B-271](#b-271--cleared-clearance-items-are-rendered-but-not-labelled) | 2.9A | Cleared clearance items rendered but not labelled |
| [B-272](#b-272--clearance-text-is-an-overlay-plate-over-a-still-stretch) | 2.9A | Clearance text is an overlay plate over a still stretch |
| [B-273](#b-273--phone-positives-must-be-valid-numbers-outside-the-fiction-range) | 2.9A | Phone positives valid and outside the fiction range (controller ruling) |
| [B-274](#b-274--track-plan-per-title-stacked-edits-in-one-copy-separate-tracks-for-drift-and-offset) | 2.9A | Track plan per title; drift and offset on their own tracks |
| [B-275](#b-275--glossary-variants-live-in-the-notes-column) | 2.9A | Glossary variants in the `notes` column |
| [B-276](#b-276--synthetic-show-in-the-manifest-with-license-cc-by-40-and-no-source) | 2.9A | `synthetic-show` in the manifest, CC-BY-4.0, no source |
| [B-277](#b-277--nip-eval-inject-is-wired-as-a-command-not-a-sub-app) | 2.9A | `nip eval inject` wired as a command |
| [B-278](#b-278--each-injector-seeds-its-own-stream-from-injector-id-seed) | 2.9A | Seeds per (injector id, seed) |
| [B-279](#b-279--a-film-is-showslug-episodes01e01) | 2.9A | A film is `show=<slug>`, `episode=S01E01` (controller ruling) |
| [B-280](#b-280--evallabels-is-reserved-for-label-format-files-exp-004-ground-truth-moves-out) | 2.9A | `eval/labels/` reserved for Label format; EXP-004 truth moves out (controller ruling) |
| [B-281](#b-281--mention-truth-records-every-entity-surface-in-a-line) | 2.9A | Mention truth records every entity surface |
| [B-282](#b-282--wiring-by-an-idempotent-pipelinewire-called-from-nip-run-not-module-level-add_stage) | W-int | Wiring by an idempotent `wire()` called from `nip run` |
| [B-283](#b-283--stage-order-knowledge-stages-before-timeline-cue-alignment-after-it) | W-int | Stage order: knowledge stages before `timeline`, cue alignment after |
| [B-284](#b-284--nip-run-asks-for-asr-text_llm-and-text_embedder-asr-pinned-to-timelineasrvariant) | W-int | `nip run` asks for asr/text_llm/text_embedder; asr pinned to turbo |
| [B-285](#b-285--knowledge-and-story-constants-move-to-configpipelineyaml-with-identical-values) | W-int | Knowledge constants in `config/pipeline.yaml` |
| [B-286](#b-286--load_timeline-resolves-superseded-facts-as-well-as-active-ones) | W-int | `load_timeline` resolves superseded facts |
| [B-287](#b-287--vllm-structured-outputs-run-with-xgrammar-and-disable_any_whitespace) | W-int | xgrammar `disable_any_whitespace` (did not cure the runaway) |
| [B-288](#b-288--cis-integration-step-runs-the-postgres-only-store-tests) | W-int | CI runs the Postgres-only store tests (controller ruling) |
| [B-289](#b-289--the-clearance-ocr-stage-is-not-wired-by-w-int-27-may-add-the-one-line) | W-int | Clearance OCR stage left to 2.7 (controller ruling) |
| [B-290](#b-290--the-vllm-image-smoke-is-re-run-on-the-new-lock-with-a-forced-exact-kv-setting) | W-int | vLLM image smoke re-run on the new lock (controller ruling) |
| [B-291](#b-291--the-asr-stub-under-the-cpu-profile-still-does-its-io-proposal-not-built) | W-int | cpu-profile ASR stub keeps its I/O (not built) |
| [B-292](#b-292--a-w-serve-step-before-w2-nip-run-inside-ray-head-with-staged-serving-and-an-hf_home-default) | W-serve | **W-serve step: `nip run` in ray-head with staged serving, `HF_HOME` default** (controller ruling) |
| [B-293](#b-293--nip-run---in-cluster-plus-a-documented-docker-compose-exec-line-no-wrapper-command-no-schedulerpy) | W-serve | `nip run --in-cluster`, no wrapper, no `scheduler.py` |
| [B-294](#b-294--only-vllm-slots-are-deployed-as-serve-apps-actor-slots-stay-in-process) | W-serve | Only vLLM slots deployed; actors in-process |
| [B-295](#b-295--staged-serving-is-cut-into-stage-segments-not-17s-servingrunplan-work) | W-serve | Stage segments inside `serving.group` |
| [B-296](#b-296--a-skipped-slots-stages-are-skipped-by-one-guard-in-run_store-and-the-checks-they-feed-are-gaps) | W-serve | Skipped slots: one guard, fed checks are gaps |
| [B-297](#b-297--a-vram-skip-says-free-vs-needed-from-the-planners-own-formula) | W-serve | VRAM skip reason states free vs needed |
| [B-298](#b-298--importing-nip-defaults-hf_home-to-the-repos-model-cache) | W-serve | `HF_HOME` defaults to the repo model cache |
| [B-299](#b-299--composedevyaml-mounts-the-weights-and-the-source-into-ray-head) | W-serve | `compose.dev.yaml` mounts weights and source into ray-head |
| [B-300](#b-300--nip_vram_margin_gb-default-05-the-8-gb-laptop-may-set-025) | W-serve | **`NIP_VRAM_MARGIN_GB`, default 0.5, laptop 0.25** (controller ruling) |
| [B-301](#b-301--one-execution-order-everywhere-each-stage-over-all-episodes-before-the-next-stage) | W-serve | **One stage-major execution order everywhere** (controller ruling) |
| [B-302](#b-302--a-serve-group-that-fails-to-deploy-is-a-coverage-gap-vram-drift-after-the-work-is-a-warning) | W-serve | Deploy failure is a gap; drift is a warning |
| [B-303](#b-303--the-extraction-runaway-and-single-stream-throughput-are-handed-on-not-fixed-in-w-serve) | W-serve | Runaway and single-stream throughput handed to 2.1B / W2 |
| [B-304](#b-304--cuda-12-cublas-only-on-ldconfig-and-the-uv-cache-dir-fixed) | 2.close | CUDA 12 cuBLAS only, on `ldconfig`; uv cache dir fixed |
| [B-305](#b-305--gliner-x-large-stays-the-planners-pick-on-the-8-gb-laptop-measured-no-pin) | 2.close | `gliner-x-large` stays the laptop pick, measured and scored (controller ruling) |
| [B-306](#b-306--occurrence-ref-clrocc-hash-with-kind-clearance_item-occurrences-are-derived-not-stored) | 2.close | `clr/occ-<hash>` refs, kind `clearance_item`, derived from stored detections |
| [B-307](#b-307--the-occurrence-hash-uses-registry-independent-fields-only) | 2.close | Occurrence hash uses registry-independent fields (controller ruling) |
| [B-308](#b-308--nothing-changed-in-the-image-for-ocr-the-cpu-fallback-stays) | 2.close | No image change for OCR; CPU fallback stays |

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

## 1.7 Serving and EXP-001

### B-073 · One Serve app per variant, vLLM as a child process group, placeholders for actor slots

- **Date / commit:** 2026-10-16 · `f35045e`, `33fe525` · 1.7
- **Choice:** `serving.apps(plan, catalog, inventory, slots)` turns a stage group into Ray Serve applications: one per non-stub variant (`nip-<variant>`, route `/models/<variant>`); slots that share a variant (vlm + text_llm, a reusing judge) share one app; `num_gpus = gpu_fraction` if set, else `gpus_per_replica`. vLLM flags come from the Plan: model repo (`checkpoint` or `base_model`), `--served-model-name`, `--tensor-parallel-size`, `--max-model-len`, `--gpu-memory-utilization`, `--enforce-eager`, and for a vlm riding on the variant `--limit-mm-per-prompt.image` and `--mm-processor-kwargs {"max_pixels": ...}` read from `decisions[vlm]` (as the 1.6 review asked). The replica (`VllmServer`) runs `vllm serve ... --host 127.0.0.1 --port <free>` in its own process group, polls `/health` (900 s timeout, fails early with the log tail if the process exits), forwards requests with httpx, and `check_health` fails if the child died.
- **Actor slots** (whisper, OCR, embedders, detector) deploy a `Placeholder` that holds the Plan's GPU fraction and answers `{"variant", "stub": true}` until their backends ship (2.5, 2.6, 2.8, 3.x). Why: staged scheduling stays real (Ray accounts the fractions) without loading models no Phase 1 check uses.
- **Why Serve load/unload through `serve.run(name, route_prefix)` and `serve.delete(name)`:** it is what the architecture specifies; no REST PUT. Resident mode is one `resident` group through the same loop. The review marked this whole item compliant.

### B-074 · `max_constructor_retry_count=1` on every app

- **Date / commit:** 2026-10-16 · `f35045e` · 1.7
- **Context:** Ray Serve 2.58 defaults `max_constructor_retry_count` to 20 (threshold min(count, replicas x 3)), so a vLLM start that fails for lack of memory would be retried 20 times (checked in the image).
- **Choice:** 1. A start that fails for memory fails again; retry-smaller or downgrade is the scheduler's job (Elasticity). **Consequence:** one bad replica fails a multi-replica deploy. The reviewer confirmed it bounds the failure path; all 6 failed real starts returned to idle.

### B-075 · `--enforce-eager` on GPUs of 16 GiB or less; fp8 KV not set

- **Date / commit:** 2026-10-16 · `f35045e` · 1.7
- The docs say "small GPUs" without a number: used `smallest GPU <= 16 GiB`. `--kv-cache-dtype fp8` is not set until EXP-018 decides it (the architecture says "where supported"). Recorded as a known deferral, not a gap.

### B-076 · Serve HTTP on 0.0.0.0:8000, clients default to 127.0.0.1:8000

- **Date / commit:** 2026-10-16 · `f35045e` · 1.7
- Serve runs a proxy on every node, so in-cluster callers stay local; no new environment variable.

### B-077 · Teardown waits for VRAM to return to idle plus 256 MiB, measured per group

- **Date / commit:** 2026-10-16 · `f35045e`, `989e0ed` · 1.7
- **Choice:** `teardown` = `serve.delete` then wait until NVML used VRAM is at most the idle level + 256 MiB (120 s timeout), on this node only (multi-node needs the probe per node as Ray tasks, left to the controller). `run(plan, ..., work)` measures idle before each group, deploys, calls `work(group)`, tears down in `finally`.
- **Review M2 (declined, with reason):** because idle is re-measured per group, a leak under 256 MiB per group compounds across the 5 laptop groups (up to about 1.25 GiB) without tripping; and the opposite, desktop VRAM growth during a long group, can fail teardown on WSL2. A run-level check back to the run-start idle would abort finished runs whenever the Windows desktop grows, so it was not added; the integration test compares the end state with the run-start idle instead. Measured: within tolerance in 66/66 trials.

### B-078 · Deploys inside a group are sequential

- **Date / commit:** 2026-10-16 · `f35045e` · 1.7
- `serve.run` blocks per app. Fine for the laptop (one big model per group); parallel loads are to be revisited when a cloud group holds several engines.

### B-079 · Only the LLM client in Phase 1, stubs are minimal valid schema instances, instructor deferred

- **Date / commit:** 2026-10-16 · `f35045e` · 1.7
- **Choice:** `LLMClient(variant, base_url)` uses the openai SDK against `/models/<variant>/v1`, temperature 0, `response_format` = JSON schema of the Pydantic model, images as data URLs, responses buffered (no streaming), and returns the validated model. `StubLLM` returns `stub_instance(schema)`: required fields only, first enum member, lower bounds, `minItems` elements, `minLength` padding, `prefixItems` for tuples, formats for date/date-time/uri. `clients.llm(plan, catalog, slot)` picks the stub when the variant's engine is `stub`. The asr / ocr / detector / embedder / ner clients come with the deliverables that first call them (no Phase 1 consumer).
- **Known limits (review M5, M6):** `stub_instance(Fact)` and `stub_instance(Flag)` fail because of custom validators (13 contract models ok, 2 fail per the reviewer); a hand-made stub or schema-level bounds are needed in Phase 2 (2.1 owns `Fact` extraction). D-025 says `instructor` wraps the client with one repair retry; that is deferred to 2.1, the first structured-extraction consumer (the notes had no deferral until the fix round).

### B-080 · Dev compose override instead of editing `compose.yaml`; `openai` added unpinned

- **Date / commit:** 2026-10-16 · `6854081` (exp files), `f35045e` (dependency) · 1.7
- `compose.yaml` belongs to 1.5 ([B-068](#b-068--compose-ownership-15-owns-composeyaml-including-mlflow)). `eval/exp/exp001.compose.yaml` bind-mounts the repo's `./models` (the global rule: weights live in the repo, on D:), `./src`, `./eval`, `./tests`, `./config` (PYTHONPATH `/app/src:/app`) and sets `HF_HUB_OFFLINE=1`, so code changes need no 23 GB image rebuild. Proposal for `compose.yaml`: ray-head and api should mount the same host `./models`.
- `uv add openai` wrote `>=3.31.0`, which would have upgraded the 3.16.2 that the vLLM image ships; changed to plain `openai`. Review M8: the `pyproject.toml` comment was truncated, fixed.

### B-081 · EXP-001 method: interleaved rounds, one start per trial, exact-KV gate, fixed-length decoding

- **Date / commit:** 2026-10-16 · `6854081` (script) · 1.7
- Rounds are interleaved (each round runs every setting once) so desktop drift hits all settings alike; one vLLM start per trial with retries off; the exact-KV arm uses gmu 0.5 only as vLLM's startup gate; `ignore_eos` for fixed-length decoding (8 prompts x 128 tokens); NVML peak sampled every 0.2 s. Added two desktop-pressure arms that the design did not have (see [EXP-001](experiments.md#exp-001--vllm-memory-headroom-on-the-laptop)) because the main trials ran on an unusually idle desktop.
- Review M4 fixed: any bench error other than `ServingError` skipped teardown, the MLflow run and the sampler stop and left the app deployed; benchmark errors are now tagged and teardown and logging still run.

### B-082 · Checkpoint for `qwen3.5-4b-awq` is `cyankiwi/Qwen3.5-4B-AWQ-4bit`, in the catalog

- **Date / commit:** 2026-10-16 · `989e0ed` · 1.7 · **Controller ruling** (review Important I1)
- **Context:** the catalog had no AWQ repo, so `Variant.repo` (= `checkpoint or base_model`) was the 8.68 GiB bf16 `Qwen/Qwen3.5-4B`; every real laptop run would have failed at the LLM group. EXP-001 and the integration test had overridden it in code, so no run used the shipped path.
- **Options and choice:** see [C-016](experiments.md#c-016--which-awq-checkpoint-for-qwen35-4b-awq). `config/catalog.yaml` now has `checkpoint: cyankiwi/Qwen3.5-4B-AWQ-4bit` (3.78 GiB, Apache-2.0); the unit assertion was flipped to the AWQ repo; the overrides were removed from the integration test and the EXP script, so both use the stock catalog. The EXP's historical `kv-planner` budget is frozen as `KV_PLANNER_BYTES = 1,006,632,960` because the catalog's KV figure changed and recomputing would change what that variant means.
- **Caveat:** third-party quantization; licence and provenance as reported on the Hub, not verified by the reviewer.

### B-083 · Exact KV budgets on single-GPU engines sized by the planner from probed free VRAM

- **Date / commit:** 2026-10-16 · `989e0ed` · 1.7 · **Controller ruling** (the EXP-001 decision)
- **Context:** [EXP-001](experiments.md#exp-001--vllm-memory-headroom-on-the-laptop). By the written bar the laptop calibration is gmu 0.86 and exact KV does not qualify (21,597 vs at least 35,746 tokens at idle). But under WSL2 CUDA in the container reports a fixed 6.93 GiB free, so vLLM's startup check never fails below gmu 0.866, and with Windows memory in active use its profiler counts that memory as its own non-torch memory (6.15 vs 4.25 GiB). gmu 0.75 and 0.83 started 0/3; gmu 0.86 started 3/3 at 1.52 sequences; exact KV started 13/13 at 2.64.
- **Options (from the notes):** (a) gmu 0.86 per the bar: most KV at idle, collapses to 1.5x under load, and the Plan's own gmu (0.77) fails outright; (b) exact KV equal to the planner's own estimate (2 x 8k), gmu only as startup gate; (c) exact KV sized to fill the usable budget, more KV than (b) when there is room, not measured as an arm.
- **Ruling:** exact KV budgets on single-GPU engines, **sized by the pure planner from the probed free VRAM** (NVML on the host reports Windows usage truthfully, unlike WSL2 CUDA's constant 6.93 GiB). That is (c) in effect: `kv_cache_bytes` = min(room - weights - overhead, KV(default context x 2)), floored to MiB, where `room` is the engine's allocation plus the GPU's leftover when it is the only engine on that GPU. `gpu_memory_utilization` stays `ceil2(per_gpu/total)` (0.79 on the laptop) and now only gates the start (at most 0.866 passes the WSL2 check). Engines with tp > 1 keep gmu sizing. `plan()` stays pure: free VRAM comes in only through the inventory.
- **Cost if wrong (recorded by the controller):** the probe is taken at plan time. In staged mode the LLM group loads last, so if the desktop grows between probe and deploy the budget can exceed what is physically free; vLLM's check cannot catch it (it sees 6.93 GiB), so the start fails or WDDM pages memory (slow) until Phase 4's OOM-amendment path re-plans. Mitigation available: re-probe at group boundaries. It also deviates from the bar's "at least as much KV", which was measured at idle only, and gives less KV than gmu 0.86 at idle if the budget is conservative.
- **Review view:** partly supported (synthetic pressure, n = 3; gmu 0.86 also survived; marginal 47 MiB headroom under pressure); see the EXP-001 takeaway. **Result:** the laptop Plan at the docs' 7.15 GB free went from {8k, gmu 0.77} to {16k, gmu 0.79, KV 2,170 MiB}.

### B-084 · EXP-001 calibration applied to the catalog, and the AWQ checkpoint added

- **Date / commit:** 2026-10-16 · `989e0ed` · 1.7 · **Controller ruling**
- Catalog `qwen3.5-4b-awq`: `kv_mb_per_1k_tokens` 60 to **44.6**; `overhead_gb` 1.2 to **0.53** (steady non-KV = NVML peak minus vLLM KV: 4.47 / 4.46 / 4.53 GiB at gmu 0.80 / 0.83 / 0.86, max taken, weights 4.0); new optional `startup_peak_gb: 6.25` (was the planner's 6.14 estimate); the checkpoint ([B-082](#b-082--checkpoint-for-qwen35-4b-awq-is-cyankiwiqwen35-4b-awq-4bit-in-the-catalog)). Per-GPU need is now `max(weights/tp + KV(ctx x 2)/tp + overhead, startup_peak_gb)`.
- Only this variant was measured, so only it changed; every other variant keeps its estimates. The 44.6 was later restated as 45.8 per 1,024 tokens ([B-115](#b-115--kv-calibration-restated-per-1024-tokens-446---458)).

### B-085 · The startup peak is a fit floor, not subtracted from the KV budget

- **Date / commit:** 2026-10-16 · `989e0ed` · 1.7 · **Controller ruling** (interpretation of "minus measured startup overhead")
- **Reasoning:** the two runs with different KV (gmu 0.75 at 1.56 GiB, the exact 0.94 GiB budget) both peaked at 6.25 GiB, so the peak occurs before the KV cache is allocated and the two are never resident together. KV = usable - weights - *steady* overhead (0.53), and the peak only decides whether the variant fits at all. Subtracting the peak would leave 0.40 GiB of KV at 7.15 GB free, below one 8k pair (0.70 GiB), and the laptop would lose its LLM.
- **Cost if wrong:** an occasional start failure; the measured steady overhead was 54 to 107 MiB above the model at 16k, inside the 0.5 GiB margin.

### B-086 · Additive contract and catalog fields: `SlotDecision.kv_cache_bytes`, `Variant.startup_peak_gb`

- **Date / commit:** 2026-10-16 · `989e0ed` · 1.7 · **Controller ruling**
- `SlotDecision.kv_cache_bytes` (`int | None = None`, later `gt=0`, [B-116](#b-116--the-kv-budget-must-be-positive-zero-is-rejected-not-ignored)) and the optional `Variant.startup_peak_gb`. Existing fields are unchanged and `extra="forbid"` still holds; the contract round-trip passes in every table case. Cost if wrong: one field rename. (The ledger line says "Plan.kv_cache_bytes"; the field lives on `SlotDecision`, which is how the code and the review name it.)

### B-087 · `stop()` always kills the process group, and liveness ignores zombies

- **Date / commit:** 2026-10-16 · `989e0ed` · 1.7 (review Important I2)
- **Context:** `stop()` skipped the group kill when the main `vllm serve` process had already exited, but the EngineCore is a separate child (that is why the group exists). An orphan would keep its VRAM, the restart that the architecture relies on would then fail for memory, and teardown would only raise.
- **Choice:** always SIGTERM `-pgid` (ignoring `ProcessLookupError`), wait while `_group_running`, SIGKILL after 30 s. On the first real run unload took 33.1 s because the orphan became a zombie under PID 1; liveness now reads `/proc/*/stat` and skips state `Z` ([C-012](experiments.md#c-012--unload-time-331-s-down-to-40-s-the-zombie-enginecore)). Also: the failed-start path calls `stop()` and `__del__` calls it again, which the re-review judged safe while any member holds the pgid.
- **Mypy detail:** `os.killpg` and `signal.SIGKILL` do not exist in the win32 stubs and `assert sys.platform` did not narrow inside the method, so the code uses `os.kill(-pgid, SIGTERM/9)`.

### B-088 · Exact KV applies to every single-GPU engine; leftover goes to KV only when the engine is alone on its GPU

- **Date / commit:** 2026-10-16 · `989e0ed` · 1.7 · **Controller ruling**
- The planner cannot tell WSL2 from bare Linux, and on Linux the exact budget equals what gmu sizing would give, capped at the default context x 2. Consequence: big single GPUs get at most 2 full-context sequences of KV per replica (for example 27b-fp8 on 48 GB: 10.0 GiB). Co-resident engines get exactly their sized KV (test: 1x 86 GB throughput). Numbers in [C-019](experiments.md#c-019--exact-kv-budget-vs-the-old-gmu-sizing-on-big-gpus). Revisit with EXP-015 (throughput objective on cloud). Re-review minors N1, N2, N4 became B-115, B-117, B-116.

## 1.8 Part B: real-film run and EXP-002

### B-089 · Cut labels use the `pull` object format, the masks go in a separate sidecar

- **Date / commit:** 2026-10-16 · `6854081` · 1.8B · follows [B-049](#b-049--cut-labels-are-a-separate-json-file-not-flags)
- The labels file is exactly the one-object JSON that `labeling.py pull` writes (`{title, check, fps, labeller: "agent-provisional", frame_convention, unlabelled_clips, cuts}`), filename `sintel_cuts.provisional.json`, so the later human labels drop in. The windows where no cut is defined (dissolves, credits) are a sidecar `sintel_cuts.provisional.masks.json` (`regions: [{start, end, kind, note}]`, inclusive frames) that the scorer reads together with the labels. Proposal for the labelling README: document the sidecar. (The earlier build-log wording `labeller: agent` was the ruling's shorthand; the stored value is `agent-provisional`.)

### B-090 · The EXP-002 headline metric is masked, the unmasked F1 is always reported

- **Date / commit:** 2026-10-16 · `6854081` · 1.8B
- **Rationale:** a dissolve has no single "first frame of the new shot" (a detector may flag the start, middle or end), and 16 % of Sintel is end credits. Predicted cuts inside a masked window are dropped before scoring (and the labels inside, one: the cut to the credits at 17858). **Effect at defaults:** TransNetV2 0.917 masked vs 0.901 unmasked, Content 0.839 vs 0.817, Adaptive 0.880 vs 0.875, so the ranking does not change. Naming caveat (review M2): `shown/*` here means "masked headline" while in `eval.report` it means "flags shown to the user"; documented in the script docstring.

### B-091 · Seconds per video-minute is the wall time of the full detector, one process, 3 repeats, defaults

- **Date / commit:** 2026-10-16 · `6854081` · 1.8B
- TransNetV2 includes TorchCodec decode + resize + model + model load; PySceneDetect includes OpenCV decode. Not GPU-seconds. For the comparison table, "wall s per content-hour" is the same number x 60. Only the 3-repeat defaults support speed claims (sweep-run seconds are single runs). Review M4: the docstring command now says `--repeat 3`.

### B-092 · Provisional labels by candidate union and contact sheets, with a committed verification record

- **Date / commit:** 2026-10-16 · `6854081`, `be9daac` · 1.8B (review Important I1)
- **Method:** union of three detectors at deliberately low thresholds plus a frame-difference scan, merged to 646 events, every event inspected as a 6-frame contact sheet (details and bias numbers in [EXP-002](experiments.md#where-the-labels-came-from-and-how-they-are-biased)). The frame-difference scan exists because the candidate set is detector-seeded: it looks for cuts no detector flagged. It found nothing new (labelled cuts it found: 0), which is weak evidence that few exist, not proof.
- **Review fix (I1):** the per-event decisions and the per-cut verification record were only in git-ignored `data/`; now committed as `sintel_cuts.provisional.decisions.txt` and `sintel_cuts.provisional.verification.json`, generated by `label_sheets.py verification`.
- **Integrity rule that came out of the rate-limit incident:** decisions made without a real view of the image were discarded, not patched; only decisions on actually shown images survive ([journal](journal.md#2026-10-16--18b-the-provisional-labels-method-bias-and-a-blind-first-draft)).

### B-093 · EXP-002 decision: keep TransNetV2 provisionally, as a cost/risk call, not a result

- **Date / commit:** 2026-10-16 · `be9daac` · 1.8B (review Important I2) · decision proposal, accepted as provisional
- **Context:** the bar's verdict flips with tuning (defaults +0.037 TransNetV2; tuned on the same labels +0.021 Adaptive; held out +0.016 Adaptive), the labels are agent-made and detector-seeded, and dissolves were masked.
- **Choice:** keep TransNetV2 in Phase 1 because it is pinned in the docs and integrated and tested in part A; swapping on a 0.016 to 0.021 gap on seeded labels would not be justified. **Withdrawn after review:** two rationales not supported by any run ("adds fades/dissolves handling", "no tuning knob to overfit"). **Proposed, not applied:** `timeline.shots.threshold` 0.5 to 0.2 pending human labels (config is not 1.8B's); re-run with human-verified labels for Sintel and Tears of Steel; the experiment's own rule decides if a tuned Adaptive is at least 0.02 above a tuned TransNetV2.
- **Cost if wrong:** Phase 1 ships a slightly conservative default (recall 0.85 on this film) and a heavier dependency than needed. Full entry: [EXP-002](experiments.md#exp-002--shot-detection-transnetv2-vs-pyscenedetect).

### B-094 · No change to part A after EXP-002, and where the experiment files live

- **Date / commit:** 2026-10-16 · `6854081` · 1.8B
- `src/nip/timeline/` untouched: no bug found, the resize-filter test ([C-014](experiments.md#c-014--transnetv2-input-resize-filter-torchcodec-bilinear-vs-ffmpeg-bicubic)) found no effect, and the ffmpeg-CLI-is-faster finding ([C-015](experiments.md#c-015--decode-backend-and-keyframe-cost-on-real-film)) does not outweigh exact seek. Files: `eval/exp/exp002_shots.py` (experiment, scorer, sweeps), `eval/exp/label_sheets.py` (labelling helpers), `eval/labeling/labels/` (labels, masks, verification, decisions), `tests/unit/eval/test_exp002_shots.py`. Optional wiring if wanted: `eval_app.add_typer(exp002_app, name="exp002")`; the commands run as `python -m eval.exp.exp002_shots ...`. `docs/project-structure.md` has no `eval/exp/` (see doc corrections).

### B-095 · Tears of Steel is not labelled, so half of EXP-002 is open

- **Date / commit:** 2026-10-16 · `6854081` · 1.8B
- The brief asked for Sintel's cuts only, so Tears of Steel has speed and cut counts but no F1. Suggested follow-up: label it with the same `label_sheets` tooling or in Label Studio. Stays on the deferred list.

## 1.10 Walking skeleton

### B-096 · One flag per cue

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10
- A cue that breaks several rules gets one flag whose title lists all of them ("Cue 11: reading speed 100.0 CPS (max 17); duration 0.50 s (min 5/6 s)"); severity is the worst rule's. Why: one reviewer action per cue, and labels (one per planted cue) match one flag. **Alternative rejected:** one flag per (cue, rule), more precise per-rule counting but an edit that breaks two rules would score one false positive.

### B-097 · Gap and overlap rules belong to the later cue

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10
- The claim is the cue whose start is too close; the previous cue is `context` evidence (ignored by eval matching). "Previous" is the previous in file order (`idx - 1`), so an out-of-order cue shows up as an overlap.

### B-098 · Durations, CPS and gaps are measured in frames, not milliseconds

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10 · answers the 1.4 review's open question
- The Netflix rules are stated in frames (2-frame gap, 20 frames at 24 fps) and `Span` carries frames only, so the check uses the timeline's frame axis (the picture's probed rate; 24 without a picture). **Cost:** plus or minus 1 frame of rounding vs ms timing: Sintel cue 11 is 17.14 CPS in frames and 17.24 in ms (both exceed the 17 limit, so it is flagged either way).

### B-099 · Rule pack layout: section-wise merge, no silent fallback to another language

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10
- `config/languages/{_base,en,es,fr,de}.yaml`, one `readability:` section per file, packs merge section-wise (`_base` to `es` to `es-419`). Shared limits live in `_base` (42 chars, 2 lines, 5/6 s to 7 s, 2-frame gap, gaps under 1/2 s closed to 2); reading speed lives only in the language files (adult/children: en 20/17, es/fr/de 17/13). Fractions are stored exactly as strings (`5/6`). **A language without a pack is rejected** (`INPUT_REJECTED: no readability rule pack for language 'it'`) rather than silently getting another language's CPS. `es-ES.yaml` is not created: per the doc it only overrides address forms, which this check does not use. Children's CPS is stored; `audience="adult"` by default and no CLI option exposes it yet.

### B-100 · Gap-closing is part of `loc.readability`, severity 2, tier follows confidence

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10 · reviewer adjudicated
- Gaps strictly between `min_gap_frames` and 1/2 s (3 to 11 frames at 24 fps, 3 to 12 at 25) are flagged with severity 2 ("should be closed to 2"); every other violation is severity 3. Confidence is 1.0 for all (pure rules), so every flag lands in `must_review`. **Open product call:** 15 of the 20 flags on the clean Sintel tracks are gap-closing ones; if reviewers find that too noisy, lower its confidence below 0.70 so it is suppressed by default, or move it to `loc.shot_change`'s timing group. The reviewer judged it in spec (the rule-pack row says gaps of 3 to 11 frames are closed to 2; tier is assigned purely by confidence) and a product decision, not a defect.

### B-101 · `requires = {source_subs, target_subs}`; no source track means the check is skipped

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10
- Per the activation matrix, although the rules read only target tracks. Without a source track the check is skipped and listed in `run.json` `skipped` (coverage 0.0 for the agent). Doc correction filed (the matrix marks source subs required for readability but it is unused).

### B-102 · Verification is `nip.verification.verify` with the re-check injected; dropped flags are kept apart

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10
- Step 1 resolves evidence (ref exists with the same kind, frames equal the timeline's, quote is in the stored text, frames inside the episode); step 2 re-checks the rule. Verification must not import agents (project-structure), so `verify(flags, tl, rechecks)` takes a `{check_id: callable}` map; the pipeline passes `Readability.recheck`, which recomputes the finding for the claimed cue on the current timeline and requires the same title. Step 1 also requires evidence frames to equal the timeline's, which catches a stale cached flag. Steps 3 (LLM judge) and 4 (routing/dedup) are not built; the tier stays as assigned at emission (1.4 decision). `flags.jsonl` holds verified flags (fed to `nip eval run`), `dropped.jsonl` the dropped ones with `verification.*: "fail"`.
- **Review M6/M7 (open):** a flag on a last cue that overruns the picture by a frame is dropped by the "inside the episode" rule rather than reported; `ev.quote not in span.text` is unguarded against `span.text is None`.

### B-103 · `src/nip/pipeline.py` is the Phase-1 composition root, and `nip run` takes files

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10 · accepted deviation (reviewer M3)
- project-structure.md has no such module (runs flow api to `runtime.controller` to scheduler from the store), and nothing is in the store yet, so `nip run --episode E --script F --subs LANG=F ... [--source-lang en] [--video F] [--picture picture.json] --out-dir D` takes files and writes JSON. `--picture` reuses `nip timeline picture` output (fps must equal the probe's, else rejected). **Phase 2 must replace it** with the documented `--show/--episodes` form backed by the store (a breaking CLI change) and move the stage sequence into `runtime.scheduler`; flag ids are null until the store assigns them.

### B-104 · No Plan for the walking skeleton run

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10
- `plan_id = "none"`, `mode = staged`, `judge_independent = false` in the report and `produced_by`, because the check uses no model slot.

### B-105 · Keyframes live on the timeline as one-frame spans

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10
- `build_timeline(..., keyframes=[(shot, n, frame)])` adds `keyframe` spans `{ep}/kf/{shot}.{n}` (shot = index, as 1.4's shot refs), needed for the exit criterion "timeline with shots and keyframes". Nothing cites them yet.

### B-106 · Duplicate scene numbers are rejected at ingest, not as a `Timeline` crash

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10 · refines [B-066](#b-066--duplicate-timeline-refs-are-rejected)
- The pipeline rejects them with `INPUT_REJECTED: <file>: duplicate scene numbers ['1']; renumber them` (exit 1) instead of the `ValueError` that 1.4's review M3 flagged. Test: `test_duplicate_scene_numbers_are_rejected`.

### B-107 · The walking-skeleton benchmark set and the machine-triaged native labels

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10
- **Set name:** `walking-skeleton`, not `smoke` (which the docs define as a 2-minute excerpt with about 30 errors across all checks). Labels under `eval/labels/walking-skeleton/`; injected labels are regenerated from seeds and live under `data/runs/1.10/`. MLflow runs go to a local sqlite store `data/runs/1.10/mlflow.db` (tag `exp=WS-1.10`, not an EXP id).
- **Native labels:** the 6 clean-run flags for Sintel es are machine-triaged, not by a person as evaluation.md requires: confirmed with an independent ms-based recompute (pysubs2, same limits), written with `injector: "native-triage"`, `reviewed: false`. A person should sign them off.

### B-108 · The `loc.readability.v1` injector: isolated cues, one kind per pick, ref-based labels

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10
- Edits only isolated cues (both neighbours at least 600 ms away, 1 to 6 s long, no two picks adjacent) so an edit can never create a violation on an unlabelled cue; one kind per pick, rotating so all six kinds appear before any repeats; ms-level edits chosen to break the rule at any common frame rate (min duration to 500 ms; max to 8 s; gap to 20 ms; CPS to 1.5x the limit, at least 900 ms). Labels cite the cue ref, not frames (the injector has no frame rate), and `metrics.py` matches ref-only labels by shared ref. `episode` defaults to the corpus title directory, `lang` to the `<lang>_` file prefix (since 2.9A a film is `show=<slug>`, `episode="S01E01"`, [B-279](#b-279--a-film-is-showslug-episodes01e01)). Limits come from the same rule pack the check uses, which is why the 1.00 score is circular ([C-018](experiments.md#c-018--walking-skeleton-benchmark-prf1-100-on-planted-readability-errors-and-why-it-proves-little)). `pysubs2.load` autodetection failed on a synthetic SRT, so the injector passes `format_` from the file extension.

### B-109 · The Sintel picture stage is reused from the cached 1.8B run

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10 · permitted by the brief
- 1.10 converted 1.8B's cached EXP-002 "picture" run (`data/exp002/runs/picture/sintel/`: 161 cuts, 21,312 frames, 398 keyframe JPEGs, same code path and config, threshold 0.5) into `analyze_picture`'s `picture.json` with a scratch script (shots = `shots_from_cuts`, keyframe records recomputed with `keyframe_frames` and checked against the files on disk: 398 = 398). No GPU run was needed. **Caveat carried into the exit verification:** the picture stage was not re-run live; the timeline uses the probe's 21,313-frame duration while the shots end at 21,312.

### B-110 · CLI wiring executed

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10 · executes [B-067](#b-067--cli-wiring-is-a-separate-integration-step)
- `src/nip/cli.py` wires `eval` (with `corpus` and `labels` nested), `timeline`, `plan` and `run`. 1.7's `serving.py` has no Typer app, so nothing was wired for it. Test: `nip --help` lists run/eval/timeline/plan; `nip eval --help` lists run/compare/corpus/labels. `nip doctor`, `nip models`, `nip ingest`, `nip eval inject` are in the docs' CLI table but are not wired (none is a Phase 1 deliverable; injectors are Python-callable only).

### B-111 · CLI import cost accepted for now (superseded by B-113)

- **Date / commit:** 2026-10-16 · `77257b6` · 1.10 · **Superseded by [B-113](#b-113--lazy-torch-mlflow-and-scipy-imports-in-the-cli-superseding-b-111)**
- `nip` imported torch and mlflow at startup (about 9 s) because `nip.timeline.picture` and `eval.report` import them at module level. The implementer accepted it with the upgrade path written down (lazy imports); the review marked it a Minor (M5) owned by those modules, and the fix round did it. `cli.py` also sets `MLFLOW_DISABLE_AGENT_HINT=1` by default to silence the INFO line MLflow 3.17 prints on import.

### B-112 · `NIP_CONFIG_DIR` with auto-detection

- **Date / commit:** 2026-10-16 · `2d0bf6a` · 1.10 fix round (review M1)
- **Context:** `readability.rule_pack` resolved `parents[4] / "config" / "languages"` from `__file__`. The nip image installs non-editable (`uv pip install .`), so in site-packages that path points outside `/app/config` and every language would be rejected. `picture.py` used the same `parents[]` pattern, and `load_catalog` and `nip plan --catalog` were cwd-relative.
- **Choice:** one helper, `nip.config.config_dir()`: `$NIP_CONFIG_DIR`, else the source tree's `config/` (detected by `config/pipeline.yaml` next to `src/`, i.e. an editable install), else `./config`. Every reader (`rule_pack`, `timeline_config`, `load_catalog`, `nip plan --catalog`) resolves it at call time. The Dockerfile sets `ENV NIP_CONFIG_DIR=/app/config`; `.env.example` documents it. An editable checkout needs no setting and the image is explicit. Tests: `tests/unit/test_config.py` (3: source-tree default, installed-package fallback, env override). The image was not built. **Left:** `media.py`'s repo-relative FFmpeg lookup (already overridable by `NIP_FFMPEG_DIR`); `load_catalog` untested under `NIP_CONFIG_DIR`.

### B-113 · Lazy torch, mlflow and scipy imports in the CLI, superseding B-111

- **Date / commit:** 2026-10-16 · `2d0bf6a` · 1.10 fix round (review M5)
- torch is imported inside `picture.analyze_picture` (via `shots`), mlflow inside `eval.report.run/compare`, scipy inside `eval.metrics`'s `run`. `nip --help` went from 10.4 to 10.9 s to 1.1 to 1.2 s ([C-013](experiments.md#c-013--nip-cli-startup-109-s-down-to-11-s-lazy-imports)). 1.8's picture CLI test now patches `shots.detect_shots`; the reviewer confirmed its assertions are unchanged. Anyone doing `from nip.timeline.picture import detect_shots` would now break (no caller found).

## Phase 1 closeout

### B-114 · The closeout fixes only the load-bearing minors; everything else is deferred and listed

- **Date / commit:** 2026-10-16 · `09c87f8` · closeout · scope from the controller's ledger
- Six items from the ledger were fixed (see B-115 to B-118); the other deferred minors per deliverable are listed in `notes/phase1-exit.md` and in [review-findings.md](review-findings.md). Not done on purpose: Tears of Steel labels and human verification of Sintel's, lowering `timeline.shots.threshold` to 0.2, EXP-005's 32k arm (ruling R4), real-model knowledge arms (gated on EXP-001, R7), and the minors of 1.1 through 1.11. Cost if wrong: minors resurface in Phase 2; the list is the guard.

### B-115 · KV calibration restated per 1,024 tokens (44.6 -> 45.8)

- **Date / commit:** 2026-10-16 · `09c87f8` · closeout · supersedes the 44.6 figure of [B-084](#b-084--exp-001-calibration-applied-to-the-catalog-and-the-awq-checkpoint-added) (re-review minor N1)
- **Context:** EXP-001 measured 35,746 tokens in 1.56 GiB and 21,597 in 0.94 GiB, which is 45.76 and 45.64 MiB per 1,024 tokens; 44.6 to 44.7 was per 1,000. The planner's `_kv_gb` divides context by 1,024, so it underestimated per-token KV by about 2.4 %.
- **Choice:** catalog `qwen3.5-4b-awq.kv_mb_per_1k_tokens` 44.6 to **45.8**. **Effect:** only the 24 GB cap test moved (2,854 to 2,931 MiB); the laptop KV is free-VRAM-bound (2,170 MiB unchanged); all six table Plans are unchanged. Test: `test_catalog_kv_calibration_uses_1024_token_blocks`. At 16k the real figure is about 38, so the planner stays conservative there.

### B-116 · The KV budget must be positive: zero is rejected, not ignored

- **Date / commit:** 2026-10-16 · `09c87f8` · closeout (re-review N4)
- `SlotDecision.kv_cache_bytes` is `Field(gt=0)`; `vllm_args` tests `is not None` (before, `if d.kv_cache_bytes:` silently fell back to gmu sizing on 0); the planner asserts the computed value is positive. Test: `test_a_zero_kv_budget_is_rejected_not_ignored`.

### B-117 · Shared-GPU exact KV: the premise was wrong, pinned with a test instead of changed

- **Date / commit:** 2026-10-16 · `09c87f8` · closeout (re-review N2, ledger item 4)
- **Premise (from the review):** on a GPU shared with actors the exact budget absorbs all leftover memory, leaving the actors' unmeasured `vram_gb` protected only by the 0.5 GiB margin. **What the code does:** the packer places vLLM first, then actors and replicas, and puts actor sizes into `cluster.free` before the KV room is computed, so the actors were already reserved. Checked on 20/24/32/48 GB resident inventories: engines + actors sum to at most usable.
- **Choice:** change nothing, pin it: `test_exact_kv_leaves_the_actors_their_catalog_sizes_on_a_shared_gpu` (48 GB resident: actors above 5 GiB reserved, total equals usable). **What remains true:** actor sizes are catalog estimates, and the only cushion beyond them is the 0.5 GiB margin / 10 % utilization slack.

### B-118 · Closeout hygiene: ray-head `init: true`, laptop-only dev realm, `.gitignore` pattern and timecode strictness

- **Date / commit:** 2026-10-16 · `09c87f8` · closeout
- `compose.yaml` ray-head gets `init: true` (tini reaps the orphaned EngineCore zombies, [C-012](experiments.md#c-012--unload-time-331-s-down-to-40-s-the-zombie-enginecore)). `.env.example` ships `NIP_KEYCLOAK_DEV_REALM=true` as a comment with a "LAPTOP ONLY" note (the 1.5 re-review minor: copying the template to a cloud host would enable the dev realm). `.gitignore` gets `/eval/*-s[0-9]*-[0-9]*T[0-9]*/` for run output directories (a blanket `/eval/*/` would have ignored the `eval/corpus` and `eval/exp` source packages; verified new files there stay visible). Timecode: `ms_to_frame` rejects negative ms, `frame_to_ms` negative frames (beyond the ask, for symmetry; no caller broke), and every function rejects non-`Fraction` fps (TypeError) and fps <= 0.

### B-119 · Phase 1 is closed with caveats, after an exit-criteria check run against the commit

- **Date / commit:** 2026-10-16 · `09c87f8` · closeout
- Results (details in the [journal](journal.md#2026-10-16--phase-1-exit-criteria-verified-against-09c87f8)): 1 ingest to timeline PASS; 2 flags with resolvable evidence PASS (11/11); 3 planner tables PASS; 4 CI without a GPU PASS locally (304 passed, 1 skipped; migration test 1 passed); 5 experiment entries complete with caveats (EXP-002 decision provisional) and this build-log merge closes "journal up to date" (finding F-2); 6 CLI PASS with findings (F-1 report flag summaries carry no evidence or id by design; F-3 several documented commands not wired). The GitHub Actions workflow itself was not run.

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

### B-120 · Phase 2 plan rulings R1 to R15 adopted

- **Date:** 2026-10-16 (ledger, after the rate-limit interruption) · **Controller ruling**
- **Context:** the Phase 2 plan was saved in `briefs/phase2-plan.md` with one brief per deliverable (2.0 to 2.9B). **Ruling:** adopt its planner rulings R1 to R15, among them R1 (adds deliverable 2.0, the store spine), R3 (a synthetic show replaces Beverly Hillbillies for the knowledge experiments), R4 (EXP-005's 32k arm deferred to cloud) and R7 (real-model knowledge arms gated on EXP-001). EXP-001 has since completed ([B-083](#b-083--exact-kv-budgets-on-single-gpu-engines-sized-by-the-planner-from-probed-free-vram)).
- **Cost if wrong (recorded):** Phase 2 knowledge numbers come from synthetic data only. Phase 2 is not started in this build log.

### B-121 · Commit by explicit file paths, not directory pathspecs

- **Date:** 2026-10-16 · process, after the 1.8B incident · extends [B-070](#b-070--parallel-agents-on-disjoint-paths-with-path-scoped-commits)
- **Context:** B-070's pathspec commit stops cross-agent sweeping of *staged* files, but a pathspec naming a directory (`eval/exp`) also commits every untracked file in it. 1.8B's commit `6854081` therefore included 1.7's untracked `eval/exp/exp001.compose.yaml` and `eval/exp/exp001_vllm_headroom.py`; the committed blobs are 1.7's final versions (verified clean against HEAD), so no separate 1.7 commit holds them.
- **Choice:** 1.8B's fix round (`be9daac`) listed its five files explicitly. History was not rewritten (nothing is pushed, and the blobs are correct); owners were told to expect the files already in HEAD.

## 2.0 Store spine

### B-130 · `nip ingest` takes `[TAG=]PATH` positionals

- **Date:** 2026-10-16 · 2.0 · commit `870c54b` · DP-1 in `notes/2.0.md`
- **Context:** the docs give `nip ingest --show S --episode E files…` with no rule for telling a subtitle's language or a csv's kind.
- **Options:** a flag per kind; a manifest file; `[TAG=]PATH` positionals.
- **Choice:** positionals. Kind comes from the extension (script pdf/fountain/fdx, picture mp4/mov/mkv/mxf/m4v, bible yaml); subtitles must be `LANG=PATH` with a BCP-47-shaped tag (`_LANG_RE` from `ingest/tables.py`); a csv must be `glossary=PATH` or `clearance_log=PATH`; `--source-lang` (default `en`) sets the source/target role; `--episode` is needed only for episode files and must match `SxxEyy` (the `episode` row needs a season and a number); after review m4 the show slug must match `[a-z0-9][a-z0-9_-]*` because it goes into S3 keys.
- **Consequence:** file-mode episode refs such as `E1` cannot be ingested; films become `S01E01` ([B-279](#b-279--a-film-is-showslug-episodes01e01)).

### B-131 · `episode_seq = season * 1000 + number`

- **Date:** 2026-10-16 · 2.0 · commit `870c54b` · DP-2
- **Choice:** not a true release order, but monotonic in SxxEyy order, which is all `screen_key` needs. **Consequence:** the API's `POST /episodes` can set it explicitly later.

### B-132 · Frames at ingest; a non-24 fps picture after 24 fps rows is refused

- **Date:** 2026-10-16 · 2.0 · commit `870c54b` · DP-3
- **Choice:** scenes are stored with unclipped `scene_bounds` frames, cues with exact ms → frame ([B-062](decisions.md#b-062--sub-frame-cues-keep-one-frame-and-shot-refs-use-the-list-index)), both at the episode's probed fps or 24 fps when there is no picture yet; `load_timeline` clips scenes to `episode.duration_frames` as `build_timeline` does. A picture whose fps is not 24 arriving after rows were placed at 24 fps is refused ("ingest the picture first"), not re-derived. A cached `picture.json` whose fps or duration differ from the probe, or whose shots end past the probed duration, is refused.
- **Consequence:** order matters when a non-24 fps title is ingested in pieces; the `ponytail:` upgrade path is to re-derive rows from the stored source objects. Deferred (review m5): `analyze_picture` still runs inside the open ingest transaction.

### B-133 · Replacing an episode's source is refused; show-level files are upserted

- **Date:** 2026-10-16 · 2.0 · commit `870c54b` · DP-4 · **Superseded in part** by 2.9B-1 (`4eff744`), which accepts a new script draft
- **Choice:** an episode that already has a script, a picture or a track in the same language rejects another one (`INPUT_REJECTED`) until 2.9B decides how a new draft replaces rows that facts reference. Show-level files are upserted: entities by (show, kind, canonical_name) with aliases added; glossary approved renderings replaced per language; clearance items by (name case-insensitive, kind, scope) with status, notes and source updated. Idempotency is by sha256, so the same bytes under another language tag are "unchanged".
- **Consequence:** re-ingest of identical files writes nothing (11.7 s, hashing only).

### B-134 · Bible mapping to `entity` and `entity_alias`

- **Date:** 2026-10-16 · 2.0 · commit `870c54b` · DP-5
- **Choice:** characters: `canonical_name = name`, `attributes = {bible_id, gender, pronouns, identity_hidden_until}`, aliases = name (kind `name`) and aliases (kind `nickname`), lang `any`. Secrets: `canonical_name = id`, `attributes = {bible_id, description, revealed_on_screen}`. Fictional brands, orgs and places become kinds `brand`, `org`, `location` with `fictional=true`. Glossary: `entity(kind=term, origin=glossary)` with alias (any, term, name) plus (lang, rendering, approved_rendering).
- **Not stored:** relationships and `story_overrides`; 2.2 and the Phase 3 formality check read them from the bible file.

### B-135 · `script_line.seq` is 1-based within its scene

- **Date:** 2026-10-16 · 2.0 · commit `870c54b` · DP-6; refined by 2.9A ([B-269](#b-269--the-synthetic-show-is-a-template-generator-with-truth-by-construction-a-script-line-is-a-fountain-element))
- **Choice:** `{ep}/line/{scene}.{seq}` with seq the 1-based position of the element in the scene (`S01E01/line/1.2` is scene 1's second element). 2.9A found that the Fountain reader merges consecutive action paragraphs into one element, so seq counts elements, not printed lines. **Consequence:** 2.9A's line labels and 2.1/2.3 refs use the same base.

### B-136 · Line, ASR, fact and clearance refs are built in `nip.store.load`

- **Date:** 2026-10-16 · 2.0 · commit `870c54b` · DP-7
- **Context:** `nip.contracts.refs` is frozen and has builders only for scene, shot, keyframe and cue; `refs.parse` already reads the other formats.
- **Choice:** f-strings in `load.py`. **Proposal (not ruled in the ledger):** add `line()`, `asr()`, `fact()`, `clr()` builders to `refs.py`, together with the rr m3 fix (require a BCP-47-shaped lang in `parse`). 2.close later added `refs.occurrence()` / `refs.is_occurrence()` there ([B-306](#b-306--occurrence-ref-clrocc-hash-with-kind-clearance_item-occurrences-are-derived-not-stored)).

### B-137 · Fact spans carry their source quotes; clearance-item spans carry the item name

- **Date:** 2026-10-16 · 2.0 · commit `870c54b` · DP-8
- **Choice:** a fact span's text is its source events' quotes joined with newlines in event-id order, with no frames, so a quote check (`ev.quote in span.text`) accepts any source quote. Clearance-item spans: text = item name, no frames; all of the show's items are included, without filtering by scope.

### B-138 · The `CHECKS` construction convention

- **Date:** 2026-10-16 · 2.0 · commit `870c54b` · DP-9
- **Choice:** each agent package exports `CHECKS: list[type[Check]]`; a class is used when `cls.active(available)` holds and is constructed with only the keywords its `__init__` names, out of `langs` (target languages), `source_lang`, `conn` (the run's SQLAlchemy Connection, or None in file mode), `show`, `episode`. A `ValueError` from a constructor (no rule pack) is `INPUT_REJECTED` and nothing is written.
- **Options rejected:** a context object (needs a new type in `agents.base` or the frozen contracts); factories (lose `Check.active` on the class).
- **Consequence:** `Readability(langs)` stays untouched; 2.3's SQL checks get the run's own connection and see rows written earlier in the same transaction.

### B-139 · Run artifacts are per episode

- **Date:** 2026-10-16 · 2.0 · commit `870c54b` · DP-10
- **Context:** the brief and data-model put the report at `runs/{run_id}/report.json`, but a run spans episodes and `Report` is per episode.
- **Choice:** `nip-artifacts/runs/{run_id}/{ep}/report.json` and `--out-dir/{ep}/...`, plus `runs/{run_id}/plan.json` (the full Plan with its `plan_N` id) and `--out-dir/run.json`. The reviewer accepted the deviation.

### B-140 · Run lifecycle and the stage contract: `ep.unit()`, gaps, coverage from check units

- **Date:** 2026-10-16 · 2.0 · commits `870c54b`, `0a086a1` · DP-11 and the fix round 1 proposal; review I1
- **Context:** the first version let a stage only raise (failing the whole run), inserted units inside `stage_checks`, and computed coverage over every unit, which raised `KeyError` on content stages ([journal](journal.md#2026-10-16--20-review-and-two-fix-rounds-the-stage-contract-artifacts-after-commit-stable-refs-a-savepoint-per-unit)).
- **Choice:** prepare (episodes, inputs, check construction; a rejection writes nothing) → plan and run rows committed (`running`, `code_version` = HEAD SHA plus `-dirty` when tracked files differ, `previous_run_id` = the show's last run over the same sorted `episode_ids`) → stages in one transaction → `completed`, or `completed_with_gaps` when any unit failed; on an exception the transaction rolls back, the run is set `failed` and the exception is re-raised. A stage records work through `with ep.unit(stage, key, model_variant=...)`; a failed unit is a gap and the stage continues; units are inserted once per episode after its last stage; coverage per agent counts only check-id units (1.0 when the agent is active with no units, 0.0 when all its checks were skipped); content-stage gaps only set `completed_with_gaps`, because the Report's coverage is keyed by agent. `add_stage(name, fn, before="timeline")` keeps call order. One attempt per unit (`ponytail:`; retries with backoff come with model stages); `cache_key` NULL and `--force` accepted with no effect until 2.9B.
- **Consequence:** W1 stages are `fn(ep) -> None`, read `ep.plan`, and wrap each unit in `ep.unit`. The docs' "retry up to 3 times with backoff" is not built (doc correction).

### B-141 · Artifacts are published only after the commit; the whole run is one transaction

- **Date:** 2026-10-16 · 2.0 · commit `0a086a1` · review I2; **Controller ruling** (whole-run transaction)
- **Context:** reports uploaded inside the episode loop survived a rolled-back run and named flag ids that never existed.
- **Choice:** `publish()` writes S3 and `--out-dir` after `conn.commit()`; the whole run, across episodes, is all-or-nothing (R8). The controller ruled this acceptable for Phase 2 on condition that 2.9B writes stage-cache entries and objects in their own transactions.
- **Consequence:** a crash in episode N discards episodes 1..N−1, including GPU work, until the cache exists (2.9B-1 writes each cache put in its own short transaction, [B-122](decisions.md#b-122--cache-objects-are-gzip-json-not-zstd)). If an S3 upload fails after the commit the run is `completed` with no report (re-review m-d, accepted as the lesser failure).

### B-142 · A store run plans with `current_plan({})`

- **Date:** 2026-10-16 · 2.0 · commit `870c54b` · DP-12
- **Choice:** `nip plan`'s path, with `NIP_PROFILE=cpu` giving the stub Plan; the workload is empty because no check declares a model slot yet (W-int adds slot workloads). The plan row stores the inventory, catalog sha, objective, and decisions/pins/amendments as JSON. The report's `plan.mode` is the Plan's mode (`resident` for the empty plan; file mode had used the `staged` sentinel).

### B-143 · The file-mode CLI is renamed `nip run-files`; `nip run` is the store command

- **Date:** 2026-10-16 · 2.0 · commit `870c54b` · DP-13 · supersedes the Phase 1 CLI form of [B-103](decisions.md#b-103--srcnippipelinepy-is-the-phase-1-composition-root-and-nip-run-takes-files)
- **Choice:** `nip run --show S --episodes E…` is the documented store command (synchronous, R8); the file command is kept as `nip run-files` so agents without Postgres can still run the walking skeleton, and builds its checks through the same `build_checks`.

### B-144 · Keyframe object keys use the shot index

- **Date:** 2026-10-16 · 2.0 · commit `870c54b` · DP-14
- **Choice:** `{show}/{ep}/keyframes/{shot_index}_{n}.jpg`, not `{shot_id}`, because the index is the evidence-ref id ([B-062](decisions.md#b-062--sub-frame-cues-keep-one-frame-and-shot-refs-use-the-list-index)). Images are uploaded only when `<picture.json dir>/keyframes/<file>` exists; Sintel's cached `picture.json` has no images beside it, so its 398 keyframes have no `object_key`.

### B-145 · `script_line.speaker` is added by 2.8 in migration 0002

- **Date:** 2026-10-16 · 2.0 (DP-15) → 2.8 · **Controller ruling**
- **Context:** `script_line` had no speaker column and `speaker_entity_id` stays NULL until 2.1's entity resolution, so the speaker name was lost at ingest, and 2.1 needs speakers.
- **Choice:** 2.8, the sole schema owner, adds `script_line.speaker text` in 0002; 2.0's `_write_script` writes it (one line). Until then speakers came from the stored script object. **Cost if wrong (ledger):** one more migration.

### B-146 · A Serve client module is named after its slot (`clients/text_embedder.py`)

- **Date:** 2026-10-16 · 2.0 (DP-16) → 2.8 · commit `870c54b` · **Controller ruling**
- **Context:** `_bind` resolves `nip.runtime.clients.<slot value>.Actor`; the text embedder slot is `text_embedder`, but phase2-plan named the module `embedder.py`, and `clients/__init__.py` is frozen.
- **Choice:** the module is `clients/text_embedder.py`, so the generic hook works; carried into the 2.8 brief. A module that exists but fails to import raises instead of silently falling back to `Placeholder`; after review m7, an app whose slots resolve to different actor classes raises `ServingError`.

### B-147 · Every flag must carry at least one stable evidence ref

- **Date:** 2026-10-16 · 2.0 · commit `0a086a1` · review I3 · **Controller ruling**
- **Context:** R13 excludes `fact/` and `asr/` refs from the fingerprint because they churn on re-extraction; a flag citing only facts then hashed to `sha256(check + "\n" + lang)`, shared by every such flag of that check in every episode, so one override would override all of them and a new finding would look "unchanged".
- **Options (reviewer):** raise when no stable ref remains, or fall back to the fact's source-line refs.
- **Choice:** a flag must cite at least one scene, line, shot, keyframe, cue or clearance-item ref; `runs.fingerprint` raises `ValueError` otherwise, and `require_stable_refs` drops such flags at verification with reason `no stable evidence ref (scene/line/shot/kf/cue/clr), R13`, in store and file mode. **Cost if wrong (ledger):** a pure fact-only finding needs a scene anchor, which is always available for plot rules.
- **Consequence:** 2.3's SQL rules cite the offending line or scene as the claim. Drops are logged, listed in the run summary and `dropped.jsonl`, not persisted (re-review m-c).

### B-148 · Each work unit runs in a savepoint; a malformed evidence ref is a counted drop

- **Date:** 2026-10-16 · 2.0 · commit `9d0727d` · re-review N1
- **Context:** without a savepoint a failed unit's partial rows were committed with the run, and a DB error inside a unit aborted the Postgres transaction for every later unit.
- **Choice:** `ep.unit()` wraps its body in `conn.begin_nested()`, rolls back to the savepoint on `Exception`, records the gap, and releases the savepoint on success (one SAVEPOINT/RELEASE round trip per unit). `BaseException` still propagates to `run_store`, which rolls back the whole run. `require_stable_refs` catches `refs.parse`'s `ValueError` and drops the flag with `malformed evidence ref: …`.
- **Consequence:** a unit's output is all-or-nothing; a body must not call `conn.commit()` / `rollback()` itself.

### B-149 · `nip eval compare` prints every logged metric and refuses mixed groups (R10)

- **Date:** 2026-10-16 · 2.0 · commit `5989485` · ruling R10 ([B-120](decisions.md#b-120--phase-2-plan-rulings-r1-to-r15-adopted)); closes 1.11 minors
- **Choice:** a row for every other logged metric key; `--exp` validated against `[\w.-]+` (it goes into an MLflow filter); `--subset` must be `shown` or `all`; a variant column whose runs repeat a seed or have different `plan_fingerprint` values is refused; `nip eval run` ids are `{set}-s{seed}-{ts}-{variant}-{4 hex}`. `--md` stays a no-op flag.
- **Consequence:** experiment numbers can be read from `nip eval compare` alone, as the docs' rule requires.

### B-150 · The store integration tests go into CI in W-int

- **Date:** 2026-10-16 · 2.0 · **Controller ruling**
- **Context:** `ci.yml` was not 2.0's file; the store tests ran only locally against the compose Postgres.
- **Choice:** adding `tests/integration/test_store.py` (with `test_migrations_pg.py`) to `ci.yml` is assigned to W-int.

## 2.1 Fact extraction, grounding, entity resolution, consolidation

### B-151 · Knowledge thresholds stay module constants until `config/pipeline.yaml` is free

- **Date:** 2026-10-16 · 2.1 · commit `38fa323` · **Controller ruling** (W1 dispatch: "config/pipeline.yaml stays 2.5's until 2.5 is complete; 2.1 keeps knowledge keys as module constants until told")
- **Context:** the 2.1 brief made 2.1 the sole W1 owner of the `knowledge:` keys, while 2.5 was still writing the file. **Options:** add the keys now, or keep constants. **Choice:** constants (`extract.PROMPT_VERSION`, `extract.MAX_TOKENS` 2048, `grounding.THRESHOLD` 90, `entities.RESOLVE_THRESHOLD` 90), with the proposed YAML in the notes. **Consequence:** the reviewer's M-5 called the notes' "2.5 owns the file" wrong for this key; nothing functional. Cost if wrong, as ruled: one later move of keys. W-int moved them into `config/pipeline.yaml` (`3d66622`); 2.1B's `EVENTS_PER_LINE` is still a module constant.

### B-152 · `LLMClient` goes through instructor and returns a plain instance parsed from the final reply

- **Date:** 2026-10-16 · 2.1 · commit `38fa323` · 1.7 review M6
- **Context:** D-025 and tech-stack's build notes ask for instructor in JSON-schema mode with one repair; Phase 1 deferred it ([B-079](decisions.md#b-079--only-the-llm-client-in-phase-1-stubs-are-minimal-valid-schema-instances-instructor-deferred)). **Choice:** JSON-schema mode, `max_retries=1`, `context=` (instructor 1.17's keyword), temperature 0, thinking off; the instance instructor returns (a subclass carrying `_raw_response`) is not returned, the final reply is re-parsed into the schema. **Consequence:** 1.7's wire test passes unchanged; only the line number is a structural validator, so a bad quote drops the event without a repair.

### B-153 · Recorded LLM stub keyed by sha256(variant, system, prompt, schema)

- **Date:** 2026-10-16 · 2.1 · commit `38fa323` · D-020; brief item 5
- **Choice:** recordings in `tests/fixtures/llm/{key}.json`, replayed for `qwen3.5-4b-awq` by exact call, else `stub_instance`; `NIP_LLM_RECORD_DIR` records real replies. The key includes `system` (a superset of the brief's key); `json.dumps(sort_keys=True)` over `model_json_schema()` makes it deterministic. **Consequence:** any prompt, registry or schema edit needs a re-recording (D-020's stated cost): 2.1B re-recorded twice (`b8d320b`, `8a5d5bd`). A miss is logged since `6b2ddf4` (review M-9), because a silent fallback turns replays into empty event lists.

### B-154 · Registry keys are bible id or canonical name; candidates are not in the enum

- **Date:** 2026-10-16 · 2.1 · commit `38fa323` · DP-1 in notes/2.1.md
- **Choice:** the enum is built from bible ids for characters, else canonical names, in id order; candidate entities are excluded, so a prompt does not change with earlier extraction output and recordings stay replayable. Unknown names fall back to fuzzy matching. **Consequence:** review M-7: two non-character entities with the same canonical name (a location and a brand "Harbor") give a duplicate enum value; the proposal (`kind:name` for the later one) was not built because no current registry collides.

### B-155 · Grounding: normalized `partial_ratio` ≥ 90, `ratio` for over-long quotes, two-word minimum

- **Date:** 2026-10-16 · 2.1 · commits `38fa323`, `6b2ddf4` · DP-8; review M-4
- **Choice:** NFKC + quote marks and dashes + whitespace, `partial_ratio` ≥ 90; `ratio` when the quote is longer than its line; a quote needs two words unless it is the whole line (fix round 1). Threshold 90 kept because 85 / 90 / 95 are indistinguishable on real output ([EXP-006](experiments.md#exp-006--grounding-validator-threshold)). **Consequence:** the check bounds quotation, not truth; 2.1B added argument checks next to it ([B-167](decisions.md#b-167--post-model-drops-zero-confidence-duplicates-argument-kinds-per-predicate)).

### B-156 · Raw events were uploaded inside the stage (deviation, moved by W-int)

- **Date:** 2026-10-16 · 2.1 · commit `38fa323` · DP-2; review M-1
- **Context:** EXP-006 needs pre-grounding events per run; 2.0's contract publishes artifacts only after commit. **Choice:** `runs/{run_id}/{ep}/knowledge.events.raw.jsonl` written inside the stage, each event with its grounding verdict and resolved ids; a failed run can leave the object behind. Not moved in the fix round because `publish` is in `pipeline.py` (W-int's file). **Consequence:** W-int (item 4a) added `EpisodeRun.artifacts` and moved the upload into `publish`.

### B-157 · `fact_event.work_unit_id` stays NULL

- **Date:** 2026-10-16 · 2.1 · commit `38fa323` · DP-3; review M-2 (accepted)
- **Context:** work-unit rows are inserted after the episode, so their ids do not exist while the stage runs. **Choice:** NULL; the column is nullable. **Consequence:** linking was left to 2.9B (per-scene cache) or an `EpisodeRun.unit` that inserts at start.

### B-158 · Consolidation re-runs show-wide and keeps the ids of unchanged facts

- **Date:** 2026-10-16 · 2.1 · commits `38fa323`, `6b2ddf4` · DP-4; review I-2
- **Context:** the first version superseded all active facts and reinserted them, so `fact/{id}` evidence stopped resolving and the table grew on every run. **Choice:** identity = (predicate, subject, object, value, story range, screen range); an unchanged fact keeps its row (events and confidence updated in place); facts no longer produced are superseded before inserts (the EXCLUDE constraint holds); new facts carry `supersedes`. **Consequence:** a no-op re-run adds 0 rows; ≥ 80 % of S01E01's ids survive S01E02. Still open: `load_timeline` resolves only active facts, so an episode-1 `fact/{id}` closed by episode 2 stops resolving (re-review M-b; flags keep a stable line ref); `supersedes` can name the wrong predecessor when several old facts share (predicate, subject, object) (M-a); a reviewer's `fact_correction` retraction is not carried into the next consolidation (Phase 4's correction loop must re-apply it). Re-extraction deletes the scene's previous `fact_event` rows, so superseded facts may point at deleted event ids (the array column has no FK).

### B-159 · Interval choices the docs left open

- **Date:** 2026-10-16 · 2.1 · commit `38fa323` · DP-5
- **Choice:** `state: injured` lasts until another state of the subject (`healed` / `treated`), not until the end of the story day; holds/owns end when someone else holds the object, on give / lose / lost / drop / sell, or on the object's destroyed / lost state; closed screen ranges end at the superseding scene's screen start, or at the fact's own last scene when the superseding scene is earlier on screen; without a full `story_seq` script order is used and nothing is inferred.

### B-160 · Fact shapes shared with 2.3, and `state: lost` from lose/drop events

- **Date:** 2026-10-16 · 2.1 · commit `38fa323` · **Controller ruling** (four rulings applied, the last from 2.3's review I-1)
- **Choice:** a use is a `holds` event with `{"event": "use"}` inside the holder's fact; `state` facts carry `value.state`; speakers resolve into `script_line.speaker_entity_id` and no candidate is created for an unmatched speaker (for 2.3's dead_acts); a `state: lost` event is its own fact, and a holds/owns lose / lost / drop event also yields the prop's `state: lost` fact from the same event id, both ending the holds interval. **Consequence:** without the last ruling `plot.prop_provenance`'s lost case could never fire on extracted facts (2.3 review I-1, fixed in 2.3 by `3aa1594`). Tests `test_state_lost_is_a_fact_and_a_later_state_ends_it`, `test_holds_ends_when_given_away_or_destroyed`.

### B-161 · Names match on whole words (subset with at least half the words), an exact name scores 101

- **Date:** 2026-10-16 · 2.1 · commits `6b2ddf4`, `608c5a1` · review I-1, re-review N-1
- **Context:** WRatio scored any containment at exactly 90 ("tomato" → Tom, "Dover Street" → Dov). **Options:** raise the threshold (would also break "Ada" → "Ada Kovac", which used the same 90 path); `token_set_ratio` (the reviewer's suggestion; accepts the reverse containment "Dov Street" → Dov, "Captain Ada Kovac" → Ada); a directional whole-word subset. **Choice:** lower-case and strip punctuation; 100 when the surface's words are a subset of a known name's words and at least half of them, else rapidfuzz `ratio` (tolerates a typo: "Tomas Vael" 90); an exact normalized name scores 101 so it beats subset ties; whitespace collapsed. **Consequence:** titles, possessives on one-word names and lone middle names ("Captain Kovac", "Tom's", "Maria") fail closed into the candidate queue (recall cost, visible in `review_queue`); a bare surname candidate ("Vale") absorbs every later bare "Vale". Probes in [C-22](experiments.md#c-22--entity-name-scorer-wratio-vs-whole-word-subset-vs-exact-first).

### B-162 · Object-less holds/owns/wearing events are not stored

- **Date:** 2026-10-16 · 2.1 · commit `6b2ddf4` · review M-8
- **Context:** `f.object_id == e.object_id` with None == None let an UNKNOWN object with no name end or continue an unrelated object-less holds fact. **Choice:** drop them at save time.

### B-163 · EXP-006 (first wave): keep threshold 90; the bar is not met by any threshold

- **Date:** 2026-10-16 · 2.1 / EXP-006 · commit `38fa323` (MLflow re-sweep after `6b2ddf4`) · DP-8
- **Choice:** keep 90 (no measurable difference between 85, 90, 95) and record that D-005's quote check bounds quotation, not truth; propose argument type checks. Status done, bar not met. Superseded in part by [B-181](#b-181--exp-006-ship-the-argument-checks-the-bar-is-still-not-met) (checks shipped). Evidence: [EXP-006](experiments.md#exp-006--grounding-validator-threshold).

### B-164 · EXP-020 (first wave): no decision until the rule-precision half

- **Date:** 2026-10-16 · 2.1 / EXP-020 · commits `38fa323`, `6b2ddf4`, `608c5a1` · DP-7; review M-6
- **Choice:** status inconclusive. The enum is "not shown at least as accurate" (0.949 vs 0.966, about 1.4 SE on about 550 arguments and 1 seed), not "fails". Alias resolution cannot be judged on the synthetic show (0 alias-only fact arguments). Continued in [B-180](#b-180--exp-020-inconclusive-d-025-registry-ids-as-an-enum-stands-by-default).

## 2.1B Runaway guard, argument type checks, knowledge experiments on real models

### B-165 · Runaway guard: at most 4 events per scene line, enforced by the grammar

- **Date:** 2026-10-16 · 2.1B · commit `b8d320b` · DP-1 (shipped)
- **Context:** the model loops inside valid JSON (W-serve: 42 events, 40 `wearing` at confidence 0.0) until `max_tokens`. **Options (brief):** `maxItems`; `confidence` minimum > 0 in the schema; dedupe; repetition / frequency penalty. **Choice:** `maxItems` = `EVENTS_PER_LINE` (4) × the scene's line count (largest legitimate reply in 2.1's 1,217 saved events: 3.5 per line; the looping scene: 10.5); confidence-0 events dropped after the call rather than forbidden in the schema (a constraint the grammar might not enforce would turn the whole reply into a repair); no penalty (it would penalise the repeated JSON keys; not tried). **Consequence:** failed scenes 8/75 → 0/150 ([C-23](experiments.md#c-23--runaway-guard-21s-schema-vs-a-per-line-cap-vs-cap--line-enum)); a capped reply's last item can be malformed (probe), and capped scenes' surplus is dropped. Ceiling (a `ponytail:` note in the code): a 30-line scene may ask for 120 events, more than `max_tokens: 2048` holds; scale `max_tokens` with the line count when real scripts need it. Proposed key `knowledge.extract.events_per_line: 4`.

### B-166 · `line` is an enum of the scene's line numbers

- **Date:** 2026-10-16 · 2.1B · commit `b8d320b` · found during the runs
- **Context:** the cap-only pass still failed 2/150 with "line 2 is not a line of this scene ([1])", repeated by the repair call. **Choice:** `line` is a `Literal` of the scene's line numbers (the context validator stays for stubs). **Consequence:** 0/150 failures, but the review showed the two scenes were a rendering bug (two paragraphs under one number, [B-169](#b-169--the-prompt-prints-one-numbered-line-per-script_line)); the enum forced line 1 there "correct by luck" and hid the symptom.

### B-167 · Post-model drops: zero confidence, duplicates, argument kinds per predicate

- **Date:** 2026-10-16 · 2.1B · commit `b8d320b` (refined in `22074b9`) · DP-2 (shipped)
- **Context:** EXP-006 showed the quote check keeps 93 % of hallucinated events, which are wrong arguments with correct quotes. **Choice:** `save_events` drops zero-confidence events, repeated events (same raw line / predicate / subject / object / names / value) and events whose argument kinds do not fit the predicate (`entities.ARG_KINDS`, from the prompt's predicate definitions); candidates are created only for kept events; every drop is counted and kept in the raw file with its reason. In fix round 1: subject-less events get their own reason `no subject` (M7), `seen` holds kept events only (M1). Two kinds are wider than the prompt (M7): a `state` subject may be a location, a `mentions` object may be a person or a term. **Consequence:** hallucinated kept 0.93 → 0.27, true dropped 0 → 1/150; enum fact precision 0.59 → 0.86 ([EXP-006](experiments.md#exp-006--grounding-validator-threshold), [EXP-020](experiments.md#exp-020--entity-resolution-enum-constrained-ids-vs-fuzzy-matching-afterwards)).

### B-168 · The OpenAI SDK under instructor runs with `max_retries=0`

- **Date:** 2026-10-17 · 2.1B · commit `b8d320b` · DP-3
- **Context:** the SDK's default `max_retries=2` re-sent a deterministic temperature-0 request after each 600 s timeout: 3 scenes took 1,801 to 1,803 s. **Choice:** no SDK retries; instructor's one repair stays. A timeout of a temperature-0 request is not transient.

### B-169 · The prompt prints one numbered line per `script_line`

- **Date:** 2026-10-17 · 2.1B fix round 1 · commit `22074b9` (fixtures re-recorded in `8a5d5bd`) · review I1
- **Context:** the Fountain reader joins consecutive action paragraphs into one `script_line` with `\n\n`; the second paragraph was printed unnumbered and cited as the next line, so grounding dropped it. **Options (review):** flatten paragraphs in `render`, or split action paragraphs into lines at ingest (changes line refs). **Choice:** flatten in `render`, whitespace collapsed; line refs and 2.0's ingest unchanged. **Consequence:** quote drops 28.7 → 3.7 (free text) and 57.3 → 4.3 (enum) per show, free-text fact recall 0.860 → 0.887 ([C-26](experiments.md#c-26--one-printed-line-per-script_line-quote-drops-before-and-after)).

### B-170 · Resolved dialogue speakers are present at the heading's location (D-2.1B-1)

- **Date:** 2026-10-17, amended 2026-10-18 · 2.1B fix rounds 1–3 · commits `22074b9`, `962512f`, `dd557fe` · D-2.1B-1; review I1, re-review N3
- **Context:** `plot.two_places` needs `present_at` on lines such as "I got here as fast as I could.", which name no place; a quoted fact cannot come from them. **Choice:** `save_speakers` adds a derived `present_at` for each resolved dialogue speaker at the location the scene heading names, on the speaker's first line, quote = the whole line, confidence 0.9, unless the model already gave it. Amended: not for off-screen voices (V.O., O.S., O.C., filtered, pre-lap, phone, radio, intercom, voice-over) by cue or preceding parenthetical; **not** skipped in `intercut` scenes (tried: two_places 9/9 → 0/9, because `intercut` also marks SAME TIME scenes, which is where the rule is defined). **Consequence:** two_places 0 → 9/9 in both arms; fact precision scored against truth drops (enum 0.728 → 0.647) because truth puts `present_at` on the action line, not the speaker's line ([C-24](experiments.md#c-24--derived-speaker-presence-with-without-and-skipping-intercut-scenes)). Confidence 0.9 is above `NIP_FACT_REVIEW_THRESHOLD` 0.80, so the facts are active without review.

### B-171 · A candidate entity's guessed kind is provisional

- **Date:** 2026-10-17 · 2.1B fix round 1 · commit `22074b9` · review I2
- **Choice:** `Resolver.provisional` holds every candidate id; `typed` checks only confirmed kinds. **Consequence:** a prop first met as a `state` subject (guessed character) is still a valid `holds` object; drops no longer depend on event order.

### B-172 · holds/owns values are mapped only from the prompt's vocabulary; other verbs are dropped and counted (D-2.1B-2)

- **Date:** 2026-10-18 · 2.1B fix rounds 1–2 · commits `11d03c4` (superseded), `962512f` · D-2.1B-2; **Controller ruling** on re-review N2
- **Context:** the model wrote `check` (186) and `share` (171) where the prompt says `use`, and `plot.prop_provenance` reads `value.event = 'use'`. **First version (`11d03c4`, superseded):** any other verb → `use`, take/pick up/grab/get/find → `obtain`; free-text recall 0.25 → 0.47 at 92.3 false positives per injected show; the re-review showed the catch-all was chosen from and evaluated on the same replies, turned `remove` from an ending into a use, and turned acquisitions into uses (N2). **Choice (ruling):** `HOLDS_VERBS` maps obtain / pick up → obtain, use / carry / check → use, give / lose / lost / drop / sell / remove → themselves (with inflections); anything else is dropped as `unknown holds value` and counted, never guessed. **Consequence:** prop_provenance recall stays 8/9 with false positives 58.3 → 29.3 per injected show; `take`, `get`, `gets` are now dropped, which loses acquisitions on real scripts; the re-review's root-cause suggestion (enforce the prompt's value vocabulary in the schema) is open ([C-25](experiments.md#c-25--holdsowns-values-as-written-vs-any-verb--use-vs-prompt-verbs-only)).

### B-173 · `script_line.speaker` stores the character cue as written (D-2.1B-3)

- **Date:** 2026-10-18 · 2.1B fix round 3 · commit `dd557fe` · D-2.1B-3; **Controller ruling** ("a minimal ingest change is allowed, with no schema migration")
- **Context:** `script.speaker_name` stripped `(V.O.)` at ingest, so N3's off-screen check could only see parentheticals. **Options (re-review):** keep the extension at ingest, or skip derived presence in intercut scenes (rejected, see B-170). **Choice:** `script.Element` carries `speaker` (clean name) and `extension`; the store writes speaker + extension into `script_line.speaker` (no migration); name readers use `speaker_name`. **Consequence:** shows ingested before this change keep clean speakers until re-ingested; the raw cue reached the extraction prompt (re-review 3 M-new1), fixed later by 2.9B-1 (`e2bab95`).

### B-174 · All GPU work in the EXP harnesses goes through `gpu_session`, which releases only a lock it owns

- **Date:** 2026-10-17 to 2026-10-18 · 2.1B · commits `dc4e6fc`, `bb68eac`, `22074b9`, `962512f`, `dd557fe` · review M2/M3, re-review N1, re-review 2 m5
- **Context:** a crashed teardown held the lock 03:54 to 06:11; the desktop's VRAM made the planner refuse arms; extraction passes relied on a manual `mkdir`; the first `gpu_session` could tear down another holder's apps. **Choice:** UTF-8 decoding and release in its own `finally`; wait with the lock released while the device holds more than 1,500 MiB (retry every 5 min, 150 s gap after each release); `gpu_session(purpose, arm)` = acquire, wait, deploy, body, delete every Serve app and release in nested `finally`s, logging a dirty release; `owner.txt` ends with `pid N` and teardown/release run only when this process holds it; `owner.txt` is written into `gpu.lock.<pid>` and renamed onto `gpu.lock`. **Consequence:** not covered (re-review, inherent to an mkdir lock with no staleness check): a hard kill. Processes outside the harness can still use the GPU during the lock (the 2026-10-18 collision).

### B-175 · EXP harness `down` deletes Serve apps by status

- **Date:** 2026-10-17 · 2.1B · commit `bbf653a` · 2.2B finding (`23f13d4`)
- **Context:** `exp020_resolution down` re-planned with the model loaded and deleted nothing. **Choice:** delete every Serve app by `serve.status()` and wait for VRAM; the EXP-018 driver calls `down` after every round.

### B-176 · Secret-in-scene check for learns/references: measured, not shipped

- **Date:** 2026-10-17 · 2.1B · commit `bbf653a` (variant in `exp020_rules`) · DP-4
- **Choice:** not shipped. The variant (partial_ratio ≥ 90 of the secret's description vs the scene text) removed 12 of 16 enum false positives on the clean seed-1 show (16.00 → 3.67 ± 0.58 per clean show over 3 seeds), did nothing for the free-text arm and nothing for recall, and encodes how this generator writes secrets; it needs a real-script check first. The reviewer agreed it should not ship before I1 was fixed and real scripts are checked.

### B-177 · Prompt v2 for learns vs references: proposed, not built

- **Date:** 2026-10-17 · 2.1B · DP-5
- **Context:** on the clean seed-1 show the enum arm's kept learns/references events: 8 correct, 8 with the predicate swapped, 2 with a wrong subject, 37 on lines where truth has no secret event; on the planted "Do not worry. <secret>. I have known for a long time." the model emits both `learns` and `references`, and a `learns` at the same story position counts as learned, so `plot.knowledge_order` cannot fire. **Proposal:** the teller references, the listener learns, never both on one line. Not built: needs `pipeline.yaml`'s `prompt_version` (not 2.1B's file) and a re-recording. knowledge_order stayed 0/9 in every variant.

### B-178 · prop_provenance on never-obtained personal props: lower tier proposed to 2.3

- **Date:** 2026-10-18 · 2.1B fix round 1 · no code (2.3's SQL) · decision proposal "For 2.3"
- **Context:** with free-text props extracted, prop_provenance fires on personal items nobody ever obtains ("X uses the watch / thermos before obtaining it. No scene shows anyone obtaining it."). CPU what-if (not shipped): dropping the "never obtained anywhere" case removes all of them on the clean shows (58 / 67 / 55 → 0) but keeps only 3 of the 8 true flags (seeds 1–3: 2, 0, 1). **Proposal:** report such a use at a lower tier (review_recommended), or only for props the bible or a `setup` event tracks. Open; about 29 false positives per show remain after fix round 2.

### B-179 · EXP-018: do not adopt the FP8 KV cache

- **Date:** 2026-10-17, restated 2026-10-18 · 2.1B / EXP-018 · no code change (`serving.vllm_args`, planner KV term, catalog untouched) · DP-6; review M4, I3
- **Choice:** keep the default KV cache. Reason as restated: FP8 is 21 % slower (133.8 vs 169.7 tok/s unconstrained) and per-scene extraction gains nothing from more context (a scene prompt is about 1.5k tokens; the planner's 16k already exceeds it). The F1 leg of the bar is unresolved, not failed (one pass per arm; fp8-32k has no F1 pass; no default-16k start trials). **Consequence:** FP8 32k starts 10/10, so EXP-005's 32k arm could run on the laptop with an FP8 confound. Evidence: [EXP-018](experiments.md#exp-018--kv-cache-precision-on-the-laptop).

### B-180 · EXP-020: inconclusive; D-025 (registry IDs as an enum) stands by default

- **Date:** 2026-10-18 · 2.1B / EXP-020 · fix round 1 rewrite · review I3 (supersedes the first reading "done, keep the enum")
- **Choice:** status inconclusive. Enum accuracy 1.00 vs 0.96 is partly by construction (the type check removes exactly the enum's mis-resolved arguments) and the spec's metric (nicknames, titles, descriptions) has 0 alias-only arguments here; rule precision after the fixes (enum 0.20 vs free text 0.08) differs for reasons other than resolution: the enum has fewer knowledge_order false positives and cannot express props at all. **Next step:** a set with alias-only mentions (BH, R3) and prompt v2. Evidence: [EXP-020](experiments.md#exp-020--entity-resolution-enum-constrained-ids-vs-fuzzy-matching-afterwards).

### B-181 · EXP-006: ship the argument checks; the bar is still not met

- **Date:** 2026-10-17 · 2.1B / EXP-006 · commit `b8d320b` · EXP-006 follow-up decision
- **Choice:** ship the checks: hallucinated kept 0.93 → 0.27, true dropped 0.00 → 0.007 (1/150). The bar (≤ 2 % true dropped, ≤ 1 % hallucinated kept) is not met: kinds catch wrong-argument errors, not wrong-predicate or invented-relation errors. Status done (bar not met).

### B-182 · EXP-005: 8k arm only; inconclusive until the 32k arm runs

- **Date:** 2026-10-17 · 2.1B / EXP-005 · ruling R4 ([B-120](decisions.md#b-120--phase-2-plan-rulings-r1-to-r15-adopted))
- **Choice:** run the 8k arm on the laptop (synthetic show, generator truth, R3) and leave the success bar unjudged; the 32k arm is deferred to the Phase 4 cloud. The notes add that 8k vs 16k changes nothing in what the model sees (about 1.5k-token scene prompts); only the 32k variant (two neighbouring scenes on each side) is a different input.

### B-183 · `exp020_rules` is the harness for future extraction experiments

- **Date:** 2026-10-17 · 2.1B · commits `b8d320b`, `bbf653a` · DP-7
- **Choice:** a throwaway database per show, a reply cache keyed by call key (so clean and injected twin shows share replies), truth story order, and the shipped `save_events`, consolidation and rules; commands `extract`, `flags`, `score`, `facts`, `runaway`, plus `--secret-check` and `--no-presence` variants. Failed rows are removed from the cache before a retry, so every reply used is a successful one.

### B-184 · Fix round 1 must re-measure the plot rules on real facts; later rounds re-score without the GPU

- **Date:** 2026-10-17 / 2026-10-18 · 2.1B · **Controller ruling** (ledger: "fix round 1/5 sent + re-measure plot rules on real facts before/after"; "fix round 2/5 sent (rescore from saved replies, no GPU)")
- **Choice:** the first fix round re-ran real extraction (3 seeds, clean and injected) and scored before and after; fix rounds 2 and 3 re-scored the saved fix-round-1 replies. **Consequence:** the I1 bug's effect is measured, not argued; the r2 numbers carry no new model nondeterminism.

## 2.2 Story order and story days

### B-185 · A pure `derive` with the marker lexicon as module constants; the LLM only for ambiguous transitions

- **Date:** 2026-10-16 · 2.2 · commit `6ad9a53` · notes "What was built", P5
- **Context:** docs/architecture.md says derivation is rule-based, "ambiguous transitions go to the LLM with neighboring scenes", without defining ambiguous. EXP-007 needs a rules-only and a rules + LLM arm from the same code. The W1 controller ruling kept `config/pipeline.yaml` with 2.5 until 2.5 was done, and the brief said to keep the lexicon as module constants.
- **Choice:** `derive(scenes, overrides, llm=None, *, unit, memo)` is pure over `SceneIn`; `llm=None` is the rules arm. An ambiguous transition is a time of day that goes backwards between present scenes with no cue; the default is the next day with `story_inferred=true`; with an LLM there is one schema-constrained `Verdict` per transition (temperature 0), and a failed call leaves the default and records the unit `failed`. `Story.ambiguous`, `llm_calls` and `Position.source` (rule | llm | override) let EXP-007 score both arms from one return value. Lexicon and limits are module constants; proposed keys (not applied): `story.llm_max_tokens: 300`, `story.excerpt_chars: 600`, `story.inferred_confidence_factor` (the env `NIP_INFERRED_STORY_CONFIDENCE_FACTOR` already exists), `story.days_per_unit: {WEEK: 7, MONTH: 30, YEAR: 365}`.
- **Consequence:** the LLM is asked only on a regressing time of day, so scenes whose heading does not regress are never asked ("silent" cases, measured in [EXP-007](experiments.md#exp-007--story-order-rules-only-vs-rules--llm)). On the base synthetic show the trigger never fires.

### B-186 · Flashbacks with an unknown day rank first in the show and are inferred

- **Date:** 2026-10-16 · 2.2 · commit `6ad9a53` · P1 in the 2.2 notes
- **Context:** D-006 and architecture.md say flashbacks are "moved", not where.
- **Options:** keep screen position; place before the present; place at an LLM guess.
- **Choice:** unknown-day flashbacks rank first in the show; a known day (override, "N YEARS EARLIER") ranks by that day; both are `story_inferred` unless the day is explicit.
- **Consequence:** conservative for plot rules (a flashback never makes a character act before they could know something), and flags depending on it lose 15% confidence; wrong when a flashback shows something recent: rules-only tau 0.9998 on the synthetic show, where the generator puts the later of the two flashbacks earlier in story time.

### B-187 · Flashback spans: a heading cue marks one scene, a lead-in cue marks until the present returns

- **Date:** 2026-10-16 · 2.2 · commit `6ad9a53` · P2
- **Choice:** a flashback cue in a heading marks that scene only; a cue in the lead-in (previous scene's transition such as `FLASHBACK TO:`, or an opening super such as `THREE YEARS EARLIER`) marks every scene until PRESENT DAY / BACK TO PRESENT / END FLASHBACK or the episode end.
- **Consequence:** both conventions in real scripts are read, and an unended span cannot swallow the rest of the show. Lead-in scanning is loose (review M5: every transition of the previous scene counts; a short all-caps action line such as `THE VISION BLURS.` marks a vision); deferred.

### B-188 · Bible overrides always win, including over the LLM

- **Date:** 2026-10-16 · 2.2 · commits `6ad9a53`, `ad1b1b9` · P3, revised by review I2, I3, M1
- **Context:** architecture.md: "the bible's `story_overrides` always win". The first version let an LLM verdict add markers to a markers-only override (I2) and ignored an override day on a sharing scene for ordering (I3); an override flashback with no day was `inferred=false` (M1). Scene keys are free text ([B-020](decisions.md#b-020--bible-schema-leniency)).
- **Choice:** a non-empty override `markers` list replaces the detected markers (the Bible model cannot tell `markers: []` from absent); `story_day` replaces the day and, for a present scene, moves the day counter. With a markers-only override the LLM may fill only the unset day (`next_day`, `same_day`, `later_days`; source stays `override`); `earlier` / `simultaneous` are ignored. An override day on a dream / vision / intercut scene makes it its own rank unit at that day (marker kept, counter not moved). Override positions are `inferred=false`, except a flashback with no day (still a guess, `inferred=true`). Keys such as `S01E05 scene 3` and `s1e5 sc 3` are normalised to the ref; unmatched keys are logged as warnings, not rejected.
- **Consequence:** seq always follows day for overridden scenes (re-review probe: days 1, 9, 2 give seqs 1, 3, 2). Known edge (re-review minor): an unoverridden sharing scene directly after an override-day sharing scene inherits that day. Override markers are lower-cased but not validated against the marker set (review M6, deferred).

### B-189 · The stage re-derives the whole show for every episode; verdicts memoised per variant

- **Date:** 2026-10-16 · 2.2 · commits `6ad9a53`, `ad1b1b9` · P4, review M3
- **Context:** `story_seq` is show-wide, and ranking flashbacks needs every episode.
- **Options:** per-episode derivation with stored chain state (rejected: cannot rank flashbacks across episodes); re-derive the whole show and overwrite the rows (idempotent).
- **Choice:** the latter, with LLM verdicts memoised in a module dict so a multi-episode run asks each transition once; after the review the memo is keyed per model variant (`_VERDICTS[variant][prompt]`), so one variant's verdicts are not served to another.
- **Consequence:** transitions of other episodes are recorded as units of the current episode run (review M4, deferred), so per-episode coverage counts are off for multi-episode shows; a memo hit records no unit. The notes proposed that 2.9B's stage cache replace the memo, keyed on the show's scene `text_hash` set; 2.9B-1 did not cache `knowledge.story` ([journal](journal.md#2026-11-06--29b-1-stage-cache-incremental-re-runs-and-get-runsiddiff)).

### B-190 · Markers stored in the data-model set; cues read from every heading segment except the location

- **Date:** 2026-10-16 · 2.2 · commits `6ad9a53`, `ad1b1b9` · P6, review I1
- **Choice:** stored markers are the data-model set: `flashback`, `dream`, `vision`, `intercut` (INTERCUT, SAME TIME and MEANWHILE), `continuous` (CONTINUOUS, CONTINUING); the generator's `same_time` becomes `intercut`. PRESENT DAY ends a flashback; it is not a flashback marker. After review I1, `_tail` reads every " - " segment except the location (the segment starting INT./EXT., else the first) plus every parenthetical, so `FLASHBACK - INT. B - DAY`, `INT. B - FLASHBACK - NIGHT`, `INT. B - DREAM - NIGHT` and `INT. B - SAME TIME - NIGHT` are detected while `DREAM HOUSE` / `FLASHBACK DINER` stay locations.
- **Consequence:** a dream or intercut scene shares the seq and day of the last non-sharing scene, even a flashback. Doc corrections recorded for architecture.md.

## 2.2B EXP-007 story order: ambiguous-transitions variant and harness

### B-191 · An ambiguous-transitions synthetic variant so EXP-007 can discriminate

- **Date:** 2026-10-16 · 2.2 → 2.2B · **Controller ruling** (implemented in commit `11354bc`)
- **Context:** on the base synthetic show rules only score tau 0.9998 and rules + bible 1.0000, and no ambiguous transition is one the next-day default gets wrong ([C-27](experiments.md#c-27--story-order-on-the-base-synthetic-show-rules-only-vs-rules--bible-and-stress-variants)). Beverly Hillbillies is deferred (R3, [B-120](decisions.md#b-120--phase-2-plan-rulings-r1-to-r15-adopted)).
- **Choice:** 2.2B (W2) adds an "ambiguous transitions" variant with exact truth to `eval/synthetic`, additive only (2.9A's determinism tests stay byte-identical). Cost if wrong, as ruled: EXP-007 inconclusive.

### B-192 · EXP-007 holds the facts fixed (oracle facts); only the story columns vary between arms

- **Date:** 2026-10-16 · 2.2B · commit `11354bc` · notes, harness section
- **Context:** the brief asks for downstream precision of `plot.knowledge_order` and `plot.dead_acts`; 2.1B was changing extraction at the same time.
- **Choice:** every arm loads the same oracle facts from `truth.json` through 2.3's `layer1_oracle.consolidate`; only `scene.story_seq`, `markers`, `story_inferred` differ (the facts' story intervals follow the arm's seq). Arms are MLflow `variant` tags `<variant>-<arm>`, plus a `truth` sanity arm. Experiment `exp007-story`, tag `exp=EXP-007`.
- **Consequence:** precision differences are attributable to story order alone; they say nothing about real extraction. The fact set inherits 2.3's consolidation stand-in semantics (review M-6 of 2.3).

### B-193 · How the variant hides story time: prose cues, a regressing heading, silent cases kept

- **Date:** 2026-10-16 · 2.2B · commit `11354bc`
- **Choice:** NEXT MORNING → MORNING (`loose_next_day`) or → LATER (`later_unstated`); flashbacks lose "(FLASHBACK)" and "Years earlier." and open with "<N> years ago." in action prose (N 3..10, distinct; 2 of them are memories of dead characters); SAME TIME scenes lose "(SAME TIME)" and open with "At the same moment," / "Meanwhile," / "Across the harbor, at that very moment,"; the heading's time of day is forced to regress so a flashback, a cross-cut and a plain next day present the same heading signal. Scenes whose heading cannot regress are kept and marked `silent`. N is capped at 10 because `Verdict.days` allows at most 3650.
- **Consequence:** resolvable from text for flashbacks and simultaneous scenes (the regex cue reader reaches tau 1.0 on seed 1), but `later_unstated` has no prose cue at all (review M1, deferred), and the cues are fixed templates, so the variant measures explicit cues only. `ambiguate`'s sample sizes hold for seeds 1-3 only (review M4).

### B-194 · Prompt v2: a regressing time of day is normally the next day

- **Date:** 2026-10-16/17 · 2.2B · commit `11354bc` (file `config/prompts/knowledge.story.v2.md`) · notes "Tried X -> switched"
- **Context:** prompt v1 (2.2's) read a regressing time of day as `earlier`: verdict accuracy 0.29, 84 false flashbacks, cascading re-asks.
- **Choice:** v2 says a time of day going backwards is normal and almost always the next day; `earlier`, `simultaneous`, `later_days` only when the second scene's own text says so; check the relations in that order; default `next_day`; `reason` one short sentence. Same `$` fields as v1, so `build_prompt` is unchanged. One version only, not iterated after its run.
- **Consequence:** verdict accuracy 0.82 (mean of 0.893 / 0.792 / 0.769). v2 was written after v1's verdicts on all three seeds existed and its examples are the generator's templates, so it is tuned to this generator ([B-195](#b-195--storyprompt-is-v2)).

### B-195 · `story.PROMPT` is v2

- **Date:** 2026-10-17 · 2.2B · commit `6dc6ba8` · **Controller ruling** (proposal P1 in the 2.2B notes)
- **Context:** `story.py` is 2.2's file; the 2.2B brief allowed edits there only for bugs. v1 makes the story step a source of false flashbacks.
- **Options:** keep v1; switch to v2; drop the LLM step.
- **Choice:** switch to v2; 2.2B makes the one-line edit (`PROMPT = "knowledge.story.v2.md"`). The ruling's stated evidence was "+30 pts precision on held-out seeds"; the review then found "held out" overstated (I1), and the notes were corrected to "a ceiling for explicit cues on this generator". Cost if wrong, as ruled: v2 overfit to templated ambiguity.
- **Consequence:** every `nip run` with a `text_llm` slot uses v2; v1 is still reachable for `derive --arm llm`. No test pins `story.PROMPT` (re-review minor).

### B-196 · EXP-007 decision: keep the LLM step with prompt v2, bible overrides first

- **Date:** 2026-10-17 · 2.2B · commits `11354bc`, `6dc6ba8` · notes Decision, P2
- **Context:** bar "keep the LLM step if rule precision rises by ≥ 3 points". On the ambiguous variant v1 gives +18 points but drops planted `dead_acts` recall 1.00 → 0.56; v2 gives +30 with all 18 planted flags found; on the base show the LLM is never asked (+0, not testable). Bible overrides give precision 1.00 with no call but no intercut marker and no `later_unstated` days.
- **Choice:** keep the LLM step with v2, not v1; prefer bible overrides where the bible has them (`derive` already lets overrides win, so no code change). Rejecting v1 on recall is an extra criterion beyond the written bar, disclosed. EXP-007 status: done on the synthetic sets; the real-content check is deferred with R3.
- **Consequence:** the +26 to +30 points are a ceiling for explicit, templated cues; the LLM's value on real scripts, and against a plain regex cue reader, is unmeasured.

### B-197 · The experiment's `down` deletes Serve apps by status, under the GPU lock

- **Date:** 2026-10-17 · 2.2B · commits `23f13d4`, `6dc6ba8` (docstring) · notes "What broke" 3, review M3
- **Context:** `down` first re-planned to find the apps; with the model loaded the planner no longer fit it, so the list was empty, nothing was deleted, and teardown timed out on VRAM ([C-28](experiments.md#c-28--experiment-teardown-delete-by-re-planning-vs-delete-by-serve-status)).
- **Choice:** delete every app in `serve.status().applications`, then wait for idle. It deletes all Serve apps, not only this experiment's, which is safe only because every GPU user holds `data/gpu.lock`; documented in the docstring, not narrowed.
- **Consequence:** 18.9 s, VRAM 7651 → 343 MiB. 2.1B's `exp020_resolution.down` had the same flaw; 2.1B's commit `bbf653a` ("EXP harness down deletes Serve apps by status (2.2B finding)") adopted the by-status delete.

### B-198 · Three story-step improvements proposed and left undone

- **Date:** 2026-10-17 · 2.2B · notes P3, P4, P5
- **Choice:** not done: (P3) a cascade guard after a mis-called `earlier` / `simultaneous` (v1 asked 36 / 59 / 63 times against 26 / 23 / 26; v2 asks 24-28, so it is unnecessary here); (P4) a second trigger for silent cases (a scene whose own opening says "years ago" / "at the same moment" / "meanwhile"), unmeasured; (P5) raising `Verdict.days` from 3650 to 36500 ("twelve years ago" fails validation, one retry, then a gap with the rule default).
- **Consequence:** silent flashbacks and cross-cuts stay unreached (2 + 2 scenes on seed 2, 2 on seed 3), and `story/day_acc_present` stays low (0.10 rules, 0.32 v2) because one missed day shifts every later day.

## 2.3 Script Critic Layer 1 SQL rules

### B-199 · One parameterized SQL file per rule; claim on the script line; one flag per claim line

- **Date:** 2026-10-16 · 2.3 · commit `35a33ca` · notes decisions 3, 6
- **Choice:** `config/rules/plot.*.sql`, bound `:show` / `:episode` parameters, story order from scene rows (`scene.story_seq`, `markers`, `story_inferred`; a NULL `story_seq` never matches, and the prop rule excludes it explicitly), active facts only. A small loader (`layer1.rows()`) turns rows into `Finding`s: claim = `{ep}/line/{scene}.{seq}`, the setup or contradiction as `fact/{id}` with its quote, other-episode facts only as `fact/` refs. The loader keeps the first row per claim ref.
- **Consequence:** label granularity matches (a planted line). The reviewer found the SQL injection-safe (fixed file chosen by the `CheckId` enum, bound parameters). A dead character with N lines in a later scene still gives N flags (review M-1, deferred).

### B-200 · Severities 4 / 3 / 3 / 2; the inferred-story factor applied once, on raw event confidence

- **Date:** 2026-10-16 · 2.3 · commit `35a33ca` · notes decision 1, "What broke" 2
- **Choice:** `plot.dead_acts` 4 (a dead character on screen is glaring), `plot.knowledge_order` 3, `plot.two_places` 3, `plot.prop_provenance` 2 (easy to miss, easy to fix). Confidence = min of the cited events' raw `fact_event.confidence`, x `NIP_INFERRED_STORY_CONFIDENCE_FACTOR` once if any cited scene is `story_inferred`, because 2.1's consolidation already stores the reduced value in `fact.confidence`.
- **Consequence:** no squared discount. The 0.85 default is now duplicated in three places (`consolidate.py`, `story.py`, `layer1.py`; review M-7, deferred: agents cannot import `nip.knowledge`). 2.9B-1 later added the factor to `SqlRule.params()` so changing it misses the cache.

### B-201 · The fact contract the rules assume (and what 2.1 must emit)

- **Date:** 2026-10-16 · 2.3 · commit `35a33ca` · notes decision 2, "What broke" 1
- **Context:** the data model has no predicate or value shape for a prop use, and the EXCLUDE constraint forbids a separate `holds` fact for it.
- **Choice:** `present_at` = the scene's own range with object = the location; `references` and `learns` objects = the secret; death = a `state` fact with `value.state = 'dead'` (open-ended); props: `holds` / `owns` events, a use = a `holds` event with `value.event = 'use'` (any other `holds` / `owns` event is a possession); destroyed / lost = a `state` event on the prop entity with `value.state` in (destroyed, lost). The prop rule reads the source events (`fact_event`) of active facts, so it works after consolidation merges a holder's events. Speaking = `script_line.speaker_entity_id` (dead_acts counts such lines also without a `present_at` fact). "Never obtained" means nobody held or owned it (matches `eval/synthetic/rules.py`).
- **Consequence:** the reviewer found death/destroyed to be the docs' own contract, the use shape an invention that 2.1 had already adopted verbatim (`consolidate.py` docstring, prompt `obtain|use|give|lose`), and loss a mismatch (I-1, [B-206](#b-206--lost-is-handled-like-destroyed-21-builds-state-lost-facts)). If 2.1's wording changes, only the `.sql` files change.

### B-202 · Marker exemptions: dead_acts and two_places skip flashback/dream/vision; the other two do not

- **Date:** 2026-10-16 · 2.3 · commit `35a33ca` · notes decision 4
- **Choice:** `dead_acts` skips flashback, dream and vision scenes (the brief). `two_places` also skips them, because 2.2 gives a dream or vision scene the base scene's `story_seq`, so it can share a seq with a scene elsewhere. `knowledge_order` and `prop_provenance` do not skip (a flashback that refers to a secret learned later is still a contradiction), matching `eval/synthetic/rules.py`.
- **Consequence:** the reviewer accepted the dream/vision grounds and called the flashback exemption in `two_places` weakly grounded (not in the spec); recorded as a doc correction.

### B-203 · `two_places` orients a pair by screen order, so it is flagged once, in the later episode

- **Date:** 2026-10-16 · 2.3 · commit `35a33ca` · notes decision 5
- **Choice:** the claim is the later scene in screen order (episode, scene); the earlier presence is cited as `fact/`. The data-model example uses `a.id < b.id`.
- **Consequence:** a pair lands in one episode's report. Within an episode the order uses `scene.id`, which equals script order only because ingest inserts in order (review M-2, deferred).

### B-204 · The re-check re-runs the rule's SQL and compares only the claim line

- **Date:** 2026-10-16 · 2.3 · commit `35a33ca` · notes decision 7
- **Choice:** Stage 5 step 2 re-executes the same rule file against the live connection and passes while the claimed line is still a row; it does not compare the cited other fact, because fact ids churn on re-extraction (R13).
- **Consequence:** one whole-episode query per flag (about 0.05 s); a per-line parameter is the upgrade if flags get many. The re-check also passes if the line is still a row for another reason (review M-3, ratify); the evidence step covers a retracted cited fact on a fresh timeline (7 retract tests).

### B-205 · The oracle-facts loader lives in `eval/exp/layer1_oracle.py`, tagged `PLOT-L1`

- **Date:** 2026-10-16 · 2.3 · commits `35a33ca`, `3aa1594` · notes decision 8, review M-6
- **Context:** the brief asks for an oracle benchmark, and no deliverable owns that file.
- **Choice:** 2.3 writes it outside its ownership list (recorded); 2.2B / 2.1B import `build_store`, `consolidate`, `run_rules`. MLflow tag `exp=PLOT-L1`, not EXP-007, so EXP-007's tables stay clean. After review its `consolidate()` is documented as a stand-in for 2.1's consolidation.
- **Consequence:** EXP-007 inherits this stand-in's semantics; the benchmark cannot see a mismatch with 2.1's real consolidation (as I-1 showed).

### B-206 · `lost` is handled like `destroyed`; 2.1 builds `state: lost` facts

- **Date:** 2026-10-16 · 2.3 (and 2.1) · commit `3aa1594` (2.3 side) · **Controller ruling** on review I-1
- **Context:** in 2.1's consolidation a `lost` state or a `lose` / `drop` holds event started no fact, so the prop rule (which reads events of active facts) could never fire "after lost"; only `destroyed` worked. The reviewer offered two fixes: read loss events directly in the rule, or have 2.1 keep loss as a fact.
- **Choice:** 2.1 builds `state: lost` facts from lose/lost/drop events; 2.3 treats `lost` exactly like `destroyed` and the oracle loader gains `--gone-as lost` (variant `oracle-facts-lost`). Fixed in the same round: `after_gone` uses the latest loss before the use (I-2).
- **Consequence:** both oracle variants score 1.00 on 3 seeds; 2.1's working tree emitted `state: lost` at re-review time, but the rule was not run end to end on 2.1's output in 2.3.

## 2.4 Source-target cue alignment and the localization sync/term checks

### B-207 · Cue alignment fits one line per track by onset coincidence, then measures overlap on that line

- **Date:** 2026-10-16 · 2.4 · commit `fa1f18c` · D-24-1
- **Context:** plain temporal overlap on raw times fails on exactly the tracks `loc.drift` and `loc.offset` must catch; rank-based pairing locked onto a line one cue off under splits and merges, and a shifted rank search got 0 of 916 links on a 900-cue stress track ([journal](journal.md#2026-10-16--24-cue-alignment-rank-pairing-failed-on-splits-and-merges-onset-coincidence-replaced-it), [C-30](experiments.md#c-30--cue-alignment-rank-pairing-vs-shifted-rank-pairing-vs-rank-free-onset-coincidence)).
- **Options:** (a) overlap on raw times; (b) rank pairing + Theil-Sen; (c) rank pairing over -5..+5 shifts; (d) rank-free onset cross-correlation by FFT over slope x offset, then nearest-start + Theil-Sen rounds. **Choice:** (d), plus a "same timing" alternative start that wins ties (found on a 5-cue track where the coarse search reported +29 frames on an identical track).
- **Consequence:** a drifted track is aligned "corrected"; `Alignment.fit` is what drift/offset classify. Ceilings marked `ponytail:` in `cue_align.py`: one line per track (no mid-episode re-sync), slopes within +-30 %, offsets within +-60 s.

### B-208 · Links are persisted by the stage; the checks recompute them

- **Date:** 2026-10-16 · 2.4 · commit `fa1f18c` · D-24-2
- **Choice:** `cue_align.stage` writes `subtitle_cue.aligned_source_cue_ids` (`[]` = aligned to nothing, NULL = never aligned); the checks recompute alignment from the Timeline (`aligned()` memoises the last 16 timelines), because the Timeline carries no links and recomputing is deterministic and cheap. **Consequence:** the column is for other consumers (UI, 2.7, and later `loc.term`'s show-wide standard, [B-213](#b-213--observed-standard-over-the-whole-show-recomputed-every-run)); both come from `align`, so they cannot diverge.

### B-209 · drift and offset require the picture (**Superseded** by B-210)

- **Date:** 2026-10-16 · 2.4 · commit `fa1f18c` · D-24-3
- **Context:** without a picture the timeline's rate is an assumed 24, so the drift cause and the frame counts would be invented. **Choice:** both checks required the picture and were reported in the pipeline's `skipped` list without one; side effect: 2.0's script + subtitles integration tests stayed unchanged.
- **Superseded:** the review (I-2) pointed out the activation matrix marks the picture optional for timing and that drift is a relative measurement; see [B-210](#b-210--drift-and-offset-run-without-a-picture-and-say-less).

### B-210 · drift and offset run without a picture and say less

- **Date:** 2026-10-16 · 2.4 fix round · commit `313ccd0` · review I-2
- **Context:** a subtitles-only delivery, the common localization QC case, got no sync check at all under B-209.
- **Options:** (a) drop `Input.PICTURE` and degrade; (b) ask the user to keep B-209. **Choice:** (a). Without a picture the slope is matched against the ratio of every ordered pair of `timing.sync_rates` (25/24 → "timing for 25 fps material read as 24 fps"), confidence 0.95 (0.99 with a probed rate, 0.90 when nothing matches); the offset is stated in seconds only ("Shift every cue by -0.500 s"). A timeline "has a picture" when it has shots.
- **Consequence:** with a picture nothing changes. Near-equal ratios (24/23.976 and 30/29.97 are both 0.1001 %) mean the cause can name one of several pairs; on an exact tie only the first is named (re-review M-a). A run with media whose shot stage failed is treated as "no picture" (M-d; the flag text says so). The doc correction drafted under B-209 was withdrawn.

### B-211 · loc.term matching rules

- **Date:** 2026-10-16 · 2.4 · commits `fa1f18c`, `313ccd0` · D-24-4, review M-3 and M-6
- **Choice:** content words must form the phrase (same order, same gaps); inflection only for common nouns, judged from the *source* surface (no capitalised content word), both stems >= 5 letters without accents, ending 1-3 letters; an accent alone is a misspelling; near miss = rapidfuzz `ratio` >= 75 (>= 85 under 5 letters), confidence 0.92; approved rendering missing 0.80; observed standard dropped sporadically 0.55 (suppressed, below 0.70); a near miss of an observed standard 0.85; groups of more than 2 cues capped at 0.65. Thresholds in `config/languages/_base.yaml term:`; confidences are module constants (tier policy, not language data). Fix round: the loose source-side match is for common nouns only ("Wren" is not mentioned by "wrench").
- **Why 0.80 for a missing approved rendering** although a pronoun in its place is the same ambiguity that sets the observed case to 0.55 (M-6): the glossary is binding (an approved term is an instruction, an observed name only a habit). Reviewable tier, not `must_review`.
- **Consequence:** the set-based version's recall 0.88 on ToS fr seed 1 and the false passes `Thomas`/`Sintell` are gone; German nouns are no longer misread as names ([journal](journal.md#2026-10-16--24-locterm-locshot_change-locdrift-and-locoffset-what-each-check-does)).

### B-212 · Observed standard per episode, names kept verbatim only (**Superseded** by B-213)

- **Date:** 2026-10-16 · 2.4 · commit `fa1f18c` · D-24-5
- **Choice:** with no approved rendering, the standard was the name kept verbatim in >= 60 % of >= 3 groups of the current episode; `term.stage` wrote `observed_rendering` aliases with the episode's count, overwritten each run. A translated name had no standard (left to Phase 3).
- **Superseded:** the review (I-3) showed the spec's own example ("Wren" rendered "Reyezuelo" in E3) was undetectable inside E3; see [B-213](#b-213--observed-standard-over-the-whole-show-recomputed-every-run).

### B-213 · Observed standard over the whole show, recomputed every run

- **Date:** 2026-10-16 · 2.4 fix round · commit `313ccd0` · review I-3
- **Choice:** other episodes are read from the store (target cue text + the source cues in `aligned_source_cue_ids`); the current episode from its Timeline. A one-word name's rendering is the target word that best singles out the cues mentioning it (share of mentions carrying it minus its share of other cues, >= 0.5), a name kept verbatim winning when it qualifies; a multi-word name is its own standard. Standard = that rendering carries >= 60 % of >= 3 mentions over the show. An episode carrying 0 % against >= 90 % elsewhere (a switch) is flagged at 0.80 per mention; a sporadic miss stays 0.55. `term.stage` deletes the observed rows of entries without approved renderings and writes the show-wide count (idempotent).
- **Consequence:** the doc example gives 5 flags at 0.80; alone, E3 gives none. Ceilings (`ponytail:`): translated standards for one-word names only; one (source cues, target cue) pair per target cue; the first episode of a run sees only episodes aligned by earlier runs (run again to converge). Re-review M-b: an entry approved in `es` but not in `fr` keeps a stale `fr` observed row.

### B-214 · Native labels for shot_change come from the clean run and are a regression guard, not truth

- **Date:** 2026-10-16 · 2.4 · commits `fa1f18c`, `313ccd0` · D-24-6, review ⚠️ item 2
- **Context:** the official subtitles are not cut-aware (13 of 26 Sintel cues and 40 of 76 ToS cues per language near a cut), so raw precision against planted labels only is 0.12 / 0.03. **Choice:** variant `regression-<title>` labels every flag the check raises on the clean copy as native (SELF-LABELLED, untriaged); `raw-<title>` scores without them and is the precision figure. **Consequence:** the regression variant's 0.94 / 0.99 shows only that the injections add little noise; there is no honest precision for `loc.shot_change` until natives are hand-triaged; the cuts themselves are detector output (EXP-002).

### B-215 · The ToS `it` offset injection runs in-process

- **Date:** 2026-10-16 · 2.4 · commit `fa1f18c` (driver), `313ccd0` · D-24-7
- **Context:** 2.9A put the ToS offset injection on `it`, which has no readability rule pack (not an MVP language), and the store pipeline needs one. **Choice:** the benchmark driver runs Drift/Offset on `it` in-process; proposal to 2.9A: move whole-track injections to es/fr/de or add `config/languages/it.yaml`. Not changed by 2.4 (not its files).

### B-216 · shot_change passes an out point at cut - 2 .. cut and flags points on either side of a cut

- **Date:** 2026-10-16 · 2.4 fix round · commit `313ccd0` · review I-1 and M-4
- **Context:** the rule pack says cues ending within 1/2 s before a cut extend to it "keeping the 2-frame gap", and readability flags gaps under 2 frames, so the compliant out point is cut - 2; the first version flagged it.
- **Choice:** `ShotChange` reads `min_gap_frames` from the readability pack and does not flag an out point 0..`min_gap_frames` frames before a cut. Points are flagged on either side of a cut (M-4): the doc is directional (in points after a cut, out points before); the line-220 example supports out-after; in-before is this build's reading of "1-11 frames from a cut" and of the injector's labels (narrowing would drop planted labels such as Sintel seed 2's "in-point 1 frames before the cut").
- **Consequence:** clean copies 39 → 33 (Sintel) and 121 → 115 (ToS) flags; the pair `(100, 238), (240, 300)` raises no shot_change and no readability flag. An out point at cut - 1 passes shot_change while readability flags the 1-frame gap (M-e): the two checks stay consistent. The 2.9A injector had to stop planting cut - 1 / cut - 2 out points ([B-218](#b-218--24-follow-ups-assigned-to-w-int)).

### B-217 · The benchmark driver lives in `eval/exp/loc_bench.py` and runs at a committed SHA

- **Date:** 2026-10-16 · 2.4 fix round · commit `313ccd0` · review I-4
- **Context:** round 0's driver was in the git-ignored workspace and its MLflow runs carried another deliverable's commit tag with uncommitted 2.4 code. **Choice:** commit the driver with a unit test (scoping, native labels), its own stub Plan, no import from tests; re-run all 12 runs (`exp=2.4r1`); cite the runs. **Consequence:** `nip eval compare --exp 2.4r1 --md --tracking-uri sqlite:///data/mlflow/mlflow.db` reproduces the table; the round-0 runs are superseded (soft-deleted in W-int).

### B-218 · 2.4 follow-ups assigned to W-int

- **Date:** 2026-10-16 · 2.4 complete · **Controller ruling**
- **Choice:** the 2.9A injector fix (never plant a compliant cut - 1 / cut - 2 out point) and deleting the stale `exp=2.4` MLflow runs go to W-int, not back to 2.4 (`eval/injectors/**` is 2.9A's). **Consequence:** done in `be494b4` and the W-int MLflow cleanup; Sintel shot_change recall 0.83 → 1.00 ([journal](journal.md#2026-10-16--24-follow-up-in-w-int-the-injector-stops-planting-a-compliant-out-point)).

## 2.5 Speech-to-text and script-to-transcript alignment

### B-219 · faster-whisper's own audio decoder is bypassed; nip reads a 16 kHz wav

- **Date:** 2026-10-16 · 2.5 · commit `bd74e53` · notes journal "faster-whisper on the Windows host"
- **Context:** faster-whisper 1.2.1's `decode_audio` passes `metadata_errors` to `av.open`, which PyAV 19.0.1 (what uv resolved) rejects. **Options:** pin `av<17` (moves the shared lock) or bypass. **Choice:** ffmpeg writes 16 kHz mono PCM16; `read_wav()` (stdlib `wave` + numpy) passes a float32 array. **Consequence:** PyAV never runs; a smaller change than a pin.

### B-220 · Laptop ASR default is `faster-whisper-large-v3-turbo-int8`

- **Date:** 2026-10-16 · 2.5 · commits `bd74e53`, `fa47838` · proposal 2.5-1
- **Context:** [EXP-003](experiments.md#exp-003--speech-to-text-whisper-large-v3-vs-large-v3-turbo). Under every equal-config no-VAD arm turbo's sub+del is at or below large-v3's; it is 2.3x (novad-hst) to 3.2x (fb-p50) faster and needs about half the VRAM. The WER bar (within +1.0 point) is met at `fb-p50` (-1.2) and `novad-hst` (+0.2), not under plain `fb` (+4.3).
- **Choice:** turbo for the laptop and the workstation default; large-v3 stays selectable with the same decode settings. **Consequence:** `timeline.asr.variant` = turbo; English only was measured. W-int found the planner picks large-v3 on the laptop without a pin, so `nip run` pins asr to this variant unless `NIP_PIN_ASR`.

### B-221 · Decoding: no VAD, temperature fallback, `min_prob 0.5` (**Superseded** by B-222 for the fallback and the filter)

- **Date:** 2026-10-16 · 2.5 fix round · commit `fa47838` · proposal 2.5-2
- **Context:** VAD on mis-timed segments by up to 234 s ("I have failed." at 211.75 s instead of 445.85 s); temperature 0 lets large-v3 loop. **Choice:** `vad: false`, fallback tuple 0..1.0 for every variant, `min_prob 0.5`; `decode_by_variant` supported. **Cost stated:** non-deterministic transcripts (WER SD up to 0.018), turbo RTF 0.0219 vs 0.0139, a transcript cache needed for reproducible re-runs. Revisit triggers: a film with continuous music under quiet dialogue (0.5 tuned on 2 films); the unexamined cause of the VAD mis-timing (probably faster-whisper 1.2.1's chunk-timestamp restore with array input and word timestamps, not VAD as such).
- **Superseded:** the re-review showed the fallback changes nothing measurable for turbo on these films (ToS transcripts byte-identical); `vad: false` stays. See [B-222](#b-222--asr-decoding-default-is-the-deterministic-novad-hst-arm).

### B-222 · ASR decoding default is the deterministic `novad-hst` arm

- **Date:** 2026-10-16 · W-int, after the 2.5 re-review · commit `3d66622` · **Controller ruling**
- **Context:** the 2.5 re-review (N-1): `fb-p50` and `novad-p50` turbo transcripts of ToS are byte-identical; the WER gap is Sintel insertions in non-dialogue regions; `novad-hst` is equal footing and meets the bar.
- **Options:** (a) `fb-p50` (lowest WER 0.543, non-deterministic, RTF 0.0219); (b) `novad-p50` (deterministic, WER 0.574); (c) `novad-hst` (deterministic, WER 0.606 vs large-v3 0.604, sub+del 0.115, RTF 0.0161). **Choice:** (c): turbo, `temperature: 0.0`, `hallucination_silence_threshold: 2.0`, `min_prob: 0.0`, `vad: false`.
- **Consequence:** a transcript is the same every run (WER SD 0), so it is cacheable and re-runs are reproducible; it also matches the docs' rule "model calls use temperature 0 unless the experiment is about sampling". Cost if wrong: a rare confident repetition loop is not retried. The fallback tuple remains available per variant through `decode_by_variant`. EXP-004's token default is unchanged (0.676).

### B-223 · Token-level alignment is the default, with a 0.3 s first-word cap

- **Date:** 2026-10-16 · 2.5 · commit `bd74e53` · proposal 2.5-3
- **Context:** [EXP-004](experiments.md#exp-004--script-to-transcript-alignment-token-level-monotonic-vs-rapidfuzz-line-level): token 0.68 vs line 0.51 within +-12 frames (with the cap), 0.46 vs 0.37 without. Whisper's first word after silence starts 0.1-0.7 s before the audible onset. **Choice:** `timeline.align.variant: token`, `first_word_cap_s: 0.3` (a line starts at `max(f_in, f_out - 0.3 s)` of its first word), `min_match: 0.5`; the rapidfuzz line variant stays selectable. **Consequence:** the 95 % bar is not met; reaching it needs hand-marked starts and an ASR that catches short exclamations.

### B-224 · `not_in_cut` needs at least 8 unplaced dialogue words

- **Date:** 2026-10-16 · 2.5 · commit `bd74e53` · proposal 2.5-4
- **Context:** a missed one-line scene is far more likely an ASR miss than a scene cut from the edit, and `not_in_cut` hides a scene from screen-order checks (Sintel had 2 of 10 scenes wrongly `not_in_cut`). **Choice:** `NOT_IN_CUT_WORDS = 8` and no anchored line; shorter scenes stay `in_cut=True` with `frames` None unless they can share a gap between anchored neighbours; such scenes are labelled "(unplaced)" on the Timeline (review I-3, `0440e1d`). **Consequence:** a scene moved in the edit still looks `not_in_cut`, because alignment is monotonic in script order; detecting moves needs a second, non-monotonic pass (not built). In-cut scenes before the first or after the last anchored scene get no frames (review M9).

### B-225 · EXP-004 ground truth: derived as-broadcast scripts, labels outside `eval/labels/`

- **Date:** 2026-10-16 · 2.5 · commit `bd74e53` · **Controller ruling** (labels location; R5 from [B-120](decisions.md#b-120--phase-2-plan-rulings-r1-to-r15-adopted))
- **Context:** no hand-marked line starts exist; Sintel's script covers the first minute and ToS's is subscriber-only (R5). `eval/labels/` is reserved for Label-format benchmark files, and 2.9A's `test_committed_labels_validate` scanned 2.5's JSONL there. **Choice:** derive one Fountain line per official-en-SRT cue and label its start (agent, `basis: srt-cue-start`) plus 3 pairable lines of the real Sintel script; store them in `eval/exp/exp004_labels/`. **Consequence:** EXP-004 measures agreement with subtitle timing, not speech onset; the 3 real-script labels reuse cue starts already in the Sintel set (102 distinct targets in 105, review M2).

### B-226 · Timeline stages type the episode with a Protocol instead of importing `nip.pipeline`

- **Date:** 2026-10-16 · 2.5 fix round · commit `051534b` · controller note on layering
- **Context:** `timeline.asr` / `timeline.align` imported `nip.pipeline` (timeline → pipeline → agents), breaking `lint-imports` and reaching `nip.agents.localization` from `nip.runtime.clients.asr`. **Choice:** a `StageEpisode` Protocol (conn, s3, episode, episode_id, plan, `unit(...)`) in `nip/timeline/asr.py`, which `EpisodeRun` satisfies. **Consequence:** `lint-imports` 7 kept, 0 broken; `mypy src` clean.

### B-227 · EXP-003 logs substitutions+deletions and per-film S/D/I next to WER

- **Date:** 2026-10-16 · 2.5 · commits `bd74e53`, `0440e1d` · proposal 2.5-6
- **Context:** R6 (official SRT as reference) puts the credits song and shouts the SRT omits into insertions, so absolute WER is misleading (Sintel WER above 1). R6 assumed the inflation is equal for both variants; under temperature 0 it was not (large-v3 loops). **Choice:** log `sub_del_rate`, inserted-word counts and `sub_/del_/ins_<film>`; read WER next to them.

### B-228 · No transcript spans on the Timeline yet

- **Date:** 2026-10-16 · 2.5 · commit `bd74e53` · proposal 2.5-5
- **Choice:** `transcript_segment` is persisted, but the Timeline gets scene spans only (no `asr` or line spans); whether checks need `{ep}/asr/{id}` or `{ep}/line/{id}` spans is left to W-int / later checks.

## 2.6 OCR channel and Presidio recognizers

### B-229 · The `ocr` slot uses RapidOCR (ONNX Runtime) with PP-OCRv6 medium; the catalog id `pp-ocrv6-medium` is kept

- **Date:** 2026-10-16 · 2.6 · commit `9c3bf5a` · DP-2.6-1
- **Context:** `paddlepaddle-gpu` 3.4.0 runs alone (5.24 kf/s) but cannot be locked beside torch 2.13.0 on Linux (`nvidia-nccl-cu13` 2.29.7 vs 2.30.7) and clashes on Windows (cuDNN 9.15 vs 9.20, duplicate OpenMP) ([journal](journal.md#2026-10-16--26-paddleocr-beside-torch-three-conflicts-then-rapidocr)).
- **Options:** (a) paddle in the same env (cannot lock); (b) paddle in a separate OCR image/venv (works, about 4x faster, adds a second image and Serve app env); (c) RapidOCR with the same model family as ONNX. **Choice:** (c), one environment.
- **Consequence:** 1.29 kf/s and 1,569 MiB VRAM delta on the laptop ([C-32](experiments.md#c-32--ocr-backends-on-sintels-398-keyframes-paddleocr-gpu-vs-rapidocr-variants)); the catalog's `family` and `vram_gb` needed changing (done by 2.close in `d2a8fa3`: `rapidocr`, 1.6). Revisit (separate paddle image for the actor) if EXP-008 shows OCR time matters.

### B-230 · OCR detection on the GPU, recognition on the CPU

- **Date:** 2026-10-16 · 2.6 · commit `9c3bf5a` · DP-2.6-2
- **Context:** the CUDA recognizer took 5.3 s vs 0.5 s on CPU for 30 keyframes (variable line widths → new shapes); conv-algo search settings and padding did not help ([C-33](experiments.md#c-33--onnx-runtime-cuda-detector-and-recognizer-where-each-runs)). **Choice:** two ONNX Runtime sessions from one RapidOCR config, det on CUDA, rec on CPU (`RapidOcrBackend(cuda=True)`). **Consequence:** relies on the private `RapidOCR._load_det_model()` plus a config mutation; a rapidocr upgrade that loads eagerly would silently put rec back on CUDA (review M-5, deferred). Revisit with fixed-shape ONNX or CUDA graphs.

### B-231 · The CPU `onnxruntime` is excluded from the lock

- **Date:** 2026-10-16 · 2.6 · commit `eafce85`
- **Context:** `rapidocr` depends on the CPU `onnxruntime`; it and `onnxruntime-gpu` own the same `onnxruntime/` directory and the CPU build overwrote the GPU one, so CUDA never registered (0.47-0.60 kf/s instead of a GPU path). **Choice:** `[tool.uv] override-dependencies = ["onnxruntime; sys_platform == 'never'"]`. **Consequence:** `pip check` in the image reports "faster-whisper 1.2.1 requires onnxruntime, which is not installed"; faster-whisper needs it only for Silero VAD, which is off. The same class of clash exists for `opencv-python-headless` beside `opencv-python` (review M-3, harmless while both are 5.0.0.93).

### B-232 · Fiction-reserved phone numbers are matched on the national significant number

- **Date:** 2026-10-16 · 2.6 · commit `9c3bf5a` · DP-2.6-3
- **Context:** D-026 names "an anchored 555-01xx pattern"; Presidio's regex allow-list is `re.search` over free text. **Choice:** per-region `fullmatch` patterns in `config/clearance/fiction_phone_ranges.yaml` run on `str(national_number)`, so "(212) 555-0142", "212.555.0142" and "+1 212 555 0142" behave the same. NANP `\d{3}55501\d{2}`; GB Ofcom drama ranges ([B-239](#b-239--gb-drama-ranges-from-a-secondary-source-of-ofcoms-table-unverifiable-blocks-removed)); ES/DE/FR none (every number there is a candidate, failing toward flagging). **Consequence:** the NANP rule is keyed by region US/CA, not country code 1 (review M-1); `reserved()` re-parses with the first region that yields a valid number (M-2).

### B-233 · 555-0100..0199 is fiction-reserved under every area code

- **Date:** 2026-10-16 · 2.6 · commit `9c3bf5a` · DP-2.6-4 · **Controller ruling**
- **Context:** the 2.6 brief said "(212) 555-0123 is a candidate"; D-026 and architecture.md reserve 555-0100..0199 under any area code. **Choice:** the documented rule; the ledger records the brief's example as the controller's error. (212) 555-0123 is not a candidate; (212) 555-0223 and (617) 482-9154 are. **Consequence:** if legal wants area-code-qualified numbers flagged, change `national` in the yaml. Known gap: bare 7-digit numbers are not detected by libphonenumber for US.

### B-234 · Reserved domains are filtered in code

- **Date:** 2026-10-16 · 2.6 · commit `9c3bf5a` · DP-2.6-5
- **Choice:** `example.com/.net/.org`, `.example`, `.test`, `.invalid`, `.localhost` and their subdomains (list in `recognizers.yaml`) are removed from URL and email candidates and from GLiNER org spans on those hosts, not through Presidio's allow-list.

### B-235 · `TextScanner` takes one language; fictional and deny-listed brands are constructor arguments

- **Date:** 2026-10-16 · 2.6 · commit `9c3bf5a` · DP-2.6-6
- **Choice:** `candidates(detections, lang)` scans in the episode's source language only (recognizers are language-agnostic apart from context words); `fictional=` (bible brands/orgs, normalized, token-boundary match) and `deny_brands=` (clearance-log items, 2.7) are constructor arguments; a seed list of 20 real brands lives in `recognizers.yaml`.

### B-236 · Presidio without GPL spaCy models; GLiNER carries names; GLiNER with its own word splitter and no extra weights

- **Date:** 2026-10-16 · 2.6 · commit `9c3bf5a` · notes journal "Presidio setup", "GLiNER"
- **Choice:** `SlimSpacyNlpEngine` with MIT `en_core_web_sm` / `de_core_news_sm` and `spacy.blank` es/fr, setting the private `_blank_languages` directly (the public path would load GPL `es_core_news_sm`); no spaCy NER recognizer at all, organizations and names come from GLiNER; GLiNER's `stanza` splitter replaced by its whitespace/punctuation splitter; `snapshot_download(ignore_patterns=[onnx/*, model.bf16*, model.fp16*, *.png])` avoids 3.9 GB of unused copies. **Consequence:** private-API dependence under `>=` pins (review M-5); the snapshot has no `revision=` pin, although the license policy rejects a later non-commercial gliner-x release (review M-6, deferred).

### B-237 · gliner's cap `transformers<5.17.0` is accepted for now

- **Date:** 2026-10-16 · 2.6 fix round · commit `fa95853` (decision recorded) · DP-2.6-9 · vLLM smoke: **Controller ruling**
- **Context:** `gliner==0.2.29` declares `transformers<5.17.0,>=4.51.3`; the whole lock (win32 and Linux, including the vLLM image's `nip` install) moved transformers 5.20.0 → 5.16.1, huggingface-hub 2.2.0 → 1.33.0, numpy on win32 2.5.4 → 2.3.5. vLLM 0.30.0's declared requirements are still met.
- **Options:** (a) accept; (b) a uv override forcing transformers >= 5.17 (untested by gliner); (c) isolate GLiNER (own env or ONNX path). **Choice:** (a): GLiNER is the only `ner` backend and the laptop model's config classes (`qwen3_5`, `qwen3_5_moe`, `gemma4`, `ministral3`) exist in 5.16.1. The controller ruled that W-int re-runs the vLLM image smoke.
- **Consequence:** catalog models needing transformers >= 5.17 (Qwen3.8-27B, Qwen3.6-35B-A3B unverified) cannot load in this environment; sentence-transformers and 2.8's embedders are frozen at 5.16.1. The W-int smoke passed (also openai 3.31.0 → 3.3.0 in the image). Revisit when gliner lifts the cap or a model needs a newer transformers; first try (b) with the `ner` tests.

### B-238 · Plate patterns are case-sensitive, allow one space, and exclude caption words by name

- **Date:** 2026-10-16 · 2.6 fix rounds · commits `fa95853`, `3c1a5de` · review I-1, re-review N-1
- **Context:** Presidio's default `IGNORECASE` made "upper case only" void and captions matched (I-1); the first fix dropped the spaced forms that real plates use (N-1). Shape alone cannot separate "ABC 1234" from "MAY 1985".
- **Choice:** `global_regex_flags=re.DOTALL | re.MULTILINE`; US/DE allow one space; negative lookaheads list months and caption words before "ABC 1234", units after "123 ABC", function words before German "B AB 1234" (which needs 3-4 digits when spaced). **Consequence:** 16/16 plate probes match; 26/50 caption-shaped probes still match ([C-34](experiments.md#c-34--plate-regexes-over-three-rounds-captions-vs-real-plates)); the error is on the over-flag side; plates stay "to validate" (EXP-019). Re-review 2 recommends not growing the stop-lists by hand and, if needed, a score tier (bare shape 0.4, context-word lifted).

### B-239 · GB drama ranges from a secondary source of Ofcom's table; unverifiable blocks removed

- **Date:** 2026-10-16 · 2.6 fix rounds · commits `fa95853`, `3c1a5de` · review I-2, re-review M-b
- **Context:** the first list (written from memory) had 7 ranges; Ofcom's page returned HTTP 403 to automated fetches. **Choice:** the ranges in britishtelephones.com's reproduction of Ofcom's table (read 2026-10-16): 0113-0118, 0121, 0131, 0141, 0151, 0161 `496 0000-0999`; 020 `7946 0000-0999`; 0191 `498 0000-0999`; 028 `9649 6000-6999`; 029 `2018 0000-0999`; 01632 `960000-960999`; 07700 `900000-900999`; 08081 `570000-570999`; 0909 `879 0000-0999`; 03069 `990000-990999`. Coventry 024 7618, Portsmouth 023 9288 and Southampton 023 8049 6 (reviewer recollection, in no source) were added as `# unverified`, then removed. **Consequence:** a real number in those three blocks is a candidate (fails toward flagging); Ofcom's own page is still unread.

### B-240 · OCR and NER clients read `NIP_SERVE_URL`

- **Date:** 2026-10-16 · 2.6 · commit `9c3bf5a` · DP-2.6-7
- **Context:** a 2.0 review minor relayed by the controller: the clients hard-coded port 8000. **Choice:** base URL through `clients.llm.SERVE_URL`.

### B-241 · OCR URL cleanup joins a spaced dot only before a known TLD; ccTLDs only in lower case

- **Date:** 2026-10-16 · 2.6 · commits `9c3bf5a`, `fa95853` · D-026 cleanup, review M-9
- **Context:** a general ". followed by a 2-letter word" rule made hosts of "Hello. It works" and "Dolor. Es muy". **Choice:** after a space-dot only gTLDs or known ccTLDs may follow, ccTLDs in lower case only; after "x. " only gTLDs. **Consequence:** "Hola . Es verdad" is no host; upper-case spaced hosts with a ccTLD ("SHOP .DE") are missed (re-review M-a, accepted).

### B-242 · GLiNER spans that overlap a structured finding are not second findings

- **Date:** 2026-10-16 · 2.6 · commit `9c3bf5a`
- **Context:** real GLiNER tagged "+1 415 555 0100" as `address` and URL hosts as organizations. **Choice:** an address candidate must contain a word of at least 3 letters; an address/brand span overlapping a phone/URL/email span (fiction-safe ones included) is dropped; the domain inside an email is not a URL finding.

## 2.7 Clearance matching, occurrences, prominence, clearance CSV, clr.* flags

### B-243 · Identifiers match exactly, names fuzzily; the strictest status wins

- **Date:** 2026-10-16 · 2.7 · commit `4c131c1` · DP-2.7-4 in the 2.7 notes
- **Context:** architecture.md's matching normalizes "case, punctuation, known variants" but does not say how close a match must be.
- **Options:** fuzzy matching for every kind; exact for every kind; exact for identifiers, fuzzy for names. **Choice:** phones, plates, e-mails and URLs match exactly after normalization; addresses and brands by token containment (>= 2 tokens) or `rapidfuzz.ratio >= 90`. An item whose `scope` (`S01E03`, `S01E01-S01E08`, comma lists) does not cover the episode does not apply. With several matching items, denied > pending > cleared.
- **Consequence:** a one-character difference in a phone number or plate is a different number, so a wrong "cleared" cannot hide a real exposure. The other side of that risk (an OCR slip of a pending/denied identifier becoming `unknown`) was closed by [B-250](#b-250--a-one-edit-ocr-slip-of-a-pendingdenied-phone-or-plate-escalates-to-must_review).

### B-244 · Pending/denied are `must_review` and cleared `suppressed` whatever the confidence

- **Date:** 2026-10-16 · 2.7 · commit `4c131c1` · brief (the one Phase 2 edit allowed in `agents/base.py`), extends [B-064](decisions.md#b-064--emit-enforces-evidence-or-nothing-and-assigns-the-tier)
- **Choice:** `Finding.tier` is an optional override that `emit` uses instead of the confidence tiers. **Consequence:** the system target "pending/denied detected but not shown = 0" holds by construction for exact reads; tests run a pending phone and a denied plate through `emit` at confidences 0.0, 0.01, 0.3, 0.69, 0.7, 0.95, 1.0.

### B-245 · Candidate confidence = OCR confidence x max(recognizer score, certainty floor)

- **Date:** 2026-10-16 · 2.7 · commit `4c131c1` · DP-2.7-2, DP-2.7-11
- **Context:** Presidio scores phones and plates 0.4, so an unlogged real phone number scored 0.38 and was `suppressed` ([journal](journal.md#2026-10-16--27-clearance-matching-occurrences-the-clearanceocr-stage-and-the-csv)).
- **Choice:** per-check floors for recognizers that validate their match: phone 0.9 (libphonenumber), e-mail 0.9, URL 0.85. Plates and GLiNER spans keep their own score (plates stay "to validate", EXP-019). `Scan.rows` stores this confidence, not the Presidio score.
- **Consequence:** unlogged phone numbers, e-mails and URLs reach a reviewer; unknown plates stay <= 0.4 and `suppressed` ([B-260](#b-260--unknown-plates-stay-at-their-recognizer-score-and-suppressed)). Not exercised by the benchmark (every injected positive is logged, so its tier is forced).

### B-246 · Occurrences merge by a 2 s gap between keyframe cells; scene boundaries are not used

- **Date:** 2026-10-16 · 2.7 · commit `4c131c1` · DP-2.7-3
- **Context:** architecture.md merges "detections of the same item in consecutive shots of a scene (gap <= 2 s)".
- **Choice:** merge by time gap only (<= 2 s, inclusive, between keyframe cells). Store scenes are script estimates until alignment sets `timeline_source = 'picture'`, and a text that comes back within 2 s across a scene cut is still the same sign. Unknown items group by exact normalized text.
- **Consequence:** review minors M5 (OCR variants of one unknown item, e.g. "Netherlands Film Fund" / "THENETHERLANDSFILMFUND", stay separate occurrences) and M6 (under 1 per shot, two adjacent long shots showing one sign split because cells are capped at 4 s) were recorded as known limits, not changed.

### B-247 · A keyframe span stands for its cell; the flag's claim is the keyframes (**Superseded** by B-248)

- **Date:** 2026-10-16/17 · 2.7 · commits `4c131c1`, `2407222` · DP-2.7-1 (round 0)
- **Context:** the brief's shot-span claim cannot reach IoU 0.3 against 3 to 4 s overlays in 4 to 24 s shots ([C-36](experiments.md#c-36--claim-span-for-an-occurrence-shot-span-vs-keyframe-cell-vs-occurrence-range)).
- **Options:** shot spans (the brief); extend `emit`/verification to accept sub-ranges (outside 2.7's files); keyframe-as-cell. **Choice (round 0):** keyframe-as-cell, `cell_cap_s` = 4 s, keyframe claims with quote + crop, shots as context.
- **Why superseded:** the review (I4) found the width a constant matched to the injector (a label longer than about 13.3 s could never match), the claim differed from the occurrence range the CSV reports, and stored `kf` evidence had ranges a fresh `load_timeline` does not reproduce, so re-verification would drop every clr flag.

### B-248 · The claim is the occurrence's frame range, as a `clr/occ-<hash>` span

- **Date:** 2026-10-17 · 2.7 fix round 1 · commit `f324627` · **Controller ruling** (review I4)
- **Ruling text (progress.md):** clr flag claim = occurrence frame range (as in CSV), not a fixed 4 s window; spec occurrence semantics; re-verifiable. Cost if wrong: lower IoU on long labels, reported honestly.
- **Choice:** the `clearance.ocr` stage adds one span per occurrence to the run's timeline (`clr/occ-<hash>`, kind `clearance_item`, frames = the occurrence's range = the CSV's tc_in/tc_out, text = what was read); that span is the claim. The keyframe is `context` with quote + crop and its single stored frame; shots are `context`. `windows()` and the stretched keyframe spans are gone. The range is the union of the keyframes' cells (cell capped at `cell_cap_s` = 4 s, an evidence-horizon estimate also used for screen time).
- **Consequence:** recall unchanged (1.00 current and dense, 0.50 1 per shot); a unit test shows a 60 s label against a 4 s occurrence (IoU 0.07) does not match. A fresh `load_timeline` lacks the `clr/occ-` span, so re-verification must run `clearance.ocr` first or refs need an occurrence kind; the Phase 2 closeout made `clr/occ-` refs resolve from the store (`5f65199`).

### B-249 · Each occurrence has its own stable ref, so R13 fingerprints separate distinct items

- **Date:** 2026-10-17 · 2.7 fix round 1 · commit `f324627` · review I2
- **Context:** fingerprints use stable refs only (R13); round 0's clr flags carried only `kf` and `shot` refs, so every unknown item on one keyframe set shared one identity (41 of 109 flags in 17 colliding groups per seed, measured by the reviewer).
- **Choice:** `Occurrence.ref` = `clr/occ-` + sha1[:12] of (episode, check, registry item or normalized text, first keyframe). It parses as a `clr/` ref, so `runs.stable_refs` includes it. **Consequence:** 253 flags, 253 fingerprints, 0 colliding ([C-38](experiments.md#c-38--fingerprint-collisions-among-clr-flags-41-of-109-per-seed--0-of-253)). The implementer proposed a real occurrence kind (`occ/{ep}/{id}`) to the refs owner. Later the Phase 2 closeout ruled that the hash use registry-independent fields only (episode, check, normalized first read, first keyframe), commit `ddf6206`.

### B-250 · A one-edit OCR slip of a pending/denied phone or plate escalates to `must_review`

- **Date:** 2026-10-17 · 2.7 fix round 1 · commit `f324627` · **Controller ruling** (review I3)
- **Ruling text:** near-match (<= 1 edit) to pending/denied phone/plate escalates to must_review, because "pending/denied detected but not shown = 0". Cost if wrong: some extra reviews.
- **Context:** with exact matching an O/0, I/1, B/8 slip of a pending/denied plate became `unknown`, at score <= 0.4 (no plate floor), `suppressed`, while still matching the label: detected but not shown. Not observed on this set (OCR read all 32 exactly).
- **Choice:** with no exact in-scope hit, a phone or plate of normalized length >= 6 within Levenshtein distance 1 of a pending/denied item of that kind returns `Match(status=that item's, item, near=True)`; the explanation says "may be the denied item ... (one character different ...)". Exact matching stays for `cleared` and for e-mails, URLs and names.
- **Consequence:** a different number one digit from a pending one is shown as a possible match (accepted by the ruling). Residual (re-review N3, tested, by design): with two logged numbers one digit apart, an exact read of the cleared one that was really a misread of the denied one stays cleared.

### B-251 · EXP-008: keep the 4 s / 2 s keyframe policy as a recorded override of the bar

- **Date:** 2026-10-17 · 2.7 fix round 1 · commit `f324627` (config comment; first recorded in `e464917`) · **Controller ruling**, DP-2.7-9
- **Context:** [EXP-008](experiments.md#exp-008--keyframe-density-for-on-screen-text): shown recall 0.50 / 1.00 / 1.00 for 1 per shot / current / 1 per 1 s, keyframes 302 / 723 / 1,458. The bar ("a denser policy is kept only if recall rises >= 5 points for <= 50 % more keyframes") applied against the sparsest arm rejects both denser arms (+0.50 recall for +139 %; +0.00 for +102 %), so by its text the policy is 1 per shot. Its recall of 0.50 fails the 0.85 MVP recall target for the six `clr.*` checks (evaluation.md).
- **Ruling text (progress.md):** EXP-008 keep 4s/2s as OVERRIDE of the bar (1/shot recall 0.50 < 0.85 MVP). Cost if wrong: +139 % keyframes vs 1/shot.
- **Choice:** `timeline.keyframes` stays at the B-027 policy ([B-027](decisions.md#b-027--keyframe-policy-made-concrete)); `config/pipeline.yaml` says it is an override. The round-0 text that presented this as "per the bar" was withdrawn.
- **Consequence:** +139 % keyframes and, per the notes, +700 % OCR time on the policy frames (1,470 vs 180 s per content hour on the GPU scans). The set favours density (3 to 4 s overlays in long shots); revisit with a set of persistent signage.

### B-252 · EXP-017: keep the dedicated OCR engine (`pp-ocrv6-medium` via RapidOCR)

- **Date:** 2026-10-17 · 2.7 · commit `e778928` · experiment result under the written bar
- **Context:** [EXP-017](experiments.md#exp-017--ocr-engine-vs-reading-text-with-the-vision-model): recall 1.00 for both readers; bar "keep PP-OCR unless the vision model's recall is >= 10 points higher".
- **Choice:** keep `pp-ocrv6-medium` (RapidOCR PP-OCRv6 medium, 2.6's fallback). **Consequence:** the vision model's lower shown-FP count is not counted as an advantage, because 16.1 % of its reads failed on credits cards; it also takes 1.30x the stage seconds and a 156.6 s load to 7.9 GB on the 8 GB card, where the OCR actor needs 1.5 GiB.

### B-253 · Credits and title cards give no GLiNER brand or address guesses

- **Date:** 2026-10-17 · 2.7 · commit `2407222` · DP-2.7-10
- **Context:** GLiNER tagged names, roles and software in the closing credits as organizations / products; shown FPs on seed 1 were 95 (Sintel) and 89 (Tears of Steel) ([C-35](experiments.md#c-35--scanner-rules-on-unlogged-credits-text-shown-false-positives-95--29-and-89--24)).
- **Choice:** a keyframe with >= 8 OCR lines (`dense_frame_lines`, config) gets no GLiNER address/brand guesses (deny-lists, phones, URLs, e-mails and plates still count); a GLiNER person / job-title reading removes an overlapping brand or address; a brand span needs 3 letters ("IT", "CG", "O0" are OCR noise).
- **Consequence:** shown FPs 95 → 29 and 89 → 24 (seed 1). A real brand named only in credits ("Dell Computers") is not flagged unless logged. The rules were written looking at seed-1 flags; the review (I5) called them principled in kind but tuned on the evaluation data in degree. The recall cost on in-scene text-heavy frames (newsstand, storefront row) is not measurable on these films, which have none.

### B-254 · Credits URLs are correct `unknown` flags; precision is reported against injected labels only; junk is dropped by rule

- **Date:** 2026-10-17 · 2.7 fix round 1 · commit `f324627` (natives adjusted in `cda802e`) · **Controller ruling** (review I5)
- **Ruling text (progress.md):** credits third-party URLs are correct `unknown` flags → agent-provisional natives; precision reported vs injected labels only; junk filters by rule, measured on seeds 2-3.
- **Choice:** (a) the injected-run precision is called "precision vs injected labels only"; the 113/h figure is not the spec's noise metric (clean runs with human triage), which stays unmeasured. (b) Rules: the show's own title and the bible's fictional names (whole words) are never clearance items; a brand/address made only of credit words (a trade vocabulary in `recognizers.yaml`) is a credit line; GLiNER reads all-caps OCR lines in title case; GLiNER guesses only on lines read at OCR confidence >= 0.8; brand spans need 3 letters. (c) Measured on seeds 2 to 3. (d) Native labels `eval/labels/exp008/{sintel,tears-of-steel}.native.jsonl` for real web addresses printed in the credits (`accepted_urls.yaml`; OCR fragments l.org, DivX.Inc, Yi.us rejected; injector `clr.native.agent.v1`, `reviewed` false, labeller agent (provisional)); 8 + 5 in fix round 1, **7 + 5 = 12** after `www.sintel.org` (first-party) was removed in fix round 2. Native frames are seed 1's own occurrence ranges (IoU 1 with seed 1's flags by construction; seeds 2 to 3 share the credits frames).
- **Consequence:** final precision 0.21 ± 0.01 injected-only, 0.44 ± 0.01 with natives, recall 1.00 ([C-35](experiments.md#c-35--scanner-rules-on-unlogged-credits-text-shown-false-positives-95--29-and-89--24)). The credit vocabulary was partly extended from these films' credits (farm, servers, bug, fixing, violinist, gold, financial, administration, printing, websites), so it is not independent of the data (re-review N4). Real organizations in credits and sponsor cards were not labelled (the ruling names URLs).

### B-255 · The clearance log is matched before any junk rule

- **Date:** 2026-10-17 · 2.7 fix round 2 · commit `cda802e` · re-review N1
- **Context:** the fix-round-1 rules ran before the log, so a logged `Waffle House` (denied) with a show titled "House" became `fictional` ([journal](journal.md#2026-10-17--27-re-review-a-fix-that-could-hide-logged-items-and-fix-round-2)).
- **Choice:** `match` returns registry hits (exact, in scope) and the one-edit near match first; the fictional / own-title test runs only when nothing in the log matched. In `TextScanner`, deny-list results skip the credit-word, person/role-overlap, fictional-substring and short-noise drops; only the reserved-host test stays. **Consequence:** "fictional" now means unlogged; unlogged look-alikes ("THE HOUSE OF CARDS", "9 Springfield Lane") are still dropped. No benchmark flag changed (0 frames with different candidates).

### B-256 · No NER pin in code; the planner/catalog decides the NER variant

- **Date:** 2026-10-17 · 2.7 fix round 1 · commit `f324627` (the pin was added in `2407222`) · **Controller ruling** (review I6); DP-2.7-5 withdrawn
- **Context:** round 0 pinned the `ner` slot to `gliner-x-base` (`clearance.ner_variant`, one line in `pipeline.current_plan`) because the quality objective picked `gliner-x-large` (catalog 3.7 GiB, never downloaded or measured). The reviewer: an unconditional pin contradicts tech-stack.md ("`gliner-x-large` on big GPUs") and belongs in the catalog/planner.
- **Ruling text:** NER variant from planner/catalog (no unconditional gliner-x-base pin); exercise GPU nip run --in-cluster on Sintel once.
- **Choice:** pin and key removed; `current_plan` pins asr only; 2.7's runs set `NIP_PIN_NER=gliner-x-base` (the documented env mechanism). **Consequence:** all published 2.7 numbers (EXP-008, EXP-017, e2e) were produced with `gliner-x-base`. The Phase 2 closeout measured `gliner-x-large` at 2.6 GiB, kept it as the planner's laptop pick, and scored it on EXP-008's set ([C-54](experiments.md#c-54--ner-ab-on-replayed-ocr-gliner-x-large-vs-gliner-x-base-on-the-exp-008-end-to-end-benchmark)).

### B-257 · `pipeline.py`: two stages and the slot tables, beyond the one sanctioned `add_stage`

- **Date:** 2026-10-16 · 2.7 · commits `4c131c1`, `2407222`, `f324627` · DP-2.7-6, accepted by the **Controller ruling** on review I6
- **Context:** the controller had allowed "the ONE `add_stage(...)` line" for the OCR stage (progress.md, after W-int/W-serve).
- **Choice:** `add_stage("clearance.ocr")` + `add_stage("clearance.csv")`; `STAGE_SLOTS["clearance.ocr"] = Slot.OCR` and `FEEDS["clearance.ocr"] = "clr."` (a skipped OCR slot skips the stage and the clr checks as a recorded gap, as for extraction); `MODEL_SLOTS += (OCR, NER)` (without them the Plan has no OCR decision and the stage silently does nothing); `tests/unit/test_cli.py` dry-run expectation updated.
- **Consequence:** every `nip run` Plan now carries OCR and NER (VRAM budget beside text_llm); the in-cluster run confirmed text_llm still fits on the laptop (context 32768 → 16384, no skipped slots).

### B-258 · Clearance CSV per run and episode, CLI now, API route later

- **Date:** 2026-10-16 · 2.7 · commits `4c131c1`, `e464917` · DP-2.7-8; ruling R11 ([B-120](decisions.md#b-120--phase-2-plan-rulings-r1-to-r15-adopted))
- **Choice:** the `clearance.csv` stage writes `runs/{run_id}/{ep}/clearance_report.csv` (data-model says `runs/{run_id}/clearance_report.csv`; 2.0 already made `report.json` per episode because a run spans episodes). Columns exactly as api-contracts.md. `nip clearance report --show S --episode E [--run run_N] [--out f.csv] [--include-hidden]`; wiring line in `cli.py`: `app.add_typer(clearance_report.app, name="clearance")`. CSV flag ids are keyed by check + best keyframe + quote (`e464917`).
- **Consequence:** `thumbnail_url` is `s3://...` until the API presigns it (4.1). Review minor M4: `--run run_N` recomputes occurrences from today's registry and detections, so a historical run's CSV can show statuses its flags did not have (not changed).

### B-259 · Crop sharpness is stored as a companion `detection` row

- **Date:** 2026-10-16 · 2.7 · commit `4c131c1` · notes ("Smaller findings")
- **Context:** `detection` has no attribute column. **Choice:** a row with `label` = `sharpness` per candidate whose `confidence` holds the Laplacian variance of its crop. **Consequence:** review M3: other readers of `channel='ocr'` confidences see out-of-range values (300+); the proposed fix is an `attrs jsonb` column in a migration 0003 (not done).

### B-260 · Unknown plates stay at their recognizer score and `suppressed`

- **Date:** 2026-10-17 · 2.7 fix round 1 · commit `f324627` · review M7 (stated as a decision in the report)
- **Choice:** no certainty floor for plates (scores <= 0.4); plates are "to validate" by EXP-019. **Consequence:** an unlogged real plate is not shown by default; pending/denied plates are covered by the tier override and the near match.

## 2.8 Scene vector index and hybrid retrieval

### B-261 · The embedder client module is `clients/text_embedder.py`

- **Date:** 2026-10-16 · 2.8 · commit `7a664c1` · **Controller ruling** (carried into the 2.8 brief); D-2.8-1 in the 2.8 notes
- **Ruling text (progress.md):** embedder client module named `clients/text_embedder.py` (matches Slot name so 2.0's generic `_bind` hook works; phase2-plan said `embedder.py`).
- **Consequence:** `serving.actor_class(slot)` imports `nip.runtime.clients.text_embedder` and takes `Actor` with no per-slot code (checked by the reviewer). Deviates from `phase2-plan.md`.

### B-262 · `script_line.speaker text` in migration 0002 holds the raw character cue

- **Date:** 2026-10-16 · 2.8 · commit `7a664c1` · **Controller ruling**; D-2.8-2
- **Ruling text (progress.md):** `script_line.speaker` column added by 2.8 in migration 0002 (2.8 is sole schema owner). Cost if wrong: one more migration.
- **Context:** 2.0's ingest dropped the speaker and 2.1 needs it. **Choice:** the column holds the script's raw cue (e.g. `MAYA`); `speaker_entity_id` stays 2.1's job (entity resolution). `_write_script` fills it for dialogue and parenthetical elements (the one allowed edit to 2.0's writer, 4 lines). **Consequence:** episodes ingested before 0002 keep `speaker = NULL` and re-ingest is a no-op (review minor 4; backfill left to 2.9B). 2.1B later kept cue extensions as written (V.O., O.S.) in this column.

### B-263 · `UNIQUE (scene_id, kind, embedder_variant)` on `scene_chunk`; the writer is an upsert

- **Date:** 2026-10-16 · 2.8 · commit `7a664c1` · D-2.8-3
- **Options:** no constraint and delete + insert (races, duplicates on retry). **Choice:** the database enforces "embed once per variant"; a changed scene is replaced in place. Skipping compares the stored chunk text with the current scene text, not `scene.text_hash` (the reviewer: same semantics, stricter, since speaker and parenthetical text are part of it).
- **Consequence:** a scene replaced on re-ingest must have its chunks deleted or upserted first (the FK); 2.9B-1 deletes `scene_chunk` before `scene`. The constraint's explicit name equals Postgres's default, so the drift test sees no difference.

### B-264 · One HNSW partial expression index per catalog embedder variant, with the variant inlined

- **Date:** 2026-10-16 · 2.8 · commit `7a664c1` · D-2.8-4 and the build findings; resolves the deferral in [B-004](decisions.md#b-004--schema-v1-contains-all-26-tables)
- **Choice:** `((embedding::vector(1024)) vector_cosine_ops) WHERE embedder_variant = '<v>'` for `qwen3-embedding-0.6b` and `-8b` (the 8b one exists although no 8b chunks do, because the catalog lists it); default HNSW parameters (m 16, ef_construction 64); the stub gets no index. The variant is inlined into the query SQL (regex-checked `[\w.-]+`) because Postgres uses a partial index only for a predicate it can prove; every vector query sets `hnsw.iterative_scan = strict_order`; `hnsw.ef_search` is clamped to 1000.
- **Consequence:** a new embedder variant needs a migration. Review minor 5: `schema.HNSW_VARIANTS` duplicates the migration's list and nothing checks catalog `text_embedder` variants are covered (a third variant would run un-indexed and pass the drift test).

### B-265 · Hybrid score = cosine + weight x IDF-weighted entity overlap, weight 1.0

- **Date:** 2026-10-16 · 2.8 · commit `7a664c1` · D-2.8-5
- **Options:** a hard filter on shared entities (misses scenes about the same thing from another angle); reciprocal-rank fusion (no fact weighting); plain Jaccard (a main character shared everywhere counts as much as a secret). **Choice:** cosine plus weight times the IDF-weighted share of the query scene's entities; one SQL candidate query plus a few lines of Python; the IDF needs no entity-kind table. `Filters(kinds, shared_only, episode_ids)` lets a Phase 3 consumer ask for props and secrets only.
- **Consequence:** weight 1.0 was picked from a sweep on 3 planted pairs ([C-39](experiments.md#c-39--scene-retrieval-vector-only-vs-hybrid-vector--entity-overlap)), where the facts are the generator's truth; the reviewer noted 1.0 lets the overlap term dominate the narrow cosine band. Re-sweep with 2.1's real facts. Review minors 1 and 3: `retrieve` reloads the whole show's facts per call and the shared-entity pool is unbounded (fine at 150 scenes, a ceiling for Phase 3 Layer 2).

### B-266 · CPU is the in-process embedding default; the Serve actor uses CUDA

- **Date:** 2026-10-16 · 2.8 · commit `7a664c1` · D-2.8-6
- **Context:** CPU 5.8 to 6.0 scenes/s vs GPU 242.5 to 280.8 on short scenes ([C-40](experiments.md#c-40--scene-embedding-throughput-cpu-vs-gpu-qwen3-embedding-06b)); the GPU is shared with vLLM and a 1.6 GiB actor does not fit next to a resident LLM on the 8 GB laptop.
- **Choice:** `make_embedder(device="cpu")` in process; the Serve `Actor` uses CUDA because the planner decided its placement. **Consequence:** at about 300 tok/s an episode of 60 scenes x about 300 tokens (an assumption, not measured) is roughly a minute on CPU, a season about 10 minutes; revisit if that is too slow.

### B-267 · No instruction prompt; scene text is heading plus `SPEAKER: text`, truncated at 1,024 tokens

- **Date:** 2026-10-16 · 2.8 · commit `7a664c1` · D-2.8-7, D-2.8-8
- **Choice:** Qwen3-Embedding is trained with a query instruction for asymmetric retrieval, but both sides here are scene text (symmetric), so none is used. Scene text = heading, then each element: dialogue as `SPEAKER: text`, parentheticals in parentheses, transitions dropped; `max_seq_length` 1,024 tokens (the model allows 32k). **Consequence:** the longest synthetic scene is 69 tokens, so truncation is untested on real scripts; a longer scene loses its tail.

### B-268 · The index stage is a no-op without a `text_embedder` decision; never a silent stub

- **Date:** 2026-10-16 · 2.8 · commit `7a664c1` · D-2.8-9
- **Choice:** one work unit per episode; without a Plan decision the stage does nothing rather than fall back to the stub (stub vectors in a real database would be wrong). **Consequence:** W-int must put a `text_embedder` workload into the Plan (`current_plan({Slot.TEXT_EMBEDDER: n})`) for it to run.

## 2.9A Injectors, synthetic show, sidecars

### B-269 · The synthetic show is a template generator with truth by construction; a script line is a Fountain element

- **Date:** 2026-10-16 · 2.9A · commit `2e3cb6e` · D-A in `notes/2.9A.md` · implements ruling R2 ([B-120](decisions.md#b-120--phase-2-plan-rulings-r1-to-r15-adopted))
- **Context:** evaluation.md says the show is generated "using the local text model"; an LLM may not fit and gives no exact truth.
- **Choice:** a deterministic template generator. `truth.json` = the model (scenes, lines, facts with quotes, mentions incl. nicknames/descriptions, story_seq/day, markers) plus computed line/scene refs and setup/payoff pairs; predicates `present_at`, `learns`, `references`, `holds` (value.event obtain|use), `state` (value.state dead|destroyed), `setup`, `payoff`. Because the Fountain reader merges consecutive action paragraphs, the generator merges adjacent actions and the line `seq` is the element position ([B-135](#b-135--script_lineseq-is-1-based-within-its-scene)).
- **Consequence:** 2.1/2.2/2.3 can load oracle facts from it; prose is repetitive, and synthetic results are reported separately.

### B-270 · Label conventions per target kind

- **Date:** 2026-10-16 · 2.9A · commit `2e3cb6e` · D-B · applies ruling R12
- **Choice:** cue-level labels (`loc.term`, `loc.shot_change`) carry the cue ref and the cue's frame range in the output file; track-level labels (`loc.drift`, `loc.offset`) carry every cue ref of the track and no frames, kind `subtitle_track`; script labels (`plot.*`) are kind `script_line` with refs = planted line + its scene (+ the paired scene for two_places), no frames; clearance labels are kind `frame_range` with frames only (the overlay window, 72 to 96 frames).
- **Consequence:** `eval.metrics.overlap` matches track labels by any claimed cue ref, script labels by line or scene ref, clearance labels by IoU ≥ 0.3, so 2.7 should flag the occurrence's shot/keyframe range. Labels are written to `<out>/<set>/seed<N>/labels/<title>.jsonl`, not the spec's `eval/labels/<set>/<title>.jsonl` (review M3).

### B-271 · Cleared clearance items are rendered but not labelled

- **Date:** 2026-10-16 · 2.9A · commit `2e3cb6e` · D-C
- **Context:** the sidecar clearance log marks injected items cleared, pending or denied; a cleared item must be hidden, so finding it is not an error.
- **Options:** label everything and mark the status in the description (rejected); label only what should be shown.
- **Choice:** cleared items and negatives (555-0100..0199, RFC 2606 domains/emails, bible-fictional brands) are listed in `<picture>.clr.json`, not in the labels, so 2.7 can test that cleared items are hidden and negatives unflagged without charging a correct system with false negatives.

### B-272 · Clearance text is an overlay plate over a still stretch

- **Date:** 2026-10-16 · 2.9A · commit `2e3cb6e` · D-D and "Tried → switched"
- **Choice:** an opaque dark plate with white text in one of five fixed screen regions for 72 to 96 frames inside a still stretch (frame-to-frame difference under 1.0 gray level for at least 84 frames, [C-41](experiments.md#c-41--low-motion-threshold-for-clearance-overlay-windows)), drawn as Pillow PNGs with ffmpeg `overlay=enable='between(n,a,b)'` rather than `drawtext` (no font-file dependency); bitexact ffmpeg flags.
- **Consequence:** easier to read than a sign in perspective, so OCR numbers from this injector are an upper bound (top risk 3 in the phase plan). Byte-identity is proven on one machine only (review M4).

### B-273 · Phone positives must be valid numbers outside the fiction range

- **Date:** 2026-10-16 · 2.9A · commit `2894fdd` · review I1b · **Controller ruling** · supersedes D-E
- **Context:** D-E followed the doc: positives with NANP N9X expansion area codes (290, 390) plus 555 numbers outside 0100-0199. The reviewer showed N9X numbers are `is_valid_number` False and Presidio's default leniency (VALID) rejects them ([C-42](experiments.md#c-42--phone-positives-nanp-expansion-area-codes-vs-555-numbers-outside-the-fiction-range)).
- **Choice:** positives are `phonenumbers`-valid and outside 555-0100..0199 ((212) 555-0234, (415) 555-2671, (310) 555-0287, (212) 555-0963); N9X rows dropped. **Consequence:** clr.phone recall is no longer capped below 1 by the detector's validity check.

### B-274 · Track plan per title: stacked edits in one copy, separate tracks for drift and offset

- **Date:** 2026-10-16 · 2.9A · commit `2e3cb6e` · D-F (`eval/inject.py::PLANS`)
- **Choice:** Sintel: es = term + shot_change + readability, fr = drift, de = offset, en untouched. Tears of Steel: es = term + shot_change + readability, fr = term + shot_change, de = drift, it = offset; en/nl/no/ru copied untouched (the `no` file is UTF-16 and copied as is). Stack order term → shot_change → readability with an `avoid` cue set.
- **Options rejected:** one copy per injector; injecting everything everywhere, because drift and offset move every cue and invalidate other labels on the same track.

### B-275 · Glossary variants live in the `notes` column

- **Date:** 2026-10-16 · 2.9A · commit `2e3cb6e` · D-G
- **Choice:** `glossary.csv` `notes` may contain `variants: A | B`; without it `loc.term` misspells by swapping two inner letters. Keeps the file valid for `parse_glossary` with no extra column. The sidecar glossaries were hand-written from the English/target subtitles (terms checked to occur in the files).
- **Consequence (review M2):** some variants contain the approved rendering (`Thom` / `Thomas`), which a substring checker would miss.

### B-276 · `synthetic-show` in the manifest with license CC-BY-4.0 and no source

- **Date:** 2026-10-16 · 2.9A · commit `2e3cb6e` · D-H
- **Choice:** added to titles and `mvp` with `CC-BY-4.0` (the `test_corpus` licence whitelist has no CC0; the content is generated by the project) and an empty source, so `nip eval corpus fetch --set mvp` creates an empty `data/corpus/synthetic-show/`. **Alternative:** add CC0-1.0 to the whitelist in `tests/unit/eval/test_corpus.py` (not 2.9A's file).

### B-277 · `nip eval inject` is wired as a command, not a sub-app

- **Date:** 2026-10-16 · 2.9A · commit `2e3cb6e` · D-I; wired by W-int in `3d66622`
- **Choice:** `from eval.inject import inject` and `eval_app.command("inject")(inject)`; a one-command Typer added with `add_typer` would need a sub-command name. `eval.inject.app` exists for tests.

### B-278 · Each injector seeds its own stream from `(injector id, seed)`

- **Date:** 2026-10-16 · 2.9A · commit `2e3cb6e` · D-J
- **Choice:** `random.Random(f"{injector id}/{seed}")` (string seeding is stable across processes), so stacked injectors on one seed do not share a stream; `Label.seed` is the user's seed. **Consequence (review M5):** the title is not in the seed, so Sintel and ToS pick correlated positions; `loc_readability.py` still seeds with the bare seed.

### B-279 · A film is `show=<slug>`, `episode="S01E01"`

- **Date:** 2026-10-16 · 2.9A · commit `2894fdd` · review I1 · **Controller ruling** · changes the episode default stated in [B-108](decisions.md#b-108--the-locreadabilityv1-injector-isolated-cues-one-kind-per-pick-ref-based-labels)
- **Context:** film labels used `episode = <title slug>` (inherited from 1.9/1.10), the store accepts only `SxxEyy`, and `metrics.overlap` returns 0 when episodes differ, so no film flag could ever match a film label.
- **Choice:** films are `S01E01` under `show=<slug>`; `FILM_EPISODE` is every injector's default, label ids start with the title, cue refs read `S01E01/es/N`; the 1.10 walking-skeleton native labels were rewritten to `S01E01`. **Cost if wrong (ledger):** relabel.

### B-280 · `eval/labels/` is reserved for Label-format files; EXP-004 ground truth moves out

- **Date:** 2026-10-16 · 2.9A review → 2.5 · **Controller ruling**
- **Context:** `test_committed_labels_validate` scans `eval/labels/**` and failed on 2.5's untracked `eval/labels/exp004/*.jsonl` (rows of `{scene, element, text, start_ms, labeller, basis}`, no `label_id`). The reviewer judged the test correctly scoped by the spec and advised against loosening it.
- **Choice:** 2.5's EXP-004 alignment ground truth moves out of `eval/labels/`; the test stays strict.

### B-281 · Mention truth records every entity surface in a line

- **Date:** 2026-10-16 · 2.9A · commit `2894fdd` · review I2
- **Context:** `truth.json` recorded mentions for characters and Kappa Cola only; EXP-020 scores resolution against these mentions, and a registry-enum extractor legitimately emits location, prop and org mentions.
- **Choice:** `model.find_mentions` scans each line's final text for every entity surface (character full/first name, nickname, description such as "the informant", location, prop, org, brand; whole words, longest first), used by the generator and the plot injectors instead of template-time bookkeeping. **Consequence:** 483 → 704 mention records for seed 1; generated scripts unchanged ([C-43](experiments.md#c-43--synthetic-show-mention-truth-template-bookkeeping-vs-scanning-every-surface)).

## W-int Wiring, integration fixes, image smoke, end-to-end store runs

### B-282 · Wiring by an idempotent `pipeline.wire()` called from `nip run`, not module-level `add_stage`

- **Date:** 2026-10-16 · W-int · commit `3d66622` · W-1 in the W-int notes
- **Context:** 2.0 provided `add_stage(name, fn, before=...)`; each W0/W1 report listed its wiring lines. Nine integration tests copy `pipeline.STAGES` and add their own stage.
- **Options:** (a) module-level `add_stage` at import of `nip.pipeline`; (b) a separate full stage list; (c) an idempotent `wire()`.
- **Choice:** (c). (a) would run the tests' stages twice, make every store test also run ASR, extraction and the SQL rules, and load the knowledge modules on every `nip --help`.
- **Consequence:** library callers of `run_store` get only the core stages unless they call `wire()`; 2.9B and the API controller must call it. A test that invokes `nip run` must patch copies of `STAGES`/`AGENTS`, or the wiring leaks into later tests (found and fixed in `test_store.py`).

### B-283 · Stage order: knowledge stages before `timeline`, cue alignment after it

- **Date:** 2026-10-16 · W-int · commit `3d66622` · W-2
- **Context:** the brief (and `briefs/phase2-plan.md`'s W2 order) listed cue_align + loc.observed before story; architecture.md puts "Target ↔ source cues" in Stage 2 (Timeline), before Stage 3 (Knowledge).
- **Choice:** `timeline.asr → timeline.align → knowledge.story → knowledge.extract → knowledge.consolidate → knowledge.index → timeline → timeline.cue_align → loc.observed → checks → verification → flags → report`. Forced by what the code reads: `cue_align.stage` reads `ep.timeline`, and `load_timeline` must see the new `fact/{id}` rows and aligned frames. No knowledge stage reads cue links, so the move is data-equivalent (the reviewer agreed, watch item W-a).
- **Consequence:** doc correction recorded; the reviewer also noted `knowledge.index` (group `text_prep`) runs after `knowledge.extract` (group `llm`), the reverse of the docs' group order, harmless while the embedder runs in-process.

### B-284 · `nip run` asks for asr, text_llm and text_embedder; asr pinned to `timeline.asr.variant`

- **Date:** 2026-10-16 · W-int · commit `3d66622` · W-3
- **Context:** the laptop Plan had no `asr`, `text_llm` or `text_embedder` decisions, so those stages would never run with a real model (2.5 / 2.8 notes).
- **Options for the asr choice:** let the planner choose (it picked `faster-whisper-large-v3-int8`, gpu_fraction 0.38, by quality rank, against EXP-003's turbo decision); change the catalog `quality_rank` (1.6's file and semantics); pin to the pipeline config.
- **Choice:** workload `{asr, text_llm, text_embedder: len(episodes)}` (one unit per episode per slot, a deliberate simplification: the counts only size replicas on multi-GPU hardware); asr pinned to `timeline.asr.variant` (turbo) unless `NIP_PIN_ASR` is set.
- **Consequence:** laptop Plan: asr turbo (0.19), text_embedder qwen3-embedding-0.6b (0.20), resident; text_llm skipped at 6.69 to 6.73 GB free. Reviewer M-3: asr is requested even for script-only shows, where on one 8 GB GPU in resident mode it competes with text_llm for a stage that does nothing (deferred). Watch W-c: planner behaviour when the pinned turbo cannot be placed was not exercised.


### B-285 · Knowledge and story constants move to `config/pipeline.yaml` with identical values

- **Date:** 2026-10-16 · W-int · commit `3d66622` · brief item 3 (2.1 review M-5; the controller had ruled in W1 that 2.1 keep them as module constants until told, because `pipeline.yaml` was 2.5's file until 2.5 completed)
- **Choice:** a `knowledge:` section (extract prompt_version/max_tokens, grounding and resolve thresholds, story llm_max_tokens / excerpt_chars / days_per_unit) read through `nip.config.pipeline_config()`; module attribute names unchanged; `NIP_INFERRED_STORY_CONFIDENCE_FACTOR` stays an env var.
- **Consequence:** reviewer minors, deferred: M-1 the four callers read the config at import time although `pipeline_config()` says "read on every call", so a `NIP_CONFIG_DIR` without a `knowledge:` section makes any `nip run` fail with `KeyError` via `wire()`; M-2 two readers of the same file (`timeline_config()` and `pipeline_config()`); M-5 `extract.PROMPT_VERSION` is now user-editable although it versions a template in code and is part of the recording and cache identity.

### B-286 · `load_timeline` resolves superseded facts as well as active ones

- **Date:** 2026-10-16 · W-int · commit `3d66622` · brief item 4b (2.1 note)
- **Context:** consolidation of a later episode closes earlier facts (`superseded`), and earlier episodes' flags cite them as `fact/{id}`.
- **Choice:** load `active` + `superseded`, exclude `retracted`. All four `plot.*.sql` rules still filter `status = 'active'`, so only an older flag's evidence resolves a superseded fact.
- **Consequence (watch W-b):** `superseded` covers two meanings once the fact-correction loop exists (closed by consolidation vs replaced by a reviewer edit); then re-evaluation must look at fact status or version, or an edit must mark the old version distinctly.

### B-287 · vLLM structured outputs run with xgrammar and `disable_any_whitespace`

- **Date:** 2026-10-16 · W-int · commit `3d66622` · brief item 4d (2.1 proposal 6)
- **Context:** 2.1 measured about 5 % of scenes running to max_tokens and attributed it to whitespace.
- **Choice:** `serving.vllm_args` always appends `--structured-outputs-config {"backend": "xgrammar", "disable_any_whitespace": true}` (vLLM 0.30 syntax; the old `--guided-decoding-backend xgrammar:disable-any-whitespace` is gone and `auto` is rejected with the option). Confirmed applied in the engine config in the image smoke.
- **Consequence:** **the hypothesis behind it was wrong.** W-serve measured 2 of 25 scenes still at 2,048 tokens with the flag on, and found the cause to be an enumeration loop inside valid JSON ([C-49](experiments.md#c-49--does-xgrammars-disable_any_whitespace-stop-the-extraction-runaway)). The flag stays (JSON output has fixed separators).

### B-288 · CI's integration step runs the Postgres-only store tests

- **Date:** 2026-10-16 · W-int · commit `3d66622` · **Controller ruling** (W0: adding `tests/integration/test_store.py` to `ci.yml` assigned to W-int) + brief item 4e
- **Choice:** the ten Postgres-only store files under `NIP_PROFILE=cpu`, with `test_index_pg.py::test_real_embedder_ranks` deselected (it downloads 1.2 GB under `NIP_INDEX_REAL`, and `NIP_CI=1` turns a skip into a failure). LLM replays come from the tracked `tests/fixtures/llm` (142 files, reviewer count).
- **Consequence:** 76 passed locally with the exact CI command. W-serve appended its Postgres tests to `test_store.py` so CI runs them.

### B-289 · The clearance OCR stage is not wired by W-int; 2.7 may add the one line

- **Date:** 2026-10-16 · W-int · W-4 → **Controller ruling** ("2.7 may add the one add_stage line for the clearance OCR stage in pipeline.py (after W-serve lands)")
- **Context:** 2.6 exposes only `ocr_detections` and `insert_detections`, no `fn(ep)` stage; `wire()` lives in `pipeline.py`, which 2.7 does not own.
- **Options (W-4):** 2.7 adds one `add_stage("clearance.ocr", ...)` line; or 2.9B (the W3 owner) adds it.
- **Choice:** 2.7, after W-serve. **Consequence:** clearance has no stage in W-int's runs; `clearance.CHECKS` stays empty until 2.7.

### B-290 · The vLLM image smoke is re-run on the new lock, with a forced exact-KV setting

- **Date:** 2026-10-16 · W-int · **Controller ruling** ("W-int must re-run the vLLM image smoke (transformers/hf-hub changed by gliner)"); fix commit `ff7b038`
- **Context:** 2.6's gliner pin moved transformers 5.20.0 → 5.16.1 and huggingface-hub 2.2.0 → 1.33.0 in the image's install; the Phase 1 smoke had validated the previous lock.
- **Choice:** rebuild `nip:dev` (old kept as `nip:pre-wint`), run `test_serving.py` in ray-head and one qwen3.5-4b-awq start through the shipped `serving.vllm_args`. Because the planner refused text_llm at the desktop's VRAM, the start forced EXP-001's `kv-planner` exact KV (`--kv-cache-memory-bytes 1006632960`).
- **Consequence:** PASS; the planner's own text_llm path was not exercised; load and throughput were worse than the Phase 1 smoke (n = 1, not attributed). The latent placeholder-test failure (Slot.ASR now bound to 2.5's actor) was fixed by using `Slot.DETECTOR`.

### B-291 · The ASR stub under the cpu profile still does its I/O (proposal, not built)

- **Date:** 2026-10-16 · W-int · W-6 (not built)
- **Context:** under the cpu profile the stub ASR still downloads the picture and extracts audio for an empty transcript (13.3 s on Sintel).
- **Choice:** not changed: skipping it would hide the I/O path from cpu-profile tests.

## W-serve Real models for `nip run` (staged serving in ray-head)

### B-292 · A W-serve step before W2: `nip run` inside ray-head with staged serving, and an `HF_HOME` default

- **Date:** 2026-10-16 · W-serve · **Controller ruling** W-5 (and W-7)
- **Context:** W-int found that no real LLM ever ran in `nip run` on the laptop: (a) nothing deploys the Serve apps for a run started on the Windows host (no Ray there; Phase 2 ruling R8 deferred the pgqueuer controller, [B-120](decisions.md#b-120--phase-2-plan-rulings-r1-to-r15-adopted)); (b) at the desktop's free VRAM the planner skips text_llm. W-int's W-5 options: run inside ray-head with `serving.run(plan, ...)`; a `nip serve up/down` command; wait for the Phase 4 controller. Separately its first real-ASR pass put 2.8 GB of HF models on C: because `HF_HOME` was unset (W-7).
- **Choice:** run inside ray-head with staged serving (deploy per stage group, teardown, VRAM check), which matches the docs' "controller runs inside the Ray cluster"; `nip` defaults `HF_HOME` to `<repo>/models/hf`. W-int review I-1 (silent skipped slots) was folded into the same step because W-serve owned `pipeline.py`. Cost if wrong (ledger): one extra exec hop for laptop runs.
- **Consequence:** [B-293](#b-293--nip-run---in-cluster-plus-a-documented-docker-compose-exec-line-no-wrapper-command-no-schedulerpy) to [B-303](#b-303--the-extraction-runaway-and-single-stream-throughput-are-handed-on-not-fixed-in-w-serve).

### B-293 · `nip run --in-cluster` plus a documented `docker compose exec` line; no wrapper command, no `scheduler.py`

- **Date:** 2026-10-16 · W-serve · commit `c02a542` · WS-1
- **Options:** a `nip cluster run` host wrapper that shells out to `docker compose exec` (it must know the compose files, `MSYS_NO_PATHCONV` and env passing); a flag that runs inside ray-head; wait for the Phase 4 controller.
- **Choice:** the flag, the smallest piece matching project-structure.md's `runtime/scheduler.py` / `controller.py` inside the cluster. The command: `HF_HUB_OFFLINE=1 docker compose -f compose.yaml -f compose.dev.yaml up -d --wait ray-head`, then `MSYS_NO_PATHCONV=1 docker compose -f compose.yaml -f compose.dev.yaml exec ray-head nip run --show S --episodes E… --in-cluster`.
- **Consequence:** one command on the laptop, but the user types the compose prefix; `--in-cluster` on the host raises `BadParameter` with the in-cluster command. `runtime/scheduler.py` was not created; the segment loop is about 15 lines in `run_store`, to move when the controller lands.

### B-294 · Only vLLM slots are deployed as Serve apps; actor slots stay in-process

- **Date:** 2026-10-16 · W-serve · commit `c02a542` · WS-3
- **Context:** only `text_llm` is called over HTTP; ASR (faster-whisper, CUDA) and the text embedder (CPU) are built in-process by their stages. Deploying the whole Plan group would load whisper twice on an 8 GB GPU.
- **Choice:** `pipeline.serve_slots` deploys only slots whose engine is `vllm`. Before a group loads, the in-process ASR cache is cleared (`asr.backend.cache_clear()` + `gc.collect()`).
- **Consequence:** the cache release is unexercised (M-6: every run was script-only). Revisit when a stage calls an actor over Serve, as 2.6's OCR/NER clients will (they hard-code `SERVE_URL`).

### B-295 · Staged serving is cut into stage segments, not 1.7's `serving.run(plan, work)`

- **Date:** 2026-10-16 · W-serve · commit `c02a542` · design entry in the W-serve notes
- **Context:** `serving.run` deploys every group's apps and calls `work(group)` in the Plan's group order, but the pipeline order runs `knowledge.index` (`text_prep`) after `knowledge.extract` (`llm`).
- **Choice:** `pipeline.segments(STAGES, served)` cuts the stage list where the needed Serve group changes; each segment runs inside `serving.group(...)` (a new context manager: idle → deploy → body → teardown → VRAM within idle + 256 MiB). `serving.run` was rewritten on top of `group`; 1.7's tests pass unchanged.
- **Consequence:** with the wired order the model loads once per run (`[story, extract]` in `llm`). Reviewer watch: if the embedder becomes a Serve app, `text_prep` would split into a second load.

### B-296 · A skipped slot's stages are skipped by one guard in `run_store`, and the checks they feed are gaps

- **Date:** 2026-10-16 · W-serve · commit `c02a542` · WS-4 (fixes W-int review I-1)
- **Context:** on a non-cpu Plan without text_llm the stages fell back to `StubLLM` or returned silently, and the run said `completed` with script_critic coverage 1.0 over 0 facts.
- **Options:** edit the three stage modules (`extract.py`, `index.py`, `asr.py`, owned by others); one guard in `run_store`.
- **Choice:** the guard, keyed on `plan.skipped_slots` (not "absent from decisions", so `stub_plan()` tests keep their behaviour): `STAGE_SLOTS` decides which stages are not called; `knowledge.story` is `RULES_ONLY`; `FEEDS = {"knowledge.extract": "plot."}` moves the plot checks to `skipped`, so the run is `completed_with_gaps`. ASR and index skips are recorded but not gaps. `ReportPlan` gains additive optional `skipped_slots` and `warnings`; the run summary gains `plan` and `serving`; episodes gain `skipped_stages`.
- **Consequence:** `extract.text_llm`'s stub fallback (`extract.py:276-279`) is still in the code but unreachable from `nip run` on a hardware Plan. Reviewer minors deferred: M-3 `slot_reason` parses warning strings (a structured `{slot: reason}` is the upgrade path); M-4 coverage 0.0 for a lost agent looks the same as a "not applicable" 0.0.

### B-297 · A VRAM skip says free vs needed, from the planner's own formula

- **Date:** 2026-10-16 · W-serve · commits `c02a542`, `dff0f7f` (M-1, M-2) · brief item 2
- **Choice:** `no_fit()` replaces the bare `no hardware for <slot>`: smallest candidate's per-GPU need at its minimum context, max(weights + KV + overhead, startup peak), against the roomiest GPU's usable = min(gmu × total, free − margin). Example: "qwen3.5-4b-awq needs 6.25 GiB on one GPU, GPU 0 has 6.20 usable = min(0.90 x 8.00 total, 6.70 free - 0.50 margin): short 0.05 GiB". The margin is passed to `planner.plan(margin_gb=…)` so message and planner cannot drift. After review: `need_gb` reuses `planner._kv_gb`; when VRAM is not the cause the bare reason is kept (never a negative shortfall). A run outside the cluster reports `no Serve for <slot>`.

### B-298 · Importing `nip` defaults `HF_HOME` to the repo's model cache

- **Date:** 2026-10-16 · W-serve · commit `c02a542` · W-7 (**Controller ruling** in W-5)
- **Context:** W-int's first real-ASR pass downloaded turbo (1.6 GB) and Qwen3-Embedding-0.6B (1.2 GB) into `C:\Users\pc872\.cache\huggingface\hub` because `HF_HOME` was unset.
- **Options:** default in `nip.config`; or each client passes `cache_dir`.
- **Choice:** `nip/config.py` `os.environ.setdefault("HF_HOME", …)` at import: `$NIP_MODEL_CACHE/hf` (compose sets `/models`), else `<repo>/models/hf`; the empty `nip/__init__.py` imports `nip.config` (one line outside the brief's file list, needed for "before any HF import"; the reviewer agreed only the package `__init__` runs before every entry point).
- **Consequence:** in the container compose already sets `HF_HOME=/models/hf`, so the default acts on the host. Reviewer M-7 (deferred): `nip.config` mutates the environment for every `import nip.contracts`, bypassing the contracts layer's import-linter ban on `nip.config` (import-linter does not count implicit parent-package imports); say so in the import-linter contract comment. The existing C: downloads were left for the user ("Do NOT delete", ledger).

### B-299 · `compose.dev.yaml` mounts the weights and the source into ray-head

- **Date:** 2026-10-16 · W-serve · commit `c02a542`
- **Context:** the named `models` volume held none of `models/hf`; the 26.5 GB image runs its baked source copy.
- **Choice:** ray-head mounts `./models:/models`, `./src`, `./config`, `./eval`, `./tests` (code read-only) with `PYTHONPATH=/app/src:/app`, the same set as 1.7's `exp001.compose.yaml`. `HF_HUB_OFFLINE=1` is set when the container is created (the vLLM child inherits Ray's environment), documented in the overlay header.
- **Consequence:** ray-head must be created from a shell without the host-side `NIP_DATABASE_URL` / `NIP_S3_ENDPOINT`, or compose bakes the loopback URLs into the container (a fix-round run failed in 11 s this way).

### B-300 · `NIP_VRAM_MARGIN_GB`, default 0.5; the 8 GB laptop may set 0.25

- **Date:** 2026-10-16 · W-serve · commit `dff0f7f` · **Controller ruling** (review I-2; WS-5)
- **Context:** the shipped 0.5 GiB margin refused qwen3.5-4b-awq by 0.02 to 0.21 GiB with the user's usual desktop apps open; the real end-to-end run used a monkeypatched 0.25 (device peak 7,585 of 8,188 MiB). WS-5 options: keep 0.5 (text_llm runs only when the desktop is at about 1,045 MiB or less); an env knob; lower it to 0.25 on single-GPU WSL2 hosts.
- **Choice:** env knob `NIP_VRAM_MARGIN_GB` (`nip.config.vram_margin_gb()`), default 0.5, fed to `planner.plan(margin_gb=…)` and `no_fit`; `.env.example` documents 0.25 for the laptop (EXP-001: real use +54..107 MiB over the prediction). An environment-only difference; cost if wrong (ledger): occasional start OOM → recorded gap.
- **Consequence:** run 3 at 0.25 peaked at 7,792 of 8,188 MiB; the gpu test passed at 0.5 when the desktop was light (388 MiB used). Builds on [B-083](decisions.md#b-083--exact-kv-budgets-on-single-gpu-engines-sized-by-the-planner-from-probed-free-vram).

### B-301 · One execution order everywhere: each stage over all episodes before the next stage

- **Date:** 2026-10-16 · W-serve · commit `dff0f7f` · **Controller ruling** (review I-3; supersedes WS-2's "in-cluster only")
- **Context:** the first version ran in-cluster runs segment-major (so the model loads once) but kept the per-episode order on the host, so the same input gave different `plot.*` flags for earlier episodes on the host and in the cluster (the host path is the test and CI proxy). The docs imply group-major ("Load group → drain all its work units → unload"; "Each model is loaded at most once per run").
- **Choice:** stage-major over all episodes, on the host and in the cluster, justified by the spec and cross-episode Script Critic; `segments()` only decides where a Serve group is held up. Cost if wrong (ledger): higher peak memory for long seasons.
- **Consequence:** every episode's plot checks see the facts of every episode in the run. Test: 6 identical flags on both paths over synthetic S01E01-02. Single-transaction semantics hold (re-review).

### B-302 · A Serve group that fails to deploy is a coverage gap; VRAM drift after the work is a warning

- **Date:** 2026-10-16 · W-serve · commit `dff0f7f` · review I-1 (fix as the reviewer proposed; tolerance value is the implementer's)
- **Context:** a deploy `ServingError` rolled back every episode and marked the run `failed`; with 20 to 50 MiB of headroom a load OOM from desktop drift is likely. The post-work teardown check raised if VRAM was not within 256 MiB of the pre-load idle, and the desktop moved 604 MiB (1,065 → 1,669) in 25 minutes.
- **Choice:** a deploy failure removes the group's slots from each episode's Plan (`no Serve for text_llm: group llm failed to deploy: …`) and degrades through the same path as a planner skip, ending `completed_with_gaps` with the error in `serving[]`. Post-work drift becomes `serving[].warning`; `DRIFT_TOLERANCE_MIB = 1024` (a left-over model is at least 1.5 GiB, vLLM about 6 GiB); the apps are deleted before the wait, and if the desktop really took the room the next group's deploy fails as a gap.
- **Consequence:** re-review minors (deferred): `rec["error"]` keeps only the first line, losing the teardown-also-failed note; the drift warning is not logged and not in `plan.warnings` or report.json.

### B-303 · The extraction runaway and single-stream throughput are handed on, not fixed in W-serve

- **Date:** 2026-10-16 · W-serve · WS-6 and the fix-round runaway analysis
- **Context:** runs 2 and 3 lost `sc/7` and `sc/25` to max_tokens (2/25), about 89 to 110 s of GPU each; the cause is an enumeration loop inside schema-valid JSON ([C-49](experiments.md#c-49--does-xgrammars-disable_any_whitespace-stop-the-extraction-runaway)). Extraction sends one scene at a time (14 to 24 tok/s), so 25 scenes take about 460 to 560 s.
- **Choice:** the runaway fix candidates (`maxItems` on `events`, forbidding `confidence: 0.0` events, a repetition penalty) are in 2.1B's `extract.py` / `llm.py`, so the evidence went to 2.1B; bounded units in flight per replica (docs › Work units and backpressure) to W2 / 2.9B.
- **Consequence:** 2.1B shipped a runaway guard (see the 2.1B record).

## 2.close Phase 2 closeout

### B-304 · CUDA 12 cuBLAS only, on `ldconfig`, and the uv cache dir fixed

- **Date:** 2026-10-18 · 2.close · commits `d5ef357`, `7532221` · DP-2.close-1 (+ review M1)
- **Context:** the image is CUDA 13; CTranslate2 4.8.3's Linux wheel dlopens `libcublas.so.12` and never cuDNN ([journal](journal.md#2026-10-18--2close-image-cuda-12-cublas-for-faster-whisper-and-a-uv-cache-mount-that-was-never-used)).
- **Options:** cuBLAS + cuDNN cu12 wheels as the docs say (cuDNN unused on Linux, and `nvidia-cudnn-cu12` would overwrite the cu13 `nvidia/cudnn` directory); a system CUDA 12 install (+GB, apt); `LD_LIBRARY_PATH` (lost if a launcher overrides the environment).
- **Choice:** `nvidia-cublas-cu12` in the `serve` extra (locked, Linux only) + an `/etc/ld.so.conf.d` entry + `ENV UV_CACHE_DIR=/root/.cache/uv UV_LINK_MODE=copy`. The wheels' licence (NVIDIA CUDA proprietary redistributable, the same class as the base image's CUDA libraries) was accepted; the docs' License Policy covers catalog variants, not pip wheels.
- **Consequence:** faster-whisper runs on the GPU in ray-head (RTF 0.019 to 0.027); image 25.1 GB (was 26.5); a later cuBLAS bump is a lock change; drop the wheel if CTranslate2 moves to CUDA 13. Deferred (review M2): the hardcoded `python3.12/dist-packages` path has no build-time guard.

### B-305 · `gliner-x-large` stays the planner's pick on the 8 GB laptop, measured, no pin

- **Date:** 2026-10-18 · 2.close · commits `d2a8fa3`, `c0988ee`, `cf6724e` · DP-2.close-2 · **Controller ruling** (keep only if EXP-008 recall ≥ base)
- **Context:** the planner picked `gliner-x-large` from an unmeasured 3.7 GiB estimate, and runs pinned `NIP_PIN_NER=gliner-x-base`; 2.7's ruling had already said the NER variant comes from the planner/catalog, not a pin.
- **Options:** keep a pin (the withdrawn DP-2.7-5); demote large in the catalog (quality_rank below base); measure and leave the planner alone.
- **Choice:** measure ([C-53](experiments.md#c-53--gliner-x-base-vs-gliner-x-large-size-latency-and-candidates-on-sintels-stored-ocr)): x-large 2.6 GiB, x-base 1.4, `pp-ocrv6-medium` 1.6 (`family: rapidocr`). The review found the default unscored; the controller ruled large stays only if a scored EXP-008 run (3 seeds, both films) shows recall at least equal to base. The NER A/B on replayed OCR gave recall 1.00 for both and shown FP per content-hour 90.99 → 86.55 ([C-54](experiments.md#c-54--ner-ab-on-replayed-ocr-gliner-x-large-vs-gliner-x-base-on-the-exp-008-end-to-end-benchmark)), so large stays.
- **Consequence:** laptop runs use large (+1.2 GiB, about +25 ms per call); `NIP_PIN_NER` is no longer needed; the published 2.7 EXP-008 numbers are for base and stay reproducible because `exp008_e2e run-cpu` still pins base in code. The A/B bounds "no recall loss" only: the benchmark barely exercises NER-driven checks.

### B-306 · Occurrence ref `clr/occ-<hash>` with kind `clearance_item`; occurrences are derived, not stored

- **Date:** 2026-10-18 · 2.close · commit `5f65199` · DP-2.close-3
- **Context:** stored clearance flags claim `clr/occ-<hash>` spans that existed only in the run's timeline.
- **Options:** a new `EvidenceKind` (frozen contract, DB enum, every consumer); a first-class ref format with the existing kind; occurrence rows.
- **Choice:** `refs.occurrence()` / `refs.is_occurrence()`; `load_timeline` rebuilds keyframe OCR text and occurrence spans from the stored `detection` rows through `checks.with_stored_ocr` (helpers in `checks.py` because importing `stage` costs 9.3 s for Presidio/spaCy against 0.8 s).
- **Consequence:** no migration and no contract change; `load_timeline` costs one extra query per episode plus the occurrence analysis (about 0.07 s on Sintel) when OCR rows exist; 34/34 stored Sintel flags re-verify without OCR. Deferred (review M4): `store.load` now lazily imports `agents.clearance.checks`, inverting store → agents.

### B-307 · The occurrence hash uses registry-independent fields only

- **Date:** 2026-10-18 · 2.close · commit `ddf6206` · review I1 · **Controller ruling**
- **Context:** hashing the matched registry item made the ref change when an unknown item was later logged, so the stored claim stopped resolving.
- **Choice:** hash episode, check, the normalized text of the first read and the first keyframe `(shot, n)`; the matched item is separate `context` evidence. Known limit: logging an item that merges two differently spelled reads into one occurrence can move the first keyframe. The rule re-check still drops the one flag whose item status changed (its "not in the clearance log" finding is stale); relaxing `ClearanceText.recheck` was left to 2.9B (see [B-124](decisions.md#b-124--a-clearance-status-change-shows-in-the-run-diff-as-resolved--new)).

### B-308 · Nothing changed in the image for OCR; the CPU fallback stays

- **Date:** 2026-10-18 · 2.close · no commit (no change)
- **Context:** the brief asked to make onnxruntime-gpu's CUDA provider load in the container; it already did ([C-52](experiments.md#c-52--rapidocr-in-the-container-cuda-provider-vs-cpu-and-the-041-kfs-that-was-not-reproduced)), and the log line read as a failure is a benign ORT 1.31 warning.
- **Choice:** no image change for OCR; `RapidOcrBackend(cuda=False)` and `_cuda()` false without torch CUDA remain the fallback. **Consequence:** 2.7's "OCR ran on the CPU in the container" statement is wrong and recorded as such.

## 2.9B-1 Stage cache, incremental re-runs, run diff

### B-122 · Cache objects are gzip JSON, not zstd

- **Date:** 2026-11-06 · 2.9B-1 · commit `e2bab95` · DP-2.9B-2 in the 2.9B notes
- **Context:** the data model names cache objects `.json.zst`. `zstandard` is not installed, and adding it needs an image rebuild, which the C: drive rule (no new Docker pulls or builds) ruled out.
- **Choice:** gzip (stdlib) at `cache/{key[0:2]}/{key}.json.gz`. **Consequence:** larger objects than zstd; switching later only changes the object suffix and codec, since keys are content hashes. Doc correction recorded.

### B-123 · Every check unit's cache key includes the unit key

- **Date:** 2026-11-06 · 2.9B-1 · commit `e2bab95` · DP-2.9B-3
- **Context:** without it, a SQL plot rule's unit in S01E02 had the same key as in S01E01 (no spans, show-wide facts) and replayed S01E01's findings ([journal](journal.md#2026-11-06--29b-1-stage-cache-incremental-re-runs-and-get-runsiddiff)).
- **Choice:** the unit key (which names the episode) is an input of every check key. **Consequence:** an identical subtitle window in another episode is a miss, not a hit, because findings cite episode-scoped refs; the cost is a few extra check runs, not wrong evidence.

### B-124 · A clearance status change shows in the run diff as resolved + new

- **Date:** 2026-11-06 · 2.9B-1 · commit `cca0f1c` · DP-2.9B-1 (controller addition iii)
- **Context:** when an `unknown` clearance occurrence gets logged (`pending`, `denied`, ...), its flag cites the logged item `clr/{id}`, so its fingerprint changes.
- **Options:** (a) show the old flag resolved and a new one; (b) a fourth "changed" class keyed on the occurrence. **Choice:** (a): the finding's statement changed and needs a fresh review, a disposition of the old statement must not carry over, and the spec's diff has three classes. Documented in the `api/runs.py` docstring. **Consequence:** logging N items shows N resolved + N new in the next diff.

### B-125 · `changed_inputs` labels a source by version label, else `src_{id}`

- **Date:** 2026-11-06 · 2.9B-1 · commit `cca0f1c` · DP-2.9B-4
- **Choice:** a source file is labelled by its `version_label`, else `src_{id}` (`nip ingest` has no version-label option yet), e.g. "S01E01 script src_68 → src_74 (scenes 3 changed)". "Changed scenes" are the extraction units whose cache key differs from the previous run's.

### B-126 · Reading a run is open to every authenticated role

- **Date:** 2026-11-06 · 2.9B-1 · commit `cca0f1c` · DP-2.9B-5
- **Context:** the API contract's Roles table lists no rule for reading runs; starting and cancelling are operator-only. **Choice:** any authenticated role may read a run and its diff.

## Process and CI (Phase 2)

### B-127 · phase-2's commit messages were rewritten once, before the first push, to drop Claude co-author trailers

- **Date:** 2026-11-06 · **User instruction** ("push ... as me and not you")
- **Context:** 96 of the 97 unpushed commits ended with `Co-Authored-By: Claude`; GitHub shows that as a co-author.
- **Choice:** strip only those trailer lines with `git filter-branch --msg-filter` over `origin/main..phase-2`, keep a backup branch (`backup/phase-2-before-trailer-strip`), verify the tree is unchanged, then push. Future commits in this project carry no Claude trailer. **Consequence:** every Phase 2 SHA changed ([journal](journal.md#2026-11-06--first-push-of-phase-2-claude-co-author-trailers-removed-from-96-commit-messages)); `phase-2` is now public, so it is not rewritten again (that would need a force push).

### B-128 · Tests force Typer's plain (non-Rich-terminal) output

- **Date:** 2026-11-06 · CI on PR #1 · commit `36e9305`
- **Context:** Typer forces a Rich terminal when `GITHUB_ACTIONS` is set, which styles captured help text and broke 5 CLI tests on the runner only ([journal](journal.md#2026-11-06--ci-on-pr-1-three-failures-that-only-appeared-on-the-github-runner)).
- **Options:** (a) strip ANSI in each test; (b) set `_TYPER_FORCE_DISABLE_TERMINAL` in the CI workflow; (c) set it in `tests/conftest.py`. **Choice:** (c): one line, covers every test and anyone running tests with `FORCE_COLOR` / `PY_COLORS` set, and needs no change per test.

### B-129 · Tests that need local `data/` files are marked integration; CI is replayed locally before a push

- **Date:** 2026-11-06 · CI on PR #1 · commit `36e9305` · extends the NIP_CI rule in `tests/conftest.py`
- **Context:** a test with a `skipif` on local `data/` files passes on the laptop and fails on the runner, where `NIP_CI=1` turns its skip into a failure.
- **Choice:** such tests carry `@pytest.mark.integration` (`test_real_sintel_labels_describe_the_written_tracks` is the one found; a search of `skipif` / `pytest.skip` in the CPU selection found only ffmpeg checks, which CI installs). Before pushing, the CI steps are replayed locally with `GITHUB_ACTIONS=true NIP_CI=1 NIP_PROFILE=cpu`.
