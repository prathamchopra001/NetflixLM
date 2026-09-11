"""Recap Agent - tonal variant generation."""

import httpx


_DEFAULT_VARIANTS = [
    {"tone": "action", "thread_focus": "conflict and pacing"},
    {"tone": "romance", "thread_focus": "relationships and emotional beats"},
    {"tone": "suspense", "thread_focus": "tension and mystery"},
    {"tone": "comedy", "thread_focus": "humor and levity"},
    {"tone": "character_study", "thread_focus": "internal arcs and growth"},
]


class VariantEngine:
    """Generates tonal recap variants from a base recap via LLM."""

    def __init__(self, llm_url: str) -> None:
        self._llm_url = llm_url

    def generate_variants(
        self,
        base_recap: str,
        thread_labels: list[str],
        config: dict | None = None,
    ) -> list[dict]:
        """For each tone variant, call LLM to rewrite the base recap."""
        variants_config = (config or {}).get("variants", _DEFAULT_VARIANTS)
        thread_str = ", ".join(thread_labels) if thread_labels else "general narrative"

        results: list[dict] = []
        for variant in variants_config:
            tone = variant["tone"] if isinstance(variant, dict) else variant
            focus = variant.get("thread_focus", tone) if isinstance(variant, dict) else tone
            rewritten = self._rewrite(base_recap, tone, focus, thread_str)
            results.append({
                "text": rewritten,
                "tone": tone,
                "thread_focus": focus,
                "emotional_valence": self._infer_valence(tone),
            })
        return results

    def _rewrite(self, base_recap: str, tone: str, focus: str, thread_str: str) -> str:
        prompt = (
            f"Rewrite this recap with a {tone} focus, emphasizing {focus}...\n\n"
            f"Original recap:\n{base_recap}\n\n"
            f"Primary narrative threads: {thread_str}\n"
            f"Target tone: {tone}\n"
            "Produce a 3-paragraph variant maintaining factual accuracy."
        )

        resp = httpx.post(
            f"{self._llm_url}/v1/chat/completions",
            json={
                "model": "default",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _infer_valence(tone: str) -> dict[str, float]:
        valence_map = {
            "action": {"excitement": 0.9, "tension": 0.8},
            "romance": {"warmth": 0.9, "longing": 0.7},
            "suspense": {"tension": 0.9, "dread": 0.7},
            "comedy": {"joy": 0.8, "absurdity": 0.7},
            "character_study": {"introspection": 0.8, "empathy": 0.7},
        }
        return valence_map.get(tone, {"neutral": 0.5})
