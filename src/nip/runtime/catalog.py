"""Model catalog: load config/catalog.yaml, fill missing sizes with hf-mem, validate.

All `*_gb` sizes are GiB (2**30 bytes), the unit NVML-derived free memory is in.
"""

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from nip.contracts import Slot

CATALOG_PATH = Path("config/catalog.yaml")
GIB = 2**30

# repo -> (weights_gb, kv_mb_per_1k_tokens or None)
Estimator = Callable[[str], tuple[float, float | None]]


class Context(BaseModel):
    default: int
    min: int


class Variant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    serves: list[Slot]
    family: str | None = None
    engine: Literal["vllm", "actor", "stub"]
    base_model: str | None = None
    checkpoint: str | None = None
    quant: str | None = None
    min_vllm: str | None = None
    box_format: str | None = None
    weights_gb: float | None = None  # vllm
    overhead_gb: float = 0.0  # vllm
    kv_mb_per_1k_tokens: float | None = None  # vllm
    context: Context | None = None  # vllm
    tp_options: list[int] = [1]
    min_compute_capability: str | None = None
    vram_gb: float | None = None  # actor / stub
    quality_rank: int
    cost_hint: float = 1.0
    license: str

    @property
    def repo(self) -> str | None:
        return self.checkpoint or self.base_model

    @model_validator(mode="after")
    def _sized(self) -> Self:
        if self.engine == "vllm" and self.context is None:
            raise ValueError(f"{self.id}: vllm variants need a context")
        return self


class Catalog(BaseModel):
    variants: list[Variant]
    sha256: str
    excluded: dict[str, str] = {}  # variant id -> reason (validation)


def hf_mem_estimate(repo: str) -> tuple[float, float | None]:
    """Weights and KV cost from the repo's safetensors headers and config (nothing downloaded)."""
    import hf_mem  # network client; imported only when a variant actually lacks a size

    r = hf_mem.run(repo, experimental=True, max_model_len=1024, batch_size=1)
    assert isinstance(r.memory, int)  # safetensors repos give one total
    kv = r.kv_cache if isinstance(r.kv_cache, int) else None
    return round(r.memory / GIB, 2), None if kv is None else round(kv / 2**20, 1)


def _cache_path() -> Path:
    return Path(os.environ.get("HF_HOME", "models/hf")) / "hf-mem-cache.json"


def _fill(v: Variant, estimate: Estimator, cache: dict[str, list[float | None]]) -> Variant:
    missing = (
        v.weights_gb is None or v.kv_mb_per_1k_tokens is None
        if v.engine == "vllm"
        else v.engine == "actor" and v.vram_gb is None
    )
    if not missing:
        return v
    if v.repo is None:
        raise ValueError(f"{v.id}: no size and no base_model/checkpoint to estimate it from")
    if v.repo not in cache:
        cache[v.repo] = list(estimate(v.repo))
    weights, kv = cache[v.repo]
    if v.engine == "actor":
        # ponytail: weights only; runtime overhead comes from calibration after the first load
        return v.model_copy(update={"vram_gb": weights})
    if kv is None and v.kv_mb_per_1k_tokens is None:
        raise ValueError(f"{v.id}: hf-mem cannot estimate the KV cache of {v.repo}")
    estimated = {"weights_gb": weights, "kv_mb_per_1k_tokens": kv}
    return v.model_copy(update={k: x for k, x in estimated.items() if getattr(v, k) is None})


def load_catalog(
    path: Path = CATALOG_PATH,
    estimate: Estimator = hf_mem_estimate,
    cache_path: Path | None = None,
) -> Catalog:
    """Variants without a size get an hf-mem estimate, cached per repo in `cache_path`."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cache_path = cache_path or _cache_path()
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    before = len(cache)
    variants = [_fill(Variant.model_validate(v), estimate, cache) for v in raw["variants"]]
    if len(cache) != before:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True))
    ids = [v.id for v in variants]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate variant ids in the catalog")
    # Hash what the planner sees (estimates included), not the file bytes.
    blob = json.dumps([v.model_dump(mode="json") for v in variants], sort_keys=True)
    return Catalog(variants=variants, sha256=hashlib.sha256(blob.encode()).hexdigest())


def _version(s: str) -> tuple[int, ...]:
    return tuple(int(p) for p in s.split("."))


def validate(catalog: Catalog, vllm_version: str | None, licenses: set[str] | None) -> Catalog:
    """Drop variants the image can't load or the license policy forbids (None = don't check).

    Compute capability is checked per GPU by the planner.
    """
    excluded: dict[str, str] = {}
    for v in catalog.variants:
        if licenses is not None and v.engine != "stub" and v.license not in licenses:
            excluded[v.id] = f"license {v.license} not allowed"
        elif vllm_version and v.min_vllm and _version(v.min_vllm) > _version(vllm_version):
            excluded[v.id] = f"needs vLLM {v.min_vllm}, image has {vllm_version}"
    return catalog.model_copy(
        update={
            "variants": [v for v in catalog.variants if v.id not in excluded],
            "excluded": excluded,
        }
    )
