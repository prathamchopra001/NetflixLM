"""Story order and story days (architecture.md > Story order and story days, D-006).

`derive(scenes, overrides, llm)` gives every scene a `story_day`, a `story_seq` (chronological rank,
dense across the whole show, episodes in release order) and `markers`; the bible's `story_overrides`
always win. Plain functions over `SceneIn`, so unit tests and EXP-007 need no database:
`llm=None` is the rules-only arm, any object with `complete(prompt, schema)` is the rules + LLM arm.

Rules (lexicons are the module constants below; B-021: a heading's time of day is a heuristic):
- Present scenes carry a day counter (day 1 = first scene of the show, continuing across episodes).
  NEXT MORNING / NEXT DAY / "N DAYS LATER" advance it, CONTINUOUS / LATER / THAT NIGHT keep it, and
  a time of day that does not go backwards keeps it. A time of day that goes backwards with no
  cue (NIGHT then DAY) is the one ambiguous transition: the default is the next day, and with an
  LLM one schema-constrained call per transition decides (see `Verdict`).
- Flashbacks (FLASHBACK, N YEARS EARLIER, an LLM `earlier`) leave the day counter alone. A cue in
  the scene heading flashbacks that scene; a cue in the lead-in (previous scene's transitions or the
  scene's opening super) flashbacks every scene until PRESENT DAY / BACK TO PRESENT / END FLASHBACK
  or the episode ends. Their `story_day` is the override's, else the present day minus "N YEARS"
  when the cue gives N, else unknown; scenes are ranked by (day, screen order) with unknown-day
  flashbacks first. That placement is the conservative one for plot rules: a flashback never makes
  a character act before they could have known something.
- INTERCUT / SAME TIME / MEANWHILE and DREAM / VISION scenes share the `story_seq` and day of the
  last scene that does not share (marker `intercut`, `dream`, `vision`).
- `story_inferred` is true when the position is not stated: no time of day, an unresolved
  regression, a flashback without an offset, "DAYS LATER" without a number, any LLM verdict. It does
  not propagate to later scenes: their order is still rank-exact relative to each other.
- Overrides: matched on the scene ref (free text like "S01E05 scene 3" is normalised, B-020). A
  non-empty `markers` replaces the detected ones; `story_day` replaces the day (and moves the day
  counter for a present scene). Override positions are never inferred.
"""

import logging
import os
import re
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from string import Template
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, Field
from sqlalchemy import Connection, bindparam, select, update

from nip.config import config_dir
from nip.contracts import refs
from nip.contracts.plan import Slot
from nip.ingest.bible import StoryOverride, parse_bible
from nip.ingest.script import HEADING_RE
from nip.store import schema

if TYPE_CHECKING:
    from nip.ingest.script import Script
    from nip.pipeline import EpisodeRun

log = logging.getLogger(__name__)

STAGE = "knowledge.story"
PROMPT = "knowledge.story.v1.md"
MARKERS = ("flashback", "dream", "vision", "intercut", "continuous")

