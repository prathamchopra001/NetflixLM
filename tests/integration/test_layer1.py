"""Script Critic Layer 1 (2.3): the four SQL rules on fixture facts inserted directly (R15).

Every rule has a positive and a negative fixture; flags must pass `verify` with resolved evidence,
and retracting the fact a flag stands on makes the SQL re-check drop it.
"""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest
from psycopg.types.range import Range
from sqlalchemy import Connection, Engine, insert, select, update

from nip import pipeline
from nip.agents import script_critic as script_critic_pkg
from nip.agents.base import run_check
from nip.agents.script_critic import CHECKS, DeadActs, KnowledgeOrder, PropProvenance, TwoPlaces
from nip.contracts import Flag, ProducedBy
from nip.contracts.flag import CheckId, EvidenceKind, EvidenceRole
from nip.pipeline import require_stable_refs
from nip.store import schema
from nip.store.ingest import ingest_files
from nip.store.load import load_timeline
from nip.verification.verify import verify

pytestmark = pytest.mark.integration

PB = ProducedBy(model_variant=None, plan_id="plan_t")
SHA = "0" * 64
NL = chr(10)


class World:
    """A show built row by row: scenes with lines, entities, and facts with their source events."""

    def __init__(self, conn: Connection):
        self.c = conn
        self.show_id = conn.execute(
            insert(schema.show).values(slug="demo", title="Demo").returning(schema.show.c.id)
        ).scalar_one()
        self.ep: dict[str, int] = {}
        self.scene: dict[tuple[str, str], int] = {}
        self.line: dict[tuple[str, str, int], int] = {}
        self.ent: dict[str, int] = {}

    @classmethod
    def from_store(cls, conn: Connection) -> "World":
        """The World of an ingested show: scene and line ids read back from the rows."""
        w = cls.__new__(cls)
        w.c = conn
        w.show_id = conn.execute(select(schema.show.c.id)).scalar_one()
        w.ep = {r.ref: r.id for r in conn.execute(select(schema.episode))}
        by_id = {v: k for k, v in w.ep.items()}
        w.scene, w.line, w.ent = {}, {}, {}
        for sc in conn.execute(select(schema.scene)):
            w.scene[by_id[sc.episode_id], sc.script_scene_no] = sc.id
        sc_key = {v: k for k, v in w.scene.items()}
        for ln in conn.execute(select(schema.script_line)):
            ep, no = sc_key[ln.scene_id]
            w.line[ep, no, ln.seq] = ln.id
        return w

    def entity(self, key: str, kind: str, name: str) -> None:
        self.ent[key] = self.c.execute(
            insert(schema.entity)
            .values(show_id=self.show_id, kind=kind, canonical_name=name, origin="bible")
            .returning(schema.entity.c.id)
        ).scalar_one()

    def add_scene(
        self,
        ep: str,
        no: str,
        story_seq: int | None,
        lines: Iterable[str | tuple[str, str]] = ("Line one.", "Line two."),
        markers: tuple[str, ...] = (),
        inferred: bool = False,
    ) -> None:
        if ep not in self.ep:
            n = int(ep[-2:])
            self.ep[ep] = self.c.execute(
                insert(schema.episode)
                .values(show_id=self.show_id, season=1, number=n, episode_seq=1000 + n, ref=ep)
                .returning(schema.episode.c.id)
            ).scalar_one()
        sid = self.c.execute(
            insert(schema.scene)
            .values(
                episode_id=self.ep[ep],
                script_scene_no=no,
                heading=f"INT. PLACE {no} - DAY",
                markers=list(markers),
                story_seq=story_seq,
                story_inferred=inferred,
                text_hash=SHA,
            )
            .returning(schema.scene.c.id)
        ).scalar_one()
        self.scene[ep, no] = sid
        for seq, ln in enumerate(lines, 1):
            text, speaker = (ln, None) if isinstance(ln, str) else ln
            self.line[ep, no, seq] = self.c.execute(
                insert(schema.script_line)
                .values(
                    scene_id=sid,
                    seq=seq,
                    kind="action" if speaker is None else "dialogue",
                    text=text,
                    speaker_entity_id=self.ent[speaker] if speaker else None,
                )
                .returning(schema.script_line.c.id)
            ).scalar_one()

    def fact(
        self,
        predicate: str,
        subject: str,
        at: tuple[str, str, int],
        story: tuple[int, int | None],
        obj: str | None = None,
        value: dict[str, Any] | None = None,
        quote: str = "Line",
        conf: float = 0.9,
        more: Iterable[tuple[tuple[str, str, int], str, dict[str, Any] | None]] = (),
    ) -> int:
        """A fact whose source events are on line `at` = (episode, scene no, line seq) and on
        each of `more` = (line, quote, event value): a consolidated fact merges its events."""
        ev_ids = [
            self.c.execute(
                insert(schema.fact_event)
                .values(
                    scene_id=self.scene[where[0], where[1]],
                    line_id=self.line[where],
                    predicate=predicate,
                    subject_id=self.ent[subject],
                    object_id=self.ent[obj] if obj else None,
                    value=val,
                    quote=q,
                    confidence=conf,
                )
                .returning(schema.fact_event.c.id)
            ).scalar_one()
            for where, q, val in [(at, quote, value), *more]
        ]
        return self.c.execute(
            insert(schema.fact)
            .values(
                show_id=self.show_id,
                predicate=predicate,
                subject_id=self.ent[subject],
                object_id=self.ent[obj] if obj else None,
                value=value,
                screen=Range(0, 1),
                story=Range(story[0], story[1]),
                source_event_ids=ev_ids,
                confidence=conf,
            )
            .returning(schema.fact.c.id)
        ).scalar_one()

    def retract(self, fact_id: int) -> None:
        self.c.execute(
            update(schema.fact).where(schema.fact.c.id == fact_id).values(status="retracted")
        )


