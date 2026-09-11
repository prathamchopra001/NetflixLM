# API Contracts

## REST API

Base URL: `http://localhost:8080/api/v1`

Auth: OIDC via Keycloak. All endpoints require `Authorization: Bearer <token>`.

---

### Pipeline Management

#### `POST /episodes`

Submit a new episode for processing.

```json
// Request
{
  "show_id": "stranger-things",
  "season": 3,
  "episode": 5,
  "script_version": "draft_07",
  "script_file": "s3e5_draft07.fdx",
  "video_file": "s3e5_finalcut02.mp4",
  "subtitles_file": "s3e5_subtitles.srt",
  "options": {
    "run_agents": ["script_critic", "continuity_inspector", "recap_agent"],
    "recap_locales": ["en"],
    "spoiler_mode": "episodic"
  }
}

// Response 202
{
  "pipeline_run_id": "pr-uuid-001",
  "status": "queued",
  "estimated_duration_minutes": 30
}
```

#### `GET /episodes/{show_id}/{season}/{episode}`

Get the latest Pre-Live Report for an episode.

```json
// Response 200
{
  "show_id": "stranger-things",
  "season": 3,
  "episode": 5,
  "script_version": "draft_07",
  "pipeline_run_id": "pr-uuid-001",
  "status": "completed",
  "flags": [
    {
      "id": "flag-uuid-001",
      "type": "plot_hole",
      "issue": "Walter references Gale's assignment in E6 but doesn't learn about it until E8",
      "severity": 4,
      "confidence": 0.97,
      "source_agent": "script_critic",
      "disposition": null
    }
  ],
  "recaps": [
    {
      "locale": "en",
      "base_recap": "...",
      "variants": 5,
      "spoiler_risk_score": 0.15
    }
  ],
  "created_at": "2026-06-24T10:00:00Z",
  "completed_at": "2026-06-24T10:28:00Z"
}
```

#### `GET /episodes/{show_id}/{season}/{episode}/versions`

List all script versions processed for this episode.

```json
// Response 200
{
  "versions": [
    {
      "script_version": "draft_06",
      "pipeline_run_id": "pr-uuid-000",
      "status": "completed",
      "flag_count": 4,
      "completed_at": "2026-06-20T14:00:00Z"
    },
    {
      "script_version": "draft_07",
      "pipeline_run_id": "pr-uuid-001",
      "status": "completed",
      "flag_count": 2,
      "completed_at": "2026-06-24T10:28:00Z"
    }
  ]
}
```

#### `GET /episodes/{show_id}/{season}/{episode}/diff`

Get incremental diff between two script versions.

```json
// Request query params: ?from=draft_06&to=draft_07

// Response 200
{
  "from_version": "draft_06",
  "to_version": "draft_07",
  "changed_scenes": ["Sc03", "Sc07"],
  "affected_cross_references": ["Sc02", "Sc09"],
  "new_flags": [
    {
      "id": "flag-uuid-003",
      "type": "plot_hole",
      "issue": "New inconsistency introduced by Sc03 changes"
    }
  ],
  "resolved_flags": [
    {
      "id": "flag-uuid-001",
      "type": "continuity",
      "issue": "Prop swap in Sc05 (resolved by wardrobe change in draft_07)"
    }
  ]
}
```

---

### Flag Management

#### `PUT /flags/{flag_id}/disposition`

Record human disposition on a flag.

```json
// Request
{
  "action": "overridden",
  "note": "Intentional inconsistency - dream sequence",
  "user": "editor@example.com"
}

// Response 200
{
  "flag_id": "flag-uuid-001",
  "disposition": {
    "action": "overridden",
    "note": "Intentional inconsistency - dream sequence",
    "timestamp": "2026-06-24T12:00:00Z",
    "user": "editor@example.com"
  }
}
```

#### `GET /flags`

List flags with filtering.

```json
// Query params: ?show_id=stranger-things&severity_min=3&disposition=null&source_agent=script_critic

// Response 200
{
  "flags": [
    {
      "id": "flag-uuid-002",
      "type": "plot_hole",
      "issue": "...",
      "severity": 4,
      "confidence": 0.92,
      "source_agent": "script_critic",
      "disposition": null
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50
}
```

