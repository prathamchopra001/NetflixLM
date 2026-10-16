"""Runs: the store-backed `nip run --show S --episodes E…` and the file-mode `run_pipeline`.

Store run (`run_store`; R8: synchronous and in-process, the queue and controller come later):
1. Prepare, per episode: the inputs registered by `nip ingest` (activation-matrix columns) and the
   active checks of every agent package in `AGENTS`. An unknown episode or an unusable rule pack is
   INPUT_REJECTED and nothing is written.
2. `plan` + `run` rows, committed (the run is visible as `running`).
3. Per episode, every stage of `STAGES` in order, all in ONE transaction for the whole run: every
   episode commits, or (on an exception) none does and the run is marked `failed` (re-raised).
4. Commit with status `completed`, or `completed_with_gaps` when any work unit failed. Only then are
   artifacts published (`runs/{run_id}/plan.json`, `runs/{run_id}/{ep}/report.json`, `--out-dir`),
   so a failed run leaves no report.

Stage contract. A stage is `(name, fn)` with `fn(ep: EpisodeRun) -> None`; add one with
`add_stage(name, fn, before="timeline")` (repeated calls keep their call order); `wire()` adds
Phase 2's content stages in order (asr, align, story, extract, consolidate, index; cue_align and
loc.observed after `timeline`) and the script_critic and clearance packages. A stage
- reads and fills `ep` and writes rows through `ep.conn` (the run's transaction);
- reads the Plan as `ep.plan` (e.g. `ep.plan.decisions[Slot.TEXT_LLM].variant`, `ep.plan.plan_id`);
- does each unit of work inside `with ep.unit(stage, key, model_variant=...):`. A unit that
  raises is logged and recorded `failed`, a coverage gap (the run ends `completed_with_gaps`),
  and the stage goes on. Work units are inserted once, after the episode's last stage (stages
  never insert work_unit rows);
- raises only for bugs or lost infrastructure, which fails the whole run.
Report coverage per agent counts units whose stage is a check id; content-stage units only decide
`completed_with_gaps`. Wall time is recorded per stage.

Checks: each package in `AGENTS` exports `CHECKS`, a list of `Check` classes; the pipeline imports
packages, never check modules. A class is used when `cls.active(available)` holds, and it is
constructed with those keyword arguments its `__init__` names, out of: `langs` (target subtitle
languages of the episode), `source_lang`, `conn` (the run's SQLAlchemy connection; None in file
mode), `show` (slug; None in file mode), `episode` (ref).
Every flag must cite at least one stable evidence ref (scene, script line, shot, keyframe,
subtitle cue or clearance item): `fact/` and `asr/` refs churn on re-extraction and are left out
of the fingerprint (R13), so a flag citing only those is dropped at verification ("no stable
evidence ref"). Cite the line or scene a fact came from.

File mode (`run_pipeline`, `nip run-files`): the Phase 1 walking skeleton, files in, JSON out.
"""

import inspect
import json
import logging
import os
import time
from collections import Counter
from collections.abc import Callable, Collection, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from fractions import Fraction
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any

import typer
from sqlalchemy import Connection, Engine, create_engine, or_, select

from nip.agents import localization
from nip.agents.base import Check, Input, emit, run_check
from nip.contracts.flag import CHECK_OWNER, Agent, CheckId, Flag, ProducedBy
from nip.contracts.inventory import HardwareInventory
from nip.contracts.plan import Mode, Objective, Plan, Slot
from nip.contracts.report import Report, ReportPlan, build_report
from nip.contracts.timeline import Timeline
from nip.ingest import Script, SubtitleTrack
from nip.ingest.media import MediaRejected, probe
from nip.store import objects, runs, schema
from nip.store.db import database_url
from nip.store.ingest import FORMATS, InputRejected, ingest
from nip.store.load import episode_row, load_timeline
from nip.timeline.estimate import build_timeline
from nip.timeline.picture import analyze_picture, timeline_config
from nip.verification.verify import verify

