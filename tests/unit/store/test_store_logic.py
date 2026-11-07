"""Store logic that needs no database: ids, fingerprints, object keys, file classification."""

from pathlib import Path

import pytest

from nip.contracts import Flag
from nip.store import objects
from nip.store.ingest import InputRejected, classify
from nip.store.runs import db_id, ext_id, fingerprint


def flag(refs: list[str], lang: str | None = "es", check: str = "loc.readability") -> Flag:
    agent = "script_critic" if check.startswith("plot") else "localization_auditor"
    category = "plot_hole" if check.startswith("plot") else "localization"
    ev = [
        {"kind": k, "ref": r, "role": "claim" if i == 0 else "context"}
        for i, (r, k) in enumerate((r, _kind(r)) for r in refs)
    ]
    return Flag.model_validate({
        "run_id": "run_1", "episode": "S01E01", "agent": agent, "check": check,
        "category": category, "lang": lang, "severity": 3, "confidence": 1.0, "tier": "must_review",
        "title": "t", "explanation": "e", "evidence": ev,
        "produced_by": {"model_variant": None, "plan_id": "plan_1"},
    })  # fmt: skip


def _kind(ref: str) -> str:
    from nip.contracts import refs

    return str(refs.parse(ref).kind)


def test_ids_round_trip() -> None:
    assert ext_id("run", 912) == "run_912" and db_id("run_912") == 912 and db_id("flg_7") == 7


def test_fingerprint_uses_stable_refs_only() -> None:
    a = flag(["S01E01/es/4", "S01E01/es/3"])
    assert fingerprint(a) == fingerprint(flag(["S01E01/es/3", "S01E01/es/4"]))  # order-free
    assert fingerprint(a) != fingerprint(flag(["S01E01/es/4", "S01E01/es/3"], lang=None))
    assert fingerprint(a) != fingerprint(flag(["S01E01/es/4"]))
    # fact / asr ids churn on re-extraction (R13): they never change the fingerprint
    p1 = flag(["S01E01/line/3.2", "fact/10", "S01E01/asr/5"], None, "plot.knowledge_order")
    p2 = flag(["S01E01/line/3.2", "fact/99"], None, "plot.knowledge_order")
    assert fingerprint(p1) == fingerprint(p2) and len(fingerprint(p1)) == 64
    # a flag citing only churning refs has no identity: refused (2.0 review I3 ruling)
    with pytest.raises(ValueError, match="no stable evidence ref"):
        fingerprint(flag(["fact/10", "S01E01/asr/5"], None, "plot.knowledge_order"))


def test_add_stage_keeps_call_order(monkeypatch: pytest.MonkeyPatch) -> None:
    from nip import pipeline

    monkeypatch.setattr(pipeline, "STAGES", list(pipeline.STAGES))
    for name in ("timeline.asr", "timeline.align", "knowledge.extract"):
        pipeline.add_stage(name, lambda ep: None)
    pipeline.add_stage("index", lambda ep: None, before="checks")
    assert [n for n, _ in pipeline.STAGES] == [
        "timeline.asr", "timeline.align", "knowledge.extract", "timeline", "index", "checks",
        "verification", "flags", "report",
    ]  # fmt: skip


def test_object_keys_follow_the_layout() -> None:
    assert objects.source_key("sintel", "S01E01", "ab", ".SRT") == "sintel/S01E01/source/ab.srt"
    assert objects.source_key("sintel", None, "ab", ".yaml") == "sintel/show-level/ab.yaml"
    assert objects.keyframe_key("s", "S01E01", 3, 1) == "s/S01E01/keyframes/3_1.jpg"
    assert objects.run_key("run_1", "S01E01", "report.json") == "runs/run_1/S01E01/report.json"


def test_classify() -> None:
    sub = classify("es-419", Path("x.srt"), "en")
    assert (sub.kind, sub.lang, sub.role) == ("subtitle", "es-419", "target")
    assert classify("en", Path("x.vtt"), "en").role == "source"
    assert classify(None, Path("s.fountain"), "en").kind == "script"
    assert classify(None, Path("m.MKV"), "en").format == "mkv"
    assert classify(None, Path("bible.yaml"), "en").show_level
    assert classify("clearance_log", Path("c.csv"), "en").kind == "clearance_log"
    for tag, name, msg in [
        (None, "x.srt", "LANG=PATH"),
        ("scene", "x.srt", "LANG=PATH"),  # not a language tag
        (None, "g.csv", "glossary=PATH"),
        ("es", "s.fountain", "only subtitles and csv"),
        (None, "x.docx", "unsupported format"),
    ]:
        with pytest.raises(InputRejected, match=msg):
            classify(tag, Path(name), "en")
