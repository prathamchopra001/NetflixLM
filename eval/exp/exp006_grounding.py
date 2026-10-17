"""EXP-006: grounding validator threshold, rapidfuzz partial ratio 85 / 90 / 95 (D-005).

    uv run python -m eval.exp.exp006_grounding sheet    # writes data/exp006/to_label.jsonl
    (label every listed event in eval/exp/exp006_labels.jsonl: {"id", "label", "note"})
    uv run python -m eval.exp.exp006_grounding sweep    # MLflow "exp006-grounding", 3 runs
    uv run nip eval compare --exp EXP-006 --md --tracking-uri sqlite:///data/mlflow/mlflow.db

Set: 300 raw (pre-grounding) events sampled (seeded) from EXP-020's enum-arm extraction pass of
the synthetic show (data/exp020/enum/events.jsonl, real qwen3.5-4b-awq output); no new LLM calls.
Labels: an event is `true` when the line supports it (predicate, subject, object; value ignored),
else `hallucinated`. Events matching a truth.json fact of their line are `true` (labeller:
generator); the rest are labelled by the agent (eval/exp/exp006_labels.jsonl, labeller: agent).
Metrics per threshold: share of true events dropped, share of hallucinated events kept.

2.1B follow-up (variant `t90-checks`): the same sample after `extract --replay` with the shipped
`save_events`, which also drops zero-confidence events, repeated events and events whose arguments
have the wrong entity kind (`entities.ARG_KINDS`); an event is kept when its quote scores >= 90 and
`dropped` is empty. The drop reasons are counted per label.
"""

import json
import random
from pathlib import Path
from typing import Any

import typer

from eval.exp.exp020_resolution import OUT as EXP020
from eval.exp.exp020_resolution import SEED, TRACKING_URI, _clear, truth_index

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "exp006"
LABELS = Path(__file__).with_name("exp006_labels.jsonl")
THRESHOLDS = (85, 90, 95)
N = 300
app = typer.Typer(no_args_is_help=True)


def sample() -> list[dict[str, Any]]:
    lines = (EXP020 / "enum" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(x) for x in lines]
    picked = random.Random(f"exp006/{SEED}").sample(events, N)
    return sorted(picked, key=lambda e: events.index(e))


def generator_labels(events: list[dict[str, Any]]) -> dict[str, str]:
    from eval.synthetic import build

    facts, _ = truth_index(build(SEED))
    return {
        e["id"]: "true"
        for e in events
        if (e["predicate"], e.get("subject_truth"), e.get("object_truth"))
        in facts.get(e["line_ref"], set())
    }


def agent_labels() -> dict[str, str]:
    if not LABELS.exists():
        return {}
    rows = [json.loads(x) for x in LABELS.read_text(encoding="utf-8").splitlines() if x.strip()]
    return {r["id"]: r["label"] for r in rows}


@app.command()
def sheet() -> None:
    """The sampled events that truth.json does not decide, for agent labelling."""
    events = sample()
    gen, agent = generator_labels(events), agent_labels()
    todo = [e for e in events if e["id"] not in gen and e["id"] not in agent]
    OUT.mkdir(parents=True, exist_ok=True)
    keys = (
        "id",
        "line_text",
        "predicate",
        "subject",
        "subject_name",
        "object",
        "object_name",
        "value",
        "quote",
        "score",
        "subject_truth",
        "object_truth",
    )
    (OUT / "to_label.jsonl").write_text(
        "".join(json.dumps({k: e.get(k) for k in keys}, ensure_ascii=False) + "\n" for e in todo),
        encoding="utf-8",
    )
    typer.echo(
        f"{len(events)} sampled: {len(gen)} by truth, {len(agent)} by agent, {len(todo)} to label"
    )


def rates(
    events: list[dict[str, Any]], labels: dict[str, str], t: float, checks: bool = False
) -> dict[str, float]:
    def kept(e: dict[str, Any]) -> bool:
        return e["score"] >= t and not (checks and e.get("dropped"))

    true = [e for e in events if labels[e["id"]] == "true"]
    bad = [e for e in events if labels[e["id"]] == "hallucinated"]
    out = {
        "true_dropped_rate": sum(not kept(e) for e in true) / max(len(true), 1),
        "hallucinated_kept_rate": sum(kept(e) for e in bad) / max(len(bad), 1),
        "kept_rate": sum(map(kept, events)) / len(events),
        "n_true": len(true),
        "n_hallucinated": len(bad),
    }
    if checks:
        for name, group in (("true", true), ("hallucinated", bad)):
            for why in ("argument type", "zero confidence", "duplicate"):
                n = sum(e.get("dropped") == why for e in group)
                out[f"{name}_dropped_{why.replace(' ', '_')}"] = n
    return out


@app.command()
def sweep() -> None:
    import mlflow

    events = sample()
    gen = generator_labels(events)
    labels = agent_labels() | gen
    missing = [e["id"] for e in events if e["id"] not in labels]
    if missing:
        raise typer.BadParameter(f"{len(missing)} events unlabelled; run `sheet` first")
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("exp006-grounding")
    arms = [(f"t{t}", t, False) for t in THRESHOLDS] + [("t90-checks", 90, True)]
    for variant, t, checks in arms:
        m = rates(events, labels, t, checks) | {"n_generator_labels": len(gen)}
        _clear("exp006-grounding", "EXP-006", variant)
        with mlflow.start_run(run_name=f"EXP-006-{variant}"):
            mlflow.set_tags(
                {
                    "exp": "EXP-006",
                    "variant": variant,
                    "seed": str(SEED),
                    "labeller": "generator+agent",
                }
            )
            mlflow.log_params(
                {
                    "threshold": t,
                    "scorer": "rapidfuzz partial_ratio"
                    + (" + confidence/duplicate/argument-type checks" if checks else ""),
                    "n": N,
                    "source": "EXP-020 enum arm, qwen3.5-4b-awq",
                }
            )
            mlflow.log_metrics(m)
        typer.echo(f"{variant}: {json.dumps(m)}")


if __name__ == "__main__":
    app()