__all__ = ["FORMATS", "InputRejected", "ingest", "run_pipeline", "run_store"]

log = logging.getLogger(__name__)

AGENTS: list[ModuleType] = [localization]  # agent packages; wiring appends the others
PLAN_ID = "none"  # file mode computes no Plan
FILE_INPUTS = {"script": Input.SCRIPT, "picture": Input.PICTURE, "bible": Input.BIBLE,
               "glossary": Input.GLOSSARY, "clearance_log": Input.CLEARANCE_LOG}  # fmt: skip


def owner(check: str) -> Agent:
    return CHECK_OWNER[check.split(".")[0]][0]


def build_checks(
    available: Collection[Input], ctx: dict[str, Any], agents: Collection[Agent] | None = None
) -> tuple[list[Check], list[str]]:
    """(active checks, constructed; ids of inactive ones) over every package in AGENTS."""
    checks: list[Check] = []
    skipped: list[str] = []
    for cls in (c for pkg in AGENTS for c in pkg.CHECKS):
        if agents is not None and owner(cls.check) not in agents:
            continue
        if not cls.active(available):
            skipped.append(str(cls.check))
            continue
        params = inspect.signature(cls).parameters
        try:
            checks.append(cls(**{k: v for k, v in ctx.items() if k in params}))
        except ValueError as e:  # e.g. no rule pack for a target language
            raise InputRejected(str(e)) from e
    return checks, skipped


@contextmanager
def _timed(stages: list[dict[str, Any]], name: str) -> Iterator[None]:
    t = time.perf_counter()
    yield
    stages.append({"stage": name, "wall_s": round(time.perf_counter() - t, 4)})


def _jsonl(rows: list[Any]) -> str:
    return "".join(r.model_dump_json() + "\n" for r in rows)


# ---- store mode ------------------------------------------------------------------------------
@dataclass
class EpisodeRun:
    """One episode's state, threaded through STAGES."""

    conn: Connection
    s3: Any
    show: str
    episode: str
    episode_id: int
    run_id: str  # "run_912"
    plan: Plan  # with its plan_id ("plan_42"); stages read model variants from `decisions`
    checks: list[Check]
    skipped: list[str]
    stages: list[dict[str, Any]] = field(default_factory=list)
    tl: Timeline | None = None
    flags: list[Flag] = field(default_factory=list)
    kept: list[Flag] = field(default_factory=list)
    dropped: list[tuple[Flag, str]] = field(default_factory=list)
    units: list[dict[str, Any]] = field(default_factory=list)  # work_unit rows, inserted once
    report: Report | None = None
    # name -> body, uploaded to runs/{run_id}/{ep}/{name} by `publish`, after the commit
    artifacts: dict[str, bytes] = field(default_factory=dict)

    @property
    def timeline(self) -> Timeline:
        assert self.tl is not None, "the timeline stage runs first"
        return self.tl

    @contextmanager
    def unit(self, stage: str, key: str, model_variant: str | None = None) -> Iterator[None]:
        """One work unit: recorded `done`, or `failed` (logged, swallowed: a coverage gap).

        The body runs in a savepoint: a failed unit's rows are rolled back, and a database error
        in it does not poison the run's transaction for the units after it."""
        row: dict[str, Any] = {  # every row has the same keys: one executemany inserts them all
            "stage": stage,
            "unit_key": key,
            "model_variant": model_variant,
            "error": None,
            "started_at": datetime.now(UTC),
        }
        savepoint = self.conn.begin_nested()
        try:
            yield
        except Exception as e:  # ponytail: one attempt; retries with backoff come with models
            savepoint.rollback()
            log.exception("%s unit %s failed", stage, key)
            row |= {"status": "failed", "error": f"{type(e).__name__}: {e}"}
        else:
            savepoint.commit()
            row["status"] = "done"
        self.units.append(row | {"finished_at": datetime.now(UTC)})


