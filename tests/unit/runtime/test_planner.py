"""Planner v1 against simulated inventories and the default catalog (table-driven).

These expected Plans are the authoritative worked examples (docs/hardware-adaptation.md).
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nip.contracts import (
    Autoscaling,
    Gpu,
    HardwareInventory,
    Mode,
    Node,
    Objective,
    Plan,
    Slot,
    SlotDecision,
)
from nip.runtime.catalog import Catalog, load_catalog
from nip.runtime.planner import PlanError, app, plan

CATALOG_YAML = Path(__file__).parents[3] / "config" / "catalog.yaml"


def _no_network(repo: str) -> tuple[float, float | None]:
    raise AssertionError(f"the default catalog must not need hf-mem ({repo})")


CATALOG = load_catalog(CATALOG_YAML, estimate=_no_network)


def _inv(n: int, name: str, total: float, free: float, cc: str, cpus: int) -> HardwareInventory:
    gpus = [
        Gpu(index=i, name=name, vram_total_gb=total, vram_free_gb=free, compute_capability=cc)
        for i in range(n)
    ]
    return HardwareInventory(
        fingerprint=f"sim:{n}x{name}",
        nodes=[Node(node_id="n0", cpus=cpus, ram_gb=64.0, gpus=gpus)],
        autoscaling=Autoscaling(enabled=False, max_gpu_nodes=0),
    )


# The laptop at its documented idle free memory (7.15 GB), a 48 GB workstation, an 8x H100 node.
LAPTOP = _inv(1, "NVIDIA GeForce RTX 4060 Laptop GPU", 8.0, 7.15, "8.9", 16)
WS48 = _inv(1, "NVIDIA RTX 6000 Ada Generation", 47.99, 47.4, "8.9", 32)
H100X8 = _inv(8, "NVIDIA H100 80GB HBM3", 79.65, 79.1, "9.0", 192)
INVENTORIES = {"1x8GB": LAPTOP, "1x48GB": WS48, "8x80GB": H100X8}

# Work units of a typical episode, every slot needed.
EPISODE = {
    Slot.TEXT_LLM: 400,
    Slot.VLM: 200,
    Slot.JUDGE_LLM: 100,
    Slot.ASR: 60,
    Slot.OCR: 600,
    Slot.DETECTOR: 600,
    Slot.IMAGE_EMBEDDER: 600,
    Slot.TEXT_EMBEDDER: 120,
    Slot.NER: 300,
    Slot.SHOT_DETECTOR: 4,
}


def _fmt(d: SlotDecision) -> str:
    """'variant xREPLICAS tpN ctxN gmuF' for engines, 'variant xR fracF' for actors."""
    if d.shared_with and d.replicas is None:
        return f"{d.variant} (shared)"
    parts = [d.variant, f"x{d.replicas}"]
    if d.gpus_per_replica:
        parts += [f"tp{d.gpus_per_replica}", f"ctx{d.context}", f"gmu{d.gpu_memory_utilization}"]
    else:
        parts.append(f"frac{d.gpu_fraction}")
    return " ".join(parts)


LAPTOP_STAGED = (
    "staged",
    ["timeline", "vision_prep", "text_prep", "vlm+llm", "judge"],
    {
        "text_llm": "qwen3.5-4b-awq x1 tp1 ctx16384 gmu0.79",  # startup peak 6.25 GiB
        "vlm": "qwen3.5-4b-awq (shared)",
        "judge_llm": "ministral-3-3b-fp8 x1 tp1 ctx8192 gmu0.82",
        "asr": "faster-whisper-large-v3-int8 x1 frac0.38",
        "ocr": "pp-ocrv6-medium x1 frac0.13",
        "detector": "llmdet-large x1 frac0.23",
        "image_embedder": "dinov2-large x1 frac0.2",
        "text_embedder": "qwen3-embedding-0.6b x1 frac0.2",
        "ner": "gliner-x-large x1 frac0.47",
        "shot_detector": "transnetv2 x1 frac0.07",
    },
    ["text_llm context reduced 32768 -> 16384", "judge_llm context reduced 16384 -> 8192"],
)

CASES = [
    ("1x8GB", "quality", *LAPTOP_STAGED),
    # Not even the smallest set packs on 6.65 GB usable: throughput falls back to staged.
    ("1x8GB", "throughput", *LAPTOP_STAGED),
    (
        "1x48GB",
        "quality",
        "staged",
        ["timeline+vision_prep+text_prep", "vlm+llm", "judge"],
        {
            "text_llm": "qwen3.8-27b-fp8 x1 tp1 ctx32768 gmu0.89",
            "vlm": "qwen3.8-27b-fp8 (shared)",
            "judge_llm": "gemma-4-31b-qat x1 tp1 ctx8192 gmu0.86",
            "asr": "faster-whisper-large-v3-int8 x1 frac0.07",
            "ocr": "pp-ocrv6-medium x1 frac0.03",
            "detector": "llmdet-large x1 frac0.04",
            "image_embedder": "dinov2-large x1 frac0.04",
            "text_embedder": "qwen3-embedding-8b x1 frac0.32",
            "ner": "gliner-x-large x1 frac0.08",
            "shot_detector": "transnetv2 x1 frac0.02",
        },
        ["judge_llm context reduced 16384 -> 8192"],
    ),
    (
        "1x48GB",
        "throughput",
        "resident",
        ["resident"],
        {
            # An independent judge (ministral@8k, 6.5 GiB) would push text_llm to 8k and asr to
            # turbo, so the judge reuses text_llm (step 7).
            "text_llm": "qwen3.8-27b-int4 x1 tp1 ctx16384 gmu0.57",
            "vlm": "qwen3.8-27b-int4 (shared)",
            "judge_llm": "qwen3.8-27b-int4 (shared)",
            "asr": "faster-whisper-large-v3-int8 x1 frac0.07",
            "ocr": "pp-ocrv6-medium x1 frac0.03",
            "detector": "llmdet-large x1 frac0.04",
            "image_embedder": "dinov2-large x1 frac0.04",
            "text_embedder": "qwen3-embedding-0.6b x1 frac0.04",
            "ner": "gliner-x-large x1 frac0.08",
            "shot_detector": "transnetv2 x1 frac0.02",
        },
        ["text_llm context reduced 32768 -> 16384"],
    ),
    (
        "8x80GB",
        "quality",
        "staged",
        ["timeline+vision_prep+text_prep", "vlm+llm", "judge"],
        {
            "text_llm": "qwen3.5-397b-a17b-fp8 x1 tp8 ctx32768 gmu0.72",
            "vlm": "qwen3.5-397b-a17b-fp8 (shared)",
            "judge_llm": "gemma-4-31b-qat x8 tp1 ctx16384 gmu0.71",
            "asr": "faster-whisper-large-v3-int8 x8 frac0.04",
            "ocr": "pp-ocrv6-medium x8 frac0.02",
            "detector": "llmdet-large x8 frac0.03",
            "image_embedder": "dinov2-large x8 frac0.03",
            "text_embedder": "qwen3-embedding-8b x8 frac0.19",
            "ner": "gliner-x-large x8 frac0.05",
            "shot_detector": "transnetv2 x4 frac0.01",  # capped by its 4 work units
        },
        [],
    ),
    (
        "8x80GB",
        "throughput",
        "resident",
        ["resident"],
        {
            "text_llm": "qwen3.5-397b-a17b-int4 x1 tp4 ctx32768 gmu0.77",
            "vlm": "qwen3.5-397b-a17b-int4 (shared)",
            "judge_llm": "gemma-4-31b-qat x4 tp1 ctx16384 gmu0.71",
            "asr": "faster-whisper-large-v3-int8 x3 frac0.04",
            "ocr": "pp-ocrv6-medium x3 frac0.02",
            "detector": "llmdet-large x3 frac0.03",
            "image_embedder": "dinov2-large x3 frac0.03",
            "text_embedder": "qwen3-embedding-8b x1 frac0.19",
            "ner": "gliner-x-large x3 frac0.05",
            "shot_detector": "transnetv2 x4 frac0.01",
        },
        [],
    ),
]


@pytest.mark.parametrize(
    ("machine", "objective", "mode", "groups", "decisions", "warnings"),
    CASES,
    ids=[f"{c[0]}-{c[1]}" for c in CASES],
)
def test_expected_plan(
    machine: str,
    objective: str,
    mode: str,
    groups: list[str],
    decisions: dict[str, str],
    warnings: list[str],
) -> None:
    inv = INVENTORIES[machine]
    p = plan(inv, CATALOG, EPISODE, Objective(objective))
    assert p.mode == mode
    assert [g.name for g in p.groups] == groups
    assert {s.value: _fmt(d) for s, d in p.decisions.items()} == decisions
    assert p.warnings == warnings
    assert p.skipped_slots == []
    judge = p.decisions[Slot.JUDGE_LLM]
    assert judge.independent_family is (judge.variant != p.decisions[Slot.TEXT_LLM].variant)
    vlm = p.decisions[Slot.VLM]  # catalog defaults for the image caps
    assert (vlm.max_pixels, vlm.images_per_prompt) == (589824, 2)
    assert sorted(s for g in p.groups for s in g.slots) == sorted(EPISODE)  # each slot once
    assert (p.inventory_fingerprint, p.catalog_sha256) == (inv.fingerprint, CATALOG.sha256)
    assert Plan.model_validate_json(p.model_dump_json()) == p  # contract round-trip
    assert plan(inv, CATALOG, EPISODE, Objective(objective)) == p  # deterministic


@pytest.mark.parametrize(
    ("free", "context", "kv_mib"),
    [
        (7.15, 16384, 2170),  # usable 6.65 - weights 4.0 - overhead 0.53 = 2.12 GiB
        (7.6, 16384, 2631),  # idle desktop: more free VRAM, more KV, same context
        (8.0, 16384, 2734),  # usable capped by 0.90 x 8.0 = 7.2
    ],
)
def test_laptop_llm_gets_an_exact_kv_budget_from_free_vram(
    free: float, context: int, kv_mib: int
) -> None:
    inv = _inv(1, "NVIDIA GeForce RTX 4060 Laptop GPU", 8.0, free, "8.9", 16)
    text = plan(inv, CATALOG, EPISODE).decisions[Slot.TEXT_LLM]
    assert (text.context, text.gpu_memory_utilization) == (context, 0.79)
    assert text.kv_cache_bytes == kv_mib * 2**20


def test_laptop_below_the_startup_peak_gets_no_llm() -> None:
    busy = _inv(1, "NVIDIA GeForce RTX 4060 Laptop GPU", 8.0, 6.6, "8.9", 16)  # usable 6.1 < 6.25
    p = plan(busy, CATALOG, EPISODE)
    assert {Slot.TEXT_LLM, Slot.VLM} <= set(p.skipped_slots)


@pytest.mark.parametrize(
    ("machine", "objective", "slot", "kv_mib"),
    [
        ("1x8GB", "quality", Slot.TEXT_LLM, 2170),  # usable 6.65 - weights 4.0 - overhead 0.53
        ("1x8GB", "quality", Slot.JUDGE_LLM, 972),  # usable 6.65 - 4.7 - 1.0 (staged: alone)
        ("1x48GB", "quality", Slot.TEXT_LLM, 10240),  # capped: 2 seq at default 32k ctx
        ("1x48GB", "quality", Slot.JUDGE_LLM, 17808),  # usable 43.19 - 23.3 - 2.5 GiB
        ("1x48GB", "throughput", Slot.TEXT_LLM, 8182),  # resident: actors reserved first
    ],
)
def test_expected_kv_budgets(machine: str, objective: str, slot: Slot, kv_mib: int) -> None:
    p = plan(INVENTORIES[machine], CATALOG, EPISODE, Objective(objective))
    assert p.decisions[slot].kv_cache_bytes == kv_mib * 2**20


def test_exact_kv_leaves_the_actors_their_catalog_sizes_on_a_shared_gpu() -> None:
    inv = INVENTORIES["1x48GB"]
    p = plan(inv, CATALOG, EPISODE, Objective.THROUGHPUT)
    assert p.mode is Mode.RESIDENT
    by_id = {v.id: v for v in CATALOG.variants}
    actors = sum(
        (by_id[d.variant].vram_gb or 0.0) * (d.replicas or 1)
        for d in p.decisions.values()
        if by_id[d.variant].engine == "actor" and d.replicas
    )
    text = p.decisions[Slot.TEXT_LLM]
    llm = by_id[text.variant]
    assert text.kv_cache_bytes and llm.weights_gb
    total = llm.weights_gb + llm.overhead_gb + text.kv_cache_bytes / 2**30 + actors
    usable = min(0.90 * 47.99, 47.4 - 0.5)
    assert actors > 5  # the actors really share this GPU
    assert usable - 0.01 < total <= usable  # nothing left over, and nothing taken from the actors


def test_catalog_kv_calibration_uses_1024_token_blocks() -> None:
    """EXP-001: vLLM held 35,746 tokens in 1.56 GiB; the planner's KV for them must match."""
    v = next(v for v in CATALOG.variants if v.id == "qwen3.5-4b-awq")
    assert v.kv_mb_per_1k_tokens
    assert v.kv_mb_per_1k_tokens * 35746 / 1024 == pytest.approx(1.56 * 1024, rel=0.01)


