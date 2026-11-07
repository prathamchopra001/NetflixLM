"""Plot Layer 1 injectors (docs/evaluation.md > Script Critic) on the synthetic show.

`src` and `dst` are show directories (Fountain scripts + `bible.yaml` + `truth.json`). Each injector
edits the model loaded from `truth.json` by inserting one line into a scene, renders the scripts
again and writes a `truth.json` that includes the new line's facts (so oracle-facts runs see the
planted violation). Scenes already edited by an earlier injector are skipped (`touched`), which
keeps earlier labels' line numbers valid when injectors are stacked.

Labels are script-level: refs are the planted line and its scene (flags may claim either), plus
the other scene for two_places. Order checks use story order (`story_seq`), never screen order.
"""

import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

from eval.injectors.base import Injector, Label, Target, register
from eval.synthetic.model import (
    Fact,
    Line,
    Scene,
    Show,
    find_mentions,
    line_ref,
    merge_actions,
    read_show,
    write_show,
)
from nip.contracts import refs

Spot = tuple[str, Scene]  # (episode, scene)
Planted = tuple[str, Scene, Line, str, list[str]]  # episode, scene, new line, why, extra refs


class _Plot(Injector):
    def inject(self, src: Path, dst: Path, seed: int, *, k: int = 3) -> list[Label]:
        show = read_show(src)
        rng = random.Random(f"{self.id}/{seed}")
        labels: list[Label] = []
        for n, (ep, sc, line, why, extra) in enumerate(self.plant(show, rng, k), 1):
            sc.lines.insert(rng.randint(1, len(sc.lines)), line)  # after the establishing line
            sc.lines = merge_actions(sc.lines)  # an action next to an action is one element
            seq = next(i for i, ln in enumerate(sc.lines) if line.text in ln.text)
            show.touched.append(refs.scene(ep, sc.no))
            labels.append(
                Label(
                    label_id=f"{show.show}-{self.check}-s{seed}-{n}",
                    title=show.show,
                    episode=ep,
                    check=self.check,
                    target=Target(
                        kind="script_line",
                        refs=[line_ref(ep, sc.no, seq + 1), refs.scene(ep, sc.no), *extra],
                    ),
                    description=why,
                    injector=self.id,
                    seed=seed,
                )
            )
        write_show(show, dst)
        return labels

    def plant(self, show: Show, rng: random.Random, k: int) -> list[Planted]:
        """Up to `k` plantings; the caller inserts the lines and writes the labels."""
        raise NotImplementedError


def _spots(show: Show) -> list[Spot]:
    return [(ep, sc) for ep, scenes in show.episodes.items() for sc in scenes]


def _fresh(show: Show, ep: str, sc: Scene) -> bool:
    return refs.scene(ep, sc.no) not in show.touched


def _facts(show: Show, pred: str) -> list[tuple[Spot, Fact]]:
    return [
        ((ep, sc), f)
        for ep, sc in _spots(show)
        for ln in sc.lines
        for f in ln.facts
        if f.predicate == pred
    ]


def _first(show: Show, e: str) -> str:
    return show.entity(e).name.split()[0]


def _pick(cands: list[Any], rng: random.Random, k: int, spot: Callable[[Any], Spot]) -> list[Any]:
    """Shuffle, then take up to `k` candidates, at most one per scene."""
    rng.shuffle(cands)
    used: set[str] = set()
    out: list[Any] = []
    for c in cands:
        ep, sc = spot(c)
        key = refs.scene(ep, sc.no)
        if key not in used and len(out) < k:
            used.add(key)
            out.append(c)
    return out


def _at(c: tuple[Any, ...]) -> Spot:
    return c[0]  # type: ignore[no-any-return]


@register
class KnowledgeOrder(_Plot):
    """A character refers to a secret in a scene before the one where they learn it."""

    id = "plot.knowledge_order.v1"
    check = "plot.knowledge_order"

    def plant(self, show: Show, rng: random.Random, k: int) -> list[Planted]:
        learns = {(f.subject, f.object): sc.story_seq for (_, sc), f in _facts(show, "learns")}
        cands = []
        for (lep, lsc), f in _facts(show, "learns"):
            x, s = f.subject, str(f.object)
            for ep, sc in _spots(show):
                if (
                    sc.story_seq < lsc.story_seq
                    and sc.marker != "flashback"
                    and _fresh(show, ep, sc)
                    and x in show.cast(sc)
                    and learns[(x, s)] >= lsc.story_seq  # not learned earlier anywhere
                ):
                    cands.append(((ep, sc), x, s, (lep, lsc)))
        out: list[Planted] = []
        for (ep, sc), x, s, (lep, lsc) in _pick(cands, rng, k, _at):
            secret = show.entity(s)
            desc = secret.attrs["description"]
            text = f"Do not worry. {desc}. I have known for a long time."
            line = Line(
                kind="dialogue",
                text=text,
                speaker=x,
                facts=[Fact(predicate="references", subject=x, object=s, quote=desc)],
                mentions=find_mentions(show.entities, text),
            )
            why = (
                f"{_first(show, x)} refers to a secret ({desc}) in {refs.scene(ep, sc.no)} before "
                f"learning it in {refs.scene(lep, lsc.no)}"
            )
            out.append((ep, sc, line, why, []))
        return out


