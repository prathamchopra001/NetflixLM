"""Script Critic Layer 1, the pure parts (the SQL is tested in tests/integration/test_layer1.py)."""

import pytest

from nip.agents.base import Input
from nip.agents.script_critic import CHECKS
from nip.agents.script_critic.layer1 import PropProvenance, TwoPlaces, claim_ref
from nip.config import config_dir
from nip.contracts.timeline import Timeline


def test_every_check_has_its_sql_file_with_the_two_parameters() -> None:
    assert len(CHECKS) == 4
    for cls in CHECKS:
        sql = (config_dir() / "rules" / f"{cls.check}.sql").read_text(encoding="utf-8")
        assert ":show" in sql and ":episode" in sql
        assert cls.active({Input.SCRIPT}) and not cls.active({Input.PICTURE})
        assert cls().params()["sql"]  # the rule text is a cache-key input


def test_without_a_store_there_is_nothing_to_check() -> None:
    tl = Timeline(episode="S01E01", fps=(24, 1), duration_frames=0, spans=())
    rule = TwoPlaces()  # file mode: no Connection
    assert rule.units(tl) == []


def test_explanations_name_the_scenes() -> None:
    row = {
        "episode": "S01E02", "scene_no": "4", "line_seq": 2, "other_episode": "S01E01",
        "other_scene_no": "9", "subject": "Maya", "object": "Pier Nine", "other_object": "Diner",
        "other_fact": 7, "detail": "after_gone",
    }  # fmt: skip
    assert claim_ref(row) == "S01E02/line/4.2"
    title, text, _ = PropProvenance().describe(row)
    assert "Maya" in title and "S01E02/sc/4" in text and "S01E01/sc/9" in text
    _, text, _ = TwoPlaces().describe(row)
    assert "Pier Nine" in text and "Diner" in text


@pytest.mark.parametrize("cls", CHECKS)
def test_severities_are_on_the_scale(cls: type) -> None:
    assert 1 <= cls.severity <= 5
