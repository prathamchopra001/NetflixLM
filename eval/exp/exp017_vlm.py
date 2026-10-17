"""EXP-017: a dedicated OCR model (`pp-ocrv6-medium`, run by RapidOCR) vs the vision model
(`qwen3.5-4b-awq`) reading each keyframe (docs/experiments.md).

Single variable: who reads the keyframe. The frames (the keyframe policy EXP-008 adopted), the
injected pictures, the typed-candidate scan (`TextScanner`, same recognizers), matching,
occurrences,
the six checks and scoring are the same for both arms (`eval.exp.exp008_keyframes`).

    # 1. vlm app up in ray-head (see exp017_serve.py), then, on the host, under data/gpu.lock:
    NIP_SERVE_URL=http://127.0.0.1:8001 uv run python -m eval.exp.exp017_vlm read --seeds 1,2,3
    # 2. stop it (touch /tmp/exp017.stop in the container), then score both arms:
    uv run python -m eval.exp.exp017_vlm score --seeds 1,2,3 --ocr-tag gpu
    nip eval compare --exp EXP-017 --md --tracking-uri sqlite:///data/mlflow/mlflow.db

The vision model answers with structured output (D-025): `{"lines": [{"text", "box"}]}`, the box on
the 0-1000 grid Qwen uses (catalog `box_format: xyxy_0_1000`). It has no per-line confidence, so
every line gets the constant `VLM_CONFIDENCE` (an assumption: it only moves unlogged items between
tiers, never a pending / denied one). Cost: wall seconds the model is busy reading per content
hour; the vlm reads 8 frames at once (what vLLM batches), the OCR arm one at a time as shipped.
"""

import hashlib
import json
import pickle
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import typer
from pydantic import BaseModel, Field

from eval.exp import exp008_keyframes as bench
from nip.agents.clearance.ocr_text import TextScanner
from nip.agents.clearance.stage import Scan
from nip.runtime.clients.llm import SERVE_URL, LLMClient
from nip.runtime.clients.ocr import OcrLine, StubOCR

VARIANT = "qwen3.5-4b-awq"
VLM_CONFIDENCE = 0.9
ROOT = Path("data/exp017")
PROMPT = (
    "Read all the text visible in this video frame: signs, captions, screens, labels, license "
    "plates, phone numbers, web and e-mail addresses. Return every line of text exactly as it is "
    "written, one entry per line of text, with its bounding box on a 0-1000 grid as "
    "[x0, y0, x1, y1] (left, top, right, bottom). If the frame shows no text, return an empty list."
)
app = typer.Typer(no_args_is_help=True)


class VlmLine(BaseModel):
    text: str
    box: list[int] = Field(min_length=4, max_length=4)


class VlmLines(BaseModel):
    lines: list[VlmLine]


def to_ocr_lines(reply: VlmLines) -> list[OcrLine]:
    """The model's lines as the reader interface: boxes become normalized [x, y, w, h]."""
    out = []
    for ln in reply.lines:
        if not ln.text.strip():
            continue
        x0, y0, x1, y1 = (min(max(v, 0), 1000) / 1000 for v in ln.box)
        out.append(
            OcrLine(
                text=ln.text.strip(),
                box=(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)),
                confidence=VLM_CONFIDENCE,
            )
        )
    return out


def read_one(client: LLMClient, image: bytes) -> list[OcrLine]:
    reply = client.complete(PROMPT, VlmLines, images=[image], max_tokens=600)
    return to_ocr_lines(reply)


def cache_path(film: bench.Film) -> Path:
    return ROOT / "vlm" / f"{film.name}-s{film.seed}.pkl"


