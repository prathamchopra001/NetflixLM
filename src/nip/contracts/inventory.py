"""HardwareInventory — docs/hardware-adaptation.md › Hardware Probe."""

from datetime import datetime

from nip.contracts._base import Contract


class Gpu(Contract):
    index: int
    name: str
    vram_total_gb: float
    vram_free_gb: float
    compute_capability: str  # "8.9"


class Node(Contract):
    node_id: str
    cpus: int
    ram_gb: float  # memory visible to the container (the WSL VM's limit under WSL2)
    gpus: list[Gpu] = []


class Autoscaling(Contract):
    enabled: bool
    max_gpu_nodes: int
    node_type: str | None = None


class HardwareInventory(Contract):
    fingerprint: str
    probed_at: datetime | None = None
    nodes: list[Node]
    autoscaling: Autoscaling
