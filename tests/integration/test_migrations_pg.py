"""The migrations and the Core tables (`nip.store.schema`) must build the same database.

Builds two throwaway databases next to NIP_TEST_DATABASE_URL's — one with `alembic upgrade head`,
one with `metadata.create_all` — and compares their catalogs: columns (type, NOT NULL, default,
identity), every constraint's definition (PK, FK, UNIQUE, CHECK, EXCLUDE) and every index.
Needs a role that may CREATE DATABASE (the pgvector image's superuser).
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, make_url, text

from nip.store.db import database_url
from nip.store.schema import metadata

pytestmark = pytest.mark.integration

CATALOG = {
    "columns": """
        SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,
               pg_get_expr(d.adbin, d.adrelid), a.attidentity
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE n.nspname = 'public' AND c.relkind = 'r' AND a.attnum > 0
          AND NOT a.attisdropped AND c.relname <> 'alembic_version'""",
    "constraints": """
        SELECT c.relname, k.conname, pg_get_constraintdef(k.oid)
        FROM pg_constraint k
        JOIN pg_class c ON c.oid = k.conrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname <> 'alembic_version'""",
    "indexes": """
        SELECT tablename, indexname, indexdef FROM pg_indexes
        WHERE schemaname = 'public' AND tablename <> 'alembic_version'""",
    "extensions": "SELECT extname FROM pg_extension",
}


def _catalog(engine: Engine) -> dict[str, set[tuple[Any, ...]]]:
    with engine.connect() as conn:
        return {k: {tuple(r) for r in conn.execute(text(q))} for k, q in CATALOG.items()}


@contextmanager
def _scratch_db(admin_url: str, name: str) -> Iterator[str]:
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {name}"))
    try:
        yield make_url(admin_url).set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        admin.dispose()


def test_migration_matches_core_tables_and_downgrades(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("NIP_TEST_DATABASE_URL")
    if not url:
        pytest.skip("NIP_TEST_DATABASE_URL not set")
    monkeypatch.setenv("NIP_DATABASE_URL", url)
    admin_url = database_url()
    cfg = Config()
    cfg.set_main_option("script_location", "nip.store:migrations")

    with _scratch_db(admin_url, "nip_test_migrated") as mig_url, \
         _scratch_db(admin_url, "nip_test_core") as core_url:  # fmt: skip
        monkeypatch.setenv("NIP_DATABASE_URL", mig_url)
        command.upgrade(cfg, "head")
        migrated = create_engine(mig_url)

        core = create_engine(core_url)
        with core.begin() as conn:
            conn.execute(text("CREATE EXTENSION vector"))
            conn.execute(text("CREATE EXTENSION btree_gist"))
            metadata.create_all(conn)

        try:
            expected, actual = _catalog(core), _catalog(migrated)
            assert len(expected["columns"]) > 200  # the queries really see the schema
            for part in CATALOG:
                assert actual[part] - expected[part] == set(), f"only in migration: {part}"
                assert expected[part] - actual[part] == set(), f"only in schema.py: {part}"

            command.downgrade(cfg, "base")
            assert _catalog(migrated)["columns"] == set()
        finally:
            migrated.dispose()
            core.dispose()
