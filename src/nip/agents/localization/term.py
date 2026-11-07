"""`loc.term`: names and terms rendered inconsistently in the target track.

architecture.md > Agent 1 > Names & terms. Deterministic: the registry's names and glossary terms
are looked up in each group of aligned source cues (`nip.timeline.cue_align.groups`), and the
aligned target cues must carry the approved rendering (glossary), or the observed standard when
there is none. Matching is by word: casefolded, short words (articles) ignored, a common noun may
differ by a 1-3 letter ending (inflection); a proper noun, or an accent changed, may not. A word
that is missing but resembles one in the target (rapidfuzz) is a misspelling.

Confidence: approved rendering missing 0.80, misspelled 0.92. Observed standard (no approved
rendering): the most frequent rendering of the name over the whole show, i.e. this episode and the
other episodes of the show as persisted by `cue_align.stage`. Missing it is 0.80 when the episode
switches (the standard carries >= 90% of the mentions elsewhere and <= 20% here: "Wren" rendered
"Reyezuelo" in E3), 0.55 otherwise (below 0.70, so suppressed: the name may be dropped for a
pronoun, an LLM adjudicates in Phase 3), 0.85 when a word of the target resembles it. Any finding in
a group of more than 2 source or 2 target cues is capped at 0.65 (alignment less sure).

`ponytail:` the rendering of a one-word name is the target word that best singles out the cues
mentioning it (share of those cues minus share of the others); a multi-word name is its own
standard (kept verbatim). A name rendered by several words, or by a word of under 4 letters, has no
standard and nothing is checked. Other episodes are read as one (source cues, target cue) pair per
target cue, so a rendering in the other half of a split target counts as missing there. Episodes of
a run are checked in order: the first sees only episodes aligned by earlier runs; run again to
converge.
"""

import hashlib
import logging
import re
import unicodedata
from collections import Counter
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy import Connection, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from nip.agents.base import Check, Finding, Input, WorkUnit, cue_windows
from nip.agents.localization.readability import rule_pack
from nip.contracts import refs
from nip.contracts.flag import CheckId, Evidence, EvidenceRole, Flag
from nip.contracts.timeline import Timeline
from nip.store import schema
from nip.timeline.cue_align import Group, aligned, groups

log = logging.getLogger(__name__)

APPROVED_MISSING, APPROVED_MISSPELLED = 0.80, 0.92
OBSERVED_MISSING, OBSERVED_MISSPELLED, OBSERVED_SWITCHED = 0.55, 0.85, 0.80
COMPLEX_GROUP = 0.65
SHOULD_FIX, MINOR = 3, 2
SHORT_RATIO = 85  # near-miss ratio for words under 5 letters (short words resemble many others)
MAX_SIDE = 2  # a group with more source or target cues than this is an uncertain alignment


@dataclass
class Entry:
    """One name or term: its source surface and the renderings per target language tag."""

    surface: str
    renderings: dict[str, list[str]] = field(default_factory=dict)  # approved, by lang tag
    entity_ids: list[int] = field(default_factory=list)

    @property
    def common(self) -> bool:
        """A common noun (no capitalised content word in the source surface): its renderings may be
        inflected. A name or title may not."""
        return not any(w[:1].isupper() for w in _WORD.findall(self.surface) if len(w) > 3)

    @property
    def key(self) -> str:
        return self.surface.casefold()


@dataclass
class Pair:
    """The words (casefolded, in order) of an aligned group of source cues and of target cues."""

    src: list[str]
    tgt: list[str]


@dataclass
class Standard:
    """The observed rendering of a name over the show."""

    rendering: str  # one casefolded word, or the whole surface of a multi-word name
    kept: int  # mentions of the name (show-wide) whose target carries it
    n: int  # mentions of the name (show-wide)
    switched: bool  # this episode drops it where the other episodes keep it