@pytest.fixture
def w(pg: Engine) -> Iterable[World]:
    with pg.begin() as conn:
        world = World(conn)
        for key, kind, name in [
            ("maya", "character", "Maya Reyes"),
            ("leo", "character", "Leo Park"),
            ("ada", "character", "Ada Kovac"),
            ("dock", "location", "Pier Nine"),
            ("diner", "location", "Tidewater Diner"),
            ("secret", "secret", "Ada is the informant"),
            ("key", "prop", "rusted key"),
        ]:
            world.entity(key, kind, name)
        yield world


def flags(w: World, rule: type, ep: str, show: str = "demo") -> tuple[list[Flag], Any]:
    """(flags the rule raises for `ep`, the episode's timeline)."""
    tl = load_timeline(w.c, show, ep)
    return run_check(rule(w.c, show), tl, "run_1", PB), tl


def claim_refs(fl: list[Flag]) -> list[str]:
    return [next(e.ref for e in f.evidence if e.role is EvidenceRole.CLAIM) for f in fl]


def check_verified(fl: list[Flag], tl: Any, rule: Any) -> list[Flag]:
    stable, dropped = require_stable_refs(fl)
    kept, dropped2 = verify(stable, tl, [rule])
    assert not dropped and not dropped2
    assert all(f.verification.evidence == "pass" == f.verification.rule_recheck for f in kept)
    return kept


# --- plot.knowledge_order ---------------------------------------------------------------------
def order_world(w: World, learn_seq: int | None, learn_ep: str = "S01E02") -> dict[str, int]:
    w.add_scene("S01E01", "1", 1)
    w.add_scene("S01E01", "2", 2, ["Maya whispers.", "Ada is the informant, Maya says."])
    w.add_scene("S01E02", "1", 5, ["Leo hears it.", "Leo learns it all."])
    ids = {
        "ref": w.fact(
            "references", "maya", ("S01E01", "2", 2), (2, 3), "secret", quote="Ada is the informant"
        )  # fmt: skip
    }
    if learn_seq is not None:
        scene = "1" if learn_ep == "S01E02" else "2"
        line = 2 if learn_ep == "S01E02" else 1
        ids["learn"] = w.fact("learns", "maya", (learn_ep, scene, line), (learn_seq, None),
                              "secret", quote="Leo learns")  # fmt: skip
    return ids


