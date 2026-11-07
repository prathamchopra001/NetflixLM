"""Picture stage of the timeline (probe -> shots -> keyframes) and its `picture` CLI command."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from nip.config import config_dir
from nip.ingest.media import MediaRejected, probe
from nip.timeline.keyframes import extract_keyframes

app = typer.Typer(no_args_is_help=True)


@app.callback()
def timeline() -> None:
    """Timeline stages."""


def timeline_config(path: Path | None = None) -> dict[str, Any]:
    path = path or config_dir() / "pipeline.yaml"
    return yaml.safe_load(path.read_text())["timeline"]  # type: ignore[no-any-return]


def analyze_picture(
    video: Path, out_dir: Path, cfg: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Frame axis, shot ranges and keyframe images (written under `out_dir/keyframes`)."""
    from nip.timeline import shots  # torch: imported only when a picture is analysed

    cfg = cfg or timeline_config()
    info = probe(video)
    ranges = shots.detect_shots(video, threshold=cfg["shots"]["threshold"])
    kf = extract_keyframes(video, ranges, info.fps, out_dir / "keyframes", **cfg["keyframes"])
    return {
        "fps": [info.fps.numerator, info.fps.denominator],
        "duration_frames": info.duration_frames,
        "start_tc_frames": info.start_tc_frames,
        "drop_frame": info.drop_frame,
        "shots": [list(s) for s in ranges],
        "keyframes": kf,
    }


@app.command()
def picture(
    video: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    out_dir: Annotated[Path, typer.Option(help="Where keyframes and picture.json are written")],
) -> None:
    """Probe a picture file, detect shots and extract keyframes."""
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = analyze_picture(video, out_dir)
    except MediaRejected as e:
        typer.echo(f"INPUT_REJECTED: {e}", err=True)
        raise typer.Exit(1) from e
    (out_dir / "picture.json").write_text(json.dumps(result))
    typer.echo(f"{len(result['shots'])} shots, {len(result['keyframes'])} keyframes -> {out_dir}")
