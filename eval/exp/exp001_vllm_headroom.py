"""EXP-001: vLLM memory headroom on the laptop (docs/experiments.md).

qwen3.5-4b-awq at 8k context, started through runtime.serving (Ray Serve + `vllm serve`), once per
trial: gpu_memory_utilization 0.75 / 0.80 / 0.83 / 0.86, and an exact KV budget
(`--kv-cache-memory-bytes` = the planner's KV estimate). Every trial is logged to MLflow
(experiment "EXP-001", tag exp=EXP-001, variant=<setting>).

  host:      uv run python -m eval.exp.exp001_vllm_headroom drive --trials 10
             (waits until no other compute process holds the GPU, then runs each trial in ray-head)
  ray-head:  python3 -m eval.exp.exp001_vllm_headroom trial --setting gmu-0.80 --trial 1
             (--setting plan: probe -> planner -> serving.apps, the shipped path with no overrides)
  host:      uv run python -m eval.exp.exp001_vllm_headroom table   (results from MLflow)
Stack:  docker compose -f compose.yaml -f eval/exp/exp001.compose.yaml up -d --wait ray-head mlflow
"""

import json
import os
import re
import statistics
import subprocess
import threading
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, Any

import typer

from nip.contracts import Slot, SlotDecision
from nip.runtime.catalog import load_catalog

app = typer.Typer(no_args_is_help=True)

EXP = "EXP-001"
VARIANT = "qwen3.5-4b-awq"
CONTEXT = 8192
SETTINGS = ["gmu-0.75", "gmu-0.80", "gmu-0.83", "gmu-0.86", "kv-planner"]
KV_GATE_GMU = 0.5  # with --kv-cache-memory-bytes, gmu only gates vLLM's free-memory check
COMPOSE = ["docker", "compose", "-f", "compose.yaml", "-f", "eval/exp/exp001.compose.yaml"]
PROMPTS = [
    "Summarize the plot of a heist film in three sentences.",
    "List five continuity errors a script supervisor watches for.",
    "Explain what a subtitle reading speed limit is.",
    "Describe a rainy night street scene for a screenplay.",
    "What is the difference between a shot and a scene?",
    "Write a short dialogue between a detective and a witness.",
    "Explain drop-frame timecode to a new editor.",
    "Give three tips for translating jokes in subtitles.",
]
MAX_TOKENS = 128  # with ignore_eos every request generates exactly this many tokens


# The planner's KV estimate when the 66 trials ran (60 MiB/1k x 8k x 2 sequences = 0.94 GiB). Fixed
# here: the catalog now holds the measured 44.6 MiB/1k, which would change the variant's meaning.
KV_PLANNER_BYTES = 1_006_632_960


class _Vram:
    """NVML used/free MiB (GPU 0) and a background peak sampler."""

    def __init__(self) -> None:
        import pynvml

        self.nvml = pynvml
        pynvml.nvmlInit()
        self.h = pynvml.nvmlDeviceGetHandleByIndex(0)
        self.peak, self._stop = 0, threading.Event()

    def read(self) -> tuple[int, int]:
        m = self.nvml.nvmlDeviceGetMemoryInfo(self.h)
        return int(m.used) // 2**20, int(m.free) // 2**20

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, self.read()[0])
            time.sleep(0.2)

    def start(self) -> None:
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self) -> int:
        self._stop.set()
        return self.peak


def parse_log(text: str) -> dict[str, float]:
    """Numbers from vLLM's startup log."""
    out: dict[str, float] = {}
    pats = {
        "kv_cache_tokens": r"KV cache size: ([\d,]+) tokens",
        "max_concurrency_8k": r"Maximum concurrency for [\d,]+ tokens per request: ([\d.]+)x",
        "weights_gib": r"Model loading took ([\d.]+) GiB",
        "kv_cache_gib": r"Available KV cache memory: (-?[\d.]+) GiB",
        # gmu path only: vLLM's own accounting, unaffected by the desktop's VRAM drift
        "consumed_gib": r"Actual usage is ([\d.]+) GiB for consumed memory",
        "activation_gib": r"([\d.]+) GiB for peak activation",
        "cuda_free_gib_start": r"(?:Free memory on device \(|Initial free memory )([\d.]+)",
    }
    for k, p in pats.items():
        if m := re.search(p, text):
            out[k] = float(m.group(1).replace(",", ""))
    return out