def test_knowledge_order_reference_before_learning_is_flagged(w: World) -> None:
    ids = order_world(w, 5)
    fl, tl = flags(w, KnowledgeOrder, "S01E01")
    assert claim_refs(fl) == ["S01E01/line/2.2"]
    f = fl[0]
    assert (f.check, f.severity, f.episode) == (CheckId.PLOT_KNOWLEDGE_ORDER, 3, "S01E01")
    claim, setup = f.evidence
    assert (claim.kind, claim.quote) == (EvidenceKind.SCRIPT_LINE, "Ada is the informant")
    # the later learning, in another episode, is cited only as a fact ref, with its quote
    assert (setup.ref, setup.role, setup.quote) == (
        f"fact/{ids['learn']}", EvidenceRole.SETUP, "Leo learns")  # fmt: skip
    assert "S01E02/sc/1" in f.explanation
    assert fl and flags(w, KnowledgeOrder, "S01E02")[0] == []  # claims live in their own episode
    check_verified(fl, tl, KnowledgeOrder(w.c, "demo"))


def test_knowledge_order_never_learned_is_flagged_without_setup(w: World) -> None:
    order_world(w, None)
    (f,), _ = flags(w, KnowledgeOrder, "S01E01")
    assert [e.role for e in f.evidence] == [EvidenceRole.CLAIM]
    assert "No scene shows" in f.explanation


@pytest.mark.parametrize("learn_seq", [1, 2])  # earlier, and the same story moment
def test_knowledge_order_learned_earlier_or_same_moment_is_clean(w: World, learn_seq: int) -> None:
    order_world(w, learn_seq, learn_ep="S01E01")
    assert flags(w, KnowledgeOrder, "S01E01")[0] == []


def test_knowledge_order_story_order_not_screen_order(w: World) -> None:
    """Screen order says the reference (sc 1) comes first, but the learning is earlier in story."""
    w.add_scene("S01E01", "1", 9, ["Maya mentions it.", "Ada is the informant."])
    w.add_scene("S01E01", "2", 3, ["Maya finds out.", "Learns."])  # a flashback-like earlier seq
    w.fact("references", "maya", ("S01E01", "1", 2), (9, 10), "secret", quote="Ada is")
    w.fact("learns", "maya", ("S01E01", "2", 2), (3, None), "secret", quote="Learns")
    assert flags(w, KnowledgeOrder, "S01E01")[0] == []


# --- plot.dead_acts ---------------------------------------------------------------------------
def dead_world(w: World, later_marker: tuple[str, ...] = ()) -> dict[str, int]:
    w.add_scene("S01E01", "1", 1, ["Ada falls.", "Ada dies."])
    w.add_scene("S01E01", "2", 2, ["Maya grieves.", "Ada is at the door."])
    w.add_scene("S01E02", "1", 4, ["Ada speaks.", ("Hello again.", "ada")], markers=later_marker)
    return {
        "dead": w.fact("state", "ada", ("S01E01", "1", 2), (1, None), value={"state": "dead"},
                       quote="Ada dies"),
        "here": w.fact("present_at", "ada", ("S01E02", "1", 1), (4, 5), "dock", quote="Ada speaks"),
    }  # fmt: skip


def test_dead_acts_present_after_death_is_flagged(w: World) -> None:
    ids = dead_world(w)
    fl, tl = flags(w, DeadActs, "S01E02")
    # the present_at line, and the spoken line (speaker_entity_id) of the same scene
    assert claim_refs(fl) == ["S01E02/line/1.1", "S01E02/line/1.2"]
    f = fl[0]
    assert (f.severity, f.evidence[1].ref, f.evidence[1].role) == (
        4, f"fact/{ids['dead']}", EvidenceRole.CONTRADICTION)  # fmt: skip
    assert "S01E01/sc/1" in f.explanation
    assert flags(w, DeadActs, "S01E01")[0] == []  # the death scene itself is not "after"
    check_verified(fl, tl, DeadActs(w.c, "demo"))


