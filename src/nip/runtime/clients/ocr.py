"""ocr slot: PP-OCRv6 medium text detection + recognition on keyframes.

The catalog variant `pp-ocrv6-medium` is served through RapidOCR (the same PP-OCRv6 medium weights
exported to ONNX, run by ONNX Runtime). PaddlePaddle's GPU build could not share one environment
with torch cu130 (tech-stack.md › Build notes anticipated this: `uv lock` fails on linux with
`nvidia-nccl-cu13` pinned to 2.29.7 by torch and 2.30.7 by paddlepaddle-gpu; build-log).

Every backend has one method, `read(image) -> list[OcrLine]`. Boxes are normalized `[x, y, w, h]`
(data-model.md › detection). The vlm re-read of low-confidence crops is Phase 3.
"""

import hashlib
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from pydantic import BaseModel, Field

from nip.runtime.clients.llm import SERVE_URL  # NIP_SERVE_URL, default Serve on :8000

VARIANT = "pp-ocrv6-medium"

Image = str | Path | bytes


class OcrLine(BaseModel):
    text: str
    box: tuple[float, float, float, float]  # normalized [x, y, w, h]
    confidence: float = Field(ge=0, le=1)


def models_dir() -> Path:
    """ONNX weights: `$NIP_OCR_MODELS`, else `<repo>/models/rapidocr` (git-ignored)."""
    if env := os.environ.get("NIP_OCR_MODELS"):
        return Path(env)
    return Path(__file__).resolve().parents[4] / "models" / "rapidocr"


def _bgr(image: Image) -> "np.ndarray[Any, Any]":
    data = image if isinstance(image, bytes) else Path(image).read_bytes()
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("not a decodable image")
    return img


class RapidOcrBackend:
    """PP-OCRv6 medium (det + rec) on ONNX Runtime; `cuda` puts detection on the GPU."""

    variant = VARIANT

    def __init__(self, *, cuda: bool = True, min_score: float = 0.5) -> None:
        if cuda:
            import onnxruntime
            import torch  # noqa: F401  # loads torch's CUDA 13 / cuDNN 9 DLLs that ORT's CUDA EP needs

            onnxruntime.preload_dlls()
        from rapidocr import EngineType, LangDet, LangRec, ModelType, OCRVersion, RapidOCR

        d = models_dir()
        params: dict[str, Any] = {
            "Global.use_cls": False,  # keyframes are upright; the angle classifier costs a pass
            "Global.text_score": min_score,
            "Global.log_level": "warning",
            "EngineConfig.onnxruntime.use_cuda": cuda,
            # keyframes differ in size: EXHAUSTIVE would re-tune every conv for each new shape
            "EngineConfig.onnxruntime.cuda_ep_cfg.cudnn_conv_algo_search": "HEURISTIC",
            "Det.engine_type": EngineType.ONNXRUNTIME,
            "Det.ocr_version": OCRVersion.PPOCRV6,
            "Det.model_type": ModelType.MEDIUM,
            "Det.lang_type": LangDet.MULTI,
            "Det.model_path": str(d / "PP-OCRv6_det_medium.onnx"),
            "Rec.engine_type": EngineType.ONNXRUNTIME,
            "Rec.ocr_version": OCRVersion.PPOCRV6,
            "Rec.model_type": ModelType.MEDIUM,
            "Rec.lang_type": LangRec.EN,  # one multilingual model; lang only picks a route
            "Rec.model_path": str(d / "PP-OCRv6_rec_medium.onnx"),
        }
        self._engine = RapidOCR(params=params)
        if cuda:
            # Detection on CUDA, recognition on CPU: the CUDA EP re-plans for every line width and
            # recognized a keyframe set 10x slower than ORT's CPU provider (build-log).
            self._engine._load_det_model()  # type: ignore[no-untyped-call]
            self._engine.cfg.EngineConfig.onnxruntime.use_cuda = False

    def read(self, image: Image) -> list[OcrLine]:
        img = _bgr(image)
        h, w = img.shape[:2]
        out: Any = self._engine(img)
        if out.txts is None or out.boxes is None:
            return []
        lines = []
        for pts, text, score in zip(out.boxes, out.txts, out.scores, strict=True):
            x0, y0 = np.clip(pts.min(axis=0) / (w, h), 0, 1)
            x1, y1 = np.clip(pts.max(axis=0) / (w, h), 0, 1)
            lines.append(
                OcrLine(
                    text=text,
                    box=(float(x0), float(y0), float(x1 - x0), float(y1 - y0)),
                    confidence=float(score),
                )
            )
        return lines


def fingerprint(image: Image) -> str:
    """Key of a recorded stub answer: sha256 of the image file's bytes."""
    data = image if isinstance(image, bytes) else Path(image).read_bytes()
    return hashlib.sha256(data).hexdigest()


class StubOCR:
    """No model (NIP_PROFILE=cpu): replays `recorded[fingerprint(image)]`, else reads nothing."""

    variant = VARIANT

    def __init__(self, recorded: Mapping[str, Sequence[OcrLine]] | None = None) -> None:
        self._recorded = recorded or {}

    def read(self, image: Image) -> list[OcrLine]:
        return list(self._recorded.get(fingerprint(image), ()))


class ServeOCR:
    """The Serve app of the ocr slot: POST the image bytes, get `{"lines": [...]}`."""

    def __init__(self, variant: str = VARIANT, base_url: str = SERVE_URL, timeout_s: float = 60):
        self.variant = variant
        self._url = f"{base_url}/models/{variant}"
        self._timeout = timeout_s

    def read(self, image: Image) -> list[OcrLine]:
        import httpx

        data = image if isinstance(image, bytes) else Path(image).read_bytes()
        r = httpx.post(self._url, content=data, timeout=self._timeout)
        r.raise_for_status()
        return [OcrLine.model_validate(x) for x in r.json()["lines"]]


class Actor:
    """Ray Serve replica (`serving._bind` uses `clients.<slot>.Actor`): body = image bytes."""

    def __init__(self, variant: str) -> None:
        self.variant = variant
        self._ocr = RapidOcrBackend()

    async def __call__(self, request: Any) -> dict[str, Any]:
        lines = self._ocr.read(await request.body())
        return {"variant": self.variant, "lines": [x.model_dump() for x in lines]}
