"""The six on-screen-text clearance checks: clr.phone, clr.url, clr.email, clr.address, clr.plate,
clr.brand_text (architecture.md > Agent 2).

The OCR stage (`stage.py`) wrote the typed candidates to `detection` (channel `ocr`, label = the
check id, plus a `sharpness` companion row per candidate); a check only reads the store: it loads
the candidates and the clearance registry, matches them (`matching.py`), merges them into
occurrences (`occurrences.py`) and emits ONE flag per occurrence of its check id.

Evidence of a flag: the keyframes that show it as `claim`, the best view first with the quote and
the crop box (a keyframe span stands for the stretch of its shot it represents, so the claim covers
about the seconds the text was seen and matches a labelled frame range by overlap); its shots and
the clearance item, when the log has it, as `context`.

Routing (architecture.md > Review tiers): pending and denied are `must_review` whatever the
confidence; cleared is `suppressed` (hidden by default, kept for the audit); unknown goes by
confidence. Severity: `occurrences.severity`.
"""

import logging
from collections.abc import Sequence
from typing import Any, ClassVar

from sqlalchemy import Connection, func, select

from nip.agents.base import Check, Finding, Input, WorkUnit
from nip.agents.clearance.matching import Item, Registry
from nip.agents.clearance.occurrences import Hit, Occurrence, analyze, geometry
from nip.config import pipeline_config
from nip.contracts import refs
from nip.contracts.flag import (
    CheckId,
    Crop,
    Evidence,
    EvidenceKind,
    EvidenceRole,
    Flag,
    Tier,
)
from nip.contracts.timeline import Timeline
from nip.store import schema

log = logging.getLogger(__name__)

SHARPNESS = "sharpness"  # label of a candidate's companion row: `confidence` holds the variance
MAX_KEYFRAMES = 6  # keyframes cited as claim per flag
MAX_SHOTS = 6  # shots cited as context

WHAT = {  # check -> (what it is, fix)
    "clr.phone": (
        "phone number",
        "Replace it with a number in the fiction-reserved range (555-0100 to 555-0199) or blur it.",
    ),
    "clr.url": ("web address", "Use a reserved domain (example.com, .test) or blur it."),
    "clr.email": ("e-mail address", "Use a reserved domain (example.com, .test) or blur it."),
    "clr.address": ("street address", "Use an invented address or blur it."),
    "clr.plate": ("license plate", "Use an invented plate or blur it."),
    "clr.brand_text": (
        "brand name",
        "Replace it with a fictional brand, clear it with the owner, or obscure it.",
    ),
}
STATUS_TEXT = {
    "pending": "is pending in the clearance log (item {name!r})",
    "denied": "is DENIED in the clearance log (item {name!r})",
    "cleared": "is cleared in the clearance log (item {name!r}); hidden from the report by default",
    "unknown": "is not in the clearance log",
}


# ---- reading the store -----------------------------------------------------------------------
def load_registry(conn: Connection, show: str) -> Registry:
    """The show's clearance items and the names its bible declares fictional (with aliases)."""
    sh, ci, en, al = schema.show, schema.clearance_item, schema.entity, schema.entity_alias
    items = tuple(
        Item(r.id, r.name, r.kind, r.status, r.scope)
        for r in conn.execute(
            select(ci).join(sh, sh.c.id == ci.c.show_id).where(sh.c.slug == show).order_by(ci.c.id)
        )
    )
    fic = (
        select(en.c.id, en.c.canonical_name)
        .join(sh, sh.c.id == en.c.show_id)
        .where(sh.c.slug == show, en.c.fictional.is_(True))
    ).subquery()
    names = [r[0] for r in conn.execute(select(fic.c.canonical_name))]
    names += [r[0] for r in conn.execute(select(al.c.alias).join(fic, fic.c.id == al.c.entity_id))]
    return Registry(items, tuple(dict.fromkeys(names)))


