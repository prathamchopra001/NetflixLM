"""Script Critic Layer 1: the four deterministic plot rules, each one SQL file over timed facts.

architecture.md > Agent 3 > Layer 1; the queries live in `config/rules/plot.*.sql` (story order,
active facts only, one parameterized file per rule: `:show` slug, `:episode` ref). A row is one
violating script line: the claim is that line (`{ep}/line/{scene}.{seq}`); the fact that makes it a
violation (the death, the other location, the later learning, the destruction) is cited as
`fact/{id}` evidence with its quote, which is also how a fact from another episode is cited.
Verification step 2 runs the same SQL again against the current facts (`recheck`).

Agents read the store only: these checks take the run's Connection and never import `nip.knowledge`.
"""

import hashlib
import os
from collections.abc import Mapping
from typing import Any, ClassVar

from sqlalchemy import Connection, text

from nip.agents.base import Check, Finding, Input, WorkUnit
from nip.config import config_dir
from nip.contracts import refs
from nip.contracts.flag import CheckId, Evidence, EvidenceKind, EvidenceRole, Flag
from nip.contracts.timeline import Timeline

Row = Mapping[str, Any]


def rows(conn: Connection, check: str, show: str, episode: str) -> list[Row]:
    """The rule's violations with their claim in `episode`, one per claim line (first row wins)."""
    sql = (config_dir() / "rules" / f"{check}.sql").read_text(encoding="utf-8")
    first: dict[str, Row] = {}
    for r in conn.execute(text(sql), {"show": show, "episode": episode}).mappings():
        first.setdefault(claim_ref(row := dict(r)), row)
    return list(first.values())


def claim_ref(r: Row) -> str:
    return f"{r['episode']}/line/{r['scene_no']}.{r['line_seq']}"


def here(r: Row) -> str:
    return refs.scene(r["episode"], r["scene_no"])


def there(r: Row) -> str:
    """The scene of the other fact (`other_*` columns)."""
    return refs.scene(r["other_episode"], r["other_scene_no"])


class SqlRule(Check):
    requires = frozenset({Input.SCRIPT})
    version = "1"
    severity: ClassVar[int]
    other_role: ClassVar[EvidenceRole] = EvidenceRole.CONTRADICTION

    def __init__(self, conn: Connection | None = None, show: str | None = None):
        # file mode has no store (conn None): no facts, no findings
        self.conn, self.show = conn, show

    def describe(self, r: Row) -> tuple[str, str, str]:
        """(title, explanation, suggested fix) for one row."""
        raise NotImplementedError

    def other_evidence_role(self, r: Row) -> EvidenceRole:
        return self.other_role

    def params(self) -> dict[str, Any]:
        sql = (config_dir() / "rules" / f"{self.check}.sql").read_bytes()
        return {"sql": hashlib.sha256(sql).hexdigest()}

    def units(self, tl: Timeline) -> list[WorkUnit]:
        return [WorkUnit(f"{tl.episode}/{self.check}", ())] if self.conn is not None else []

    def run(self, unit: WorkUnit, tl: Timeline) -> list[Finding]:
        assert self.conn is not None and self.show is not None
        factor = float(os.environ.get("NIP_INFERRED_STORY_CONFIDENCE_FACTOR", "0.85"))
        out = []
        for r in rows(self.conn, str(self.check), self.show, tl.episode):
            line = tl.resolve(claim_ref(r))
            quote = r["claim_quote"] if line is not None and r["claim_quote"] in line.text else None
            evidence = [
                Evidence(
                    kind=EvidenceKind.SCRIPT_LINE,
                    ref=claim_ref(r),
                    role=EvidenceRole.CLAIM,
                    quote=quote,
                )
            ]
            fact = tl.resolve(f"fact/{r['other_fact']}") if r["other_fact"] is not None else None
            if fact is not None:
                evidence.append(
                    Evidence(
                        kind=EvidenceKind.FACT,
                        ref=fact.ref,
                        role=self.other_evidence_role(r),
                        quote=r.get("other_quote") or fact.text.split("\n")[0] or None,
                    )
                )
            title, explanation, fix = self.describe(r)
            conf = r["confidence"] * (factor if r["inferred"] else 1.0)
            out.append(
                Finding(
                    severity=self.severity,
                    confidence=min(1.0, float(conf)),
                    title=title,
                    explanation=explanation,
                    evidence=evidence,
                    suggested_fix=fix,
                )
            )
        return out

    def recheck(self, flag: Flag, tl: Timeline) -> bool:
        """Re-run the SQL on the current facts: the claimed line must still be a violation."""
        # ponytail: one whole-episode query per flag (~0.05 s); add a per-line parameter if needed
        claim = next((e for e in flag.evidence if e.role is EvidenceRole.CLAIM), None)
        if claim is None or self.conn is None or self.show is None:
            return False
        return any(
            claim_ref(r) == claim.ref
            for r in rows(self.conn, str(self.check), self.show, flag.episode)
        )


