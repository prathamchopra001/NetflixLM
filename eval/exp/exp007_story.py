"""EXP-007: story order, rules only vs rules + LLM (D-006).

    uv run python -m eval.exp.exp007_story prepare             # shows + plot-L1 injections (CPU)
    uv run python -m eval.exp.exp007_story derive --arm rules  # story order per arm (CPU)
    uv run python -m eval.exp.exp007_story derive --arm bible
    # GPU: hold data/gpu.lock only while vLLM is up (phase2-plan.md > GPU contention)
    DC="docker compose -f compose.yaml -f compose.dev.yaml -f eval/exp/exp001.compose.yaml"
    $DC up -d --wait ray-head
    $DC exec ray-head python3 -m eval.exp.exp007_story up      # probe -> plan -> deploy
    NIP_SERVE_URL=http://127.0.0.1:8001 uv run python -m eval.exp.exp007_story derive --arm llm
    $DC exec ray-head python3 -m eval.exp.exp007_story down    # teardown, VRAM back to idle
    NIP_TEST_DATABASE_URL=... uv run python -m eval.exp.exp007_story score     # CPU -> MLflow
    uv run nip eval compare --exp EXP-007 --md --tracking-uri sqlite:///data/mlflow/mlflow.db

Shows: the synthetic show (seeds 1-3) in two variants, `base` (as generated) and `ambiguous`
(eval/synthetic/ambiguous.py: story time stated only in prose), each with the 2.9A plot-L1
injections. Arms (`<variant>-<arm>` is the MLflow variant tag):
- `rules`: `derive` with no LLM and no bible (the EXP-007 rules-only arm).
- `rules+llm`: `derive` with the real qwen3.5-4b-awq, one verdict per ambiguous transition.
- `rules+bible`: `derive` with the bible's story_overrides (reference: a filled-in bible).
- `truth`: the generator's own order (the ceiling: the labels are defined by it).
Fixed fact set: oracle facts from `truth.json` (eval/exp/layer1_oracle.consolidate), identical in
every arm, so the arms differ only in the `scene.story_seq` / `markers` / `story_inferred` the
four Layer 1 SQL rules (2.3) read. Metrics: Kendall tau-b of story_seq vs truth, present-scene day
accuracy, flashback / simultaneous marker recall, LLM verdict accuracy per kind of transition, and
per-check precision / recall of the plot rules against the injected labels (`nip eval run`).
"""

import json
import os
import re
import shutil
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any

import typer

from eval.synthetic import Show, build, read_show, write_show

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "exp007"
TRACKING_URI = f"sqlite:///{(ROOT / 'data' / 'mlflow' / 'mlflow.db').as_posix()}"
SEEDS = (1, 2, 3)
VARIANTS = ("base", "ambiguous")
ARMS = {
    "rules": "rules",
    "llm": "rules+llm",  # prompt v1 (config/prompts/knowledge.story.v1.md)
    "llm-v2": "rules+llm-v2",  # prompt v2, written after reading v1's verdicts on seed 1
    "bible": "rules+bible",
    "truth": "truth",
}
MODEL = "qwen3.5-4b-awq"
SET = "exp007-story"
app = typer.Typer(no_args_is_help=True)


def _dir(variant: str, seed: int) -> Path:
    return OUT / variant / f"seed{seed}"


# ---- prepare -------------------------------------------------------------------------------------
def make_show(variant: str, seed: int) -> tuple[Show, dict[str, str]]:
    from eval.synthetic.ambiguous import ambiguate

    show = build(seed)
    return ambiguate(show, seed) if variant == "ambiguous" else (show, {})


def inject_plot(show: Show, root: Path, seed: int) -> list[Any]:
    """The four plot-L1 injectors stacked (as `nip eval inject` does): `root/clean`,
    `root/injected`, labels returned."""
    import tempfile

    from eval.inject import PLOT
    from eval.injectors import get

    write_show(show, root / "clean")
    labels: list[Any] = []
    cur = root / "clean"
    with tempfile.TemporaryDirectory() as tmp:
        for i, name in enumerate(PLOT):
            nxt = root / "injected" if i == len(PLOT) - 1 else Path(tmp) / str(i)
            labels += get(name).inject(cur, nxt, seed)
            cur = nxt
    return labels


