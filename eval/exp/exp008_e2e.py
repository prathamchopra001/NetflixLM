"""2.7 end to end: the injected films through the shipped pipeline (`nip ingest` -> `nip run`)
and scored with `nip eval run` over 3 seeds.

    uv run python -m eval.exp.exp008_e2e prepare --arm 1-per-shot --tag a   # keyframes + ingest
    uv run python -m eval.exp.exp008_e2e run --tag a                        # under data/gpu.lock
    uv run python -m eval.exp.exp008_e2e score --tag a --variant e2e-1-per-shot

Each film, seed and policy tag is its own show (`clr-<film>-s<seed>-<tag>`, episode S01E01): the
injected picture, the sidecar bible and clearance log, and the keyframes of the chosen policy
(the images `nip ingest` stores; EXP-008's frame cache already holds them).
`nip run --agents clearance_scanner` then runs the wired stages (OCR + GLiNER in-process on the
planner's slots) and the six checks. Scoring is the same as EXP-008's.
Needs the dev stack (`docker compose -f compose.yaml -f compose.dev.yaml up -d postgres
objectstore`) and the environment of data/wint/env.sh.
"""

import contextlib
import functools
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


def show_of(film: str, seed: int, tag: str) -> str:
    return f"clr-{film}-s{seed}-{tag}"


def set_title(show: str, title: str) -> None:
    """`nip ingest` names a show by its slug; the clearance scan treats the show's title as the
    production's own name (never a clearance item), so give it the film's real one."""
    from sqlalchemy import create_engine, text

    from nip.store.db import database_url

    engine = create_engine(database_url())
    with engine.begin() as conn:
        conn.execute(text("UPDATE show SET title = :t WHERE slug = :s"), {"t": title, "s": show})
    engine.dispose()


def files(show: str, mode: str) -> tuple[Path, Path]:
    """(out dir of `nip run`, its summary json): `cpu` = run-cpu, `gpu` = the shipped `nip run`."""
    sfx = "" if mode == "cpu" else f"-{mode}"  # cpu | gpu (host `nip run`) | cluster
    return ROOT / show / f"out{sfx}", ROOT / show / f"run-stdout{sfx}.json"


@app.command("prepare")
def prepare(
    arm: str = "1-per-shot", seeds: str = "1,2,3", films: str = "sintel,tears-of-steel",
    tag: str = "a",
) -> None:  # fmt: skip
    """Write picture.json + keyframes of the policy next to each injected film, then ingest."""
    for seed in map(int, seeds.split(",")):
        for name in films.split(","):
            film = bench.load_film(name, seed)
            frames = bench.extract(film)
            folder = ROOT / show_of(name, seed, tag)
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
            show = show_of(name, seed, tag)
            t = time.perf_counter()
            nip("ingest", "--show", show, str(side / "bible.yaml"),
                f"clearance_log={side / 'clearance_log.csv'}")  # fmt: skip
            out = nip("ingest", "--show", show, "--episode", "S01E01",
                      "--picture", str(folder / "picture.json"), str(film.video))  # fmt: skip
            set_title(show, film.title)
            print(show, f"{time.perf_counter() - t:.0f} s", out.stdout.replace("\n", " ")[:200])


@app.command("run")
def run(seeds: str = "1,2,3", films: str = "sintel,tears-of-steel", tag: str = "a") -> None:
    """`nip run` for each film and seed with the clearance agent, under the GPU lock."""
    with bench.gpu_lock("2.7 end-to-end clearance run (OCR + GLiNER + ASR in-process)"):
        for seed in map(int, seeds.split(",")):
            for name in films.split(","):
                show = show_of(name, seed, tag)
                out, summary_json = files(show, "gpu")
                t = time.perf_counter()
                res = nip("run", "--show", show, "--episodes", "S01E01",
                          "--agents", "clearance_scanner", "--out-dir", str(out))  # fmt: skip
                wall = time.perf_counter() - t
                summary_json.write_text(res.stdout, encoding="utf-8")
                s = json.loads(res.stdout)
                ep = s["episodes"]["S01E01"]
                stages = {x["stage"]: x["wall_s"] for x in ep["stages"] if x["wall_s"] > 0.5}
                print(show, s["status"], f"{wall:.0f} s", ep["flags_kept"], "flags", ep["units"],
                      stages, ep["skipped_stages"], flush=True)  # fmt: skip


