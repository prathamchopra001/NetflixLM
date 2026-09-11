from __future__ import annotations
import json
from typing import Optional
import httpx


RELATION_EXTRACTION_PROMPT = """You are a knowledge graph relation extractor for TV scripts.

Given the following text and extracted entities, identify all relations between them.

Text:
{text}

Entities:
{entities}

For each relation, output a JSON object with:
- relation_type: one of AT_LOCATION, HOLDS_PROP, KNOWS_SECRET, ALIVE_AT, RELATES_TO, CONTAINS, STATE_OF, CAUSES, PRECEDES, CONCEALED_FROM
- source: entity name (source)
- target: entity name (target)
- timecode: SMPTE timecode if available, else null
- episode_ref: episode reference if available, else null
- confidence: 0.0-1.0

Output a JSON array of relation objects only. No explanation."""


class RelationExtractor:
    def __init__(self, llm_url: str = "http://localhost:8000", model: str = "meta-llama/Llama-3.1-70B-Instruct") -> None:
        self.llm_url = llm_url.rstrip("/")
        self.model = model
        self._fallback_mode = False

    def _call_llm(self, prompt: str) -> str:
        try:
            resp = httpx.post(
                f"{self.llm_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 4096,
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError):
            self._fallback_mode = True
            return "[]"

    def extract(self, text: str, entities: list[dict]) -> list[dict]:
        if self._fallback_mode:
            return []
        entities_str = json.dumps(entities, indent=2)
        prompt = RELATION_EXTRACTION_PROMPT.format(text=text, entities=entities_str)
        raw = self._call_llm(prompt)
        try:
            relations = json.loads(raw)
            if isinstance(relations, list):
                return relations
            return []
        except json.JSONDecodeError:
            return []
