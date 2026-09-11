# Data Schemas

## Canonical EpisodeDocument

The unified data structure produced by the ingestion layer. All downstream agents consume this.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "EpisodeDocument",
  "type": "object",
  "required": ["show_id", "season", "episode", "script_version", "timeline"],
  "properties": {
    "show_id": {
      "type": "string",
      "description": "Unique show identifier (e.g., 'stranger-things')"
    },
    "season": { "type": "integer" },
    "episode": { "type": "integer" },
    "script_version": {
      "type": "string",
      "description": "Draft identifier (e.g., 'draft_07', 'final_cut_02')"
    },
    "show_metadata": {
      "type": "object",
      "properties": {
        "title": { "type": "string" },
        "genre": { "type": "string", "enum": ["drama", "sci-fi", "comedy", "thriller", "horror", "romance", "documentary", "animation", "other"] },
        "tone_guide": { "type": "string" },
        "characters": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "character_id": { "type": "string" },
              "name": { "type": "string" },
              "description": { "type": "string" },
              "first_appearance": { "type": "string", "format": "season-episode-timecode" }
            }
          }
        },
        "relationships": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "source": { "type": "string" },
              "target": { "type": "string" },
              "relation": { "type": "string" },
              "since": { "type": "string" }
            }
          }
        }
      }
    },
    "timeline": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["timecode", "scene_id"],
        "properties": {
          "timecode": {
            "type": "string",
            "pattern": "^\\d{2}:\\d{2}:\\d{2}:\\d{2}$",
            "description": "SMPTE timecode HH:MM:SS:FF"
          },
          "scene_id": { "type": "string" },
          "script_block": {
            "type": "object",
            "properties": {
              "location": { "type": "string" },
              "time_of_day": { "type": "string" },
              "characters_present": { "type": "array", "items": { "type": "string" } },
              "dialogue": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "character": { "type": "string" },
                    "line": { "type": "string" },
                    "direction": { "type": "string" }
                  }
                }
              },
              "stage_directions": { "type": "string" }
            }
          },
          "transcript_segment": {
            "type": "object",
            "properties": {
              "text": { "type": "string" },
              "start_tc": { "type": "string" },
              "end_tc": { "type": "string" },
              "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
            }
          },
          "keyframe": {
            "type": "object",
            "properties": {
              "image_path": { "type": "string" },
              "timecode": { "type": "string" },
              "detected_objects": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "object_class": { "type": "string" },
                    "bounding_box": { "type": "array", "items": { "type": "number" } },
                    "track_id": { "type": "string" },
                    "character_id": { "type": "string" },
                    "attributes": { "type": "object" }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

---

## Knowledge Graph Schema

### Entity Types

| Entity Type | Required Properties | Optional Properties |
|------------|-------------------|-------------------|
| **Character** | `name`, `first_appearance_tc` | `description`, `actor_name`, `status` (alive/dead), `death_tc` |
| **Location** | `name`, `first_appearance_tc` | `description`, `type` (indoor/outdoor/vehicle) |
| **Prop** | `name`, `first_appearance_tc` | `description`, `category` (weapon/clothing/device/vehicle/other), `current_state` |
| **Event** | `name`, `timecode`, `episode_ref` | `description`, `significance` (minor/major/climactic) |
| **Secret** | `name`, `revealed_tc`, `revealed_in_episode` | `description`, `scope` (personal/relational/plot-critical) |

### Relation Types

| Relation | Source | Target | Properties | Description |
|----------|--------|--------|------------|-------------|
| `AT_LOCATION` | Character | Location | `timecode`, `episode_ref`, `confidence` | Character is at location at timecode |
| `HOLDS_PROP` | Character | Prop | `timecode`, `episode_ref`, `hand` (left/right/unspecified), `confidence` | Character holds/owns prop at timecode |
| `KNOWS_SECRET` | Character | Secret | `since_tc`, `episode_ref`, `source` (witness/told/inferred), `confidence` | Character knows secret since timecode |
| `ALIVE_AT` | Character | Event | `timecode`, `episode_ref`, `status` (alive/dead/unknown), `confidence` | Character alive/dead status at timecode |
| `RELATES_TO` | Character | Character | `relation` (parent/child/spouse/sibling/friend/enemy/other), `since_tc`, `episode_ref`, `confidence` | Relationship between characters |
| `CONTAINS` | Location | Location | `episode_ref`, `confidence` | Location contains sub-location |
| `STATE_OF` | Prop | Prop | `timecode`, `state` (loaded/unloaded/open/closed/worn/etc), `episode_ref`, `confidence` | Prop state at timecode |
| `CAUSES` | Event | Event | `episode_ref`, `confidence` | Event causes another event |
| `PRECEDES` | Event | Event | `episode_ref`, `confidence` | Event precedes another event chronologically |
| `CONCEALED_FROM` | Secret | Character | `until_tc`, `episode_ref`, `confidence` | Secret hidden from character until timecode |

### Time-Versioned Properties

All relations carry `timecode` and `episode_ref` attributes. This enables:

- **Point-in-time queries**: "Where is Walter at 00:14:22 in S3E5?"
- **Temporal range queries**: "What does Walter know between S3E1 and S3E8?"
- **Change detection**: "When did this prop change state?"

### Confidence Annotations

Every relation has a `confidence` field:

| Value | Meaning | Source |
|-------|---------|--------|
| 1.0 | Explicitly stated in script | Human-verified or high-confidence extraction |
| 0.95 | High-confidence extraction | Fine-tuned NER extraction above threshold |
| 0.70–0.94 | Lower-confidence extraction | Below threshold, queued for human review |
| 0.50–0.69 | Weak evidence | Inferred from context, needs validation |

---

## KG Constraint Definitions

The deterministic constraint engine enforces these rules. No LLM involved — pure graph queries.

| Constraint ID | Rule | Query Pattern | Violation Example |
|--------------|------|---------------|-------------------|
| `C-LOC-001` | Character cannot be at two locations at the same timecode | `MATCH (c:Character)-[r:AT_LOCATION]->(l:Location) WHERE r.timecode = $tc WITH c, collect(l) AS locs WHERE size(locs) > 1 RETURN c, locs` | Character appears in two sets simultaneously |
| `C-DEAD-001` | Dead character cannot perform actions after death timecode | `MATCH (c:Character)-[a:ALIVE_AT]->(e:Event) WHERE a.status = 'dead' WITH c, a.timecode AS death_tc MATCH (c)-[r:AT_LOCATION|HOLDS_PROP]->(x) WHERE r.timecode > death_tc RETURN c, r, x` | Dead character speaks in later scene |
| `C-PROP-001` | Prop cannot be held by two characters at same timecode | `MATCH (c1:Character)-[r1:HOLDS_PROP]->(p:Prop)<-[r2:HOLDS_PROP]-(c2:Character) WHERE r1.timecode = r2.timecode AND c1 <> c2 RETURN c1, c2, p` | Two characters hold same prop simultaneously |
| `C-SEC-001` | Secret cannot be known before revelation event | `MATCH (c:Character)-[k:KNOWS_SECRET]->(s:Secret) WHERE k.since_tc < s.revealed_tc RETURN c, s` | Character acts on information they haven't received yet |
| `C-REL-001` | Biological parent relation is immutable | `MATCH (c1:Character)-[r:RELATES_TO]->(c2:Character) WHERE r.relation = 'parent' WITH c1, c2, r MATCH (c1)-[r2:RELATES_TO]->(c2) WHERE r2.relation <> r.relation AND r2.since_tc > r.since_tc RETURN c1, c2, r, r2` | Parent relation contradicted later |

---

## Agent Output Schemas

### Plot Hole Flag

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "PlotHoleFlag",
  "type": "object",
  "required": ["id", "issue", "severity", "layer", "evidence", "confidence", "script_version"],
  "properties": {
    "id": { "type": "string", "format": "uuid" },
    "issue": { "type": "string" },
    "severity": { "type": "integer", "minimum": 1, "maximum": 5 },
    "layer": { "type": "string", "enum": ["graph_traversal", "rac_retrieval", "bdi_simulation"] },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["ref", "type"],
        "properties": {
          "ref": { "type": "string", "description": "Episode timecode reference (e.g., 'S3E6@00:22:15')" },
          "type": { "type": "string", "enum": ["dialogue", "stage_direction", "revelation_event", "action", "visual"] }
        }
      }
    },
    "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
    "suggested_fix": { "type": "string" },
    "script_version": { "type": "string" },
    "human_disposition": {
      "type": "object",
      "properties": {
        "action": { "type": "string", "enum": ["accepted", "fix_and_rerun", "overridden"] },
        "note": { "type": "string" },
        "timestamp": { "type": "string", "format": "date-time" },
        "user": { "type": "string" }
      }
    }
  }
}
```

### Continuity Flag

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ContinuityFlag",
  "type": "object",
  "required": ["id", "issue", "severity", "signal_source", "evidence", "confidence", "script_version"],
  "properties": {
    "id": { "type": "string", "format": "uuid" },
    "issue": { "type": "string" },
    "severity": { "type": "integer", "minimum": 1, "maximum": 5 },
    "signal_source": { "type": "string", "enum": ["deterministic_graph", "visual_cv_vlm", "contrastive_pre-filter"] },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["frame", "observation"],
        "properties": {
          "frame": { "type": "string", "description": "Keyframe reference (e.g., 'S4E2_Sc3_ShotA_00:14:22')" },
          "observation": { "type": "string" }
        }
      }
    },
    "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
    "suggested_fix": { "type": "string" },
    "script_version": { "type": "string" },
    "human_disposition": {
      "type": "object",
      "properties": {
        "action": { "type": "string", "enum": ["accepted", "fix_and_rerun", "overridden"] },
        "note": { "type": "string" },
        "timestamp": { "type": "string", "format": "date-time" },
        "user": { "type": "string" }
      }
    }
  }
}
```

