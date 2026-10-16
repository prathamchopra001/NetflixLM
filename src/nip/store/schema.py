"""SQLAlchemy Core tables for schema v1 (docs/data-model.md › Schema).

Mirrors migrations/versions/0001_schema_v1.py; the integration test compares the two.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    SmallInteger,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import (
    ARRAY,
    CHAR,
    INT4RANGE,
    INT8RANGE,
    JSONB,
    REAL,
    TIMESTAMP,
    ExcludeConstraint,
)

metadata = MetaData()

TSTZ = TIMESTAMP(timezone=True)
SHA = CHAR(64)


def _id() -> Column[int]:
    return Column("id", BigInteger, Identity(always=True), primary_key=True)


def _fk(name: str, target: str, nullable: bool = False) -> Column[int]:
    return Column(name, BigInteger, ForeignKey(target), nullable=nullable)


# --- content and timeline

show = Table(
    "show", metadata,
    _id(),
    Column("slug", Text, nullable=False, unique=True),
    Column("title", Text, nullable=False),
)

episode = Table(
    "episode", metadata,
    _id(),
    _fk("show_id", "show.id"),
    Column("season", Integer, nullable=False),
    Column("number", Integer, nullable=False),
    Column("episode_seq", Integer, nullable=False),  # release order across the show
    Column("ref", Text, nullable=False),  # 'S01E03'
    Column("fps_num", Integer),
    Column("fps_den", Integer),
    Column("drop_frame", Boolean),
    Column("start_tc_frames", Integer, server_default=text("0")),
    Column("duration_frames", BigInteger),
    Column("timeline_source", Text, nullable=False, server_default="script_estimate"),
    UniqueConstraint("show_id", "season", "number"),
)

source_file = Table(
    "source_file", metadata,
    _id(),
    _fk("episode_id", "episode.id", nullable=True),  # null for show-level files
    _fk("show_id", "show.id"),
    Column("kind", Text, nullable=False),
    Column("lang", Text),
    Column("role", Text),
    Column("format", Text, nullable=False),
    Column("object_key", Text, nullable=False),
    Column("sha256", SHA, nullable=False),
    Column("version_label", Text),
    Column("declared_fps", Text),
    Column("ingested_at", TSTZ, nullable=False, server_default=text("now()")),
)

scene = Table(
    "scene", metadata,
    _id(),
    _fk("episode_id", "episode.id"),
    Column("script_scene_no", Text, nullable=False),
    Column("heading", Text, nullable=False),
    Column("location_entity_id", BigInteger),
    Column("time_of_day", Text),
    Column("markers", ARRAY(Text), nullable=False, server_default=text("'{}'")),
    Column("story_day", Integer),
    Column("story_seq", Integer),
    Column("story_inferred", Boolean, nullable=False, server_default=text("false")),
    Column("frames", INT8RANGE),
    Column("in_cut", Boolean, nullable=False, server_default=text("true")),
    Column("text_hash", SHA, nullable=False),
)

script_line = Table(
    "script_line", metadata,
    _id(),
    _fk("scene_id", "scene.id"),
    Column("seq", Integer, nullable=False),
    Column("kind", Text, nullable=False),
    Column("speaker_entity_id", BigInteger),
    Column("text", Text, nullable=False),
    Column("frames", INT8RANGE),
    Index("ix_script_line_frames", "frames", postgresql_using="gist"),
)

shot = Table(
    "shot", metadata,
    _id(),
    _fk("episode_id", "episode.id"),
    _fk("scene_id", "scene.id", nullable=True),
    Column("frames", INT8RANGE, nullable=False),
    Column("setup_cluster", Integer),
    Column("keyframes", JSONB, nullable=False),
    Index("ix_shot_episode_frames", "episode_id", "frames", postgresql_using="gist"),
)

transcript_segment = Table(
    "transcript_segment", metadata,
    _id(),
    _fk("episode_id", "episode.id"),
    Column("frames", INT8RANGE, nullable=False),
    Column("lang", Text, nullable=False),
    Column("text", Text, nullable=False),
    Column("words", JSONB, nullable=False),
    _fk("aligned_line_id", "script_line.id", nullable=True),
    Index(
        "ix_transcript_segment_episode_frames", "episode_id", "frames", postgresql_using="gist"
    ),
)

subtitle_track = Table(
    "subtitle_track", metadata,
    _id(),
    _fk("episode_id", "episode.id"),
    _fk("source_file_id", "source_file.id"),
    Column("lang", Text, nullable=False),
    Column("role", Text, nullable=False),
)

subtitle_cue = Table(
    "subtitle_cue", metadata,
    _id(),
    _fk("track_id", "subtitle_track.id"),
    Column("idx", Integer, nullable=False),
    Column("frames", INT8RANGE, nullable=False),
    Column("text", Text, nullable=False),
    Column("aligned_source_cue_ids", ARRAY(BigInteger)),
    UniqueConstraint("track_id", "idx"),
    Index("ix_subtitle_cue_track_frames", "track_id", "frames", postgresql_using="gist"),
)

# --- knowledge layer

entity = Table(
    "entity", metadata,
    _id(),
    _fk("show_id", "show.id"),
    Column("kind", Text, nullable=False),
    Column("canonical_name", Text, nullable=False),
    Column("attributes", JSONB, nullable=False, server_default=text("'{}'")),
    Column("origin", Text, nullable=False),
    Column("fictional", Boolean),
    Column("status", Text, nullable=False, server_default="confirmed"),
)

entity_alias = Table(
    "entity_alias", metadata,
    _fk("entity_id", "entity.id"),
    Column("lang", Text, nullable=False, server_default="any"),
    Column("alias", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("occurrences", Integer, nullable=False, server_default=text("0")),
    PrimaryKeyConstraint("entity_id", "lang", "alias"),
)

fact_event = Table(
    "fact_event", metadata,
    _id(),
    _fk("scene_id", "scene.id"),
    _fk("line_id", "script_line.id"),
    Column("predicate", Text, nullable=False),
    _fk("subject_id", "entity.id"),
    _fk("object_id", "entity.id", nullable=True),
    Column("value", JSONB),
    Column("quote", Text, nullable=False),
    Column("confidence", REAL, nullable=False),
    Column("work_unit_id", BigInteger),
)

fact = Table(
    "fact", metadata,
    _id(),
    _fk("show_id", "show.id"),
    Column("predicate", Text, nullable=False),
    _fk("subject_id", "entity.id"),
    _fk("object_id", "entity.id", nullable=True),
    Column("value", JSONB),
    Column("screen", INT8RANGE, nullable=False),
    Column("story", INT4RANGE, nullable=False),
    Column("source_event_ids", ARRAY(BigInteger), nullable=False),
    Column("confidence", REAL, nullable=False),
    Column("version", Integer, nullable=False, server_default=text("1")),
    Column("status", Text, nullable=False, server_default="active"),
    _fk("supersedes", "fact.id", nullable=True),
    Index("ix_fact_subject_predicate_story", "subject_id", "predicate", "story",
          postgresql_using="gist"),
    Index("ix_fact_subject_predicate_screen", "subject_id", "predicate", "screen",
          postgresql_using="gist"),
    ExcludeConstraint(
        ("subject_id", "="), ("predicate", "="), ("object_id", "="), ("story", "&&"),
        name="fact_consolidated_no_overlap",
        using="gist",
        where=text("status = 'active'"),
    ),
)

# --- registries and retrieval

clearance_item = Table(
    "clearance_item", metadata,
    _id(),
    _fk("show_id", "show.id"),
    Column("name", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("scope", Text),
    Column("notes", Text),
    _fk("source_file_id", "source_file.id", nullable=True),
)

scene_chunk = Table(
    "scene_chunk", metadata,
    _id(),
    _fk("scene_id", "scene.id"),
    Column("kind", Text, nullable=False),
    Column("text", Text, nullable=False),
    # Untyped dimension so embedder variants can differ by Plan; HNSW indexes are partial
    # expression indexes per variant, added when an embedder ships.
    Column("embedding", Vector(), nullable=False),
    Column("embedder_variant", Text, nullable=False),
)

detection = Table(
    "detection", metadata,
    _id(),
    _fk("episode_id", "episode.id"),
    _fk("shot_id", "shot.id", nullable=True),
    Column("keyframe_n", Integer),
    Column("channel", Text, nullable=False),
    Column("label", Text, nullable=False),
    Column("text", Text),
    Column("box", ARRAY(REAL, dimensions=1)),  # normalized [x, y, w, h]
    Column("confidence", REAL, nullable=False),
    Column("model_variant", Text, nullable=False),
)

# --- runs, plans, caching, coverage

plan = Table(
    "plan", metadata,
    _id(),
    Column("inventory", JSONB, nullable=False),
    Column("catalog_sha256", SHA, nullable=False),
    Column("objective", Text, nullable=False),
    Column("pins", JSONB, nullable=False, server_default=text("'{}'")),
    Column("decisions", JSONB, nullable=False),
    Column("amendments", JSONB, nullable=False, server_default=text("'[]'")),
    Column("created_at", TSTZ, nullable=False, server_default=text("now()")),
)

run = Table(
    "run", metadata,
    _id(),
    _fk("show_id", "show.id"),
    Column("episode_ids", ARRAY(BigInteger), nullable=False),
    Column("agents", ARRAY(Text), nullable=False),
    Column("languages", ARRAY(Text)),
    _fk("plan_id", "plan.id", nullable=True),
    Column("status", Text, nullable=False),
    Column("code_version", Text, nullable=False),
    _fk("previous_run_id", "run.id", nullable=True),
    Column("queue_job_id", BigInteger),
    Column("requested_by", Text, nullable=False),
    Column("started_at", TSTZ),
    Column("finished_at", TSTZ),
)

work_unit = Table(
    "work_unit", metadata,
    _id(),
    _fk("run_id", "run.id"),
    Column("stage", Text, nullable=False),
    Column("unit_key", Text, nullable=False),
    Column("cache_key", SHA),
    Column("status", Text, nullable=False),
    Column("attempts", Integer, nullable=False, server_default=text("0")),
    Column("error", Text),
    Column("model_variant", Text),
    Column("started_at", TSTZ),
    Column("finished_at", TSTZ),
)

stage_cache = Table(
    "stage_cache", metadata,
    Column("cache_key", SHA, primary_key=True),
    Column("stage", Text, nullable=False),
    Column("artifact_key", Text, nullable=False),
    Column("model_variant", Text),
    Column("prompt_version", Text),
    Column("created_at", TSTZ, nullable=False, server_default=text("now()")),
    Column("hits", Integer, nullable=False, server_default=text("0")),
)

variant_calibration = Table(
    "variant_calibration", metadata,
    Column("variant", Text, nullable=False),
    Column("gpu_name", Text, nullable=False),
    Column("context", Integer, nullable=False),
    Column("peak_gb", REAL, nullable=False),
    Column("measured_at", TSTZ, nullable=False, server_default=text("now()")),
    PrimaryKeyConstraint("variant", "gpu_name", "context"),
)

# --- flags, review, audit

flag = Table(
    "flag", metadata,
    _id(),
    _fk("run_id", "run.id"),
    _fk("episode_id", "episode.id"),
    Column("agent", Text, nullable=False),
    Column("check_id", Text, nullable=False),
    Column("category", Text, nullable=False),
    Column("lang", Text),
    Column("severity", SmallInteger, CheckConstraint("severity BETWEEN 1 AND 5"), nullable=False),
    Column("confidence", REAL, CheckConstraint("confidence BETWEEN 0 AND 1"), nullable=False),
    Column("tier", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("explanation", Text, nullable=False),
    Column("suggested_fix", Text),
    Column("fingerprint", SHA, nullable=False),
    Column("produced_by", JSONB, nullable=False),
    Column("verification", JSONB, nullable=False),
    _fk("merged_into", "flag.id", nullable=True),
    Column("status", Text, nullable=False, server_default="open"),
)

evidence = Table(
    "evidence", metadata,
    _id(),
    _fk("flag_id", "flag.id"),
    Column("kind", Text, nullable=False),
    Column("ref", Text, nullable=False),
    Column("role", Text, nullable=False),
    Column("frames", INT8RANGE),
    Column("lang", Text),
    Column("quote", Text),
    Column("crop", JSONB),
)

disposition = Table(
    "disposition", metadata,
    _id(),
    Column("flag_fingerprint", SHA, nullable=False),
    _fk("flag_id", "flag.id"),
    Column("action", Text, nullable=False),
    Column("note", Text),
    Column("actor", Text, nullable=False),
    Column("at", TSTZ, nullable=False, server_default=text("now()")),
)

fact_correction = Table(
    "fact_correction", metadata,
    _id(),
    _fk("fact_id", "fact.id"),
    Column("action", Text, nullable=False),
    Column("new_value", JSONB),
    Column("reason", Text, nullable=False),
    Column("actor", Text, nullable=False),
    Column("at", TSTZ, nullable=False, server_default=text("now()")),
)

# Append-only: the application role gets INSERT but not UPDATE/DELETE.
audit_event = Table(
    "audit_event", metadata,
    _id(),
    Column("at", TSTZ, nullable=False, server_default=text("now()")),
    Column("actor", Text, nullable=False),
    Column("action", Text, nullable=False),
    Column("target", Text, nullable=False),
    Column("payload", JSONB, nullable=False),
)