# --- lexicons, matched on upper-cased text (config keys are proposed in the notes, not added)
_NUMBERS = {
    **{w: i for i, w in enumerate("ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE TEN".split(), 1)},
    "A": 1, "AN": 1, "ANOTHER": 1, "TWELVE": 12,
}  # fmt: skip
_UNIT_DAYS = {"DAY": 1, "WEEK": 7, "MONTH": 30, "YEAR": 365}
_REL = re.compile(
    rf"\b(?:(\d+|{'|'.join(_NUMBERS)})\s+)?(DAY|WEEK|MONTH|YEAR)S?\s+(LATER|EARLIER)\b"
)  # "THREE YEARS EARLIER", "A WEEK LATER", "DAYS LATER"
_NEXT = re.compile(
    r"\b(?:NEXT|FOLLOWING)\s+(?:MORNING|DAY|NIGHT|EVENING|AFTERNOON)\b"
    r"|\bTHE (?:MORNING|DAY) AFTER\b"
)
_THAT = re.compile(r"\bTHAT (NIGHT|EVENING|AFTERNOON)\b")
_SAME_DAY = re.compile(
    r"\bCONTINUOUS(?:LY)?\b|\bCONTINUING\b"
    r"|\b(?:MOMENTS?|SECONDS?|MINUTES?|HOURS?) LATER\b|\bLATER\b"
)
_CONTINUOUS = re.compile(r"\bCONTINUOUS(?:LY)?\b|\bCONTINUING\b")
_END_FLASHBACK = re.compile(
    r"\bEND(?: OF)? FLASHBACK\b|\bBACK TO (?:THE )?PRESENT\b|\bPRESENT (?:DAY|TIME)\b"
)
_FLASHBACK = re.compile(r"\bFLASHBACK\b")
_INTERCUT = re.compile(r"\bINTERCUT(?:TING)?\b|\bSAME TIME\b|\bMEANWHILE\b|\bSIMULTANEOUS(?:LY)?\b")
_DREAM = re.compile(r"\bDREAM(?: SEQUENCE)?\b|\bNIGHTMARE\b")
_VISION = re.compile(r"\bVISION\b|\bHALLUCINATION\b")
_TOD = [  # (rank, words): a rank that goes down between present scenes is a possible new day
    (0, "DAWN|SUNRISE|DAYBREAK"),
    (1, "MORNING"),
    (2, r"AFTERNOON|NOON|MIDDAY|DAY"),
    (3, "EVENING|DUSK|SUNSET|TWILIGHT"),
    (4, "NIGHT|MIDNIGHT"),
]
_TOD_RE = [(r, re.compile(rf"\b(?:{w})\b")) for r, w in _TOD]
_NO_TOD = re.compile(r"\b(?:NEXT|FOLLOWING) DAY\b|\bTHE DAY AFTER\b")
_SCENE_NO = re.compile(r"^\s*S(\d+)E(\d+)\W*(?:SC(?:ENE)?\W*)?(\S+?)\s*$", re.IGNORECASE)
_CAPS_MAX = 80  # an all-caps action line this short is a super or slug, not prose


@dataclass(frozen=True)
class SceneIn:
    """One scene in screen order: `ref` is `S01E01/sc/3`; `elements` are (kind, text) as in the
    script (`nip.ingest.script.Element`, or `script_line` rows)."""

    ref: str
    heading: str
    elements: tuple[tuple[str, str], ...] = ()

    @property
    def episode(self) -> str:
        return self.ref.split("/", 1)[0]


@dataclass(frozen=True)
class Position:
    ref: str
    markers: tuple[str, ...]
    story_day: int | None
    story_seq: int
    inferred: bool
    source: Literal["rule", "llm", "override"]


@dataclass
class Story:
    positions: list[Position]
    unmatched: list[str] = field(default_factory=list)  # override keys that matched no scene
    ambiguous: int = 0  # transitions the rules could not settle
    llm_calls: int = 0  # LLM verdicts obtained (memo hits and failures excluded)


class Verdict(BaseModel):
    """The LLM's answer for one ambiguous transition (config/prompts/knowledge.story.v1.md)."""

    relation: Literal["next_day", "same_day", "later_days", "earlier", "simultaneous"]
    days: int = Field(1, ge=1, le=3650)
    reason: str = ""


class LLM(Protocol):
    def complete[M: BaseModel](self, prompt: str, schema: type[M], **kw: Any) -> M: ...


Unit = Callable[[str], AbstractContextManager[None]]


def scenes_from_script(ep: str, script: "Script") -> list[SceneIn]:
    return [
        SceneIn(refs.scene(ep, s.number), s.heading, tuple((e.kind, e.text) for e in s.elements))
        for s in script.scenes
    ]


# --- reading cues ------------------------------------------------------------------------------
def _caps(kind: str, text: str) -> bool:
    return kind == "transition" or (kind == "action" and text.isupper() and len(text) <= _CAPS_MAX)


def _tail(heading: str) -> str:
    """Every " - " segment of the heading except the location (the one starting INT./EXT., else
    the first), plus every parenthetical: where a heading states time and markers, in any position
    (`FLASHBACK - INT. B - DAY`, `INT. B - FLASHBACK - NIGHT`). Location names such as DREAM HOUSE
    stay out of it."""
    h = heading.upper()
    segs = h.split(" - ")
    loc = next((i for i, x in enumerate(segs) if HEADING_RE.match(x)), 0)
    rest = [x for i, x in enumerate(segs) if i != loc]
    return f"{' '.join(rest)} {' '.join(re.findall(r'\(([^)]*)\)', h))}"


