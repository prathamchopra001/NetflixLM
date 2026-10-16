"""Label Studio helpers for hand-labelled shot cuts (EXP-002).

Flow: `prepare` cuts a film into frame-exact, all-intra preview clips -> `push` creates the project
and tasks -> a person labels -> `pull` writes eval/labeling/labels/<title>_cuts.json.

Frame conventions: Label Studio numbers frames from 1; we store 0-based global frame indexes of the
FIRST frame of the new shot (a cut at frame N means frames N-1 and N are in different shots).
Clips overlap by one frame so a cut on a clip boundary is still visible; that overlap frame
(frame 1 of every clip) is never a cut of that clip.
"""

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import typer

from nip.ingest.media import probe

CONFIG = Path(__file__).with_name("cuts.xml")
CLIP_FRAMES = 1440  # 60 s at 24 fps
FONT = (
    "C\\:/Windows/Fonts/arial.ttf"
    if os.name == "nt"
    else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
)
app = typer.Typer(no_args_is_help=True)


@app.callback()
def _group() -> None:
    """Label Studio projects for hand labels."""


def parse_fps(text: str) -> tuple[int, int]:
    num, _, den = text.partition("/")
    return int(num), int(den or 1)


def probe_fps(video: Path) -> tuple[int, int]:
    """Exact frame rate of a video file (nip.ingest.media.probe)."""
    f = probe(video).fps
    return f.numerator, f.denominator


def common_fps(files: list[Path]) -> tuple[int, int]:
    """The one exact frame rate of all files; refuses mixed rates."""
    rates = {probe_fps(f) for f in files}
    if len(rates) != 1:
        raise ValueError(f"expected exactly one frame rate, got {sorted(rates)}")
    return rates.pop()


def count_frames(video: Path) -> int:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_packets",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_packets",
            "-of",
            "csv=p=0",
            str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return int(out)


def ls_framerate(fps: tuple[int, int]) -> str:
    """Framerate string for the Label Studio Video tag: a decimal, never a fraction."""
    num, den = fps
    return str(num // den) if num % den == 0 else f"{num / den:.9f}".rstrip("0")


def render_config(fps: tuple[int, int]) -> str:
    return CONFIG.read_text(encoding="utf-8").replace("{framerate}", ls_framerate(fps))


def clip_offset(k: int, clip_frames: int = CLIP_FRAMES) -> int:
    """0-based global frame index of Label Studio frame 1 of clip k."""
    return 0 if k == 0 else k * clip_frames - 1


def _encode(
    src_args: list[str], dst: Path, fps: tuple[int, int], vf: str, extra: list[str]
) -> None:
    num, den = fps
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            *src_args,
            "-an",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "26",
            "-g",
            "1",
            "-pix_fmt",
            "yuv420p",
            "-fps_mode",
            "passthrough",
            "-video_track_timescale",
            str(num * 1000),
            *extra,
            str(dst),
        ],
        check=True,
    )


