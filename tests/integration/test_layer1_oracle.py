"""2.3 benchmark path: oracle facts of the synthetic show -> store -> Layer 1 rules -> labels.

The clean show raises nothing; on the 2.9A plot-injected show every planted violation is found
(and nothing else), for two seeds; seed 2 writes every destroyed prop as `lost`.
"""

from pathlib import Path

import pytest
from sqlalchemy import Engine

from eval.exp.layer1_oracle import build_store, run_rules
from eval.inject import SYNTHETIC, _synthetic
from eval.metrics import match
from eval.synthetic import read_show

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(("seed", "gone_as"), [(1, None), (2, "lost")])
def test_injected_show_is_found_exactly_and_the_clean_show_is_silent(
    pg: Engine, tmp_path: Path, seed: int, gone_as: str | None
) -> None:
    labels = _synthetic(tmp_path, seed)
    assert len(labels) == 12
    clean = tmp_path / SYNTHETIC / "clean"
    build_store(pg, clean, read_show(clean))
    assert run_rules(pg, list(read_show(clean).episodes))[0] == []

    from sqlalchemy import text

    with pg.begin() as conn:  # the second show goes into an empty store
        conn.execute(text('TRUNCATE "show" RESTART IDENTITY CASCADE'))
    injected = tmp_path / SYNTHETIC / "injected"
    show = read_show(injected)
    build_store(pg, injected, show, gone_as)
    flags, _ = run_rules(pg, list(show.episodes))
    assert len(flags) == 12 and len(match(flags, labels)) == 12
    assert all(f.verification.evidence == f.verification.rule_recheck == "pass" for f in flags)
