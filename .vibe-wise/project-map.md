# Project Map

## Purpose
NIP (Narrative Intelligence Pipeline): a self-hosted pipeline that audits a show before release —
localization drift, clearance risks, plot holes, and continuity errors (README.md).

## Requirements
- Open-weight, self-hosted models only; no third-party AI APIs (docs/architecture.md › Design Rules).
- Every fact/flag must cite evidence on the timeline; unresolvable evidence is dropped.
- Deterministic checks first, models second; model outputs constrained to JSON schemas.
- Verification can only drop/downgrade/merge flags, never add.
- Agents are independent: read the shared knowledge layer, never each other's output.
- Runs on hardware from an 8 GB laptop GPU up to clusters (docs/hardware-adaptation.md).

## Components
Package `src/nip/` (verified to exist):
- `contracts/` — shared types; depends on nothing else in nip (import-linter contract).
- `timecode/` — frame/SMPTE math; depends on nothing.
- `ingest/` — parse script, subtitles, bible, glossary, clearance log.
- `timeline/` — shot detection, keyframes, ASR (`asr.py`), alignment on one frame axis.
- `knowledge/` — timed-fact extraction (`extract.py`), story (`story.py`), registries.
- `agents/` — `localization/`, `clearance/`, `script_critic/` (continuity not present yet), `base.py`.
- `verification/` — drops/downgrades agent flags.
- `runtime/` — hardware planning, model clients (`clients/`), `cache.py` (untracked, new).
- `store/` — Postgres/pgvector + object storage; `ingest.py`, `load`.
- `api/` — FastAPI; queues runs in Postgres, never calls runtime.
- `pipeline.py`, `cli.py` (Typer app `nip`), `config.py`.
- `eval/` — evaluation package (shipped in the wheel).

## Main Flow
Documented design (docs/architecture.md):

  Ingest --files--> Timeline (frames) --aligned objects--> Knowledge (timed facts, index, registries)
    --read by--> 4 agents (independent) --flags--> Verification --surviving flags--> Human Review

Implemented stage order for `nip run` (verified in src/nip/pipeline.py `wire()`):
  [nip ingest -> Postgres/object store]
  timeline.asr -> timeline.align -> story -> extract -> consolidate -> index -> timeline
    -> timeline.cue_align -> loc.observed -> clearance OCR -> checks -> verification -> flags
    -> clearance.csv -> report
  API -> ? (only /healthz, /readyz, identity; no run routes yet)

## Status (as of 2026-11-01, branch phase-2)
- Phase 1 (foundation): implemented.
- Phase 2 (knowledge + deterministic checks): 2.1–2.8 implemented; 2.9 stage cache /
  incremental re-runs in progress (uncommitted: runtime/cache.py + 10 modified files).
- Phase 3 (LLM/vision checks, continuity agent, LLM judge): not started.
- Phase 4 (review UI, domain API, Helm/cloud): not started.

## Data and Trust Boundaries
- Postgres + pgvector (sqlalchemy, alembic, psycopg); object storage via boto3 (keyframes, files).
- Models served via vLLM's OpenAI-compatible API (`openai` client), Ray Serve on Linux.
- MLflow (`mlruns/` locally) for experiments.
- Auth: pyjwt present; roles described in docs/api-contracts.md (not verified in code).

## Build and Deployment
- Python 3.12, uv, hatchling; CLI entry `nip = nip.cli:app`.
- Dev: pytest (markers `gpu`, `integration`), ruff, mypy strict, import-linter (`lint-imports`).
- README: `docker compose up -d`, `docker compose exec api nip doctor`. Compose file location not verified.

## Unknowns
- How the pipeline worker picks up queued runs and schedules stages (pipeline.py/runtime not traced).
- Where the Compose/Docker config lives.
- Continuity Inspector agent status.