def _tod(text: str) -> int | None:
    text = _NO_TOD.sub("", _REL.sub("", re.sub(r"\([^)]*\)", " ", text)))
    hits = [(m.start(), r) for r, rx in _TOD_RE if (m := rx.search(text))]
    return min(hits)[1] if hits else None


@dataclass
class Cues:
    heading_flash: bool = False  # FLASHBACK in the heading: this scene only
    span_flash: bool = False  # in the lead-in: until the end cue
    end_flash: bool = False
    back_days: int | None = None  # "THREE YEARS EARLIER"
    markers: tuple[str, ...] = ()  # intercut, dream, vision, continuous
    new_days: int | None = None  # exact days since the last present scene
    next_cue: bool = False  # NEXT MORNING and the like (not "3 DAYS LATER")
    fuzzy_days: int | None = None  # "WEEKS LATER": a unit known, the count not
    same_day: bool = False
    tod: int | None = None
    now_tod: int | None = None  # time of day a THAT NIGHT / NEXT MORNING cue forces


def _paras(s: SceneIn) -> list[tuple[str, str]]:
    """Elements as (kind, text), an action element split into paragraphs: the Fountain reader
    joins consecutive action paragraphs into one element."""
    return [(k, p) for k, t in s.elements for p in (t.split("\n\n") if k == "action" else [t])]


def _cues(s: SceneIn, prev: SceneIn | None) -> Cues:
    tail = _tail(s.heading)
    lead = [t.upper() for k, t in _paras(s)[:1] if _caps(k, t)]  # a super opening the scene
    if prev is not None:  # what the previous scene hands over: its transitions, a closing slug
        pp = _paras(prev)
        lead += [t.upper() for k, t in pp if k == "transition"]
        lead += [t.upper() for k, t in pp[-1:] if _caps(k, t) and k != "transition"]
    head, lead_text = tail, " | ".join(lead)
    both = f"{head} | {lead_text}"
    c = Cues(tod=_tod(head))
    c.end_flash = bool(_END_FLASHBACK.search(both))
    for text, is_head in ((head, True), (lead_text, False)):
        text = _END_FLASHBACK.sub(" ", text)
        rel = next((m for m in _REL.finditer(text) if m[3] == "EARLIER"), None)
        if _FLASHBACK.search(text) or rel:
            c.heading_flash |= is_head
            c.span_flash |= not is_head
            if rel and rel[1]:
                c.back_days = _NUMBERS.get(rel[1]) or int(rel[1])
                c.back_days *= _UNIT_DAYS[rel[2]]
    marks = [n for n, rx in (("intercut", _INTERCUT), ("dream", _DREAM), ("vision", _VISION),
                             ("continuous", _CONTINUOUS)) if rx.search(both)]  # fmt: skip
    c.markers = tuple(marks)
    later = next((m for m in _REL.finditer(both) if m[3] == "LATER"), None)
    nxt, that = _NEXT.search(both), _THAT.search(both)
    if later:
        n = (_NUMBERS.get(later[1]) or int(later[1])) if later[1] else None
        if n is not None:
            c.new_days = n * _UNIT_DAYS[later[2]]
        else:
            c.fuzzy_days = _UNIT_DAYS[later[2]]
    elif nxt:
        c.new_days, c.next_cue = 1, True
    elif that:
        c.same_day, c.now_tod = True, _tod(that[0])
    elif _SAME_DAY.search(both):
        c.same_day = True
    return c


# --- overrides ---------------------------------------------------------------------------------
def override_ref(key: str) -> str:
    """`S01E05/sc/3` for "S01E05 scene 3", "s1e5 sc 3", "S01E05/sc/3"; else `key` as given."""
    m = _SCENE_NO.match(key)
    return refs.scene(f"S{int(m[1]):02d}E{int(m[2]):02d}", m[3]) if m else key.strip()


# --- the LLM step ------------------------------------------------------------------------------
@contextmanager
def _swallow(key: str) -> Iterator[None]:
    try:
        yield
    except Exception:
        log.exception("story unit %s failed; the rule default stands", key)


def _excerpt(s: SceneIn, limit: int = 600) -> str:
    body = "\n".join(t for _, t in s.elements)
    return f"{s.heading}\n{body[:limit]}"


