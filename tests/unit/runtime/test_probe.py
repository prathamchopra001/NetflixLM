from types import SimpleNamespace
from typing import Any

from nip.runtime.probe import GIB, fingerprint, inventory, probe_node


class FakeNVMLError(Exception):
    pass


def fake_nvml(gpus: list[tuple[str, int, int, tuple[int, int]]] | None) -> Any:
    """Stand-in NVML: (name, total B, free B, compute capability) per GPU; None = no driver."""

    def init() -> None:
        if gpus is None:
            raise FakeNVMLError("NVML Shared Library Not Found")

    return SimpleNamespace(
        NVMLError=FakeNVMLError,
        nvmlInit=init,
        nvmlShutdown=lambda: None,
        nvmlDeviceGetCount=lambda: len(gpus or []),
        nvmlDeviceGetHandleByIndex=lambda i: (gpus or [])[i],
        nvmlDeviceGetName=lambda h: h[0],
        nvmlDeviceGetMemoryInfo=lambda h: SimpleNamespace(total=h[1], free=h[2]),
        nvmlDeviceGetCudaComputeCapability=lambda h: h[3],
    )


LAPTOP_GPU = ("NVIDIA GeForce RTX 4060 Laptop GPU", 8188 * 2**20, 7321 * 2**20, (8, 9))


def test_probe_reads_gpus_in_gib() -> None:
    node = probe_node("a1f3", fake_nvml([LAPTOP_GPU, LAPTOP_GPU]))
    assert node.node_id == "a1f3"
    assert node.cpus >= 1 and node.ram_gb > 0
    assert [g.index for g in node.gpus] == [0, 1]
    g = node.gpus[0]
    # The doc's laptop numbers: 8,188 MiB total, 7,321 MiB free at idle.
    assert (g.name, g.vram_total_gb, g.vram_free_gb) == (LAPTOP_GPU[0], 8.0, 7.15)
    assert g.compute_capability == "8.9"


def test_probe_without_nvml_has_no_gpus() -> None:
    assert probe_node("cpu", fake_nvml(None)).gpus == []


def test_fingerprint_ignores_free_memory_and_node_ids() -> None:
    busy = (LAPTOP_GPU[0], LAPTOP_GPU[1], 2 * GIB, (8, 9))
    a = probe_node("a", fake_nvml([LAPTOP_GPU]))
    b = probe_node("b", fake_nvml([busy]))
    other = probe_node("a", fake_nvml([("NVIDIA H100 80GB HBM3", 80 * GIB, 79 * GIB, (9, 0))]))
    assert fingerprint([a]) == fingerprint([b]) != fingerprint([other])
    inv = inventory([a], max_gpu_nodes=0)
    assert inv.fingerprint.startswith("sha256:") and inv.autoscaling.enabled is False