@app.command()
def prepare() -> None:
    """Both variants x 3 seeds: show, notes (scene kind), plot-L1 injection, labels."""
    from eval.injectors import write_labels

    for variant in VARIANTS:
        for seed in SEEDS:
            root = _dir(variant, seed)
            shutil.rmtree(root, ignore_errors=True)
            show, notes = make_show(variant, seed)
            labels = inject_plot(show, root, seed)
            write_labels(labels, root / "labels" / "synthetic-show.jsonl")
            (root / "notes.json").write_text(json.dumps(notes, indent=1), encoding="utf-8")
            kinds: dict[str, int] = {}
            for k in notes.values():
                kinds[k] = kinds.get(k, 0) + 1
            typer.echo(f"{variant} seed{seed}: {len(labels)} labels, scenes by kind {kinds}")


# ---- deriving each arm's story order -------------------------------------------------------------
def load_scenes(injected: Path) -> list[Any]:
    from nip.ingest import parse_fountain
    from nip.knowledge.story import scenes_from_script

    out: list[Any] = []
    for f in sorted(injected.glob("S01E*.fountain")):
        parsed = parse_fountain(f.read_bytes())
        assert parsed.ok and parsed.data, (f, parsed.errors)
        out += scenes_from_script(f.stem, parsed.data)
    return out


class Recording:
    """Wraps the LLM: logs every verdict with the scene it was asked about."""

    def __init__(self, llm: Any) -> None:
        self.llm, self.ref = llm, ""
        self.log: list[dict[str, Any]] = []

    def complete(self, prompt: str, schema: Any, **kw: Any) -> Any:
        t = time.perf_counter()
        entry: dict[str, Any] = {"ref": self.ref, "prompt": prompt}
        self.log.append(entry)
        v = self.llm.complete(prompt, schema, **kw)
        entry |= {"verdict": v.model_dump(), "seconds": round(time.perf_counter() - t, 2)}
        return v

    def unit(self, key: str) -> Any:
        from nip.knowledge.story import _swallow

        @contextmanager
        def cm() -> Iterator[None]:
            self.ref = key
            with _swallow(key):
                yield

        return cm()


def run_arm(arm: str, injected: Path, llm: Any = None) -> dict[str, Any]:
    from nip.ingest import parse_bible
    from nip.knowledge.story import derive

    scenes = load_scenes(injected)
    overrides: list[Any] = []
    if arm == "bible":
        parsed = parse_bible((injected / "bible.yaml").read_bytes())
        overrides = parsed.data.story_overrides if parsed.data else []
    rec = Recording(llm) if llm else None
    t = time.perf_counter()
    st = derive(scenes, overrides, rec, unit=rec.unit if rec else _noop)
    return {
        "arm": arm,
        "seconds": round(time.perf_counter() - t, 3),
        "ambiguous": st.ambiguous,
        "llm_calls": st.llm_calls,
        "unmatched": st.unmatched,
        "verdicts": rec.log if rec else [],
        "positions": [
            {**p.__dict__, "markers": list(p.markers), "story_day": p.story_day}
            for p in st.positions
        ],
    }


def _noop(key: str) -> Any:
    from nip.knowledge.story import _swallow

    return _swallow(key)


