"""Benchmark report, MLflow logging, and `nip eval run` / `nip eval compare`.

Wire into the root CLI with:  app.add_typer(eval_app, name="eval")  (from eval.report import app).
"""

import hashlib
import json
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex
from typing import Annotated, Any

import typer

from nip.contracts import Flag, Plan

app = typer.Typer(no_args_is_help=True, help="Benchmark scoring, MLflow logging, comparisons.")

TAGS = ("exp", "variant", "seed", "baseline", "commit", "plan_fingerprint", "objective", "mode")
PRF = ("precision", "recall", "f1")


def load_flags(path: Path) -> list[Flag]:
    """Flags as a JSON array or as JSONL."""
    text = path.read_text(encoding="utf-8").strip()
    rows = json.loads(text) if text.startswith("[") else [json.loads(x) for x in text.splitlines()]
    return [Flag.model_validate(r) for r in rows]


def plan_fingerprint(plan: Plan) -> str:
    """Catalog hash + chosen variants (docs/evaluation.md > Regression Gate), hashed."""
    variants = sorted((str(s), d.variant) for s, d in plan.decisions.items())
    return hashlib.sha256(json.dumps([plan.catalog_sha256, variants]).encode()).hexdigest()[:16]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _commit() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        return r.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _cell(
    metrics: dict[str, float], subset: str, scope: str, names: tuple[str, ...], fmt: str
) -> str:
    return " / ".join(format(metrics.get(f"{subset}/{m}/{scope}", 0.0), fmt) for m in names)


def render_report(title: str, metrics: dict[str, float]) -> str:
    """Per-scope Markdown table for one run (shown and all flags), then the other metrics."""
    scopes = sorted({k.split("/", 2)[2] for k in metrics if k.startswith("shown/f1/")})
    scopes.sort(key=lambda s: (s != "all", s))
    lines = [
        f"# {title}",
        "",
        "| Scope | shown P / R / F1 | shown TP / FP / FN | all P / R / F1 |",
        "|---|---|---|---|",
    ]
    for s in scopes:
        lines.append(
            f"| {'overall' if s == 'all' else s} | {_cell(metrics, 'shown', s, PRF, '.2f')} "
            f"| {_cell(metrics, 'shown', s, ('tp', 'fp', 'fn'), '.0f')} "
            f"| {_cell(metrics, 'all', s, PRF, '.2f')} |"
        )
    rest = {k: v for k, v in metrics.items() if k.split("/")[0] not in ("shown", "all")}
    lines += ["", "| Metric | Value |", "|---|---|"]
    lines += [f"| {k} | {v:.4g} |" for k, v in sorted(rest.items())]
    return "\n".join(lines) + "\n"


