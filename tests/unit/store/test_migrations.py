import os
import re
import subprocess
import sys
from pathlib import Path

from nip.store.schema import metadata

REPO = Path(__file__).parents[3]


def test_upgrade_renders_offline_sql() -> None:
    env = {k: v for k, v in os.environ.items() if k != "NIP_DATABASE_URL"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=REPO, env=env, capture_output=True, text=True, check=True,
    )  # fmt: skip
    created = set(re.findall(r"CREATE TABLE (\w+)", result.stdout)) - {"alembic_version"}
    # The frozen migration and the Core tables describe the same schema.
    assert created == set(metadata.tables)
    assert "CREATE EXTENSION IF NOT EXISTS vector" in result.stdout
    assert "embedding vector NOT NULL" in result.stdout
    assert "EXCLUDE USING gist" in result.stdout
