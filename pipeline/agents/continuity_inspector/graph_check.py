"""Continuity Inspector - deterministic KG constraint check for continuity violations."""

import uuid
from typing import Any

from neo4j import GraphDatabase


class GraphCheck:
    """Queries the constraint engine for prop/location/state continuity violations."""

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str) -> None:
        self._driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    def close(self) -> None:
        self._driver.close()

    def check_continuity(self, show_id: str, episode_ref: str) -> list[dict]:
        """Run constraint engine for prop/location/state violations, return ContinuityFlag dicts."""
        from pipeline.knowledge_graph.constraints.engine import ConstraintEngine

        engine = ConstraintEngine(self._driver)
        violations = engine.evaluate(show_id, episode_ref)

        flags: list[dict] = []
        for v in violations:
            if v.get("category") not in ("prop", "location", "state", "visual"):
                continue
            confidence = self._severity_to_confidence(v.get("severity", "medium"))
            flags.append({
                "id": str(uuid.uuid4()),
                "issue": v.get("description", "Unknown continuity issue"),
                "severity": v.get("severity", "medium"),
                "signal_source": "deterministic_graph",
                "evidence": v.get("evidence", []),
                "confidence": confidence,
                "script_version": episode_ref,
            })
        return flags

    @staticmethod
    def _severity_to_confidence(severity: str) -> float:
        mapping = {"critical": 0.95, "high": 0.85, "medium": 0.70, "low": 0.50}
        return mapping.get(severity, 0.70)
