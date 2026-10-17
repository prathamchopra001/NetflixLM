"""2.7 end to end: the injected films through the shipped pipeline (`nip ingest` -> `nip run`)
and scored with `nip eval run` over 3 seeds.

    uv run python -m eval.exp.exp008_e2e prepare --arm 1-per-shot+2s   # keyframes + `nip ingest`
    uv run python -m eval.exp.exp008_e2e run                            # `nip run`, under gpu.lock
    uv run python -m eval.exp.exp008_e2e score                          # flags -> `nip eval run`

Each film and seed is its own show (`clr-<film>-s<seed>`, episode S01E01): the injected picture, the
sidecar bible and clearance log, and the keyframes of the chosen policy (the images `nip ingest`
stores; EXP-008's frame cache already holds them). `nip run --agents clearance_scanner` then runs
the wired stages (OCR + GLiNER in-process on the planner's slots) and the six checks. Scoring is
the same as EXP-008's, with the variant name `e2e`.
Needs the dev stack (`docker compose -f compose.yaml -f compose.dev.yaml up -d postgres
objectstore`) and the environment of data/wint/env.sh (plus `NIP_PIN_NER=gliner-x-base`).
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import typer

from eval.exp import exp008_keyframes as bench
from nip.contracts.flag import Flag

ROOT = bench.ROOT / "e2e"
EXP = "2.7-e2e"
app = typer.Typer(no_args_is_help=True)


def nip(*args: str) -> subprocess.CompletedProcess[str]:
    exe = str(Path(sys.executable).with_name("nip"))
    return subprocess.run([exe, *args], capture_output=True, text=True, check=True, env=os.environ)


def show_of(film: str, seed: int) -> str:
    return f"clr-{film}-s{seed}"


@app.command("prepare")
def prepare(
    arm: str = "1-per-shot+2s", seeds: str = "1,2,3", films: str = "sintel,tears-of-steel"
) -> None:
    """Write picture.json + keyframes of the policy next to each injected film, then ingest."""
    for seed in map(int, seeds.split(",")):
        for name in films.split(","):
            film = bench.load_film(name, seed)
            frames = bench.extract(film)
            folder = ROOT / show_of(name, seed)
            (folder / "keyframes").mkdir(parents=True, exist_ok=True)
            recs = []
            for shot, n, f in bench.policy(film, arm):
                shutil.copyfile(frames[f], folder / "keyframes" / f"{shot}_{n}.jpg")
                recs.append({"shot": shot, "n": n, "frame": f, "file": f"{shot}_{n}.jpg"})
            fps = film.info.fps
            (folder / "picture.json").write_text(
                json.dumps(
                    {"fps": [fps.numerator, fps.denominator],
                     "duration_frames": film.info.duration_frames,
                     "start_tc_frames": film.info.start_tc_frames,
                     "drop_frame": film.info.drop_frame,
                     "shots": [list(s) for s in film.shots], "keyframes": recs}
                ),
                encoding="utf-8",
            )  # fmt: skip
            side = bench.SIDECAR / name
            show = show_of(name, seed)
            t = time.perf_counter()
            nip("ingest", "--show", show, str(side / "bible.yaml"),
                f"clearance_log={side / 'clearance_log.csv'}")  # fmt: skip
            out = nip("ingest", "--show", show, "--episode", "S01E01",
                      "--picture", str(folder / "picture.json"), str(film.video))  # fmt: skip
            print(show, f"{time.perf_counter() - t:.0f} s", out.stdout.replace("\n", " ")[:200])


@app.command("run")
def run(seeds: str = "1,2,3", films: str = "sintel,tears-of-steel") -> None:
    """`nip run` for each film and seed with the clearance agent, under the GPU lock."""
    with bench.gpu_lock("2.7 end-to-end clearance run (OCR + GLiNER + ASR in-process)"):
        for seed in map(int, seeds.split(",")):
            for name in films.split(","):
                show = show_of(name, seed)
                out = ROOT / show / "out"
                t = time.perf_counter()
                res = nip("run", "--show", show, "--episodes", "S01E01",
                          "--agents", "clearance_scanner", "--out-dir", str(out))  # fmt: skip
                wall = time.perf_counter() - t
                (ROOT / show / "run-stdout.json").write_text(res.stdout, encoding="utf-8")
                s = json.loads(res.stdout)
                ep = s["episodes"]["S01E01"]
                stages = {x["stage"]: x["wall_s"] for x in ep["stages"] if x["wall_s"] > 0.5}
                print(show, s["status"], f"{wall:.0f} s", ep["flags_kept"], "flags", ep["units"],
                      stages, ep["skipped_stages"], flush=True)  # fmt: skip


def collected(seed: int, films: list[str]) -> tuple[list[Flag], list[bench.Film]]:
    flags: list[Flag] = []
    sel = [bench.load_film(n, seed) for n in films]
    for film in sel:
        path = ROOT / show_of(film.name, seed) / "out" / "S01E01" / "flags.jsonl"
        for line in path.read_text("utf-8").splitlines():
            f = Flag.model_validate_json(line)
            flags.append(f.model_copy(update={"episode": film.episode}))  # S01E02 for ToS
    return flags, sel


@app.command("score")
def score(
    seeds: str = "1,2,3", films: str = "sintel,tears-of-steel", exp: str = EXP,
    variant: str = "e2e", arm: str = "1-per-shot+2s",
) -> None:  # fmt: skip
    """Score the pipeline's flags (both films of a seed in one run) with `nip eval run`."""
    for seed in map(int, seeds.split(",")):
        flags, sel = collected(seed, films.split(","))
        hours = sum(f.hours for f in sel)
        wall = 0.0
        for f in sel:
            s = json.loads((ROOT / show_of(f.name, seed) / "run-stdout.json").read_text("utf-8"))
            wall += sum(x["wall_s"] for x in s["episodes"]["S01E01"]["stages"]
                        if x["stage"] == "clearance.ocr")  # fmt: skip
        official = [lb for f in sel for lb in f.labels]
        allpos = [lb for f in sel for lb in bench.all_positive_labels(f)]
        extra: dict[str, Any] = {"e2e/ocr_stage_s_per_content_hour": wall / hours}
        for name, labels in ((variant, official), (f"{variant}@all-positives", allpos)):
            out = ROOT / "scored" / f"{name}-s{seed}"
            params = {"arm": arm, "path": "nip ingest + nip run"}
            line = bench.nip_eval_run(
                flags,
                labels,
                exp=exp,
                variant=name,
                seed=seed,
                out=out,
                content_hours=hours,
                gpu_seconds=wall,
                extra=extra,
                params=params,
            )
            print(line, flush=True)


if __name__ == "__main__":
    app()
