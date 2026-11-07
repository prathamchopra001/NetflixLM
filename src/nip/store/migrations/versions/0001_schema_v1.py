"""Schema v1: every table in docs/data-model.md › Schema.

The DDL is transcribed from the doc and frozen here; later changes are new revisions.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

ID = "id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY"

DDL = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    "CREATE EXTENSION IF NOT EXISTS btree_gist",
    # --- content and timeline
    f"""CREATE TABLE show (
  {ID},
  slug text UNIQUE NOT NULL,
  title text NOT NULL
)""",
    f"""CREATE TABLE episode (
  {ID},
  show_id bigint NOT NULL REFERENCES show(id),
  season int NOT NULL,
  number int NOT NULL,
  episode_seq int NOT NULL,
  ref text NOT NULL,
  fps_num int,
  fps_den int,
  drop_frame bool,
  start_tc_frames int DEFAULT 0,
  duration_frames bigint,
  timeline_source text NOT NULL DEFAULT 'script_estimate',
  UNIQUE (show_id, season, number)
)""",
    f"""CREATE TABLE source_file (
  {ID},
  episode_id bigint REFERENCES episode(id),
  show_id bigint NOT NULL REFERENCES show(id),
  kind text NOT NULL,
  lang text,
  role text,
  format text NOT NULL,
  object_key text NOT NULL,
  sha256 char(64) NOT NULL,
  version_label text,
  declared_fps text,
  ingested_at timestamptz NOT NULL DEFAULT now()
)""",
    f"""CREATE TABLE scene (
  {ID},
  episode_id bigint NOT NULL REFERENCES episode(id),
  script_scene_no text NOT NULL,
  heading text NOT NULL,
  location_entity_id bigint,
  time_of_day text,
  markers text[] NOT NULL DEFAULT '{{}}',
  story_day int,
  story_seq int,
  story_inferred bool NOT NULL DEFAULT false,
  frames int8range,
  in_cut bool NOT NULL DEFAULT true,
  text_hash char(64) NOT NULL
)""",
    f"""CREATE TABLE script_line (
  {ID},
  scene_id bigint NOT NULL REFERENCES scene(id),
  seq int NOT NULL,
  kind text NOT NULL,
  speaker_entity_id bigint,
  text text NOT NULL,
  frames int8range
)""",
    f"""CREATE TABLE shot (
  {ID},
  episode_id bigint NOT NULL REFERENCES episode(id),
  scene_id bigint REFERENCES scene(id),
  frames int8range NOT NULL,
  setup_cluster int,
  keyframes jsonb NOT NULL
)""",
    f"""CREATE TABLE transcript_segment (
  {ID},
  episode_id bigint NOT NULL REFERENCES episode(id),
  frames int8range NOT NULL,
  lang text NOT NULL,
  text text NOT NULL,
  words jsonb NOT NULL,
  aligned_line_id bigint REFERENCES script_line(id)
)""",
    f"""CREATE TABLE subtitle_track (
  {ID},
  episode_id bigint NOT NULL REFERENCES episode(id),
  source_file_id bigint NOT NULL REFERENCES source_file(id),
  lang text NOT NULL,
  role text NOT NULL
)""",
    f"""CREATE TABLE subtitle_cue (
  {ID},
  track_id bigint NOT NULL REFERENCES subtitle_track(id),
  idx int NOT NULL,
  frames int8range NOT NULL,
  text text NOT NULL,
  aligned_source_cue_ids bigint[],
  UNIQUE (track_id, idx)
)""",
    "CREATE INDEX ix_script_line_frames ON script_line USING gist (frames)",
    "CREATE INDEX ix_shot_episode_frames ON shot USING gist (episode_id, frames)",
    "CREATE INDEX ix_transcript_segment_episode_frames"
    " ON transcript_segment USING gist (episode_id, frames)",
    "CREATE INDEX ix_subtitle_cue_track_frames ON subtitle_cue USING gist (track_id, frames)",
    # --- knowledge layer
    f"""CREATE TABLE entity (
  {ID},
  show_id bigint NOT NULL REFERENCES show(id),
  kind text NOT NULL,
  canonical_name text NOT NULL,
  attributes jsonb NOT NULL DEFAULT '{{}}',
  origin text NOT NULL,
  fictional bool,
  status text NOT NULL DEFAULT 'confirmed'
)""",
    """CREATE TABLE entity_alias (
  entity_id bigint NOT NULL REFERENCES entity(id),
  lang text NOT NULL DEFAULT 'any',
  alias text NOT NULL,
  kind text NOT NULL,
  occurrences int NOT NULL DEFAULT 0,
  PRIMARY KEY (entity_id, lang, alias)
)""",
    f"""CREATE TABLE fact_event (
  {ID},
  scene_id bigint NOT NULL REFERENCES scene(id),
  line_id bigint NOT NULL REFERENCES script_line(id),
  predicate text NOT NULL,
  subject_id bigint NOT NULL REFERENCES entity(id),
  object_id bigint REFERENCES entity(id),
  value jsonb,
  quote text NOT NULL,
  confidence real NOT NULL,
  work_unit_id bigint
)""",
    f"""CREATE TABLE fact (
  {ID},
  show_id bigint NOT NULL REFERENCES show(id),
  predicate text NOT NULL,
  subject_id bigint NOT NULL REFERENCES entity(id),
  object_id bigint REFERENCES entity(id),
  value jsonb,
  screen int8range NOT NULL,
  story int4range NOT NULL,
  source_event_ids bigint[] NOT NULL,
  confidence real NOT NULL,
  version int NOT NULL DEFAULT 1,
  status text NOT NULL DEFAULT 'active',
  supersedes bigint REFERENCES fact(id)
)""",
    "CREATE INDEX ix_fact_subject_predicate_story"
    " ON fact USING gist (subject_id, predicate, story)",
    "CREATE INDEX ix_fact_subject_predicate_screen"
    " ON fact USING gist (subject_id, predicate, screen)",
    """ALTER TABLE fact ADD CONSTRAINT fact_consolidated_no_overlap
  EXCLUDE USING gist (subject_id WITH =, predicate WITH =, object_id WITH =, story WITH &&)
  WHERE (status = 'active')""",
    # --- registries and retrieval
    f"""CREATE TABLE clearance_item (
  {ID},
  show_id bigint NOT NULL REFERENCES show(id),
  name text NOT NULL,
  kind text NOT NULL,
  status text NOT NULL,
  scope text,
  notes text,
  source_file_id bigint REFERENCES source_file(id)
)""",
    f"""CREATE TABLE scene_chunk (
  {ID},
  scene_id bigint NOT NULL REFERENCES scene(id),
  kind text NOT NULL,
  text text NOT NULL,
  embedding vector NOT NULL,
  embedder_variant text NOT NULL
)""",
    f"""CREATE TABLE detection (
  {ID},
  episode_id bigint NOT NULL REFERENCES episode(id),
  shot_id bigint REFERENCES shot(id),
  keyframe_n int,
  channel text NOT NULL,
  label text NOT NULL,
  text text,
  box real[4],
  confidence real NOT NULL,
  model_variant text NOT NULL
)""",
    # --- runs, plans, caching, coverage
    f"""CREATE TABLE plan (
  {ID},
  inventory jsonb NOT NULL,
  catalog_sha256 char(64) NOT NULL,
  objective text NOT NULL,
  pins jsonb NOT NULL DEFAULT '{{}}',
  decisions jsonb NOT NULL,
  amendments jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz NOT NULL DEFAULT now()
)""",
    f"""CREATE TABLE run (
  {ID},
  show_id bigint NOT NULL REFERENCES show(id),
  episode_ids bigint[] NOT NULL,
  agents text[] NOT NULL,
  languages text[],
  plan_id bigint REFERENCES plan(id),
  status text NOT NULL,
  code_version text NOT NULL,
  previous_run_id bigint REFERENCES run(id),
  queue_job_id bigint,
  requested_by text NOT NULL,
  started_at timestamptz,
  finished_at timestamptz
)""",
    f"""CREATE TABLE work_unit (
  {ID},
  run_id bigint NOT NULL REFERENCES run(id),
  stage text NOT NULL,
  unit_key text NOT NULL,
  cache_key char(64),
  status text NOT NULL,
  attempts int NOT NULL DEFAULT 0,
  error text,
  model_variant text,
  started_at timestamptz,
  finished_at timestamptz
)""",
    """CREATE TABLE stage_cache (
  cache_key char(64) PRIMARY KEY,
  stage text NOT NULL,
  artifact_key text NOT NULL,
  model_variant text,
  prompt_version text,
  created_at timestamptz NOT NULL DEFAULT now(),
  hits int NOT NULL DEFAULT 0
)""",
    """CREATE TABLE variant_calibration (
  variant text NOT NULL,
  gpu_name text NOT NULL,
  context int NOT NULL,
  peak_gb real NOT NULL,
  measured_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (variant, gpu_name, context)
)""",
    # --- flags, review, audit
    f"""CREATE TABLE flag (
  {ID},
  run_id bigint NOT NULL REFERENCES run(id),
  episode_id bigint NOT NULL REFERENCES episode(id),
  agent text NOT NULL,
  check_id text NOT NULL,
  category text NOT NULL,
  lang text,
  severity smallint NOT NULL CHECK (severity BETWEEN 1 AND 5),
  confidence real NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  tier text NOT NULL,
  title text NOT NULL,
  explanation text NOT NULL,
  suggested_fix text,
  fingerprint char(64) NOT NULL,
  produced_by jsonb NOT NULL,
  verification jsonb NOT NULL,
  merged_into bigint REFERENCES flag(id),
  status text NOT NULL DEFAULT 'open'
)""",
    f"""CREATE TABLE evidence (
  {ID},
  flag_id bigint NOT NULL REFERENCES flag(id),
  kind text NOT NULL,
  ref text NOT NULL,
  role text NOT NULL,
  frames int8range,
  lang text,
  quote text,
  crop jsonb
)""",
    f"""CREATE TABLE disposition (
  {ID},
  flag_fingerprint char(64) NOT NULL,
  flag_id bigint NOT NULL REFERENCES flag(id),
  action text NOT NULL,
  note text,
  actor text NOT NULL,
  at timestamptz NOT NULL DEFAULT now()
)""",
    f"""CREATE TABLE fact_correction (
  {ID},
  fact_id bigint NOT NULL REFERENCES fact(id),
  action text NOT NULL,
  new_value jsonb,
  reason text NOT NULL,
  actor text NOT NULL,
  at timestamptz NOT NULL DEFAULT now()
)""",
    f"""CREATE TABLE audit_event (
  {ID},
  at timestamptz NOT NULL DEFAULT now(),
  actor text NOT NULL,
  action text NOT NULL,
  target text NOT NULL,
  payload jsonb NOT NULL
)""",
]

TABLES = [
    "show", "episode", "source_file", "scene", "script_line", "shot", "transcript_segment",
    "subtitle_track", "subtitle_cue", "entity", "entity_alias", "fact_event", "fact",
    "clearance_item", "scene_chunk", "detection", "plan", "run", "work_unit", "stage_cache",
    "variant_calibration", "flag", "evidence", "disposition", "fact_correction", "audit_event",
]  # fmt: skip


def upgrade() -> None:
    for statement in DDL:
        op.execute(statement)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