def load_hits(conn: Connection, show: str, episode: str, tl: Timeline) -> list[Hit]:
    """The episode's candidates (detection rows labelled clr.*) with their sharpness."""
    ep, sh, d = schema.episode, schema.show, schema.detection
    ep_id = conn.execute(
        select(ep.c.id)
        .join(sh, sh.c.id == ep.c.show_id)
        .where(sh.c.slug == show, ep.c.ref == episode)
    ).scalar_one_or_none()
    if ep_id is None:
        return []
    shot_at = {frames[0]: i for i, frames in enumerate(geometry(tl)[2])}
    rows = conn.execute(
        select(
            d.c.id,
            d.c.keyframe_n,
            d.c.label,
            d.c.text,
            d.c.box,
            d.c.confidence,
            d.c.model_variant,
            func.lower(schema.shot.c.frames).label("start"),
        )  # fmt: skip
        .join(schema.shot, schema.shot.c.id == d.c.shot_id)
        .where(
            d.c.episode_id == ep_id,
            d.c.channel == "ocr",
            (d.c.label.like("clr.%")) | (d.c.label == SHARPNESS),
        )
        .order_by(d.c.id)
    ).all()

    def key(r: Any) -> tuple[int, int, tuple[float, ...]]:
        return r.start, r.keyframe_n, tuple(round(float(b), 4) for b in r.box)

    sharp = {key(r): float(r.confidence) for r in rows if r.label == SHARPNESS}
    return [
        Hit(
            r.label,
            r.text,
            shot_at[r.start],
            r.keyframe_n,
            tuple(float(b) for b in r.box),  # type: ignore[arg-type]
            float(r.confidence),
            r.model_variant,
            sharp.get(key(r)),
            r.id,
        )
        for r in rows
        if r.label != SHARPNESS and r.start in shot_at
    ]


def load_keyframes(conn: Connection, show: str, episode: str) -> list[tuple[int, int, int]]:
    """(shot index, n, frame) of the episode's keyframes, from `shot.keyframes`: the frames the
    images were taken at, whatever range the timeline's keyframe spans carry by now."""
    sh, ep, s = schema.show, schema.episode, schema.shot
    rows = conn.execute(
        select(s.c.keyframes)
        .join(ep, ep.c.id == s.c.episode_id)
        .join(sh, sh.c.id == ep.c.show_id)
        .where(sh.c.slug == show, ep.c.ref == episode)
        .order_by(func.lower(s.c.frames), s.c.id)
    )
    return [(i, k["n"], k["frame"]) for i, (kfs,) in enumerate(rows) for k in kfs]


def episode_occurrences(
    conn: Connection, show: str, tl: Timeline, cfg: dict[str, Any]
) -> list[Occurrence]:
    """Every occurrence of the episode (all six checks), from the stored candidates."""
    return analyze(
        load_hits(conn, show, tl.episode, tl),
        load_registry(conn, show),
        tl,
        cfg,
        load_keyframes(conn, show, tl.episode),
    )


# ---- the checks ------------------------------------------------------------------------------
class ClearanceText(Check):
    """Base of the six checks; `hits`, `registry` and `keyframes` (shot, n, frame) replace the
    store reads (experiments, tests)."""

    requires = frozenset({Input.PICTURE})  # bible and clearance log improve it (◐)
    version = "1"

    def __init__(
        self,
        conn: Connection | None = None,
        show: str | None = None,
        *,
        hits: Sequence[Hit] | None = None,
        registry: Registry | None = None,
        keyframes: Sequence[tuple[int, int, int]] | None = None,
        cfg: dict[str, Any] | None = None,
    ) -> None:
        self.conn, self.show = conn, show
        self._hits, self._registry, self._keyframes = hits, registry, keyframes
        self.cfg = cfg or pipeline_config()["clearance"]
        self._by_key: dict[str, Occurrence] = {}

    def params(self) -> dict[str, Any]:
        return {"cfg": self.cfg}

    def occurrences(self, tl: Timeline) -> list[Occurrence]:
        """This check's occurrences in the episode (the analysis is shared by the six checks)."""
        if self._hits is not None and self._registry is not None:
            occs = analyze(self._hits, self._registry, tl, self.cfg, self._keyframes)
        elif self.conn is not None and self.show is not None:
            occs = episode_occurrences(self.conn, self.show, tl, self.cfg)
        else:
            return []  # file mode: no store, no detections
        return [o for o in occs if o.check == self.check]

    def units(self, tl: Timeline) -> list[WorkUnit]:
        occs = self.occurrences(tl)
        self._by_key = {o.key: o for o in occs}
        out = []
        for o in occs:
            spans = [tl.resolve(r) for r in keyframe_refs(o, tl.episode)]
            spans += [tl.resolve(refs.shot(tl.episode, i)) for i in o.shots[:MAX_SHOTS]]
            out.append(WorkUnit(f"{tl.episode}/{o.key}", tuple(s for s in spans if s)))
        return out

    def run(self, unit: WorkUnit, tl: Timeline) -> list[Finding]:
        o = self._by_key[unit.key.removeprefix(f"{tl.episode}/")]
        return [finding(o, tl)]

    def recheck(self, flag: Flag, tl: Timeline) -> bool:
        """The occurrence is still there: same best keyframe, same text, same logged item."""
        kf = next((e for e in flag.evidence if e.kind is EvidenceKind.KEYFRAME), None)
        item = next((e.ref for e in flag.evidence if e.kind is EvidenceKind.CLEARANCE_ITEM), None)
        return kf is not None and any(
            kf.ref == refs.keyframe(tl.episode, o.best.shot, o.best.n)
            and kf.quote in (None, o.best.text)  # no quote: the span had no text to quote from
            and item == (f"clr/{o.match.item.id}" if o.match.item else None)
            for o in self.occurrences(tl)
        )


