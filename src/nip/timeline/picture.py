"""Picture stage of the timeline (probe -> shots -> keyframes) and its `picture` CLI command."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from nip.ingest.media import probe
from nip.timeline.keyframes import extract_keyframes
from nip.timeline.shots import detect_shots

app = typer.Typer(no_args_is_help=True)


@app.callback()
def timeline() -> None:
    """Timeline stages."""

_CONFIG = Path(__file__).resolve().parents[3] / "config" / "pipeline.yaml"


def timeline_config(path: Path = _CONFIG) -> dict[str, Any]:
    return yaml.safe_load(path.read_text())["timeline"]  # type: ignore[no-any-return]


def analyze_picture(
    video: Path, out_dir: Path, cfg: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Frame axis, shot ranges and keyframe images (written under `out_dir/keyframes`)."""
    cfg = cfg or timeline_config()
    info = probe(video)
    shots = detect_shots(video, threshold=cfg["shots"]["threshold"])
    kf = extract_keyframes(video, shots, info.fps, out_dir / "keyframes", **cfg["keyframes"])
    return {
        "fps": [info.fps.numerator, info.fps.denominator],
        "duration_frames": info.duration_frames,
        "start_tc_frames": info.start_tc_frames,
        "drop_frame": info.drop_frame,
        "shots": [list(s) for s in shots],
        "keyframes": kf,
    }


@app.command()
def picture(
    video: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    out_dir: Annotated[Path, typer.Option(help="Where keyframes and picture.json are written")],
) -> None:
    """Probe a picture file, detect shots and extract keyframes."""
    out_dir.mkdir(parents=True, exist_ok=True)
    result = analyze_picture(video, out_dir)
    (out_dir / "picture.json").write_text(json.dumps(result))
    typer.echo(f"{len(result['shots'])} shots, {len(result['keyframes'])} keyframes -> {out_dir}")
