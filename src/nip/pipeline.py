"""Walking-skeleton run (Phase 1): ingest -> timeline -> loc.readability -> verification -> report.

One process, files in, JSON out. The store-backed flow (api queues a run, runtime.controller
claims it, runtime.scheduler runs the stages) replaces this in Phase 2; until then `nip run`
takes the source files directly.
"""

import json
import logging
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Annotated, Any

import typer

from nip.agents.base import Input, run_check
from nip.agents.localization.readability import Readability
from nip.contracts.flag import Agent, ProducedBy
from nip.contracts.plan import Mode
from nip.contracts.report import ReportPlan, build_report
from nip.ingest import Script, SubtitleTrack, parse
from nip.ingest.media import MediaRejected, probe
from nip.timeline.estimate import build_timeline
from nip.timeline.picture import analyze_picture
from nip.verification.verify import verify

log = logging.getLogger(__name__)

FORMATS = {
    ".pdf": "pdf",
    ".fountain": "fountain",
    ".fdx": "fdx",
    ".srt": "srt",
    ".vtt": "vtt",
    ".ttml": "ttml",
    ".xml": "ttml",
}
PLAN_ID = "none"  # loc.readability uses no model slot, so no Plan is computed yet


class InputRejected(ValueError):
    """A source file refused at the door (api-contracts.md INPUT_REJECTED)."""


def ingest[T](path: Path, want: type[T]) -> T:
    """Parse + validate one source file, chosen by extension, as a `want`; warnings are logged."""
    fmt = FORMATS.get(path.suffix.lower())
    if fmt is None:
        raise InputRejected(f"{path.name}: unsupported format {path.suffix!r}")
    p = parse(fmt, path.read_bytes())
    for w in p.warnings:
        log.warning("%s: %s", path.name, w)
    if not p.ok:
        e = p.errors[0]
        raise InputRejected(f"{path.name}: {e.reason}" + (f" (line {e.line})" if e.line else ""))
    if not isinstance(p.data, want):  # e.g. --script given a subtitle file
        raise InputRejected(f"{path.name}: a {fmt} file is not a {want.__name__}")
    return p.data


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

    @contextmanager
    def stage(name: str) -> Iterator[None]:
        t = time.perf_counter()
        yield
        stages.append({"stage": name, "wall_s": round(time.perf_counter() - t, 4)})

    with stage("ingest"):
        scr = ingest(script, Script)
        dup = sorted(n for n, k in Counter(s.number for s in scr.scenes).items() if k > 1)
        if dup:
            raise InputRejected(f"{script.name}: duplicate scene numbers {dup}; renumber them")
        tracks = {lang: ingest(p, SubtitleTrack) for lang, p in subs.items()}
        try:
            media = probe(video) if video else None
        except MediaRejected as e:
            raise InputRejected(str(e)) from e

    with stage("picture"):
        pic: dict[str, Any] = {"shots": [], "keyframes": []}
        if media is not None and picture is not None:
            pic = json.loads(picture.read_text(encoding="utf-8"))
            if Fraction(*pic["fps"]) != media.fps:
                raise InputRejected(f"{picture.name}: fps {pic['fps']} is not the picture's")
        elif video is not None:
            pic = analyze_picture(video, out_dir / "picture")
            (out_dir / "picture" / "picture.json").write_text(json.dumps(pic), encoding="utf-8")

    with stage("timeline"):
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
    try:
        check = Readability(targets)
    except ValueError as e:
        raise InputRejected(str(e)) from e
    skipped = [] if check.active(available) else [str(check.check)]
    with stage(str(check.check)):
        pb = ProducedBy(model_variant=None, plan_id=PLAN_ID)
        flags = [] if skipped else run_check(check, tl, run_id, pb)

    with stage("verification"):
        kept, dropped = verify(flags, tl, [check])

    with stage("report"):
        report = build_report(
            episode=episode,
            run_id=run_id,
            status="completed",
            plan=ReportPlan(plan_id=PLAN_ID, mode=Mode.STAGED, judge_independent=False),
            coverage={Agent.LOCALIZATION_AUDITOR: 0.0 if skipped else 1.0},
            flags=kept,
        )

    def jsonl(rows: list[Any]) -> str:
        return "".join(r.model_dump_json() + "\n" for r in rows)

    (out_dir / "timeline.json").write_text(tl.model_dump_json(), encoding="utf-8")
    (out_dir / "flags.jsonl").write_text(jsonl(kept), encoding="utf-8")
    (out_dir / "dropped.jsonl").write_text(jsonl([f for f, _ in dropped]), encoding="utf-8")
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


def run(
    episode: Annotated[str, typer.Option(help="Episode id used in evidence refs, e.g. S01E03")],
    script: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="pdf/fountain/fdx")],
    subs: Annotated[list[str], typer.Option(help="LANG=PATH (srt/vtt/ttml), repeated")],
    out_dir: Annotated[Path, typer.Option(help="Where timeline/flags/report JSON go")],
    source_lang: Annotated[str, typer.Option(help="Language of the source track")] = "en",
    video: Annotated[Path | None, typer.Option(exists=True, dir_okay=False)] = None,
    picture: Annotated[
        Path | None, typer.Option(
            exists=True, dir_okay=False, help="picture.json from `nip timeline picture`"
        )
    ] = None,
) -> None:
    """Run the walking skeleton (loc.readability) on one episode's files."""
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
