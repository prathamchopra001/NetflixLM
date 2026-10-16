"""Planner v1: (inventory, catalog, workload, objective, pins) -> Plan. Pure and deterministic.

docs/hardware-adaptation.md › The Planner. Memory is budgeted per GPU in GiB:
usable = min(utilization × total, free − margin); an LLM/VLM replica at tensor-parallel degree tp
needs weights/tp + KV(context × CONCURRENCY)/tp + overhead on each of its tp GPUs.
"""

import math
import os
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated

import typer

from nip.contracts import HardwareInventory, Mode, Objective, Plan, Slot, SlotDecision, StageGroup
from nip.runtime.catalog import Catalog, Variant, load_catalog, validate
from nip.runtime.probe import probe

CONCURRENCY = 2  # sequences per LLM/VLM replica the KV budget covers
EPS = 1e-9

# Staged mode: groups in data-dependency order (adjacent groups merge when they fit together).
STAGES: list[tuple[str, list[Slot]]] = [
    ("timeline", [Slot.SHOT_DETECTOR, Slot.ASR]),
    ("vision_prep", [Slot.OCR, Slot.DETECTOR, Slot.IMAGE_EMBEDDER]),
    ("text_prep", [Slot.TEXT_EMBEDDER, Slot.NER]),
    ("vlm", [Slot.VLM]),
    ("llm", [Slot.TEXT_LLM]),
    ("judge", [Slot.JUDGE_LLM]),
]


class PlanError(Exception):
    """A pin that cannot be honoured (API error code CLUSTER_UNAVAILABLE)."""

    code = "CLUSTER_UNAVAILABLE"


@dataclass(frozen=True)
class _Gpu:
    node: int
    name: str
    cc: tuple[int, ...]
    total: float
    usable: float


@dataclass(frozen=True)
class _Cand:
    """One way to deploy a variant: tensor-parallel degree, context, GiB per GPU."""

    variant: Variant
    tp: int
    context: int | None
    per_gpu: float

    @property
    def gb(self) -> float:
        return self.per_gpu * self.tp


def _cc(s: str) -> tuple[int, ...]:
    return tuple(int(p) for p in s.split("."))


def _ceil2(x: float) -> float:
    return math.ceil(round(x * 100, 6)) / 100


class _Cluster:
    """Free GiB per GPU while packing. Multi-GPU replicas take whole, untouched GPUs (Ray
    allocates them whole); single-GPU engines and actors take fractions."""

    def __init__(self, gpus: list[_Gpu]) -> None:
        self.gpus = gpus
        self.free = [g.usable for g in gpus]
        self.engine = [False] * len(gpus)

    def place(self, c: _Cand, exclude: set[int] | frozenset[int] = frozenset()) -> list[int] | None:
        v = c.variant
        if v.engine == "stub":
            return []
        need = _cc(v.min_compute_capability) if v.min_compute_capability else ()
        ok = [
            i
            for i, g in enumerate(self.gpus)
            if self.free[i] >= c.per_gpu - EPS
            and g.cc >= need
            and self.free[i] > EPS
            and i not in exclude
        ]
        if c.tp > 1:
            for node, name in dict.fromkeys((self.gpus[i].node, self.gpus[i].name) for i in ok):
                group = [
                    i
                    for i in ok
                    if (self.gpus[i].node, self.gpus[i].name) == (node, name)
                    and self.free[i] == self.gpus[i].usable
                ]
                if len(group) >= c.tp:
                    for i in group[: c.tp]:
                        self.free[i], self.engine[i] = 0.0, True
                    return group[: c.tp]
            return None
        if v.engine == "vllm":  # a GPU of its own where possible; share only when none is left
            ok = [i for i in ok if not self.engine[i]] or ok
        if not ok:
            return None
        i = min(ok, key=lambda i: self.free[i])  # best fit
        self.free[i] -= c.per_gpu
        self.engine[i] = self.engine[i] or v.engine == "vllm"
        return [i]