def make_clips(
    src: Path, out_dir: Path, total_frames: int, clip_frames: int = CLIP_FRAMES, width: int = 640
) -> list[Path]:
    """Cut src into all-intra H.264 clips (every frame a keyframe -> exact browser seeking)."""
    fps = probe_fps(src)
    out_dir.mkdir(parents=True, exist_ok=True)
    clips = []
    for k in range((total_frames + clip_frames - 1) // clip_frames):
        first = clip_offset(k, clip_frames)
        n = min(clip_frames + (1 if k else 0), total_frames - first)
        dst = out_dir / f"{src.stem.split('.')[0].lower()}_{k:03d}.mp4"
        start = (
            max(first - 0.5, 0) * fps[1] / fps[0]
        )  # half a frame early: robust to ms-rounded pts
        _encode(
            ["-ss", f"{start:.6f}", "-i", str(src)],
            dst,
            fps,
            f"scale={width}:-2",
            ["-frames:v", str(n)],
        )
        clips.append(dst)
    return clips


def make_verify_clip(
    dst: Path, fps: tuple[int, int], seconds: int = 10, src: Path | None = None
) -> None:
    """Clip with the 1-based frame number burned in; compare it with Label Studio's counter."""
    text = (
        f"drawtext=fontfile='{FONT}':text='%{{frame_num}}':start_number=1:x=20:y=20:"
        "fontsize=100:fontcolor=white:box=1:boxcolor=black@0.7"
    )
    inp = (
        ["-i", str(src), "-t", str(seconds)]
        if src
        else [
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size=640x360:rate={fps[0]}/{fps[1]}:duration={seconds}",
        ]
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    _encode(inp, dst, fps, f"scale=640:-2,{text}", [])


def parse_cuts(tasks: list[dict[str, Any]]) -> tuple[list[int], list[str]]:
    """(global 0-based cut frames, names of clips without a finished annotation).

    Uses the latest non-cancelled annotation per task; the verify task is ignored.
    """
    cuts: set[int] = set()
    unlabelled: list[str] = []
    for t in tasks:
        if t["data"].get("verify"):
            continue
        anns = [a for a in t.get("annotations", []) if not a.get("was_cancelled")]
        if not anns:
            unlabelled.append(t["data"]["clip"])
            continue
        ann = max(anns, key=lambda a: a.get("updated_at", ""))
        offset = t["data"]["offset_frames"]
        for r in ann["result"]:
            for rng in r["value"].get("ranges", []):
                f = rng["start"]  # 1-based Label Studio frame
                if f == 1:
                    continue  # never a cut (clip 0: film start; others: overlap frame)
                cuts.add(offset + f - 1)
    return sorted(cuts), sorted(unlabelled)


def task_fps(tasks: list[dict[str, Any]]) -> str:
    rates = {t["data"]["fps"] for t in tasks}
    if len(rates) != 1:
        raise ValueError(f"tasks carry different frame rates: {sorted(rates)}")
    return str(rates.pop())


def write_cuts(
    title: str, cuts: list[int], fps: str, out: Path, labeller: str, unlabelled: list[str]
) -> None:
    """Cuts label file, documented in README.md (one JSON object)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "title": title,
        "check": "shot.cut",
        "fps": fps,
        "labeller": labeller,
        "frame_convention": "0-based index in the whole film of the first frame of the new shot",
        "unlabelled_clips": unlabelled,
        "cuts": cuts,
    }
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")


class LabelStudio:
    """Minimal REST client (stdlib only). Token: personal access token (JWT) or legacy token."""

    def __init__(self, url: str, token: str) -> None:
        self.url = url.rstrip("/")
        self.auth = f"Token {token}"
        if token.count(".") == 2:  # personal access token: exchange for a short-lived access token
            access = self.call("POST", "/api/token/refresh", {"refresh": token}, auth=False)
            self.auth = f"Bearer {access['access']}"

    def call(self, method: str, path: str, body: Any = None, auth: bool = True) -> Any:
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = self.auth
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.url + path, method=method, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{method} {path}: {e.code} {e.read().decode()[:500]}") from e
        return json.loads(raw) if raw else None


VERIFY = "_verify.mp4"


def make_tasks(
    title: str, clips: list[Path], fps: str, verify: bool = True, root: str = "labeling"
) -> list[dict[str, Any]]:
    """Task payloads (the frame-number verify clip first); videos use local-files serving."""

    def task(name: str, offset: int, **extra: Any) -> dict[str, Any]:
        url = f"/data/local-files/?d={root}/{title}/{name}"
        return {"data": {"video": url, "offset_frames": offset, "clip": name, "fps": fps, **extra}}

    head = [task(VERIFY, 0, verify=True)] if verify else []
    return head + [task(c.name, clip_offset(k)) for k, c in enumerate(clips)]


def _client(url: str) -> LabelStudio:
    return LabelStudio(url, os.environ["LABEL_STUDIO_TOKEN"])


def _clips(data_dir: Path, title: str) -> list[Path]:
    d = data_dir / "labeling" / title
    clips = sorted(d.glob(f"{title}_[0-9]*.mp4"))
    if not clips or not (d / VERIFY).exists():
        raise typer.BadParameter(f"no clips or {VERIFY} in {d}: run `prepare` first")
    return clips


def _project_fps(data_dir: Path, title: str) -> tuple[int, int]:
    """Probed rate of every clip and the verify clip; mixed rates are an error."""
    files = [*_clips(data_dir, title), data_dir / "labeling" / title / VERIFY]
    try:
        return common_fps(files)
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e


@app.command()
def prepare(title: str = "sintel", data_dir: Path = Path("data")) -> None:
    """Cut data/corpus/<title>'s picture into labelling clips + the frame-number verify clip."""
    src = next(p for p in (data_dir / "corpus" / title).iterdir() if p.suffix in {".mkv", ".mov"})
    out = data_dir / "labeling" / title
    clips = make_clips(src, out, count_frames(src))
    make_verify_clip(out / VERIFY, probe_fps(src), src=src)
    typer.echo(f"{len(clips)} clips + {VERIFY} in {out}")


@app.command("verify-clip")
def verify_clip(
    out: Path = Path("data/labeling/verify_24.mp4"), fps: str = "24/1", src: Path | None = None
) -> None:
    """Write a stand-alone burned-in frame-number clip (fps like 24/1 or 24000/1001)."""
    make_verify_clip(out, parse_fps(fps), src=src)
    typer.echo(str(out))


@app.command()
def config(title: str = "sintel", data_dir: Path = Path("data")) -> None:
    """Print the Label Studio project config exactly as `push` will send it."""
    typer.echo(render_config(_project_fps(data_dir, title)))


@app.command()
def push(
    project: str = "cuts-sintel",
    title: str = "sintel",
    url: str = "http://localhost:8081",
    data_dir: Path = Path("data"),
) -> None:
    """Create the project (config from the clips' probed frame rate), storage and tasks.

    Task 1 is the burned-in frame-number verify clip; one task per clip follows.
    """
    clips = _clips(data_dir, title)
    fps = _project_fps(data_dir, title)
    ls = _client(url)
    p = ls.call("POST", "/api/projects", {"title": project, "label_config": render_config(fps)})
    ls.call(
        "POST",
        "/api/storages/localfiles",
        {"project": p["id"], "title": title, "path": f"/label-studio/files/labeling/{title}"},
    )
    ls.call(
        "POST", f"/api/projects/{p['id']}/import", make_tasks(title, clips, f"{fps[0]}/{fps[1]}")
    )
    typer.echo(f"project {p['id']}: verify task + {len(clips)} clip tasks, fps {fps[0]}/{fps[1]}")


@app.command()
def pull(
    project_id: int,
    title: str = "sintel",
    labeller: str = "human",
    allow_partial: bool = typer.Option(False, help="Write the file even if clips are unlabelled."),
    url: str = "http://localhost:8081",
    out_dir: Path = Path("eval/labeling/labels"),
) -> None:
    """Export finished annotations to eval/labeling/labels/<title>_cuts.json.

    Fails if any clip has no finished annotation (a missing clip would read as "no cuts").
    A non-human labeller writes <title>_cuts.provisional.json.
    """
    tasks = _client(url).call(
        "GET", f"/api/projects/{project_id}/export?exportType=JSON&download_all_tasks=true"
    )
    cuts, unlabelled = parse_cuts(tasks)
    total = sum(1 for t in tasks if not t["data"].get("verify"))
    typer.echo(f"{total - len(unlabelled)}/{total} clips labelled")
    if unlabelled and not allow_partial:
        typer.echo(f"unlabelled clips: {', '.join(unlabelled)} (finish them or --allow-partial)")
        raise typer.Exit(1)
    out = out_dir / f"{title}_cuts{'' if labeller == 'human' else '.provisional'}.json"
    write_cuts(title, cuts, task_fps(tasks), out, labeller, unlabelled)
    typer.echo(f"{len(cuts)} cuts -> {out}")


if __name__ == "__main__":
    app()
