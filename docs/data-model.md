# Data Model

All structured data lives in **PostgreSQL** (with the `vector` and `btree_gist` extensions). Media and large artifacts live in **S3-compatible object storage**. This document defines how time is represented, the schema, the input file formats, and the output schemas that agents, the API, and the review UI share.

---

## Time

Time is the backbone of every check, so its representation is strict.

| Concept | Representation | Notes |
|---------|---------------|-------|
| **Frame** | `integer`, 0 = first frame of program | Never floating-point seconds |
| **Frame rate** | Rational `fps_num / fps_den` (e.g. `24000/1001`) | Per episode, from the media probe |
| **Drop-frame** | `boolean` | Only meaningful at 29.97 / 59.94 |
| **Start timecode** | Frame offset (masters commonly start at `01:00:00:00`) | Added only for display |
| **Range** | `int8range`, half-open `[in, out)` | GiST-indexed for overlap queries |
| **Display** | SMPTE `HH:MM:SS:FF` (`;` separator for drop-frame) | Computed, never stored as the source of truth |
| **Screen position** | `screen_key = (episode_seq << 32) \| frame` (bigint) | Orders everything across episodes in viewer order |
| **Story position** | `story_seq` (integer rank per scene), `story_day` | Chronological order; see [Architecture › Story order](architecture.md#story-order-and-story-days) |

**Subtitle conversion.** Cue times in milliseconds are converted with exact rational arithmetic:
`frame = round(ms × fps_num / (1000 × fps_den))`. Frame-based cue times (TTML `frameRate` / SMPTE timecodes) are converted using the *declared* frame rate of the file, which is also recorded — a declared rate that differs from the picture's is itself a localization finding.

**Script-estimate mode.** Without picture, scenes receive estimated ranges (one script page ≈ one minute at 24 fps) and `timeline_source = 'script_estimate'`. Picture alignment later replaces them and sets `timeline_source = 'picture'`.

---

## Schema

Types are abbreviated; `id` columns are `bigint generated always as identity primary key` unless noted. External APIs expose prefixed string ids (`flg_48213`, `run_912`).

### Content and timeline

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE show (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  slug text UNIQUE NOT NULL,                 -- 'harbor-lights'
  title text NOT NULL
);

CREATE TABLE episode (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  show_id bigint NOT NULL REFERENCES show(id),
  season int NOT NULL, number int NOT NULL,
  episode_seq int NOT NULL,                  -- release order across the show
  ref text NOT NULL,                         -- 'S01E03'
  fps_num int, fps_den int, drop_frame bool,
  start_tc_frames int DEFAULT 0,
  duration_frames bigint,
  timeline_source text NOT NULL DEFAULT 'script_estimate',  -- | 'picture'
  UNIQUE (show_id, season, number)
);

CREATE TABLE source_file (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  episode_id bigint REFERENCES episode(id),  -- null for show-level files (bible, glossary, clearance log)
  show_id bigint NOT NULL REFERENCES show(id),
  kind text NOT NULL,        -- script | picture | subtitle | bible | glossary | clearance_log
  lang text,                 -- BCP 47 for subtitles: 'en', 'es-419', 'fr-FR', 'de-DE'
  role text,                 -- subtitles: 'source' | 'target'
  format text NOT NULL,      -- fountain | fdx | pdf | mp4 | srt | vtt | ttml | yaml | csv
  object_key text NOT NULL,  -- content-addressed: .../{sha256}.{ext}
  sha256 char(64) NOT NULL,
  version_label text,        -- 'draft_07', 'picture_lock_02', 'es_v3'
  declared_fps text,         -- subtitles with frame-based timing
  ingested_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE scene (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  episode_id bigint NOT NULL REFERENCES episode(id),
  script_scene_no text NOT NULL,             -- '12', '12A'
  heading text NOT NULL,                     -- 'INT. HARBOR WAREHOUSE - NIGHT'
  location_entity_id bigint,                 -- resolved location
  time_of_day text,
  markers text[] NOT NULL DEFAULT '{}',      -- flashback, dream, vision, intercut, continuous
  story_day int, story_seq int,
  story_inferred bool NOT NULL DEFAULT false,-- true = position inferred, not explicit
  frames int8range,                          -- estimated or aligned
  in_cut bool NOT NULL DEFAULT true,
  text_hash char(64) NOT NULL                -- drives incremental re-runs
);

CREATE TABLE script_line (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  scene_id bigint NOT NULL REFERENCES scene(id),
  seq int NOT NULL,
  kind text NOT NULL,                        -- dialogue | action | parenthetical | transition
  speaker_entity_id bigint,
  text text NOT NULL,
  frames int8range                           -- after alignment
);

CREATE TABLE shot (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  episode_id bigint NOT NULL REFERENCES episode(id),
  scene_id bigint REFERENCES scene(id),
  frames int8range NOT NULL,
  setup_cluster int,                         -- camera-setup group within the scene
  keyframes jsonb NOT NULL                   -- [{"n":0,"frame":84211,"object_key":"..."}]
);

CREATE TABLE transcript_segment (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  episode_id bigint NOT NULL REFERENCES episode(id),
  frames int8range NOT NULL,
  lang text NOT NULL,
  text text NOT NULL,
  words jsonb NOT NULL,                      -- [{"w":"still","f_in":84230,"f_out":84241,"p":0.97}]
  aligned_line_id bigint REFERENCES script_line(id)
);

CREATE TABLE subtitle_track (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  episode_id bigint NOT NULL REFERENCES episode(id),
  source_file_id bigint NOT NULL REFERENCES source_file(id),
  lang text NOT NULL,
  role text NOT NULL                         -- source | target
);

CREATE TABLE subtitle_cue (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  track_id bigint NOT NULL REFERENCES subtitle_track(id),
  idx int NOT NULL,                          -- cue number as in the file
  frames int8range NOT NULL,
  text text NOT NULL,                        -- lines joined with '\n'
  aligned_source_cue_ids bigint[],           -- target → source (1:n / n:1)
  UNIQUE (track_id, idx)
);

CREATE INDEX ON script_line USING gist (frames);
CREATE INDEX ON shot USING gist (episode_id, frames);
CREATE INDEX ON transcript_segment USING gist (episode_id, frames);
CREATE INDEX ON subtitle_cue USING gist (track_id, frames);
```

### Knowledge layer

Extraction produces scene-local **events**; a deterministic consolidation step turns them into **facts** with validity intervals. Events are cacheable per scene; consolidation is cheap and re-runs whenever any event changes.

```sql
CREATE TABLE entity (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  show_id bigint NOT NULL REFERENCES show(id),
  kind text NOT NULL,       -- character | location | prop | secret | term | org | brand | person | product
  canonical_name text NOT NULL,
  attributes jsonb NOT NULL DEFAULT '{}',    -- gender, pronouns, identity_hidden_until, importance...
  origin text NOT NULL,     -- bible | extracted | glossary | clearance_log
  fictional bool,           -- true = declared fictional in the bible
  status text NOT NULL DEFAULT 'confirmed'   -- confirmed | candidate
);

CREATE TABLE entity_alias (
  entity_id bigint NOT NULL REFERENCES entity(id),
  lang text NOT NULL DEFAULT 'any',   -- BCP 47 tag, or 'any'
  alias text NOT NULL,
  kind text NOT NULL,       -- name | nickname | approved_rendering | observed_rendering
  occurrences int NOT NULL DEFAULT 0,
  PRIMARY KEY (entity_id, lang, alias)
);

CREATE TABLE fact_event (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  scene_id bigint NOT NULL REFERENCES scene(id),
  line_id bigint NOT NULL REFERENCES script_line(id),
  predicate text NOT NULL,  -- present_at | holds | owns | state | wearing | learns | references
                            -- | relationship | setup | payoff | decision | mentions
  subject_id bigint NOT NULL REFERENCES entity(id),
  object_id bigint REFERENCES entity(id),
  value jsonb,              -- {"state":"injured","detail":"left hand cut"} / {"kind":"partners"}
  quote text NOT NULL,      -- must be found in line_id's text (grounding validator)
  confidence real NOT NULL,
  work_unit_id bigint       -- extraction unit that produced it
);

CREATE TABLE fact (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  show_id bigint NOT NULL REFERENCES show(id),
  predicate text NOT NULL,
  subject_id bigint NOT NULL REFERENCES entity(id),
  object_id bigint REFERENCES entity(id),
  value jsonb,
  screen int8range NOT NULL,        -- validity in viewer order (screen_key units)
  story int4range NOT NULL,         -- validity in story order (story_seq units)
  source_event_ids bigint[] NOT NULL,
  confidence real NOT NULL,         -- min of source events, reduced if story position inferred
  version int NOT NULL DEFAULT 1,
  status text NOT NULL DEFAULT 'active',   -- active | superseded | retracted
  supersedes bigint REFERENCES fact(id)
);

CREATE INDEX ON fact USING gist (subject_id, predicate, story);
CREATE INDEX ON fact USING gist (subject_id, predicate, screen);
```

**Consolidation rules (examples):**

| Predicate | Interval |
|-----------|----------|
| `present_at` | The scene's own range |
| `holds`, `owns`, `wearing`, `relationship` | From the establishing scene until a superseding event for the same subject (and object where relevant) |
| `state: injured` | Until a `healed`/`treated` event or the end of the story day, whichever the rule pack specifies |
| `state: dead` | Open-ended |
| `learns` | Open-ended from the learning point (knowledge is never lost) |

### Registries and retrieval

```sql
CREATE TABLE clearance_item (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  show_id bigint NOT NULL REFERENCES show(id),
  name text NOT NULL,
  kind text NOT NULL,       -- brand | logo | artwork | product | person | phone | url | address | plate | location
  status text NOT NULL,     -- cleared | pending | denied
  scope text,               -- 'S01E01-S01E08' or null for whole show
  notes text,
  source_file_id bigint REFERENCES source_file(id)
);

CREATE TABLE scene_chunk (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  scene_id bigint NOT NULL REFERENCES scene(id),
  kind text NOT NULL,       -- 'scene_text' (MVP embeds scene text only)
  text text NOT NULL,
  embedding vector NOT NULL,  -- untyped dimension so embedder variants can differ by Plan
  embedder_variant text NOT NULL
);
-- pgvector indexes need a fixed dimension, so one partial expression index per embedder variant:
-- CREATE INDEX ON scene_chunk USING hnsw ((embedding::vector(1024)) vector_cosine_ops)
--   WHERE embedder_variant = 'qwen3-embedding-0.6b';

CREATE TABLE detection (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  episode_id bigint NOT NULL REFERENCES episode(id),
  shot_id bigint REFERENCES shot(id),
  keyframe_n int,
  channel text NOT NULL,    -- ocr | detector | vlm | ner
  label text NOT NULL,      -- 'logo', 'phone_number', 'org', ...
  text text,                -- OCR text / recognized name
  box real[4],              -- normalized [x, y, w, h]
  confidence real NOT NULL,
  model_variant text NOT NULL
);
```

### Runs, plans, caching, coverage

```sql
CREATE TABLE plan (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  inventory jsonb NOT NULL,     -- HardwareInventory (see Hardware Adaptation)
  catalog_sha256 char(64) NOT NULL,
  objective text NOT NULL,      -- quality | throughput
  pins jsonb NOT NULL DEFAULT '{}',
  decisions jsonb NOT NULL,     -- per slot: variant, replicas, gpus, mode
  amendments jsonb NOT NULL DEFAULT '[]',  -- e.g. OOM downgrades during the run
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE run (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  show_id bigint NOT NULL REFERENCES show(id),
  episode_ids bigint[] NOT NULL,
  agents text[] NOT NULL,       -- resolved from inputs unless explicitly requested
  languages text[],
  plan_id bigint REFERENCES plan(id),
  status text NOT NULL,         -- queued | running | completed | completed_with_gaps | failed | cancelled
  code_version text NOT NULL,   -- git SHA of the running image
  previous_run_id bigint REFERENCES run(id),
  requested_by text NOT NULL,
  started_at timestamptz, finished_at timestamptz
);

CREATE TABLE work_unit (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id bigint NOT NULL REFERENCES run(id),
  stage text NOT NULL,          -- 'timeline.asr', 'knowledge.extract', 'loc.gender', ...
  unit_key text NOT NULL,       -- 'S01E03/sc/12', 'S01E03/es-419/200-219'
  cache_key char(64),
  status text NOT NULL,         -- pending | running | done | cached | failed
  attempts int NOT NULL DEFAULT 0,
  error text,
  model_variant text,
  started_at timestamptz, finished_at timestamptz
);

CREATE TABLE stage_cache (
  cache_key char(64) PRIMARY KEY,
  stage text NOT NULL,
  artifact_key text NOT NULL,   -- object storage key of the cached output
  model_variant text, prompt_version text,
  created_at timestamptz NOT NULL DEFAULT now(),
  hits int NOT NULL DEFAULT 0
);

CREATE TABLE variant_calibration (
  variant text NOT NULL,        -- catalog variant id
  gpu_name text NOT NULL,       -- NVML device name
  context int NOT NULL,         -- tokens (0 for non-LLM variants)
  peak_gb real NOT NULL,        -- measured peak GPU memory after load + warm-up
  measured_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (variant, gpu_name, context)
);
```

Coverage per agent is a view over `work_unit` (`units_total`, `done + cached`, `failed`, with failed unit keys listed as gaps). The planner reads `variant_calibration` in preference to catalog estimates ([Hardware Adaptation › Memory model](hardware-adaptation.md#memory-model)).

### Flags, review, audit

```sql
CREATE TABLE flag (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id bigint NOT NULL REFERENCES run(id),
  episode_id bigint NOT NULL REFERENCES episode(id),
  agent text NOT NULL,          -- localization_auditor | clearance_scanner | script_critic | continuity_inspector
  check_id text NOT NULL,       -- see Check IDs below
  category text NOT NULL,       -- clearance | continuity | localization | plot_hole
  lang text,
  severity smallint NOT NULL CHECK (severity BETWEEN 1 AND 5),
  confidence real NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  tier text NOT NULL,           -- must_review | review_recommended | suppressed
  title text NOT NULL,
  explanation text NOT NULL,
  suggested_fix text,
  fingerprint char(64) NOT NULL,   -- stable identity across runs (check + normalized evidence)
  produced_by jsonb NOT NULL,      -- {model_variant, prompt_version, plan_id, cache_key}
  verification jsonb NOT NULL,     -- {evidence, rule_recheck, judge, judge_variant}
  merged_into bigint REFERENCES flag(id),
  status text NOT NULL DEFAULT 'open'   -- open | resolved | dispositioned
);

CREATE TABLE evidence (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  flag_id bigint NOT NULL REFERENCES flag(id),
  kind text NOT NULL,       -- scene | script_line | shot | keyframe | transcript_segment | subtitle_cue
                            -- | fact | clearance_item | detection
  ref text NOT NULL,        -- human-readable reference, see Evidence refs
  role text NOT NULL,       -- claim | context | contradiction | setup | payoff | expected
  frames int8range,
  lang text,
  quote text,
  crop jsonb                -- {"keyframe": "S01E03/kf/118.0", "box": [0.61, 0.22, 0.12, 0.09]}
);

CREATE TABLE disposition (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  flag_fingerprint char(64) NOT NULL,   -- dispositions follow the finding across runs
  flag_id bigint NOT NULL REFERENCES flag(id),
  action text NOT NULL,     -- accepted | fix_rerun | overridden
  note text,                -- required when action = overridden
  actor text NOT NULL,
  at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fact_correction (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fact_id bigint NOT NULL REFERENCES fact(id),
  action text NOT NULL,     -- confirm | edit | retract
  new_value jsonb,
  reason text NOT NULL,
  actor text NOT NULL,
  at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE audit_event (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  at timestamptz NOT NULL DEFAULT now(),
  actor text NOT NULL,      -- user id or 'system'
  action text NOT NULL,     -- run.started, flag.dropped, flag.dispositioned, plan.amended, fact.corrected ...
  target text NOT NULL,     -- 'flg_48213', 'run_912', 'fact/8812'
  payload jsonb NOT NULL
);
```

`audit_event` is append-only: the application role has `INSERT` but not `UPDATE`/`DELETE` on it.

**Fingerprints.** A flag's fingerprint is `sha256(check_id + normalized evidence refs + lang)`. It is stable across runs, which is how dispositions carry forward (an overridden finding stays overridden) and how run diffs classify flags as new, resolved, or unchanged.

---

## Rule Queries (examples)

Layer 1 Script Critic rules are plain SQL over `fact`:

```sql
-- plot.knowledge_order: character references a secret before learning it (story order)
SELECT r.id AS reference_fact, r.subject_id AS character_id, r.object_id AS secret_id
FROM fact r
WHERE r.predicate = 'references' AND r.status = 'active'
  AND NOT EXISTS (
    SELECT 1 FROM fact l
    WHERE l.predicate = 'learns' AND l.status = 'active'
      AND l.subject_id = r.subject_id
      AND l.object_id  = r.object_id
      AND lower(l.story) <= lower(r.story));

-- plot.two_places: same character at two different locations at the same story moment
SELECT a.subject_id, a.id AS fact_a, b.id AS fact_b
FROM fact a
JOIN fact b ON a.subject_id = b.subject_id
           AND a.predicate = 'present_at' AND b.predicate = 'present_at'
           AND a.id < b.id
           AND a.object_id <> b.object_id
           AND a.story && b.story
WHERE a.status = 'active' AND b.status = 'active';
```

---

## Evidence Refs

Human-readable, stable references used in flags, the API, and the UI:

| Kind | Format | Example |
|------|--------|---------|
| Scene | `{ep}/sc/{no}` | `S01E03/sc/12` |
| Script line | `{ep}/line/{scene}.{seq}` | `S01E03/line/12.4` |
| Shot | `{ep}/shot/{id}` | `S01E03/shot/118` |
| Keyframe | `{ep}/kf/{shot}.{n}` | `S01E03/kf/118.0` |
| Transcript segment | `{ep}/asr/{id}` | `S01E03/asr/903` |
| Subtitle cue | `{ep}/{lang}/{idx}` | `S01E03/es-419/212` |
| Fact | `fact/{id}` | `fact/8812` |
| Clearance item | `clr/{id}` | `clr/77` |

---

## Check IDs

| Agent | Check IDs |
|-------|-----------|
| Localization Auditor | `loc.term`, `loc.gender`, `loc.formality`, `loc.spoiler`, `loc.readability`, `loc.shot_change`, `loc.drift`, `loc.offset` |
| Clearance Scanner | `clr.phone`, `clr.url`, `clr.email`, `clr.address`, `clr.plate`, `clr.brand_text`, `clr.logo`, `clr.artwork`, `clr.dialogue_ref` |
| Script Critic | `plot.knowledge_order`, `plot.dead_acts`, `plot.two_places`, `plot.prop_provenance`, `plot.motivation`, `plot.unresolved_setup` |
| Continuity Inspector | `cont.wardrobe_text`, `cont.injury_text`, `cont.prop_text`, `cont.visual` |

The same IDs are used by the evaluation harness's ground-truth labels ([Evaluation](evaluation.md)).

---

## Flag and Evidence

Agents emit flags in this shape (Pydantic model in `nip/contracts/flag.py`; JSON Schema exported for constrained decoding and the API):

```json
{
  "id": "flg_48213",
  "run_id": "run_912",
  "episode": "S01E03",
  "agent": "clearance_scanner",
  "check": "clr.phone",
  "category": "clearance",
  "lang": null,
  "severity": 4,
  "confidence": 0.96,
  "tier": "must_review",
  "title": "Real-format phone number visible on shop sign",
  "explanation": "OCR reads '(617) 4XX-XXXX' on the storefront sign for 6.2 s (featured). The number is outside the fiction-reserved 555-0100–0199 range and is not in the clearance log.",
  "suggested_fix": "Replace with a number in 555-0100–0199, or blur in post.",
  "evidence": [
    {"kind": "keyframe", "ref": "S01E03/kf/118.0", "role": "claim",
     "tc_in": "00:12:04:08", "tc_out": "00:12:10:13",
     "quote": "(617) 4XX-XXXX",
     "crop": {"keyframe": "S01E03/kf/118.0", "box": [0.61, 0.22, 0.12, 0.09]}},
    {"kind": "shot", "ref": "S01E03/shot/118", "role": "context",
     "tc_in": "00:12:04:08", "tc_out": "00:12:10:13"}
  ],
  "produced_by": {"model_variant": "pp-ocrv6-medium", "prompt_version": null,
                  "plan_id": "plan_42", "cache_key": "9f1c…"},
  "verification": {"evidence": "pass", "rule_recheck": "pass", "judge": "n/a"},
  "status": "open",
  "disposition": null
}
```

Field rules:

- `evidence` must contain at least one item with `role: "claim"`. Layer 2 Script Critic flags need at least two evidence items.
- `tc_in` / `tc_out` are display fields computed from `frames`; in script-estimate mode they are replaced by `"scene": "S01E03 · Sc 12 (script estimate)"`.
- `severity`: 5 = blocks release or certain legal exposure; 4 = must fix before release; 3 = should fix; 2 = minor; 1 = cosmetic.

---

## Input File Formats

### Show bible (`bible.yaml`)

```yaml
show: harbor-lights
characters:
  - id: maya
    name: Maya Reyes
    aliases: [May, Detective Reyes]
    gender: female
    pronouns: {en: she/her}
  - id: ada
    name: Ada Kovač
    aliases: ["the informant"]
    gender: female
    identity_hidden_until: S01E08       # the viewer learns who "the informant" is here
relationships:
  - between: [maya, leo]
    timeline:
      - {from: S01E01, kind: strangers}
      - {from: S01E04, kind: partners, register: {es: T, fr: T, de: T}}
secrets:
  - id: ada_is_informant
    description: Ada is the police informant
    revealed_on_screen: S01E08          # refined to the exact scene by extraction
fictional:
  brands: [Brightwave Energy, Kappa Cola]
  orgs: [Harbor City PD]
  places: [Harbor Warehouse]
story_overrides:
  - {scene: S01E05/sc/3, markers: [flashback], story_day: 0}
```

### Glossary (`glossary.csv`)

```csv
term,lang,approved_rendering,notes
Wren,es-419,Wren,Character name - never translate
the Hollow,es-419,el Hueco,
the Hollow,fr-FR,le Creux,
```

### Clearance log (`clearance_log.csv`)

```csv
item,kind,status,scope,notes
Acme Hardware,logo,pending,S01E03,Storefront in ep 3 - legal reviewing
Harbor Gazette,brand,cleared,,Licensed newspaper prop
```

---

## Object Storage Layout

```
nip-media/
  {show}/{episode}/source/{sha256}.{ext}          # scripts, picture, subtitles (content-addressed)
  {show}/{episode}/keyframes/{shot_id}_{n}.jpg
  {show}/{episode}/crops/{detection_id}.jpg
  {show}/show-level/{sha256}.{ext}                # bible, glossary, clearance log
nip-artifacts/
  cache/{key[0:2]}/{key}.json.zst                 # stage cache outputs
  runs/{run_id}/report.json
  runs/{run_id}/clearance_report.csv
  runs/{run_id}/plan.json
  eval/{benchmark_run_id}/...                     # see Evaluation
```

Buckets are configured by environment (`NIP_S3_ENDPOINT`, `NIP_S3_MEDIA_BUCKET`, `NIP_S3_ARTIFACT_BUCKET`), so the same code uses a local S3-compatible server in development and native object storage in the cloud.

---

## Cache Keys

```
cache_key = sha256(canonical_json({
  "stage": "loc.gender",
  "stage_version": 3,                 # bumped when the stage's code changes behavior
  "model_variant": "qwen3.5-4b-awq",
  "prompt_version": "loc.gender.v5",
  "params": {...},                    # thresholds and options that affect output
  "inputs": ["<sha256 of each consumed input, sorted>"]
}))
```

For retrieval-based units, `inputs` includes the hashes of the retrieved facts and scenes — the cache is keyed on what the unit actually read.
