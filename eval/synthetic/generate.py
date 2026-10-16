"""Template generator for the synthetic show (R2: no LLM; truth is exact by construction).

6 episodes x 25 scenes. A seeded plan puts arc events into scene slots, then every slot is filled
by a template: secrets are discovered, confided and referred to in order; props are set up,
obtained, used and destroyed; two casualties die and later appear only in flashbacks; each episode
has one INTERCUT (SAME TIME) pair of scenes in different places; the rest are chat scenes. The
result is a clean show: none of the Layer 1 plot rules fires on it, and the plot injectors then
plant violations.

Template markup: `@x` (first name), `@x.full`, `@x.nick`, `@x.desc`, `@x.any` (random alias) name
the entity bound to `x`; `[[...]]` marks the quote that backs the line's facts (default: the whole
line). Mentions are recorded as they are rendered.
"""

import random
import re
from collections.abc import Sequence
from typing import Any

from eval.synthetic.model import Entity, Fact, Line, Mention, Scene, Show, merge_actions

EPISODES = [f"S01E{e:02d}" for e in range(1, 7)]
SCENES_PER_EP = 25
N = len(EPISODES) * SCENES_PER_EP
TODS = ("MORNING", "DAY", "DUSK", "NIGHT")

# id, first, last, nickname, description, gender
CAST = [
    ("maya", "Maya", "Reyes", "May", "the detective", "female"),
    ("leo", "Leo", "Park", "Lee", "the rookie", "male"),
    ("ada", "Ada", "Kovac", "Addie", "the informant", "female"),
    ("tomas", "Tomas", "Vale", "Tom", "the harbormaster", "male"),
    ("ines", "Ines", "Okafor", "Nes", "the courier", "female"),
    ("rui", "Rui", "Marlow", "Ruiz", "the engineer", "male"),
    ("nell", "Nell", "Quillan", "Nelly", "the clerk", "female"),
    ("orin", "Orin", "Hale", "Old O", "the old man", "male"),
    ("sasha", "Sasha", "Brandt", "Sash", "the pilot", "female"),
    ("dov", "Dov", "Lindqvist", "Dovvy", "the medic", "male"),
]
LOCS = [
    ("Harbor Warehouse", "INT"),
    ("Pier Nine", "EXT"),
    ("Tidewater Diner", "INT"),
    ("Customs Office", "INT"),
    ("Signal Hill", "EXT"),
    ("Marrow Street Garage", "INT"),
    ("The Lantern Bar", "INT"),
    ("Ferry Terminal", "EXT"),
    ("Saltworks Yard", "EXT"),
    ("Quill Archive", "INT"),
    ("Greywater Dock", "EXT"),
    ("Station House", "INT"),
]
PROPS = [
    ("key", "rusted key", "lock on the archive door"),
    ("ledger", "brass ledger", "safe behind the counter"),
    ("radio", "portable radio", "harbor channel"),
    ("lantern", "storm lantern", "signal tower"),
    ("folder", "blue folder", "evidence locker"),
    ("watch", "pocket watch", "clock case"),
    ("flare", "signal flare", "hatch of the ferry"),
    ("map", "tide map", "chart table"),
]
SECRETS = [
    "@s.full is the informant",
    "@s.full started the fire at {loc}",
    "@s.full forged the customs ledger",
    "@s.full takes money from Greywater Holdings",
]
OPENERS = [
    "Did you sleep at all, @b?",
    "@b, have you seen the tide tables?",
    "Hey @b.any, got a minute?",
    "Tell me {loc} is still standing, @b.",
    "Nobody told me we were meeting at {loc}, @b.",
    "@b, the fog is worse than yesterday.",
    "Where is everyone, @b?",
    "Grab me a Kappa Cola on your way back, @b.",
]
REPLIES = [
    "Not a minute. The harbor never goes quiet.",
    "Barely. The coffee went cold again.",
    "I counted gulls instead of sleeping.",
    "Ask me after another cup.",
    "They said noon. They always say noon.",
    "It held through the night, mostly.",
    "Somebody has to keep the lights on.",
]
CLOSERS = [
    "Then let's get moving.",
    "We sort it out by morning.",
    "Keep your head down out there.",
    "I will find you at the dock.",
    "Fine. But I am not carrying the crates.",
    "Good. Stay close.",
]
FLASH = [
    "You always worried too much, @b.",
    "Somebody has to worry.",
    "Then worry quietly. The boats are listening.",
]
EST_PAIR = [
    "@a and @b wait at {loc}.",
    "@a and @b argue quietly at {loc}.",
    "@a and @b share a thermos at {loc}.",
    "@a and @b check their watches at {loc}.",
]
EST_THREE = "@a, @b and @c crowd into {loc}."
EST_ONE = "@a sits alone at {loc}, a stack of old papers on the table."
KEEP_QUIET = ["Then we keep quiet.", "Not a word to anyone.", "Understood."]
REFER = [
    "We cannot let anyone find out. [[{phrase}]].",
    "Remember what we know. [[{phrase}]].",
    "It changes everything. [[{phrase}]].",
]


