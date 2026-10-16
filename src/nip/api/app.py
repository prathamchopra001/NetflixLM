"""FastAPI skeleton: health, readiness and the caller's identity (domain routes come later)."""

import os
import urllib.request
from typing import Annotated, Any

import boto3
from botocore.config import Config
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlalchemy import create_engine, text

from nip.api.auth import current_user
from nip.store.db import database_url

system = APIRouter(tags=["system"])
v1 = APIRouter(prefix="/api/v1")


@system.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _postgres() -> None:
    engine = create_engine(database_url(), connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    finally:
        engine.dispose()


def _object_storage() -> None:
    cfg = Config(connect_timeout=3, read_timeout=3, retries={"max_attempts": 1})
    # endpoint empty/unset = the cloud provider's native endpoint (docs/project-structure.md)
    boto3.client(
        "s3", endpoint_url=os.environ.get("NIP_S3_ENDPOINT") or None, config=cfg
    ).list_buckets()


def _ray() -> None:
    # The dashboard head's GCS health route: avoids starting a Ray client inside the API process.
    url = os.environ.get("NIP_RAY_DASHBOARD_URL", "http://ray-head:8265") + "/api/gcs_healthz"
    urllib.request.urlopen(url, timeout=3).close()  # noqa: S310 (fixed http URL from our env)


@system.get("/readyz")
def readyz() -> dict[str, str]:
    """Postgres, object storage and the Ray cluster; 503 naming whichever is down."""
    status, down = {}, False
    for name, probe in (
        ("postgres", _postgres),
        ("object_storage", _object_storage),
        ("ray", _ray),
    ):
        try:
            probe()
            status[name] = "ok"
        except Exception as e:  # any failure = not ready; report the type, not connection strings
            status[name], down = f"down: {type(e).__name__}", True
    if down:
        raise HTTPException(503, status)
    return status


@v1.get("/me")
def me(user: Annotated[dict[str, Any], Depends(current_user)]) -> dict[str, Any]:
    return user


def create_app() -> FastAPI:
    app = FastAPI(title="nip", version="0.1.0")
    app.include_router(system)
    app.include_router(system, prefix="/api/v1")  # reachable behind the UI's /api proxy too
    app.include_router(v1)
    return app