@app.command()
def run(
    set_: Annotated[str, typer.Option("--set", help="Benchmark set; one MLflow experiment each")],
    flags: Annotated[Path, typer.Option(help="Flags JSON array or JSONL")],
    labels: Annotated[list[Path], typer.Option(help="Label files/dirs; *.native.jsonl = native")],
    exp: Annotated[str | None, typer.Option(help="EXP-0XX id")] = None,
    variant: Annotated[str | None, typer.Option()] = None,
    seed: Annotated[int, typer.Option(help="Injector seed (tag only; labels not filtered)")] = 1,
    plan: Annotated[Path | None, typer.Option(help="Plan JSON")] = None,
    content_hours: Annotated[float | None, typer.Option()] = None,
    gpu_seconds: Annotated[float | None, typer.Option()] = None,
    wall_seconds: Annotated[float | None, typer.Option()] = None,
    coverage: Annotated[float | None, typer.Option()] = None,
    baseline: Annotated[bool, typer.Option("--baseline")] = False,
    param: Annotated[list[str] | None, typer.Option(help="Extra MLflow param, k=v")] = None,
    tracking_uri: Annotated[str | None, typer.Option(help="Default: MLflow's own")] = None,
    out_dir: Annotated[Path, typer.Option()] = Path("eval"),
) -> None:
    """Score a flags file against labels, write the report, log the run to MLflow."""
    from eval.metrics import evaluate, load_labels  # scipy: ~1 s to import

    files = [f for p in labels for f in (sorted(p.glob("*.jsonl")) if p.is_dir() else [p])]
    inj = [lb for f in files if not f.name.endswith(".native.jsonl") for lb in load_labels(f)]
    nat = [lb for f in files if f.name.endswith(".native.jsonl") for lb in load_labels(f)]
    fl = load_flags(flags)
    metrics = evaluate(
        fl,
        inj,
        nat,
        content_hours=content_hours,
        gpu_seconds=gpu_seconds,
        wall_seconds=wall_seconds,
        coverage=coverage,
    )

    commit = _commit()
    # variant + random suffix: seeds and variants started in the same second never collide
    run_id = f"{set_}-s{seed}-{datetime.now(UTC):%Y%m%dT%H%M%S}-{variant or 'base'}-{token_hex(2)}"
    tags = {
        "commit": commit,
        "seed": str(seed),
        "baseline": str(baseline).lower(),
        "flags_sha256": _sha(flags),
        "labels_sha256": hashlib.sha256(
            "".join(sorted(_sha(f) for f in files)).encode()
        ).hexdigest()[:16],
    }
    params: dict[str, str] = {}
    if exp:
        tags["exp"] = exp
    if variant:
        tags["variant"] = variant
    if plan:
        p = Plan.model_validate_json(plan.read_text(encoding="utf-8"))
        tags |= {
            "plan_fingerprint": plan_fingerprint(p),
            "objective": p.objective.value,
            "mode": p.mode.value,
            "plan_sha256": _sha(plan),
        }
        params |= {f"variant.{s}": d.variant for s, d in p.decisions.items()}
    versions: dict[str, set[str]] = defaultdict(set)
    for f in fl:
        if f.produced_by.prompt_version:
            versions[f.check].add(f.produced_by.prompt_version)
    params |= {f"prompt_version.{c}": ",".join(sorted(v)) for c, v in versions.items()}
    params |= dict(kv.split("=", 1) for kv in param or [])

    out = out_dir / run_id
    out.mkdir(parents=True)
    title = f"Benchmark {set_} · commit {commit[:8]} · {datetime.now(UTC):%Y-%m-%d} · seed {seed}"
    (out / "report.md").write_text(render_report(title, metrics), encoding="utf-8")
    (out / "report.json").write_text(
        json.dumps(
            {
                "benchmark_run_id": run_id,
                "set": set_,
                "tags": tags,
                "params": params,
                "metrics": metrics,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (out / "flags.jsonl").write_text(
        "".join(f.model_dump_json() + "\n" for f in fl), encoding="utf-8"
    )
    if plan:
        (out / "plan.json").write_text(plan.read_text(encoding="utf-8"), encoding="utf-8")

    import mlflow  # ~4 s to import: only when a run is logged

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(set_)
    with mlflow.start_run(run_name=run_id) as r:
        mlflow.set_tags(tags)
        mlflow.log_params(params)
        mlflow.log_metrics(metrics)
        mlflow.log_artifacts(str(out))
    typer.echo(f"{run_id}  mlflow_run_id={r.info.run_id}  report={out / 'report.md'}")


def _fmt(vals: list[float]) -> str:
    if not vals:
        return "—"
    m = statistics.fmean(vals)
    return f"{m:.2f} ± {statistics.stdev(vals):.2f}" if len(vals) > 1 else f"{m:.2f}"


def compare_table(groups: dict[str, list[Any]], subset: str = "shown") -> str:
    """Markdown table: one column per group of runs (seeds), mean ± sample std, run IDs last."""

    def vals(runs: list[Any], key: str) -> list[float]:
        return [r.data.metrics[key] for r in runs if key in r.data.metrics]

    metrics = {k for rs in groups.values() for r in rs for k in r.data.metrics}
    checks = sorted(k.split("/", 3)[3] for k in metrics if k.startswith(f"{subset}/f1/check/"))
    names = list(groups)
    rows = [["Metric", *names], ["Seeds (n)", *(str(len(groups[n])) for n in names)]]
    for label, scope in [("overall", "all"), *((c, f"check/{c}") for c in checks)]:
        cells = (
            " / ".join(_fmt(vals(groups[n], f"{subset}/{m}/{scope}")) for m in PRF) for n in names
        )
        rows.append([f"{label} P / R / F1", *cells])
    fixed = [
        ("Noise: shown FP per content-hour", "noise/fp_per_hour"),
        ("Verification: FPs dropped", "verification/fp_dropped_rate"),
        ("Verification: TPs dropped", "verification/tp_dropped_rate"),
        ("GPU-s per content-hour", "cost/gpu_s_per_hour"),
        ("Wall s per content-hour", "cost/wall_s_per_hour"),
        ("Coverage", "coverage"),
    ]
    shown = {k for _, k in fixed} | {
        f"{subset}/{m}/{scope}" for m in PRF for scope in ["all", *(f"check/{c}" for c in checks)]
    }
    # R10: every other logged metric (experiment numbers such as WER or RTF) gets its own row
    for label, key in fixed + [(k, k) for k in sorted(metrics - shown)]:
        rows.append([label, *(_fmt(vals(groups[n], key)) for n in names)])
    rows.append(["MLflow runs", *(", ".join(r.info.run_id for r in groups[n]) for n in names)])
    return (
        "\n".join(
            [f"| {' | '.join(rows[0])} |", f"|{'---|' * len(rows[0])}"]
            + [f"| {' | '.join(r)} |" for r in rows[1:]]
        )
        + "\n"
    )


@app.command()
def compare(
    exp: Annotated[str | None, typer.Option(help="EXP-0XX: every run tagged with it")] = None,
    runs: Annotated[list[str] | None, typer.Option(help="MLflow run ids, repeated")] = None,
    md: Annotated[bool, typer.Option("--md", help="Markdown table (the only format)")] = True,
    subset: Annotated[str, typer.Option(help="shown | all")] = "shown",
    tracking_uri: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Comparison table from MLflow runs; runs sharing a variant tag are seeds of one column."""
    if bool(exp) == bool(runs):
        raise typer.BadParameter("give exactly one of --exp or --runs")
    if subset not in ("shown", "all"):
        raise typer.BadParameter("--subset is shown or all")
    if exp and not re.fullmatch(r"[\w.-]+", exp):  # it goes into an MLflow filter string
        raise typer.BadParameter(f"--exp {exp!r}: letters, digits, '.', '-', '_' only")
    from mlflow import MlflowClient

    client = MlflowClient(tracking_uri)
    if exp:
        ids = [e.experiment_id for e in client.search_experiments()]
        found: list[Any] = list(
            client.search_runs(ids, filter_string=f"tags.exp = '{exp}'", max_results=1000)
        )
    else:
        found = [client.get_run(r) for r in runs or []]
    if not found:
        typer.echo(f"no runs found for {exp or runs}", err=True)
        raise typer.Exit(1)
    groups: dict[str, list[Any]] = defaultdict(list)
    for r in sorted(found, key=lambda r: r.info.start_time):
        groups[r.data.tags.get("variant") or r.info.run_id].append(r)
    for name, rs in groups.items():  # a column averages seeds of one setup, nothing else
        seeds = Counter(r.data.tags.get("seed") for r in rs)
        plans = {r.data.tags.get("plan_fingerprint") for r in rs}
        if max(seeds.values()) > 1 or len(plans) > 1:
            dup = ", ".join(r.info.run_id for r in rs)
            typer.echo(
                f"variant {name}: runs {dup} repeat a seed or differ in plan; delete the stale "
                "runs or pick them with --runs",
                err=True,
            )
            raise typer.Exit(1)
    typer.echo(compare_table(groups, subset))
