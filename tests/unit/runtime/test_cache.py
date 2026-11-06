"""2.9B stage cache: key derivation, the work-unit protocol (`EpisodeRun.unit` + `Unit`), cached
finding round trips and the cache-key inputs of the checks that read beyond their spans."""

import hashlib
import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from nip import pipeline
from nip.agents.base import Finding, WorkUnit
from nip.agents.script_critic.layer1 import TwoPlaces
from nip.contracts.flag import Evidence, EvidenceKind, EvidenceRole, Tier
from nip.contracts.plan import Mode, Objective, Plan
from nip.runtime import cache


def k(**over: Any) -> str:
    args: dict[str, Any] = {"stage": "knowledge.extract", "stage_version": 1,
                            "model_variant": "m", "prompt_version": "p1", "params": {"t": 1},
                            "inputs": ["a", "b"]}  # fmt: skip
    return cache.key(**args | over)


def test_key_hashes_every_field_and_ignores_input_order() -> None:
    assert k() == k(inputs=["b", "a"]) == k(stage_version="1")
    for over in ({"stage": "x"}, {"stage_version": 2}, {"model_variant": "n"},
                 {"prompt_version": "p2"}, {"params": {"t": 2}}, {"inputs": ["a"]}):  # fmt: skip
        assert k(**over) != k(), over
    assert len(k()) == 64


def test_digest_and_object_layout() -> None:
    assert cache.digest(b"abc") == hashlib.sha256(b"abc").hexdigest()
    assert cache.digest({"b": 1, "a": [1, 2]}) == cache.digest({"a": [1, 2], "b": 1})
    key = k()
    assert cache.object_key(key) == f"cache/{key[:2]}/{key}.json.gz"


def test_force_never_reads() -> None:
    assert cache.StageCache(MagicMock(), MagicMock(), force=True).get(k()) is None


class FakeCache:
    def __init__(self, stored: dict[str, Any] | None = None, fail_put: bool = False) -> None:
        self.stored, self.fail_put, self.puts = stored or {}, fail_put, []

    def get(self, key: str) -> Any:
        return self.stored.get(key)

    def put(self, key: str, stage: str, value: Any, *a: Any) -> None:
        if self.fail_put:
            raise OSError("storage down")
        self.puts.append((key, stage, value))


def episode(fake: Any) -> pipeline.EpisodeRun:
    plan = Plan(inventory_fingerprint="f", catalog_sha256="c", objective=Objective.QUALITY,
                mode=Mode.RESIDENT, groups=[], decisions={})  # fmt: skip
    ep = pipeline.EpisodeRun(MagicMock(), None, "s", "S01E01", 1, "run_1", plan, [], [])
    ep.cache = fake
    return ep


def test_a_hit_is_recorded_cached_and_not_stored_again() -> None:
    ep = episode(fake := FakeCache({"k1": [1]}))
    with ep.unit("st", "S01E01/sc/1") as u:
        assert u.lookup("k1") == [1]
    assert ep.units[0]["status"] == "cached" and ep.units[0]["cache_key"] == "k1"
    assert fake.puts == []


def test_a_miss_stores_the_value_only_when_the_unit_succeeds() -> None:
    ep = episode(fake := FakeCache())
    with ep.unit("st", "a") as u:
        assert u.lookup("k1") is None
        u.value = {"x": 1}
    with ep.unit("st", "b") as u:
        u.lookup("k2")
        u.value = {"x": 2}
        raise RuntimeError("model died")
    with ep.unit("st", "c"):  # no lookup: an uncached unit
        pass
    assert [u["status"] for u in ep.units] == ["done", "failed", "done"]
    assert [u["cache_key"] for u in ep.units] == ["k1", "k2", None]
    assert fake.puts == [("k1", "st", {"x": 1})]


def test_a_failed_cache_write_does_not_fail_the_unit() -> None:
    ep = episode(FakeCache(fail_put=True))
    with ep.unit("st", "a") as u:
        u.lookup("k1")
        u.value = 1
    assert ep.units[0]["status"] == "done"


def test_no_cache_means_every_lookup_misses() -> None:
    ep = episode(None)
    with ep.unit("st", "a") as u:
        assert u.lookup("k1") is None
    assert ep.units[0]["status"] == "done"


def test_findings_round_trip_through_json() -> None:
    ev = Evidence(kind=EvidenceKind.SCRIPT_LINE, ref="S01E01/line/1.2", role=EvidenceRole.CLAIM,
                  quote="q")  # fmt: skip
    for tier in (None, Tier.MUST_REVIEW):
        f = Finding(3, 0.8, "t", "e", [ev], "fix", "es", tier)
        assert pipeline.finding_from(json.loads(cache.canonical(pipeline.finding_json(f)))) == f


def test_check_key_follows_what_the_check_reads() -> None:
    class Rule(TwoPlaces):
        read = "facts v1"

        def inputs(self, unit: WorkUnit, tl: Any) -> list[str]:
            return [cache.digest(self.read)]

    rule, unit = Rule(), WorkUnit("S01E01/plot.two_places", ())
    before = pipeline.check_key(rule, rule.params(), unit, None)  # type: ignore[arg-type]
    rule.read = "facts v2"
    after = pipeline.check_key(rule, rule.params(), unit, None)  # type: ignore[arg-type]
    other = WorkUnit("S01E02/plot.two_places", ())  # same show-wide facts, other episode's refs
    assert len({before, after, pipeline.check_key(rule, rule.params(), other, None)}) == 3  # type: ignore[arg-type]


def test_sql_rule_params_carry_the_inferred_story_factor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NIP_INFERRED_STORY_CONFIDENCE_FACTOR", "0.85")
    a = TwoPlaces().params()
    monkeypatch.setenv("NIP_INFERRED_STORY_CONFIDENCE_FACTOR", "0.5")
    b = TwoPlaces().params()
    assert a["sql"] == b["sql"] and a != b