def _pack(gpus: list[_Gpu], cands: list[_Cand]) -> tuple[_Cluster, dict[str, list[int]]] | None:
    cluster, where = _Cluster(gpus), {}
    for c in sorted(cands, key=lambda c: (c.variant.engine != "vllm", -c.tp, -c.per_gpu)):
        placed = cluster.place(c)
        if placed is None:
            return None
        where[c.variant.id] = placed
    return cluster, where


_Deps = dict[str, tuple[_Cand, list[Slot]]]  # variant id -> (how it's deployed, slots it serves)


def _replicas(
    cluster: _Cluster, deps: _Deps, where: dict[str, list[int]], workload: dict[Slot, int]
) -> dict[str, int]:
    """With one replica each placed, add more, one at a time, to the deployment with the highest
    demand (units × cost_hint) per replica that still fits. At most one replica of a deployment
    per GPU, and never more replicas than work units."""
    units = {vid: sum(workload[s] for s in slots) for vid, (_, slots) in deps.items()}
    used = {vid: set(gpus) for vid, gpus in where.items()}
    reps = {vid: 1 for vid in deps}
    while True:
        demand = {v: units[v] * deps[v][0].variant.cost_hint / reps[v] for v in deps}
        for vid in sorted(deps, key=lambda v: (-demand[v], v)):
            placed = cluster.place(deps[vid][0], used[vid]) if reps[vid] < units[vid] else None
            if placed:
                used[vid].update(placed)
                reps[vid] += 1
                break
        else:
            return reps


def _placements(v: Variant, gpus: list[_Gpu]) -> list[_Cand]:
    """Ways `v` fits alone: per context (default, halving to min), the smallest tp that fits."""
    if v.engine != "vllm":
        c = _Cand(v, 1, None, v.vram_gb or 0.0)
        return [c] if _Cluster(gpus).place(c) is not None else []
    assert v.context and v.weights_gb is not None and v.kv_mb_per_1k_tokens is not None
    contexts, ctx = [], v.context.default
    while ctx > v.context.min:
        contexts.append(ctx)
        ctx //= 2
    contexts.append(v.context.min)
    cands = []
    for ctx in contexts:
        for tp in sorted(v.tp_options):
            kv = v.kv_mb_per_1k_tokens * ctx / 1024 * CONCURRENCY / 1024
            c = _Cand(v, tp, ctx, (v.weights_gb + kv) / tp + v.overhead_gb)
            if _Cluster(gpus).place(c) is not None:
                cands.append(c)
                break
    return cands


