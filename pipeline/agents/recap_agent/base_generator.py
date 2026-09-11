"""Recap Agent - base recap generation from KG scene nodes."""

import httpx
from neo4j import GraphDatabase


class BaseRecapGenerator:
    """Queries KG for scene nodes and generates a structured base recap via LLM."""

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        llm_url: str,
    ) -> None:
        self._driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self._llm_url = llm_url

    def close(self) -> None:
        self._driver.close()

    def generate(
        self,
        show_id: str,
        episode_ref: str,
        spoiler_mode: str = "episodic",
    ) -> dict:
        """Query KG scene nodes, identify threads, draft recap via LLM."""
        scenes = self._fetch_scene_nodes(show_id, episode_ref)
        thread_labels = self._identify_threads(scenes)
        base_recap = self._draft_recap(scenes, thread_labels, episode_ref, spoiler_mode)
        emotional_valence_map = self._extract_emotional_valence(scenes)
        character_arc_weights = self._compute_character_arcs(scenes)

        return {
            "episode_ref": episode_ref,
            "base_recap": base_recap,
            "thread_labels": thread_labels,
            "emotional_valence_map": emotional_valence_map,
            "character_arc_weights": character_arc_weights,
        }

    def _fetch_scene_nodes(self, show_id: str, episode_ref: str) -> list[dict]:
        query = (
            "MATCH (s:Scene {show_id: $show_id, episode_ref: $ep}) "
            "OPTIONAL MATCH (s)-[:HAS_CHARACTER]->(c:Character) "
            "OPTIONAL MATCH (s)-[:AT_LOCATION]->(l:Location) "
            "RETURN s ORDER BY s.timecode_start"
        )
        records = self._driver.execute_query(query, {"show_id": show_id, "ep": episode_ref})
        return [dict(r["s"]) for r in records[0]] if records[0] else []

    @staticmethod
    def _identify_threads(scenes: list[dict]) -> list[str]:
        thread_counts: dict[str, int] = {}
        for scene in scenes:
            for tag in scene.get("genre_tags", []):
                thread_counts[tag] = thread_counts.get(tag, 0) + 1
        sorted_threads = sorted(thread_counts, key=thread_counts.get, reverse=True)
        return sorted_threads[:3]

    def _draft_recap(
        self,
        scenes: list[dict],
        thread_labels: list[str],
        episode_ref: str,
        spoiler_mode: str,
    ) -> str:
        scene_text = "\n".join(
            f"Scene {i+1}: {s.get('summary', s.get('description', ''))}"
            for i, s in enumerate(scenes[:20])
        )

        prompt = (
            f"Generate a structured recap of this episode based on the scene graph nodes...\n\n"
            f"Episode: {episode_ref}\n"
            f"Primary threads: {', '.join(thread_labels)}\n"
            f"Spoiler mode: {spoiler_mode}\n\n"
            f"SCENES:\n{scene_text}\n\n"
            "Produce a 3-paragraph recap covering setup, escalation, and resolution."
        )

        resp = httpx.post(
            f"{self._llm_url}/v1/chat/completions",
            json={
                "model": "default",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _extract_emotional_valence(scenes: list[dict]) -> dict[str, float]:
        valence: dict[str, float] = {}
        for scene in scenes:
            emotion = scene.get("dominant_emotion", "neutral")
            intensity = scene.get("emotional_intensity", 0.5)
            valence[emotion] = max(valence.get(emotion, 0.0), intensity)
        return valence

    @staticmethod
    def _compute_character_arcs(scenes: list[dict]) -> dict[str, float]:
        weights: dict[str, float] = {}
        for scene in scenes:
            for char in scene.get("characters", []):
                weights[char] = weights.get(char, 0.0) + 1.0
        total = sum(weights.values()) or 1.0
        return {k: round(v / total, 3) for k, v in weights.items()}
