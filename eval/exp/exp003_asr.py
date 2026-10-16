"""EXP-003: faster-whisper large-v3-int8 vs large-v3-turbo-int8 on English film dialogue.

    uv run python -m eval.exp.exp003_asr run [--runs 3] [--config novad-p50]

Sintel + Tears of Steel, WER against the normalized official English SRT (ruling R6: the SRT is the
reference, so absolute WER is inflated for both variants alike). Each (variant, run) is a fresh
process holding `data/gpu.lock`: model load, then both films; RTF = transcribe wall seconds / audio
seconds (model load excluded, reported separately); peak VRAM = device-wide NVML peak minus the
idle level read just before the model loads. Run 1's transcripts are kept in data/exp003/<variant>/
(frames from the probed fps) and reused by EXP-004. MLflow: experiment "exp003-asr".
"""

import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

import typer

from nip.ingest.media import probe
from nip.ingest.subtitles import parse_srt
from nip.timeline.align import normalize

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "exp003"
TRACKING_URI = f"sqlite:///{(ROOT / 'data' / 'mlflow' / 'mlflow.db').as_posix()}"
LOCK = ROOT / "data" / "gpu.lock"
VARIANTS = ["faster-whisper-large-v3-int8", "faster-whisper-large-v3-turbo-int8"]
FILMS = {
    "sintel": ("data/corpus/sintel/Sintel.2010.1080p.mkv", "data/corpus/sintel/en_sintel_en.srt"),
    "tears-of-steel": (
        "data/corpus/tears-of-steel/tears_of_steel_720p.mov",
        "data/corpus/tears-of-steel/en_TOS-en.srt",
    ),
}
# Decoding configurations (kwargs of FasterWhisperASR; `min_prob` is explicit everywhere because the
# client's default is the shipped one). SHIPPED is what 2.5 defaults to; the others are what was
# tried and why it was replaced (EXP-003 notes). Round 1 (temperature 0.0, no fallback) came first;
# the `fb*` arms use faster-whisper's own decoding defaults: temperature fallback
# (0, .2, ..., 1.0) retried on compression_ratio > 2.4 or avg_logprob < -1.0, no_speech 0.6.
FALLBACK = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
CONFIGS: dict[str, dict[str, Any]] = {
    "vad": {"vad": True, "min_prob": 0.0},
    "vad03": {"vad": True, "min_prob": 0.0, "vad_parameters": {"threshold": 0.3}},
    "novad": {"vad": False, "min_prob": 0.0},
    "novad-hst": {"vad": False, "min_prob": 0.0, "hallucination_silence_threshold": 2.0},
    "novad-p50": {"vad": False, "min_prob": 0.5},
    "fb": {"vad": False, "min_prob": 0.0, "temperature": FALLBACK},
    "fb-cond": {
        "vad": False,
        "min_prob": 0.0,
        "temperature": FALLBACK,
        "condition_on_previous_text": True,
    },
    "fb-p50": {"vad": False, "min_prob": 0.5, "temperature": FALLBACK},
}
SHIPPED = "fb-p50"  # round-2 decision (notes); config/pipeline.yaml records the same
app = typer.Typer(no_args_is_help=True)


def _sfx(config: str) -> str:
    return f".{config}"


def _label(variant: str, config: str) -> str:
    """MLflow variant tag: the model alone for the shipped config, else "<model>+<config>"."""
    short = variant.removeprefix("faster-whisper-")
    return short if config == SHIPPED else f"{short}+{config}"


def wer(ref: list[str], hyp: list[str]) -> tuple[float, int, int, int, int]:
    """(WER, substitutions, deletions, insertions, reference words) by word-level Levenshtein."""
    prev = [(j, 0, 0, j) for j in range(len(hyp) + 1)]  # (cost, S, D, I)
    for i, r in enumerate(ref, 1):
        cur = [(i, 0, i, 0)]
        for j, h in enumerate(hyp, 1):
            c, s, d, n = prev[j - 1]
            sub = (c + (r != h), s + (r != h), d, n)
            dele = (prev[j][0] + 1, prev[j][1], prev[j][2] + 1, prev[j][3])
            ins = (cur[j - 1][0] + 1, cur[j - 1][1], cur[j - 1][2], cur[j - 1][3] + 1)
            cur.append(min(sub, dele, ins))
        prev = cur
    c, s, d, n = prev[-1]
    return c / max(len(ref), 1), s, d, n, len(ref)


def reference(film: str) -> list[str]:
    p = parse_srt((ROOT / FILMS[film][1]).read_bytes())
    assert p.data is not None
    return [t for c in p.data.cues for t in normalize(c.text)]


@contextmanager
def gpu_lock(purpose: str) -> Iterator[None]:
    """data/gpu.lock (atomic mkdir + owner.txt); polls every 60 s while another job holds it."""
    while True:
        try:
            LOCK.mkdir(parents=True)
            break
        except FileExistsError:
            print(f"gpu.lock held ({(LOCK / 'owner.txt').read_text().strip()}); waiting 60 s")
            time.sleep(60)
    (LOCK / "owner.txt").write_text(f"2.5 {purpose} {time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
    try:
        yield
    finally:
        (LOCK / "owner.txt").unlink(missing_ok=True)
        LOCK.rmdir()


class VramPeak:
    """Peak device-wide used memory (MiB) over a `with` block, sampled every 20 ms via NVML."""

    def __init__(self) -> None:
        import pynvml

        pynvml.nvmlInit()
        self.nv = pynvml
        self.h = pynvml.nvmlDeviceGetHandleByIndex(0)
        self.peak = 0.0
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)

    def used(self) -> float:
        return float(self.nv.nvmlDeviceGetMemoryInfo(self.h).used) / 2**20

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, self.used())
            time.sleep(0.02)

    def __enter__(self) -> "VramPeak":
        self._t.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._t.join()