def test_kv_budget_is_capped_at_default_context_times_concurrency() -> None:
    gpu24 = _inv(1, "NVIDIA GeForce RTX 4090", 24.0, 23.5, "8.9", 16)
    text = plan(gpu24, CATALOG, EPISODE, Objective.THROUGHPUT).decisions[Slot.TEXT_LLM]
    assert (text.variant, text.context) == ("qwen3.5-4b-awq", 32768)
    assert text.kv_cache_bytes == int(45.8 * 32 * 2) * 2**20  # 2.86 GiB, not the 18 GiB left


def test_a_zero_kv_budget_is_rejected_not_ignored() -> None:
    with pytest.raises(ValueError, match="greater than 0"):
        SlotDecision(variant="x", kv_cache_bytes=0)


def test_engines_sharing_a_gpu_get_only_their_own_kv() -> None:
    gpu86 = _inv(1, "big", 86.0, 85.5, "8.9", 32)
    p = plan(gpu86, CATALOG, EPISODE, Objective.THROUGHPUT)
    assert p.mode is Mode.RESIDENT and p.decisions[Slot.JUDGE_LLM].independent_family
    for s in (Slot.TEXT_LLM, Slot.JUDGE_LLM):
        d = p.decisions[s]
        v = next(v for v in CATALOG.variants if v.id == d.variant)
        assert v.kv_mb_per_1k_tokens and d.context and d.kv_cache_bytes
        own = v.kv_mb_per_1k_tokens * d.context / 1024 * 2  # MiB for 2 sequences
        assert d.kv_cache_bytes == int(own) * 2**20