class Builder:
    def __init__(self, seed: int):
        self.rng = random.Random(f"synthetic/{seed}")
        rng = self.rng
        cast = [c for c in CAST if c[0] == "ada"] + rng.sample(
            [c for c in CAST if c[0] != "ada"], 7
        )
        rng.shuffle(cast)
        i = next(k for k, c in enumerate(cast) if c[0] == "ada")
        if i >= 6:  # the informant is not a casualty
            cast[i], cast[0] = cast[0], cast[i]
        self.ents: dict[str, Entity] = {}
        for cid, first, last, nick, desc, gender in cast:
            self.ents[cid] = Entity(
                id=cid,
                kind="character",
                name=f"{first} {last}",
                aliases=[(nick, "nickname"), (desc, "description")],
                attrs={"gender": gender},
            )
        self.chars = [c[0] for c in cast]
        self.main, self.casualties = self.chars[:6], self.chars[6:]
        for name, kind in rng.sample(LOCS, 9):
            lid = "loc_" + re.sub("[^a-z]+", "_", name.lower()).strip("_")
            self.ents[lid] = Entity(id=lid, kind="location", name=name, attrs={"setting": kind})
        self.locs = [e for e in self.ents.values() if e.kind == "location"]
        self.props = []
        for pid, name, thing in rng.sample(PROPS, 6):
            self.ents["prop_" + pid] = Entity(
                id="prop_" + pid, kind="prop", name=name, attrs={"thing": thing}
            )
            self.props.append("prop_" + pid)
        for eid, kind, name in (
            ("brand_kappa_cola", "brand", "Kappa Cola"),
            ("brand_brightwave", "brand", "Brightwave Energy"),
            ("org_greywater", "org", "Greywater Holdings"),
            ("org_harbor_pd", "org", "Harbor City PD"),
        ):
            self.ents[eid] = Entity(id=eid, kind=kind, name=name)
        self.dead: set[str] = set()
        self.day, self.tod = 1, 1
        self.scenes: list[tuple[str, Scene]] = []

    # -- text -----------------------------------------------------------------------------

    def _fill(self, tpl: str, who: dict[str, str], first: bool) -> tuple[str, list[Mention]]:
        ms: list[Mention] = []

        def sub(m: re.Match[str]) -> str:
            e = self.ents[who[m[1]]]
            how = m[2] or "first"
            if how == "any":
                how = self.rng.choice(["first", "nick", "desc"])
            if how == "desc" and first and m.start() == 0:
                how = "nick"
            first_name = e.name.split()[0]
            surface, kind = {
                "first": (first_name, "name"),
                "full": (e.name, "name"),
                "nick": (e.aliases[0][0], "nickname"),
                "desc": (e.aliases[1][0], "description"),
            }[how]
            ms.append(Mention(surface=surface, entity=e.id, kind=kind))
            return surface

        return re.sub(r"@([a-z])(?:\.(full|nick|desc|any))?", sub, tpl), ms

    def _line(
        self,
        kind: str,
        tpl: str,
        who: dict[str, str],
        speaker: str | None = None,
        facts: Sequence[tuple[str, str, str | None, dict[str, Any] | None]] = (),
    ) -> Line:
        """`facts`: (predicate, subject, object, value); each is quoted with the [[...]] span."""
        pre, _, rest = tpl.partition("[[")
        quote_tpl, _, post = rest.partition("]]")
        parts, mentions = [], []
        for i, seg in enumerate((pre, quote_tpl, post)):
            text, ms = self._fill(seg, who, first=i == 0 or (i == 1 and not pre))
            parts.append(text)
            mentions += ms
        text = "".join(parts)
        quote = parts[1] if "[[" in tpl else text
        return Line(
            kind=kind,
            text=text,
            speaker=speaker,
            facts=[
                Fact(predicate=p, subject=s, quote=quote, object=o, value=v) for p, s, o, v in facts
            ],
            mentions=mentions,
        )

    def est(self, cast: list[str], loc: str, prefix: str = "") -> Line:
        who = {k: c for k, c in zip("abc", cast, strict=False)}
        name = self.ents[loc].name
        if len(cast) == 1:
            tpl = EST_ONE
        elif len(cast) == 2:
            tpl = self.rng.choice(EST_PAIR)
        else:
            tpl = EST_THREE
        tpl = (prefix + " " if prefix else "") + tpl.replace("{loc}", name)
        facts = [("present_at", c, loc, None) for c in cast]
        return self._line("action", tpl, who, facts=facts)

    def say(self, speaker: str, tpl: str, who: dict[str, str], facts: Any = (), **fmt: str) -> Line:
        return self._line("dialogue", tpl.format(**fmt) if fmt else tpl, who, speaker, facts)

    def act(self, tpl: str, who: dict[str, str], facts: Any = (), **fmt: str) -> Line:
        return self._line("action", tpl.format(**fmt) if fmt else tpl, who, None, facts)

    # -- scenes ---------------------------------------------------------------------------

    def alive(self, exclude: set[str] = frozenset()) -> list[str]:  # type: ignore[assignment]
        return [c for c in self.chars if c not in self.dead and c not in exclude]

    def loc(self) -> str:
        return self.rng.choice(self.locs).id

    def heading(self, loc: str, tod: str, suffix: str = "") -> str:
        e = self.ents[loc]
        return f"{e.attrs['setting']}. {e.name.upper()} - {tod}{suffix}"

    def chat(self, cast: list[str], loc: str, n_lines: int = 3) -> list[Line]:
        a, b = cast[0], cast[1]
        who = {"a": a, "b": b, "c": cast[-1]}
        opener = self.rng.choice(OPENERS)
        lines = [self.est(cast, loc), self.say(a, opener, who, loc=self.ents[loc].name)]
        mention = "Kappa Cola" in opener
        if mention:
            lines[-1].mentions.append(
                Mention(surface="Kappa Cola", entity="brand_kappa_cola", kind="name")
            )
        lines.append(self.say(b, self.rng.choice(REPLIES), who))
        if n_lines > 3:
            lines.append(self.say(a, self.rng.choice(CLOSERS), who))
        return lines

    def add(self, ep: str, sc: Scene) -> None:
        self.scenes.append((ep, sc))