def build_prompt(
    prev: SceneIn, prev_day: int, prev_tod: int | None, cur: SceneIn, nxt: SceneIn | None
) -> str:
    tod = next((w.split("|")[0] for r, w in _TOD if r == prev_tod), "unknown")
    return Template((config_dir() / "prompts" / PROMPT).read_text(encoding="utf-8")).substitute(
        transition=(
            "The second scene opens a new episode."
            if prev.episode != cur.episode
            else "Both scenes are in the same episode."
        ),
        prev_day=prev_day,
        prev_tod=tod,
        prev_scene=_excerpt(prev),
        next_scene=_excerpt(cur),
        following=nxt.heading if nxt and nxt.episode == cur.episode else "(none)",
    )


# --- derivation --------------------------------------------------------------------------------
@dataclass
class _P:  # working record of one scene
    kind: Literal["present", "flash", "share"] = "present"
    markers: list[str] = field(default_factory=list)
    day: int | None = None
    inferred: bool = False
    source: Literal["rule", "llm", "override"] = "rule"
    base: int = -1  # share: index of the scene whose seq it takes


class _Deriver:
    def __init__(
        self,
        scenes: Sequence[SceneIn],
        ov: dict[str, StoryOverride],
        story: Story,
        llm: LLM | None,
        unit: Unit,
        memo: dict[Any, Verdict],
    ) -> None:
        self.scenes, self.ov, self.story = scenes, ov, story
        self.llm, self.unit, self.memo = llm, unit, memo
        self.out: list[_P] = []
        self.day = 1  # the present chain: day counter, last time-of-day rank
        self.tod: int | None = None
        self.after_next: int | None = None  # time of day the last present scene opened a day with
        self.last = -1  # index of the last present scene
        self.base = -1  # index of the last scene that does not share a seq
        self.span: tuple[int | None, bool] | None = None  # (day, inferred) of a running flashback

    def run(self) -> None:
        cur_ep = None
        for i, s in enumerate(self.scenes):
            if s.episode != cur_ep:  # a new episode starts in the present, with no lead-in
                cur_ep, self.span, prev = s.episode, None, None
            else:
                prev = self.scenes[i - 1]
            self.scene(i, _cues(s, prev), self.ov.get(s.ref))

    def scene(self, i: int, c: Cues, o: StoryOverride | None) -> None:
        detect = not (o and o.markers)  # a non-empty override list replaces the detected markers
        p = _P(markers=list(c.markers) if detect else [m.lower() for m in o.markers])  # type: ignore[union-attr]
        if o:
            p.source = "override"
        if c.end_flash:
            self.span = None
        if detect and c.span_flash:
            self.span = (self.day - c.back_days if c.back_days else None, not c.back_days)
        if detect:
            flash = c.heading_flash or self.span is not None
        else:
            flash = "flashback" in p.markers
        if flash:
            p.kind = "flash"
            if "flashback" not in p.markers:
                p.markers.append("flashback")
            p.day, p.inferred = self.flash_day(c, o, detect)
        elif self.base >= 0 and {"intercut", "dream", "vision"} & set(p.markers):
            if o and o.story_day is not None:
                # a stated day beats sharing: own unit at that day, marker kept
                p.kind, p.day = "flash", o.story_day
            else:
                p.kind, p.day = "share", self.out[self.base].day
        else:
            self.present(i, c, o, p)
        if p.kind == "share":
            p.base = self.base
        else:
            self.base = i
        if p.kind == "present":
            assert p.day is not None
            keep = None if p.day > self.day else self.tod  # a new day forgets the old time of day
            self.day = p.day
            self.tod = next((t for t in (c.now_tod, c.tod, keep) if t is not None), None)
            self.after_next = c.tod if c.next_cue else None
            self.last = i
        self.out.append(p)

    def flash_day(self, c: Cues, o: StoryOverride | None, detect: bool) -> tuple[int | None, bool]:
        if o and o.story_day is not None:
            return o.story_day, False
        if detect and c.heading_flash and c.back_days:
            return self.day - c.back_days, False
        if detect and self.span is not None:
            return self.span
        return None, True  # first in the show is a guess, an override or not

    def present(self, i: int, c: Cues, o: StoryOverride | None, p: _P) -> None:
        if o and o.story_day is not None:
            p.day = o.story_day
        elif self.last < 0:
            p.day = 1  # the first present scene of the show is day 1
        elif c.new_days is not None:
            # two NEXT MORNING scenes in a row are one morning
            again = c.next_cue and self.after_next is not None and self.after_next == c.tod
            p.day = self.day + (0 if again else c.new_days)
        elif c.fuzzy_days is not None:
            p.day, p.inferred = self.day + c.fuzzy_days, True
        elif c.same_day:
            p.day = self.day
        elif c.tod is None or self.tod is None:
            p.day, p.inferred = self.day, True  # nothing states the time of day
        elif c.tod >= self.tod:
            p.day = self.day
        else:  # the one ambiguous transition: the time of day goes back with no cue
            self.story.ambiguous += 1
            p.day, p.inferred = self.day + 1, True
            if (v := self.ask(i)) is not None:
                self.verdict(p, v, overridden=o is not None)

    def verdict(self, p: _P, v: Verdict, overridden: bool) -> None:
        """An override (here: markers without a day) always wins: the LLM only fills the day."""
        if overridden and v.relation in ("earlier", "simultaneous"):
            return
        p.source = "override" if overridden else "llm"
        if v.relation == "same_day":
            p.day = self.day
        elif v.relation == "later_days":
            p.day = self.day + max(v.days, 2)
        elif v.relation == "earlier":
            p.kind, p.day = "flash", self.day - v.days
            p.markers.append("flashback")
        elif v.relation == "simultaneous":
            p.kind, p.day = "share", self.out[self.base].day
            p.markers.append("intercut")

    def ask(self, i: int) -> Verdict | None:
        if self.llm is None:
            return None
        nxt = self.scenes[i + 1] if i + 1 < len(self.scenes) else None
        prompt = build_prompt(self.scenes[self.last], self.day, self.tod, self.scenes[i], nxt)
        if prompt in self.memo:
            return self.memo[prompt]
        v: Verdict | None = None
        with self.unit(self.scenes[i].ref):
            v = self.llm.complete(prompt, Verdict, max_tokens=300)
            self.story.llm_calls += 1
        if v is not None:
            self.memo[prompt] = v
        return v


