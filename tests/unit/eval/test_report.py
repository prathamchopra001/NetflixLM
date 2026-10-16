import json
from pathlib import Path

import mlflow
import pytest
from typer.testing import CliRunner

from eval.report import app, load_flags
from nip.contracts import Flag

runner = CliRunner()


def flag(frames: tuple[int, int] = (100, 200)) -> Flag:
    return Flag.model_validate({
        "run_id": "r", "episode": "E1", "agent": "localization_auditor", "check": "loc.gender",
        "category": "localization", "lang": "es", "severity": 3, "confidence": 0.9,
        "tier": "must_review", "title": "t", "explanation": "e",
        "evidence": [{"kind": "subtitle_cue", "ref": "r", "role": "claim", "frames": frames}],
        "produced_by": {"model_variant": None, "plan_id": "p"},
    })  # fmt: skip


@pytest.fixture(autouse=True)
def _cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)  # a sqlite tracking store puts artifacts under ./mlruns


def lab(lid: str, frames: tuple[int, int], check: str = "loc.gender") -> str:
    return json.dumps(
        {"label_id": lid, "title": "t", "episode": "E1", "check": check, "lang": "es",
         "target": {"kind": "subtitle_cue", "frames": list(frames)},
         "description": "d", "injector": "test.v1", "seed": 0}
    )  # fmt: skip


@pytest.fixture
def files(tmp_path: Path) -> tuple[Path, Path, Path]:
    flags = [flag(), flag((500, 600))]  # 1 TP, 1 FP
    fp = tmp_path / "flags.json"
    fp.write_text(json.dumps([f.model_dump(mode="json") for f in flags]), encoding="utf-8")
    labels = tmp_path / "labels"
    labels.mkdir()
    (labels / "t.jsonl").write_text(lab("a", (100, 200)) + "\n" + lab("b", (300, 400)) + "\n")
    (labels / "t.native.jsonl").write_text(lab("n", (500, 600)) + "\n")
    return fp, labels, tmp_path


def test_run_and_compare(files: tuple[Path, Path, Path]) -> None:
    fp, labels, tmp = files
    uri = f"sqlite:///{tmp / 'mlflow.db'}"
    ids = []
    for variant, seed in [("A", 1), ("A", 2), ("B", 1)]:
        r = runner.invoke(
            app,
            ["run", "--set", "smoke", "--flags", str(fp), "--labels", str(labels),
             "--exp", "EXP-099", "--variant", variant, "--seed", str(seed),
             "--content-hours", "1", "--gpu-seconds", "10",
             "--tracking-uri", uri, "--out-dir", str(tmp / "out")],
        )  # fmt: skip
        assert r.exit_code == 0, r.output
        ids.append(r.output.split("mlflow_run_id=")[1].split()[0])
    report = next((tmp / "out").glob("smoke-s1-*"))
    assert {p.name for p in report.iterdir()} == {"report.md", "report.json", "flags.jsonl"}
    # the FP matches the native label, so precision is 1.0; one of two injected labels is found
    metrics = json.loads((report / "report.json").read_text())["metrics"]
    assert metrics["shown/precision/all"] == 1.0 and metrics["shown/recall/all"] == 0.5
    assert "| overall | 1.00 / 0.50 / 0.67 |" in (report / "report.md").read_text()

    r = runner.invoke(app, ["compare", "--exp", "EXP-099", "--md", "--tracking-uri", uri])
    assert r.exit_code == 0, r.output
    rows = {
        line.split("|")[1].strip(): line.split("|")[2:-1]
        for line in r.output.splitlines()
        if line.startswith("|")
    }
    assert rows["Metric"] == [" A ", " B "]
    assert rows["Seeds (n)"] == [" 2 ", " 1 "]
    assert rows["overall P / R / F1"][0].strip() == "1.00 ± 0.00 / 0.50 ± 0.00 / 0.67 ± 0.00"
    assert rows["overall P / R / F1"][1].strip() == "1.00 / 0.50 / 0.67"
    assert rows["MLflow runs"][0].strip() == ", ".join(ids[:2])

    r = runner.invoke(app, ["compare", "--runs", ids[0], "--runs", ids[2], "--tracking-uri", uri])
    assert r.exit_code == 0 and "| Metric | A | B |" in r.output


def test_compare_needs_one_selector() -> None:
    assert runner.invoke(app, ["compare"]).exit_code != 0


def test_load_flags_jsonl(tmp_path: Path) -> None:
    p = tmp_path / "f.jsonl"
    p.write_text("".join(flag().model_dump_json() + "\n" for _ in range(2)))
    assert len(load_flags(p)) == 2


def test_run_logs_plan_tags(files: tuple[Path, Path, Path]) -> None:
    fp, labels, tmp = files
    plan = tmp / "plan.json"
    plan.write_text(json.dumps({
        "inventory_fingerprint": "f", "catalog_sha256": "c", "objective": "quality",
        "mode": "staged", "groups": [], "decisions": {"text_llm": {"variant": "qwen"}},
    }))  # fmt: skip
    uri = f"sqlite:///{tmp / 'm.db'}"
    args = ["run", "--set", "s", "--flags", str(fp), "--labels", str(labels), "--plan", str(plan)]
    r = runner.invoke(app, [*args, "--baseline", "--tracking-uri", uri, "--out-dir", str(tmp)])
    assert r.exit_code == 0, r.output
    run = mlflow.MlflowClient(uri).get_run(r.output.split("mlflow_run_id=")[1].split()[0])
    assert run.data.tags["baseline"] == "true" and run.data.tags["objective"] == "quality"
    assert run.data.params["variant.text_llm"] == "qwen"
    assert len(run.data.tags["plan_fingerprint"]) == 16


def test_compare_prints_every_metric_and_guards_groups(tmp_path: Path) -> None:
    uri = f"sqlite:///{tmp_path / 'c.db'}"
    client = mlflow.MlflowClient(uri)
    exp_id = client.create_experiment("exp003")

    def log(variant: str, seed: int, metrics: dict[str, float]) -> None:
        tags = {"exp": "EXP-003", "variant": variant, "seed": str(seed)}
        run_id = client.create_run(exp_id, tags=tags).info.run_id
        for k, v in metrics.items():
            client.log_metric(run_id, k, v)

    for variant, seed, wer in [("v3", 1, 0.10), ("v3", 2, 0.20), ("turbo", 1, 0.30)]:
        log(variant, seed, {"wer": wer, "rtf": 0.5})
    r = runner.invoke(app, ["compare", "--exp", "EXP-003", "--tracking-uri", uri])
    assert r.exit_code == 0, r.output
    assert "| wer | 0.15 ± 0.07 | 0.30 |" in r.output and "| rtf | 0.50 ± 0.00 | 0.50 |" in r.output
    assert runner.invoke(app, ["compare", "--exp", "x' OR '1", "--tracking-uri", uri]).exit_code
    assert runner.invoke(app, ["compare", "--exp", "EXP-003", "--subset", "shwn"]).exit_code
    log("v3", 1, {"wer": 0.9})  # a stale re-run of seed 1 would be averaged in silently
    r = runner.invoke(app, ["compare", "--exp", "EXP-003", "--tracking-uri", uri])
    assert r.exit_code == 1 and "variant v3" in r.output