@app.command("run-cluster")
def run_cluster(
    seeds: str = "1", films: str = "sintel", tag: str = "b", container: str = "netflixlm-ray-head-1"
) -> None:
    """The shipped GPU path once: `nip run --in-cluster` inside ray-head (OCR and GLiNER in-process;
    Plan's llm group staged around its stages), under data/gpu.lock. The ner slot is the
    planner's choice (gliner-x-large on the laptop since 2.close measured it)."""
    env = ["-e", "NIP_OCR_MODELS=/models/rapidocr", "-e", "NIP_VRAM_MARGIN_GB=0.25"]  # fmt: skip
    with bench.gpu_lock("2.7 nip run --in-cluster on a film (OCR + GLiNER + llm group)"):
        for seed in map(int, seeds.split(",")):
            for name in films.split(","):
                show = show_of(name, seed, tag)
                out, summary_json = files(show, "cluster")
                t = time.perf_counter()
                nip_plan = ["docker", "exec", *env, container, "nip", "plan", "--units", "1"]
                plan = subprocess.run(nip_plan, capture_output=True, text=True)
                (ROOT / show).mkdir(parents=True, exist_ok=True)
                (ROOT / show / "plan-cluster.json").write_text(plan.stdout, encoding="utf-8")
                res = subprocess.run(
                    ["docker", "exec", *env, container, "nip", "run", "--show", show,
                     "--episodes", "S01E01", "--agents", "clearance_scanner", "--in-cluster",
                     "--out-dir", "/tmp/clr-cluster"],
                    capture_output=True, text=True,
                )  # fmt: skip
                wall = time.perf_counter() - t
                (ROOT / show / "run-stderr-cluster.txt").write_text(res.stderr, encoding="utf-8")
                summary_json.write_text(res.stdout, encoding="utf-8")
                subprocess.run(["docker", "cp", f"{container}:/tmp/clr-cluster/.", str(out)],
                               check=False)  # fmt: skip
                subprocess.run(["docker", "exec", container, "rm", "-rf", "/tmp/clr-cluster"],
                               check=False)  # fmt: skip
                print(show, f"exit {res.returncode}", f"{wall:.0f} s", flush=True)
                if res.returncode == 0:
                    sm = json.loads(res.stdout)
                    ep = sm["episodes"]["S01E01"]
                    print(sm["status"], ep["flags_kept"], ep["units"], sm["serving"],
                          sm["plan"]["skipped_slots"], flush=True)  # fmt: skip


@app.command("run-cpu")
def run_cpu(seeds: str = "1,2,3", films: str = "sintel,tears-of-steel", tag: str = "b") -> None:
    """The same `run_store` with the real OCR and GLiNER on the CPU (no GPU, no lock): the stub Plan
    with the ocr and ner slots set to the real variants, `CUDA_VISIBLE_DEVICES=-1`. For when the
    GPU is held by an LLM job; `run` is the shipped `nip run` path."""
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    os.environ["NIP_PROFILE"] = "cpu"
    from sqlalchemy import create_engine

    from nip import pipeline
    from nip.contracts import Slot, SlotDecision
    from nip.contracts.flag import Agent
    from nip.store import objects
    from nip.store.db import database_url

    pipeline.wire()
    plan, inv = pipeline.current_plan({s: 1 for s in pipeline.MODEL_SLOTS})
    decisions = {Slot.OCR: SlotDecision(variant="pp-ocrv6-medium"),
                 Slot.NER: SlotDecision(variant="gliner-x-base")}  # fmt: skip
    plan = plan.model_copy(update={"decisions": {**plan.decisions, **decisions}})
    engine = create_engine(database_url())
    s3 = objects.client()
    for seed in map(int, seeds.split(",")):
        for name in films.split(","):
            show = show_of(name, seed, tag)
            t = time.perf_counter()
            summary = pipeline.run_store(
                engine, s3, show=show, episodes=["S01E01"], plan=plan, inventory=inv,
                agents={Agent.CLEARANCE_SCANNER}, out_dir=files(show, "cpu")[0],
            )  # fmt: skip
            wall = time.perf_counter() - t
            files(show, "cpu")[1].write_text(json.dumps(summary), encoding="utf-8")
            ep = summary["episodes"]["S01E01"]
            stages = {x["stage"]: x["wall_s"] for x in ep["stages"] if x["wall_s"] > 0.5}
            print(show, summary["status"], f"{wall:.0f} s", ep["flags_kept"], "flags", ep["units"],
                  stages, flush=True)  # fmt: skip


