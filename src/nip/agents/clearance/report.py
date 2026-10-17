"""Clearance report: one row per occurrence, as CSV (api-contracts.md > clearance-report; R11: the
CSV artifact and this CLI now, the API route with 4.1).

    occurrence_id,item,kind,status,tc_in,tc_out,screen_time_s,prominence,severity,thumbnail_url,flag_id

`item`/`kind` are the clearance-log row's when the text matched one, else the detected text and its
kind; `prominence` is `featured` or `background`; `thumbnail_url` is the stored crop of the best
keyframe (`s3://<media bucket>/<show>/<ep>/crops/<detection id>.jpg`; the API presigns it later).
Cleared occurrences are hidden from the report and stay in the flags (tier `suppressed`) for the
audit; `include_hidden` puts them in the CSV too.

The pipeline stage `clearance.csv` (after `flags`) stores the CSV as run artifact
`runs/{run_id}/{ep}/clearance_report.csv` (per episode like report.json, 2.0). Wiring (cli.py):
`app.add_typer(clearance_report.app, name="clearance")` with
`from nip.agents.clearance import report as clearance_report` -> `nip clearance report`.
"""

import csv
import io
from fractions import Fraction
from pathlib import Path
from typing import Annotated, Any

import typer
from sqlalchemy import create_engine, func, select

from nip.agents.clearance.checks import episode_occurrences
from nip.agents.clearance.occurrences import Occurrence
from nip.config import pipeline_config
from nip.contracts.flag import EvidenceKind
from nip.contracts.timeline import Timeline
from nip.store import objects, schema
from nip.timecode import frame_to_smpte

COLUMNS = [
    "occurrence_id", "item", "kind", "status", "tc_in", "tc_out", "screen_time_s", "prominence",
    "severity", "thumbnail_url", "flag_id",
]  # fmt: skip
KIND = {  # kind of an item that is not in the log, from the check that found it
    "clr.phone": "phone", "clr.url": "url", "clr.email": "email",
    "clr.address": "address", "clr.plate": "plate", "clr.brand_text": "brand",
}  # fmt: skip


def occurrence_rows(
    occs: list[Occurrence],
    tl: Timeline,
    show: str,
    flag_ids: dict[tuple[str, str, str | None], str],
    *,
    include_hidden: bool = False,
) -> list[dict[str, Any]]:
    """The CSV rows. `flag_ids`: (check, best keyframe ref, its quote) of a flag -> its id."""
    from nip.contracts import refs

    fps = Fraction(*tl.fps)
    rows: list[dict[str, Any]] = []
    for o in sorted(occs, key=lambda o: (o.frames, o.check)):
        if o.match.status == "cleared" and not include_hidden:
            continue
        item = o.match.item
        kf = refs.keyframe(tl.episode, o.best.shot, o.best.n)
        tc = [frame_to_smpte(f + tl.start_tc_frames, fps, tl.drop_frame) for f in o.frames]
        det = o.best.detection_id
        rows.append(
            {
                "occurrence_id": f"occ_{len(rows) + 1}",
                "item": item.name if item else o.text,
                "kind": item.kind if item else KIND[o.check],
                "status": o.match.status,
                "tc_in": tc[0],
                "tc_out": tc[1],
                "screen_time_s": f"{o.screen_frames / fps:.1f}",
                "prominence": "featured" if o.featured else "background",
                "severity": o.severity,
                "thumbnail_url": (
                    f"s3://{objects.media_bucket()}/{show}/{tl.episode}/crops/{det}.jpg"
                    if det
                    else ""
                ),
                "flag_id": flag_ids.get(
                    (o.check, kf, o.best.text), flag_ids.get((o.check, kf, None), "")
                ),
            }
        )
    return rows


def to_csv(rows: list[dict[str, Any]]) -> str:
    out = io.StringIO()
    w = csv.DictWriter(out, COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return out.getvalue()


def from_csv(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def stage(ep: Any) -> None:
    """Pipeline stage `clearance.csv`, after `flags`: the report CSV as a run artifact."""
    tl: Timeline = ep.timeline
    occs = episode_occurrences(ep.conn, ep.show, tl, pipeline_config()["clearance"])
    ids = {  # the best keyframe of a flag is the one with the crop
        (str(f.check), e.ref, e.quote): f.id
        for f in ep.kept
        if f.agent.value == "clearance_scanner" and f.id
        for e in f.evidence
        if e.kind is EvidenceKind.KEYFRAME and e.crop is not None
    }
    ep.artifacts["clearance_report.csv"] = to_csv(occurrence_rows(occs, tl, ep.show, ids)).encode()


# ---- CLI ---------------------------------------------------------------------------------------
app = typer.Typer(no_args_is_help=True)


@app.callback()
def clearance() -> None:
    """Clearance reports."""


@app.command("report")
def report_cmd(
    show: Annotated[str, typer.Option(help="Show slug")],
    episode: Annotated[str, typer.Option(help="Episode ref, e.g. S01E01")],
    run: Annotated[
        str, typer.Option(help="Run id (run_12) whose flag ids to cite, or latest")
    ] = "latest",
    out: Annotated[Path | None, typer.Option(help="Write the CSV here (default: stdout)")] = None,
    include_hidden: Annotated[bool, typer.Option(help="Also list cleared occurrences")] = False,
) -> None:
    """Write the clearance report CSV of an episode from the store."""
    from nip.store import runs
    from nip.store.db import database_url
    from nip.store.load import episode_row, load_timeline

    engine = create_engine(database_url())
    try:
        with engine.connect() as conn:
            try:
                ep = episode_row(conn, show, episode)
            except LookupError as e:
                typer.echo(f"INPUT_REJECTED: {e}", err=True)
                raise typer.Exit(1) from e
            tl = load_timeline(conn, show, episode)
            fl, ev = schema.flag, schema.evidence
            run_id = (
                runs.db_id(run)
                if run != "latest"
                else conn.execute(
                    select(func.max(fl.c.run_id)).where(fl.c.episode_id == ep.id)
                ).scalar()
            )
            ids = {
                (r.check_id, r.ref, r.quote): runs.ext_id("flg", r.id)
                for r in conn.execute(
                    select(fl.c.id, fl.c.check_id, ev.c.ref, ev.c.quote)
                    .join(ev, ev.c.flag_id == fl.c.id)
                    .where(
                        fl.c.run_id == run_id,
                        fl.c.episode_id == ep.id,
                        fl.c.agent == "clearance_scanner",
                        ev.c.kind == EvidenceKind.KEYFRAME.value,
                        ev.c.crop.is_not(None),
                    )
                )
            }
            occs = episode_occurrences(conn, show, tl, pipeline_config()["clearance"])
    finally:
        engine.dispose()
    text = to_csv(occurrence_rows(occs, tl, show, ids, include_hidden=include_hidden))
    if out:
        out.write_text(text, encoding="utf-8", newline="")
    else:
        typer.echo(text, nl=False)