def test_tensor_parallel_engines_keep_gmu_sizing() -> None:
    text = plan(H100X8, CATALOG, EPISODE).decisions[Slot.TEXT_LLM]
    assert text.gpus_per_replica == 8 and text.kv_cache_bytes is None


def test_script_only_run_needs_no_vision_or_audio_slots() -> None:
    script_only = {Slot.TEXT_LLM: 50, Slot.JUDGE_LLM: 10, Slot.TEXT_EMBEDDER: 20, Slot.NER: 20}
    p = plan(LAPTOP, CATALOG, script_only)
    assert set(p.decisions) == set(script_only)
    assert [g.name for g in p.groups] == ["text_prep", "llm", "judge"]


def test_judge_reuses_text_llm_when_no_independent_family_fits() -> None:
    no_judges = Catalog(
        variants=[v for v in CATALOG.variants if v.serves != [Slot.JUDGE_LLM]], sha256="x"
    )
    p = plan(LAPTOP, no_judges, EPISODE)
    judge = p.decisions[Slot.JUDGE_LLM]
    assert (judge.variant, judge.independent_family) == ("qwen3.5-4b-awq", False)
    assert p.decisions[Slot.TEXT_LLM].shared_with == [Slot.VLM, Slot.JUDGE_LLM]
    assert p.groups[-1].name == "vlm+llm"  # the judge runs in the llm group, no own group
    assert Slot.JUDGE_LLM in p.groups[-1].slots