def plan(
    inventory: HardwareInventory,
    catalog: Catalog,
    workload: dict[Slot, int],
    objective: Objective = Objective.QUALITY,
    pins: dict[Slot, str] | None = None,
    *,
    stub: bool = False,
    gpu_mem_utilization: float = 0.90,
    margin_gb: float = 0.5,
) -> Plan:
    """`workload`: work units per slot; slots with no units are not needed by this run.
    `stub=True` is NIP_PROFILE=cpu: every slot resolves to its stub variant."""
    pins = pins or {}
    required = [s for s in Slot if workload.get(s, 0) > 0]
    if stub:
        stubs = {s: v.id for v in catalog.variants if v.engine == "stub" for s in v.serves}
        served = [s for s in required if s in stubs]
        missing = [s for s in required if s not in stubs]
        return Plan(
            inventory_fingerprint=inventory.fingerprint,
            catalog_sha256=catalog.sha256,
            objective=objective,
            pins=pins,
            mode=Mode.RESIDENT,
            groups=[StageGroup(name="resident", slots=served)],
            decisions={s: SlotDecision(variant=stubs[s], replicas=1) for s in served},
            skipped_slots=missing,
            warnings=[f"no hardware for {s}" for s in missing],
        )

    gpus = [
        _Gpu(
            n,
            g.name,
            _cc(g.compute_capability),
            g.vram_total_gb,
            min(gpu_mem_utilization * g.vram_total_gb, g.vram_free_gb - margin_gb),
        )
        for n, node in enumerate(inventory.nodes)
        for g in node.gpus
    ]

    # 1–3. Candidates per required slot, best first. The judge's list ends with "reuse text_llm".
    cands: dict[Slot, list[_Cand | None]] = {}
    skipped: list[Slot] = []
    for slot in required:
        pool = [v for v in catalog.variants if slot in v.serves and v.engine != "stub"]
        if slot in pins:
            pool = [v for v in pool if v.id == pins[slot]]
            if not pool:
                raise PlanError(f"pinned {pins[slot]!r} is not a catalog variant for {slot}")
        elif slot is Slot.JUDGE_LLM and Slot.TEXT_LLM in cands:
            text = cands[Slot.TEXT_LLM][0]
            assert text is not None
            pool = [v for v in pool if v.family != text.variant.family]
        ranked = sorted(pool, key=lambda v: (-v.quality_rank, v.id))
        found: list[_Cand | None] = [c for v in ranked for c in _placements(v, gpus)]
        if slot in pins and not found:
            raise PlanError(f"pinned variant {pins[slot]!r} does not fit on this cluster")
        if slot is Slot.JUDGE_LLM and Slot.TEXT_LLM in cands and slot not in pins:
            found.append(None)
        if found:
            cands[slot] = found
        else:
            skipped.append(slot)

    def effective(choice: dict[Slot, int]) -> dict[Slot, _Cand]:
        """vlm rides on text_llm's model when it serves both; a reusing judge rides on it too."""
        eff: dict[Slot, _Cand] = {}
        for s, i in choice.items():
            c = cands[s][i]
            text = eff.get(Slot.TEXT_LLM)
            rides = s is Slot.VLM and s not in pins and text and s in text.variant.serves
            if text and (c is None or rides):
                c = text
            assert c is not None
            eff[s] = c
        return eff

    def deployments(eff: dict[Slot, _Cand], slots: list[Slot]) -> _Deps:
        deps: _Deps = {}
        for s in sorted(slots, key=list(Slot).index):
            deps.setdefault(eff[s].variant.id, (eff[s], []))[1].append(s)
        return deps

    def packs(choice: dict[Slot, int]) -> bool:
        deps = deployments(effective(choice), list(choice))
        return _pack(gpus, [c for c, _ in deps.values()]) is not None

    def gb(choice: dict[Slot, int]) -> float:
        return sum(c.gb for c, _ in deployments(effective(choice), list(choice)).values())

    def rank(choice: dict[Slot, int], s: Slot) -> int:
        c = cands[s][choice[s]]
        return c.variant.quality_rank if c else 0

    # 4. Resident or staged.
    best = {s: 0 for s in cands}
    choice = dict(best)
    if objective is Objective.QUALITY:
        resident = packs(best)
    else:  # greedy: downgrade where quality lost per GiB freed is smallest, until the set packs
        capacity = sum(g.usable for g in gpus)
        while not packs(choice):
            # GiB beyond the shortfall earn nothing; if the sum fits, packing is the problem
            short = gb(choice) - capacity
            moves = []
            for k, s in enumerate(choice):
                for j in range(choice[s] + 1, len(cands[s])):
                    new = {**choice, s: j}
                    freed = gb(choice) - gb(new)
                    if freed > EPS:
                        useful = min(freed, short) if short > EPS else freed
                        moves.append(((rank(choice, s) - rank(new, s)) / useful, -freed, k, j, s))
            if not moves:
                break
            *_, j, s = min(moves)
            choice[s] = j
        resident = packs(choice)
        if resident:  # climb back wherever the packed set leaves room (greedy over-shoots)
            for s in choice:
                choice[s] = next(j for j in range(choice[s] + 1) if packs({**choice, s: j}))
        else:
            choice = dict(best)

    eff = effective(choice)
    judge = choice.get(Slot.JUDGE_LLM)
    judge_reuses = judge is not None and cands[Slot.JUDGE_LLM][judge] is None

    # Stage groups: required slots only; merge adjacent groups whose models fit together.
    if resident:
        stages = [("resident", list(choice))]
    else:
        stages = []
        for name, slots in STAGES:
            ss = [s for s in slots if s in choice and not (s is Slot.JUDGE_LLM and judge_reuses)]
            if name == "llm" and judge_reuses:
                ss.append(Slot.JUDGE_LLM)
            if not ss:
                continue
            fits = _pack(gpus, [c for c, _ in deployments(eff, ss).values()]) is not None
            stages += [(name, ss)] if fits else [(f"{name}:{s}", [s]) for s in ss]
        merged = stages[:1]
        for name, ss in stages[1:]:
            prev_name, prev = merged[-1]
            if _pack(gpus, [c for c, _ in deployments(eff, prev + ss).values()]) is not None:
                merged[-1] = (f"{prev_name}+{name}", prev + ss)
            else:
                merged.append((name, ss))
        stages = merged

    # 5–6. Pack each group, then add replicas one at a time where demand per replica is highest.
    decisions: dict[Slot, SlotDecision] = {}
    warnings: list[str] = []
    for _, ss in stages:
        deps = deployments(eff, ss)
        packed = _pack(gpus, [c for c, _ in deps.values()])
        assert packed is not None
        cluster, where = packed
        reps = _replicas(cluster, deps, where, workload)

        for vid, (c, slots) in deps.items():
            total = gpus[where[vid][0]].total if where[vid] else 1.0
            fraction = _ceil2(c.per_gpu / total)
            main = SlotDecision(variant=vid, replicas=reps[vid])
            if c.variant.engine == "vllm":
                main.gpus_per_replica = c.tp
                main.context = c.context
                main.gpu_memory_utilization = fraction
                main.gpu_fraction = fraction if c.tp == 1 else None
                assert c.variant.context and c.context
                default = c.variant.context.default
                if c.context < default:
                    warnings.append(f"{slots[0]} context reduced {default} -> {c.context}")
            elif c.variant.engine == "actor":
                main.gpu_fraction = fraction
            for k, s in enumerate(slots):
                d = main if k == 0 else SlotDecision(variant=vid)
                others = [o for o in slots if o is not s]
                decisions[s] = d.model_copy(update={"shared_with": others or None})
    if Slot.JUDGE_LLM in decisions:
        decisions[Slot.JUDGE_LLM].independent_family = not judge_reuses

    return Plan(
        inventory_fingerprint=inventory.fingerprint,
        catalog_sha256=catalog.sha256,
        objective=objective,
        pins=pins,
        mode=Mode.RESIDENT if resident else Mode.STAGED,
        groups=[StageGroup(name=n, slots=sorted(ss, key=list(Slot).index)) for n, ss in stages],
        decisions={s: decisions[s] for s in Slot if s in decisions},
        skipped_slots=skipped,
        warnings=warnings + [f"no hardware for {s}" for s in skipped],
    )