@pytest.mark.parametrize("marker", ["flashback", "dream", "vision"])
def test_dead_acts_flashback_dream_vision_scenes_are_exempt(w: World, marker: str) -> None:
    dead_world(w, (marker,))
    assert flags(w, DeadActs, "S01E02")[0] == []


def test_dead_acts_earlier_story_position_is_clean(w: World) -> None:
    """A scene shown after the death on screen but earlier in story order (unmarked flashback)."""
    w.add_scene("S01E01", "1", 5, ["Ada falls.", "Ada dies."])
    w.add_scene("S01E01", "2", 2, ["Ada speaks.", "Ada waves."])
    w.fact("state", "ada", ("S01E01", "1", 2), (5, None), value={"state": "dead"}, quote="Ada dies")
    w.fact("present_at", "ada", ("S01E01", "2", 1), (2, 3), "dock", quote="Ada speaks")
    assert flags(w, DeadActs, "S01E01")[0] == []


# --- plot.two_places --------------------------------------------------------------------------
def places_world(w: World, b_marker: tuple[str, ...] = ()) -> dict[str, int]:
    w.add_scene("S01E01", "1", 3, ["Maya at the dock.", "Maya waits."])
    w.add_scene("S01E01", "2", 3, ["Maya at the diner.", "Maya eats."], markers=b_marker)
    return {
        "a": w.fact("present_at", "maya", ("S01E01", "1", 1), (3, 4), "dock", quote="Maya at"),
        "b": w.fact("present_at", "maya", ("S01E01", "2", 1), (3, 4), "diner", quote="Maya at"),
    }


def test_two_places_same_story_moment_is_flagged_once_on_the_later_scene(w: World) -> None:
    ids = places_world(w)
    fl, tl = flags(w, TwoPlaces, "S01E01")
    assert claim_refs(fl) == ["S01E01/line/2.1"]
    f = fl[0]
    assert (f.severity, f.evidence[1].ref) == (3, f"fact/{ids['a']}")
    assert "Pier Nine" in f.explanation and "Tidewater Diner" in f.explanation
    check_verified(fl, tl, TwoPlaces(w.c, "demo"))


def test_two_places_cross_episode_pair_is_flagged_in_the_later_episode_only(w: World) -> None:
    w.add_scene("S01E01", "1", 3)
    w.add_scene("S01E02", "1", 3)
    ids = {
        "a": w.fact("present_at", "maya", ("S01E01", "1", 1), (3, 4), "dock"),
        "b": w.fact("present_at", "maya", ("S01E02", "1", 1), (3, 4), "diner"),
    }
    assert flags(w, TwoPlaces, "S01E01")[0] == []
    (f,), tl = flags(w, TwoPlaces, "S01E02")
    assert f.evidence[1].ref == f"fact/{ids['a']}"  # the other episode's fact: a fact ref only
    check_verified([f], tl, TwoPlaces(w.c, "demo"))


def test_two_places_clean_cases(w: World) -> None:
    # different characters intercut at one seq; same character at the same place; distinct seqs
    w.add_scene("S01E01", "1", 3)
    w.add_scene("S01E01", "2", 3)
    w.add_scene("S01E01", "3", 4)
    w.fact("present_at", "maya", ("S01E01", "1", 1), (3, 4), "dock")
    w.fact("present_at", "leo", ("S01E01", "2", 1), (3, 4), "diner")
    w.fact("present_at", "leo", ("S01E01", "3", 1), (4, 5), "dock")  # next moment: just walked
    assert flags(w, TwoPlaces, "S01E01")[0] == []


@pytest.mark.parametrize("marker", ["flashback", "dream", "vision"])
def test_two_places_marked_scene_is_exempt(w: World, marker: str) -> None:
    places_world(w, (marker,))
    assert flags(w, TwoPlaces, "S01E01")[0] == []


