"""Object storage (data-model.md › Object Storage Layout): content-addressed sources, run artifacts.

`client()` is boto3's S3 client for NIP_S3_ENDPOINT (SeaweedFS locally, native S3 in the cloud).
Callers take the client as an argument, so tests pass a fake with `upload_file` and `put_object`.
"""

import hashlib
import os
from pathlib import Path
from typing import Any


def client() -> Any:
    import boto3  # ~0.3 s to import: only when objects are written

    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("NIP_S3_ENDPOINT") or None,  # empty: native cloud endpoint
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )


def media_bucket() -> str:
    return os.environ.get("NIP_S3_MEDIA_BUCKET", "nip-media")


def artifact_bucket() -> str:
    return os.environ.get("NIP_S3_ARTIFACT_BUCKET", "nip-artifacts")


def sha256_file(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def source_key(show: str, episode: str | None, sha: str, suffix: str) -> str:
    """`{show}/{episode}/source/{sha}.{ext}`, or `{show}/show-level/{sha}.{ext}` (bible etc.)."""
    where = f"{episode}/source" if episode else "show-level"
    return f"{show}/{where}/{sha}{suffix.lower()}"


def keyframe_key(show: str, episode: str, shot: int, n: int) -> str:
    """Shot = its index in the episode (the evidence-ref id, B-062), not the shot row id."""
    return f"{show}/{episode}/keyframes/{shot}_{n}.jpg"


def run_key(run_id: str, *parts: str) -> str:
    return "/".join(["runs", run_id, *parts])


def put_file(s3: Any, bucket: str, key: str, path: Path) -> None:
    """Upload `path` (multipart for big media). Keys are content-addressed, so a repeat is a no-op
    in effect; idempotency of rows is the store's job (source_file.sha256)."""
    s3.upload_file(str(path), bucket, key)


def put_bytes(s3: Any, bucket: str, key: str, data: bytes) -> None:
    s3.put_object(Bucket=bucket, Key=key, Body=data)