app = typer.Typer()


@app.callback(invoke_without_command=True)
def plan_cmd(
    objective: Objective = Objective.QUALITY,
    simulate: Annotated[Path | None, typer.Option(help="HardwareInventory JSON")] = None,
    units: Annotated[int, typer.Option(help="Work units assumed per slot")] = 100,
    catalog: Path = Path("config/catalog.yaml"),
) -> None:
    """Show the Plan for this hardware, or for a simulated inventory."""
    inv = HardwareInventory.model_validate_json(simulate.read_text()) if simulate else probe()
    try:
        vllm: str | None = version("vllm")
    except PackageNotFoundError:
        vllm = None
    cat = validate(load_catalog(catalog), vllm, licenses=None)
    pins = {s: os.environ.get(f"NIP_PIN_{s.upper()}", "") for s in Slot}
    try:
        p = plan(
            inv,
            cat,
            {s: units for s in Slot},
            objective,
            {s: v for s, v in pins.items() if v},
            stub=os.environ.get("NIP_PROFILE") == "cpu",
            gpu_mem_utilization=float(os.environ.get("NIP_GPU_MEM_UTILIZATION", "0.90")),
        )
    except PlanError as e:
        typer.echo(f"{PlanError.code}: {e}", err=True)
        raise typer.Exit(1) from e
    typer.echo(p.model_dump_json(indent=2, exclude_none=True))
