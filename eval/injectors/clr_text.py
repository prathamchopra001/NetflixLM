"""Clearance text injector: render phone / URL / email / address / plate / brand text onto the
picture and re-encode a copy (docs/evaluation.md > Clearance).

Simplification (recorded in notes): the text is an opaque overlay in a fixed screen region held for
72-96 frames inside a stretch of the picture where nothing moves, not a texture mapped onto a
planar surface in the scene. A window can never straddle a shot change because a cut makes the
frame-to-frame difference huge, so "low motion" also means "one shot". What OCR must handle is
therefore easier than a sign in perspective; the benchmark reports it as such.

Positives come from the title's sidecar `clearance_log.csv` (rows whose notes start with
`injected`), with their log status: cleared items are rendered but not labelled (a cleared item
must be hidden, so it is not an error to find); pending and denied items are labelled. Negatives
are generated from the seed: 555-0100..0199 numbers, RFC 2606 domains and addresses, and brands
the bible declares fictional. Everything that was rendered is listed in `<dst>.clr.json`.
"""

import json
import random
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from eval.injectors.base import Injector, Label, Target, register
from eval.injectors.common import SIDECAR
from nip.ingest import parse_bible, parse_clearance_log
from nip.ingest.media import MediaInfo, probe

CHECKS = {
    "phone": "clr.phone",
    "url": "clr.url",
    "email": "clr.email",
    "address": "clr.address",
    "plate": "clr.plate",
    "brand": "clr.brand_text",
}
MOTION_THRESHOLD = 1.0  # mean absolute gray-level change between consecutive 48x27 frames
MIN_RUN = 84  # frames of stillness needed: a 72-frame window plus 6 frames of margin each side
WINDOW = (72, 96)  # frames the text stays up (3-4 s at 24 fps)
REGIONS = {  # name -> (anchor x, anchor y) as fractions of the frame; text hangs from the anchor
    "bottom-left": (0.05, 0.84),
    "bottom-right": (0.95, 0.84),
    "top-left": (0.05, 0.08),
    "top-right": (0.95, 0.08),
    "middle-left": (0.05, 0.46),
}
NEG_DOMAINS = [
    "www.example.com",
    "https://example.org",
    "portal.example.net",
    "shop.test",
    "help.invalid",
]
NEG_EMAILS = ["info@example.com", "contact@example.org", "support@mail.test", "press@demo.invalid"]
NEG_AREAS = ["212", "415", "617", "310"]
FFMPEG_TIMEOUT_S = 3600


def low_motion_runs(path: Path, info: MediaInfo) -> list[tuple[int, int]]:
    """[start, end) frame runs, at least MIN_RUN long, in which every frame is within
    MOTION_THRESHOLD of the next (decoded at 48x27 gray through ffmpeg)."""
    w, h = 48, 27
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-vf",
         f"scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True, timeout=FFMPEG_TIMEOUT_S,
    ).stdout  # fmt: skip
    frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.int16)
    still = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2)) < MOTION_THRESHOLD
    runs, start = [], None
    for i, s in enumerate([*still, False]):
        if s and start is None:
            start = i
        elif not s and start is not None:
            if i - start >= MIN_RUN and start > 0:  # a run from frame 0 is the fade-in
                runs.append((start, i))
            start = None
    return [r for r in runs if r[1] <= info.duration_frames]