### Recap Output

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "RecapOutput",
  "type": "object",
  "required": ["episode_ref", "base_recap", "variants", "thread_labels", "emotional_valence_map", "character_arc_weights", "spoiler_risk_score"],
  "properties": {
    "episode_ref": { "type": "string", "description": "e.g., 'S3E5'" },
    "base_recap": { "type": "string" },
    "variants": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["text", "tone", "thread_focus", "emotional_valence"],
        "properties": {
          "text": { "type": "string" },
          "tone": { "type": "string", "enum": ["action", "romance", "suspense", "comedy", "character_study"] },
          "thread_focus": { "type": "string" },
          "emotional_valence": {
            "type": "object",
            "additionalProperties": { "type": "number", "minimum": 0, "maximum": 1 },
            "description": "Emotion → intensity mapping (e.g., {\"tension\": 0.9, \"relief\": 0.1})"
          }
        }
      }
    },
    "thread_labels": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Primary narrative threads identified (e.g., ['walter_coverup', 'skyler_agency', 'hank_investigation'])"
    },
    "emotional_valence_map": {
      "type": "object",
      "additionalProperties": { "type": "number", "minimum": 0, "maximum": 1 },
      "description": "Overall episode emotional profile"
    },
    "character_arc_weights": {
      "type": "object",
      "additionalProperties": { "type": "number" },
      "description": "Character → narrative weight mapping (sums to 1.0)"
    },
    "spoiler_risk_score": {
      "type": "number",
      "minimum": 0,
      "maximum": 1,
      "description": "0 = completely safe, 1 = contains end-of-season spoilers"
    },
    "locale": {
      "type": "string",
      "default": "en",
      "enum": ["en", "es", "pt", "ko", "ja"]
    }
  }
}
```

---

## Confidence Threshold Configuration

```yaml
confidence_thresholds:
  # Flag routing
  auto_escalate: 0.90
  review_recommended: 0.70
  suppress_below: 0.70

  # NER extraction
  ner_auto_accept: 0.95
  ner_human_review: 0.70

  # Recap gating
  spoiler_risk_block_threshold: 0.40
  hallucination_reject_threshold: 0.30

  # Continuity VLM
  visual_continuity_precision_floor: 0.75
  contrastive_anomaly_distance_threshold: 0.85
```

---

## Vector Index Chunk Schema

```json
{
  "chunk_id": "S3E5_Sc03_001",
  "episode_ref": "S3E5",
  "scene_id": "Sc03",
  "text": "...",
  "embedding_model": "BAAI/bge-large-en-v1.5",
  "metadata": {
    "show_id": "stranger-things",
    "season": 3,
    "episode": 5,
    "scene_characters": ["walter", "jesse"],
    "scene_location": "superlab",
    "timecode_start": "00:14:00:00",
    "timecode_end": "00:17:30:00",
    "chunk_type": "scene"
  }
}
```

Chunking strategy: scene-level granularity. Each scene becomes one chunk. Long scenes (>2000 tokens) are sub-chunked with overlap (200 tokens).