def load_others(
    conn: Connection, show: str, episode: str, source_lang: str, lang: str
) -> dict[str, list[Pair]]:
    """Pairs of the other episodes of `show` for target language `lang`, by episode ref: each
    target cue with the source cues persisted in its `aligned_source_cue_ids`."""
    ep, tr, cue, sh = schema.episode, schema.subtitle_track, schema.subtitle_cue, schema.show
    rows = conn.execute(
        select(ep.c.ref, tr.c.lang, tr.c.role, cue.c.id, cue.c.idx, cue.c.text,
               cue.c.aligned_source_cue_ids)
        .join(tr, tr.c.episode_id == ep.c.id)
        .join(cue, cue.c.track_id == tr.c.id)
        .join(sh, sh.c.id == ep.c.show_id)
        .where(sh.c.slug == show, ep.c.ref != episode, tr.c.lang.in_([lang, source_lang]))
        .order_by(ep.c.ref, cue.c.idx)
    ).all()  # fmt: skip
    src = {r.id: words(r.text) for r in rows if r.lang == source_lang and r.role == "source"}
    out: dict[str, list[Pair]] = {}
    for r in rows:
        if r.lang == lang and r.role == "target" and r.aligned_source_cue_ids:
            ws = [w for i in r.aligned_source_cue_ids for w in src.get(i, [])]
            out.setdefault(r.ref, []).append(Pair(ws, words(r.text)))
    return out


def load_registry(conn: Connection, show: str) -> list[Entry]:
    """Confirmed entities of `show` by surface (name aliases); entities with the same surface
    (a bible character and a glossary term) are one entry."""
    e, a, s = schema.entity, schema.entity_alias, schema.show
    rows = conn.execute(
        select(e.c.id, a.c.lang, a.c.alias, a.c.kind)
        .join(a, a.c.entity_id == e.c.id)
        .join(s, s.c.id == e.c.show_id)
        .where(s.c.slug == show, e.c.status == "confirmed")
        .order_by(e.c.id, a.c.alias)
    ).all()
    by_entity: dict[int, list[Any]] = {}
    for r in rows:
        by_entity.setdefault(r.id, []).append(r)
    merged: dict[str, Entry] = {}
    for eid, aliases in by_entity.items():
        for name in (r.alias for r in aliases if r.kind == "name"):
            entry = merged.setdefault(name.casefold(), Entry(name))
            entry.entity_ids.append(eid)
            for r in aliases:
                if r.kind == "approved_rendering" and r.alias not in entry.renderings.get(
                    r.lang, []
                ):
                    entry.renderings.setdefault(r.lang, []).append(r.alias)
    return list(merged.values())


# ---- words -----------------------------------------------------------------------------------
_WORD = re.compile(r"\w+")


def words(text: str) -> list[str]:
    return [w.casefold() for w in _WORD.findall(text)]


def core(text: str) -> list[tuple[int, str]]:
    """(position, word) of the content words of `text`, casefolded: words of 4+ letters (all of
    them when there is none). Positions count every word, so a dropped article is a changed gap."""
    ws = _WORD.findall(text)
    keep = [(i, w.casefold()) for i, w in enumerate(ws) if len(w) > 3]
    return keep or [(i, w.casefold()) for i, w in enumerate(ws)]


