"""2.1B extraction passes on the real model and what is scored from them:
- the runaway rate (failed scenes per extraction schema `--mode`: `before` = 2.1's, `cap` = events
  capped per scene line, `shipped` = cap + `line` an enum of the scene's lines),
- EXP-020's rule-precision half: the Layer 1 `plot.*` rules on extracted facts, enum vs free text,
  on the 2.9A plot-L1 injected shows and their clean twins (3 seeds),
- fact precision / recall per pass (EXP-005 8k arm, EXP-018 per KV arm).

    # GPU, under data/gpu.lock, with an arm deployed (eval.exp.exp018_kv up --arm default-8k):
    NIP_SERVE_URL=http://127.0.0.1:8001 uv run python -m eval.exp.exp020_rules extract \
        --cache data/exp020/rules/default-8k/enum.jsonl --arm enum --seeds 1,2,3
    # CPU: store + consolidation + rules per seed, clean and injected; then MLflow
    uv run python -m eval.exp.exp020_rules flags --arm enum \
        --cache data/exp020/rules/default-8k/enum.jsonl
    uv run python -m eval.exp.exp020_rules score --out data/exp020/rules/default-8k --arm enum

Shows: `data/layer1/inject/mvp/seed{N}/synthetic-show/{clean,injected}` (2.9A, `nip eval inject
--set mvp --seed N --only plot`), labels `.../labels/synthetic-show.jsonl` (12 per seed). Every show
is ingested into a throwaway database (scratch DB per call, dropped afterwards). Model replies are
cached per call key (sha256 of variant, prompt, schema: `stub.record_key`), so a scene the injector
did not touch is extracted once and both twins see the same reply; failures are cached too.
Story order: truth `story_seq` + markers (as 2.3's oracle benchmark), so only the facts vary.
Calls run `--concurrency` at a time (the shipped stage sends one at a time; the same concurrency is
used for every pass compared here).
"""

import json
import os
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path
from secrets import token_hex
from typing import Annotated, Any

import typer
from sqlalchemy import Engine, create_engine, make_url, select, text, update

from eval.exp.exp020_resolution import metrics as fact_metrics
from eval.exp.exp020_resolution import truth_ids
from eval.exp.layer1_oracle import MARKERS, SLUG, FakeS3, run_rules
from eval.synthetic import Show, read_show

ROOT = Path(__file__).resolve().parents[2]
INJECT = ROOT / "data" / "layer1" / "inject" / "mvp"
RUNS = ROOT / "data" / "exp020" / "runs"
TRACKING_URI = f"sqlite:///{(ROOT / 'data' / 'mlflow' / 'mlflow.db').as_posix()}"
VARIANT = "qwen3.5-4b-awq"
ARMS = {"enum": True, "free-text": False}
app = typer.Typer(no_args_is_help=True)


def show_dir(seed: int, which: str) -> Path:
    return INJECT / f"seed{seed}" / "synthetic-show" / which


@contextmanager
def scratch_db() -> Iterator[Engine]:
    """An empty database with the schema (NIP_TEST_DATABASE_URL, else NIP_DATABASE_URL, needs
    CREATE DATABASE), dropped on exit."""
    from nip.store import schema

    url = os.environ.get("NIP_TEST_DATABASE_URL") or os.environ["NIP_DATABASE_URL"]
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    name = f"nip_21b_{token_hex(4)}"
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
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
        admin.dispose()


