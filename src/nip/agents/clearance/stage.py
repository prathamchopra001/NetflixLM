"""Pipeline stage `clearance.ocr`: read each stored keyframe, find clearance candidates, persist.

For each keyframe image of the episode (object storage `{show}/{ep}/keyframes/{shot}_{n}.jpg`):
OCR reader (`ocr` slot) -> `detection` rows channel `ocr` label `text` (one per line, 2.6) ->
`TextScanner` -> one row per candidate, label = its check id (`clr.phone` ...), and a companion
row label `sharpness` whose `confidence` column holds the Laplacian variance of the text crop
(the `detection` table has no attribute column). A crop image of every candidate is stored as
`{show}/{ep}/crops/{detection_id}.jpg` (data-model.md > Object Storage Layout).

One work unit per keyframe, so a keyframe that fails is a coverage gap and the run says
`completed_with_gaps`; the others go on. Re-running replaces the episode's `ocr` rows.

The stage also puts the OCR text on the timeline's keyframe spans (`ep.tl`), so a flag's quote is
resolved against the stored text by the evidence resolver.

Wiring (W-int pipeline.py): `add_stage("clearance.ocr", stage.stage, before="checks")`; the
slots `ocr` and `ner` are in `MODEL_SLOTS`. Both models run in-process, like asr and the embedder.
"""

import gc
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from typing import Any, Protocol

import cv2
from sqlalchemy import Connection, delete, func, insert, select

from nip.agents.clearance.occurrences import Occurrence, crop, decode, sharpness
from nip.agents.clearance.ocr_text import Candidate, Detection, TextScanner
from nip.config import pipeline_config
from nip.contracts import refs
from nip.contracts.flag import EvidenceKind
from nip.contracts.plan import Slot
from nip.contracts.timeline import Span, Timeline
from nip.runtime.clients.ner import StubNER
from nip.runtime.clients.ocr import StubOCR
from nip.store import objects, schema
from nip.timecode import frame_to_smpte

log = logging.getLogger(__name__)

STAGE = "clearance.ocr"
SHARPNESS = "sharpness"
LANGS = ("en", "de", "es", "fr")  # what the TextScanner is set up for
STUB = "stub"


class StageEpisode(Protocol):
    """What the stage reads of `nip.pipeline.EpisodeRun`."""

    conn: Connection
    s3: Any
    show: str
    episode: str
    episode_id: int
    plan: Any
    tl: Timeline | None

    @property
    def timeline(self) -> Timeline: ...

    def unit(self, stage: str, key: str, model_variant: str | None = None) -> Any: ...


@dataclass
class Scan:
    """What one keyframe gave: its OCR lines, its candidates, and each candidate's sharpness."""

    lines: list[Detection]
    candidates: list[Candidate]
    sharpness: list[float]  # one per candidate

    def rows(self, cfg: dict[str, Any]) -> list[Detection]:
        """The `detection` rows: the lines, then per candidate its row and its sharpness row."""
        out = list(self.lines)
        for c, s in zip(self.candidates, self.sharpness, strict=True):
            conf = confidence(c, cfg)
            out.append(Detection(c.shot, c.n, c.text, c.box, conf, c.model_variant, "ocr", c.check))
            out.append(Detection(c.shot, c.n, "", c.box, s, c.model_variant, "ocr", SHARPNESS))
        return out


def confidence(c: Candidate, cfg: dict[str, Any]) -> float:
    """Confidence of a candidate: OCR confidence x certainty, the recognizer's score or the check's
    `certainty_floor` when higher. A recognizer whose rule validates the value (libphonenumber for
    a phone number, the address grammar and the TLD list for a URL) is as sure as its validation;
    its pattern score (phone: 0.4) says how loose the regex is, not how likely a validated value
    is a phone number, and would route every unlogged number to `suppressed`."""
    floor = cfg["certainty_floor"].get(c.check, 0.0)
    return float(round(c.ocr_confidence * max(c.score, floor), 4))


def scan_image(
    shot: int, n: int, image: bytes, reader: Any, scanner: TextScanner, lang: str = "en"
) -> Scan:
    """OCR one keyframe image and scan its lines (the same call in the stage and in EXP-008/017)."""
    lines = [
        Detection(shot, n, x.text, x.box, x.confidence, reader.variant) for x in reader.read(image)
    ]
    cands = scanner.candidates(lines, lang)
    return Scan(lines, cands, [sharpness(image, c.box) for c in cands])