def _plain(w: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", w) if not unicodedata.combining(c))


def inflected(a: str, b: str) -> bool:
    """`a` and `b` differ by a 1-3 letter ending once accents are dropped (dragón / dragones)."""
    a, b = _plain(a), _plain(b)
    short, long = sorted((a, b), key=len)
    return len(short) >= 5 and long.startswith(short) and 1 <= len(long) - len(short) <= 3


def has_word(word: str, common: bool, have: Collection[str]) -> bool:
    return word in have or (common and any(inflected(word, h) for h in have))


def has_all(rendering: str, have: list[str], common: bool) -> bool:
    """The content words of `rendering` occur in `have` (target words in order) as a phrase: in
    the same order, with as many words between them as in the rendering (a dropped or added
    article is a different rendering)."""
    first, *rest = core(rendering)
    return any(
        has_word(first[1], common, [w])
        and all(
            p + i - first[0] < len(have) and has_word(word, common, [have[p + i - first[0]]])
            for i, word in rest
        )
        for p, w in enumerate(have)
    )


def near_miss(rendering: str, have: list[str], ratio: float, common: bool) -> str | None:
    """A word of `have` that resembles a content word of `rendering` that `have` lacks."""
    for _, w in core(rendering):
        if not has_word(w, common, have):
            best = max(have, key=lambda h: fuzz.ratio(w, h), default=None)
            if best is not None and fuzz.ratio(w, best) >= (ratio if len(w) >= 5 else SHORT_RATIO):
                return best
    return None


def mentions(surface: str, have: Collection[str], common: bool = False) -> bool:
    """The source side: the surface's content words; a common noun loosely (any 1-3 letter ending,
    as `has_word` does), a name exactly."""

    def seen(w: str) -> bool:
        return w in have or (
            common and len(w) >= 4 and any(_plain(h).startswith(_plain(w)) and len(h) - len(w) <= 3
                                           for h in have)
        )  # fmt: skip

    return all(seen(w) for _, w in core(surface))


def tag_renderings(e: Entry, lang: str) -> list[str]:
    """Approved renderings for the track's language: the exact tag, else any tag of the same
    language (es-419 for a track tagged es)."""
    if lang in e.renderings:
        return e.renderings[lang]
    base = lang.split("-")[0]
    return [r for tag, rs in e.renderings.items() if tag.split("-")[0] == base for r in rs]


# ---- the check -------------------------------------------------------------------------------
class Term(Check):
    check = CheckId.LOC_TERM
    requires = frozenset({Input.SOURCE_SUBS, Input.TARGET_SUBS})
    version = "1"

    @classmethod
    def active(cls, available: Collection[Input]) -> bool:
        """Source and target subtitles, and a registry: a bible or a glossary."""
        return super().active(available) and bool({Input.BIBLE, Input.GLOSSARY} & set(available))

    def __init__(
        self,
        langs: Iterable[str],
        source_lang: str,
        conn: Connection | None = None,
        show: str | None = None,
        registry: list[Entry] | None = None,
        root: Path | None = None,
        episode: str | None = None,
        others: dict[str, dict[str, list[Pair]]] | None = None,
    ):
        self.source_lang = source_lang
        self.langs = list(langs)
        self.rules = {lang: rule_pack(lang, root).get("term", {}) for lang in self.langs}
        for lang, r in self.rules.items():
            if "near_miss_ratio" not in r:
                raise ValueError(f"no term rule pack for language {lang!r}")
        if registry is None:
            registry = load_registry(conn, show) if conn is not None and show else []
        if not registry:
            log.warning("loc.term: no registry (bible or glossary rows): nothing to check")
        self.registry = registry
        self.conn, self.show, self.episode = conn, show, episode
        self._others = others  # target language -> episode ref -> pairs; None: read from the store
        self._memo: dict[str, tuple[Timeline, list[Group], dict[str, Standard]]] = {}

    def params(self) -> dict[str, Any]:
        reg = [(e.surface, sorted(e.renderings.items())) for e in self.registry]
        return {"source_lang": self.source_lang, "rules": self.rules, "registry": reg}

    def _context(self, tl: Timeline, lang: str) -> tuple[list[Group], dict[str, Standard]]:
        """(groups of aligned cues, observed standards by entry key) of target language `lang`."""
        hit = self._memo.get(lang)
        if hit is None or hit[0] is not tl:
            gs = groups(aligned(tl, self.source_lang, lang))
            hit = self._memo[lang] = (tl, gs, self._standards(tl, gs, lang))
        return hit[1], hit[2]

    def _other_pairs(self, lang: str) -> dict[str, list[Pair]]:
        if self._others is not None:
            return self._others.get(lang, {})
        if self.conn is None or self.show is None or self.episode is None:
            return {}
        return load_others(self.conn, self.show, self.episode, self.source_lang, lang)

    def _standards(self, tl: Timeline, gs: list[Group], lang: str) -> dict[str, Standard]:
        """Entries without an approved rendering that have an observed standard over the show."""
        r = self.rules[lang]
        here = [Pair(self._words(tl, g.sources), self._words(tl, g.targets)) for g in gs]
        other = [p for ps in self._other_pairs(lang).values() for p in ps]
        pairs = [*here, *other]
        df = Counter(w for p in pairs for w in set(p.tgt))  # pairs whose target has the word
        out = {}
        for e in self.registry:
            if tag_renderings(e, lang):
                continue
            seen = [p for p in pairs if mentions(e.surface, p.src, e.common)]
            if len(seen) < r["observed_min_cues"]:
                continue
            rendering = e.surface
            if len(core(e.surface)) == 1:  # the target word that singles out the mentions
                with_w = Counter(w for p in seen for w in set(p.tgt) if len(w) >= 4)
                rest = max(len(pairs) - len(seen), 1)
                lift = {w: k / len(seen) - (df[w] - k) / rest for w, k in with_w.items()}
                if not lift:
                    continue
                own = core(e.surface)[0][1]  # a name kept verbatim is the standard if it qualifies
                kept_own = with_w[own] / len(seen) if own in with_w else 0.0
                if (
                    lift.get(own, 0.0) >= r["observed_min_lift"]
                    and kept_own >= r["observed_min_share"]
                ):
                    rendering = own
                else:
                    rendering = max(lift, key=lambda w: (lift[w], w))
                    if lift[rendering] < r["observed_min_lift"]:
                        continue
            kept = [has_all(rendering, p.tgt, e.common) for p in seen]
            if sum(kept) / len(seen) < r["observed_min_share"]:
                continue
            mine = [has_all(rendering, p.tgt, e.common) for p in here
                    if mentions(e.surface, p.src, e.common)]  # fmt: skip
            theirs = [has_all(rendering, p.tgt, e.common) for p in other
                      if mentions(e.surface, p.src, e.common)]  # fmt: skip
            switched = (
                len(mine) >= r["observed_min_cues"]
                and sum(mine) / len(mine) <= r["observed_switch_here"]
                and len(theirs) >= r["observed_min_cues"]
                and sum(theirs) / len(theirs) >= r["observed_switch_others"]
            )
            out[e.key] = Standard(rendering, sum(kept), len(seen), switched)
        return out

    @staticmethod
    def _words(tl: Timeline, cue_refs: Iterable[str]) -> list[str]:
        """Words of the cues in order (duplicates kept: phrases are matched by position)."""
        return [w for ref in cue_refs if (s := tl.resolve(ref)) for w in words(s.text)]

    def inputs(self, unit: WorkUnit, tl: Timeline) -> list[str]:
        """The observed standards of the unit's language: they count mentions over the whole show
        (other episodes' aligned cues, read from the store)."""
        _, standards = self._context(tl, unit.key.split("/")[1])
        return [hashlib.sha256(repr(sorted(standards.items())).encode()).hexdigest()]

    def units(self, tl: Timeline) -> list[WorkUnit]:
        """Cue windows of each target track; a group belongs to the window of its first target
        cue, and its source cues are the unit's context."""
        out = []
        for lang in self.langs:
            gs, _ = self._context(tl, lang)
            for u in cue_windows(tl, lang):
                mine = {s.ref for s in u.spans}
                srcs = dict.fromkeys(s for g in gs if g.targets[0] in mine for s in g.sources)
                context = tuple(sp for ref in srcs if (sp := tl.resolve(ref)) is not None)
                out.append(WorkUnit(u.key, u.spans, context))
        return out

    def run(self, unit: WorkUnit, tl: Timeline) -> list[Finding]:
        lang = unit.spans[0].lang
        assert lang is not None
        mine = {s.ref for s in unit.spans}
        gs, standards = self._context(tl, lang)
        return [
            f for g in gs if g.targets[0] in mine for f in self.findings(g, lang, tl, standards)
        ]

    def findings(
        self, g: Group, lang: str, tl: Timeline, standards: dict[str, Standard]
    ) -> list[Finding]:
        src, tgt = self._words(tl, g.sources), self._words(tl, g.targets)
        ratio = float(self.rules[lang]["near_miss_ratio"])
        out = []
        for e in self.registry:
            if not mentions(e.surface, src, e.common):
                continue
            approved = tag_renderings(e, lang)
            st = standards.get(e.key)
            if not approved and st is None:
                continue
            expected = approved or [st.rendering if st else e.surface]
            if any(has_all(r, tgt, e.common) for r in expected):
                continue
            miss = next((m for r in expected if (m := near_miss(r, tgt, ratio, e.common))), None)
            if approved:
                conf = APPROVED_MISSPELLED if miss else APPROVED_MISSING
            elif miss:
                conf = OBSERVED_MISSPELLED
            else:
                conf = OBSERVED_SWITCHED if st and st.switched else OBSERVED_MISSING
            if len(g.sources) > MAX_SIDE or len(g.targets) > MAX_SIDE:
                conf = min(conf, COMPLEX_GROUP)
            shown = [e.surface if r == core(e.surface)[0][1] else r for r in expected]
            out.append(self._finding(e, shown, miss, bool(approved), conf, g, lang, tl, st))
        return out

    def _finding(self, e: Entry, expected: list[str], miss: str | None, approved: bool,
                 conf: float, g: Group, lang: str, tl: Timeline,
                 st: Standard | None = None) -> Finding:  # fmt: skip
        want = " / ".join(f'"{r}"' for r in expected)
        kind = "approved" if approved else "observed standard"
        if st is not None:
            kind += f" ({st.kept} of {st.n} mentions in the show"
            kind += ", which this episode drops)" if st.switched else ")"
        what = f'"{miss}" is a near miss of {want}' if miss else f"{want} is missing"
        cues = [c for ref in g.targets if (c := tl.resolve(ref)) is not None]
        srcs = [c for ref in g.sources if (c := tl.resolve(ref)) is not None]
        idx = refs.parse(g.targets[0]).id
        return Finding(
            severity=SHOULD_FIX if approved else MINOR,
            confidence=conf,
            title=f'Cue {idx}: "{e.surface}" should be {want}',
            explanation=(
                f'The source says "{e.surface}"; the {kind} rendering in {lang} is {want}, but '
                f"{what} in the aligned target cue{'s' if len(cues) > 1 else ''}."
                + ("" if conf >= 0.7 else " Ambiguous: left for adjudication.")
            ),
            evidence=[
                *(Evidence(kind=c.kind, ref=c.ref, role=EvidenceRole.CLAIM, quote=c.text)
                  for c in cues),
                *(Evidence(kind=c.kind, ref=c.ref, role=EvidenceRole.CONTEXT, quote=c.text,
                           lang=self.source_lang) for c in srcs),
            ],
            suggested_fix=f"Use {want}.",
            lang=lang,
        )  # fmt: skip

    def recheck(self, flag: Flag, tl: Timeline) -> bool:
        """Re-run the group of the claimed cue: the same finding still comes out."""
        claim = next(e for e in flag.evidence if e.role is EvidenceRole.CLAIM)
        if flag.lang not in self.rules or tl.resolve(claim.ref) is None:
            return False
        gs, standards = self._context(tl, flag.lang)
        return any(
            f.title == flag.title
            for g in gs
            if claim.ref in g.targets
            for f in self.findings(g, flag.lang, tl, standards)
        )

    def observed(self, tl: Timeline) -> list[tuple[Entry, str, Standard]]:
        """(entry, lang, standard) for every observed standard."""
        out = []
        for lang in self.langs:
            _, standards = self._context(tl, lang)
            out += [(e, lang, standards[e.key]) for e in self.registry if e.key in standards]
        return out


def stage(ep: Any) -> None:
    """Pipeline stage (`add_stage("loc.observed", term.stage, before="checks")`): record the
    observed standards of the show as `observed_rendering` aliases whose `occurrences` is the
    show-wide count of mentions that carry them. The rows are recomputed, not accumulated, so a
    re-run gives the same numbers; a standard that no longer holds is deleted."""
    term = next((c for c in ep.checks if isinstance(c, Term)), None)
    if term is None:
        return
    al = schema.entity_alias
    with ep.unit("loc.observed", ep.episode):
        ids = [eid for e in term.registry if not e.renderings for eid in e.entity_ids]
        if ids and term.langs:
            ep.conn.execute(
                delete(al).where(
                    al.c.entity_id.in_(ids),
                    al.c.lang.in_(term.langs),
                    al.c.kind == "observed_rendering",
                )
            )
        rows = [
            {
                "entity_id": eid,
                "lang": lang,
                "alias": e.surface if st.rendering == core(e.surface)[0][1] else st.rendering,
                "kind": "observed_rendering",
                "occurrences": st.kept,
            }
            for e, lang, st in term.observed(ep.timeline)
            for eid in e.entity_ids
        ]
        if rows:
            ins = pg_insert(al)
            ep.conn.execute(
                ins.on_conflict_do_update(
                    index_elements=["entity_id", "lang", "alias"],
                    set_={"occurrences": ins.excluded.occurrences},
                    where=al.c.kind == "observed_rendering",
                ),
                rows,
            )