@app.command("ocr-lines")
def ocr_lines(seeds: str = "1,2,3", films: str = "sintel,tears-of-steel", tag: str = "b") -> None:
    """Snapshot each show's stored OCR text lines (`detection`, channel ocr, label text) to
    `ocr-lines/<show>.json`, so `run-ner` can replay one fixed OCR input through any NER variant."""
    from sqlalchemy import create_engine, func, select

    from nip.store import schema
    from nip.store.db import database_url

    d, sh, ep, shw = schema.detection, schema.shot, schema.episode, schema.show
    (ROOT / "ocr-lines").mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url())
    with engine.connect() as conn:
        for seed in map(int, seeds.split(",")):
            for name in films.split(","):
                show = show_of(name, seed, tag)
                eid = conn.execute(
                    select(ep.c.id).join(shw, shw.c.id == ep.c.show_id).where(shw.c.slug == show)
                ).scalar_one()
                index = {
                    sid: i
                    for i, sid in enumerate(
                        conn.execute(
                            select(sh.c.id)
                            .where(sh.c.episode_id == eid)
                            .order_by(func.lower(sh.c.frames), sh.c.id)
                        ).scalars()
                    )
                }
                rows = conn.execute(
                    select(d.c.shot_id, d.c.keyframe_n, d.c.text, d.c.box, d.c.confidence)
                    .where(d.c.episode_id == eid, d.c.channel == "ocr", d.c.label == "text")
                    .order_by(d.c.id)
                ).all()
                lines = [
                    [index[r.shot_id], r.keyframe_n, r.text, list(r.box), r.confidence]
                    for r in rows
                ]
                (ROOT / "ocr-lines" / f"{show}.json").write_text(json.dumps(lines), "utf-8")
                print(show, len(lines), "lines", flush=True)
    engine.dispose()