def crop_jpeg(image: bytes, box: tuple[float, float, float, float], pad: float = 0.15) -> bytes:
    """The text region of a keyframe (padded by `pad` of its size) as a JPEG thumbnail."""
    ok, buf = cv2.imencode(".jpg", crop(decode(image), box, pad))
    assert ok
    return bytes(buf.tobytes())


# ---- backends (in-process, loaded once per process) --------------------------------------------
def _cuda() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except ImportError:
        return False


@cache
def ocr_reader(variant: str) -> Any:
    if variant == STUB:
        return StubOCR()
    from nip.runtime.clients.ocr import RapidOcrBackend

    return RapidOcrBackend(cuda=_cuda())


@cache
def ner_backend(variant: str) -> Any:
    if variant == STUB:
        return StubNER()
    from nip.runtime.clients.ner import GlinerBackend

    return GlinerBackend(variant, cuda=_cuda())


def release_models() -> None:
    """Drop the in-process OCR / NER models (and their GPU memory)."""
    ocr_reader.cache_clear()
    ner_backend.cache_clear()
    gc.collect()


@cache
def scanner_for(
    ner_variant: str | None,
    brands: tuple[str, ...],
    addresses: tuple[str, ...],
    fictional: tuple[str, ...],
) -> TextScanner:
    ner = ner_backend(ner_variant) if ner_variant else None
    return TextScanner(ner, deny_brands=brands, deny_addresses=addresses, fictional=fictional)


# ---- the stage ---------------------------------------------------------------------------------
def _keyframe_keys(conn: Connection, episode_id: int) -> dict[tuple[int, int], str]:
    """(shot index, n) -> object key of the stored image, for the keyframes that have one."""
    sh = schema.shot
    rows = conn.execute(
        select(sh.c.keyframes)
        .where(sh.c.episode_id == episode_id)
        .order_by(func.lower(sh.c.frames), sh.c.id)
    )
    return {
        (i, k["n"]): k["object_key"]
        for i, (kfs,) in enumerate(rows)
        for k in kfs
        if k.get("object_key")
    }


def _source_lang(conn: Connection, episode_id: int) -> str:
    sf = schema.source_file
    lang = conn.execute(
        select(sf.c.lang).where(
            sf.c.episode_id == episode_id, sf.c.kind == "subtitle", sf.c.role == "source"
        )
    ).scalar()
    lang = (lang or "en").split("-")[0].lower()
    return lang if lang in LANGS else "en"


