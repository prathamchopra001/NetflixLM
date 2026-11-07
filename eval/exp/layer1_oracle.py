"""2.3 benchmark: the Layer 1 plot rules on the 2.9A injected synthetic show with oracle facts.

Loads one injected show (`eval/synthetic` output: Fountain scripts + `truth.json`) into a throwaway
Postgres database, writes the facts of `truth.json` as consolidated `fact` rows (the way 2.1's
consolidation does: events merged per interval rule), runs the four Layer 1 checks with
verification, and writes the flags as JSONL for `nip eval run` (variant `oracle-facts`).

    uv run python -m eval.exp.layer1_oracle --flags data/layer1/flags/seed1.jsonl \
        --show-dir data/layer1/inject/mvp/seed1/synthetic-show/injected
"""

import json
import os
import time
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from psycopg.types.range import Range
from sqlalchemy import Engine, create_engine, insert, make_url, select, text, update

from eval.synthetic import Show, read_show
from nip.agents.base import run_check
from nip.agents.script_critic import CHECKS
from nip.agents.script_critic.layer1 import SqlRule
from nip.contracts import ProducedBy
from nip.pipeline import require_stable_refs
from nip.store import schema
from nip.store.ingest import ingest_files
from nip.store.load import load_timeline
from nip.verification.verify import verify

SLUG = "synthetic-show"
MARKERS = {"flashback": ["flashback"], "same_time": ["intercut"]}


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        self.objects[bucket, key] = Path(filename).read_bytes()

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:  # noqa: N803 (boto3)
        self.objects[Bucket, Key] = Body


Event = tuple[
    str, str, int, str, dict[str, Any] | None
]  # episode, scene no, line seq, quote, value


def consolidate(show: Show, gone_as: str | None = None) -> list[dict[str, Any]]:
    """Fact specs from the truth facts: predicate, subject, object, value, story (lo, hi), events.

    A stand-in for 2.1's consolidation (rules-only ceiling, not 2.1's semantics). `gone_as`
    writes every `destroyed` prop state as that state instead (e.g. `lost`).

    present_at and references are points ([seq, seq+1), merged per subject/object/seq); learns,
    holds (a character's events of one prop, uses included) and state are open-ended from their
    first event (data-model.md > consolidation rules). setup/payoff/etc. are not Layer 1 inputs.
    """
    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    for ep, scenes in show.episodes.items():
        for sc in scenes:
            for n, line in enumerate(sc.lines, 1):
                for f in line.facts:
                    fv = (
                        {**(f.value or {}), "state": gone_as}
                        if gone_as and (f.value or {}).get("state") == "destroyed"
                        else f.value
                    )
                    seq, ev = sc.story_seq, (ep, sc.no, n, f.quote, fv)
                    if f.predicate in ("present_at", "references"):
                        key: tuple[Any, ...] = (f.predicate, f.subject, f.object, seq)
                        story: tuple[int, int | None] = (seq, seq + 1)
                        value = None
                    elif f.predicate in ("learns", "holds"):
                        key, story, value = (f.predicate, f.subject, f.object), (seq, None), None
                    elif f.predicate == "state":
                        value = {"state": (fv or {}).get("state")}
                        key, story = (f.predicate, f.subject, value["state"]), (seq, None)
                    else:
                        continue
                    g = groups.setdefault(
                        key,
                        {"predicate": f.predicate, "subject": f.subject, "object": f.object,
                         "value": value, "story": story, "events": []},
                    )  # fmt: skip
                    g["story"] = (min(g["story"][0], story[0]), story[1])
                    g["events"].append(ev)
    return list(groups.values())


