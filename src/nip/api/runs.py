"""`GET /runs/{run_id}` and `GET /runs/{run_id}/diff?against=previous` (api-contracts.md › Runs).

Any authenticated role may read them (Roles: reading a run is not an operator action).

The diff compares a run with `run.previous_run_id` (the show's last run over the same episodes,
set by `runs.create_run`) by flag fingerprint (data-model.md › Fingerprints): a fingerprint only
in this run is new, one only in the previous run is resolved, one in both is unchanged. It adds
the work done (`units_rerun`: units not served from the stage cache; `units_cached`) and the
changed inputs: source files ingested between the two runs' starts, and for a script the scenes
whose extraction unit's cache key differs from the previous run's (or that are new), i.e. the
scenes whose text (or bible context) changed.

Status changes keep no identity of their own (2.close note, controller addition iii): when a
clearance occurrence that was `unknown` is logged (now `pending`, `denied`, ...), its flag cites
the logged item `clr/{id}`, so its fingerprint changes and the diff shows the old flag resolved
and a new one. That is deliberate: the finding's statement changed ("not in the clearance log" vs
"pending clearance"), so it needs a fresh review, and a disposition of the old statement must not
carry over to the new one. The diff has no fourth "changed" class (the spec has three).
"""

import json
import re
from collections import Counter
from functools import lru_cache
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Connection, Engine, create_engine, select

from nip.api.auth import current_user
from nip.api.errors import ApiError
from nip.contracts.flag import CHECK_OWNER, CheckId
from nip.store import objects, schema
from nip.store.db import database_url
from nip.store.runs import db_id, ext_id

router = APIRouter(prefix="/runs", tags=["runs"], dependencies=[Depends(current_user)])
EXTRACT = "knowledge.extract"  # its units are scenes: `S01E03/sc/12`
CHECK_IDS = {str(c) for c in CheckId}


@lru_cache
def engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True)


def s3() -> Any:
    return objects.client()


def _run(conn: Connection, run_id: str) -> Any:
    row = None
    if re.fullmatch(r"run_\d+", run_id):
        r = schema.run
        row = conn.execute(select(r).where(r.c.id == db_id(run_id))).one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", f"Unknown run {run_id}")
    return row


def _units(conn: Connection, rid: int) -> list[Any]:
    wu = schema.work_unit
    return list(conn.execute(select(wu).where(wu.c.run_id == rid).order_by(wu.c.id)))


def _mode(s3c: Any, run_id: str) -> str | None:
    """The Plan's mode from the published plan.json (not stored in the `plan` row)."""
    key = objects.run_key(run_id, "plan.json")
    try:
        body = s3c.get_object(Bucket=objects.artifact_bucket(), Key=key)["Body"].read()
        mode: str | None = json.loads(body).get("mode")
        return mode
    except (
        Exception
    ):  # not published (running or failed run) or storage down: the rest still answers
        return None


