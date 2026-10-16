"""Story stage (2.2) on Postgres: the scene columns persist, overrides come from the stored bible,
and each LLM transition is a recorded work unit (a failed one is a coverage gap)."""

import logging
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import Engine, select

from eval.synthetic.generate import build
from eval.synthetic.model import write_show
from nip import pipeline
from nip.contracts import (
    Autoscaling,
    HardwareInventory,
    Mode,
    Objective,
    Plan,
    Slot,
    StageGroup,
)
from nip.contracts.plan import SlotDecision
from nip.knowledge import story
from nip.knowledge.story import Verdict
from nip.store import schema
from nip.store.ingest import ingest_files

pytestmark = pytest.mark.integration
log = logging.getLogger(__name__)


class ReadableS3:
    """The boto3 calls the store and the story stage make, over a dict."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        self.objects[bucket, key] = Path(filename).read_bytes()

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:  # noqa: N803 (boto3)
        self.objects[Bucket, Key] = Body

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803 (boto3)
        class Body:
            def read(_self) -> bytes:  # noqa: N805
                return self.objects[Bucket, Key]

        return {"Body": Body()}


def plan(llm: str | None = None) -> tuple[Plan, HardwareInventory]:
    inv = HardwareInventory(
        fingerprint="f", nodes=[], autoscaling=Autoscaling(enabled=False, max_gpu_nodes=0)
    )
    return (
        Plan(
            inventory_fingerprint="f",
            catalog_sha256="c",
            objective=Objective.QUALITY,
            mode=Mode.RESIDENT,
            groups=[StageGroup(name="resident", slots=[])],
            decisions={Slot.TEXT_LLM: SlotDecision(variant=llm)} if llm else {},
        ),
        inv,
    )


def ingest(pg: Engine, s3: Any, show: str, ep: str, *files: Path) -> None:
    with pg.begin() as conn:
        ingest_files(conn, s3, show=show, episode=ep, files=[(None, f) for f in files])


def run(pg: Engine, s3: Any, show: str, eps: list[str], p: tuple[Plan, HardwareInventory]) -> Any:
    return pipeline.run_store(
        pg, s3, show=show, episodes=eps, plan=p[0], inventory=p[1], out_dir=None
    )


@pytest.fixture
def with_story(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "STAGES", list(pipeline.STAGES))
    monkeypatch.setattr(story, "_VERDICTS", {})
    pipeline.add_stage(story.STAGE, story.stage_story)


def rows(pg: Engine) -> dict[str, Any]:
    sc, ep = schema.scene, schema.episode
    with pg.connect() as c:
        return {
            f"{r.ref}/sc/{r.script_scene_no}": r
            for r in c.execute(
                select(
                    ep.c.ref, sc.c.script_scene_no, sc.c.markers, sc.c.story_day,
                    sc.c.story_seq, sc.c.story_inferred,
                ).join(ep, ep.c.id == sc.c.episode_id)
            )
        }  # fmt: skip


def test_columns_persist_for_the_whole_show_and_match_truth(
    pg: Engine, with_story: None, tmp_path: Path
) -> None:
    s3 = ReadableS3()
    show = build(1)
    write_show(show, tmp_path)
    for ep in show.episodes:
        ingest(pg, s3, "syn", ep, tmp_path / f"{ep}.fountain")
    ingest(pg, s3, "syn", "S01E01", tmp_path / "bible.yaml")  # show-level: the overrides
    # one episode in the run: the stage still orders the whole show (flashbacks cross episodes)
    s = run(pg, s3, "syn", ["S01E02"], plan())
    assert s["status"] == "completed"
    got = rows(pg)
    truth = {f"{ep}/sc/{sc.no}": sc for ep, scs in show.episodes.items() for sc in scs}
    assert got.keys() == truth.keys()
    assert all(r.story_seq is not None for r in got.values())
    assert {k: r.story_day for k, r in got.items()} == {k: t.story_day for k, t in truth.items()}
    tau = story.kendall_tau(
        {k: t.story_seq for k, t in truth.items()}, {k: r.story_seq for k, r in got.items()}
    )
    log.warning("story order, synthetic show seed 1, from Postgres: tau %.4f", tau)
    assert tau == 1.0 and {k: r.story_seq for k, r in got.items()} == {
        k: t.story_seq for k, t in truth.items()
    }
    assert {k for k, r in got.items() if "flashback" in r.markers} == {
        k for k, t in truth.items() if t.marker == "flashback"
    }
    assert {k for k, r in got.items() if "intercut" in r.markers} == {
        k for k, t in truth.items() if t.marker == "same_time"
    }
    assert not any(r.story_inferred for r in got.values())  # overrides + stated headings


def test_rerun_overwrites_and_without_the_bible_flashbacks_are_inferred(
    pg: Engine, with_story: None, tmp_path: Path
) -> None:
    s3 = ReadableS3()
    show = build(1)
    write_show(show, tmp_path)
    for ep in list(show.episodes)[:2]:
        ingest(pg, s3, "syn", ep, tmp_path / f"{ep}.fountain")
    run(pg, s3, "syn", ["S01E01"], plan())
    first = rows(pg)
    run(pg, s3, "syn", ["S01E01", "S01E02"], plan())
    assert rows(pg) == first  # idempotent
    assert {k for k, r in first.items() if r.story_inferred} == {
        k for k, r in first.items() if "flashback" in r.markers
    }


SCRIPT = (
    "INT. A - NIGHT\n\nMaya waits.\n\nINT. B - DAY\n\nMaya is still waiting.\n\n"
    "INT. C - NIGHT\n\nShe leaves.\n\nINT. D - MORNING\n\nShe arrives.\n"
)


class Scripted:
    variant = "scripted"

    def __init__(self, fail: bool = False) -> None:
        self.fail, self.calls = fail, 0

    def complete[M: BaseModel](self, prompt: str, schema: type[M], **kw: Any) -> M:
        self.calls += 1
        if self.fail:
            raise TimeoutError("model timed out")
        return Verdict(relation="same_day", reason="still waiting")  # type: ignore[return-value]


def test_llm_transitions_are_work_units(
    pg: Engine, with_story: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    s3 = ReadableS3()
    f = tmp_path / "s.fountain"
    f.write_text(SCRIPT, encoding="utf-8")
    ingest(pg, s3, "demo", "S01E01", f)
    llm = Scripted()
    monkeypatch.setattr(story, "make_llm", lambda variant: llm)
    s = run(pg, s3, "demo", ["S01E01"], plan("scripted"))
    assert s["status"] == "completed" and llm.calls == 2
    got = rows(pg)
    assert [got[f"S01E01/sc/{n}"].story_day for n in "1234"] == [1, 1, 1, 1]  # the LLM: same day
    assert [got[f"S01E01/sc/{n}"].story_inferred for n in "1234"] == [False, True, False, True]
    wu = schema.work_unit
    with pg.connect() as c:
        units = c.execute(
            select(wu.c.stage, wu.c.unit_key, wu.c.status, wu.c.model_variant).order_by(wu.c.id)
        ).all()
    assert [tuple(u) for u in units if u.stage == story.STAGE] == [
        (story.STAGE, "S01E01/sc/2", "done", "scripted"),
        (story.STAGE, "S01E01/sc/4", "done", "scripted"),
    ]
    run(pg, s3, "demo", ["S01E01"], plan("scripted"))
    assert llm.calls == 2  # the verdicts are memoised: a rerun asks nothing


def test_a_failed_llm_call_is_a_gap_and_the_rule_default_persists(
    pg: Engine, with_story: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    s3 = ReadableS3()
    f = tmp_path / "s.fountain"
    f.write_text(SCRIPT, encoding="utf-8")
    ingest(pg, s3, "demo", "S01E01", f)
    monkeypatch.setattr(story, "make_llm", lambda variant: Scripted(fail=True))
    s = run(pg, s3, "demo", ["S01E01"], plan("scripted"))
    assert s["status"] == "completed_with_gaps"
    assert s["episodes"]["S01E01"]["units"] == {"failed": 2}
    got = rows(pg)
    assert [got[f"S01E01/sc/{n}"].story_day for n in "1234"] == [1, 2, 2, 3]  # next-day default
    assert got["S01E01/sc/2"].story_inferred