def report_plan(plan: Plan) -> ReportPlan:
    judge = plan.decisions.get(Slot.JUDGE_LLM)
    return ReportPlan(
        plan_id=plan.plan_id or PLAN_ID,
        mode=plan.mode,
        judge_independent=bool(judge and judge.independent_family),
    )


def require_stable_refs(flags: list[Flag]) -> tuple[list[Flag], list[tuple[Flag, str]]]:
    """(flags citing a stable ref, [(flag, reason)] for the others: only fact/asr refs, or a ref
    that is not an evidence ref at all)."""
    ok: list[Flag] = []
    bad: list[tuple[Flag, str]] = []
    for f in flags:
        try:
            stable = runs.stable_refs(f)
        except ValueError as e:  # refs.parse: not an evidence ref
            reason = f"malformed evidence ref: {e}"
        else:
            if stable:
                ok.append(f)
                continue
            reason = "no stable evidence ref (scene/line/shot/kf/cue/clr), R13"
        log.warning("dropped %s flag %r: %s", f.check, f.title, reason)
        bad.append((f, reason))
    return ok, bad


def stage_timeline(ep: EpisodeRun) -> None:
    ep.tl = load_timeline(ep.conn, ep.show, ep.episode)


def stage_checks(ep: EpisodeRun) -> None:
    """Every work unit of every active check; a unit that raises is a coverage gap (failed)."""
    tl = ep.timeline
    pb = ProducedBy(model_variant=None, plan_id=ep.plan.plan_id or PLAN_ID)
    for check in ep.checks:
        for unit in check.units(tl):
            with ep.unit(str(check.check), unit.key):
                flags = [emit(f, check.check, tl, ep.run_id, pb) for f in check.run(unit, tl)]
                ep.flags += [f for f in flags if f is not None]


def stage_verification(ep: EpisodeRun) -> None:
    stable, ep.dropped = require_stable_refs(ep.flags)
    ep.kept, dropped = verify(stable, ep.timeline, ep.checks)
    ep.dropped += dropped


def stage_flags(ep: EpisodeRun) -> None:
    ep.kept = runs.save_flags(ep.conn, runs.db_id(ep.run_id), ep.episode_id, ep.kept)


CHECK_IDS = {str(c) for c in CheckId}


def coverage(
    checks: list[Check], skipped: list[str], units: list[dict[str, Any]]
) -> dict[Agent, float]:
    """Done / total check work units per agent; 1.0 for an active agent with no units, 0.0 for one
    whose checks were all skipped. Content-stage units (stage not a check id) are not counted."""
    out: dict[Agent, float] = {}
    for a in {owner(c.check) for c in checks} | {owner(s) for s in skipped}:
        mine = [u for u in units if u["stage"] in CHECK_IDS and owner(u["stage"]) == a]
        active = any(owner(c.check) == a for c in checks)
        out[a] = sum(u["status"] == "done" for u in mine) / len(mine) if mine else float(active)
    return out


def stage_report(ep: EpisodeRun) -> None:
    """The report object; it is published only after the run commits (`publish`)."""
    gaps = any(u["status"] == "failed" for u in ep.units)
    ep.report = build_report(
        episode=ep.episode,
        run_id=ep.run_id,
        status="completed_with_gaps" if gaps else "completed",
        plan=report_plan(ep.plan),
        coverage=coverage(ep.checks, ep.skipped, ep.units),
        flags=ep.kept,
    )


Stage = Callable[[EpisodeRun], None]
STAGES: list[tuple[str, Stage]] = [
    ("timeline", stage_timeline),
    ("checks", stage_checks),
    ("verification", stage_verification),
    ("flags", stage_flags),
    ("report", stage_report),
]