def load(engine: Engine, d: Path) -> tuple[Show, int, list[Any], dict[str, list[Any]]]:
    """Ingest bible + episodes, truth story order; (show, show id, registry, scenes per episode)."""
    from nip.knowledge.extract import load_registry, load_scenes
    from nip.store import schema
    from nip.store.ingest import ingest_files
    from nip.store.load import episode_row

    show, s3 = read_show(d), FakeS3()
    with engine.begin() as conn:
        ingest_files(conn, s3, show=SLUG, episode=None, files=[(None, d / "bible.yaml")])
        for ep in show.episodes:
            ingest_files(conn, s3, show=SLUG, episode=ep, files=[(None, d / f"{ep}.fountain")])
        show_id = conn.execute(select(schema.show.c.id)).scalar_one()
        scenes = {}
        for ep, truth_scenes in show.episodes.items():
            row = episode_row(conn, SLUG, ep)
            for sc in truth_scenes:
                conn.execute(
                    update(schema.scene)
                    .where(schema.scene.c.episode_id == row.id,
                           schema.scene.c.script_scene_no == sc.no)
                    .values(story_seq=sc.story_seq, markers=MARKERS.get(sc.marker or "", []))
                )  # fmt: skip
            scenes[ep] = load_scenes(conn, ep, row.id)
        registry = load_registry(conn, show_id)
    return show, show_id, registry, scenes


def call(sc: Any, registry: list[Any], enum: bool, mode: str) -> tuple[str, type, str]:
    """(prompt, schema, cache key) of one scene under schema `mode` (before | cap | shipped)."""
    from nip.knowledge.extract import EVENTS_PER_LINE, event_schema, request
    from nip.runtime.clients.stub import record_key

    prompt, schema = request(sc, registry, enum)
    keys = [e.key for e in registry] if enum else None
    if mode == "before":
        schema = event_schema(keys)
    elif mode == "cap":
        schema = event_schema(keys, EVENTS_PER_LINE * len(sc.lines))
    return prompt, schema, record_key(VARIANT, prompt, schema, None)


def read_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {
        r["key"]: r for x in path.read_text(encoding="utf-8").splitlines() if (r := json.loads(x))
    }