def keyframe_refs(o: Occurrence, episode: str) -> list[str]:
    """The occurrence's distinct keyframes, the best view first (at most MAX_KEYFRAMES)."""
    rest = sorted({(h.shot, h.n) for h in o.hits} - {(o.best.shot, o.best.n)})
    return [refs.keyframe(episode, s, n) for s, n in [(o.best.shot, o.best.n), *rest]][
        :MAX_KEYFRAMES
    ]


def finding(o: Occurrence, tl: Timeline) -> Finding:
    """The flag content of one occurrence."""
    what, fix = WHAT[o.check]
    secs = o.screen_frames * tl.fps[1] / tl.fps[0]
    kind = "featured" if o.featured else "background"
    item = o.match.item
    status = STATUS_TEXT[o.match.status].format(name=item.name if item else "")
    kf_ref = keyframe_refs(o, tl.episode)[0]
    kf = tl.resolve(kf_ref)
    evidence = [  # the keyframes that show it (best first) claim it; the best one has the quote
        Evidence(
            kind=EvidenceKind.KEYFRAME,
            ref=ref,
            role=EvidenceRole.CLAIM,
            quote=o.best.text
            if ref == kf_ref and kf is not None and o.best.text in kf.text
            else None,
            crop=Crop(keyframe=ref, box=list(o.best.box)) if ref == kf_ref else None,
        )
        for ref in keyframe_refs(o, tl.episode)
    ]
    evidence += [
        Evidence(kind=EvidenceKind.SHOT, ref=refs.shot(tl.episode, i), role=EvidenceRole.CONTEXT)
        for i in o.shots[:MAX_SHOTS]
    ]
    if item is not None and (span := tl.resolve(f"clr/{item.id}")) is not None:
        evidence.append(
            Evidence(
                kind=EvidenceKind.CLEARANCE_ITEM,
                ref=span.ref,
                role=EvidenceRole.CONTEXT,
                quote=item.name if item.name in span.text else None,
            )
        )
    tier = {"pending": Tier.MUST_REVIEW, "denied": Tier.MUST_REVIEW, "cleared": Tier.SUPPRESSED}
    return Finding(
        severity=o.severity,
        confidence=min(1.0, o.confidence),
        title=f"{what.capitalize()} {o.text!r} on screen for {secs:.1f} s ({kind})",
        explanation=(
            f"OCR reads {o.text!r} at {len(o.hits)} keyframe(s) over {secs:.1f} s ({kind}, "
            f"prominence {o.prominence:.2f}). The {what} {status}."
        ),
        suggested_fix=None if o.match.status == "cleared" else fix,
        evidence=evidence,
        tier=tier.get(o.match.status),
    )


class ClrPhone(ClearanceText):
    check: ClassVar[CheckId] = CheckId.CLR_PHONE


class ClrUrl(ClearanceText):
    check: ClassVar[CheckId] = CheckId.CLR_URL


class ClrEmail(ClearanceText):
    check: ClassVar[CheckId] = CheckId.CLR_EMAIL


class ClrAddress(ClearanceText):
    check: ClassVar[CheckId] = CheckId.CLR_ADDRESS


class ClrPlate(ClearanceText):
    check: ClassVar[CheckId] = CheckId.CLR_PLATE


class ClrBrandText(ClearanceText):
    check: ClassVar[CheckId] = CheckId.CLR_BRAND_TEXT
