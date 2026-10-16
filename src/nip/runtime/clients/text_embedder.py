"""Text embedder client (`text_embedder` slot): sentence-transformers in-process, a deterministic
hash-vector stub, and the Serve actor.

Every variant returns unit-length 1,024-d vectors, because pgvector's HNSW stops at 2,000
dimensions (tech-stack.md › Build notes): `qwen3-embedding-0.6b` is natively 1,024-d, and the 8b
variant is truncated to its first 1,024 dimensions (Matryoshka) and re-normalised. Scene text is
embedded on both sides of the retrieval, so no query instruction prompt is used.
"""

import hashlib
import math
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

EMBED_DIM = 1024
MAX_TOKENS = 1024  # a long scene is cut here (the model's own limit is 32k; CPU cost grows with it)
REPOS = {
    "qwen3-embedding-0.6b": "Qwen/Qwen3-Embedding-0.6B",
    "qwen3-embedding-8b": "Qwen/Qwen3-Embedding-8B",
}
_WORD = re.compile(r"\w+")


class SentenceTransformerEmbedder:
    def __init__(self, variant: str, repo: str | None = None, device: str = "cpu") -> None:
        os.environ.setdefault("HF_HOME", str(Path(__file__).resolve().parents[4] / "models" / "hf"))
        from sentence_transformers import SentenceTransformer  # torch: imported when a model loads

        self.variant = variant
        self.model = SentenceTransformer(
            repo or REPOS[variant],
            device=device,
            truncate_dim=EMBED_DIM,
            processor_kwargs={"padding_side": "left"},
            model_kwargs={"dtype": "float16" if device.startswith("cuda") else "float32"},
        )
        self.model.max_seq_length = MAX_TOKENS

    def embed(self, texts: Sequence[str], batch_size: int = 16) -> list[list[float]]:
        # Longest first: batches of similar length waste the least padding. encode() does it.
        vecs = self.model.encode(
            list(texts), batch_size=batch_size, normalize_embeddings=True, convert_to_numpy=True
        )
        return [[float(x) for x in v] for v in vecs]


class HashEmbedder:
    """cpu-profile backend: a bag of hashed words (md5 -> bucket, signed), unit length. The same
    text always gives the same vector and texts that share words are close, so retrieval tests
    are meaningful without a model."""

    def __init__(self, variant: str = "stub") -> None:
        self.variant = variant

    def embed(self, texts: Sequence[str], batch_size: int = 16) -> list[list[float]]:
        return [self._one(t) for t in texts]

    @staticmethod
    def _one(text: str) -> list[float]:
        v = [0.0] * EMBED_DIM
        for w in _WORD.findall(text.lower()):
            h = int.from_bytes(hashlib.md5(w.encode()).digest()[:8], "big")
            v[h % EMBED_DIM] += 1.0 if (h >> 63) else -1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]


TextEmbedder = SentenceTransformerEmbedder | HashEmbedder


def make_embedder(variant: str, catalog: Any = None, device: str = "cpu") -> TextEmbedder:
    """Backend for a catalog variant: the stub when its engine is `stub`, else sentence-
    transformers. ponytail: CPU by default (fast enough for 0.6B, see the notes); pass cuda."""
    v = next((v for v in catalog.variants if v.id == variant), None) if catalog else None
    if variant == "stub" or (v is not None and v.engine == "stub"):
        return HashEmbedder(variant)
    return SentenceTransformerEmbedder(variant, v.base_model if v else None, device)


class Actor:
    """Serve deployment (docs: Serve actors, serving._bind): `POST {"texts": [...]}` ->
    `{"variant", "embeddings"}`."""

    def __init__(self, variant: str) -> None:
        self.embedder = SentenceTransformerEmbedder(variant, device="cuda")

    async def __call__(self, request: Any) -> dict[str, Any]:
        body = await request.json()
        return {
            "variant": self.embedder.variant,
            "embeddings": self.embedder.embed(body["texts"]),
        }
