"""Flag-to-label matching and precision/recall/F1 (docs/evaluation.md > Scoring)."""

import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment

from nip.contracts import EvidenceRole, Flag, Tier

IOU_MIN = 0.3
# Checks that may match each other (docs: "a small equivalence map"); value = canonical class.
EQUIVALENT = {"cont.prop_text": "plot.prop_provenance"}
SHOWN = {Tier.MUST_REVIEW, Tier.REVIEW_RECOMMENDED}
NO_LANG = "n/a"


@dataclass(frozen=True)
class Label:
    label_id: str
    episode: str | None
    check: str
    lang: str | None
    refs: tuple[str, ...]
    frames: tuple[int, int] | None  # half-open [in, out)


def load_labels(path: Path) -> list[Label]:
    """Read a label JSONL file (docs/evaluation.md > Label format)."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d: dict[str, Any] = json.loads(line)
        target = d.get("target", {})
        frames = target.get("frames")
        out.append(
            Label(
                label_id=d["label_id"],
                episode=d.get("episode"),
                check=d["check"],
                lang=d.get("lang"),
                refs=tuple(target.get("refs", ())),
                frames=(frames[0], frames[1]) if frames else None,
            )
        )
    return out


def _iou(a: tuple[int, int], b: tuple[int, int]) -> float:
    inter = min(a[1], b[1]) - max(a[0], b[0])
    return max(inter, 0) / max(max(a[1], b[1]) - min(a[0], b[0]), 1)


def _canon(check: str) -> str:
    return EQUIVALENT.get(check, check)


def overlap(flag: Flag, label: Label) -> float:
    """Match score in (0, 1], or 0.0 when the flag does not match the label."""
    if (
        flag.episode != label.episode
        or _canon(flag.check) != _canon(label.check)
        or (flag.lang and label.lang and flag.lang != label.lang)
    ):
        return 0.0
    best = 0.0
    for ev in flag.evidence:
        if ev.role is EvidenceRole.CONTEXT:
            continue  # only primary evidence (claim, contradiction, ...) may match a label
        if label.frames:  # timed target: the IoU rule is always enforced
            if ev.frames and (iou := _iou(ev.frames, label.frames)) >= IOU_MIN:
                best = max(best, iou)
        elif {ev.ref, ev.scene} & set(label.refs):  # script target: shared scene/line ref
            best = 1.0
    return best


def match(flags: Sequence[Flag], labels: Sequence[Label]) -> list[tuple[int, int]]:
    """Optimal one-to-one (flag index, label index) pairs.

    Each valid pair scores 1 + overlap, so the assignment first maximizes the number of matches
    and only then their overlap quality. Flags and labels are partitioned by (episode, check
    class) first: nothing outside a block can match, so this is exact and keeps matrices small.
    """
    blocks: dict[tuple[str | None, str], tuple[list[int], list[int]]] = defaultdict(
        lambda: ([], [])
    )
    for i, f in enumerate(flags):
        blocks[(f.episode, _canon(f.check))][0].append(i)
    for j, lb in enumerate(labels):
        blocks[(lb.episode, _canon(lb.check))][1].append(j)
    pairs = []
    for fi, li in blocks.values():
        if not fi or not li:
            continue
        score = np.array([[overlap(flags[i], labels[j]) for j in li] for i in fi])
        score = np.where(score > 0, score + 1.0, 0.0)
        for r, c in zip(*linear_sum_assignment(-score), strict=True):
            if score[r, c] > 0:
                pairs.append((fi[r], li[c]))
    return pairs


@dataclass
class Counts:
    tp: int = 0  # matched flags, booked under the flag's check/lang (precision side)
    native_tp: int = 0  # flags that hit a native (already-present) error: precision only
    fp: int = 0
    found: int = 0  # matched labels, booked under the label's check/lang (recall side)
    fn: int = 0


@dataclass
class Scored:
    counts: dict[str, Counts] = field(default_factory=lambda: defaultdict(Counts))
    outcomes: list[str] = field(default_factory=list)  # per flag: "tp" | "native" | "fp"


def score(flags: Sequence[Flag], labels: Sequence[Label], native: Sequence[Label] = ()) -> Scored:
    """Count TP/FP/FN. Scope keys: "all", "check/<id>", "lang/<code>".

    A matched pair is a TP under the flag's check/language (precision) and a found label under the
    label's (recall); they differ only for equivalence-mapped checks. An unmatched flag is a FP
    under its own; an unmatched label is a FN under its own. Unmatched flags are then matched
    against native labels, which turn them into native TPs (flag's check) instead of FPs.
    """
    res = Scored()
    res.outcomes = ["fp"] * len(flags)

    def bump(check: str, lang: str | None, what: str) -> None:
        for key in ("all", f"check/{check}", f"lang/{lang or NO_LANG}"):
            setattr(res.counts[key], what, getattr(res.counts[key], what) + 1)

    pairs = match(flags, labels)
    for i, j in pairs:
        res.outcomes[i] = "tp"
        bump(flags[i].check, flags[i].lang, "tp")
        bump(labels[j].check, labels[j].lang, "found")
    for j in set(range(len(labels))) - {j for _, j in pairs}:
        bump(labels[j].check, labels[j].lang, "fn")
    rest = [i for i, o in enumerate(res.outcomes) if o == "fp"]
    hit = {rest[i] for i, _ in match([flags[i] for i in rest], native)}
    for i in rest:
        if i in hit:
            res.outcomes[i] = "native"
            bump(flags[i].check, flags[i].lang, "native_tp")
        else:
            bump(flags[i].check, flags[i].lang, "fp")
    return res


def prf(c: Counts) -> dict[str, float]:
    """Precision, recall, F1; a zero denominator gives 0.0."""
    p = (c.tp + c.native_tp) / d if (d := c.tp + c.native_tp + c.fp) else 0.0
    r = c.found / d if (d := c.found + c.fn) else 0.0
    return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0}


def evaluate(
    flags: Iterable[Flag],
    labels: Sequence[Label],
    native: Sequence[Label] = (),
    *,
    content_hours: float | None = None,
    gpu_seconds: float | None = None,
    wall_seconds: float | None = None,
    coverage: float | None = None,
) -> dict[str, float]:
    """Flat metric dict for one run, named like "shown/f1/check/loc.term".

    Precision/recall/F1 + counts are computed separately on shown flags (must_review +
    review_recommended) and on all flags. Also: verification effect (share of FPs vs TPs that any
    verification stage failed), noise (shown FPs per content-hour, overall and per agent), cost
    per content-hour, coverage. Noise is only meaningful for clean (un-injected) runs.
    """
    flags = list(flags)
    out: dict[str, float] = {}
    shown = [f for f in flags if f.tier in SHOWN]
    shown_sc = score(shown, labels, native)
    all_sc = score(flags, labels, native)
    for subset, sc in (("shown", shown_sc), ("all", all_sc)):
        for scope, c in sc.counts.items():
            for k, v in {
                **prf(c),
                "tp": c.tp,
                "native_tp": c.native_tp,
                "fp": c.fp,
                "found": c.found,
                "fn": c.fn,
            }.items():
                out[f"{subset}/{k}/{scope}"] = float(v)

    def dropped(outcome: str) -> float:
        fl = [f for f, o in zip(flags, all_sc.outcomes, strict=True) if o == outcome]
        failed = sum(
            "fail" in (f.verification.evidence, f.verification.rule_recheck, f.verification.judge)
            for f in fl
        )
        return failed / len(fl) if fl else 0.0

    out["verification/fp_dropped_rate"] = dropped("fp")
    out["verification/tp_dropped_rate"] = dropped("tp")
    if content_hours:
        fp_flags = [f for f, o in zip(shown, shown_sc.outcomes, strict=True) if o == "fp"]
        out["noise/fp_per_hour"] = len(fp_flags) / content_hours
        for agent in {f.agent for f in fp_flags}:
            out[f"noise/fp_per_hour/agent/{agent}"] = (
                sum(f.agent == agent for f in fp_flags) / content_hours
            )
        if gpu_seconds is not None:
            out["cost/gpu_s_per_hour"] = gpu_seconds / content_hours
        if wall_seconds is not None:
            out["cost/wall_s_per_hour"] = wall_seconds / content_hours
    if coverage is not None:
        out["coverage"] = coverage
    return out
