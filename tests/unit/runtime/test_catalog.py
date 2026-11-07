from pathlib import Path

import pytest

from nip.contracts import Slot
from nip.runtime.catalog import load_catalog, validate

CATALOG_YAML = Path(__file__).parents[3] / "config" / "catalog.yaml"

NEW_VARIANT = """
variants:
  - id: new-llm
    serves: [text_llm]
    engine: vllm
    base_model: org/new-llm
    overhead_gb: 1.0
    context: {default: 8192, min: 4096}
    quality_rank: 10
    license: Apache-2.0
  - id: new-embedder
    serves: [text_embedder]
    engine: actor
    base_model: org/new-embedder
    quality_rank: 10
    license: MIT
"""


def test_default_catalog_is_complete_without_hf_mem(tmp_path: Path) -> None:
    def never(repo: str) -> tuple[float, float | None]:
        raise AssertionError(repo)

    cat = load_catalog(CATALOG_YAML, estimate=never, cache_path=tmp_path / "c.json")
    for slot in Slot:  # every slot has a real variant besides the stub
        assert any(slot in v.serves and v.engine != "stub" for v in cat.variants), slot
    for v in cat.variants:
        if v.engine == "vllm":
            assert v.weights_gb and v.kv_mb_per_1k_tokens and v.context, v.id
        else:
            assert v.vram_gb is not None, v.id
    assert len(cat.sha256) == 64


def test_missing_sizes_come_from_hf_mem_once_then_the_cache(tmp_path: Path) -> None:
    yaml_path, cache = tmp_path / "catalog.yaml", tmp_path / "cache" / "hf-mem.json"
    yaml_path.write_text(NEW_VARIANT)
    calls: list[str] = []

    def fake(repo: str) -> tuple[float, float | None]:
        calls.append(repo)
        return (7.5, 96.0) if repo == "org/new-llm" else (1.1, None)

    first = load_catalog(yaml_path, estimate=fake, cache_path=cache)
    llm, emb = first.variants
    assert (llm.weights_gb, llm.kv_mb_per_1k_tokens, emb.vram_gb) == (7.5, 96.0, 1.1)
    assert calls == ["org/new-llm", "org/new-embedder"]

    second = load_catalog(yaml_path, estimate=fake, cache_path=cache)
    assert calls == ["org/new-llm", "org/new-embedder"]  # served from the cache
    assert second.sha256 == first.sha256


def test_llm_without_kv_estimate_is_rejected(tmp_path: Path) -> None:
    yaml_path = tmp_path / "catalog.yaml"
    yaml_path.write_text(NEW_VARIANT)
    with pytest.raises(ValueError, match="KV cache"):
        load_catalog(yaml_path, estimate=lambda r: (7.5, None), cache_path=tmp_path / "c.json")


def test_validate_excludes_with_reasons(tmp_path: Path) -> None:
    cat = load_catalog(CATALOG_YAML, cache_path=tmp_path / "c.json")
    allowed = {"Apache-2.0"}  # MIT is not in this allowlist
    out = validate(cat, vllm_version="0.29.1", licenses=allowed)
    assert out.excluded["transnetv2"] == "license MIT not allowed"
    assert out.excluded["qwen3.5-4b-awq"] == "needs vLLM 0.30, image has 0.29.1"
    assert "stub" not in out.excluded
    assert {v.id for v in out.variants}.isdisjoint(out.excluded)
    assert validate(cat, vllm_version="0.30.0", licenses=None).excluded == {}