@app.command()
def derive(
    arm: Annotated[
        str, typer.Option(help="rules | bible | llm | llm-v2 (llm needs NIP_SERVE_URL)")
    ],
    only: Annotated[str, typer.Option(help="Comma list of variant:seed, default all")] = "",
) -> None:
    """Story order of every injected show under one arm; writes `<arm>.json` per show."""
    from nip.knowledge import story

    if arm not in ARMS or arm == "truth":
        raise typer.BadParameter(f"one of {[a for a in ARMS if a != 'truth']}")
    llm = None
    if arm.startswith("llm"):
        from nip.runtime.clients.llm import LLMClient

        llm = LLMClient(MODEL)
        story.PROMPT = f"knowledge.story.{arm.removeprefix('llm-') if '-' in arm else 'v1'}.md"
    todo = {tuple(x.split(":")) for x in only.split(",") if x}
    for variant in VARIANTS:
        for seed in SEEDS:
            if todo and (variant, str(seed)) not in todo:
                continue
            root = _dir(variant, seed)
            res = run_arm(arm, root / "injected", llm)
            (root / f"{arm}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
            failed = sum("verdict" not in v for v in res["verdicts"])
            typer.echo(
                f"{variant} seed{seed} {arm}: ambiguous {res['ambiguous']}, llm_calls "
                f"{res['llm_calls']}, failed {failed}, {res['seconds']} s"
            )


# ---- serving (run inside ray-head), the shipped path as in EXP-020 ---------------------------
@app.command()
def up() -> None:
    """Probe -> planner -> deploy the text_llm app; prints the decision and the idle VRAM."""
    from nip.config import vram_margin_gb
    from nip.contracts import Slot
    from nip.runtime.catalog import load_catalog
    from nip.runtime.planner import plan
    from nip.runtime.probe import probe
    from nip.runtime.serving import apps, deploy, gpu_used_mib, ray_serve

    cat, inv = load_catalog(), probe()
    idle = gpu_used_mib()
    p = plan(inv, cat, {Slot.TEXT_LLM: 1}, margin_gb=vram_margin_gb())
    if Slot.TEXT_LLM in p.skipped_slots:
        typer.echo(f"planner skipped text_llm: {p.warnings}", err=True)
        raise typer.Exit(1)
    [a] = apps(p, cat, inv, p.groups[0].slots)
    secs = deploy([a], ray_serve())
    d = p.decisions[Slot.TEXT_LLM].model_dump(exclude_none=True)
    Path("/tmp/exp007-idle.txt").write_text(str(idle))
    typer.echo(json.dumps({"load_s": secs, "idle_mib": idle, "decision": d, "args": a.vllm_args}))


@app.command()
def down() -> None:
    """Delete every Serve app and wait for VRAM back to the idle level read by `up`. (Not a
    re-plan: with the model loaded the planner no longer fits it and would delete nothing.)
    Deletes ALL Serve apps in the cluster: run it only while holding data/gpu.lock."""
    from nip.runtime.serving import IDLE_TOLERANCE_MIB, gpu_used_mib, ray_serve

    serve, t = ray_serve(), time.monotonic()
    idle_f = Path("/tmp/exp007-idle.txt")
    idle = int(idle_f.read_text()) if idle_f.exists() else None
    for name in list(serve.status().applications):
        serve.delete(name)
    while idle is not None and gpu_used_mib() > idle + IDLE_TOLERANCE_MIB:
        if time.monotonic() - t > 180:
            raise RuntimeError(f"VRAM {gpu_used_mib()} MiB after 180 s, idle was {idle}")
        time.sleep(0.5)
    typer.echo(json.dumps({"unload_s": round(time.monotonic() - t, 1), "idle_mib": idle}))


# ---- scoring -------------------------------------------------------------------------------------
def truth_relation(show: Show, ref: str) -> str:
    """How the scene relates to the last present scene before it, by truth (the LLM's question)."""
    from nip.contracts import refs

    flat = [(refs.scene(ep, sc.no), sc) for ep, scs in show.episodes.items() for sc in scs]
    i = next(k for k, (r, _) in enumerate(flat) if r == ref)
    sc = flat[i][1]
    if sc.marker == "flashback":
        return "earlier"
    if sc.marker == "same_time":
        return "simultaneous"
    prev = next((s for _, s in reversed(flat[:i]) if s.marker is None), sc)
    delta = sc.story_day - prev.story_day
    return "same_day" if delta == 0 else "next_day" if delta == 1 else "later_days"


def story_metrics(
    show: Show, notes: dict[str, str], res: dict[str, Any], truth_arm: bool = False
) -> dict[str, float]:
    """Order and marker agreement of one arm's positions with the show's truth."""
    from nip.contracts import refs
    from nip.knowledge.story import kendall_tau

    truth = {refs.scene(ep, sc.no): sc for ep, scs in show.episodes.items() for sc in scs}
    pos = {p["ref"]: p for p in res["positions"]}
    m: dict[str, float] = {
        "story/tau": kendall_tau(
            {r: s.story_seq for r, s in truth.items()}, {r: p["story_seq"] for r, p in pos.items()}
        )
    }
    present = [r for r, s in truth.items() if s.marker is None]
    m["story/day_acc_present"] = sum(
        pos[r]["story_day"] == truth[r].story_day for r in present
    ) / len(present)
    for name, marker, tag in (
        ("flashback", "flashback", "flashback"),
        ("simultaneous", "same_time", "intercut"),
    ):
        want = {r for r, s in truth.items() if s.marker == marker}
        got = {r for r, p in pos.items() if tag in p["markers"]}
        m[f"story/{name}_recall"] = len(want & got) / max(len(want), 1)
        m[f"story/{name}_precision"] = len(want & got) / max(len(got), 1)
    m["story/inferred_scenes"] = float(sum(p["inferred"] for p in pos.values()))
    m["story/ambiguous"] = float(res["ambiguous"])
    m["story/llm_calls"] = float(res["llm_calls"])
    asked = [v for v in res["verdicts"]]
    m["story/llm_failed"] = float(sum("verdict" not in v for v in asked))
    m["story/llm_seconds"] = float(sum(v.get("seconds", 0) for v in asked))
    right = 0
    for v in asked:
        if "verdict" not in v:
            continue
        kind = re.sub(r"[^a-z_]", "", notes.get(v["ref"], "other").split(",")[0])
        ok = v["verdict"]["relation"] == truth_relation(show, v["ref"])
        right += ok
        m[f"story/asked/{kind}"] = m.get(f"story/asked/{kind}", 0) + 1
        m[f"story/right/{kind}"] = m.get(f"story/right/{kind}", 0) + ok
    m["story/verdict_acc"] = right / max(res["llm_calls"], 1) if res["llm_calls"] else float("nan")
    if truth_arm:
        m.pop("story/verdict_acc")
    return {k: v for k, v in m.items() if v == v}


def arm_show(show: Show, res: dict[str, Any]) -> Show:
    """`show` with the arm's story_seq and markers in place of the truth's."""
    from nip.contracts import refs

    s = show.model_copy(deep=True)
    pos = {p["ref"]: p for p in res["positions"]}
    for ep, scs in s.episodes.items():
        for sc in scs:
            p = pos[refs.scene(ep, sc.no)]
            sc.story_seq = p["story_seq"]
            sc.marker = (
                "flashback"
                if "flashback" in p["markers"]
                else "same_time"
                if "intercut" in p["markers"]
                else None
            )
    return s


def truth_positions(show: Show) -> dict[str, Any]:
    from nip.contracts import refs

    pos = [
        {
            "ref": refs.scene(ep, sc.no),
            "markers": [{"flashback": "flashback", "same_time": "intercut"}[sc.marker]]
            if sc.marker
            else [],
            "story_day": sc.story_day,
            "story_seq": sc.story_seq,
            "inferred": False,
        }
        for ep, scs in show.episodes.items()
        for sc in scs
    ]
    return {"positions": pos, "ambiguous": 0, "llm_calls": 0, "verdicts": []}


@contextmanager
def scratch_db(admin_url: str) -> Iterator[Any]:
    """A throwaway Postgres database with the schema; yields an engine."""
    from sqlalchemy import create_engine, make_url, text

    from nip.store import schema

    name = "nip_exp007"
    url = admin_url.replace("postgresql://", "postgresql+psycopg://", 1)
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {name}"))
    engine = create_engine(make_url(url).set(database=name))
    try:
        with engine.begin() as c:
            c.execute(text("CREATE EXTENSION vector"))
            c.execute(text("CREATE EXTENSION btree_gist"))
            schema.metadata.create_all(c)
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))


