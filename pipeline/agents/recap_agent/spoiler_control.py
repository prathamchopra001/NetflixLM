"""Recap Agent - spoiler control based on KG reveals-Until timecodes."""

from neo4j import GraphDatabase


class SpoilerController:
    """Checks recaps against KG reveal timelines and enforces spoiler modes."""

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str) -> None:
        self._driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    def close(self) -> None:
        self._driver.close()

    def check_spoiler_risk(
        self,
        recap_text: str,
        show_id: str,
        episode_ref: str,
        spoiler_mode: str = "episodic",
    ) -> float:
        """Calculate spoiler risk score (0.0-1.0) for recap against future reveals."""
        if spoiler_mode != "episodic":
            return 0.0

        secrets = self._fetch_future_secrets(show_id, episode_ref)
        if not secrets:
            return 0.0

        recap_lower = recap_text.lower()
        matches = 0
        for secret in secrets:
            keywords = secret.get("keywords", [])
            if any(kw.lower() in recap_lower for kw in keywords):
                matches += 1

        return min(matches / max(len(secrets), 1), 1.0)

    def enforce_spoiler_mode(self, recap: dict, secrets: list[dict], mode: str = "episodic") -> dict:
        """Redact or rephrase spoiler content based on mode."""
        if mode != "episodic":
            return recap

        modified_text = recap.get("text", "")
        for secret in secrets:
            for keyword in secret.get("keywords", []):
                if keyword.lower() in modified_text.lower():
                    modified_text = modified_text.replace(keyword, "[REDACTED]")

        recap = dict(recap)
        recap["text"] = modified_text
        recap["spoiler_redacted"] = True
        return recap

    def _fetch_future_secrets(self, show_id: str, episode_ref: str) -> list[dict]:
        query = (
            "MATCH (s:Secret {show_id: $show_id}) "
            "WHERE s.revealed_in_episode > $ep "
            "RETURN s.keywords AS keywords, s.revealed_in_episode AS revealed_in_episode, "
            "s.description AS description"
        )
        records = self._driver.execute_query(query, {"show_id": show_id, "ep": episode_ref})
        return [dict(r) for r in records[0]] if records[0] else []
