"""persist_alignment writes segments, line and scene frames, and the picture timeline source."""

import pytest
from sqlalchemy import Engine, insert, select

from nip.ingest.script import Element, Scene, Script
from nip.store import schema
from nip.timeline.align import align, persist_alignment
from nip.timeline.asr import TranscriptSegment, TranscriptWord

pytestmark = pytest.mark.integration


def seg(text: str, start: int) -> TranscriptSegment:
    words = tuple(
        TranscriptWord(w, start + i * 6, start + i * 6 + 6, 0.9) for i, w in enumerate(text.split())
    )
    return TranscriptSegment((words[0].f_in, words[-1].f_out), "en", text, words)


def test_persist_alignment(pg: Engine):
    script = Script(
        None,
        [
            Scene(
                "1",
                "INT. A - DAY",
                [Element("action", "Rain."), Element("dialogue", "hello there", "X")],
            ),
            Scene(
                "2",
                "INT. B - DAY",
                [
                    Element(
                        "dialogue", "this long speech never happens anywhere in the cut at all", "Y"
                    )
                ],
            ),
        ],
    )
    segs = [seg("hello there", 100), seg("background chatter", 500)]
    res = align(script, segs, [(0, 90), (90, 600)], 600)
    with pg.begin() as c:
        show = c.execute(
            insert(schema.show).values(slug="s", title="S").returning(schema.show.c.id)
        ).scalar_one()
        ep = c.execute(
            insert(schema.episode)
            .values(show_id=show, season=1, number=1, episode_seq=1, ref="S01E01")
            .returning(schema.episode.c.id)
        ).scalar_one()
        for s in script.scenes:
            sid = c.execute(
                insert(schema.scene)
                .values(
                    episode_id=ep, script_scene_no=s.number, heading=s.heading, text_hash="0" * 64
                )
                .returning(schema.scene.c.id)
            ).scalar_one()
            c.execute(
                insert(schema.script_line),
                [
                    {"scene_id": sid, "seq": i, "kind": e.kind, "text": e.text}
                    for i, e in enumerate(s.elements, 1)
                ],
            )
        persist_alignment(c, ep, res, segs)
    with pg.connect() as c:
        scenes = c.execute(
            select(schema.scene.c.frames, schema.scene.c.in_cut).order_by(schema.scene.c.id)
        ).all()
        lines = c.execute(
            select(schema.script_line.c.kind, schema.script_line.c.frames).order_by(
                schema.script_line.c.id
            )
        ).all()
        rows = c.execute(
            select(schema.transcript_segment.c.frames, schema.transcript_segment.c.text,
                   schema.transcript_segment.c.words, schema.transcript_segment.c.aligned_line_id)
            .order_by(schema.transcript_segment.c.id)
        ).all()  # fmt: skip
        source = c.execute(select(schema.episode.c.timeline_source)).scalar_one()
    assert source == "picture"
    assert (scenes[0].frames.lower, scenes[0].frames.upper) == (90, 600) and scenes[0].in_cut
    assert scenes[1].frames is None and not scenes[1].in_cut
    assert lines[0].frames is None  # the action line is not dialogue
    assert (lines[1].frames.lower, lines[1].frames.upper) == (100, 112)
    assert lines[2].frames is None
    assert [r.text for r in rows] == ["hello there", "background chatter"]
    assert rows[0].words[0] == {"w": "hello", "f_in": 100, "f_out": 106, "p": 0.9}
    assert rows[0].aligned_line_id is not None and rows[1].aligned_line_id is None
