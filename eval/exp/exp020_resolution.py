"""EXP-020 (W1 part): entity resolution, registry IDs as an enum vs free-text names resolved
afterwards with rapidfuzz. Also the extraction pass whose raw events EXP-006 re-thresholds.

    # GPU: hold data/gpu.lock while vLLM is up (phase2-plan.md > GPU contention)
    DC="docker compose -f compose.yaml -f compose.dev.yaml -f eval/exp/exp001.compose.yaml"
    $DC up -d --wait ray-head
    $DC exec ray-head python3 -m eval.exp.exp020_resolution up    # probe -> plan -> deploy
    export NIP_SERVE_URL=http://127.0.0.1:8001 NIP_DATABASE_URL=... NIP_S3_ENDPOINT=...
    uv run python -m eval.exp.exp020_resolution extract --variant enum --record
    ... extract --variant free-text
    $DC exec ray-head python3 -m eval.exp.exp020_resolution down  # teardown, VRAM back to idle
    uv run python -m eval.exp.exp020_resolution score   # CPU: metrics -> MLflow
    uv run nip eval compare --exp EXP-020 --md --tracking-uri sqlite:///data/mlflow/mlflow.db

Set (rulings R2/R3): the synthetic show (seed 1, 6 x 25 scenes), ingested into the store as
`synthetic-show`; truth = `truth.json` (labeller: generator). `extract` runs the shipped path
(store scenes and speakers, registry from the bible rows, `extract_scene`,
`save_events`) inside one transaction that is rolled back, so the store keeps no events. Events are
saved with grounding threshold 0 (every event resolved, so EXP-006 can label all of them); the
grounding score is kept per event. The enum arm's calls are recorded into tests/fixtures/llm
(D-020).

Metrics, over events whose quote scores >= 90 (the shipped grounding threshold):
- resolution_accuracy: among events whose (line, predicate) has truth facts, the share of
  arguments (subject; object when truth has one) resolved to a truth entity of that line+predicate;
  split by how the line names the expected entity: by name, only by nickname/description
  (`acc_alias`), or not at all (`acc_implicit`, e.g. the speaker).
- mention_recall_{name,nickname,description}: on lines with grounded events, the share of the
  generator's mentions (by kind of surface) whose entity one of the line's events references.
- fact precision / recall against truth facts (line, predicate, subject, object), precision over
  the predicates truth covers (present_at, learns, references, holds, state, setup, payoff).
"""

import json
import os
import time
from pathlib import Path
from typing import Annotated, Any

import typer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "exp020"
SHOW_DIR = OUT / "show"
TRACKING_URI = f"sqlite:///{(ROOT / 'data' / 'mlflow' / 'mlflow.db').as_posix()}"
SHOW, SEED, VARIANT = "synthetic-show", 1, "qwen3.5-4b-awq"
ARMS = {"enum": True, "free-text": False}
GROUNDING = 90.0
TRUTH_PREDICATES = {"present_at", "learns", "references", "holds", "state", "setup", "payoff"}
app = typer.Typer(no_args_is_help=True)


# ---- serving (run inside ray-head) -------------------------------------------------------------
@app.command()
def up() -> None:
    """Probe -> planner -> deploy the text_llm app (the shipped path); prints the decision."""
    from nip.contracts import Slot
    from nip.runtime.catalog import load_catalog
    from nip.runtime.planner import plan
    from nip.runtime.probe import probe
    from nip.runtime.serving import apps, deploy, gpu_used_mib, ray_serve

    cat, inv = load_catalog(), probe()
    idle = gpu_used_mib()
    p = plan(inv, cat, {Slot.TEXT_LLM: 1})
    if Slot.TEXT_LLM in p.skipped_slots:
        typer.echo(f"planner skipped text_llm: {p.warnings}", err=True)
        raise typer.Exit(1)
    [a] = apps(p, cat, inv, p.groups[0].slots)
    secs = deploy([a], ray_serve())
    d = p.decisions[Slot.TEXT_LLM].model_dump(exclude_none=True)
    (Path("/tmp") / "exp020-idle.txt").write_text(str(idle))
    typer.echo(json.dumps({"load_s": secs, "idle_mib": idle, "decision": d, "args": a.vllm_args}))


