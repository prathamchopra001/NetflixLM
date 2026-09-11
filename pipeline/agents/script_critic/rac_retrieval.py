"""Script Critic Layer 2 - RAC retrieval for motivational/emotional gap detection."""

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue


class RACRetrievalLayer:
    """Retrieves relevant prior scenes from Qdrant and uses LLM to identify motivational gaps."""

    def __init__(
        self,
        qdrant_uri: str,
        llm_url: str,
        collection_name: str = "nip_scenes",
    ) -> None:
        self._qdrant = QdrantClient(url=qdrant_uri)
        self._llm_url = llm_url
        self._collection = collection_name

    def find_motivational_gaps(self, show_id: str, episode_ref: str) -> list[dict]:
        """Retrieve prior context from Qdrant, ask LLM to identify motivational gaps."""
        current_scenes = self._fetch_current_scenes(show_id, episode_ref)
        prior_context = self._retrieve_prior_context(show_id, episode_ref, current_scenes)

        if not prior_context:
            return []

        return self._llm_identify_gaps(current_scenes, prior_context, episode_ref)

    def _fetch_current_scenes(self, show_id: str, episode_ref: str) -> list[dict]:
        results = self._qdrant.scroll(
            collection_name=self._collection,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="show_id", value=MatchValue(value=show_id)),
                    FieldCondition(key="episode_ref", value=MatchValue(value=episode_ref)),
                ]
            ),
            limit=50,
            with_payload=True,
        )
        return [point.payload for point in results[0]]

    def _retrieve_prior_context(self, show_id: str, episode_ref: str, current_scenes: list[dict]) -> list[dict]:
        if not current_scenes:
            return []

        query_text = " ".join(s.get("text", "")[:200] for s in current_scenes[:3])
        results = self._qdrant.query_points(
            collection_name=self._collection,
            query_text=query_text,
            query_filter=Filter(
                must=[FieldCondition(key="show_id", value=MatchValue(value=show_id))],
                must_not=[FieldCondition(key="episode_ref", value=MatchValue(value=episode_ref))],
            ),
            limit=10,
            with_payload=True,
        )
        return [point.payload for point in results]

    def _llm_identify_gaps(self, current_scenes: list[dict], prior_context: list[dict], episode_ref: str) -> list[dict]:
        import uuid

        prompt = (
            "Given this scene context and prior episodes, identify motivational inconsistencies...\n\n"
            f"PRIOR CONTEXT:\n{self._format_scenes(prior_context)}\n\n"
            f"CURRENT SCENES:\n{self._format_scenes(current_scenes)}\n\n"
            "List each motivational or emotional gap as a JSON array of objects with fields: "
            "issue, severity (critical/high/medium/low), evidence, suggested_fix"
        )

        response = self._call_llm(prompt)
        gaps = self._parse_llm_gaps(response)

        return [
            {
                "id": str(uuid.uuid4()),
                "issue": g["issue"],
                "severity": g.get("severity", "medium"),
                "layer": "rac_retrieval",
                "evidence": g.get("evidence", []),
                "confidence": self._severity_to_confidence(g.get("severity", "medium")),
                "suggested_fix": g.get("suggested_fix"),
                "script_version": episode_ref,
            }
            for g in gaps
        ]

    def _call_llm(self, prompt: str) -> str:
        resp = httpx.post(
            f"{self._llm_url}/v1/chat/completions",
            json={
                "model": "default",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _format_scenes(scenes: list[dict]) -> str:
        return "\n---\n".join(s.get("text", "")[:500] for s in scenes[:8])

    @staticmethod
    def _severity_to_confidence(severity: str) -> float:
        mapping = {"critical": 0.95, "high": 0.85, "medium": 0.70, "low": 0.50}
        return mapping.get(severity, 0.70)

    @staticmethod
    def _parse_llm_gaps(response: str) -> list[dict]:
        import json

        try:
            start = response.index("[")
            end = response.rindex("]") + 1
            return json.loads(response[start:end])
        except (ValueError, json.JSONDecodeError):
            return []