def add_stage(name: str, fn: Stage, before: str = "timeline") -> None:
    """Insert a stage just before `before`; repeated calls keep their call order."""
    STAGES.insert([n for n, _ in STAGES].index(before), (name, fn))


def wire() -> None:
    """Add every content stage and agent package of Phase 2 (W-int), once.

    Order: asr -> align -> story -> extract -> consolidate -> index, all before `timeline`
    (`load_timeline` must see the aligned frames and the new `fact/{id}` rows), then cue_align
    and loc.observed after it (both read `ep.timeline`), before `checks`. `nip run` calls this;
    a direct `run_store` call (tests) keeps the core stages. Imports stay here so `nip --help`
    does not load them."""
    if "timeline.asr" in dict(STAGES):
        return
    from nip.agents import clearance, script_critic
    from nip.agents.localization import term
    from nip.knowledge import consolidate, extract, index, story
    from nip.timeline import align, asr, cue_align

    add_stage("timeline.asr", asr.stage)
    add_stage("timeline.align", align.stage)
    add_stage(story.STAGE, story.stage_story)
    add_stage(extract.STAGE, extract.stage_extract)
    add_stage(consolidate.STAGE, consolidate.stage_consolidate)
    add_stage(index.STAGE, index.stage)
    add_stage("timeline.cue_align", cue_align.stage, before="checks")
    add_stage("loc.observed", term.stage, before="checks")
    AGENTS.extend(p for p in (script_critic, clearance) if p not in AGENTS)


def publish(s3: Any, plan: Plan, eps: list[EpisodeRun], out_dir: Path | None) -> None:
    """Artifacts of a committed run: plan.json, per-episode report.json, and `out_dir` files."""
    for ep in eps:
        assert ep.report is not None
        body = ep.report.model_dump_json(indent=2)
        key = objects.run_key(ep.run_id, ep.episode, "report.json")
        objects.put_bytes(s3, objects.artifact_bucket(), key, body.encode())
        for name, data in ep.artifacts.items():
            key = objects.run_key(ep.run_id, ep.episode, name)
            objects.put_bytes(s3, objects.artifact_bucket(), key, data)
        if out_dir is not None:
            d = out_dir / ep.episode
            d.mkdir(parents=True, exist_ok=True)
            (d / "timeline.json").write_text(ep.timeline.model_dump_json(), encoding="utf-8")
            (d / "flags.jsonl").write_text(_jsonl(ep.kept), encoding="utf-8")
            (d / "dropped.jsonl").write_text(_jsonl([f for f, _ in ep.dropped]), encoding="utf-8")
            (d / "report.json").write_text(body, encoding="utf-8")
    if eps:
        key = objects.run_key(eps[0].run_id, "plan.json")
        objects.put_bytes(
            s3, objects.artifact_bucket(), key, plan.model_dump_json(indent=2).encode()
        )


def episode_inputs(
    conn: Connection, show_id: int, episode_id: int
) -> tuple[set[Input], str | None, list[str]]:
    """(inputs present, source subtitle language, target subtitle languages in ingest order)."""
    sf = schema.source_file
    rows = conn.execute(
        select(sf.c.kind, sf.c.role, sf.c.lang)
        .where(
            sf.c.show_id == show_id, or_(sf.c.episode_id == episode_id, sf.c.episode_id.is_(None))
        )
        .order_by(sf.c.id)
    ).all()
    available = {FILE_INPUTS[k] for k, _, _ in rows if k in FILE_INPUTS}
    source = next((lang for k, r, lang in rows if k == "subtitle" and r == "source"), None)
    targets = [lang for k, r, lang in rows if k == "subtitle" and r == "target"]
    available |= {Input.SOURCE_SUBS} if source else set()
    available |= {Input.TARGET_SUBS} if targets else set()
    return available, source, targets