@app.command()
def extract(
    cache: Annotated[Path, typer.Option(help="JSONL of replies by call key (appended)")],
    arm: Annotated[str, typer.Option(help="enum | free-text")] = "enum",
    seeds: Annotated[str, typer.Option()] = "1,2,3",
    which: Annotated[str, typer.Option(help="clean,injected")] = "clean,injected",
    mode: Annotated[str, typer.Option(help="schema: before | cap | shipped")] = "shipped",
    concurrency: int = 4,
    record: Annotated[bool, typer.Option(help="record replies into tests/fixtures/llm")] = False,
) -> None:
    """Extract every scene not yet in `cache` (real model at NIP_SERVE_URL)."""
    from nip.knowledge.extract import MAX_TOKENS
    from nip.runtime.clients import LLMClient
    from nip.runtime.clients.stub import FIXTURES

    if record:
        os.environ["NIP_LLM_RECORD_DIR"] = str(FIXTURES)
    enum, done = ARMS[arm], read_cache(cache)
    todo: dict[str, tuple[Any, ...]] = {}
    for seed in map(int, seeds.split(",")):
        for w in which.split(","):
            with scratch_db() as engine:
                _, _, registry, scenes = load(engine, show_dir(seed, w))
            for sc in (s for ss in scenes.values() for s in ss):
                prompt, schema, key = call(sc, registry, enum, mode)
                if key not in done:
                    todo.setdefault(key, (sc, prompt, schema))
    llm = LLMClient(VARIANT)
    typer.echo(f"{len(todo)} calls ({len(done)} cached), concurrency {concurrency}")

    def one(key: str, sc: Any, prompt: str, schema: type) -> dict[str, Any]:
        t = time.perf_counter()
        row: dict[str, Any] = {"key": key, "scene": sc.ref, "arm": arm, "mode": mode}
        try:
            ctx = {"lines": {ln.seq for ln in sc.lines}}
            out = llm.complete(prompt, schema, max_tokens=MAX_TOKENS, context=ctx)
            row["events"] = [e.model_dump(mode="json") for e in out.events]
            row["capped"] = len(row["events"]) >= 4 * len(sc.lines) if mode != "before" else False
        except Exception as e:  # a failed unit, as the stage records it
            row["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        row["s"] = round(time.perf_counter() - t, 2)
        return row

    cache.parent.mkdir(parents=True, exist_ok=True)
    t0, n_fail = time.perf_counter(), 0
    with ThreadPoolExecutor(concurrency) as ex, cache.open("a", encoding="utf-8") as f:
        futs = [ex.submit(one, k, *v) for k, v in todo.items()]
        for i, fut in enumerate(as_completed(futs), 1):
            row = fut.result()
            n_fail += "error" in row
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            typer.echo(f"[{i}/{len(futs)}] {row['scene']}: "
                       f"{row.get('error', len(row.get('events', [])))} {row['s']} s")  # fmt: skip
    wall = round(time.perf_counter() - t0, 1)
    meta = {"calls": len(todo), "failed": n_fail, "wall_s": wall, "arm": arm, "mode": mode,
            "seeds": seeds, "which": which, "concurrency": concurrency,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S")}  # fmt: skip
    with cache.with_suffix(".passes.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(meta) + "\n")
    typer.echo(json.dumps(meta))


def build(
    engine: Engine, d: Path, cached: dict[str, dict[str, Any]], enum: bool, mode: str = "shipped"
) -> tuple[Show, list[dict[str, Any]], dict[str, int]]:
    """The show's store from cached replies (shipped save_events / save_speakers / consolidation);
    (show, annotated raw events, counts)."""
    from nip.knowledge.consolidate import consolidate_show
    from nip.knowledge.extract import save_events, save_speakers
    from nip.knowledge.grounding import score

    show, show_id, registry, scenes = load(engine, d)
    events: list[dict[str, Any]] = []
    n = {"scenes": 0, "failed": 0, "missing": 0, "capped": 0}
    with engine.begin() as conn:
        for ep, ss in scenes.items():
            for sc in ss:
                n["scenes"] += 1
                row = cached.get(call(sc, registry, enum, mode)[2])
                if row is None or "error" in row:
                    n["missing" if row is None else "failed"] += 1
                    continue
                n["capped"] += bool(row.get("capped"))
                raw = [{"scene": sc.ref, **e} for e in row["events"]]
                save_events(conn, show_id, sc, raw)
                save_speakers(conn, show_id, sc)
                text_ = {ln.seq: ln.text for ln in sc.lines}
                no = sc.ref.rsplit("/", 1)[1]
                for ev in raw:
                    ev |= {"line_ref": f"{ep}/line/{no}.{ev['line']}",
                           "score": score(ev["quote"], text_[ev["line"]])}  # fmt: skip
                events += raw
        n["facts"] = consolidate_show(conn, show_id)
        ids = truth_ids(conn, show_id, show)
    for ev in events:
        ev["subject_truth"] = ids.get(ev.get("subject_id"))  # type: ignore[arg-type]
        ev["object_truth"] = ids.get(ev.get("object_id"))  # type: ignore[arg-type]
    return show, events, n


@app.command()
def flags(
    cache: Annotated[Path, typer.Option()],
    arm: Annotated[str, typer.Option()] = "enum",
    seeds: Annotated[str, typer.Option()] = "1,2,3",
    which: Annotated[str, typer.Option()] = "clean,injected",
    mode: str = "shipped",
) -> None:
    """Per seed and twin: store from the cached replies, consolidation, the four plot rules with
    verification -> `<cache dir>/<arm>/seed{N}-{which}.flags.jsonl` + `.facts.json`."""
    cached, out = read_cache(cache), cache.parent / arm
    out.mkdir(parents=True, exist_ok=True)
    for seed in map(int, seeds.split(",")):
        for w in which.split(","):
            with scratch_db() as engine:
                show, events, n = build(engine, show_dir(seed, w), cached, ARMS[arm], mode)
                got, _ = run_rules(engine, list(show.episodes))
            m = (
                fact_metrics(events, show)
                | n
                | {
                    "dropped_" + (k or "none").replace(" ", "_"): sum(
                        e.get("dropped") == k for e in events
                    )
                    for k in (None, "quote", "zero confidence", "duplicate", "argument type")
                }
            )
            by: dict[str, int] = {}
            for fl in got:
                by[str(fl.check)] = by.get(str(fl.check), 0) + 1
            stem = out / f"seed{seed}-{w}"
            stem.with_suffix(".flags.jsonl").write_text(
                "".join(fl.model_dump_json() + "\n" for fl in got), encoding="utf-8"
            )
            stem.with_suffix(".facts.json").write_text(json.dumps(m | {"flags": by}, indent=1))
            stem.with_suffix(".events.jsonl").write_text(
                "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8"
            )
            typer.echo(f"{arm} seed {seed} {w}: flags {by}; facts P {m['fact_precision']:.3f} "
                       f"R {m['fact_recall']:.3f}; {n}")  # fmt: skip


@app.command()
def score(
    out: Annotated[Path, typer.Option(help="the cache's directory")],
    arm: Annotated[str, typer.Option()] = "enum",
    seeds: Annotated[str, typer.Option()] = "1,2,3",
    exp: Annotated[str, typer.Option(help="tag of the injected-show runs")] = "EXP-020-rules",
    variant: Annotated[str | None, typer.Option(help="default: the arm")] = None,
) -> None:
    """`nip eval run` per seed: injected flags vs the 12 planted labels (set plot-l1), and the
    clean twin's flags vs no labels (set plot-l1-clean; every flag there is a false positive)."""
    from eval.report import run

    empty = out / "no-labels.jsonl"
    empty.write_text("", encoding="utf-8")
    for seed in map(int, seeds.split(",")):
        labels = INJECT / f"seed{seed}" / "labels" / "synthetic-show.jsonl"
        for w, set_, tag, lab in (("injected", "plot-l1", exp, labels),
                                  ("clean", "plot-l1-clean", f"{exp}-clean", empty)):  # fmt: skip
            stem = out / arm / f"seed{seed}-{w}"
            run(set_=set_, flags=stem.with_suffix(".flags.jsonl"), labels=[lab], exp=tag,
                variant=variant or arm, seed=seed, plan=None, content_hours=None,
                gpu_seconds=None, wall_seconds=None, coverage=None, baseline=False,
                param=None, tracking_uri=TRACKING_URI, out_dir=RUNS)  # fmt: skip


@app.command()
def facts(
    out: Annotated[Path, typer.Option(help="the cache's directory")],
    exp: Annotated[str, typer.Option()],
    variant: Annotated[str, typer.Option()],
    arm: Annotated[str, typer.Option()] = "enum",
    seeds: Annotated[str, typer.Option()] = "1",
) -> None:
    """Fact precision / recall and drop counts of the clean twin -> one MLflow run per seed."""
    import mlflow

    from eval.exp.exp020_resolution import _clear

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("exp2.1b-facts")
    _clear("exp2.1b-facts", exp, variant)
    for seed in map(int, seeds.split(",")):
        m = json.loads((out / arm / f"seed{seed}-clean.facts.json").read_text())
        with mlflow.start_run(run_name=f"{exp}-{variant}-s{seed}"):
            mlflow.set_tags(
                {"exp": exp, "variant": variant, "seed": str(seed), "labeller": "generator"}
            )
            mlflow.log_params(
                {"model": VARIANT, "arm": arm, "set": f"synthetic seed {seed} (clean)"}
            )
            mlflow.log_metrics({k: float(v) for k, v in m.items() if isinstance(v, int | float)})
        typer.echo(
            f"{exp} {variant} seed {seed}: P {m['fact_precision']:.3f} R {m['fact_recall']:.3f}"
        )


if __name__ == "__main__":
    app()