@register
class DeadActs(_Plot):
    """A character speaks in a present-day scene after their death scene."""

    id = "plot.dead_acts.v1"
    check = "plot.dead_acts"

    def plant(self, show: Show, rng: random.Random, k: int) -> list[Planted]:
        cands = []
        for (dep, dsc), f in _facts(show, "state"):
            if (f.value or {}).get("state") != "dead":
                continue
            for ep, sc in _spots(show):
                if (
                    sc.story_seq > dsc.story_seq
                    and sc.marker is None
                    and _fresh(show, ep, sc)
                    and f.subject not in show.cast(sc)
                ):
                    cands.append(((ep, sc), f.subject, (dep, dsc)))
        out: list[Planted] = []
        for (ep, sc), c, (dep, dsc) in _pick(cands, rng, k, _at):
            text = "I told you I would be back before the tide turned."
            line = Line(
                kind="dialogue",
                text=text,
                speaker=c,
                facts=[Fact(predicate="present_at", subject=c, object=sc.location, quote=text)],
            )
            why = (
                f"{_first(show, c)} speaks in {refs.scene(ep, sc.no)} after dying in "
                f"{refs.scene(dep, dsc.no)}"
            )
            out.append((ep, sc, line, why, []))
        return out


@register
class TwoPlaces(_Plot):
    """A character speaks in a SAME TIME scene while present in the paired scene elsewhere."""

    id = "plot.two_places.v1"
    check = "plot.two_places"

    def plant(self, show: Show, rng: random.Random, k: int) -> list[Planted]:
        cands = []
        for ep, scenes in show.episodes.items():
            for a, b in zip(scenes, scenes[1:], strict=False):
                only_a = show.cast(a) - show.cast(b)
                if (
                    b.marker == "same_time"
                    and a.story_seq == b.story_seq
                    and only_a
                    and _fresh(show, ep, b)
                ):
                    cands.append(((ep, b), rng.choice(sorted(only_a)), a))
        out: list[Planted] = []
        for (ep, b), c, a in _pick(cands, rng, k, _at):
            text = "I got here as fast as I could."
            line = Line(
                kind="dialogue",
                text=text,
                speaker=c,
                facts=[Fact(predicate="present_at", subject=c, object=b.location, quote=text)],
            )
            why = (
                f"{_first(show, c)} is in {refs.scene(ep, a.no)} and {refs.scene(ep, b.no)} at "
                "the same story moment"
            )
            out.append((ep, b, line, why, [refs.scene(ep, a.no)]))
        return out


@register
class PropProvenance(_Plot):
    """A character uses a prop in a scene before they obtain it or after it is destroyed."""

    id = "plot.prop_provenance.v1"
    check = "plot.prop_provenance"

    def plant(self, show: Show, rng: random.Random, k: int) -> list[Planted]:
        destroyed = {
            f.subject: sc
            for (_, sc), f in _facts(show, "state")
            if (f.value or {}).get("state") == "destroyed"
        }
        cands = []
        for (oep, osc), f in _facts(show, "holds"):
            if (f.value or {}).get("event") != "obtain":
                continue
            x, prop = f.subject, str(f.object)
            gone = destroyed.get(prop)
            for ep, sc in _spots(show):
                if sc.marker == "flashback" or not _fresh(show, ep, sc) or x not in show.cast(sc):
                    continue
                if sc.story_seq < osc.story_seq:
                    when = f"before obtaining it in {refs.scene(oep, osc.no)}"
                    cands.append(((ep, sc), x, prop, when))
                elif gone is not None and sc.story_seq > gone.story_seq:
                    cands.append(((ep, sc), x, prop, "after it was destroyed"))
        out: list[Planted] = []
        for (ep, sc), x, prop, when in _pick(cands, rng, k, _at):
            name = show.entity(prop).name
            text = f"{_first(show, x)} checks the {name} again."
            use = {"event": "use"}
            line = Line(
                kind="action",
                text=text,
                facts=[Fact(predicate="holds", subject=x, object=prop, quote=text, value=use)],
                mentions=find_mentions(show.entities, text),
            )
            why = f"{_first(show, x)} uses the {name} in {refs.scene(ep, sc.no)} {when}"
            out.append((ep, sc, line, why, []))
        return out