@app.command()
def down() -> None:
    """Delete the app and wait for VRAM back to the idle level read by `up`."""
    from nip.contracts import Slot
    from nip.runtime.catalog import load_catalog
    from nip.runtime.planner import plan
    from nip.runtime.probe import probe
    from nip.runtime.serving import apps, ray_serve, teardown

    cat, inv = load_catalog(), probe()
    p = plan(inv, cat, {Slot.TEXT_LLM: 1})
    idle_f = Path("/tmp") / "exp020-idle.txt"
    idle = int(idle_f.read_text()) if idle_f.exists() else None
    secs = teardown(apps(p, cat, inv, p.groups[0].slots), ray_serve(), idle_mib=idle)
    typer.echo(json.dumps({"unload_s": secs, "idle_mib": idle}))


# ---- extraction pass (host) --------------------------------------------------------------------
def ensure_ingested(engine: Any, s3: Any) -> None:
    """Ingest the seed-1 synthetic show once (idempotent by sha256)."""
    from eval.synthetic import build, write_show
    from nip.store.ingest import ingest_files

    show = build(SEED)
    write_show(show, SHOW_DIR)
    with engine.begin() as conn:
        ingest_files(conn, s3, show=SHOW, episode=None, files=[(None, SHOW_DIR / "bible.yaml")])
        for ep in show.episodes:
            f = SHOW_DIR / f"{ep}.fountain"
            ingest_files(conn, s3, show=SHOW, episode=ep, files=[(None, f)])


def truth_ids(conn: Any, show_id: int, show: Any) -> dict[int, str | None]:
    """entity row id -> truth entity id (bible id, secret id, name; candidates by fuzzy name)."""
    from rapidfuzz import fuzz, process, utils
    from sqlalchemy import select

    from nip.store import schema

    names = [(n, e.id) for e in show.entities for n in (e.name, *(a for a, _ in e.aliases))]
    by_name = {n.casefold(): i for n, i in names}
    out: dict[int, str | None] = {}
    for r in conn.execute(select(schema.entity).where(schema.entity.c.show_id == show_id)):
        tid = r.attributes.get("bible_id") or by_name.get(r.canonical_name.casefold())
        if tid is None and r.kind == "secret":
            tid = r.canonical_name
        if tid is None:
            hit = process.extractOne(
                r.canonical_name,
                [n for n, _ in names],
                scorer=fuzz.WRatio,
                processor=utils.default_process,
                score_cutoff=90,
            )
            tid = names[hit[2]][1] if hit else None
        out[r.id] = tid
    return out


