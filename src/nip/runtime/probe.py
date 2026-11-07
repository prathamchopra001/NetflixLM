"""Hardware probe: GPUs via NVML, CPUs and RAM via the OS (hardware-adaptation.md › Hardware Probe).

`probe_node` runs on one machine (a Ray task per node in the cluster); `inventory` combines nodes.
Without NVML (no driver, CPU-only CI) a node simply has no GPUs.
"""

import ctypes
import hashlib
import json
import os
import socket
import sys
from datetime import UTC, datetime
from types import ModuleType
from typing import Any

import pynvml

from nip.contracts import Autoscaling, Gpu, HardwareInventory, Node

GIB = 2**30


def _ram_bytes() -> int:
    if sys.platform == "win32":  # dev laptop outside Docker; the image is Linux

        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + [
                (n, ctypes.c_ulonglong)
                for n in ("total", "avail", "pf_total", "pf_avail", "v_total", "v_avail", "v_ext")
            ]

        stat = MemoryStatusEx()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return int(stat.total)
    # Inside a container under WSL2 this is the WSL VM's memory, as the doc specifies.
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")


def _gpus(nvml: ModuleType | Any) -> list[Gpu]:
    try:
        nvml.nvmlInit()
    except nvml.NVMLError:
        return []  # no driver / no GPU: the cpu profile
    try:
        gpus = []
        for i in range(nvml.nvmlDeviceGetCount()):
            h = nvml.nvmlDeviceGetHandleByIndex(i)
            mem = nvml.nvmlDeviceGetMemoryInfo(h)
            major, minor = nvml.nvmlDeviceGetCudaComputeCapability(h)
            gpus.append(
                Gpu(
                    index=i,
                    name=nvml.nvmlDeviceGetName(h),
                    vram_total_gb=round(mem.total / GIB, 2),
                    vram_free_gb=round(mem.free / GIB, 2),
                    compute_capability=f"{major}.{minor}",
                )
            )
        return gpus
    finally:
        nvml.nvmlShutdown()


def probe_node(node_id: str | None = None, nvml: ModuleType | Any = pynvml) -> Node:
    return Node(
        node_id=node_id or socket.gethostname(),
        cpus=os.cpu_count() or 1,
        ram_gb=round(_ram_bytes() / GIB, 1),
        gpus=_gpus(nvml),
    )


def fingerprint(nodes: list[Node]) -> str:
    # Hardware identity only: node ids change on restart and free VRAM changes every probe.
    shape = sorted(
        json.dumps(
            [n.cpus, n.ram_gb, [[g.name, g.vram_total_gb, g.compute_capability] for g in n.gpus]]
        )
        for n in nodes
    )
    return "sha256:" + hashlib.sha256(json.dumps(shape).encode()).hexdigest()


def inventory(nodes: list[Node], max_gpu_nodes: int = 0) -> HardwareInventory:
    return HardwareInventory(
        fingerprint=fingerprint(nodes),
        probed_at=datetime.now(UTC),
        nodes=nodes,
        autoscaling=Autoscaling(enabled=max_gpu_nodes > 0, max_gpu_nodes=max_gpu_nodes),
    )


def probe() -> HardwareInventory:
    """This machine only. In the cluster, the controller runs `probe_node` as a task per node."""
    return inventory([probe_node()], int(os.environ.get("NIP_AUTOSCALE_MAX_GPU_NODES", "0")))