# --- plot.prop_provenance ---------------------------------------------------------------------
USE = {"event": "use"}
OBTAIN = {"event": "obtain"}
LINE = {1: ("S01E01", "1", 2), 2: ("S01E01", "2", 2), 3: ("S01E01", "3", 2)}  # story seq -> line


def prop_world(w: World, use_seq: int, obtain_seq: int | None, gone_seq: int | None = None) -> dict:
    """Leo uses the key at `use_seq`; Maya obtains it at `obtain_seq`; it is destroyed at
    `gone_seq` (the prop's own state fact). Scene n is at story position n."""
    w.add_scene("S01E01", "1", 1, ["Maya picks it up.", "Maya pockets the key."])
    w.add_scene("S01E01", "2", 2, ["Leo is bored.", "Leo checks the key again."])
    w.add_scene("S01E01", "3", 3, ["The lock.", "Maya uses the key."])
    ids: dict[str, int] = {}
    if obtain_seq is not None:
        ids["obtain"] = w.fact("holds", "maya", LINE[obtain_seq], (obtain_seq, None), "key", OBTAIN,
                               "key")  # fmt: skip
    if gone_seq is not None:
        ids["gone"] = w.fact("state", "key", ("S01E01", str(gone_seq), 1), (gone_seq, None),
                             value={"state": "destroyed"}, quote="The")  # fmt: skip
    ids["use"] = w.fact("holds", "leo", LINE[use_seq], (use_seq, use_seq + 1), "key", USE, "key")
    return ids


def test_prop_used_before_obtained_is_flagged(w: World) -> None:
    ids = prop_world(w, use_seq=1, obtain_seq=3)
    fl, tl = flags(w, PropProvenance, "S01E01")
    assert claim_refs(fl) == ["S01E01/line/1.2"]
    f = fl[0]
    assert (f.severity, f.evidence[1].ref, f.evidence[1].role) == (
        2, f"fact/{ids['obtain']}", EvidenceRole.SETUP)  # fmt: skip
    check_verified(fl, tl, PropProvenance(w.c, "demo"))


def test_prop_use_merged_into_the_holders_fact_is_still_found(w: World) -> None:
    """Consolidation merges one character's holds events of a prop into one interval that starts
    at its first event: the use at 1 starts the fact, the pickup at 3 is only its second event."""
    w.add_scene("S01E01", "1", 1, ["Maya picks it up.", "Maya checks the key."])
    w.add_scene("S01E01", "3", 3, ["The lock.", "Maya pockets the key."])
    w.fact("holds", "maya", ("S01E01", "1", 2), (1, None), "key", USE, "the key",
           more=[(("S01E01", "3", 2), "the key", OBTAIN)])  # fmt: skip
    fl, _ = flags(w, PropProvenance, "S01E01")
    assert claim_refs(fl) == ["S01E01/line/1.2"]
    # the pickup is the second event of the same fact: cited as setup with its own quote
    assert [(e.role, e.quote) for e in fl[0].evidence] == [
        (EvidenceRole.CLAIM, "the key"),
        (EvidenceRole.SETUP, "the key"),
    ]


def test_prop_never_obtained_is_flagged_without_setup(w: World) -> None:
    prop_world(w, use_seq=2, obtain_seq=None)
    (f,), _ = flags(w, PropProvenance, "S01E01")
    assert len(f.evidence) == 1 and "No scene shows anyone obtaining" in f.explanation


def test_prop_used_after_destroyed_is_flagged(w: World) -> None:
    ids = prop_world(w, use_seq=3, obtain_seq=1, gone_seq=2)
    fl, tl = flags(w, PropProvenance, "S01E01")
    assert claim_refs(fl) == ["S01E01/line/3.2"]
    assert (fl[0].evidence[1].ref, fl[0].evidence[1].role) == (
        f"fact/{ids['gone']}", EvidenceRole.CONTRADICTION)  # fmt: skip
    check_verified(fl, tl, PropProvenance(w.c, "demo"))


