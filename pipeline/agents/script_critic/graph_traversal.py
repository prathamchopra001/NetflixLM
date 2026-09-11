"""Script Critic Layer 1 - KG traversal for plot hole detection."""

import uuid
from typing import Any

from neo4j import GraphDatabase


class GraphTraversalLayer:
    """Queries the knowledge graph for constraint violations and maps them to plot hole flags."""

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str) -> None:
        self._driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    def close(self) -> None:
        self._driver.close()

    def find_plot_holes(self, show_id: str, episode_ref: str) -> list[dict]:
        """Query KG constraint engine for violations, return PlotHoleFlag dicts."""
        from pipeline.knowledge_graph.constraints.engine import ConstraintEngine

        engine = ConstraintEngine(self._driver)
        violations = engine.evaluate(show_id, episode_ref)

        flags: list[dict] = []
        for v in violations:
            confidence = self._map_severity_to_confidence(v.get("severity", "medium"))
            flags.append({
                "id": str(uuid.uuid4()),
                "issue": v.get("description", "Unknown plot hole"),
                "severity": v.get("severity", "medium"),
                "layer": "graph_traversal",
                "evidence": v.get("evidence", []),
                "confidence": confidence,
                "suggested_fix": v.get("suggested_fix"),
                "script_version": episode_ref,
            })
        return flags

    @staticmethod
    def _map_severity_to_confidence(severity: str) -> float:
        mapping = {"critical": 0.95, "high": 0.85, "medium": 0.70, "low": 0.50}
        return mapping.get(severity, 0.70)