def run_plot_rules(engine: Any, injected: Path, show: Show, res: dict[str, Any]) -> list[Any]:
    """Load `injected` (scripts) with the arm's story order and the oracle facts, run the four
    Layer 1 rules; flags."""
    from sqlalchemy import select, update

    from eval.exp.layer1_oracle import build_store, run_rules
    from nip.store import schema

    arm = arm_show(show, res)
    build_store(engine, injected, arm)
    inferred = [p["ref"] for p in res["positions"] if p["inferred"]]
    with engine.begin() as c:
        for ref in inferred:
            ep, _, no = ref.split("/")
            c.execute(
                update(schema.scene)
                .where(
                    schema.scene.c.script_scene_no == no,
                    schema.scene.c.episode_id
                    == select(schema.episode.c.id)
                    .where(schema.episode.c.ref == ep)
                    .scalar_subquery(),
                )
                .values(story_inferred=True)
            )
    return run_rules(engine, list(show.episodes))[0]


def clear_runs(variant: str, seed: int) -> None:
    from mlflow import MlflowClient

    client = MlflowClient(TRACKING_URI)
    e = client.get_experiment_by_name(SET)
    for r in client.search_runs(
        [e.experiment_id] if e else [],
        filter_string=f"tags.variant = '{variant}' and tags.seed = '{seed}'",
    ):
        client.delete_run(r.info.run_id)


