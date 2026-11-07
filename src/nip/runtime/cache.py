"""Stage cache (architecture.md › Incremental Re-runs, data-model.md › Cache Keys, D-004).

A work unit's output is stored under a key derived from what the unit read:

    key = sha256(canonical_json({stage, stage_version, model_variant, prompt_version, params,
                                 inputs: sorted hashes of the inputs the unit consumed}))

`StageCache.get` looks a key up before the unit's work (a hit bumps `stage_cache.hits`);
`StageCache.put` stores the output after it. The output is JSON, gzip-compressed, at
`nip-artifacts/cache/{key[0:2]}/{key}.json.gz`, plus one `stage_cache` row. Both are written in
their own short transaction (controller ruling, 2.0 review): the run itself is one transaction,
and a crash in a later episode must not throw away units already paid for (GPU extraction, OCR).
The cache is content-addressed, not per show or run: an identical scene in another show is a hit.

gzip, not the data model's zstd: zstandard is not installed and adding it needs an image rebuild
(DP-2.9B-2). ponytail: no eviction; `hits` and `created_at` are there for a later LRU sweep.
"""

import gzip
import hashlib
import json
import logging
from typing import Any

from sqlalchemy import Engine, select, update
from sqlalchemy.dialects.postgresql import insert

from nip.store import objects, schema

log = logging.getLogger(__name__)


def canonical(obj: Any) -> bytes:
    """Canonical JSON: sorted keys, no whitespace, non-JSON values (paths, enums) as str."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=str).encode()  # fmt: skip


def digest(obj: Any) -> str:
    """sha256 of `obj`: raw bytes as they are, anything else as canonical JSON."""
    return hashlib.sha256(obj if isinstance(obj, bytes) else canonical(obj)).hexdigest()


def key(
    stage: str,
    stage_version: str | int,
    model_variant: str | None,
    prompt_version: str | None,
    params: Any,
    inputs: list[str],
) -> str:
    return digest(
        {
            "stage": stage,
            "stage_version": str(stage_version),
            "model_variant": model_variant,
            "prompt_version": prompt_version,
            "params": params,
            "inputs": sorted(inputs),
        }
    )


def object_key(k: str) -> str:
    return f"cache/{k[:2]}/{k}.json.gz"


class StageCache:
    """`force`: every lookup misses (the run recomputes and overwrites the entries)."""

    def __init__(self, engine: Engine, s3: Any, force: bool = False) -> None:
        self.engine, self.s3, self.force = engine, s3, force

    def get(self, k: str) -> Any | None:
        """The cached output of key `k`, or None. A row whose object is gone is a miss."""
        if self.force:
            return None
        sc = schema.stage_cache
        with self.engine.begin() as c:
            art = c.execute(select(sc.c.artifact_key).where(sc.c.cache_key == k)).scalar()
            if art is None:
                return None
            try:
                body = self.s3.get_object(Bucket=objects.artifact_bucket(), Key=art)["Body"].read()
            except Exception as e:  # lost object: recompute rather than fail the unit
                log.warning("stage cache %s: object %s unreadable (%s): miss", k[:12], art, e)
                return None
            c.execute(update(sc).where(sc.c.cache_key == k).values(hits=sc.c.hits + 1))
        return json.loads(gzip.decompress(body))

    def put(
        self,
        k: str,
        stage: str,
        value: Any,
        model_variant: str | None = None,
        prompt_version: str | None = None,
    ) -> None:
        art = object_key(k)
        body = gzip.compress(canonical(value), mtime=0)
        objects.put_bytes(self.s3, objects.artifact_bucket(), art, body)
        row = {"cache_key": k, "stage": stage, "artifact_key": art,
               "model_variant": model_variant, "prompt_version": prompt_version}  # fmt: skip
        ins = insert(schema.stage_cache).values(row)
        with self.engine.begin() as c:
            c.execute(ins.on_conflict_do_update(index_elements=["cache_key"],
                                                set_={"artifact_key": art}))  # fmt: skip
