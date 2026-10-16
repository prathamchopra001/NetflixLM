"""Applies the migrations to a real Postgres + pgvector and checks the Core tables match it.

Needs NIP_TEST_DATABASE_URL pointing at a throwaway database: the test drops every table.
"""

import os

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from nip.store.db import database_url
from nip.store.schema import metadata

pytestmark = pytest.mark.integration


def test_upgrade_matches_schema_and_downgrades(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("NIP_TEST_DATABASE_URL")
    if not url:
        pytest.skip("NIP_TEST_DATABASE_URL not set")
    monkeypatch.setenv("NIP_DATABASE_URL", url)
    cfg = Config()
    cfg.set_main_option("script_location", "nip.store:migrations")

    command.upgrade(cfg, "head")
    try:
        with create_engine(database_url()).connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), metadata)
        assert diff == []
    finally:
        command.downgrade(cfg, "base")