---

### Recap Endpoints

#### `GET /recaps/{show_id}/{season}/{episode}`

Get all recap drafts for an episode.

```json
// Response 200
{
  "episode_ref": "S3E5",
  "script_version": "draft_07",
  "recaps": [
    {
      "locale": "en",
      "base_recap": "...",
      "variants": [
        {
          "text": "Tension explodes as Walter's double life...",
          "tone": "suspense",
          "thread_focus": "walter_coverup",
          "emotional_valence": {"tension": 0.9, "relief": 0.1}
        }
      ],
      "thread_labels": ["walter_coverup", "skyler_agency", "hank_investigation"],
      "emotional_valence_map": {"tension": 0.85, "dread": 0.7, "relief": 0.1},
      "character_arc_weights": {"walter": 0.4, "skyler": 0.3, "hank": 0.2, "jesse": 0.1},
      "spoiler_risk_score": 0.15
    }
  ]
}
```

#### `PUT /recaps/{recap_id}/publish`

Publish a recap (requires all blocking flags resolved).

```json
// Request
{
  "variant_index": 0,
  "user": "editor@example.com"
}

// Response 200 (if flags resolved)
{
  "recap_id": "recap-uuid-001",
  "status": "published",
  "published_variant": {
    "tone": "suspense",
    "text": "..."
  },
  "published_at": "2026-06-24T12:30:00Z"
}

// Response 403 (if blocking flags exist)
{
  "error": "Cannot publish recap: 2 unresolved blocking flags",
  "blocking_flags": ["flag-uuid-001", "flag-uuid-002"]
}
```

---

### Knowledge Graph

#### `GET /kg/{show_id}/entities`

Query entities in the knowledge graph.

```json
// Query params: ?type=Character&episode=S3E5

// Response 200
{
  "entities": [
    {
      "id": "walter",
      "type": "Character",
      "name": "Walter White",
      "properties": {
        "status": "alive",
        "death_tc": null
      }
    }
  ]
}
```

#### `GET /kg/{show_id}/constraints/violations`

Get current constraint violations for a show.

```json
// Response 200
{
  "violations": [
    {
      "constraint_id": "C-SEC-001",
      "description": "Walter knows Gale's assignment before revelation event",
      "entities": ["walter", "gale_assignment_secret"],
      "evidence_timecodes": ["S3E6@00:22:15", "S3E8@00:08:30"]
    }
  ]
}
```

#### `POST /kg/{show_id}/corrections`

Submit a human correction to the KG.

```json
// Request
{
  "entity_id": "walter",
  "relation_type": "KNOWS_SECRET",
  "correction": {
    "action": "delete",
    "reason": "Walter doesn't know Gale's assignment in E6 — this was an extraction error"
  },
  "user": "editor@example.com"
}

// Response 201
{
  "correction_id": "corr-uuid-001",
  "status": "applied",
  "entity_id": "walter",
  "applied_at": "2026-06-24T13:00:00Z"
}
```

---

## Personalization Interface Contract

Version: `1.0.0`

This is the structured API that the recommendation engine consumes. The Recap Agent writes to this contract; the personalization system reads from it.

### Recap Metadata (consumed by recommendation engine)