class KnowledgeOrder(SqlRule):
    check = CheckId.PLOT_KNOWLEDGE_ORDER
    severity = 3  # should fix: the story logic breaks but nothing blocks release by itself
    other_role = EvidenceRole.SETUP

    def describe(self, r: Row) -> tuple[str, str, str]:
        later = (
            f" {r['subject']} learns it only later, in {there(r)}."
            if r["other_fact"] is not None
            else f" No scene shows {r['subject']} learning it."
        )
        return (
            f"{r['subject']} refers to a secret before learning it",
            f"In {here(r)}, {r['subject']} refers to the secret '{r['object']}' but no earlier "
            f"scene in story order has them learn it.{later}",
            "Move the reference after the scene where the character learns it, or add or move the "
            "learning scene earlier.",
        )


class DeadActs(SqlRule):
    check = CheckId.PLOT_DEAD_ACTS
    severity = 4  # must fix: a dead character on screen is a glaring error
    other_role = EvidenceRole.CONTRADICTION

    def describe(self, r: Row) -> tuple[str, str, str]:
        return (
            f"{r['subject']} acts after dying",
            f"{r['subject']} is present or speaks in {here(r)}, after dying in {there(r)}, and "
            "the scene is not marked flashback, dream or vision.",
            "Mark the scene as a flashback, dream or vision, remove the character, or move the "
            "death later.",
        )


class TwoPlaces(SqlRule):
    check = CheckId.PLOT_TWO_PLACES
    severity = 3
    other_role = EvidenceRole.CONTRADICTION

    def describe(self, r: Row) -> tuple[str, str, str]:
        return (
            f"{r['subject']} is in two places at once",
            f"{r['subject']} is at {r['object']} in {here(r)} and at {r['other_object']} in "
            f"{there(r)} at the same story moment.",
            "Remove the character from one of the scenes, or separate the scenes in story time.",
        )


class PropProvenance(SqlRule):
    check = CheckId.PLOT_PROP_PROVENANCE
    severity = 2  # minor: a prop slip is easy to miss and to fix

    def other_evidence_role(self, r: Row) -> EvidenceRole:
        if r["detail"] == "before_obtained":
            return EvidenceRole.SETUP  # the later pickup
        return EvidenceRole.CONTRADICTION  # the loss

    def describe(self, r: Row) -> tuple[str, str, str]:
        if r["detail"] == "before_obtained":
            later = (
                f" It is first obtained in {there(r)}."
                if r["other_fact"] is not None
                else " No scene shows anyone obtaining it."
            )
            return (
                f"{r['subject']} uses the {r['object']} before obtaining it",
                f"In {here(r)}, {r['subject']} uses the {r['object']} but no earlier scene in "
                f"story order has anyone hold or own it.{later}",
                "Show the character obtaining the prop first, or move the use later.",
            )
        return (
            f"{r['subject']} uses the {r['object']} after it is gone",
            f"In {here(r)}, {r['subject']} uses the {r['object']}, which was destroyed or lost "
            f"in {there(r)}.",
            "Remove the use, or show the prop recovered or replaced.",
        )