def _render(text: str, size: int, max_w: int) -> Image.Image:
    """The text on a dark translucent plate, RGBA."""
    while True:
        font = ImageFont.load_default(size)
        box = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), text, font=font)
        if box[2] - box[0] + 2 * (size // 2) <= max_w or size <= 12:
            break
        size -= 2
    pad = size // 2
    img = Image.new(
        "RGBA", (int(box[2] - box[0]) + 2 * pad, int(box[3] - box[1]) + 2 * pad), (20, 20, 20, 225)
    )
    ImageDraw.Draw(img).text(
        (pad - box[0], pad - box[1]), text, font=font, fill=(255, 255, 255, 255)
    )
    return img


def _negatives(rng: random.Random, brands: Sequence[str], n: int) -> list[tuple[str, str]]:
    pool = {
        "phone": f"({rng.choice(NEG_AREAS)}) 555-01{rng.randint(0, 99):02d}",
        "url": rng.choice(NEG_DOMAINS),
        "email": rng.choice(NEG_EMAILS),
        "brand": rng.choice(brands) if brands else "Kappa Cola",
    }
    kinds = list(pool)
    rng.shuffle(kinds)
    return [(k, pool[k]) for k in kinds[:n]]


@register
class ClrText(Injector):
    id = "clr.text.v1"
    check = "clr.text"  # the labels carry the specific clr.* check of each item

    def inject(
        self,
        src: Path,
        dst: Path,
        seed: int,
        *,
        episode: str | None = None,
        title: str | None = None,
        sidecar: Path | None = None,
        k_pos: int = 8,
        k_neg: int = 4,
    ) -> list[Label]:
        """`src` is a picture file, `dst` the re-encoded copy; `sidecar` defaults to
        eval/corpus/sidecar/<title dir>."""
        episode = episode or src.parent.name
        title = title or episode
        sidecar = sidecar or SIDECAR / src.parent.name
        log = parse_clearance_log((sidecar / "clearance_log.csv").read_bytes())
        bible = parse_bible((sidecar / "bible.yaml").read_bytes())
        if not (log.ok and log.data and bible.ok and bible.data):
            raise ValueError(f"{sidecar}: sidecar does not parse: {log.errors + bible.errors}")
        rng = random.Random(f"{self.id}/{seed}")
        info = probe(src)
        runs = low_motion_runs(src, info)
        pool = [e for e in log.data if e.notes.startswith("injected") and e.kind in CHECKS]
        pos = [
            {"kind": e.kind, "text": e.item, "negative": False, "status": e.status}
            for e in rng.sample(pool, min(k_pos, len(pool)))
        ]
        neg = [
            {"kind": k, "text": t, "negative": True, "status": None}
            for k, t in _negatives(rng, bible.data.fictional.brands, k_neg)
        ]
        items: list[dict[str, Any]] = []
        while pos or neg:  # two positives per negative, so a short film still gets negatives
            items += [*pos[:2], *neg[:1]]
            pos, neg = pos[2:], neg[1:]
        items = items[: len(runs)]  # one still stretch per item
        rng.shuffle(items)
        rng.shuffle(runs)
        for it, (a, b) in zip(items, runs, strict=False):
            n = min(rng.randint(*WINDOW), b - a - 12)
            it["frames"] = [a + 6 + rng.randint(0, b - a - n - 12), 0]
            it["frames"][1] = it["frames"][0] + n
            it["region"] = rng.choice(list(REGIONS))
        items.sort(key=lambda it: it["frames"][0])

        w, h = info.width, info.height
        with tempfile.TemporaryDirectory() as tmp:
            args: list[str] = ["ffmpeg", "-y", "-v", "error", "-i", str(src)]
            graph, last = [], "0:v"
            for i, it in enumerate(items, 1):
                img = _render(it["text"], max(16, h // 22), int(w * 0.6))
                png = Path(tmp) / f"{i}.png"
                img.save(png)
                args += ["-i", str(png)]
                ax, ay = REGIONS[it["region"]]
                x = round(ax * w) - (img.width if ax > 0.5 else 0)
                y = round(ay * h)
                it["box"] = [
                    round(x / w, 4),
                    round(y / h, 4),
                    round(img.width / w, 4),
                    round(img.height / h, 4),
                ]
                a, b = it["frames"]
                graph.append(
                    f"[{last}][{i}:v]overlay=x={x}:y={y}:enable='between(n,{a},{b - 1})'[v{i}]"
                )
                last = f"v{i}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            args += ["-filter_complex", ";".join(graph)] if graph else []
            args += ["-map", f"[{last}]" if graph else "0:v:0", "-map", "0:a?", "-c:a", "copy"]
            args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]
            args += [
                "-fflags",
                "+bitexact",
                "-flags:v",
                "+bitexact",
                "-map_metadata",
                "-1",
                str(dst),
            ]
            subprocess.run(args, check=True, capture_output=True, timeout=FFMPEG_TIMEOUT_S)
        dst.with_name(dst.name + ".clr.json").write_text(
            json.dumps(
                {"fps": str(info.fps), "frames": info.duration_frames, "items": items}, indent=1
            )
            + "\n",
            encoding="utf-8",
        )
        labels = []
        for n, it in enumerate(items, 1):
            if it["negative"] or it["status"] == "cleared":
                continue  # negatives must stay unflagged; a cleared item must be hidden
            a, b = it["frames"]
            labels.append(
                Label(
                    label_id=f"{episode}-clr-s{seed}-{n}",
                    title=title,
                    episode=episode,
                    check=CHECKS[it["kind"]],
                    target=Target(kind="frame_range", frames=(a, b)),
                    description=(
                        f"{it['kind']} text '{it['text']}' overlaid at {it['region']} for {b - a} "
                        f"frames; clearance log: {it['status']}"
                    ),
                    injector=self.id,
                    seed=seed,
                )
            )
        return labels
