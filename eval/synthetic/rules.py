"""Reference implementations of the four Layer 1 plot rules over a `Show`'s truth facts.

These are the oracle for the synthetic show: a clean show has no violations, and after the plot
injectors have run the violations are exactly the planted lines. They also give EXP-007's
`oracle-facts` variant something to compare the SQL rules (2.3) against.
"""

from typing import Any

from eval.synthetic.model import Scene, Show

Violation = tuple[str, str, str, int]  # (check, episode, scene no, line seq)


def violations(show: Show) -> list[Violation]:
    flat = [(ep, sc) for ep, scenes in show.episodes.items() for sc in scenes]
    out: list[Violation] = []

    def facts(sc: Scene, pred: str) -> list[tuple[int, str, str | None, dict[str, Any] | None]]:
        return [
            (seq, f.subject, f.object, f.value)
            for seq, ln in enumerate(sc.lines, 1)
            for f in ln.facts
            if f.predicate == pred
        ]

    learned: dict[tuple[str, str], int] = {}  # (char, secret) -> earliest story_seq
    for _, sc in flat:
        for _, x, s, _ in facts(sc, "learns"):
            k = (x, str(s))
            learned[k] = min(learned.get(k, sc.story_seq), sc.story_seq)
    died = {
        x: sc.story_seq
        for _, sc in flat
        for _, x, _, v in facts(sc, "state")
        if (v or {}).get("state") == "dead"
    }
    destroyed = {
        x: sc.story_seq
        for _, sc in flat
        for _, x, _, v in facts(sc, "state")
        if (v or {}).get("state") == "destroyed"
    }
    obtained = {
        o: sc.story_seq
        for _, sc in flat
        for _, _, o, v in facts(sc, "holds")
        if (v or {}).get("event") == "obtain"
    }
    for ep, sc in flat:
        for seq, x, s, _ in facts(sc, "references"):
            if learned.get((x, str(s)), 1 << 30) > sc.story_seq:
                out.append(("plot.knowledge_order", ep, sc.no, seq))
        if sc.marker != "flashback":
            for seq, ln in enumerate(sc.lines, 1):
                if ln.speaker in died and sc.story_seq > died[ln.speaker]:
                    out.append(("plot.dead_acts", ep, sc.no, seq))
        for seq, _, p, v in facts(sc, "holds"):
            if (v or {}).get("event") != "use":
                continue
            if sc.story_seq < obtained.get(str(p), 0) or sc.story_seq > destroyed.get(
                str(p), 1 << 30
            ):
                out.append(("plot.prop_provenance", ep, sc.no, seq))
    by_seq: dict[int, list[tuple[str, Scene]]] = {}
    for ep, sc in flat:
        by_seq.setdefault(sc.story_seq, []).append((ep, sc))
    for group in by_seq.values():
        for i, (_, a) in enumerate(group):
            for ep, b in group[i + 1 :]:
                shared = show.cast(a) & show.cast(b)
                if a.location != b.location and shared:
                    seq = next(
                        i
                        for i, ln in enumerate(b.lines, 1)
                        if {f.subject for f in ln.facts} & shared
                    )
                    out.append(("plot.two_places", ep, b.no, seq))
    return sorted(out)