def _names(conn: Connection, show: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """(brand-like clearance items to always look for, names the bible declares fictional)."""
    from nip.agents.clearance.checks import load_registry

    reg = load_registry(conn, show)
    brands = tuple(i.name for i in reg.items if i.kind in ("brand", "logo", "product", "artwork"))
    addresses = tuple(i.name for i in reg.items if i.kind in ("address", "location"))
    return brands, addresses, reg.fictional


def with_ocr(
    tl: Timeline, scans: dict[tuple[int, int], Scan], occs: Sequence[Occurrence]
) -> Timeline:
    """`tl` for the clearance checks: the keyframe spans carry the OCR text (the lines, then
    candidate texts the cleaned line changed), so a quote is found in the span's stored text, and
    every occurrence is a span `clr/occ-<hash>` with the occurrence's frame range and text, which
    is what a flag claims. Run it on the timeline as stored."""
    fps = Fraction(*tl.fps)
    spans = []
    for s in tl.spans:
        if s.kind is EvidenceKind.KEYFRAME:
            shot, _, n = refs.parse(s.ref).id.partition(".")
            if scan := scans.get((int(shot), int(n))):
                lines = [d.text for d in scan.lines]
                extra = [c.text for c in scan.candidates if not any(c.text in x for x in lines)]
                s = s.model_copy(update={"text": "\n".join(lines + extra)})
        spans.append(s)
    for o in occs:
        t = [frame_to_smpte(f + tl.start_tc_frames, fps, tl.drop_frame) for f in o.frames]
        spans.append(
            Span(kind=EvidenceKind.CLEARANCE_ITEM, ref=o.ref, frames=o.frames, text=o.text,
                 tc_in=t[0], tc_out=t[1])
        )  # fmt: skip
    return tl.model_copy(update={"spans": tuple(spans)})


def persist(
    conn: Connection,
    s3: Any,
    show: str,
    ep: str,
    episode_id: int,
    scans: dict[tuple[int, int], Scan],
    cfg: dict[str, Any],
) -> int:
    """Replace the episode's `ocr` detection rows; store a crop image per candidate."""
    d, sh = schema.detection, schema.shot
    conn.execute(delete(d).where(d.c.episode_id == episode_id, d.c.channel == "ocr"))
    shot_ids = {
        i: sid
        for i, sid in enumerate(
            conn.execute(
                select(sh.c.id)
                .where(sh.c.episode_id == episode_id)
                .order_by(func.lower(sh.c.frames), sh.c.id)
            ).scalars()
        )
    }
    rows: Iterable[Detection] = [r for k in sorted(scans) for r in scans[k].rows(cfg)]
    values = [
        {
            "episode_id": episode_id, "shot_id": shot_ids.get(r.shot), "keyframe_n": r.n,
            "channel": r.channel, "label": r.label, "text": r.text, "box": list(r.box),
            "confidence": r.confidence, "model_variant": r.model_variant,
        }
        for r in rows
    ]  # fmt: skip
    if values:
        conn.execute(insert(d), values)
    # crops: one image per candidate row, named by its detection id
    cand = conn.execute(
        select(d.c.id, d.c.shot_id, d.c.keyframe_n, d.c.box).where(
            d.c.episode_id == episode_id, d.c.channel == "ocr", d.c.label.like("clr.%")
        )
    ).all()
    by_shot = {sid: i for i, sid in shot_ids.items()}
    keys = _keyframe_keys(conn, episode_id)
    images: dict[tuple[int, int], bytes] = {}
    for r in cand:
        k = (by_shot[r.shot_id], r.keyframe_n)
        if k not in images:
            images[k] = s3.get_object(Bucket=objects.media_bucket(), Key=keys[k])["Body"].read()
        key = f"{show}/{ep}/crops/{r.id}.jpg"
        objects.put_bytes(s3, objects.media_bucket(), key, crop_jpeg(images[k], tuple(r.box)))
    return len(cand)


def stage(ep: StageEpisode) -> None:
    """Pipeline stage `clearance.ocr` (see the module docstring). No `ocr` decision in the Plan,
    or no stored keyframe image: nothing to do."""
    decision = ep.plan.decisions.get(Slot.OCR)
    keys = _keyframe_keys(ep.conn, ep.episode_id)
    if decision is None or not keys:
        return
    ner = ep.plan.decisions.get(Slot.NER)
    brands, addresses, fictional = _names(ep.conn, ep.show)
    scanner = scanner_for(ner.variant if ner else None, brands, addresses, fictional)
    reader = ocr_reader(decision.variant)
    lang = _source_lang(ep.conn, ep.episode_id)
    scans: dict[tuple[int, int], Scan] = {}
    bucket = objects.media_bucket()
    for (shot, n), key in sorted(keys.items()):
        with ep.unit(STAGE, refs.keyframe(ep.episode, shot, n), model_variant=decision.variant):
            image = ep.s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            scans[shot, n] = scan_image(shot, n, image, reader, scanner, lang)
    cfg = pipeline_config()["clearance"]
    found = persist(ep.conn, ep.s3, ep.show, ep.episode, ep.episode_id, scans, cfg)
    from nip.agents.clearance.checks import episode_occurrences

    occs = episode_occurrences(ep.conn, ep.show, ep.timeline, cfg)  # what the checks will see
    ep.tl = with_ocr(ep.timeline, scans, occs)
    log.info("%s %s: %d keyframes read, %d candidates", STAGE, ep.episode, len(scans), found)


def keyframes_of(tl: Timeline) -> Sequence[tuple[int, int, int]]:
    """(shot, n, frame) of every keyframe span of a timeline."""
    out = []
    for s in tl.spans:
        if s.kind is EvidenceKind.KEYFRAME and s.frames:
            shot, _, n = refs.parse(s.ref).id.partition(".")
            out.append((int(shot), int(n), s.frames[0]))
    return out
