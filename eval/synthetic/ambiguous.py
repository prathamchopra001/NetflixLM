"""The "ambiguous transitions" variant of the synthetic show (`build(seed, ambiguous=True)`).

`ambiguate(show, seed)` rewrites a clean show so that story time is no longer stated where the
story-order rules look (the heading, the previous scene's transitions, an all-caps super) but only
in ordinary action or dialogue prose, and recomputes the exact truth (`story_day`, `story_seq`,
`marker`). Deterministic per seed; the clean generator output is untouched.

Per scene kind (the second value in the returned notes):
- `loose_next_day`: every NEXT MORNING heading becomes plain MORNING. The time of day goes back,
  the rules cannot tell why; the next day is right. Only an LLM that errs can lose here.
- `later_unstated`: a few NEXT MORNING headings become LATER. The rules read that as the same day
  and never ask anyone (a day-count error, no order error).
- `flashback_unmarked`: the two casualty flashbacks lose "(FLASHBACK)" and "Years earlier.", four
  chat scenes become memories and two more chat scenes after a death become memories of that
  casualty (they replace one of the scene's characters); each says "<N> years ago." in its
  opening action and its heading's time of day goes back. Truth: a flashback, N * 365 days
  before the preceding present day. Rules-only keeps them in screen order (so the dead speak
  after their death).
- `simultaneous_unmarked`: each SAME TIME scene loses its heading tag and opens with "At the same
  moment" (or similar) in prose; the time of day goes back where it can. Truth: shares the seq of
  the scene before it.
A scene whose heading cannot go back (the previous time of day is the first one) is a silent case:
the rules see no ambiguity, so no LLM is asked (the notes mark it `silent`).
"""

import random
import re

from eval.synthetic.generate import TODS, _story_seq
from eval.synthetic.model import Entity, Line, Scene, Show, find_mentions
from nip.contracts import refs

N_LATER, N_MEMORIES, N_DEAD = 4, 4, 2
YEARS = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen"
YEAR_WORDS = YEARS.split()
SAME_TIME = ["At the same moment, ", "Meanwhile, ", "Across the harbor, at that very moment, "]
HEAD = re.compile(r"^(?P<loc>.* - )(?P<tod>[A-Z ]+?)(?P<tag> \([A-Z ]+\))?$")


def _split(heading: str) -> tuple[str, str]:
    m = HEAD.match(heading)
    assert m, heading
    return m["loc"], m["tod"]


def _tod_idx(sc: Scene) -> int:
    t = _split(sc.heading)[1]
    return 0 if t in ("NEXT MORNING", "MORNING") else TODS.index(t) if t in TODS else -1


def _retime(sc: Scene, tod: str) -> None:
    sc.heading = _split(sc.heading)[0] + tod


def _edit(sc: Scene, entities: list[Entity], old: str, new: str) -> None:
    """Replace `old` by `new` in the opening line and in the quotes it backs (quotes stay
    substrings of the text), then find the mentions again."""
    ln: Line = sc.lines[0]
    ln.text = ln.text.replace(old, new, 1) if old else new + ln.text
    for f in ln.facts:
        f.quote = f.quote.replace(old, new, 1) if old and old in f.quote else f.quote
    ln.mentions = find_mentions(entities, ln.text)


def _swap(show: Show, sc: Scene, old: str, new: str) -> None:
    """Replace character `old` by `new` in the scene: names, nicknames and descriptions in the
    text and quotes, speakers, fact subjects and objects."""
    new_e = show.entity(new)
    alias = {"name": new_e.name.split()[0], "nickname": new_e.aliases[0][0],
             "description": new_e.aliases[1][0]}  # fmt: skip
    for ln in sc.lines:
        sub = {
            m.surface: new_e.name if " " in m.surface else alias[m.kind]
            for m in ln.mentions
            if m.entity == old
        }

        def fix(t: str, sub: dict[str, str] = sub) -> str:
            for a, b in sub.items():
                t = re.sub(f"(?<![A-Za-z]){re.escape(a)}(?![A-Za-z])", b, t)
            return t

        ln.text = fix(ln.text)
        ln.speaker = new if ln.speaker == old else ln.speaker
        for f in ln.facts:
            f.quote = fix(f.quote)
            f.subject = new if f.subject == old else f.subject
            f.object = new if f.object == old else f.object
        ln.mentions = find_mentions(show.entities, ln.text)


