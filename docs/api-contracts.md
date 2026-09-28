# API Contracts

## Conventions

| Item | Value |
|------|-------|
| Base URL | `{NIP_PUBLIC_URL}/api/v1` (locally `http://localhost:8080/api/v1`) |
| Auth | OIDC bearer token: `Authorization: Bearer <token>`. Expected issuer, signing-key URL, audience, and roles claim come from `NIP_OIDC_ISSUER`, `NIP_OIDC_JWKS_URL`, `NIP_OIDC_AUDIENCE`, `NIP_OIDC_ROLES_CLAIM`. Keycloak is bundled for local use; any OIDC provider works in production. |
| IDs | Prefixed strings: `run_912`, `flg_48213`, `plan_42`, `src_77`. Evidence uses refs from [Data Model › Evidence Refs](data-model.md#evidence-refs). |
| Timecodes | SMPTE strings in responses (`00:14:22:05`); frames are available as `frames: [in, out)` on every timed object. |
| Pagination | `?page=1&page_size=50` (max 200); responses include `total`, `page`, `page_size`. |
| Versioning | Additive changes only within `v1`; clients must ignore unknown fields. |

### Roles

| Role | Can |
|------|-----|
| `viewer` | Read reports, flags, facts |
| `reviewer` | + disposition non-clearance flags, correct facts |
| `legal` | + disposition clearance flags (only this role can) |
| `operator` | + upload sources, start/cancel runs, view hardware and plans |

---

## System

### `GET /healthz` · `GET /readyz`

Liveness and readiness (readiness checks Postgres, object storage, and the Ray cluster). No auth. `GET /metrics` exposes Prometheus metrics on the internal network only.

### `GET /system/hardware` *(operator)*

The current hardware inventory as seen by the probe.

```json
{
  "probed_at": "2026-10-02T09:14:03Z",
  "nodes": [
    {
      "node_id": "a1f3…",
      "cpus": 16, "ram_gb": 23.5,
      "gpus": [{"index": 0, "name": "NVIDIA GeForce RTX 4060 Laptop GPU",
                "vram_total_gb": 8.0, "vram_free_gb": 6.9, "compute_capability": "8.9"}]
    }
  ],
  "autoscaling": {"enabled": false, "max_gpu_nodes": 0}
}
```

### `GET /system/plan-preview?agents=auto&objective=quality` *(operator)*

Dry run of the planner against the current hardware: the Plan a run would get right now. Same shape as `GET /runs/{id}/plan`.

---

## Shows, Episodes, Sources

### `POST /shows` *(operator)*

```json
// Request
{"slug": "harbor-lights", "title": "Harbor Lights"}
// Response 201
{"slug": "harbor-lights", "title": "Harbor Lights", "episodes": []}
```

### `POST /shows/{show}/episodes` *(operator)*

```json
// Request
{"season": 1, "number": 3, "episode_seq": 3, "title": "Low Tide"}
// Response 201
{"ref": "S01E03", "timeline_source": "script_estimate"}
```

### `POST /uploads` *(operator)*

Request a presigned upload URL. Object keys are content-addressed by the client-declared SHA-256, which the server verifies after upload.

```json
// Request
{"filename": "s01e03_picture_lock_02.mp4", "size_bytes": 3876452113, "sha256": "4be1…"}
// Response 201 (single PUT up to 5 GB; larger files get multipart part URLs)
{"object_key": "harbor-lights/S01E03/source/4be1….mp4",
 "upload_url": "https://…", "expires_at": "2026-10-02T10:14:03Z"}
```

### `POST /shows/{show}/sources` *(operator)*

Register an uploaded file. Validation runs immediately; picture validation (media probe) may be asynchronous.

```json
// Request
{"episode": "S01E03", "kind": "subtitle", "format": "ttml",
 "lang": "es-419", "role": "target",
 "object_key": "harbor-lights/S01E03/source/77c2….ttml", "version_label": "es_v3"}

// Response 201
{"source_id": "src_301", "status": "valid",
 "warnings": ["Declared frameRate 25 differs from picture 24000/1001"]}

// Response 422
{"error": {"code": "INPUT_REJECTED",
           "message": "Subtitle file failed to parse",
           "details": {"line": 1842, "reason": "Unclosed <p> element"}}}
```

`kind` ∈ `script | picture | subtitle | bible | glossary | clearance_log`. Show-level files (`bible`, `glossary`, `clearance_log`) use `"episode": null`.

### `GET /shows/{show}/sources?episode=S01E03&kind=subtitle`

Lists registered sources with version labels and validation status.

---

## Runs

### `POST /runs` *(operator)*

```json
// Request
{
  "show": "harbor-lights",
  "episodes": ["S01E03", "S01E04"],
  "agents": "auto",                     // or ["localization_auditor", "clearance_scanner", ...]
  "languages": ["es-419", "fr-FR", "de-DE"],
  "objective": "quality",               // optional; default from NIP_PLAN_OBJECTIVE
  "pins": {},                           // optional; e.g. {"vlm": "qwen3.8-27b-int4"}
  "force": false                        // true = ignore the cache
}

// Response 202
{
  "run_id": "run_912",
  "status": "queued",
  "plan_id": "plan_42",
  "agents_resolved": ["localization_auditor", "clearance_scanner", "script_critic", "continuity_inspector"],
  "inputs_used": {"S01E03": ["src_101", "src_188", "src_301"], "S01E04": ["src_102", "src_190"]},
  "skipped": [{"agent": "continuity_inspector", "episode": "S01E04",
               "checks": ["cont.visual"], "reason": "no picture registered"}]
}
```

With `"agents": "auto"`, agents and checks are activated from the inputs present ([Architecture › Activation matrix](architecture.md#activation-matrix)). Starting a run for an episode that already has an active run returns `409 RUN_CONFLICT`.

### `GET /runs/{run_id}`

```json
{
  "run_id": "run_912",
  "status": "running",                  // queued | running | completed | completed_with_gaps | failed | cancelled
  "plan_id": "plan_42",
  "mode": "staged",                     // staged | resident (from the Plan)
  "stages": [
    {"stage": "timeline.asr", "status": "done", "units": 2, "cached": 1},
    {"stage": "knowledge.extract", "status": "running", "units_done": 31, "units_total": 58},
    {"stage": "loc.gender", "status": "pending"}
  ],
  "coverage": {
    "clearance_scanner": {"units_total": 412, "done": 405, "failed": 7,
                          "gaps": ["S01E03/shot/112-118: GPU out of memory"]}
  },
  "started_at": "2026-10-02T09:20:11Z"
}
```

### `GET /runs/{run_id}/plan`

```json
{
  "plan_id": "plan_42",
  "objective": "quality",
  "mode": "staged",
  "groups": ["timeline", "vision_prep", "text_prep", "vlm+llm", "judge"],
  "decisions": {
    "text_llm":  {"variant": "qwen3.5-4b-awq", "shared_with": ["vlm"], "replicas": 1, "gpus_per_replica": 1, "context": 8192},
    "vlm":       {"variant": "qwen3.5-4b-awq", "shared_with": ["text_llm"]},
    "judge_llm": {"variant": "ministral-3-3b-fp8", "independent_family": true},
    "asr":       {"variant": "faster-whisper-large-v3-int8", "gpu_fraction": 0.5}
  },
  "amendments": [
    {"at": "2026-10-02T09:41:52Z", "slot": "asr",
     "from": "faster-whisper-large-v3-int8", "to": "faster-whisper-large-v3-turbo-int8",
     "reason": "CUDA OOM persisted after batch reduction"}
  ]
}
```

(Abbreviated; `decisions` lists every slot the run needs.)

Full Plan semantics: [Hardware Adaptation › Plan](hardware-adaptation.md#the-plan).

### `POST /runs/{run_id}/cancel` *(operator)*

Cancels pending units; running units finish. Completed unit outputs stay cached.

### `GET /runs/{run_id}/diff?against=previous`

```json
{
  "run_id": "run_915", "against": "run_912",
  "changed_inputs": ["S01E03 script draft_07 → draft_08 (scenes 5, 12 changed)"],
  "new_flags": ["flg_48790"],
  "resolved_flags": ["flg_48213"],
  "unchanged_flags": 41,
  "units_rerun": 63, "units_cached": 1204
}
```

---

## Reports

### `GET /shows/{show}/episodes/{ep}/report?run=latest`

The ranked pre-release report.

```json
{
  "episode": "S01E03", "run_id": "run_912", "status": "completed_with_gaps",
  "plan": {"plan_id": "plan_42", "mode": "staged", "judge_independent": false},
  "coverage": {"localization_auditor": 1.0, "clearance_scanner": 0.983,
               "script_critic": 1.0, "continuity_inspector": 1.0},
  "counts": {"must_review": 9, "review_recommended": 14, "suppressed": 22},
  "sections": [
    {"category": "clearance",    "flags": [ /* flag summaries, ranked */ ]},
    {"category": "continuity",   "flags": [ ]},
    {"category": "localization", "flags": [ ]},
    {"category": "plot_hole",    "flags": [ ]}
  ]
}
```

Flag summaries contain `id, check, severity, confidence, tier, title, lang, primary_tc, status`. Suppressed flags are included only with `?include_suppressed=true`.

### `GET /shows/{show}/episodes/{ep}/clearance-report?run=latest&format=json|csv`

One row per occurrence:

```csv
occurrence_id,item,kind,status,tc_in,tc_out,screen_time_s,prominence,severity,thumbnail_url,flag_id
occ_19,Acme Hardware,logo,pending,00:12:04:08,00:12:10:13,6.2,featured,4,https://…,flg_48214
```

---

## Flags

### `GET /flags`

Filters: `show, episode, run, agent, check, category, tier, lang, status, severity_min`.

### `GET /flags/{flag_id}`

The full flag ([Data Model › Flag and Evidence](data-model.md#flag-and-evidence)) with evidence resolved for display:

```json
{
  "id": "flg_48213",
  "check": "loc.spoiler",
  "evidence": [
    {"kind": "subtitle_cue", "ref": "S01E03/es-419/212", "role": "claim",
     "tc_in": "00:14:22:05", "tc_out": "00:14:24:11", "quote": "La asesina sigue aquí.",
     "aligned_source": {"ref": "S01E03/en/209", "quote": "The killer is still here."}}
  ],
  "media": {"proxy_url": "https://…", "seek_seconds": 862.2, "end_seconds": 864.5},
  "history": [{"run_id": "run_880", "status": "open"}]
}
```

`media.proxy_url` is a short-lived presigned URL.

### `PUT /flags/{flag_id}/disposition` *(reviewer; legal for clearance flags)*

```json
// Request
{"action": "overridden", "note": "Intentional - the narrator is unreliable in this scene"}
// Response 200
{"flag_id": "flg_48213", "disposition": {"action": "overridden", "note": "…",
 "actor": "reviewer@studio.example", "at": "2026-10-02T12:00:00Z"}}
```

`action` ∈ `accepted | fix_rerun | overridden`. `overridden` without a note → `400 OVERRIDE_NOTE_REQUIRED`. Dispositions attach to the flag's fingerprint, so they carry forward to later runs.

---

## Knowledge

### `GET /shows/{show}/entities?kind=character&status=candidate`

### `GET /shows/{show}/facts?entity=maya&predicate=learns&episode=S01E03`

```json
{
  "facts": [
    {"id": "fact/8812", "predicate": "learns", "subject": "maya", "object": "ada_is_informant",
     "screen": {"from": "S01E06 @ 00:31:02:14", "to": null},
     "story": {"from_seq": 211, "to_seq": null},
     "confidence": 0.94,
     "sources": [{"ref": "S01E06/line/18.7", "quote": "Ada's been feeding them everything."}]}
  ]
}
```

### `GET /shows/{show}/fact-queue`

Low-confidence facts and candidate entities awaiting review, ordered by how many flags depend on them.

### `POST /facts/{fact_id}/corrections` *(reviewer)*

```json
// Request
{"action": "retract", "reason": "Sarcasm - Leo doesn't actually know this yet"}
// Response 201
{"correction_id": "corr_55", "fact": "fact/8812", "new_version": 2,
 "reevaluating_flags": ["flg_48790", "flg_48791"]}
```

---

## WebSocket Events

`GET /ws` (same bearer token, sent as the `Sec-WebSocket-Protocol` bearer subprotocol).

| Event | Payload | Trigger |
|-------|---------|---------|
| `run.started` | `{run_id, plan_id, mode}` | Run begins |
| `run.stage_progress` | `{run_id, stage, done, total}` | At most once per second per stage |
| `run.completed` | `{run_id, status, counts, gaps}` | Run ends (`completed` or `completed_with_gaps`) |
| `run.failed` | `{run_id, error}` | Unrecoverable failure |
| `plan.amended` | `{run_id, slot, from, to, reason}` | OOM downgrade or node change |
| `flag.dispositioned` | `{flag_id, action, actor}` | Review action |
| `fact.corrected` | `{fact, correction_id, reevaluating_flags}` | Fact correction |
| `flags.reevaluated` | `{flag_ids, results}` | Re-evaluation after a correction finishes |

---

## Review UI Contract

| View | Data | Refresh on |
|------|------|-----------|
| Episode list (counts per tier, coverage) | `GET /shows/{show}/episodes`, report summaries | `run.completed` |
| Report (ranked sections, filters by agent/tier/lang) | `GET …/report` | `run.completed`, `flag.dispositioned` |
| Flag detail: evidence player (video seeks to frame), source/target subtitles side by side, crops, cited facts | `GET /flags/{id}` | `flag.dispositioned`, `flags.reevaluated` |
| Clearance report (occurrence table, thumbnails, CSV export) | `GET …/clearance-report` | `run.completed` |
| Fact queue (confirm / edit / retract) | `GET /shows/{show}/fact-queue` | `fact.corrected` |
| Run view (stages, Plan, amendments, coverage gaps) | `GET /runs/{id}`, `GET /runs/{id}/plan` | `run.stage_progress`, `plan.amended` |
| Diff view (new / resolved / unchanged) | `GET /runs/{id}/diff` | Manual |

---

## Errors

```json
{
  "error": {
    "code": "RUN_FAILED",
    "message": "Run run_912 failed: object storage unreachable",
    "details": {"stage": "timeline.keyframes", "retry_count": 3}
  }
}
```

| Code | HTTP | Meaning |
|------|------|---------|
| `VALIDATION_FAILED` | 400 | Request body invalid |
| `OVERRIDE_NOTE_REQUIRED` | 400 | Override without a note |
| `UNAUTHORIZED` | 401 | Missing or invalid token |
| `FORBIDDEN` | 403 | Role lacks permission (e.g. non-legal user dispositioning a clearance flag) |
| `NOT_FOUND` | 404 | Unknown show, episode, run, flag, or fact |
| `RUN_CONFLICT` | 409 | Episode already has an active run |
| `INPUT_REJECTED` | 422 | Source file failed validation |
| `NO_RUNNABLE_AGENTS` | 422 | Registered inputs don't activate any requested agent |
| `RUN_FAILED` | 500 | Unrecoverable pipeline failure |
| `CLUSTER_UNAVAILABLE` | 503 | Ray cluster unreachable or has no usable resources |