@pytest.mark.parametrize("use_seq,obtain_seq", [(2, 1), (3, 1), (1, 1)])  # obtained earlier / now
def test_prop_obtained_before_use_is_clean(w: World, use_seq: int, obtain_seq: int) -> None:
    """Leo uses what Maya obtained: the rule asks that anyone held it first."""
    prop_world(w, use_seq, obtain_seq)
    assert flags(w, PropProvenance, "S01E01")[0] == []


def test_prop_picked_up_again_after_loss_is_clean(w: World) -> None:
    w.add_scene("S01E01", "1", 1, ["Maya picks it up.", "Maya pockets the key."])
    w.add_scene("S01E01", "2", 2, ["The key breaks.", "Gone."])
    w.add_scene("S01E01", "3", 3, ["The lock.", "Leo uses the key."])
    w.add_scene("S01E01", "4", 3, ["Maya digs.", "Maya takes the key."])
    w.fact("holds", "maya", ("S01E01", "1", 2), (1, None), "key", OBTAIN, "the key",
           more=[(("S01E01", "4", 2), "the key", OBTAIN)])  # fmt: skip
    w.fact("state", "key", ("S01E01", "2", 1), (2, None), value={"state": "destroyed"})
    use = w.fact("holds", "leo", ("S01E01", "3", 2), (3, 4), "key", USE, "the key")
    assert flags(w, PropProvenance, "S01E01")[0] == []
    # without the pickup at 3 the use is after the loss
    w.retract(use + 0)  # keep the fixture honest: retracting the use removes every finding
    assert flags(w, PropProvenance, "S01E01")[0] == []