@app.command("run-ner")
def run_ner(
    ner: str = "gliner-x-large", seeds: str = "1,2,3", films: str = "sintel,tears-of-steel",
    tag: str = "b", cpu: bool = False,
) -> None:  # fmt: skip
    """The pipeline's `run_store` with the OCR of `ocr-lines` replayed (same text for every NER
    variant) and the real GLiNER `ner` on the GPU (under data/gpu.lock; `--cpu`: on the CPU, no
    lock, same output); output mode `ner-<ner>`.
    Score with `score --mode ner-<ner> --variant e2e-<ner>`. NIP_PROFILE=cpu keeps the other
    slots stubbed, like `run-cpu`."""
    os.environ["NIP_PROFILE"] = "cpu"
    if cpu:
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    from sqlalchemy import create_engine

    from nip import pipeline
    from nip.agents.clearance import stage
    from nip.contracts import Slot, SlotDecision
    from nip.contracts.flag import Agent
    from nip.runtime.clients.ocr import OcrLine, StubOCR, fingerprint
    from nip.store import objects
    from nip.store.db import database_url

    pipeline.wire()
    plan, inv = pipeline.current_plan({s: 1 for s in pipeline.MODEL_SLOTS})
    decisions = {Slot.OCR: SlotDecision(variant="pp-ocrv6-medium"),
                 Slot.NER: SlotDecision(variant=ner)}  # fmt: skip
    plan = plan.model_copy(update={"decisions": {**plan.decisions, **decisions}})
    engine = create_engine(database_url())
    s3 = objects.client()
    mode = f"ner-{ner}"
    with contextlib.nullcontext() if cpu else bench.gpu_lock(f"EXP-008 NER {ner} on replayed OCR"):
        for seed in map(int, seeds.split(",")):
            for name in films.split(","):
                show = show_of(name, seed, tag)
                saved = json.loads((ROOT / "ocr-lines" / f"{show}.json").read_text("utf-8"))
                with engine.connect() as conn:
                    keys = stage._keyframe_keys(conn, pipeline.episode_row(conn, show, "S01E01").id)
                recorded = {}
                for (shot, n), key in keys.items():
                    image = s3.get_object(Bucket=objects.media_bucket(), Key=key)["Body"].read()
                    recorded[fingerprint(image)] = [
                        OcrLine(text=t, box=tuple(b), confidence=c)
                        for sh, k, t, b, c in saved if (sh, k) == (shot, n)
                    ]  # fmt: skip
                reader = StubOCR(recorded)
                stage.ocr_reader = functools.cache(lambda variant, r=reader: r)
                t = time.perf_counter()
                summary = pipeline.run_store(
                    engine, s3, show=show, episodes=["S01E01"], plan=plan, inventory=inv,
                    agents={Agent.CLEARANCE_SCANNER}, out_dir=files(show, mode)[0],
                )  # fmt: skip
                wall = time.perf_counter() - t
                files(show, mode)[1].write_text(json.dumps(summary), encoding="utf-8")
                ep = summary["episodes"]["S01E01"]
                print(show, ner, summary["status"], f"{wall:.0f} s", ep["flags_kept"], "flags",
                      flush=True)  # fmt: skip
                stage.release_models()
    engine.dispose()


def collected(
    seed: int, films: list[str], tag: str, mode: str
) -> tuple[list[Flag], list[bench.Film]]:
    flags: list[Flag] = []
    sel = [bench.load_film(n, seed) for n in films]
    for film in sel:
        path = files(show_of(film.name, seed, tag), mode)[0] / "S01E01" / "flags.jsonl"
        for line in path.read_text("utf-8").splitlines():
            f = Flag.model_validate_json(line)
            flags.append(f.model_copy(update={"episode": film.episode}))  # S01E02 for ToS
    return flags, sel


@app.command("score")
def score(
    seeds: str = "1,2,3", films: str = "sintel,tears-of-steel", exp: str = EXP,
    variant: str = "e2e-cpu", arm: str = "1-per-shot+2s", tag: str = "b", mode: str = "cpu",
) -> None:  # fmt: skip
    """Score the pipeline's flags (both films of a seed in one run) with `nip eval run`."""
    for seed in map(int, seeds.split(",")):
        flags, sel = collected(seed, films.split(","), tag, mode)
        hours = sum(f.hours for f in sel)
        wall = 0.0
        for f in sel:
            s = json.loads(files(show_of(f.name, seed, tag), mode)[1].read_text("utf-8"))
            wall += sum(x["wall_s"] for x in s["episodes"]["S01E01"]["stages"]
                        if x["stage"] == "clearance.ocr")  # fmt: skip
        official = [lb for f in sel for lb in f.labels]
        allpos = [lb for f in sel for lb in bench.all_positive_labels(f)]
        extra: dict[str, Any] = {"e2e/ocr_stage_s_per_content_hour": wall / hours}
        natives = [lb for f in sel for lb in f.natives]
        runs = [(variant, official, []), (f"{variant}+native", official, natives),
                (f"{variant}@all-positives", allpos, [])]  # fmt: skip
        for name, labels, nat in runs:
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
                natives=nat,
            )
            print(line, flush=True)


if __name__ == "__main__":
    app()
