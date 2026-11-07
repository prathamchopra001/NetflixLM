"""Run persistence: plan, run, work_unit, flag + evidence rows, fingerprints, external ids.

External ids (api-contracts.md › Conventions) are the bigint identity with a prefix:
`ext_id("run", 912) == "run_912"`, `db_id("run_912") == 912` (flg_, plan_, src_ alike).
"""

import hashlib
import subprocess
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection, insert, select, update
from sqlalchemy.dialects.postgresql import Range

from nip.contracts import refs
from nip.contracts.flag import EvidenceKind, Flag
from nip.contracts.inventory import HardwareInventory
from nip.contracts.plan import Plan
from nip.store import schema

# Refs that change when knowledge or ASR is re-extracted (R13): never part of a fingerprint.
CHURNING = {EvidenceKind.FACT, EvidenceKind.TRANSCRIPT_SEGMENT}


def ext_id(prefix: str, n: int) -> str:
    return f"{prefix}_{n}"


def db_id(ext: str) -> int:
    return int(ext.rpartition("_")[2])


def stable_refs(flag: Flag) -> list[str]:
    """The flag's evidence refs that survive re-extraction (scene, line, shot, kf, cue, clr)."""
    return sorted({e.ref for e in flag.evidence if refs.parse(e.ref).kind not in CHURNING})


def fingerprint(flag: Flag) -> str:
    """sha256(check + sorted stable evidence refs + lang): a flag's identity across runs (R13).

    ValueError when the flag cites no stable ref: its fingerprint would be sha256(check + lang),
    shared by every such flag of the check in every episode (controller ruling, 2.0 review I3).
    """
    stable = stable_refs(flag)
    if not stable:
        raise ValueError(f"{flag.check} flag {flag.title!r} cites no stable evidence ref")
    return hashlib.sha256("\n".join([flag.check, *stable, flag.lang or ""]).encode()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def code_version() -> str:
    """The git SHA of the running code, `-dirty` when tracked files differ from it ("unknown"
    outside a checkout, e.g. in the image)."""
    try:
        dirty = _git("status", "--porcelain", "--untracked-files=no").strip()
        return _git("rev-parse", "HEAD").strip() + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def create_plan(conn: Connection, plan: Plan, inventory: HardwareInventory) -> int:
    pid: int = conn.execute(
        insert(schema.plan)
        .values(
            inventory=inventory.model_dump(mode="json"),
            catalog_sha256=plan.catalog_sha256,
            objective=plan.objective.value,
            pins={str(k): v for k, v in plan.pins.items()},
            decisions={str(k): d.model_dump(mode="json") for k, d in plan.decisions.items()},
            amendments=[a.model_dump(mode="json", by_alias=True) for a in plan.amendments],
        )
        .returning(schema.plan.c.id)
    ).scalar_one()
    return pid


def create_run(
    conn: Connection,
    *,
    show_id: int,
    episode_ids: Sequence[int],
    agents: Sequence[str],
    languages: Sequence[str],
    plan_id: int,
    requested_by: str,
) -> int:
    """A `running` run; `previous_run_id` is the show's last run over the same episodes."""
    r = schema.run
    ids = sorted(episode_ids)  # stored sorted, so --episodes order never hides the previous run
    prev = conn.execute(
        select(r.c.id)
        .where(r.c.show_id == show_id, r.c.episode_ids == ids)
        .order_by(r.c.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    rid: int = conn.execute(
        insert(r)
        .values(
            show_id=show_id,
            episode_ids=ids,
            agents=list(agents),
            languages=list(languages),
            plan_id=plan_id,
            status="running",
            code_version=code_version(),
            previous_run_id=prev,
            requested_by=requested_by,
            started_at=datetime.now(UTC),
        )
        .returning(r.c.id)
    ).scalar_one()
    return rid


def finish_run(conn: Connection, run_id: int, status: str) -> None:
    conn.execute(
        update(schema.run)
        .where(schema.run.c.id == run_id)
        .values(status=status, finished_at=datetime.now(UTC))
    )


def add_work_units(conn: Connection, run_id: int, rows: Iterable[dict[str, Any]]) -> None:
    """`rows`: stage, unit_key, status (done | failed), error, model_variant, started_at,
    finished_at."""
    rows = [{"run_id": run_id, "attempts": 1, **r} for r in rows]
    if rows:
        conn.execute(insert(schema.work_unit), rows)


def save_flags(conn: Connection, run_id: int, episode_id: int, flags: Iterable[Flag]) -> list[Flag]:
    """Insert flags + evidence; returns the flags with their `flg_` ids."""
    out = []
    for f in flags:
        fid = conn.execute(
            insert(schema.flag)
            .values(
                run_id=run_id,
                episode_id=episode_id,
                agent=f.agent.value,
                check_id=f.check.value,
                category=f.category.value,
                lang=f.lang,
                severity=f.severity,
                confidence=f.confidence,
                tier=f.tier.value,
                title=f.title,
                explanation=f.explanation,
                suggested_fix=f.suggested_fix,
                fingerprint=fingerprint(f),
                produced_by=f.produced_by.model_dump(mode="json"),
                verification=f.verification.model_dump(mode="json"),
                status=f.status.value,
            )
            .returning(schema.flag.c.id)
        ).scalar_one()
        conn.execute(
            insert(schema.evidence),
            [
                {
                    "flag_id": fid,
                    "kind": e.kind.value,
                    "ref": e.ref,
                    "role": e.role.value,
                    "frames": Range(*e.frames) if e.frames else None,
                    "lang": e.lang,
                    "quote": e.quote,
                    "crop": e.crop.model_dump(mode="json") if e.crop else None,
                }
                for e in f.evidence
            ],
        )
        out.append(f.model_copy(update={"id": ext_id("flg", fid)}))
    return out
