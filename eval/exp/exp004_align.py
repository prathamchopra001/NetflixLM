"""EXP-004: token-level monotonic vs rapidfuzz line-level script <-> transcript alignment.

    uv run python -m eval.exp.exp004_align run [--asr turbo-int8] [--config default]
    uv run python -m eval.exp.exp004_align matrix        # every saved EXP-003 transcript set

Sets: the derived as-broadcast scripts of Sintel and Tears of Steel (marked start = official
SRT cue start, ruling R5) and Sintel's real first-minute script (3 labelled lines; the draft's
wording differs from the film). Metric: share of labelled lines whose aligned start is within
+-12 frames of the marked start (an unplaced line counts as a miss). Transcripts come from
EXP-003 run 1 (data/exp003/<variant>/<film>[.config].transcript.json), so no GPU is needed.
Alignment is deterministic, so there is one run per variant (seed 1). MLflow: "exp004-align".
"""

import json
from fractions import Fraction
from functools import cache
from pathlib import Path
from statistics import median
from typing import Any

import typer

from eval.exp.exp003_asr import SHIPPED
from nip.ingest.media import probe
from nip.ingest.pdf import parse_pdf
from nip.ingest.script import Script, parse_fountain
from nip.timeline.align import VARIANTS
from nip.timeline.asr import TranscriptSegment, TranscriptWord

ROOT = Path(__file__).resolve().parents[2]
TRACKING_URI = f"sqlite:///{(ROOT / 'data' / 'mlflow' / 'mlflow.db').as_posix()}"
TOL = 12
VIDEOS = [
    "data/corpus/sintel/Sintel.2010.1080p.mkv",
    "data/corpus/tears-of-steel/tears_of_steel_720p.mov",
]
SETS = {  # label set -> (film whose audio it is aligned to, script loader)
    "sintel": "sintel",
    "tears-of-steel": "tears-of-steel",
    "sintel-real-script": "sintel",
}
app = typer.Typer(no_args_is_help=True)


def load_script(name: str) -> Script:
    if name == "sintel-real-script":
        p = parse_pdf((ROOT / "data/corpus/sintel/1stminute_script_11-61.pdf").read_bytes())
    else:
        p = parse_fountain((ROOT / f"eval/corpus/derived/{name}/script.fountain").read_bytes())
    assert p.data is not None and not p.errors, p.errors
    return p.data


def load_labels(name: str) -> dict[tuple[int, int], int]:
    rows = (ROOT / f"eval/exp/exp004_labels/{name}.jsonl").read_text(encoding="utf-8").splitlines()
    return {(r["scene"], r["element"]): r["start_frame"] for r in map(json.loads, rows)}


def load_transcript(asr: str, config: str, film: str) -> list[TranscriptSegment]:
    f = ROOT / "data/exp003" / f"faster-whisper-large-v3-{asr}" / f"{film}.{config}.transcript.json"
    return [
        TranscriptSegment(
            tuple(s["frames"]), s["lang"], s["text"], tuple(TranscriptWord(**w) for w in s["words"])
        )
        for s in json.loads(f.read_text())
    ]


@cache
def _fps() -> Fraction:
    """The films' frame rate from the probe (Sintel and Tears of Steel share one)."""
    rates = {probe(ROOT / v).fps for v in VIDEOS}
    assert len(rates) == 1, rates
    return rates.pop()


def score(variant: str, asr: str, config: str, cap_s: float | None = None) -> dict[str, float]:
    """Metrics for one alignment variant on one transcript set, all three label sets pooled.
    `cap_s`: first-word cap in seconds (frames = cap_s x the probed fps)."""
    kw: dict[str, Any] = {} if cap_s is None else {"first_word_cap": round(cap_s * _fps())}
    hit = total = placed = 0
    offs: list[int] = []
    out: dict[str, float] = {}
    for name, film in SETS.items():
        truth = load_labels(name)
        got = VARIANTS[variant](load_script(name), load_transcript(asr, config, film), **kw)
        h = sum(1 for k, f in truth.items() if k in got and abs(got[k].frames[0] - f) <= TOL)
        o = [got[k].frames[0] - f for k, f in truth.items() if k in got]
        out[f"within_{TOL}f_{name}"] = h / len(truth)
        out[f"placed_{name}"] = len(o) / len(truth)
        hit, total, placed = hit + h, total + len(truth), placed + len(o)
        offs += o
    out["within_12f"] = hit / total
    out["placed"] = placed / total
    out["median_abs_offset_f"] = float(median(abs(x) for x in offs)) if offs else float("nan")
    out["median_offset_f"] = float(median(offs)) if offs else float("nan")
    out["labelled_lines"] = float(total)
    return out


def _log(
    exp: str, variant: str, asr: str, config: str, cap_s: float | None, m: dict[str, float]
) -> None:
    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("exp004-align")
    client = MlflowClient(TRACKING_URI)
    eid = client.get_experiment_by_name("exp004-align").experiment_id  # type: ignore[union-attr]
    for r in client.search_runs(
        [eid], filter_string=f"tags.exp = '{exp}' and tags.variant = '{variant}'"
    ):
        client.delete_run(r.info.run_id)  # re-running replaces, never duplicates
    with mlflow.start_run(run_name=f"{exp}-{variant}"):
        mlflow.set_tags({"exp": exp, "variant": variant, "seed": "1", "labeller": "agent"})
        mlflow.log_params({
            "asr": f"large-v3-{asr}", "asr_config": config, "first_word_cap_s": str(cap_s),
            "tolerance_frames": TOL,
        })  # fmt: skip
        mlflow.log_metrics(m)


@app.command()
def run(
    asr: str = "turbo-int8", config: str = SHIPPED, cap_s: float = 0.3, exp: str = "EXP-004"
) -> None:
    """Both alignment variants on one ASR transcript set, twice: without the first-word cap
    (tag `exp`, the pre-registered comparison) and with it (`exp`-cap, the shipped start rule)."""
    for tag, cap in ((exp, None), (f"{exp}-cap", cap_s)):
        for v in VARIANTS:
            m = score(v, asr, config, cap)
            _log(tag, v, asr, config, cap, m)
            print(tag, v, {k: round(x, 3) for k, x in m.items()})


@app.command()
def matrix(cap_s: float = 0.3) -> None:
    """Every (model, decoding config) transcript set x both variants x with/without the cap
    (tag exp=EXP-004-asr-input). Shows how much the alignment depends on the ASR settings."""
    for d in sorted((ROOT / "data/exp003").glob("faster-whisper-large-v3-*")):
        asr = d.name.removeprefix("faster-whisper-large-v3-")
        for f in sorted(d.glob("sintel.*.transcript.json")):
            config = f.name.removeprefix("sintel.").removesuffix(".transcript.json")
            for v in VARIANTS:
                for cap in (None, cap_s):
                    m = score(v, asr, config, cap)
                    _log("EXP-004-asr-input", f"{v}/{asr}/{config}/cap={cap}", asr, config, cap, m)
                    print(
                        f"{v:6} {asr:10} {config:10} cap={cap!s:5} within12={m['within_12f']:.3f} "
                        f"placed={m['placed']:.3f} median|off|={m['median_abs_offset_f']:.1f}f"
                    )


if __name__ == "__main__":
    app()