def derive(
    scenes: Sequence[SceneIn],
    overrides: Iterable[StoryOverride] = (),
    llm: LLM | None = None,
    *,
    unit: Unit = _swallow,
    memo: dict[Any, Verdict] | None = None,
) -> Story:
    """Positions for `scenes` (all episodes of the show, release order, then script order).

    `unit(key)` wraps each LLM call (the pipeline passes `ep.unit`, which records the work unit and
    swallows a failure; the default only logs): a call that fails leaves the rule default.
    `memo` caches verdicts by prompt across calls."""
    known = {s.ref for s in scenes}
    ov: dict[str, StoryOverride] = {}
    story = Story([])
    for o in overrides:
        if (r := override_ref(o.scene)) in known:
            ov[r] = o
        else:
            story.unmatched.append(o.scene)
    d = _Deriver(scenes, ov, story, llm, unit, {} if memo is None else memo)
    d.run()
    story.positions = _rank(scenes, d.out)
    return story


def _rank(scenes: Sequence[SceneIn], out: list[_P]) -> list[Position]:
    """story_seq: units (a scene plus the scenes that share its seq) sorted by (day, screen order);
    unknown-day flashbacks first. Dense from 1."""
    heads = [i for i, p in enumerate(out) if p.kind != "share"]
    heads.sort(key=lambda i: (out[i].day is not None, out[i].day or 0, i))
    seq = {h: n for n, h in enumerate(heads, 1)}
    return [
        Position(
            s.ref,
            tuple(dict.fromkeys(p.markers)),
            p.day,
            seq[p.base if p.kind == "share" else i],
            p.inferred,
            p.source,
        )
        for i, (s, p) in enumerate(zip(scenes, out, strict=True))
    ]


# --- confidence --------------------------------------------------------------------------------
def story_confidence(confidence: float, inferred: bool) -> float:
    """`confidence` times NIP_INFERRED_STORY_CONFIDENCE_FACTOR (0.85) when a flag depends on an
    inferred story position (architecture.md > Story order)."""
    return (
        confidence * float(os.environ.get("NIP_INFERRED_STORY_CONFIDENCE_FACTOR", 0.85))
        if inferred
        else confidence
    )


def kendall_tau(truth: Mapping[str, int], got: Mapping[str, int]) -> float:
    """Kendall tau-b between two story orders (ref -> seq) over their common refs: ties (scenes
    sharing a seq) are handled; 1.0 = same order. EXP-007's pairwise order agreement."""
    from scipy.stats import kendalltau

    refs_ = sorted(truth.keys() & got.keys())
    return float(kendalltau([truth[r] for r in refs_], [got[r] for r in refs_]).statistic)


