"""Schema v2 (Phase 2): the scene vector index and the script speaker.

- `script_line.speaker`: the script's character cue (2.0 dropped it; `speaker_entity_id` is
  resolved later by 2.1).
- `scene_chunk`: one chunk per (scene, kind, embedder variant), and one HNSW partial expression
  index per embedder variant (data-model.md: pgvector indexes need a fixed dimension, and HNSW
  stops at 2,000, so every variant is 1,024-d, larger embedders truncated by Matryoshka).

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

VARIANTS = ["qwen3-embedding-0.6b", "qwen3-embedding-8b"]


def _index(variant: str) -> str:
    return "ix_scene_chunk_hnsw_" + variant.replace("-", "_").replace(".", "_")


def upgrade() -> None:
    op.execute("ALTER TABLE script_line ADD COLUMN speaker text")
    op.execute(
        "ALTER TABLE scene_chunk"
        " ADD CONSTRAINT scene_chunk_scene_id_kind_embedder_variant_key"
        " UNIQUE (scene_id, kind, embedder_variant)"
    )
    for v in VARIANTS:
        op.execute(
            f"CREATE INDEX {_index(v)} ON scene_chunk"
            " USING hnsw ((embedding::vector(1024)) vector_cosine_ops)"
            f" WHERE embedder_variant = '{v}'"
        )


def downgrade() -> None:
    for v in VARIANTS:
        op.execute(f"DROP INDEX {_index(v)}")
    op.execute(
        "ALTER TABLE scene_chunk DROP CONSTRAINT scene_chunk_scene_id_kind_embedder_variant_key"
    )
    op.execute("ALTER TABLE script_line DROP COLUMN speaker")