# --- confidence, retraction, re-check ---------------------------------------------------------
def test_inferred_story_position_reduces_confidence(
    w: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NIP_INFERRED_STORY_CONFIDENCE_FACTOR", "0.5")
    w.add_scene("S01E01", "1", 3, ["Maya at the dock.", "Maya waits."], inferred=True)
    w.add_scene("S01E01", "2", 3, ["Maya at the diner.", "Maya eats."])
    w.fact("present_at", "maya", ("S01E01", "1", 1), (3, 4), "dock", conf=0.9)
    w.fact("present_at", "maya", ("S01E01", "2", 1), (3, 4), "diner", conf=0.8)
    (f,), _ = flags(w, TwoPlaces, "S01E01")
    assert f.confidence == pytest.approx(0.8 * 0.5)  # min of the cited facts x factor
    assert f.tier == "suppressed"


def test_explicit_story_position_keeps_confidence(w: World) -> None:
    places_world(w)
    (f,), _ = flags(w, TwoPlaces, "S01E01")
    assert f.confidence == pytest.approx(0.9)
    assert f.tier == "must_review"


@pytest.mark.parametrize(
    "rule,build,key",
    [
        (KnowledgeOrder, lambda w: order_world(w, 5), "ref"),
        (DeadActs, lambda w: dead_world(w), "dead"),
        (DeadActs, lambda w: dead_world(w), "here"),
        (TwoPlaces, lambda w: places_world(w), "a"),
        (TwoPlaces, lambda w: places_world(w), "b"),
        (PropProvenance, lambda w: prop_world(w, 1, 3), "use"),
        (PropProvenance, lambda w: prop_world(w, 3, 1, 2), "gone"),
    ],
)
def test_retracting_a_fact_makes_the_recheck_drop_the_flag(
    w: World, rule: type, build: Any, key: str
) -> None:
    ids = build(w)
    ep = "S01E02" if rule is DeadActs else "S01E01"
    fl, tl = flags(w, rule, ep)
    assert fl
    flag = fl[0]
    check = rule(w.c, "demo")
    kept, dropped = verify(fl, tl, [check])
    assert len(kept) == len(fl) and not dropped
    # one of the facts the finding stands on is retracted: the stale timeline still resolves the
    # evidence, so only the re-run SQL can notice
    w.retract(ids[key])
    kept, dropped = verify([flag], tl, [check])
    if key == "here":  # the spoken line (speaker) still holds, only the present_at flag goes
        assert flag.evidence[0].ref == "S01E02/line/1.1"
    assert [d[1] for d in dropped] == ["rule re-check no longer reproduces the finding"]
    assert not kept


def test_flags_survive_a_fresh_timeline_only_while_their_facts_are_active(w: World) -> None:
    ids = places_world(w)
    fl, _ = flags(w, TwoPlaces, "S01E01")
    w.retract(ids["a"])
    assert flags(w, TwoPlaces, "S01E01")[0] == []
    fresh = load_timeline(w.c, "demo", "S01E01")
    kept, dropped = verify(fl, fresh, [TwoPlaces(w.c, "demo")])
    assert not kept and dropped  # evidence step (fact/a is gone) or the re-check, whichever first


def test_checks_are_exported_and_active_on_a_script() -> None:
    from nip.agents.base import Input

    assert {c.check for c in CHECKS} == {
        CheckId.PLOT_KNOWLEDGE_ORDER,
        CheckId.PLOT_DEAD_ACTS,
        CheckId.PLOT_TWO_PLACES,
        CheckId.PLOT_PROP_PROVENANCE,
    }
    assert all(c.active({Input.SCRIPT}) and not c.active(set()) for c in CHECKS)


def test_nip_run_raises_and_persists_a_plot_flag(
    pg: Engine, s3: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`run_store` with the Script Critic package: build_checks hands it the run's Connection, the
    flag passes verification, is stored with its stable line ref, and is identical in a re-run."""
    from tests.integration.test_store import stub_plan

    script = tmp_path / "s.fountain"
    script.write_text(
        "INT. DOCK - DAY #1#"
        + NL * 2
        + "Maya waits."
        + NL * 2
        + "EXT. DINER - DAY #2#"
        + NL * 2
        + "Maya eats."
        + NL,
        encoding="utf-8",
    )
    with pg.begin() as conn:
        ingest_files(conn, s3, show="demo", episode="S01E01", files=[(None, script)])
        w = World.from_store(conn)
        for key, kind, name in [("maya", "character", "Maya"), ("dock", "location", "Dock"),
                                ("diner", "location", "Diner")]:  # fmt: skip
            w.entity(key, kind, name)
        conn.execute(update(schema.scene).values(story_seq=1, markers=["intercut"]))
        w.fact("present_at", "maya", ("S01E01", "1", 1), (1, 2), "dock", quote="Maya waits")
        w.fact("present_at", "maya", ("S01E01", "2", 1), (1, 2), "diner", quote="Maya eats")
    monkeypatch.setattr(pipeline, "AGENTS", [script_critic_pkg])
    plan, inv = stub_plan()
    out = [
        pipeline.run_store(pg, s3, show="demo", episodes=["S01E01"], plan=plan, inventory=inv)
        for _ in range(2)
    ]
    ep = out[0]["episodes"]["S01E01"]
    assert (out[0]["agents"], ep["flags_kept"], ep["dropped"]) == (["script_critic"], 1, [])
    assert ep["units"] == {"done": 4}  # one unit per rule
    with pg.connect() as conn:
        rows = conn.execute(
            select(schema.flag.c.check_id, schema.flag.c.fingerprint, schema.flag.c.verification)
            .order_by(schema.flag.c.id)
        ).all()  # fmt: skip
        assert [r.check_id for r in rows] == ["plot.two_places"] * 2
        assert rows[0].fingerprint == rows[1].fingerprint  # fact ids are out of the fingerprint
        assert rows[0].verification["evidence"] == rows[0].verification["rule_recheck"] == "pass"
        ev = conn.execute(
            select(schema.evidence.c.ref, schema.evidence.c.role).where(
                schema.evidence.c.flag_id == 1
            )
        ).all()
    assert [(r.ref, r.role) for r in ev] == [
        ("S01E01/line/2.1", "claim"), ("fact/1", "contradiction")]  # fmt: skip
