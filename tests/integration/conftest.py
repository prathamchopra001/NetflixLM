"""Store fixtures (R15): `pg` is an Engine on a throwaway database built from `nip.store.schema`,
emptied after each test; it skips without NIP_TEST_DATABASE_URL (a fail under NIP_CI=1).
`s3` is an in-memory stand-in for the boto3 S3 client.

Locally: `docker compose -f compose.yaml -f compose.dev.yaml up -d postgres` and
NIP_TEST_DATABASE_URL=postgresql://nip:change_me@127.0.0.1:55432/nip (a role that may CREATE
DATABASE). Each session gets its own database, so concurrent test runs do not collide.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, make_url, text

from nip.store.schema import metadata


class FakeS3:
    """The two boto3 S3 calls the store makes, kept in a dict of (bucket, key) -> bytes."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        self.objects[bucket, key] = Path(filename).read_bytes()

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:  # noqa: N803 (boto3)
        self.objects[Bucket, Key] = Body


@pytest.fixture
def s3() -> FakeS3:
    return FakeS3()


@pytest.fixture(scope="session")
def pg_engine() -> Iterator[Engine]:
    url = os.environ.get("NIP_TEST_DATABASE_URL")
    if not url:
        pytest.skip("NIP_TEST_DATABASE_URL not set")
    admin_url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    name = f"nip_test_{os.getpid()}"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {name}"))
    engine = create_engine(make_url(admin_url).set(database=name))
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION vector"))
            conn.execute(text("CREATE EXTENSION btree_gist"))
            metadata.create_all(conn)
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        admin.dispose()


@pytest.fixture
def pg(pg_engine: Engine) -> Iterator[Engine]:
    yield pg_engine
    tables = ", ".join(f'"{t.name}"' for t in metadata.sorted_tables)
    with pg_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