@app.command()
def score(
    admin_url: Annotated[str | None, typer.Option(help="Default: $NIP_TEST_DATABASE_URL")] = None,
) -> None:
    """Every (variant, seed, arm): plot rules over the arm's story order, P/R via `eval.report.run`,
    story metrics added to the same MLflow run."""
    from mlflow import MlflowClient

    from eval import report

    url = admin_url or os.environ["NIP_TEST_DATABASE_URL"]
    for variant in VARIANTS:
        for seed in SEEDS:
            root = _dir(variant, seed)
            show = read_show(root / "injected")
            notes = json.loads((root / "notes.json").read_text(encoding="utf-8"))
            for arm, name in ARMS.items():
                f = root / f"{arm}.json"
                if arm != "truth" and not f.exists():
                    typer.echo(f"{variant} seed{seed}: no {f.name}, arm {name} skipped")
                    continue
                res = truth_positions(show) if arm == "truth" else json.loads(f.read_text("utf-8"))
                with scratch_db(url) as engine:
                    flags = run_plot_rules(engine, root / "injected", show, res)
                flag_file = OUT / "flags" / f"{variant}-{arm}-seed{seed}.jsonl"
                flag_file.parent.mkdir(parents=True, exist_ok=True)
                flag_file.write_text("".join(x.model_dump_json() + "\n" for x in flags), "utf-8")
                tag = f"{variant}-{name}"
                clear_runs(tag, seed)
                report.run(
                    set_=SET, flags=flag_file, labels=[root / "labels"], exp="EXP-007",
                    variant=tag, seed=seed, plan=None, content_hours=None, gpu_seconds=None,
                    wall_seconds=None, coverage=None, baseline=False,
                    param=[f"story_variant={variant}", f"arm={name}", f"model={MODEL}"]
                    + [f"story_prompt=knowledge.story.{arm[4:] or 'v1'}"] * (arm[:3] == "llm"),
                    tracking_uri=TRACKING_URI, out_dir=OUT / "runs",
                )  # fmt: skip
                client = MlflowClient(TRACKING_URI)
                e = client.get_experiment_by_name(SET)
                assert e
                [run] = client.search_runs(
                    [e.experiment_id],
                    filter_string=f"tags.variant = '{tag}' and tags.seed = '{seed}'",
                )
                for k, v in story_metrics(show, notes, res, arm == "truth").items():
                    client.log_metric(run.info.run_id, k, v)
                typer.echo(f"{tag} seed{seed}: {len(flags)} flags")


if __name__ == "__main__":
    sys.exit(app())