def build(seed: int = 1) -> Show:
    b = Builder(seed)
    rng = b.rng
    slots: list[tuple[str, dict[str, Any]] | None] = [None] * N

    def free(lo: int, hi: int) -> list[int]:
        return [i for i in range(max(lo, 0), min(hi, N)) if slots[i] is None]

    def put(kind: str, lo: int, hi: int, **kw: Any) -> int:
        i = rng.choice(free(lo, hi))
        slots[i] = (kind, kw)
        return i

    def put_after(kind: str, lo: int, hi: int, **kw: Any) -> int:
        return put(kind, lo + 1, hi, **kw)

    # intercut pairs: one per episode, in different places
    for e in range(len(EPISODES)):
        lo = e * SCENES_PER_EP + 3
        i = rng.choice([i for i in range(lo, lo + 19) if slots[i] is None and slots[i + 1] is None])
        slots[i], slots[i + 1] = ("same_a", {}), ("same_b", {})
    # deaths (episodes 3 and 5) and flashbacks that show the dead afterwards
    deaths = [
        put("death", 50, 75, who=b.casualties[0]),
        put("death", 100, 125, who=b.casualties[1]),
    ]
    put("flashback", max(deaths[0] + 1, 100), N, who=b.casualties[0])
    put("flashback", max(deaths[1] + 1, 125), N, who=b.casualties[1])
    # secrets: discovered, confided, referred to twice; never by a casualty
    subjects = ["ada", *rng.sample([c for c in b.main if c != "ada"], 3)]
    secret_ids = []
    fire_loc = rng.choice(b.locs).name
    for s, subject in enumerate(subjects, 1):
        x, y = rng.sample([c for c in b.main if c != subject], 2)
        sid = f"secret_{s}"
        secret_ids.append(sid)
        d = put("discover", 0, 70, who=x, sid=sid, subject=subject)
        c, r1, r2 = sorted(rng.sample(free(d + 1, N), 3))
        slots[c] = ("confide", dict(who=x, whom=y, sid=sid, subject=subject))
        slots[r1] = ("refer", dict(who=x, whom=y, sid=sid, subject=subject, n=0))
        slots[r2] = ("refer", dict(who=y, whom=x, sid=sid, subject=subject, n=1))
    # props: set up (3 with a payoff), obtained, used twice, destroyed (the other 3)
    for p, prop in enumerate(b.props):
        holder = rng.choice(b.main)
        o = put("obtain", 5, 100, who=holder, prop=prop)
        u1, u2 = sorted(rng.sample(free(o + 1, 125), 2))
        slots[u1] = ("use", dict(who=holder, prop=prop))
        slots[u2] = ("use", dict(who=holder, prop=prop, payoff=False))
        if p < 3 and free(0, o):
            put("setup", 0, o, who=holder, prop=prop)
            slots[u2][1]["payoff"] = True  # type: ignore[index]
        else:
            put_after("destroy", u2, N, who=holder, prop=prop)

    last_regular = (1, 1)  # (day, tod index) of the previous non-flashback, non-same-time scene
    prev_cast: list[str] = []
    ep_scenes: dict[str, list[Scene]] = {ep: [] for ep in EPISODES}
    pending_same: list[str] = []
    fb_days = 0
    for idx in range(N):
        ep, no = EPISODES[idx // SCENES_PER_EP], str(idx % SCENES_PER_EP + 1)
        kind, kw = slots[idx] or ("chat", {})
        if kind in ("same_b",):
            day, tod = last_regular
        elif kind == "flashback":
            fb_days += 1
            day, tod = -30 * fb_days, 1
        else:
            day, tod = b.day, b.tod
            if idx and rng.random() < 0.4:
                tod += 1
                if tod == len(TODS):
                    tod, day = 0, day + 1
                b.day, b.tod = day, tod
        tod_text = "NEXT MORNING" if tod == 0 and kind != "flashback" else TODS[tod]
        marker = {"same_b": "same_time", "flashback": "flashback"}.get(kind)
        suffix = {"same_b": " (SAME TIME)", "flashback": " (FLASHBACK)"}.get(kind, "")
        alive = b.alive()
        lines: list[Line]
        loc = b.loc()
        if kind == "chat" or kind == "same_a" or kind == "same_b":
            pool = b.alive(set(prev_cast) if kind == "same_b" else set())
            cast = rng.sample(pool, 3 if rng.random() < 0.2 else 2)
            if kind == "same_a":
                prev_cast = cast
            if kind == "same_b":
                while loc == pending_same[0]:
                    loc = b.loc()
            if kind == "same_a":
                pending_same = [loc]
            lines = b.chat(cast, loc, rng.choice([3, 4]))
        elif kind == "death":
            who, other = kw["who"], rng.choice([c for c in b.main])
            w = {"a": who, "b": other}
            lines = [
                b.est([who, other], loc),
                b.say(who, "Tell no one what you saw tonight, @b.", w),
                b.act(
                    "[[@a collapses and does not get up]].",
                    w,
                    [("state", who, None, {"state": "dead"})],
                ),
                b.say(other, "@a? Stay with me. @a!", w),
            ]
            b.dead.add(who)
            cast = [who, other]
        elif kind == "flashback":
            who = kw["who"]
            other = rng.choice(b.main)
            w = {"a": who, "b": other}
            lines = [b.est([who, other], loc, "Years earlier."), b.say(who, FLASH[0], w)]
            lines += [b.say(other, FLASH[1], w), b.say(who, FLASH[2], w)]
            cast = [who, other]
        elif kind in ("discover", "confide", "refer"):
            x, sid, subject = kw["who"], kw["sid"], kw["subject"]
            sidx = secret_ids.index(sid)
            ph_tpl = SECRETS[sidx].replace("{loc}", fire_loc)
            w = {"s": subject, "a": x, "b": kw.get("whom", x)}
            cast = [x] if kind == "discover" else [x, kw["whom"]]
            lines = [b.est(cast, loc)]
            kn = ("learns", x, sid, None)
            ref = ("references", x, sid, None)
            if kind == "discover":
                lines.append(b.say(x, f"So it is true. [[{ph_tpl}]]. All this time.", w, [kn]))
            elif kind == "confide":
                y = kw["whom"]
                lines.append(b.say(x, f"I need you to know something. [[{ph_tpl}]].", w, [ref]))
                lines.append(
                    b.say(y, "[[I never suspected]]. Not once.", w, [("learns", y, sid, None)])
                )
            else:
                lines.append(b.say(x, REFER[kw["n"] % len(REFER)].format(phrase=ph_tpl), w, [ref]))
                lines.append(b.say(kw["whom"], rng.choice(KEEP_QUIET), w))
        else:  # props
            x, prop = kw["who"], kw["prop"]
            pe = b.ents[prop]
            y = rng.choice([c for c in alive if c != x])
            w = {"a": x, "b": y}
            cast = [x] if kind == "setup" else [x, y]
            lines = [b.est(cast, loc)]

            def holds(ev: str, x: str = x, prop: str = prop) -> list[Any]:
                return [("holds", x, prop, {"event": ev})]

            if kind == "setup":
                lines.append(
                    b.act(
                        f"[[A {pe.name} sits on a shelf, easy to overlook]].",
                        w,
                        [("setup", prop, None, {"importance": 3})],
                    )
                )
            elif kind == "obtain":
                lines.append(b.act(f"[[@a picks up the {pe.name}]].", w, holds("obtain")))
                lines.append(b.say(y, "Is that what I think it is?", w))
            elif kind == "use" and kw.get("payoff"):
                lines.append(
                    b.act(
                        f"At last, [[@a uses the {pe.name} on the {pe.attrs['thing']}]].",
                        w,
                        holds("use") + [("payoff", prop, x, None)],
                    )
                )
                lines.append(b.say(y, "It worked. After all this time.", w))
            elif kind == "use":
                lines.append(b.act(f"[[@a checks the {pe.name}]] again.", w, holds("use")))
                lines.append(b.say(y, "Put it away before someone sees.", w))
            else:  # destroy
                lines.append(
                    b.act(
                        f"[[The {pe.name} slips from @a's hand and shatters]].",
                        w,
                        [("state", prop, None, {"state": "destroyed"})],
                    )
                )
                lines.append(b.say(y, "Well. That is that.", w))
        sc = Scene(
            no=no,
            heading=b.heading(loc, tod_text, suffix),
            location=loc,
            marker=marker,
            story_day=day,
            story_seq=0,
            lines=merge_actions(lines),
        )
        if kind not in ("flashback", "same_b"):
            last_regular = (day, tod)
        ep_scenes[ep].append(sc)
        prev_cast = prev_cast if kind == "same_a" else []
    _story_seq(ep_scenes)
    # secrets: entities + identity secret
    for sid, subject in zip(secret_ids, subjects, strict=True):
        tpl = SECRETS[secret_ids.index(sid)]
        desc = tpl.replace("@s.full", b.ents[subject].name).replace("{loc}", fire_loc)
        b.ents[sid] = Entity(
            id=sid, kind="secret", name=sid, attrs={"description": desc, "subject": subject}
        )
    show = Show(
        show="synthetic-show",
        title="Harbor Lights",
        seed=seed,
        entities=list(b.ents.values()),
        episodes=ep_scenes,
    )
    _identity(show)
    return show


def _story_seq(ep_scenes: dict[str, list[Scene]]) -> None:
    """Chronological rank: flashbacks first (by their story day), then screen order; a SAME TIME
    scene shares the rank of the scene before it."""
    flat = [sc for scenes in ep_scenes.values() for sc in scenes]
    flashes = sorted((s for s in flat if s.marker == "flashback"), key=lambda s: s.story_day)
    for rank, s in enumerate(flashes, 1):
        s.story_seq = rank
    seq = len(flashes)
    for s in flat:
        if s.marker == "flashback":
            continue
        if s.marker != "same_time":
            seq += 1
        s.story_seq = seq


def _identity(show: Show) -> None:
    """The informant's identity is hidden until the episode where the viewer learns it."""
    for ep, scenes in show.episodes.items():
        for sc in scenes:
            for ln in sc.lines:
                for f in ln.facts:
                    if f.predicate == "learns" and f.object == "secret_1":
                        show.entity("ada").attrs["identity_hidden_until"] = ep
                        return
