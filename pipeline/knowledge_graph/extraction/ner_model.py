from __future__ import annotations
from typing import Optional


DEFAULT_LABELS = ["character", "location", "prop", "event", "secret"]


class NERExtractor:
    def __init__(self, model_name: str = "urchade/gliner-multi", confidence_threshold: float = 0.95) -> None:
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self._model: Optional[object] = None
        self._review_queue: list[dict] = []

    def _load_model(self) -> None:
        try:
            from gliner import GLiNER
            self._model = GLiNER(model=self.model_name)
        except ImportError:
            self._model = None

    def extract(self, text: str, labels: Optional[list[str]] = None) -> list[dict]:
        labels = labels or DEFAULT_LABELS
        if self._model is None:
            self._load_model()
        if self._model is None:
            return []
        spans = self._model.predict_entities(text, labels, threshold=self.confidence_threshold)
        results = []
        for span in spans:
            result = {
                "entity_type": span.get("label", "unknown"),
                "name": span.get("text", ""),
                "text_span": (span.get("start", 0), span.get("end", 0)),
                "confidence": span.get("score", 0.0),
            }
            if result["confidence"] < self.confidence_threshold:
                self._review_queue.append(result)
            else:
                results.append(result)
        return results

    @property
    def review_queue(self) -> list[dict]:
        return list(self._review_queue)

    def clear_review_queue(self) -> None:
        self._review_queue.clear()
