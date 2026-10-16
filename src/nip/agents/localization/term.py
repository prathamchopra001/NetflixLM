"""`loc.term`: names and terms rendered inconsistently in the target track.

architecture.md > Agent 1 > Names & terms. Deterministic: the registry's names and glossary terms
are looked up in each group of aligned source cues (`nip.timeline.cue_align.groups`), and the
aligned target cues must carry the approved rendering (glossary), or the observed standard when
there is none. Matching is by word: casefolded, short words (articles) ignored, a common noun may
differ by a 1-3 letter ending (inflection); a proper noun, or an accent changed, may not. A word
that is missing but resembles one in the target (rapidfuzz) is a misspelling.

Confidence: approved rendering missing 0.80, misspelled 0.92; observed standard missing 0.55 (below
0.70, so suppressed: the name may be dropped for a pronoun, an LLM adjudicates in Phase 3),
misspelled 0.85; any finding in a group of more than 2 source or 2 target cues 0.65 (alignment
less sure).

`ponytail:` the observed standard is the name kept verbatim, in the cues of one episode; a name
that is translated every time has no standard and nothing is checked. Occurrences are written per
episode run (`stage`), the table has no episode column.
"""

import logging
import re
import unicodedata
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy import Connection, select
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
OBSERVED_MISSING, OBSERVED_MISSPELLED = 0.55, 0.85
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


def mentions(surface: str, have: Collection[str]) -> bool:
    """The source side: the surface's content words, loosely (any 1-3 letter ending)."""

    def seen(w: str) -> bool:
        return w in have or (
            len(w) >= 4 and any(_plain(h).startswith(_plain(w)) and len(h) - len(w) <= 3
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
        self._memo: dict[str, tuple[Timeline, list[Group], set[str]]] = {}

    def params(self) -> dict[str, Any]:
        reg = [(e.surface, sorted(e.renderings.items())) for e in self.registry]
        return {"source_lang": self.source_lang, "rules": self.rules, "registry": reg}

    def _context(self, tl: Timeline, lang: str) -> tuple[list[Group], set[str]]:
        """(groups of aligned cues, keys of entries whose observed standard exists in `lang`)."""
        hit = self._memo.get(lang)
        if hit is None or hit[0] is not tl:
            gs = groups(aligned(tl, self.source_lang, lang))
            hit = self._memo[lang] = (tl, gs, self._standards(tl, gs, lang))
        return hit[1], hit[2]

    def _standards(self, tl: Timeline, gs: list[Group], lang: str) -> set[str]:
        """Entries without an approved rendering whose name is kept verbatim in most groups."""
        r = self.rules[lang]
        out = set()
        for e in self.registry:
            if tag_renderings(e, lang):
                continue
            n = kept = 0
            for g in gs:
                if mentions(e.surface, self._words(tl, g.sources)):
                    n += 1
                    kept += has_all(e.surface, self._words(tl, g.targets), e.common)
            if n >= r["observed_min_cues"] and kept / n >= r["observed_min_share"]:
                out.add(e.key)
        return out

    @staticmethod
    def _words(tl: Timeline, cue_refs: Iterable[str]) -> list[str]:
        """Words of the cues in order (duplicates kept: phrases are matched by position)."""
        return [w for ref in cue_refs if (s := tl.resolve(ref)) for w in words(s.text)]

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

    def findings(self, g: Group, lang: str, tl: Timeline, standards: set[str]) -> list[Finding]:
        src, tgt = self._words(tl, g.sources), self._words(tl, g.targets)
        ratio = float(self.rules[lang]["near_miss_ratio"])
        out = []
        for e in self.registry:
            if not mentions(e.surface, src):
                continue
            approved = tag_renderings(e, lang)
            if not approved and e.key not in standards:
                continue
            expected = approved or [e.surface]
            if any(has_all(r, tgt, e.common) for r in expected):
                continue
            miss = next((m for r in expected if (m := near_miss(r, tgt, ratio, e.common))), None)
            conf = (APPROVED_MISSPELLED if miss else APPROVED_MISSING) if approved else (
                OBSERVED_MISSPELLED if miss else OBSERVED_MISSING)  # fmt: skip
            if len(g.sources) > MAX_SIDE or len(g.targets) > MAX_SIDE:
                conf = min(conf, COMPLEX_GROUP)
            out.append(self._finding(e, expected, miss, bool(approved), conf, g, lang, tl))
        return out

    def _finding(self, e: Entry, expected: list[str], miss: str | None, approved: bool,
                 conf: float, g: Group, lang: str, tl: Timeline) -> Finding:  # fmt: skip
        want = " / ".join(f'"{r}"' for r in expected)
        kind = "approved" if approved else "observed standard"
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

    def observed(self, tl: Timeline) -> list[tuple[Entry, str, int]]:
        """(entry, lang, groups that keep the name) for every observed standard."""
        out = []
        for lang in self.langs:
            gs, standards = self._context(tl, lang)
            for e in self.registry:
                if e.key in standards:
                    n = sum(
                        has_all(e.surface, self._words(tl, g.targets), e.common)
                        for g in gs
                        if mentions(e.surface, self._words(tl, g.sources))
                    )
                    out.append((e, lang, n))
        return out


def stage(ep: Any) -> None:
    """Pipeline stage (`add_stage("loc.observed", term.stage, before="checks")`): record each
    observed standard as an `observed_rendering` alias with its occurrences."""
    term = next((c for c in ep.checks if isinstance(c, Term)), None)
    if term is None:
        return
    with ep.unit("loc.observed", ep.episode):
        rows = [
            {"entity_id": eid, "lang": lang, "alias": e.surface, "kind": "observed_rendering",
             "occurrences": n}
            for e, lang, n in term.observed(ep.timeline)
            for eid in e.entity_ids
        ]  # fmt: skip
        if rows:
            ins = pg_insert(schema.entity_alias)
            ep.conn.execute(
                ins.on_conflict_do_update(
                    index_elements=["entity_id", "lang", "alias"],
                    set_={"occurrences": ins.excluded.occurrences},
                ),
                rows,
            )
