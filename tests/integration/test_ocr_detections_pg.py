"""OCR detection rows persist into `detection` (R15: needs NIP_TEST_DATABASE_URL)."""

import pytest
from sqlalchemy import Engine, insert, select

from nip.agents.clearance.ocr_text import Detection, insert_detections
from nip.store.schema import detection, episode, shot, show

pytestmark = pytest.mark.integration


def test_detections_round_trip(pg: Engine) -> None:
    with pg.begin() as conn:
        sid = conn.execute(
            insert(show).values(slug="s", title="S").returning(show.c.id)
        ).scalar_one()
        eid = conn.execute(
            insert(episode)
            .values(show_id=sid, season=1, number=1, episode_seq=1, ref="S01E01")
            .returning(episode.c.id)
        ).scalar_one()
        shot_id = conn.execute(
            insert(shot).values(episode_id=eid, frames="[0,48)", keyframes=[]).returning(shot.c.id)
        ).scalar_one()
        rows = [
            Detection(0, 0, "CALL (617) 482-9154", (0.1, 0.2, 0.3, 0.05), 0.97, "pp-ocrv6-medium"),
            Detection(0, 1, "7ABC123", (0.5, 0.5, 0.1, 0.04), 0.91, "pp-ocrv6-medium"),
        ]
        assert insert_detections(conn, eid, {0: shot_id}, rows) == 2
        got = conn.execute(select(detection).order_by(detection.c.keyframe_n)).all()
    assert [(g.shot_id, g.keyframe_n, g.channel, g.label, g.text) for g in got] == [
        (shot_id, 0, "ocr", "text", "CALL (617) 482-9154"),
        (shot_id, 1, "ocr", "text", "7ABC123"),
    ]
    assert [round(x, 2) for x in got[0].box] == [0.1, 0.2, 0.3, 0.05]
    assert got[1].confidence == pytest.approx(0.91) and got[1].model_variant == "pp-ocrv6-medium"