def run_status(conn: Connection, s3c: Any, run_id: str) -> dict[str, Any]:
    run = _run(conn, run_id)
    units = _units(conn, run.id)
    stages: dict[str, list[Any]] = {}
    for u in units:
        stages.setdefault(u.stage, []).append(u)
    coverage: dict[str, dict[str, Any]] = {}
    for u in units:
        if u.stage not in CHECK_IDS:
            continue
        c = coverage.setdefault(
            str(CHECK_OWNER[u.stage.split(".")[0]][0]),
            {"units_total": 0, "done": 0, "failed": 0, "gaps": []},
        )
        c["units_total"] += 1
        if u.status == "failed":
            c["failed"] += 1
            c["gaps"].append(f"{u.unit_key}: {u.error}")
        else:
            c["done"] += 1
    return {
        "run_id": run_id,
        "status": run.status,
        "plan_id": ext_id("plan", run.plan_id) if run.plan_id else None,
        "mode": _mode(s3c, run_id),
        "previous_run_id": ext_id("run", run.previous_run_id) if run.previous_run_id else None,
        "stages": [
            {
                "stage": stage,
                "status": "failed" if all(u.status == "failed" for u in us) else "done",
                "units": len(us),
                "cached": sum(u.status == "cached" for u in us),
                "failed": sum(u.status == "failed" for u in us),
            }
            for stage, us in stages.items()
        ],
        "coverage": coverage,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


def _flags(conn: Connection, rid: int) -> dict[str, list[int]]:
    """fingerprint -> flag ids of the run (merged duplicates left out)."""
    f = schema.flag
    out: dict[str, list[int]] = {}
    for fid, fp in conn.execute(
        select(f.c.id, f.c.fingerprint)
        .where(f.c.run_id == rid, f.c.merged_into.is_(None))
        .order_by(f.c.id)
    ):
        out.setdefault(fp, []).append(fid)
    return out


def _changed_inputs(conn: Connection, run: Any, prev: Any, units: list[Any]) -> list[str]:
    sf, ep = schema.source_file, schema.episode
    refs = dict(conn.execute(select(ep.c.id, ep.c.ref).where(ep.c.id.in_(run.episode_ids))).all())
    files = conn.execute(
        select(sf)
        .where(
            sf.c.show_id == run.show_id,
            sf.c.episode_id.in_(run.episode_ids) | sf.c.episode_id.is_(None),
            sf.c.ingested_at <= run.started_at,
        )
        .order_by(sf.c.id)
    ).all()
    before = {u.unit_key: u.cache_key for u in _units(conn, prev.id) if u.stage == EXTRACT}
    changed: dict[str, list[str]] = {}  # episode ref -> scene numbers whose extraction key changed
    for u in units:
        if u.stage == EXTRACT and u.cache_key and before.get(u.unit_key) != u.cache_key:
            ref, _, no = u.unit_key.partition("/sc/")
            changed.setdefault(ref, []).append(no)
    out = []
    for f in files:
        if prev.started_at is None or f.ingested_at <= prev.started_at:
            continue
        same = [g for g in files if g.id < f.id and (g.episode_id, g.kind, g.lang) ==
                (f.episode_id, f.kind, f.lang)]  # fmt: skip
        where = refs.get(f.episode_id, "show")
        what = f"{f.kind} {f.lang}" if f.lang else f.kind
        label = f.version_label or ext_id("src", f.id)
        old = (same[-1].version_label or ext_id("src", same[-1].id)) if same else None
        line = f"{where} {what} {old} → {label}" if old else f"{where} {what} {label} added"
        if f.kind == "script" and changed.get(where):
            line += f" (scenes {', '.join(changed[where])} changed)"
        out.append(line)
    return out


def run_diff(conn: Connection, run_id: str) -> dict[str, Any]:
    """The run against its previous run (module docstring). With no previous run every flag is
    new and `against` is null."""
    run = _run(conn, run_id)
    units = _units(conn, run.id)
    counts = Counter(u.status == "cached" for u in units)
    now = _flags(conn, run.id)
    prev = None
    if run.previous_run_id is not None:
        prev = conn.execute(select(schema.run).where(schema.run.c.id == run.previous_run_id)).one()
    before = _flags(conn, prev.id) if prev is not None else {}
    return {
        "run_id": run_id,
        "against": ext_id("run", prev.id) if prev is not None else None,
        "changed_inputs": _changed_inputs(conn, run, prev, units) if prev is not None else [],
        "new_flags": [ext_id("flg", i) for fp, ids in now.items() if fp not in before for i in ids],
        "resolved_flags": [
            ext_id("flg", i) for fp, ids in before.items() if fp not in now for i in ids
        ],
        "unchanged_flags": sum(len(ids) for fp, ids in now.items() if fp in before),
        "units_rerun": counts[False],
        "units_cached": counts[True],
    }


Db = Annotated[Engine, Depends(engine)]


@router.get("/{run_id}")
def get_run(run_id: str, db: Db, s3c: Annotated[Any, Depends(s3)]) -> dict[str, Any]:
    with db.connect() as conn:
        return run_status(conn, s3c, run_id)


@router.get("/{run_id}/diff")
def get_diff(
    run_id: str, db: Db, against: Annotated[Literal["previous"], Query()] = "previous"
) -> dict[str, Any]:
    with db.connect() as conn:
        return run_diff(conn, run_id)
