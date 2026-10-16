"""Seed candidate cuts for agent labelling and render before/after contact sheets to look at.

uv run python -m eval.exp.label_sheets sintel
Candidates = union of low-threshold detector cuts (data/exp002/candidates.json, from
`exp002_shots candidates`) + the top frame-difference peaks of every fixed 10 s window (to catch
cuts every detector missed). Candidates within 3 frames merge into one event. Each event is drawn
as 6 consecutive frames (f-3..f+2) with a red line where the cut would be (between f-1 and f).
Output: data/exp002/labelling/<film>/{events.json, sheet_NNN.jpg}
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import typer
from PIL import Image, ImageDraw

from eval.exp.exp002_shots import FILMS, OUT

W, H = 208, 89  # tile size
ROWS = 12
WINDOW = 240  # frames per scan window (10 s at 24 fps)
PER_WINDOW = 2  # diff peaks kept per window
MERGE = 3
app = typer.Typer()


def decode_small(film: str) -> np.ndarray:
    """Every frame of the film at W x H, uint8 [N, H, W, 3] (~1.8 GB for Sintel)."""
    from nip.ingest.media import load_ffmpeg

    load_ffmpeg()
    from torchcodec.decoders import VideoDecoder  # type: ignore[attr-defined]
    from torchcodec.transforms import Resize  # type: ignore[attr-defined]

    dec = VideoDecoder(
        str(FILMS[film]),
        seek_mode="exact",
        dimension_order="NHWC",
        num_ffmpeg_threads=0,
        transforms=[Resize((H, W))],
    )
    n = len(dec)
    return np.concatenate(
        [dec.get_frames_in_range(i, min(i + 500, n)).data.numpy() for i in range(0, n, 500)]
    )


def diff_signal(frames: np.ndarray) -> np.ndarray:
    """Mean abs luma difference between each frame and the previous one (d[0] = 0)."""
    g = frames.mean(axis=3, dtype=np.float32)
    return np.concatenate([[0.0], np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))])


def scan_peaks(d: np.ndarray, skip: set[int]) -> list[int]:
    """Per fixed window: frames whose diff is the biggest relative to the local median."""
    pad = np.pad(d, 12, mode="edge")
    med = np.array([np.median(pad[i : i + 25]) for i in range(len(d))]) + 0.5
    ratio = d / med
    out = []
    for s in range(0, len(d), WINDOW):
        for i in np.argsort(-ratio[s : s + WINDOW])[:PER_WINDOW] + s:
            if not any(abs(int(i) - c) <= 2 for c in skip):
                out.append(int(i))
    return out


def merge(cand: dict[int, list[str]]) -> list[dict[str, Any]]:
    events: list[list[int]] = []
    for f in sorted(cand):
        if events and f - events[-1][-1] <= MERGE:
            events[-1].append(f)
        else:
            events.append([f])
    out = []
    for fs in events:
        rep = max(fs, key=lambda f: (len(cand[f]), -f))  # most-supported frame
        out.append({"frame": rep, "members": fs, "sources": {f: cand[f] for f in fs}})
    return out


@app.command()
def sheets(film: str = "sintel", out: Path = OUT) -> None:
    frames = decode_small(film)
    n = len(frames)
    d = diff_signal(frames)
    np.save(out / f"{film}_diff.npy", d)
    cand = {int(k): v for k, v in json.loads((out / "candidates.json").read_text()).items()}
    for f in scan_peaks(d, set(cand)):
        cand.setdefault(f, []).append("scan-peak")
    events = merge(cand)
    lab = out / "labelling" / film
    lab.mkdir(parents=True, exist_ok=True)
    (lab / "events.json").write_text(json.dumps(events))
    per_sheet = ROWS
    for sheet, start in enumerate(range(0, len(events), per_sheet)):
        img = Image.new("RGB", (6 * W + 5 * 2, ROWS * (H + 14)), (30, 30, 30))
        dr = ImageDraw.Draw(img)
        for r, ev in enumerate(events[start : start + per_sheet]):
            f, y = ev["frame"], r * (H + 14)
            dr.text((2, y + 1), f"#{start + r}  f={f}", fill=(255, 255, 0))
            for k in range(6):
                i = min(max(f - 3 + k, 0), n - 1)
                img.paste(Image.fromarray(frames[i]), (k * (W + 2), y + 13))
            x = 3 * (W + 2) - 1
            dr.line([(x, y + 13), (x, y + 13 + H)], fill=(255, 0, 0), width=2)
        img.save(lab / f"sheet_{sheet:03d}.jpg", quality=88)
    print(f"{len(cand)} candidate frames -> {len(events)} events, {sheet + 1} sheets in {lab}")


def _render(frames: np.ndarray, rows: list[tuple[str, int]], path_fmt: str) -> int:
    """Rows of 6 frames (m-3..m+2, red line before m), ROWS rows per sheet; returns sheet count."""
    n = len(frames)
    sheet = -1
    for sheet, start in enumerate(range(0, len(rows), ROWS)):
        img = Image.new("RGB", (6 * W + 5 * 2, ROWS * (H + 14)), (30, 30, 30))
        dr = ImageDraw.Draw(img)
        for r, (label, m) in enumerate(rows[start : start + ROWS]):
            y = r * (H + 14)
            dr.text((2, y + 1), f"{label}  m={m}", fill=(255, 255, 0))
            for k in range(6):
                img.paste(
                    Image.fromarray(frames[min(max(m - 3 + k, 0), n - 1)]), (k * (W + 2), y + 13)
                )
            x = 3 * (W + 2) - 1
            dr.line([(x, y + 13), (x, y + 13 + H)], fill=(255, 0, 0), width=2)
        img.save(path_fmt.format(sheet), quality=88)
    return sheet + 1


@app.command()
def sheets2(film: str = "sintel", out: Path = OUT) -> None:
    """Second pass: one row per event member that the first-pass window (f-3..f+2) did not show.

    Members inside the labelled gradual regions (decisions.txt `G start end ...`) are skipped.
    """
    lab = out / "labelling" / film
    events = json.loads((lab / "events.json").read_text())
    gradual = [
        tuple(map(int, ln.split()[1:3]))
        for ln in (lab / "decisions.txt").read_text().splitlines()
        if ln.startswith(("G ", "X "))
    ]
    rows = [
        (f"#{i}", m)
        for i, e in enumerate(events)
        for m in e["members"]
        if (m < e["frame"] - 3 or m > e["frame"] + 2) and not any(a <= m <= b for a, b in gradual)
    ]
    (lab / "rows2.json").write_text(json.dumps(rows))
    n = _render(decode_small(film), rows, str(lab / "s2_{:03d}.jpg"))
    print(len(rows), "rows,", n, "sheets")


@app.command()
def strip(
    start: int, end: int, step: int = 1, film: str = "sintel", cols: int = 6, w: int = 416
) -> None:
    """Contact sheet of frames start..end (inclusive) every `step`, w px wide each -> strip.jpg."""
    from nip.ingest.media import load_ffmpeg

    load_ffmpeg()
    from torchcodec.decoders import VideoDecoder  # type: ignore[attr-defined]

    dec = VideoDecoder(str(FILMS[film]), seek_mode="exact", dimension_order="NHWC")
    idx = list(range(start, end + 1, step))
    md = dec.metadata
    assert md.height and md.width
    h = int(w * md.height / md.width)
    rows = -(-len(idx) // cols)
    img = Image.new("RGB", (cols * (w + 2), rows * (h + 14)), (30, 30, 30))
    dr = ImageDraw.Draw(img)
    for n, i in enumerate(idx):
        fr = Image.fromarray(dec.get_frame_at(i).data.numpy()).resize(
            (w, h), Image.Resampling.BILINEAR
        )
        x, y = (n % cols) * (w + 2), (n // cols) * (h + 14)
        dr.text((x + 2, y + 1), f"f={i}", fill=(255, 255, 0))
        img.paste(fr, (x, y + 13))
    path = OUT / "labelling" / film / "strip.jpg"
    img.save(path, quality=88)
    print(path)


if __name__ == "__main__":
    app()
