"""EXP-020 / EXP-006 scoring on hand-made events against the generator's truth (no model)."""

from typing import Any

from eval.exp.exp006_grounding import rates
from eval.exp.exp020_resolution import metrics, truth_index
from eval.synthetic import build

SHOW = build(1)
FACTS, _ = truth_index(SHOW)


def events_from_truth() -> list[dict[str, Any]]:
    out = []
    for ref, facts in sorted(FACTS.items())[:40]:
        for p, s, o in sorted(facts, key=str):
            out.append(
                {
                    "id": f"{ref}#{p}{s}",
                    "line_ref": ref,
                    "predicate": p,
                    "score": 100.0,
                    "subject_id": 1,
                    "subject_truth": s,
                    "object_truth": o,
                }
            )
    return out


def test_truth_events_score_perfect_precision_and_resolution() -> None:
    evs = events_from_truth()
    m = metrics(evs, SHOW)
    assert m["fact_precision"] == 1 and m["resolution_accuracy"] == 1 and 0 < m["fact_recall"] < 1
    assert m["n_args"] > 0 and m["events_grounded"] == len(evs)


def test_wrong_subject_and_ungrounded_quote_count_against() -> None:
    evs = events_from_truth()
    evs[0] = evs[0] | {"subject_truth": "nobody"}
    evs[1] = evs[1] | {"score": 50.0}  # dropped by grounding: not scored
    m = metrics(evs, SHOW)
    assert m["resolution_accuracy"] < 1 and m["fact_precision"] < 1
    assert m["events_grounded"] == len(evs) - 1


def test_threshold_rates() -> None:
    evs = [{"id": "a", "score": 100.0}, {"id": "b", "score": 88.0}, {"id": "c", "score": 92.0}]
    labels = {"a": "true", "b": "true", "c": "hallucinated"}
    assert rates(evs, labels, 90)["true_dropped_rate"] == 0.5
    assert rates(evs, labels, 90)["hallucinated_kept_rate"] == 1.0
    assert rates(evs, labels, 95)["hallucinated_kept_rate"] == 0.0