@app.command()
def extract(
    variant: Annotated[str, typer.Option(help="enum | free-text")] = "enum",
    record: Annotated[bool, typer.Option(help="record responses into tests/fixtures/llm")] = False,
    episodes: Annotated[str, typer.Option(help="comma list, default all")] = "",
    replay: Annotated[
        bool, typer.Option(help="re-resolve and re-score the saved raw events, no model calls")
    ] = False,
) -> None:
    """One extraction pass of an arm (or, with --replay, the shipped resolution and grounding
    code re-applied to the arm's saved raw events; wall times and failures are kept)."""
    from sqlalchemy import create_engine, select

    from eval.synthetic import build
    from nip.knowledge.extract import (
        extract_scene,
        load_registry,
        load_scenes,
        save_events,
    )
    from nip.knowledge.grounding import score
    from nip.runtime.clients import LLMClient
    from nip.runtime.clients.stub import FIXTURES
    from nip.store import objects, schema
    from nip.store.db import database_url
    from nip.store.load import episode_row

    enum = ARMS[variant]
    if record:
        os.environ["NIP_LLM_RECORD_DIR"] = str(FIXTURES)
    engine = create_engine(database_url().replace("postgresql://", "postgresql+psycopg://", 1))
    s3 = objects.client()
    ensure_ingested(engine, s3)
    show = build(SEED)
    eps = episodes.split(",") if episodes else list(show.episodes)
    d = OUT / variant
    saved: dict[str, list[dict[str, Any]]] = {}
    if replay:
        model_keys = (
            "line",
            "quote",
            "predicate",
            "subject",
            "subject_name",
            "object",
            "object_name",
            "value",
            "confidence",
        )  # the model's fields only
        for x in (d / "events.jsonl").read_text(encoding="utf-8").splitlines():
            e = json.loads(x)
            saved.setdefault(e["scene"], []).append(
                {"scene": e["scene"]} | {k: e.get(k) for k in model_keys}
            )
    llm = LLMClient(VARIANT)
    events: list[dict[str, Any]] = []
    timing: list[float] = []
    failures: list[str] = []
    with engine.connect() as conn:
        tx = conn.begin()
        show_id = conn.execute(
            select(schema.show.c.id).where(schema.show.c.slug == SHOW)
        ).scalar_one()
        registry = load_registry(conn, show_id)
        for ep in eps:
            row = episode_row(conn, SHOW, ep)
            for sc in load_scenes(conn, ep, row.id):
                t = time.perf_counter()
                try:
                    raw = (
                        saved.get(sc.ref, []) if replay else extract_scene(llm, sc, registry, enum)
                    )
                except Exception as e:  # recorded as a failed unit, as the stage would
                    failures.append(f"{sc.ref}: {type(e).__name__}: {str(e)[:300]}")
                    continue
                finally:
                    timing.append(time.perf_counter() - t)
                save_events(conn, show_id, sc, raw, threshold=0)
                text = {ln.seq: ln.text for ln in sc.lines}
                no = sc.ref.rsplit("/", 1)[1]
                for i, ev in enumerate(raw):
                    lt = text[ev["line"]]
                    ev |= {
                        "id": f"{sc.ref}#{i}",
                        "line_ref": f"{ep}/line/{no}.{ev['line']}",
                        "line_text": lt,
                        "score": score(ev["quote"], lt),
                    }
                events += raw
                print(f"{sc.ref}: {len(raw)} events, {timing[-1]:.1f} s", flush=True)
        ids = truth_ids(conn, show_id, show)
        tx.rollback()
    for ev in events:
        ev["subject_truth"] = ids.get(ev.get("subject_id"))  # type: ignore[arg-type]
        ev["object_truth"] = ids.get(ev.get("object_id"))  # type: ignore[arg-type]
    d.mkdir(parents=True, exist_ok=True)
    (d / "events.jsonl").write_text(
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8"
    )
    if replay:  # the pass's own wall times and failures stand
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        meta["replayed"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        (d / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        typer.echo(f"replayed {len(events)} events")
        return
    meta = {
        "variant": variant,
        "model": VARIANT,
        "episodes": eps,
        "scenes": len(timing),
        "failures": failures,
        "wall_s": round(sum(timing), 1),
        "s_per_scene": round(sum(timing) / max(len(timing), 1), 2),
    }
    (d / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    typer.echo(json.dumps(meta)[:2000])


# ---- scoring (CPU) -----------------------------------------------------------------------------
def truth_index(
    show: Any,
) -> tuple[dict[str, set[tuple[Any, ...]]], dict[str, dict[str, set[str]]]]:
    """line ref -> {(predicate, subject, object)}, and line ref -> {entity: mention kinds}."""
    facts: dict[str, set[tuple[Any, ...]]] = {}
    mentions: dict[str, dict[str, set[str]]] = {}
    for ep, scenes in show.episodes.items():
        for sc in scenes:
            for seq, ln in enumerate(sc.lines, 1):
                ref = f"{ep}/line/{sc.no}.{seq}"
                facts[ref] = {(f.predicate, f.subject, f.object) for f in ln.facts}
                for m in ln.mentions:
                    mentions.setdefault(ref, {}).setdefault(m.entity, set()).add(m.kind)
    return facts, mentions


def metrics(events: list[dict[str, Any]], show: Any) -> dict[str, float]:
    facts, mentions = truth_index(show)
    kept = [e for e in events if e["score"] >= GROUNDING and e.get("subject_id") is not None]
    got = {(e["line_ref"], e["predicate"], e["subject_truth"], e["object_truth"]) for e in kept}
    truth = {(ref, *t) for ref, ts in facts.items() for t in ts}
    scored = {g for g in got if g[1] in TRUTH_PREDICATES}
    m: dict[str, float] = {
        "events_raw": len(events),
        "events_grounded": len(kept),
        "fact_precision": len(scored & truth) / max(len(scored), 1),
        "fact_recall": len(got & truth) / max(len(truth), 1),
    }
    buckets: dict[str, list[bool]] = {"all": [], "name": [], "alias": [], "implicit": []}
    for e in kept:
        ts = [t for t in facts.get(e["line_ref"], ()) if t[0] == e["predicate"]]
        if not ts:
            continue
        args = [("subject_truth", {t[1] for t in ts})]
        if any(t[2] is not None for t in ts):
            args.append(("object_truth", {t[2] for t in ts}))
        for field, want in args:
            ok = e[field] in want
            buckets["all"].append(ok)
            expected = e[field] if ok else (next(iter(want)) if len(want) == 1 else None)
            if expected is None:
                continue
            kinds = mentions.get(e["line_ref"], {}).get(expected, set())
            b = "name" if "name" in kinds else "alias" if kinds else "implicit"
            buckets[b].append(ok)
    m["resolution_accuracy"] = sum(buckets["all"]) / max(len(buckets["all"]), 1)
    for b in ("name", "alias", "implicit"):
        m[f"acc_{b}"] = sum(buckets[b]) / max(len(buckets[b]), 1)
        m[f"n_args_{b}"] = len(buckets[b])
    m["n_args"] = len(buckets["all"])
    # mention level: on lines with grounded events, is each truth mention's entity referenced by
    # one of the line's events? (Facts never sit on alias-only lines in the synthetic show.)
    linked: dict[str, set[Any]] = {}
    for e in kept:
        linked.setdefault(e["line_ref"], set()).update((e["subject_truth"], e["object_truth"]))
    for kind in ("name", "nickname", "description"):
        hits = [
            ent in linked[ref]
            for ref, ents in mentions.items()
            if ref in linked
            for ent, kinds in ents.items()
            if kind in kinds
        ]
        m[f"mention_recall_{kind}"] = sum(hits) / max(len(hits), 1)
        m[f"n_mentions_{kind}"] = len(hits)
    return m


@app.command("score")
def score_cmd() -> None:
    """Metrics per arm from data/exp020/<arm>/events.jsonl -> MLflow (one run per arm)."""
    import mlflow

    from eval.synthetic import build

    show = build(SEED)
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("exp020-resolution")
    for arm in ARMS:
        d = OUT / arm
        if not (d / "events.jsonl").exists():
            continue
        events = [
            json.loads(x) for x in (d / "events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        m = metrics(events, show) | {
            "s_per_scene": meta["s_per_scene"],
            "failed_scenes": len(meta["failures"]),
        }
        tags = {"exp": "EXP-020", "variant": arm, "seed": str(SEED), "labeller": "generator"}
        _clear("exp020-resolution", "EXP-020", arm)
        with mlflow.start_run(run_name=f"EXP-020-{arm}"):
            mlflow.set_tags(tags)
            mlflow.log_params(
                {
                    "model": VARIANT,
                    "grounding_threshold": GROUNDING,
                    "set": f"{SHOW} seed {SEED}",
                    "scenes": meta["scenes"],
                }
            )
            mlflow.log_metrics(m)
        typer.echo(f"{arm}: {json.dumps(m)}")


def _clear(experiment: str, exp: str, variant: str) -> None:
    """Delete earlier runs with these tags, so a re-score does not duplicate a seed."""
    from mlflow import MlflowClient

    client = MlflowClient(TRACKING_URI)
    e = client.get_experiment_by_name(experiment)
    for r in client.search_runs(
        [e.experiment_id] if e else [],
        filter_string=f"tags.exp = '{exp}' and tags.variant = '{variant}'",
    ):
        client.delete_run(r.info.run_id)


if __name__ == "__main__":
    app()