```json
{
  "episode_ref": "S3E5",
  "show_id": "stranger-things",
  "locale": "en",
  "available_variants": [
    {
      "variant_id": "v-suspense-001",
      "tone": "suspense",
      "thread_focus": "walter_coverup",
      "emotional_valence": {"tension": 0.9, "relief": 0.1, "dread": 0.7},
      "text": "Tension explodes as Walter's double life..."
    },
    {
      "variant_id": "v-character_study-001",
      "tone": "character_study",
      "thread_focus": "skyler_agency",
      "emotional_valence": {"dread": 0.7, "empathy": 0.6, "tension": 0.3},
      "text": "Skyler pushes back against Walter's secrecy..."
    }
  ],
  "narrative_threads": [
    {
      "id": "walter_coverup",
      "label": "Walter's Cover-Up",
      "weight": 0.4,
      "genre_tags": ["crime", "thriller"]
    },
    {
      "id": "skyler_agency",
      "label": "Skyler's Agency",
      "weight": 0.3,
      "genre_tags": ["drama", "family"]
    },
    {
      "id": "hank_investigation",
      "label": "Hank's Investigation",
      "weight": 0.2,
      "genre_tags": ["crime", "mystery"]
    }
  ],
  "emotional_profile": {
    "dominant_emotion": "tension",
    "emotion_vector": {"tension": 0.85, "dread": 0.7, "relief": 0.1, "empathy": 0.3},
    "intensity": 0.78,
    "trajectory": "escalating"
  },
  "character_focus": {
    "primary": "walter",
    "secondary": ["skyler", "hank"],
    "weights": {"walter": 0.4, "skyler": 0.3, "hank": 0.2, "jesse": 0.1}
  },
  "spoiler_risk_score": 0.15
}
```

### Contract Rules

1. **Versioning**: All schema changes are backward-compatible. New fields added; none removed. Clients must ignore unknown fields.
2. **Availability**: Recap metadata is written within 30 minutes of pipeline completion.
3. **Freshness**: Metadata is updated when a new script version is processed (incremental diff).
4. **Language**: Each locale gets its own `RecapMetadata` instance. The `locale` field is required.
5. **Blocking**: If `spoiler_risk_score > 0.40`, the metadata is not available until editorial sign-off.

---

## Editorial UI Data Contract

The React editorial dashboard consumes these endpoints. All real-time updates use WebSocket.

### WebSocket Events

| Event | Payload | Trigger |
|-------|---------|---------|
| `pipeline.started` | `{pipeline_run_id, show_id, season, episode}` | Pipeline begins processing |
| `pipeline.agent_completed` | `{pipeline_run_id, agent, flag_count, duration_seconds}` | Individual agent finishes |
| `pipeline.completed` | `{pipeline_run_id, total_flags, total_recaps, duration_seconds}` | Full pipeline completes |
| `flag.disposition_updated` | `{flag_id, action, user, timestamp}` | Human reviews a flag |
| `kg.correction_applied` | `{correction_id, entity_id, user, timestamp}` | Human corrects KG |

### Dashboard Views

| View | Data Source | Refresh |
|------|-----------|---------|
| Episode list with flag counts | `GET /episodes/{show_id}/{season}/{episode}` | On `pipeline.completed` |
| Flag detail panel | `GET /flags/{flag_id}` | On `flag.disposition_updated` |
| Recap preview with variant selector | `GET /recaps/{show_id}/{season}/{episode}` | On `pipeline.agent_completed` (recap_agent) |
| KG violation panel | `GET /kg/{show_id}/constraints/violations` | On `kg.correction_applied` |
| Version diff view | `GET /episodes/{show_id}/{season}/{episode}/diff` | Manual trigger |

---

## Error Responses

All endpoints use standard error format:

```json
{
  "error": {
    "code": "PIPELINE_FAILED",
    "message": "Pipeline run pr-uuid-001 failed during script_critic agent execution",
    "details": {
      "agent": "script_critic",
      "stage": "kg_traversal",
      "retry_count": 3
    }
  }
}
```

| Code | HTTP Status | Meaning |
|------|-------------|---------|
| `PIPELINE_QUEUED` | 202 | Pipeline run accepted and queued |
| `PIPELINE_RUNNING` | 200 | Pipeline in progress |
| `PIPELINE_COMPLETED` | 200 | Pipeline finished successfully |
| `PIPELINE_FAILED` | 500 | Pipeline encountered an unrecoverable error |
| `RECAP_BLOCKED` | 403 | Recap publish blocked by unresolved flags |
| `KG_CORRECTION_INVALID` | 400 | KG correction refers to non-existent entity |
| `VERSION_NOT_FOUND` | 404 | Script version has no pipeline run |
| `UNAUTHORIZED` | 401 | Missing or invalid OIDC token |
| `FORBIDDEN` | 403 | Insufficient permissions |