@app.command("read")
def read_cmd(
    seeds: str = "1,2,3", arm: str = "1-per-shot+2s", concurrency: int = 8,
    films: str = "sintel,tears-of-steel", base_url: str = SERVE_URL,
) -> None:  # fmt: skip
    """Read the arm's keyframes with the vision model; cache the lines; record the wall time."""
    client = LLMClient(VARIANT, base_url=base_url, timeout_s=300)
    ROOT.joinpath("vlm").mkdir(parents=True, exist_ok=True)
    log: list[dict[str, Any]] = []
    for seed in map(int, seeds.split(",")):
        for name in films.split(","):
            film = bench.load_film(name, seed)
            images = bench.extract(film)
            wanted = sorted({f for _, _, f in bench.policy(film, arm)})
            path = cache_path(film)
            done: dict[int, list[OcrLine] | None] = (
                pickle.loads(path.read_bytes()) if path.exists() else {}
            )
            todo = [f for f in wanted if f not in done]
            failed: list[int] = []

            def work(f: int, images: dict[int, Path] = images) -> tuple[int, list[OcrLine] | None]:
                try:
                    return f, read_one(client, images[f].read_bytes())
                except Exception as e:  # a failed frame is a gap, counted, not a crash
                    print(f"  frame {f}: {type(e).__name__}: {str(e)[:120]}", flush=True)
                    return f, None

            t = time.perf_counter()
            with ThreadPoolExecutor(concurrency) as pool:
                for f, lines in pool.map(work, todo):
                    done[f] = lines
                    if lines is None:
                        failed.append(f)
            wall = time.perf_counter() - t
            path.write_bytes(pickle.dumps(done))
            rec = {"film": name, "seed": seed, "frames": len(todo), "failed": len(failed),
                   "wall_s": round(wall, 2), "concurrency": concurrency}  # fmt: skip
            log.append(rec)
            print(json.dumps(rec), flush=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    (ROOT / f"read-{stamp}.json").write_text(json.dumps(log, indent=1), encoding="utf-8")


@app.command("score")
def score_cmd(
    seeds: str = "1,2,3", arm: str = "1-per-shot+2s", ocr_tag: str = "gpu",
    films: str = "sintel,tears-of-steel", reads: str = "",
) -> None:  # fmt: skip
    """Score the two readers on the same frames: flags -> `nip eval run` for each, per seed.
    `reads`: the read-*.json whose wall times give the vlm's cost (default: the newest)."""
    sel = [bench.load_film(n, s) for s in map(int, seeds.split(",")) for n in films.split(",")]
    unions: dict[str, dict[tuple[str, int], dict[int, tuple[Scan, float]]]] = {
        VARIANT: {},
        "ocr": {},
    }
    walls = json.loads(
        (Path(reads) if reads else sorted(ROOT.glob("read-*.json"))[-1]).read_text("utf-8")
    )
    wall = {(r["film"], r["seed"]): r for r in walls}
    failed: dict[tuple[str, int], int] = {}
    for film in sel:
        key = (film.name, film.seed)
        frames = bench.extract(film)
        lines = pickle.loads(cache_path(film).read_bytes())
        recorded = {
            hashlib.sha256(frames[f].read_bytes()).hexdigest(): v
            for f, v in lines.items()
            if v is not None
        }
        failed[key] = sum(v is None for v in lines.values())
        reader = StubOCR(recorded)
        reader.variant = VARIANT
        # NER: the same GLiNER as the OCR arm's scan (its cached candidates came from it)
        ner = _ner()
        scanner = TextScanner(ner, deny_brands=film.deny, fictional=film.fictional)
        only = {f for f, v in lines.items() if v is not None}
        u = bench.scan_union(film, reader, scanner, "vlm", only)
        rec = wall.get(key)
        per_frame = rec["wall_s"] / max(rec["frames"], 1) if rec else 0.0  # amortized wall seconds
        unions[VARIANT][key] = {f: (s, per_frame) for f, (s, _) in u.items()}
        unions["ocr"][key] = pickle.loads(
            (bench.ROOT / "scans" / f"{ocr_tag}-{film.name}-s{film.seed}.pkl").read_bytes()
        )
    for seed in map(int, seeds.split(",")):
        for name, arm_name in ((VARIANT, VARIANT), ("ocr", "pp-ocrv6-medium")):
            bench.score_arm(
                sel, unions[name], arm, "EXP-017", seed, ROOT / "runs",
                {"reader": arm_name, "keyframe_policy": arm,
                 "failed_frames": str(sum(failed[(f.name, f.seed)] for f in sel if f.seed == seed))
                 if name == VARIANT else "0"},
                arm_name=arm_name, prefix="exp017",
            )  # fmt: skip


def _ner() -> Any:
    from nip.runtime.clients.ner import GlinerBackend

    return GlinerBackend(cuda=False)


if __name__ == "__main__":
    app()