def run_store(
    engine: Engine,
    s3: Any,
    *,
    show: str,
    episodes: list[str],
    plan: Plan,
    inventory: HardwareInventory,
    agents: Collection[Agent] | None = None,
    out_dir: Path | None = None,
    requested_by: str = "cli",
) -> dict[str, Any]:
    """Run every stage over `episodes` of `show` from the store; returns the run summary.

    `agents`: None = auto (every agent whose checks' inputs are present).
    """
    if not episodes:
        raise InputRejected("no episodes given")
    with engine.connect() as conn:
        try:
            rows = [episode_row(conn, show, e) for e in dict.fromkeys(episodes)]
        except LookupError as e:
            raise InputRejected(str(e)) from e
        prepared: list[tuple[Any, list[Check], list[str]]] = []
        langs: list[str] = []
        for row in rows:
            available, source, targets = episode_inputs(conn, row.show_id, row.id)
            ctx = {"langs": targets, "source_lang": source, "conn": conn, "show": show,
                   "episode": row.ref}  # fmt: skip
            prepared.append((row, *build_checks(available, ctx, agents)))
            langs += [t for t in targets if t not in langs]
        resolved = sorted({str(owner(c.check)) for _, checks, _ in prepared for c in checks})
        plan_db = runs.create_plan(conn, plan, inventory)
        plan = plan.model_copy(update={"plan_id": runs.ext_id("plan", plan_db)})
        run_db = runs.create_run(
            conn,
            show_id=rows[0].show_id,
            episode_ids=[r.id for r in rows],
            agents=sorted(str(a) for a in agents) if agents is not None else resolved,
            languages=langs,
            plan_id=plan_db,
            requested_by=requested_by,
        )
        conn.commit()
        run_id = runs.ext_id("run", run_db)
        eps = [
            EpisodeRun(conn, s3, show, row.ref, row.id, run_id, plan, checks, skipped)
            for row, checks, skipped in prepared
        ]
        try:  # one transaction for the whole run: every episode commits, or none
            for ep in eps:
                for name, fn in STAGES:
                    with _timed(ep.stages, name):
                        fn(ep)
                runs.add_work_units(conn, run_db, ep.units)
            gaps = any(u["status"] == "failed" for ep in eps for u in ep.units)
            status = "completed_with_gaps" if gaps else "completed"
            runs.finish_run(conn, run_db, status)
            conn.commit()
        except BaseException:
            conn.rollback()
            runs.finish_run(conn, run_db, "failed")
            conn.commit()
            raise
    publish(s3, plan, eps, out_dir)  # only a committed run has artifacts

    summary = {
        "run_id": run_id,
        "plan_id": plan.plan_id,
        "status": status,
        "agents": resolved,
        "episodes": {
            ep.episode: {
                "stages": ep.stages,
                "skipped": ep.skipped,
                "spans": dict(Counter(str(s.kind) for s in ep.timeline.spans)),
                "units": dict(Counter(u["status"] for u in ep.units)),
                "flags_emitted": len(ep.flags),
                "flags_kept": len(ep.kept),
                "dropped": [{"title": f.title, "reason": r} for f, r in ep.dropped],
                "counts": {str(k): v for k, v in ep.report.counts.items()} if ep.report else {},
            }
            for ep in eps
        },
    }
    if out_dir is not None:
        (out_dir / "run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


MODEL_SLOTS = (Slot.ASR, Slot.TEXT_LLM, Slot.TEXT_EMBEDDER)  # the slots the wired stages call


def current_plan(workload: dict[Slot, int]) -> tuple[Plan, HardwareInventory]:
    """The Plan for this hardware (`nip plan`'s inputs); NIP_PROFILE=cpu gives the stub Plan.

    The asr slot is pinned to `timeline.asr.variant` of pipeline.yaml (EXP-003 picked turbo over
    the planner's quality-ranked large-v3); NIP_PIN_ASR overrides it."""
    from nip.runtime import planner
    from nip.runtime.catalog import load_catalog, validate
    from nip.runtime.probe import probe as probe_hardware

    try:
        vllm: str | None = version("vllm")
    except PackageNotFoundError:
        vllm = None
    inv = probe_hardware()
    pins = {Slot.ASR: timeline_config()["asr"]["variant"]}
    pins |= {s: v for s in Slot if (v := os.environ.get(f"NIP_PIN_{s.upper()}", ""))}
    p = planner.plan(
        inv,
        validate(load_catalog(), vllm, licenses=None),
        workload,
        Objective(os.environ.get("NIP_PLAN_OBJECTIVE", "quality")),
        pins,
        stub=os.environ.get("NIP_PROFILE") == "cpu",
        gpu_mem_utilization=float(os.environ.get("NIP_GPU_MEM_UTILIZATION", "0.90")),
    )
    return p, inv


def run(
    show: Annotated[str, typer.Option(help="Show slug, as given to `nip ingest`")],
    episodes: Annotated[list[str], typer.Option(help="Episode refs; repeat or comma-separate")],
    agents: Annotated[str, typer.Option(help="auto, or comma-separated agent names")] = "auto",
    force: Annotated[bool, typer.Option(help="Ignore the stage cache (none until 2.9B)")] = False,
    out_dir: Annotated[Path | None, typer.Option(help="Also write per-episode JSON here")] = None,
    dry_run: Annotated[bool, typer.Option(help="Print the stages and checks, run nothing")] = False,
) -> None:
    """Run the checks on ingested episodes; flags and the run are stored in Postgres."""
    eps = [e.strip() for x in episodes for e in x.split(",") if e.strip()]
    try:
        wanted = None if agents == "auto" else {Agent(a.strip()) for a in agents.split(",")}
    except ValueError as e:
        raise typer.BadParameter(f"--agents: {e}") from e
    wire()
    if dry_run:
        checks = [str(c.check) for pkg in AGENTS for c in pkg.CHECKS]
        typer.echo(json.dumps({"stages": [n for n, _ in STAGES], "checks": checks}, indent=2))
        return
    # ponytail: one unit per episode for each model slot; real counts only size replicas (multi-GPU)
    plan, inv = current_plan({s: len(eps) for s in MODEL_SLOTS})
    engine = create_engine(database_url())
    try:
        summary = run_store(engine, objects.client(), show=show, episodes=eps, plan=plan,
                            inventory=inv, agents=wanted, out_dir=out_dir)  # fmt: skip
    except InputRejected as e:
        typer.echo(f"INPUT_REJECTED: {e}", err=True)
        raise typer.Exit(1) from e
    finally:
        engine.dispose()
    typer.echo(json.dumps(summary | {"force": force}, indent=2))


# ---- file mode (Phase 1 walking skeleton) ----------------------------------------------------
def run_pipeline(
    *,
    episode: str,
    script: Path,
    subs: dict[str, Path],
    source_lang: str,
    out_dir: Path,
    video: Path | None = None,
    picture: Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run every stage, write timeline/flags/report JSON to `out_dir`, return the run summary."""
    if picture is not None and video is None:
        raise InputRejected("a picture.json needs the video it was made from")
    run_id = run_id or f"run_{datetime.now(UTC):%Y%m%dT%H%M%S}"
    out_dir.mkdir(parents=True, exist_ok=True)
    stages: list[dict[str, Any]] = []

    with _timed(stages, "ingest"):
        scr = ingest(script, Script)
        tracks = {lang: ingest(p, SubtitleTrack) for lang, p in subs.items()}
        try:
            media = probe(video) if video else None
        except MediaRejected as e:
            raise InputRejected(str(e)) from e

    with _timed(stages, "picture"):
        pic: dict[str, Any] = {"shots": [], "keyframes": []}
        if media is not None and picture is not None:
            pic = json.loads(picture.read_text(encoding="utf-8"))
            if Fraction(*pic["fps"]) != media.fps:
                raise InputRejected(f"{picture.name}: fps {pic['fps']} is not the picture's")
        elif video is not None:
            pic = analyze_picture(video, out_dir / "picture")
            (out_dir / "picture" / "picture.json").write_text(json.dumps(pic), encoding="utf-8")

    with _timed(stages, "timeline"):
        tl = build_timeline(
            episode,
            scr,
            media,
            tracks,
            [(a, b) for a, b in pic["shots"]],
            [(k["shot"], k["n"], k["frame"]) for k in pic["keyframes"]],
        )

    targets = [lang for lang in tracks if lang != source_lang]
    available = {Input.SCRIPT}
    available |= {Input.PICTURE} if media else set()
    available |= {Input.SOURCE_SUBS} if source_lang in tracks else set()
    available |= {Input.TARGET_SUBS} if targets else set()
    ctx = {"langs": targets, "source_lang": source_lang, "conn": None, "show": None,
           "episode": episode}  # fmt: skip
    checks, skipped = build_checks(available, ctx)
    pb = ProducedBy(model_variant=None, plan_id=PLAN_ID)
    flags: list[Flag] = []
    for check in checks:
        with _timed(stages, str(check.check)):
            flags += run_check(check, tl, run_id, pb)

    with _timed(stages, "verification"):
        stable, unstable = require_stable_refs(flags)
        kept, dropped = verify(stable, tl, checks)
        dropped = unstable + dropped

    with _timed(stages, "report"):
        report = build_report(
            episode=episode,
            run_id=run_id,
            status="completed",
            plan=ReportPlan(plan_id=PLAN_ID, mode=Mode.STAGED, judge_independent=False),
            coverage=coverage(checks, skipped, []),
            flags=kept,
        )

    (out_dir / "timeline.json").write_text(tl.model_dump_json(), encoding="utf-8")
    (out_dir / "flags.jsonl").write_text(_jsonl(kept), encoding="utf-8")
    (out_dir / "dropped.jsonl").write_text(_jsonl([f for f, _ in dropped]), encoding="utf-8")
    (out_dir / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    summary = {
        "run_id": run_id,
        "episode": episode,
        "stages": stages,
        "skipped": skipped,
        "spans": dict(Counter(str(s.kind) for s in tl.spans)),
        "flags_emitted": len(flags),
        "flags_kept": len(kept),
        "dropped": [{"title": f.title, "reason": r} for f, r in dropped],
        "counts": {str(k): v for k, v in report.counts.items()},
    }
    (out_dir / "run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def run_files(
    episode: Annotated[str, typer.Option(help="Episode id used in evidence refs, e.g. S01E03")],
    script: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="pdf/fountain/fdx")],
    subs: Annotated[list[str], typer.Option(help="LANG=PATH (srt/vtt/ttml), repeated")],
    out_dir: Annotated[Path, typer.Option(help="Where timeline/flags/report JSON go")],
    source_lang: Annotated[str, typer.Option(help="Language of the source track")] = "en",
    video: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    picture: Annotated[
        Path | None,
        typer.Option(exists=True, dir_okay=False, help="picture.json from `nip timeline picture`"),
    ] = None,
) -> None:
    """Run the checks on one episode's files, without the store (Phase 1 walking skeleton)."""
    pairs = [s.partition("=") for s in subs]
    if any(not lang or not p for lang, _, p in pairs):
        raise typer.BadParameter("--subs takes LANG=PATH")
    try:
        summary = run_pipeline(
            episode=episode,
            script=script,
            subs={lang: Path(p) for lang, _, p in pairs},
            source_lang=source_lang,
            out_dir=out_dir,
            video=video,
            picture=picture,
        )
    except (InputRejected, FileNotFoundError) as e:
        typer.echo(f"INPUT_REJECTED: {e}", err=True)
        raise typer.Exit(1) from e
    typer.echo(json.dumps(summary, indent=2))
