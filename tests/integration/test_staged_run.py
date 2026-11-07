"""`nip run --in-cluster` on this machine: the real text_llm, deployed around the stages that call
it (staged serving), on the synthetic show's S01E01. gpu: hold data/gpu.lock. Inside ray-head:

  HF_HUB_OFFLINE=1 docker compose -f compose.yaml -f compose.dev.yaml up -d --wait ray-head
  MSYS_NO_PATHCONV=1 docker compose -f compose.yaml -f compose.dev.yaml exec \
      -e NIP_TEST_DATABASE_URL=postgresql://nip:change_me@postgres:5432/nip ray-head \
      python3 -m pytest -p no:cacheprovider /app/tests/integration/test_staged_run.py
"""

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, func, select

from nip import pipeline
from nip.contracts import Slot
from nip.store import schema
from nip.store.ingest import ingest_files

pytest.importorskip("ray")
pytestmark = [pytest.mark.integration, pytest.mark.gpu]


def test_in_cluster_run_extracts_facts_with_the_real_llm_and_unloads_it(
    pg: Engine, s3: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eval.synthetic.generate import build
    from eval.synthetic.model import write_show
    from nip.runtime.serving import IDLE_TOLERANCE_MIB, gpu_used_mib

    write_show(build(1), tmp_path)
    with pg.begin() as conn:
        ingest_files(conn, s3, show="it", episode=None, files=[(None, tmp_path / "bible.yaml")])
        ingest_files(conn, s3, show="it", episode="S01E01",
                     files=[(None, tmp_path / "S01E01.fountain")])  # fmt: skip
    monkeypatch.setattr(pipeline, "STAGES", list(pipeline.STAGES))
    monkeypatch.setattr(pipeline, "AGENTS", list(pipeline.AGENTS))
    pipeline.wire()
    plan, inv = pipeline.current_plan({s: 1 for s in pipeline.MODEL_SLOTS})
    if Slot.TEXT_LLM in plan.skipped_slots:
        pytest.skip(pipeline.slot_reason(plan, Slot.TEXT_LLM))
    served = pipeline.serve_slots(plan)
    assert served == {Slot.TEXT_LLM}  # asr / text_embedder run in-process in their stages
    idle = gpu_used_mib()
    deploy = pipeline.cluster_deploy(plan, inv, served)
    s = pipeline.run_store(pg, s3, show="it", episodes=["S01E01"], plan=plan, inventory=inv,
                           deploy=deploy, served=served)  # fmt: skip
    print(s["serving"], s["episodes"]["S01E01"]["units"])
    [g] = s["serving"]
    assert g["stages"] == ["knowledge.story", "knowledge.extract"]
    assert g["up_mib"] > idle + 4096  # the 4B model was loaded for the group
    assert g["after_mib"] <= idle + IDLE_TOLERANCE_MIB  # and unloaded before the next stages
    with pg.connect() as conn:
        events = conn.execute(select(func.count()).select_from(schema.fact_event)).scalar_one()
        variants = set(conn.execute(select(schema.work_unit.c.model_variant)).scalars())
    assert events > 0 and plan.decisions[Slot.TEXT_LLM].variant in variants
    assert s["episodes"]["S01E01"]["units"].get("done", 0) > 0