def test_throughput_judge_never_pushes_other_slots_down() -> None:
    no_judges = Catalog(
        variants=[v for v in CATALOG.variants if v.serves != [Slot.JUDGE_LLM]], sha256="x"
    )
    for inv in INVENTORIES.values():
        with_judges = plan(inv, CATALOG, EPISODE, Objective.THROUGHPUT)
        reuse_only = plan(inv, no_judges, EPISODE, Objective.THROUGHPUT)
        others = [s for s in EPISODE if s is not Slot.JUDGE_LLM]
        assert [_fmt(with_judges.decisions[s]).split(" x")[0] for s in others] == [
            _fmt(reuse_only.decisions[s]).split(" x")[0] for s in others
        ]
        for s in (Slot.TEXT_LLM, Slot.ASR):  # same variant and context
            assert with_judges.decisions[s].context == reuse_only.decisions[s].context


def test_vlm_image_caps_follow_the_catalog() -> None:
    vlm_ids = {v.id for v in CATALOG.variants if Slot.VLM in v.serves}
    bigger = Catalog(
        variants=[
            v.model_copy(update={"max_pixels": 1003520, "images_per_prompt": 4})
            if v.id in vlm_ids
            else v
            for v in CATALOG.variants
        ],
        sha256="x",
    )
    vlm = plan(H100X8, bigger, EPISODE).decisions[Slot.VLM]
    assert (vlm.variant, vlm.shared_with) == ("qwen3.5-397b-a17b-fp8", [Slot.TEXT_LLM])
    assert (vlm.max_pixels, vlm.images_per_prompt) == (1003520, 4)