def build_store(engine: Engine, show_dir: Path, show: Show, gone_as: str | None = None) -> None:
    s3 = FakeS3()
    with engine.begin() as conn:
        for ep in show.episodes:
            ingest_files(
                conn, s3, show=SLUG, episode=ep, files=[(None, show_dir / f"{ep}.fountain")]
            )
        show_id = conn.execute(select(schema.show.c.id)).scalar_one()
        eps = {r.ref: r.id for r in conn.execute(select(schema.episode))}
        scene = {}
        for ep, scenes in show.episodes.items():
            for sc in scenes:
                sid = conn.execute(
                    update(schema.scene)
                    .where(schema.scene.c.episode_id == eps[ep],
                           schema.scene.c.script_scene_no == sc.no)
                    .values(story_seq=sc.story_seq, markers=MARKERS.get(sc.marker or "", []))
                    .returning(schema.scene.c.id)
                ).scalar_one()  # fmt: skip
                scene[ep, sc.no] = sid
        line = {
            (ep, no, r.seq): (r.id, r.scene_id)
            for (ep, no), sid in scene.items()
            for r in conn.execute(
                select(schema.script_line).where(schema.script_line.c.scene_id == sid)
            )
        }  # fmt: skip
        ent = {}
        for e in show.entities:
            ent[e.id] = conn.execute(
                insert(schema.entity)
                .values(show_id=show_id, kind=e.kind, canonical_name=e.name, origin="bible")
                .returning(schema.entity.c.id)
            ).scalar_one()
        for g in consolidate(show, gone_as):
            ids = []
            for ep, no, seq, quote, value in g["events"]:
                line_id, scene_id = line[ep, no, seq]
                ids.append(
                    conn.execute(
                        insert(schema.fact_event)
                        .values(
                            scene_id=scene_id, line_id=line_id, predicate=g["predicate"],
                            subject_id=ent[g["subject"]],
                            object_id=ent[g["object"]] if g["object"] else None,
                            value=value, quote=quote, confidence=1.0,
                        )
                        .returning(schema.fact_event.c.id)
                    ).scalar_one()
                )  # fmt: skip
            conn.execute(
                insert(schema.fact).values(
                    show_id=show_id, predicate=g["predicate"], subject_id=ent[g["subject"]],
                    object_id=ent[g["object"]] if g["object"] else None, value=g["value"],
                    screen=Range(0, 1), story=Range(*g["story"]), source_event_ids=ids,
                    confidence=1.0,
                )
            )  # fmt: skip


def run_rules(engine: Engine, episodes: list[str]) -> tuple[list[Any], dict[str, float]]:
    flags: list[Any] = []
    wall: dict[str, float] = {}
    with engine.connect() as conn:
        for ep in episodes:
            tl = load_timeline(conn, SLUG, ep)
            checks = [c(conn, SLUG) for c in cast(list[type[SqlRule]], CHECKS)]
            for check in checks:
                t = time.perf_counter()
                got = run_check(
                    check, tl, "run_oracle", ProducedBy(model_variant=None, plan_id="p")
                )
                wall[str(check.check)] = wall.get(str(check.check), 0.0) + time.perf_counter() - t
                stable, _ = require_stable_refs(got)
                kept, _ = verify(stable, tl, [check])
                flags += kept
    return flags, wall


def main(
    show_dir: Annotated[Path, typer.Option(help="Injected show dir: S01E0n.fountain + truth.json")],
    flags: Annotated[Path, typer.Option(help="Flags JSONL to write")],
    admin_url: Annotated[str | None, typer.Option(help="Default: $NIP_TEST_DATABASE_URL")] = None,
    gone_as: Annotated[str | None, typer.Option(help="Write destroyed props as e.g. lost")] = None,
) -> None:
    url = (admin_url or os.environ["NIP_TEST_DATABASE_URL"]).replace(
        "postgresql://", "postgresql+psycopg://", 1
    )
    show = read_show(show_dir)
    name = "nip_layer1_oracle"
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {name}"))
    engine = create_engine(make_url(url).set(database=name))
    try:
        with engine.begin() as c:
            c.execute(text("CREATE EXTENSION vector"))
            c.execute(text("CREATE EXTENSION btree_gist"))
            schema.metadata.create_all(c)
        build_store(engine, show_dir, show, gone_as)
        got, wall = run_rules(engine, list(show.episodes))
    finally:
        engine.dispose()
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
    flags.parent.mkdir(parents=True, exist_ok=True)
    flags.write_text("".join(f.model_dump_json() + "\n" for f in got), encoding="utf-8")
    by: dict[str, int] = {}
    for f in got:
        by[str(f.check)] = by.get(str(f.check), 0) + 1
    typer.echo(json.dumps({"flags": by, "rule_wall_s": {k: round(v, 3) for k, v in wall.items()}}))


if __name__ == "__main__":
    typer.run(main)