def audio(film: str) -> Path:
    """16 kHz mono wav of the film's first audio stream, cached under data/exp003."""
    from nip.timeline.asr import extract_audio

    wav = OUT / f"{film}.wav"
    if not wav.exists():
        OUT.mkdir(parents=True, exist_ok=True)
        extract_audio(ROOT / FILMS[film][0], wav)
    return wav


@app.command("run-one")
def run_one(variant: str, run: int, config: str = SHIPPED, out: Path = OUT) -> None:
    """Worker: one model load, both films; writes <out>/<variant>/run<N>.json (+ transcripts)."""
    from nip.runtime.clients.asr import FasterWhisperASR
    from nip.timeline.asr import to_frames

    wavs = {f: audio(f) for f in FILMS}
    with VramPeak() as vram:
        idle = vram.used()
        t = time.perf_counter()
        model = FasterWhisperASR(variant, **CONFIGS[config])
        res: dict[str, Any] = {"variant": variant, "run": run, "config": config}
        res["load_s"] = time.perf_counter() - t
        for film, wav in wavs.items():
            secs = wav.stat().st_size / 32000  # 16 kHz * 2 bytes
            t = time.perf_counter()
            segs = model.transcribe(wav, "en")
            wall = time.perf_counter() - t
            hyp = [t for s in segs for w in s.words for t in normalize(w.w)]
            w_, s_, d_, i_, n_ = wer(reference(film), hyp)
            res[film] = {
                "audio_s": secs,
                "wall_s": wall,
                "rtf": wall / secs,
                "wer": w_,
                "sub": s_,
                "del": d_,
                "ins": i_,
                "ref_words": n_,
                "hyp_words": len(hyp),
            }
            if run == 1:
                fps = probe(ROOT / FILMS[film][0]).fps
                d = out / variant
                d.mkdir(parents=True, exist_ok=True)
                tr = [asdict(s) for s in to_frames(segs, fps, "en")]
                (d / f"{film}{_sfx(config)}.transcript.json").write_text(json.dumps(tr))
        res["peak_vram_mib"] = vram.peak - idle
        res["idle_vram_mib"] = idle
    d = out / variant
    d.mkdir(parents=True, exist_ok=True)
    (d / f"run{run}{_sfx(config)}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res))


def _log(res: dict[str, Any], exp: str, variant: str) -> None:
    import mlflow

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("exp003-asr")
    kinds = ("sub", "del", "ins")
    n_ref = sum(res[f]["ref_words"] for f in FILMS)
    errs = sum(res[f][k] for f in FILMS for k in kinds)
    audio_s, wall = sum(res[f]["audio_s"] for f in FILMS), sum(res[f]["wall_s"] for f in FILMS)
    m = {
        "wer": errs / n_ref,
        "sub_del_rate": (errs - sum(res[f]["ins"] for f in FILMS))
        / n_ref,  # WER without insertions
        "rtf": wall / audio_s,
        "peak_vram_mib": res["peak_vram_mib"],
        "load_s": res["load_s"],
    }
    m |= {k: float(sum(res[f][k] for f in FILMS)) for k in kinds}
    for f in FILMS:
        m |= {f"wer_{f}": res[f]["wer"], f"rtf_{f}": res[f]["rtf"]}
        m |= {f"{k}_{f}": float(res[f][k]) for k in kinds}
        m[f"sub_del_rate_{f}"] = (res[f]["sub"] + res[f]["del"]) / res[f]["ref_words"]
    with mlflow.start_run(run_name=f"{exp}-{variant}-{res['run']}"):
        mlflow.set_tags(
            {"exp": exp, "variant": variant, "seed": str(res["run"]), "labeller": "official-en-srt"}
        )
        mlflow.log_params({"config": res["config"], "model": res["variant"]})
        mlflow.log_metrics(m)


def _clear(exp: str, variant: str) -> None:
    """Delete earlier MLflow runs with these tags so re-running a config does not duplicate."""
    from mlflow import MlflowClient

    client = MlflowClient(TRACKING_URI)
    e = client.get_experiment_by_name("exp003-asr")
    for r in client.search_runs(
        [e.experiment_id] if e else [],
        filter_string=f"tags.exp = '{exp}' and tags.variant = '{variant}'",
    ):
        client.delete_run(r.info.run_id)


@app.command()
def relog(runs: int = 3) -> None:
    """Re-log every saved run JSON (adds the per-film sub/del/ins counts to older MLflow runs)."""
    for config in CONFIGS:
        for variant in VARIANTS:
            files = [OUT / variant / f"run{n}{_sfx(config)}.json" for n in range(1, runs + 1)]
            if all(f.exists() for f in files):
                _clear("EXP-003", _label(variant, config))
                for f in files:
                    _log(json.loads(f.read_text()), "EXP-003", _label(variant, config))


@app.command()
def run(runs: int = 3, config: str = SHIPPED) -> None:
    """Both variants x `runs` fresh-process runs of one decoding config under data/gpu.lock,
    logged to MLflow (variant label: see `_label`)."""
    with gpu_lock(f"exp003 whisper {config}"):
        for variant in VARIANTS:
            _clear("EXP-003", _label(variant, config))
            for n in range(1, runs + 1):
                cmd = [sys.executable, "-m", "eval.exp.exp003_asr", "run-one", variant, str(n)]
                subprocess.run(
                    [*cmd, "--config", config],
                    check=True,
                    env=dict(os.environ, HF_HOME=str(ROOT / "models" / "hf")),
                )
                f = OUT / variant / f"run{n}{_sfx(config)}.json"
                _log(json.loads(f.read_text()), "EXP-003", _label(variant, config))


if __name__ == "__main__":
    app()
