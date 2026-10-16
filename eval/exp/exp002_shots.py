"""EXP-002: TransNetV2 vs PySceneDetect (ContentDetector, AdaptiveDetector) on real film cuts.

Re-run, in this order (all MLflow runs go to data/mlflow/mlflow.db, experiment "exp002-shots"):
  run --repeat 3   defaults of the three variants on both films, timed 3x (tag exp=EXP-002-<film>)
  sweep            threshold grids on Sintel + the best setting per family ("<family>-tuned")
  split            2-fold held-out check ("<family>-heldout"; reads the sweep results from data/)
  resize-test      TorchCodec vs ffmpeg 48x27 resize filters (tag exp=EXP-002-sintel-resize)
  table --exp EXP-002-sintel   comparison table (eval.report.compare_table) for everything above
  candidates       low-threshold detector union used to seed the labels (label_sheets.py draws it)
Each (film, variant) is measured in a fresh subprocess so peak RAM is that run's own.
Cuts are 0-based frame indexes of the first frame of the new shot; results land in data/exp002/.
Metric names follow eval.metrics.evaluate() so eval.report.compare_table reads them, but here
`shown/*` is the headline with masked windows (dissolves, credits...) dropped, `unmasked/*` is not.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Annotated, Any

import typer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "exp002"
TRACKING_URI = f"sqlite:///{(ROOT / 'data' / 'mlflow' / 'mlflow.db').as_posix()}"
FILMS = {
    "sintel": ROOT / "data/corpus/sintel/Sintel.2010.1080p.mkv",
    "tears-of-steel": ROOT / "data/corpus/tears-of-steel/tears_of_steel_720p.mov",
}
LABELS = ROOT / "eval/labeling/labels/sintel_cuts.provisional.json"
MASKS = ROOT / "eval/labeling/labels/sintel_cuts.provisional.masks.json"
TOL = 2
SCOPE = "check/shot.cut"
app = typer.Typer(no_args_is_help=True)


# ---- scoring -------------------------------------------------------------------------------
def match_cuts(
    pred: list[int], truth: list[int], tol: int = TOL
) -> tuple[int, int, int, list[int]]:
    """One-to-one match of cut lists within +-tol frames.

    Returns (tp, fp, fn, signed offsets pred-truth of the matches). A single sweep over both
    sorted lists gives a maximum matching when all windows have the same width.
    """
    p, t = sorted(pred), sorted(truth)
    i = j = 0
    offs: list[int] = []
    while i < len(p) and j < len(t):
        if abs(p[i] - t[j]) <= tol:
            offs.append(p[i] - t[j])
            i += 1
            j += 1
        elif p[i] < t[j]:
            i += 1
        else:
            j += 1
    tp = len(offs)
    return tp, len(p) - tp, len(t) - tp, offs


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return prec, rec, 2 * prec * rec / (prec + rec) if prec + rec else 0.0


def cut_metrics(
    pred: list[int],
    truth: list[int],
    tol: int = TOL,
    mask: list[tuple[int, int]] | None = None,
) -> dict[str, float]:
    """Metric dict named like eval.metrics.evaluate() so eval.report.compare_table reads it.

    `shown/*` is the headline: cuts inside `mask` windows (dissolves, ambiguous spots, credits)
    are dropped from predictions and labels first. `unmasked/*` scores everything.
    """
    out: dict[str, float] = {}
    mp, mt = (apply_mask(pred, mask), apply_mask(truth, mask)) if mask else (pred, truth)
    for name, (p, t) in {"shown": (mp, mt), "unmasked": (pred, truth)}.items():
        tp, fp, fn, offs = match_cuts(p, t, tol)
        prec, rec, f1 = _prf(tp, fp, fn)
        scopes = ("all", SCOPE) if name == "shown" else ("all",)
        for scope in scopes:
            for k, v in dict(precision=prec, recall=rec, f1=f1, tp=tp, fp=fp, fn=fn).items():
                out[f"{name}/{k}/{scope}"] = float(v)
        if name == "shown":
            out["mean_abs_offset_frames"] = sum(map(abs, offs)) / len(offs) if offs else 0.0
            for t_ in (0, 5):  # tolerance sensitivity
                out[f"shown/f1_tol{t_}/all"] = _prf(*match_cuts(p, t, t_)[:3])[2]
    return out


def load_truth(path: Path = LABELS) -> list[int]:
    """Cut frames from a cuts label file (eval/labeling/README.md: one JSON object)."""
    return sorted(json.loads(path.read_text(encoding="utf-8"))["cuts"])


def load_mask(path: Path = MASKS) -> list[tuple[int, int]]:
    """Inclusive frame windows (dissolves, ambiguous spots, credits) where cuts are unlabelled."""
    return [(r["start"], r["end"]) for r in json.loads(path.read_text(encoding="utf-8"))["regions"]]


def apply_mask(cuts: list[int], mask: list[tuple[int, int]]) -> list[int]:
    """Drop cuts that fall inside a masked window (applied to predictions and labels alike)."""
    return [c for c in cuts if not any(a <= c <= b for a, b in mask)]


# ---- detectors -----------------------------------------------------------------------------
def pyscenedetect_cuts(video: Path, detector: Any) -> tuple[list[int], int]:
    from scenedetect import detect

    scenes = detect(str(video), detector, show_progress=False)
    return [s.frame_num for s, _ in scenes[1:]], scenes[-1][1].frame_num


def make_detector(variant: str, **kw: Any) -> Any:
    from scenedetect import AdaptiveDetector, ContentDetector

    return {"content": ContentDetector, "adaptive": AdaptiveDetector}[variant](**kw)


def _peak_rss_mb() -> float:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        names = (
            "PeakWorkingSetSize WorkingSetSize QuotaPeakPagedPoolUsage QuotaPagedPoolUsage "
            "QuotaPeakNonPagedPoolUsage QuotaNonPagedPoolUsage PagefileUsage PeakPagefileUsage"
        ).split()

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in names
            ]

        pmc = PMC()
        pmc.cb = ctypes.sizeof(pmc)
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        gpmi = ctypes.WinDLL("psapi").GetProcessMemoryInfo
        gpmi.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        gpmi(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return float(pmc.PeakWorkingSetSize) / 2**20
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def run_one(film: str, variant: str, out: Path, **kw: Any) -> dict[str, Any]:
    """Measure one detector on one film in this process; write <out>/<film>/<variant>.json.

    variant "picture" = TransNetV2 plus keyframe extraction (the whole part-A stage).
    """
    video = FILMS[film]
    from nip.ingest.media import probe

    info = probe(video)
    res: dict[str, Any] = {"film": film, "variant": variant, "params": kw}
    (out / film).mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    if variant in ("transnetv2", "picture"):
        import numpy as np
        import torch

        from nip.timeline.shots import cuts_from_predictions, load_model, small_frames

        t = time.perf_counter()
        frames = small_frames(video)
        res["decode_s"] = time.perf_counter() - t
        t = time.perf_counter()
        model = load_model()
        res["model_load_s"] = time.perf_counter() - t
        t = time.perf_counter()
        single, _ = model.predict_frames(frames.to(model.device), quiet=True)
        torch.cuda.synchronize()
        res["model_s"] = time.perf_counter() - t
        probs = single.numpy()
        res["n_frames"] = len(frames)
        res["decode_fps"] = len(frames) / res["decode_s"]
        res["cuts"] = cuts_from_predictions(probs, kw.get("threshold", 0.5))
        res["peak_vram_alloc_mb"] = torch.cuda.max_memory_allocated() / 2**20
        res["peak_vram_reserved_mb"] = torch.cuda.max_memory_reserved() / 2**20
        np.save(out / film / "transnetv2_probs.npy", probs)
        if variant == "picture":
            from nip.timeline.keyframes import extract_keyframes
            from nip.timeline.picture import timeline_config
            from nip.timeline.shots import shots_from_cuts

            shots = shots_from_cuts(res["cuts"], len(frames))
            t = time.perf_counter()
            kf = extract_keyframes(
                video,
                shots,
                info.fps,
                out / film / "keyframes",
                **timeline_config()["keyframes"],
            )
            res["keyframes_s"] = time.perf_counter() - t
            res["n_shots"], res["n_keyframes"] = len(shots), len(kf)
    else:
        res["cuts"], res["n_frames"] = pyscenedetect_cuts(video, make_detector(variant, **kw))
    res["wall_s"] = time.perf_counter() - t0
    res["video_s"] = float(info.duration_frames / info.fps)
    res["probe_frames"] = info.duration_frames
    res["s_per_video_min"] = res["wall_s"] / (res["video_s"] / 60)
    res["peak_rss_mb"] = _peak_rss_mb()
    (out / film / f"{variant}.json").write_text(json.dumps(res), encoding="utf-8")
    return res


@app.command("run-one")
def run_one_cmd(film: str, variant: str, params: str = "{}", out: Path = OUT) -> None:
    """Worker: one detector on one film (JSON params), result written under --out."""
    r = run_one(film, variant, out, **json.loads(params))
    typer.echo(json.dumps({k: v for k, v in r.items() if k != "cuts"}) + f" cuts={len(r['cuts'])}")


def _spawn(film: str, variant: str, params: dict[str, Any], tag: str, out: Path) -> dict[str, Any]:
    """Run the worker in a fresh process (own peak RAM); `tag` names the result directory."""
    env = dict(os.environ, MLFLOW_DISABLE_AGENT_HINT="1")
    d = out / "runs" / tag
    cmd = [sys.executable, "-m", "eval.exp.exp002_shots", "run-one", film, variant]
    subprocess.run([*cmd, "--params", json.dumps(params), "--out", str(d)], check=True, env=env)
    return json.loads((d / film / f"{variant}.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _setting(params: dict[str, Any]) -> str:
    return ",".join(f"{k}={v}" for k, v in params.items()) or "default"


def _clear(exp: str, variant: str) -> None:
    """Delete earlier MLflow runs with these tags so re-running a command does not duplicate."""
    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("exp002-shots")
    client = MlflowClient(TRACKING_URI)
    eid = client.get_experiment_by_name("exp002-shots").experiment_id  # type: ignore[union-attr]
    for r in client.search_runs(
        [eid], filter_string=f"tags.exp = '{exp}' and tags.variant = '{variant}'"
    ):
        client.delete_run(r.info.run_id)


def _log(
    exp: str, variant: str, params: dict[str, Any], metrics: dict[str, float], clear: bool = True
) -> None:
    """One MLflow run tagged exp/variant (replacing earlier ones with the same tags if `clear`)."""
    import mlflow

    if clear:
        _clear(exp, variant)
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("exp002-shots")
    labeller = json.loads(LABELS.read_text(encoding="utf-8"))["labeller"]
    with mlflow.start_run(run_name=f"{exp}-{variant}"):
        mlflow.set_tags({"exp": exp, "variant": variant, "labeller": labeller})
        mlflow.log_params({k: str(v) for k, v in params.items()})
        mlflow.log_metrics(metrics)


def _sweep_points(out: Path, film: str) -> dict[str, list[tuple[dict[str, Any], list[int], float]]]:
    """Per family: every sweep setting as (params, cuts, s per video-minute or nan).

    TransNetV2 settings come from the saved per-frame probabilities (no re-run needed); the
    PySceneDetect ones from the sweep-* result files that `sweep` writes.
    """
    import numpy as np

    from nip.timeline.shots import cuts_from_predictions

    fams: dict[str, list[tuple[dict[str, Any], list[int], float]]] = {
        "transnetv2": [],
        "content": [],
        "adaptive": [],
    }
    probs = np.load(out / film / "transnetv2_probs.npy")
    for thr in (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        fams["transnetv2"].append(
            ({"threshold": thr}, cuts_from_predictions(probs, thr), float("nan"))
        )
    runs = sorted((out / "runs").glob(f"sweep-*/{film}/*.json"), key=lambda f: int(f.parts[-3][6:]))
    for f in runs:
        r = json.loads(f.read_text())
        fams[r["variant"]].append((r["params"], r["cuts"], r["s_per_video_min"]))
    return fams


# ---- commands ------------------------------------------------------------------------------
@app.command()
def run(
    films: Annotated[list[str] | None, typer.Option("--film")] = None,
    out: Path = OUT,
    repeat: int = 1,
) -> None:
    """Defaults for all three variants on each film -> MLflow runs tagged exp=EXP-002-<film>."""
    import mlflow

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("exp002-shots")
    truth, mask = load_truth(), load_mask()
    labeller = json.loads(LABELS.read_text(encoding="utf-8"))["labeller"]
    variants = [("transnetv2", {"threshold": 0.5}), ("content", {}), ("adaptive", {})]
    for film in films or list(FILMS):
        for variant, params in variants:
            for rep in range(repeat):
                r = _spawn(film, variant, params, f"default-r{rep}", out)
                m = {k: v for k, v in r.items() if isinstance(v, int | float) and k != "n_frames"}
                if film == "sintel":
                    m |= cut_metrics(r["cuts"], truth, mask=mask)
                m["n_cuts"] = len(r["cuts"])
                m["cost/wall_s_per_hour"] = r["s_per_video_min"] * 60
                with mlflow.start_run(run_name=f"{film}-{variant}-r{rep}"):
                    mlflow.set_tags(
                        {"exp": f"EXP-002-{film}", "variant": variant, "labeller": labeller}
                    )
                    mlflow.log_params({"film": film, "detector": variant, **params})
                    mlflow.log_metrics(m)
                print(
                    film, variant, rep, f"{r['s_per_video_min']:.2f} s/min", len(r["cuts"]), "cuts"
                )
    for film in films or list(FILMS):
        table(f"EXP-002-{film}")


@app.command()
def table(exp: str = "EXP-002-sintel") -> None:
    """Comparison table via eval.report.compare_table (+ extra rows for this experiment)."""
    from collections import defaultdict

    from mlflow import MlflowClient

    from eval.report import compare_table

    client = MlflowClient(TRACKING_URI)
    ids = [e.experiment_id for e in client.search_experiments()]
    runs = client.search_runs(ids, filter_string=f"tags.exp = '{exp}'", max_results=1000)
    groups: dict[str, list[Any]] = defaultdict(list)
    for r in sorted(runs, key=lambda r: r.info.start_time):
        groups[r.data.tags["variant"]].append(r)
    print(f"## {exp}\n")
    print(compare_table(groups))
    names = list(groups)
    rows = [
        ("Seconds per video minute", "s_per_video_min", ".2f"),
        ("Peak RAM (MB)", "peak_rss_mb", ".0f"),
        ("Cuts found", "n_cuts", ".0f"),
        ("Mean abs offset of matched cuts (frames)", "mean_abs_offset_frames", ".2f"),
    ]
    print("| Extra | " + " | ".join(names) + " |\n|---|" + "---|" * len(names))
    for label, key, fmt in rows:
        cells = []
        for n in names:
            vals = [r.data.metrics[key] for r in groups[n] if key in r.data.metrics]
            cells.append(format(sum(vals) / len(vals), fmt) if vals else "—")
        print(f"| {label} | " + " | ".join(cells) + " |")


@app.command()
def sweep(
    out: Path = OUT,
    film: str = "sintel",
    reuse: Annotated[
        bool, typer.Option(help="Use existing sweep-* results, do not re-run")
    ] = False,
) -> None:
    """Threshold sweeps scored against the labels, logged to MLflow (exp=EXP-002-sintel-sweep),
    plus the best setting per family as variant "<family>-tuned" (exp=EXP-002-sintel).

    Tuned on the very labels it is scored on: exploratory and optimistic (see `split`).
    """
    grid: list[tuple[str, dict[str, Any]]] = [
        ("content", {"threshold": x}) for x in (10, 15, 20, 27, 35, 45)
    ]
    grid += [("content", {"threshold": x, "min_scene_len": 2}) for x in (15, 27)]
    grid += [("adaptive", {"adaptive_threshold": x}) for x in (1.5, 2.0, 3.0, 4.0, 5.0)]
    grid += [("adaptive", {"adaptive_threshold": 3.0, "min_scene_len": 2, "min_content_val": 8})]
    for i, (variant, params) in enumerate(grid):
        done = out / "runs" / f"sweep-{i}" / film / f"{variant}.json"
        if not (reuse and done.exists()):
            _spawn(film, variant, params, f"sweep-{i}", out)
    truth, mask = load_truth(), load_mask()
    print("| family | setting | cuts | TP | FP | FN | P | R | F1 | s/min |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for fam, points in _sweep_points(out, film).items():
        best: tuple[float, dict[str, Any], dict[str, float]] | None = None
        for params, cuts, spm in points:
            m = cut_metrics(cuts, truth, mask=mask) | {"n_cuts": float(len(cuts))}
            if spm == spm:  # not NaN
                m["s_per_video_min"] = spm
            _log("EXP-002-sintel-sweep", f"{fam}-{_setting(params)}", params, m)
            if best is None or m["shown/f1/all"] > best[0]:
                best = (m["shown/f1/all"], params, m)
            print(
                f"| {fam} | {_setting(params)} | {len(cuts)} | {m['shown/tp/all']:.0f} "
                f"| {m['shown/fp/all']:.0f} | {m['shown/fn/all']:.0f} "
                f"| {m['shown/precision/all']:.3f} | {m['shown/recall/all']:.3f} "
                f"| {m['shown/f1/all']:.3f} | {'' if spm != spm else f'{spm:.1f}'} |"
            )
        assert best is not None
        _log("EXP-002-sintel", f"{fam}-tuned", best[1], best[2])


@app.command()
def candidates(out: Path = OUT, film: str = "sintel") -> None:
    """Union of low-threshold candidates from all three detectors -> <out>/candidates.json."""
    import numpy as np

    from nip.timeline.shots import cuts_from_predictions

    cand: dict[int, list[str]] = {}
    probs_path = out / film / "transnetv2_probs.npy"
    if not probs_path.exists():
        _spawn(film, "transnetv2", {"threshold": 0.5}, "default-r0", out)
        probs_path = out / "runs" / "default-r0" / film / "transnetv2_probs.npy"
    for c in cuts_from_predictions(np.load(probs_path), 0.05):
        cand.setdefault(c, []).append("transnet@0.05")
    low: list[tuple[str, dict[str, Any]]] = [
        ("content", {"threshold": 8, "min_scene_len": 1}),
        ("adaptive", {"adaptive_threshold": 1.2, "min_scene_len": 1, "min_content_val": 4}),
    ]
    for variant, params in low:
        r = _spawn(film, variant, params, f"cand-{variant}", out)
        for c in r["cuts"]:
            cand.setdefault(c, []).append(f"{variant}@{params}")
    path = out / "candidates.json"
    path.write_text(json.dumps(dict(sorted(cand.items()))), encoding="utf-8")
    print(len(cand), "candidates ->", path)


def ffmpeg_small_frames(video: Path, flags: str) -> Any:
    """All frames at 48x27 RGB via the ffmpeg CLI scaler (bicubic = how TransNetV2 was trained)."""
    import numpy as np

    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-an", "-vf", f"scale=48:27:flags={flags}"]
    raw = subprocess.run(
        [*cmd, "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True, check=True
    )
    return np.frombuffer(raw.stdout, np.uint8).reshape(-1, 27, 48, 3)


@app.command("resize-test")
def resize_test(film: str = "sintel", out: Path = OUT) -> None:
    """Does the 48x27 resize filter matter? TorchCodec Resize vs ffmpeg bilinear/bicubic/area."""
    import numpy as np
    import torch

    from nip.timeline.shots import cuts_from_predictions, load_model

    truth, mask = load_truth(), load_mask()
    model = load_model()
    probs = {"torchcodec-resize (current)": np.load(out / film / "transnetv2_probs.npy")}
    for flags in ("bilinear", "bicubic", "area"):
        t = time.perf_counter()
        frames = torch.from_numpy(ffmpeg_small_frames(FILMS[film], flags).copy())
        dt = time.perf_counter() - t
        single, _ = model.predict_frames(frames.to(model.device), quiet=True)
        probs[f"ffmpeg-{flags}"] = single.numpy()
        print(f"ffmpeg {flags}: {len(frames)} frames decoded+scaled in {dt:.1f} s")
    print("| resize | thr | cuts | TP | FP | FN | P | R | F1 | max abs prob diff vs current |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    ref = probs["torchcodec-resize (current)"]
    for name, p in probs.items():
        for thr in (0.3, 0.5):
            c = cuts_from_predictions(p, thr)
            m = cut_metrics(c, truth, mask=mask)
            n = min(len(p), len(ref))
            m["max_abs_prob_diff_vs_current"] = float(np.abs(p[:n] - ref[:n]).max())
            m["n_cuts"] = float(len(c))
            _log("EXP-002-sintel-resize", f"{name}@{thr}", {"resize": name, "threshold": thr}, m)
            print(
                f"| {name} | {thr} | {len(c)} | {m['shown/tp/all']:.0f} | {m['shown/fp/all']:.0f} "
                f"| {m['shown/fn/all']:.0f} | {m['shown/precision/all']:.3f} "
                f"| {m['shown/recall/all']:.3f} | {m['shown/f1/all']:.3f} "
                f"| {np.abs(p[:n] - ref[:n]).max():.3f} |"
            )


@app.command()
def split(out: Path = OUT, film: str = "sintel") -> None:
    """2-fold check against tuning on the test labels: pick each family's best setting on one
    half of the film, score it on the other half; logs "<family>-heldout" (one run per fold).

    Needs `run` (for the frame count) and `sweep` to have written their results under data/.
    """
    truth, mask = load_truth(), load_mask()
    n = json.loads((out / "runs" / "default-r0" / film / "content.json").read_text())["n_frames"]
    halves = {"first": (0, n // 2), "second": (n // 2, n)}

    def half(cuts: list[int], h: str) -> list[int]:
        a, b = halves[h]
        return [c for c in cuts if a <= c < b]

    def metrics(cuts: list[int], h: str) -> dict[str, float]:
        return cut_metrics(half(cuts, h), half(truth, h), mask=mask)

    print("| family | tune on | chosen setting | F1 on tune half | F1 on held-out half |")
    print("|---|---|---|---|---|")
    for fam, points in _sweep_points(out, film).items():
        _clear("EXP-002-sintel", f"{fam}-heldout")
        for tune, test in (("first", "second"), ("second", "first")):
            params, cuts, _ = max(points, key=lambda c: metrics(c[1], tune)["shown/f1/all"])
            held = metrics(cuts, test)
            _log(
                "EXP-002-sintel",
                f"{fam}-heldout",
                {**params, "tuned_on_half": tune, "scored_on_half": test},
                held,
                clear=False,
            )
            print(
                f"| {fam} | {tune} | {_setting(params)} "
                f"| {metrics(cuts, tune)['shown/f1/all']:.3f} | {held['shown/f1/all']:.3f} |"
            )


if __name__ == "__main__":
    app()