def classify(text: str) -> str:
    if "less than desired GPU memory utilization" in text:
        return "free_memory_check"
    if "No available memory for the cache blocks" in text:
        return "no_kv_memory"  # KV budget <= 0
    if "To serve at least one request" in text:
        return "kv_below_one_seq"  # KV budget < one max_model_len sequence
    if re.search(r"out of memory|OutOfMemoryError", text, re.I):
        return "oom"
    if "not healthy in" in text:
        return "timeout"
    return "other"


def _bench(base: str) -> float:
    """Tokens/s over the fixed prompt set, all prompts in flight at once."""

    def one(prompt: str) -> int:
        body = {
            "model": VARIANT,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": MAX_TOKENS,
            "temperature": 0,
            "ignore_eos": True,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        req = urllib.request.Request(
            f"{base}/models/{VARIANT}/v1/chat/completions",
            json.dumps(body).encode(),
            {"content-type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600) as r:
            return int(json.load(r)["usage"]["completion_tokens"])

    t = time.monotonic()
    with ThreadPoolExecutor(len(PROMPTS)) as ex:
        tokens = sum(ex.map(one, PROMPTS))
    return tokens / (time.monotonic() - t)


@app.command()
def trial(
    setting: Annotated[str, typer.Option()],
    trial: Annotated[int, typer.Option()],
    pilot: Annotated[
        bool, typer.Option(help="tag exp=EXP-001-pilot (kept out of the table)")
    ] = False,
    note: Annotated[str, typer.Option(help="condition suffix for the variant tag")] = "",
) -> None:
    """One start/bench/teardown inside ray-head; logs an MLflow run."""
    import mlflow

    from nip.runtime.planner import plan
    from nip.runtime.probe import probe
    from nip.runtime.serving import (
        App,
        ServingError,
        apps,
        deploy,
        ray_serve,
        teardown,
        vllm_args,
    )

    catalog = load_catalog()
    v = next(v for v in catalog.variants if v.id == VARIANT)
    if setting == "plan":  # the shipped path: probe -> planner -> serving.apps, nothing overridden
        inv = probe()
        p = plan(inv, catalog, {Slot.TEXT_LLM: 1, Slot.VLM: 1})
        if Slot.TEXT_LLM in p.skipped_slots:
            typer.echo(f"planner skipped text_llm at this free VRAM: {p.warnings}", err=True)
            raise typer.Exit(1)
        [a] = apps(p, catalog, inv, p.groups[0].slots)
        d = p.decisions[Slot.TEXT_LLM]
        assert d.gpu_memory_utilization and d.context
        gmu, context, kv_bytes = d.gpu_memory_utilization, d.context, d.kv_cache_bytes
        args = list(a.vllm_args)
    else:
        kv = setting == "kv-planner"
        gmu, context = KV_GATE_GMU if kv else float(setting.removeprefix("gmu-")), CONTEXT
        kv_bytes = KV_PLANNER_BYTES if kv else None
        d = SlotDecision(
            variant=VARIANT,
            replicas=1,
            gpus_per_replica=1,
            context=context,
            gpu_memory_utilization=gmu,
            gpu_fraction=gmu,
            kv_cache_bytes=kv_bytes,
        )
        vlm = SlotDecision(
            variant=VARIANT, max_pixels=v.max_pixels, images_per_prompt=v.images_per_prompt
        )
        args = vllm_args(v, d, vlm, eager=True)
        a = App(VARIANT, (Slot.TEXT_LLM, Slot.VLM), 1, gmu, tuple(args))

    serve = ray_serve()
    vram = _Vram()
    used0, free0 = vram.read()
    metrics: dict[str, float] = {"free_mib_start": free0, "used_mib_start": used0}
    tags = {
        "exp": EXP + "-pilot" * pilot,
        "variant": setting + (f"@{note}" if note else ""),
        "trial": str(trial),
        "checkpoint": v.repo or "",
    }
    log_dir = Path(os.environ.get("NIP_VLLM_LOG_DIR", "/tmp/nip-vllm"))
    before = set(log_dir.glob("*.log")) if log_dir.exists() else set()
    vram.start()
    try:
        metrics["load_s"] = deploy([a], serve)[a.name]
        metrics["started"] = 1
    except ServingError as e:
        metrics["started"] = 0
        tags["error"] = str(e)[-4000:]
    if metrics["started"]:
        try:
            metrics["tokens_per_s"] = round(_bench("http://127.0.0.1:8000"), 1)
        except Exception as e:  # a failed benchmark must not skip teardown and logging
            tags["bench_error"] = repr(e)[-2000:]
    try:
        metrics["unload_s"] = teardown([a], serve, idle_mib=used0)
        metrics["returned_to_idle"] = 1
    except ServingError as e:
        metrics["returned_to_idle"] = 0
        tags["teardown_error"] = str(e)
    peak = vram.stop()
    metrics["vram_after_mib"] = vram.read()[0]
    metrics["peak_used_mib"] = peak
    metrics["peak_mib"] = peak - used0  # our share: device peak minus the desktop's at start
    new = sorted(set(log_dir.glob("*.log")) - before, key=lambda p: p.stat().st_mtime)
    text = new[-1].read_text(errors="replace") if new else ""
    metrics |= parse_log(text)
    if not metrics["started"]:
        tags["failure"] = classify(text + tags.get("error", ""))

    mlflow.set_tracking_uri(os.environ.get("NIP_MLFLOW_TRACKING_URI", "http://mlflow:5000"))
    mlflow.set_experiment(EXP)
    with mlflow.start_run(run_name=f"{setting}-t{trial}") as r:
        mlflow.set_tags(tags)
        mlflow.log_params(
            {
                "gpu_memory_utilization": gmu,
                "max_model_len": context,
                "kv_cache_memory_bytes": kv_bytes or "none",
                "vllm_args": " ".join(args),
            }
        )
        mlflow.log_metrics(metrics)
        if new:
            mlflow.log_artifact(str(new[-1]))
    typer.echo(json.dumps({"run": r.info.run_id, **tags, **metrics})[:600])


def other_compute() -> list[str]:
    """Compute-only (type C) GPU processes on the Windows host (`nvidia-smi` table)."""
    out = subprocess.run(["nvidia-smi"], capture_output=True, text=True).stdout
    return re.findall(r"\|\s+\d+\s+\S+\s+\S+\s+\d+\s+C\s+(\S+)", out)


@app.command()
def drive(
    trials: int = 10,
    settings: Annotated[str, typer.Option(help="comma-separated")] = ",".join(SETTINGS),
    start: int = 1,
) -> None:
    """Host: rounds of one trial per setting (interleaved, so desktop VRAM drift hits all alike)."""
    for t in range(start, trials + 1):
        for s in settings.split(","):
            waited = 0
            while procs := other_compute():
                typer.echo(f"GPU busy ({procs}); waiting")
                time.sleep(30)
                waited += 30
            typer.echo(f"== {s} trial {t} (waited {waited}s) {time.strftime('%H:%M:%S')}")
            cmd = [
                *COMPOSE,
                "exec",
                "-T",
                "ray-head",
                "python3",
                "-m",
                "eval.exp.exp001_vllm_headroom",
                "trial",
                "--setting",
                s,
                "--trial",
                str(t),
            ]
            subprocess.run(cmd, check=False)


def _ms(vals: list[float], fmt: str = ".0f") -> str:
    if not vals:
        return "—"
    m = statistics.fmean(vals)
    return f"{m:{fmt}} ± {statistics.stdev(vals):{fmt}}" if len(vals) > 1 else f"{m:{fmt}}"


@app.command()
def backfill(tracking_uri: str = "http://127.0.0.1:5000") -> None:
    """Re-parse each run's vLLM log artifact and log startup numbers the run lacks (parse_log
    gained fields after the first trials)."""
    import tempfile

    from mlflow import MlflowClient

    c = MlflowClient(tracking_uri)
    ids = [e.experiment_id for e in c.search_experiments()]
    for r in c.search_runs(ids, filter_string=f"tags.exp = '{EXP}'", max_results=1000):
        logs = [a.path for a in c.list_artifacts(r.info.run_id) if a.path.endswith(".log")]
        if not logs:
            continue
        with tempfile.TemporaryDirectory() as d:
            text = Path(c.download_artifacts(r.info.run_id, logs[0], d)).read_text(errors="replace")
        for k, v in parse_log(text).items():
            if k not in r.data.metrics:
                c.log_metric(r.info.run_id, k, v)
        if not r.data.metrics.get("started"):
            c.set_tag(r.info.run_id, "failure", classify(text))


@app.command()
def table(tracking_uri: str = "http://127.0.0.1:5000") -> None:
    """Markdown results table from the MLflow runs tagged exp=EXP-001."""
    from mlflow import MlflowClient

    c = MlflowClient(tracking_uri)
    ids = [e.experiment_id for e in c.search_experiments()]
    runs = c.search_runs(ids, filter_string=f"tags.exp = '{EXP}'", max_results=1000)
    by: dict[str, list[Any]] = defaultdict(list)
    for r in runs:
        by[r.data.tags["variant"]].append(r)
    cols = [s for s in SETTINGS if s in by] + sorted(set(by) - set(SETTINGS))

    def m(rs: list[Any], k: str, ok: bool = True) -> list[float]:
        return [
            r.data.metrics[k]
            for r in rs
            if k in r.data.metrics and (not ok or r.data.metrics.get("started"))
        ]

    rows = [
        [
            "Successful starts",
            *(f"{int(sum(m(by[s], 'started', False)))}/{len(by[s])}" for s in cols),
        ],
        ["Free VRAM at start, MiB", *(_ms(m(by[s], "free_mib_start", False)) for s in cols)],
        ["Peak GPU memory (ours), MiB", *(_ms(m(by[s], "peak_mib")) for s in cols)],
        ["Peak device used, MiB", *(_ms(m(by[s], "peak_used_mib")) for s in cols)],
        [
            "CUDA free at start (vLLM), GiB",
            *(_ms(m(by[s], "cuda_free_gib_start"), ".2f") for s in cols),
        ],
        ["vLLM weights+non-torch, GiB", *(_ms(m(by[s], "consumed_gib"), ".2f") for s in cols)],
        ["vLLM peak activation, GiB", *(_ms(m(by[s], "activation_gib"), ".2f") for s in cols)],
        ["vLLM KV cache, GiB", *(_ms(m(by[s], "kv_cache_gib"), ".2f") for s in cols)],
        ["KV cache, tokens", *(_ms(m(by[s], "kv_cache_tokens")) for s in cols)],
        ["Max concurrent seqs at 8k", *(_ms(m(by[s], "max_concurrency_8k"), ".2f") for s in cols)],
        ["Tokens/s (8 prompts x 128)", *(_ms(m(by[s], "tokens_per_s"), ".1f") for s in cols)],
        ["Load s", *(_ms(m(by[s], "load_s"), ".1f") for s in cols)],
        [
            "Back to idle after teardown",
            *(f"{int(sum(m(by[s], 'returned_to_idle', False)))}/{len(by[s])}" for s in cols),
        ],
        ["VRAM after teardown, MiB", *(_ms(m(by[s], "vram_after_mib", False)) for s in cols)],
        [
            "Failures",
            *(
                ", ".join(sorted({r.data.tags.get("failure", "") for r in by[s]} - {""})) or "—"
                for s in cols
            ),
        ],
        ["MLflow runs", *(" ".join(r.info.run_id[:8] for r in by[s]) for s in cols)],
    ]
    typer.echo(f"| Metric | {' | '.join(cols)} |\n|{'---|' * (len(cols) + 1)}")
    typer.echo("\n".join(f"| {' | '.join(r)} |" for r in rows))


if __name__ == "__main__":
    app()
