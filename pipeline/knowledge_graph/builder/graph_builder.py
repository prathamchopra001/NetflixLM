"""Graph builder — converts extraction results to Neo4j nodes/edges."""
from __future__ import annotations

from typing import Any
from neo4j import GraphDatabase


class GraphBuilder:
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str) -> None:
        self._driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    def close(self) -> None:
        self._driver.close()

    def build_from_episode(self, episode_doc: dict) -> None:
        """Build or update KG from an EpisodeDocument."""
        show_id = episode_doc.get("show_id", "")
        season = episode_doc.get("season", 0)
        episode = episode_doc.get("episode", 0)
        ep_ref = f"S{season:02d}E{episode:02d}"

        with self._driver.session() as session:
            for entry in episode_doc.get("timeline", []):
                script = entry.get("script_block", {})
                scene_id = script.get("scene_id", "")
                location = script.get("location", "")
                timecode = entry.get("timecode", "00:00:00:00")

                # Create Location
                if location:
                    session.write_transaction(
                        self._merge_location, location, show_id, ep_ref, timecode
                    )

                # Create Characters
                for char in script.get("characters_present", []):
                    session.write_transaction(
                        self._merge_character, char, show_id, ep_ref, timecode, location
                    )

                # Dialogue edges (character speaks in scene)
                for d in script.get("dialogue", []):
                    session.write_transaction(
                        self._merge_character, d;halt, show_id, ep_ref, timecode, location
                    )

    @staticmethod
    def _merge_location(tx, name: str, show_id: str, episode_ref: str, timecode: str) -> None:
        tx.run(
            "MERGE (l:Location {name: $name, show_id: $show_id}) "
            "\n            ON CREATE SET l.first_appearance_tc = $timecode\n            "
            "SET l.last_seen_episode = $episode_ref",
            name=name, show_id=show_id, timecode=timecode, episode_ref=episode_ref,
        )

    @staticmethod
    def _merge_character(tx, name: str, show_id: str, episode_ref: str, timecode: str, location: str) -> None:
        tx.run(
            "MERGE (c:Character {name: $name, show_id: $show_id}) "
            "ON CREATE SET c.first_appearance_tc = $timecode\n            "
            "SET c.last_seen_episode = $episode_ref\n"
            "WITH c\n"
            "MATCH (l:Location {name: $location, show_id: $show_id})\n"
            "MERGE (c)-[r:AT_LOCATION {timecode: $timecode, episode_ref: $episode_ref}]->(l)",
            name=name, show_id=show_id, episode_ref=episode_ref, timecode=timecode, location=location,
        )
