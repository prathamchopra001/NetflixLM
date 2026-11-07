"""ner slot: zero-shot entity spans (GLiNER) for names, organizations, products and addresses.

`gliner-x-base` (knowledgator/gliner-x-base, Apache-2.0) covers en/es/fr/de, so names in all four
languages come from here rather than from spaCy (tech-stack.md › Build notes). One method:
`predict(text, labels) -> list[Entity]`.
"""

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

from nip.runtime.clients.llm import SERVE_URL  # NIP_SERVE_URL, default Serve on :8000

VARIANT = "gliner-x-base"
REPO = {
    "gliner-x-base": "knowledgator/gliner-x-base",
    "gliner-x-large": "knowledgator/gliner-x-large",
}


class Entity(BaseModel):
    text: str
    label: str
    start: int
    end: int
    score: float = Field(ge=0, le=1)


class GlinerBackend:
    def __init__(self, variant: str = VARIANT, *, cuda: bool = True, threshold: float = 0.5):
        os.environ.setdefault("HF_HOME", str(Path(__file__).resolve().parents[4] / "models" / "hf"))
        from gliner import GLiNER
        from gliner.data_processing import tokenizer

        # The repo's config asks for the stanza word splitter (needs stanza + langdetect, and
        # downloads a tokenizer per language at run time, nondeterministic on short OCR lines).
        # OCR text is Latin script: use gliner's own whitespace/punctuation splitter instead.
        tokenizer.StanzaWordsSplitter = tokenizer.WhitespaceTokenSplitter
        self.variant = variant
        self.threshold = threshold
        from huggingface_hub import snapshot_download

        # fp16 / bf16 / onnx copies of the weights are 3.9 GB we never load
        path = snapshot_download(
            REPO[variant], ignore_patterns=["onnx/*", "model.bf16*", "model.fp16*", "*.png"]
        )
        self._model = GLiNER.from_pretrained(path)
        if cuda:
            self._model.to("cuda")

    def predict(self, text: str, labels: Sequence[str]) -> list[Entity]:
        found = self._model.predict_entities(text, list(labels), threshold=self.threshold)
        return [Entity.model_validate(e) for e in found]


class StubNER:
    """No model (NIP_PROFILE=cpu): replays `recorded[text]` filtered to the asked labels."""

    variant = VARIANT

    def __init__(self, recorded: Mapping[str, Sequence[Entity]] | None = None) -> None:
        self._recorded = recorded or {}

    def predict(self, text: str, labels: Sequence[str]) -> list[Entity]:
        return [e for e in self._recorded.get(text, ()) if e.label in labels]


class ServeNER:
    """The Serve app of the ner slot: POST `{text, labels}`, get `{"entities": [...]}`."""

    def __init__(self, variant: str = VARIANT, base_url: str = SERVE_URL, timeout_s: float = 60):
        self.variant = variant
        self._url = f"{base_url}/models/{variant}"
        self._timeout = timeout_s

    def predict(self, text: str, labels: Sequence[str]) -> list[Entity]:
        r = httpx.post(
            self._url, json={"text": text, "labels": list(labels)}, timeout=self._timeout
        )
        r.raise_for_status()
        return [Entity.model_validate(e) for e in r.json()["entities"]]


class Actor:
    """Ray Serve replica (`serving._bind` uses `clients.<slot>.Actor`)."""

    def __init__(self, variant: str) -> None:
        self.variant = variant
        self._ner = GlinerBackend(variant)

    async def __call__(self, request: Any) -> dict[str, Any]:
        body = await request.json()
        found = self._ner.predict(body["text"], body["labels"])
        return {"variant": self.variant, "entities": [e.model_dump() for e in found]}
