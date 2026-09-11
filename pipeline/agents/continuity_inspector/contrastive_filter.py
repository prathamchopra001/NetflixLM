"""Continuity Inspector - contrastive pre-filter for cheap VLM routing."""

import httpx
import numpy as np
from typing import Any


class ContrastiveFilter:
    """Embeds adjacent keyframes and flags anomalous pairs for VLM routing.

    This cheap triage layer cuts VLM compute by ~80% by only routing
    pairs whose embedding distance exceeds the anomaly threshold.
    """

    def __init__(
        self,
        embedder_model: str = "BAAI/bge-large-en-v1.5",
        anomaly_threshold: float = 0.85,
    ) -> None:
        self._model_name = embedder_model
        self._threshold = anomaly_threshold
        self._embedder_url: str | None = None

    def set_embedder_url(self, url: str) -> None:
        self._embedder_url = url

    def flag_anomalous_pairs(self, keyframes: list[dict]) -> list[dict]:
        """Embed adjacent keyframes, compute cosine distance, flag pairs above threshold."""
        if len(keyframes) < 2:
            return []

        texts = [kf.get("caption", kf.get("text", "")) for kf in keyframes]
        embeddings = self._embed(texts)

        flagged: list[dict] = []
        for i in range(len(embeddings) - 1):
            dist = self._cosine_distance(embeddings[i], embeddings[i + 1])
            if dist > self._threshold:
                flagged.append({
                    "frame_a": keyframes[i].get("image_path", ""),
                    "frame_b": keyframes[i + 1].get("image_path", ""),
                    "distance": float(dist),
                    "episode_ref": keyframes[i].get("episode_ref", ""),
                    "scene_context": {
                        "frame_a_tc": keyframes[i].get("timecode", ""),
                        "frame_b_tc": keyframes[i + 1].get("timecode", ""),
                        "scene_id": keyframes[i].get("scene_id", ""),
                    },
                })
        return flagged

    def _embed(self, texts: list[str]) -> list[np.ndarray]:
        if self._embedder_url:
            return self._embed_via_api(texts)
        return self._embed_local(texts)

    def _embed_local(self, texts: list[str]) -> list[np.ndarray]:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(self._model_name)
        vectors = model.encode(texts, normalize_embeddings=True)
        return [np.asarray(v) for v in vectors]

    def _embed_via_api(self, texts: list[str]) -> list[np.ndarray]:
        resp = httpx.post(
            f"{self._embedder_url}/embed",
            json={"input": texts, "model": self._model_name},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return [np.asarray(d["embedding"]) for d in data.get("data", [])]

    @staticmethod
    def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 1.0
        similarity = np.dot(a, b) / (norm_a * norm_b)
        return float(1.0 - similarity)