def test_pin_is_honoured() -> None:
    p = plan(H100X8, CATALOG, EPISODE, pins={Slot.JUDGE_LLM: "ministral-3-3b-fp8"})
    assert p.decisions[Slot.JUDGE_LLM].variant == "ministral-3-3b-fp8"
    assert p.pins == {Slot.JUDGE_LLM: "ministral-3-3b-fp8"}


@pytest.mark.parametrize("pin", ["qwen3.5-397b-a17b-fp8", "no-such-variant", "dinov2-large"])
def test_pin_that_cannot_be_honoured_fails_fast(pin: str) -> None:
    with pytest.raises(PlanError):
        plan(LAPTOP, CATALOG, EPISODE, pins={Slot.TEXT_LLM: pin})


def test_no_gpu_skips_every_slot() -> None:
    cpu_only = _inv(0, "-", 0, 0, "0.0", 4)
    p = plan(cpu_only, CATALOG, EPISODE)
    assert p.decisions == {}
    assert p.skipped_slots == list(EPISODE)
    assert p.warnings == [f"no hardware for {s}" for s in EPISODE]


def test_cpu_profile_resolves_every_slot_to_its_stub() -> None:
    cpu_only = _inv(0, "-", 0, 0, "0.0", 4)
    p = plan(cpu_only, CATALOG, EPISODE, stub=True)
    assert p.mode is Mode.RESIDENT
    assert {d.variant for d in p.decisions.values()} == {"stub"}
    assert set(p.decisions) == set(EPISODE)


def test_compute_capability_gates_fp8() -> None:
    # Same memory as the 48 GB workstation (which gets qwen3.8-27b-fp8), but Turing: no FP8.
    turing = _inv(1, "Quadro RTX 8000", 47.99, 47.4, "7.5", 32)
    p = plan(turing, CATALOG, EPISODE)
    assert p.decisions[Slot.TEXT_LLM].variant == "qwen3.8-27b-int4"


def test_cli_simulate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NIP_PROFILE", raising=False)
    monkeypatch.chdir(CATALOG_YAML.parents[1])
    inv = tmp_path / "inventory.json"
    inv.write_text(LAPTOP.model_dump_json())
    result = CliRunner().invoke(app, ["--simulate", str(inv), "--objective", "quality"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["mode"] == "staged"

    monkeypatch.setenv("NIP_PIN_TEXT_LLM", "qwen3.5-397b-a17b-fp8")
    result = CliRunner().invoke(app, ["--simulate", str(inv)])
    assert result.exit_code == 1
    assert "CLUSTER_UNAVAILABLE" in result.output