def ambiguate(show: Show, seed: int) -> tuple[Show, dict[str, str]]:
    """The ambiguous variant of `show` (modified in place) and {scene ref: kind} notes."""
    rng = random.Random(f"synthetic-ambiguous/{seed}")
    flat = [(ep, sc) for ep, scs in show.episodes.items() for sc in scs]
    notes: dict[str, str] = {}
    ents = show.entities

    def note(ep: str, sc: Scene, kind: str) -> None:
        notes[refs.scene(ep, sc.no)] = kind

    def back(i: int) -> str | None:
        """A time of day earlier than the previous scene's, or None when none exists."""
        p = _tod_idx(flat[i - 1][1]) if i else -1
        return TODS[rng.randrange(p)] if p >= 1 else None

    nexts = [i for i, (_, sc) in enumerate(flat) if _split(sc.heading)[1] == "NEXT MORNING"]
    later = set(rng.sample([i for i in nexts if flat[i][1].marker is None], N_LATER))
    for i in nexts:
        ep, sc = flat[i]
        _retime(sc, "LATER" if i in later else "MORNING")
        note(ep, sc, "later_unstated" if i in later else "loose_next_day")

    # memories: chat scenes (present_at facts only), same day as the scene before them
    chat = [
        i
        for i, (_, sc) in enumerate(flat)
        if i
        and sc.marker is None
        and not notes.get(refs.scene(flat[i][0], sc.no))
        and {f.predicate for ln in sc.lines for f in ln.facts} == {"present_at"}
        and flat[i - 1][1].story_day == sc.story_day
        and _tod_idx(flat[i - 1][1]) >= 1
        and not (i + 1 < len(flat) and flat[i + 1][1].marker == "same_time")
        and flat[i - 1][1].marker != "flashback"
    ]
    flashes = [i for i, (_, sc) in enumerate(flat) if sc.marker == "flashback"]
    died = {
        f.subject: i
        for i, (_, sc) in enumerate(flat)
        for ln in sc.lines
        for f in ln.facts
        if (f.value or {}).get("state") == "dead"
    }
    after = [
        (i, c) for i in chat for c, d in died.items() if i > d and c not in show.cast(flat[i][1])
    ]
    dead = {
        i: rng.choice([c for j, c in after if j == i])
        for i in rng.sample(sorted({i for i, _ in after}), N_DEAD)
    }
    picked = flashes + rng.sample([i for i in chat if i not in dead], N_MEMORIES) + list(dead)
    years = rng.sample(range(3, 11), len(picked))  # Verdict.days caps at 3650 (ten years)
    for i, y in zip(picked, years, strict=True):
        ep, sc = flat[i]
        prev = next(s for _, s in reversed(flat[:i]) if s.marker != "flashback")
        said = f"{YEAR_WORDS[y].capitalize()} years ago. "
        if i in dead:
            _swap(show, sc, rng.choice(sorted(show.cast(sc))), dead[i])
        _edit(sc, ents, "Years earlier. " if i in flashes else "", said)
        sc.marker, sc.story_day = "flashback", prev.story_day - 365 * y
        sc.heading = sc.heading.removesuffix(" (FLASHBACK)")
        t = back(i)
        if t:
            _retime(sc, t)
        note(ep, sc, "flashback_unmarked" if t else "flashback_unmarked,silent")

    for i, (ep, sc) in enumerate(flat):
        if sc.marker == "same_time":
            _edit(sc, ents, "", rng.choice(SAME_TIME))
            sc.heading = sc.heading.removesuffix(" (SAME TIME)")
            t = back(i)
            if t:
                _retime(sc, t)
            note(ep, sc, "simultaneous_unmarked" if t else "simultaneous_unmarked,silent")

    _story_seq(show.episodes)
    return show, notes
