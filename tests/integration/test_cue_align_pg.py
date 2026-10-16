"""2.4 against the store: the alignment is persisted, loc.term reads the registry from the
entity/entity_alias rows and records observed renderings, the picture checks run in a store run.

Postgres via the `pg` fixture (NIP_TEST_DATABASE_URL), S3 via the in-memory `s3` fake.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, select

from nip import pipeline
from nip.agents.localization import term
from nip.store import schema
from nip.timeline import cue_align
from tests.integration.test_store import clip, ingest, picture_json, stub_plan, write

pytestmark = pytest.mark.integration

SCRIPT = "INT. ROOM - DAY #1#\n\nWren waits.\n"
BIBLE = "show: demo\ncharacters:\n  - {id: wren, name: Wren}\n"
GLOSSARY = "term,lang,approved_rendering,notes\nthe Hollow,es,el Hueco,\n"


def srt(cues: list[tuple[str, str, str]]) -> str:
    return "\n".join(f"{i}\n{a} --> {b}\n{t}\n" for i, (a, b, t) in enumerate(cues, 1))


EN = srt(
    [
        ("00:00:00,500", "00:00:01,500", "Wren waits."),
        ("00:00:01,800", "00:00:02,800", "Enter the Hollow."),
        ("00:00:03,000", "00:00:04,000", "Wren runs."),
        ("00:00:04,200", "00:00:05,000", "Wren hides."),
        ("00:00:05,100", "00:00:05,900", "Bye."),
    ]
)
ES = srt(  # cue 2 lacks "el Hueco"; cue 3 starts 3 frames after the cut at 3 s (24 fps)
    [
        ("00:00:00,500", "00:00:01,500", "Wren espera."),
        ("00:00:01,800", "00:00:02,800", "Entra en el Vacío."),
        ("00:00:03,125", "00:00:04,000", "Wren corre."),
        ("00:00:04,200", "00:00:05,000", "Wren se esconde."),
        ("00:00:05,100", "00:00:05,900", "Adiós."),
    ]
)


def test_store_run_persists_alignment_term_flags_and_observed_renderings(
    pg: Engine, s3: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = write(
        tmp_path,
        {"s.fountain": SCRIPT, "en.srt": EN, "es.srt": ES, "bible.yaml": BIBLE, "g.csv": GLOSSARY},
    )
    video = clip(tmp_path)
    ingest(
        pg,
        s3,
        [
            (None, f["s.fountain"]),
            ("en", f["en.srt"]),
            ("es", f["es.srt"]),
            (None, f["bible.yaml"]),
            ("glossary", f["g.csv"]),
            (None, video),
        ],
        picture=picture_json(tmp_path, video),
    )
    monkeypatch.setattr(pipeline, "STAGES", list(pipeline.STAGES))
    pipeline.add_stage("timeline.cue_align", cue_align.stage, before="checks")
    pipeline.add_stage("loc.observed", term.stage, before="checks")
    plan, inv = stub_plan()
    out = tmp_path / "out"
    s = pipeline.run_store(
        pg, s3, show="demo", episodes=["S01E01"], plan=plan, inventory=inv, out_dir=out
    )
    assert s["status"] == "completed"
    ep = s["episodes"]["S01E01"]
    assert ep["skipped"] == []  # picture + bible + glossary: every localization check is active
    kept = [
        (x["check"], x["title"][:24])
        for x in map(json.loads, (out / "S01E01" / "flags.jsonl").read_text().splitlines())
        if x["check"] != "loc.readability"
    ]
    assert sorted(kept) == [
        ("loc.shot_change", "Cue 2: out-point 5 frame"),  # 2.8 s = frame 67, the cut is at 72
        ("loc.shot_change", "Cue 3: in-point 3 frames"),
        ("loc.term", 'Cue 2: "the Hollow" shou'),
    ]
    cue, tr = schema.subtitle_cue, schema.subtitle_track
    with pg.connect() as conn:
        rows = conn.execute(
            select(tr.c.lang, cue.c.idx, cue.c.id, cue.c.aligned_source_cue_ids)
            .join(cue, cue.c.track_id == tr.c.id)
            .order_by(tr.c.lang, cue.c.idx)
        ).all()
        en_ids = {idx: cid for lang, idx, cid, _ in rows if lang == "en"}
        assert all(a is None for lang, _, _, a in rows if lang == "en")
        assert [(idx, a) for lang, idx, _, a in rows if lang == "es"] == [
            (i, [en_ids[i]]) for i in range(1, 6)
        ]
        al, e = schema.entity_alias, schema.entity
        observed = conn.execute(
            select(e.c.canonical_name, al.c.lang, al.c.alias, al.c.occurrences)
            .join(e, e.c.id == al.c.entity_id)
            .where(al.c.kind == "observed_rendering")
        ).all()
        units = conn.execute(
            select(schema.work_unit.c.stage, schema.work_unit.c.status).order_by(
                schema.work_unit.c.id
            )
        ).all()
    assert [tuple(r) for r in observed] == [("Wren", "es", "Wren", 3)]
    assert {("timeline.cue_align", "done"), ("loc.observed", "done")} <= {tuple(u) for u in units}
    assert all(st == "done" for _, st in units)


EN2 = srt(
    [
        ("00:00:00,500", "00:00:01,500", "Wren waits."),
        ("00:00:01,800", "00:00:02,800", "Wren runs."),
        ("00:00:03,000", "00:00:04,000", "Wren hides."),
        ("00:00:04,200", "00:00:05,000", "Wren is gone."),
        ("00:00:05,100", "00:00:05,900", "Bye."),
    ]
)
ES2 = srt(  # E2 renders Wren as Reyezuelo once
    [
        ("00:00:00,500", "00:00:01,500", "Wren espera."),
        ("00:00:01,800", "00:00:02,800", "Wren corre."),
        ("00:00:03,000", "00:00:04,000", "Reyezuelo se esconde."),
        ("00:00:04,200", "00:00:05,000", "Wren se fue."),
        ("00:00:05,100", "00:00:05,900", "Adiós."),
    ]
)


def test_observed_standard_spans_the_show_and_reruns_give_the_same_counts(
    pg: Engine, s3: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = write(
        tmp_path,
        {"s.fountain": SCRIPT, "bible.yaml": BIBLE, "en1.srt": EN, "es1.srt": ES,
         "en2.srt": EN2, "es2.srt": ES2},
    )  # fmt: skip
    ingest(pg, s3, [(None, f["bible.yaml"])], episode=None)
    for ep, n in (("S01E01", "1"), ("S01E02", "2")):
        files = [(None, f["s.fountain"]), ("en", f[f"en{n}.srt"]), ("es", f[f"es{n}.srt"])]
        ingest(pg, s3, files, episode=ep)
    monkeypatch.setattr(pipeline, "STAGES", list(pipeline.STAGES))
    pipeline.add_stage("timeline.cue_align", cue_align.stage, before="checks")
    pipeline.add_stage("loc.observed", term.stage, before="checks")
    plan, inv = stub_plan()
    al, e = schema.entity_alias, schema.entity

    def observed() -> list[tuple[Any, ...]]:
        with pg.connect() as conn:
            rows = conn.execute(
                select(e.c.canonical_name, al.c.lang, al.c.alias, al.c.occurrences)
                .join(e, e.c.id == al.c.entity_id)
                .where(al.c.kind == "observed_rendering")
            ).all()
        return [tuple(r) for r in rows]

    for _ in range(2):  # the second run sees both episodes aligned: same rows, not doubled
        s = pipeline.run_store(
            pg, s3, show="demo", episodes=["S01E01", "S01E02"], plan=plan, inventory=inv
        )
        assert s["status"] == "completed"
        assert observed() == [("Wren", "es", "Wren", 6)]  # 6 of 7 mentions over both episodes
