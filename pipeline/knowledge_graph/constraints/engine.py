"""Deterministic constraint engine. No LLM involved — pure graph queries."""
from __future__ import annotations

from typing import Any, List, Dict
from neo4j import GraphDatabase


class ConstraintEngine:
    """Runs deterministic graph constraint rules against the KG."""

    def __init__(self, driver) -> None:
        self._driver = driver

    @staticmethod
    def _run_query(tx, query: str, params: dict) -> list[dict]:
        result = tx.run(query, params)
        return [record.data() for record in result]

    def evaluate(self, show_id: str, episode_ref: str) -> list[dict]:
        violations: list[dict] = []
        with self._driver.session() as session:
            violations.extend(session.read_transaction(self._check_loc, show_id, episode_ref))
            violations.extend(session.read_transaction(self._check_dead, show_id, episode_ref))
            violations.extend(session.read_transaction(self._check_prop, show_id, episode_ref))
            violations.extend(session.read_transaction(self._check_secret, show_id, episode_ref))
            violations.extend(session.read_transaction(self._check_rel, show_id, episode_ref))
        return violations

    # -- C-LOC-001: Character at two locations same timecode --
    @classmethod
    def _check_loc(cls, tx, show_id: str, episode_ref: str):
        query = """
        MATCH (c:Character)-[r:AT_LOCATION]->(l:Location)
        WHERE r.episode_ref = $ep
        WITH c, r.timecode AS tc, collect(DISTINCT l) AS locs
        WHERE size(locs) > 1
        RETURN c.name AS character, tc AS timecode, locs AS locations
        """
        records = cls._run_query(tx, query, {"ep": episode_ref})
        return [
            {
                "constraint_id": "C-LOC-001",
                "severity": "critical",
                "description": f"Character {r['character']} at multiple locations at {r['timecode']}",
                "evidence": [
                    {"ref": f"{episode_ref}@{r['timecode']}", "type": "action"},
                ],
                "suggested_fix": "Check script for simultaneous scenes",
            }
            for r in records
        ]

    # -- C-DEAD-001: Dead character performs action --
    @classmethod
    def _check_dead(cls, tx, show_id: str, episode_ref: str):
        query = """
        MATCH (c:Character)-[a:ALIVE_AT {status: 'dead'}]->(e:Event)
        WHERE a.episode_ref = $ep
        WITH c, a.timecode AS death_tc
        MATCH (c)-[r:AT_LOCATION|HOLDS_PROP]->(x)
        WHERE r.timecode > death_tc
        RETURN c.name AS character, death_tc, collect(r.timecode)[..3] AS after_times
        """
        records = cls._run_query(tx, query, {"ep": episode_ref})
        return [
            {
                "constraint_id": "C-DEAD-001",
                "severity": "critical",
                "description": f"Dead character {r['character']} acts after death at {r['death_tc']}",
                "evidence": [
                    {"ref": f"{episode_ref}@{t}", "type": "action"}
                    for t in r.get("after_times", [])
                ],
                "suggested_fix": "Remove post-death actions or adjust death timecode",
            }
            for r in records
        ]

    # -- C-PROP-001: Same prop held by two characters at same time --
    @classmethod
    def _check_prop(cls, tx, show_id: str, episode_ref: str):
        query = """
        MATCH (c1:Character)-[r1:HOLDS_PROP]->(p:Prop)<-[r2:HOLDS_PROP]-(c2:Character)
        WHERE c1 <> c2 AND r1.timecode = r2.timecode AND r1.episode_ref = $ep
        RETURN c1.name AS holder1, c2.name AS holder2, p.name AS prop, r1.timecode AS timecode
        """
        records = cls._run_query(tx, query, {"ep": episode_ref})
        return [
            {
                "constraint_id": "C-PROP-001",
                "severity": "high",
                "description": f"Prop {r['prop']} held by {r['holder1']} and {r['holder2']} at {r['timecode']}",
                "evidence": [
                    {"ref": f"{episode_ref}@{r['timecode']}", "type": "action"},
                ],
                "suggested_fix": "Check prop continuity between scenes",
            }
            for r in records
        ]

    # -- C-SECRET-001: Secret known before reveal --
    @classmethod
    def _check_secret(cls, tx, show_id: str, episode_ref: str):
        query = """
        MATCH (c:Character)-[k:KNOWS_SECRET]->(s:Secret)
        WHERE k.since_tc < s.revealed_tc
        RETURN c.name AS character, s.name AS secret, k.since_tc AS known_since, s.revealed_tc AS revealed_at
        """
        records = cls._run_query(tx, query, {"ep": episode_ref})
        return [
            {
                "constraint_id": "C-SECRET-001",
                "severity": "high",
                "description": f"{r['character']} knows secret '{r['secret']}' before reveal",
                "evidence": [
                    {"ref": f"{episode_ref}@{r['known_since']}", "type": "revelation_event"},
                    {"ref": f"{episode_ref}@{r['revealed_at']}", "type": "revelation_event"},
                ],
                "suggested_fix": "Move revelation earlier or delay character's knowledge",
            }
            for r in records
        ]

    # -- C-REL-001: Immutable biological parent relation contradicted --
    @classmethod
    def _check_rel(cls, tx, show_id: str, episode_ref: str):
        query = """
        MATCH (c1:Character)-[r1:RELATES_TO {relation: 'parent'}]->(c2:Character)
        MATCH (c1)-[r2:RELATES_TO]->(c2)
        WHERE c1 <> c2 AND r2.relation <> 'parent'
        RETURN c1.name AS source, c2.name AS target, r2.relation AS later_relation
        """
        records = cls._run_query(tx, query, {"ep": episode_ref})
        return [
            {
                "constraint_id": "C-REL-001",
                "severity": "medium",
                "description": f"Parent relation between {r['source']} and {r['target']} contradicted by later relation: {r['later_relation']}",
                "evidence": [],
                "suggested_fix": "Ensure biological relations remain immutable",
            }
            for r in records
        ]