# --- the store ---------------------------------------------------------------------------------
def load_scenes(conn: Connection, show: str) -> tuple[list[SceneIn], dict[str, int]]:
    """Every scene of the show in episode release order then script order, and ref -> scene.id."""
    sc, ep, ln = schema.scene, schema.episode, schema.script_line
    rows = conn.execute(
        select(sc.c.id, ep.c.ref, sc.c.script_scene_no, sc.c.heading)
        .join(ep, ep.c.id == sc.c.episode_id)
        .join(schema.show, schema.show.c.id == ep.c.show_id)
        .where(schema.show.c.slug == show)
        .order_by(ep.c.episode_seq, sc.c.id)
    ).all()
    lines: dict[int, list[tuple[str, str]]] = {r.id: [] for r in rows}
    for sid, kind, text in conn.execute(
        select(ln.c.scene_id, ln.c.kind, ln.c.text)
        .where(ln.c.scene_id.in_(lines))
        .order_by(ln.c.scene_id, ln.c.seq)
    ):
        lines[sid].append((kind, text))
    scenes = [
        SceneIn(refs.scene(r.ref, r.script_scene_no), r.heading, tuple(lines[r.id])) for r in rows
    ]
    return scenes, {sc_.ref: r.id for sc_, r in zip(scenes, rows, strict=True)}


def load_overrides(conn: Connection, s3: Any, show: str) -> list[StoryOverride]:
    """`story_overrides` of the show's latest ingested bible (none when there is no bible)."""
    f = schema.source_file
    row = conn.execute(
        select(f.c.object_key)
        .join(schema.show, schema.show.c.id == f.c.show_id)
        .where(schema.show.c.slug == show, f.c.kind == "bible")
        .order_by(f.c.id.desc())
        .limit(1)
    ).first()
    if row is None:
        return []
    from nip.store import objects

    body = s3.get_object(Bucket=objects.media_bucket(), Key=row.object_key)["Body"].read()
    parsed = parse_bible(body)
    return parsed.data.story_overrides if parsed.data else []


def write_positions(
    conn: Connection, ids: Mapping[str, int], positions: Iterable[Position]
) -> None:
    """Persist markers, story_day, story_seq, story_inferred (one executemany)."""
    sc = schema.scene
    rows = [
        {
            "b_id": ids[p.ref],
            "b_markers": list(p.markers),
            "b_day": p.story_day,
            "b_seq": p.story_seq,
            "b_inf": p.inferred,
        }
        for p in positions
    ]
    if rows:
        conn.execute(
            update(sc)
            .where(sc.c.id == bindparam("b_id"))
            .values(
                markers=bindparam("b_markers"),
                story_day=bindparam("b_day"),
                story_seq=bindparam("b_seq"),
                story_inferred=bindparam("b_inf"),
            ),
            rows,
        )


_VERDICTS: dict[str, dict[Any, Verdict]] = {}  # per model variant; one ask per prompt


def make_llm(variant: str) -> Any:
    from nip.runtime.clients.llm import LLMClient, StubLLM

    return StubLLM(variant) if variant == "stub" else LLMClient(variant)


def stage_story(ep: "EpisodeRun") -> None:
    """Pipeline stage `knowledge.story` (`pipeline.add_stage(story.STAGE, story.stage_story)`).

    Story order is a property of the whole show (flashbacks move scenes across episodes, seq is
    show-wide), so every episode's stage re-derives all ingested scenes; the rows are overwritten
    and the LLM verdicts are memoised by prompt, so each transition is asked once per process.
    No `text_llm` decision in the Plan (B-044): rules only."""
    scenes, ids = load_scenes(ep.conn, ep.show)
    d = ep.plan.decisions.get(Slot.TEXT_LLM)
    variant = d.variant if d else None
    llm = make_llm(variant) if variant else None

    def unit(key: str) -> AbstractContextManager[None]:
        return ep.unit(STAGE, key, model_variant=variant)

    story = derive(
        scenes,
        load_overrides(ep.conn, ep.s3, ep.show),
        llm,
        unit=unit,
        memo=_VERDICTS.setdefault(variant or "", {}),
    )
    for k in story.unmatched:
        log.warning("story_overrides: no scene matches %r", k)
    write_positions(ep.conn, ids, story.positions)
