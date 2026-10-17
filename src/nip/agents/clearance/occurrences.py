"""Occurrences and prominence (architecture.md > Agent 2 > Occurrences).

A detection is one text read at one keyframe. Detections of the same item (the registry item it
matched, else its normalized text) whose keyframes lie within `occurrence_gap_s` of each other,
across consecutive shots too, become ONE occurrence with a frame range, the screen time it covers
and a prominence score from the box area, its centrality, the sharpness of the text crop (variance
of the OpenCV Laplacian, measured by the OCR stage) and the duration.

What a keyframe proves. It shows the text at that frame only. Its *cell* is the stretch of its shot
nearer to it than to any other keyframe, capped at `cell_cap_s` and centred on the frame; screen
time and the frame range are built from cells, so a long shot with one keyframe does not claim the
whole shot. Scene boundaries are not used: store scenes are only script estimates until alignment,
and a text that returns within 2 s across a scene cut is still the same sign.
"""

import json
import logging
import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from typing import Any

import cv2
import numpy as np

from nip.agents.clearance.matching import Match, Registry, match, normalize
from nip.contracts import refs
from nip.contracts.flag import EvidenceKind
from nip.contracts.timeline import Timeline

log = logging.getLogger(__name__)

Box = tuple[float, float, float, float]  # normalized [x, y, w, h]


@dataclass(frozen=True)
class Hit:
    """One typed candidate read at one keyframe (a `detection` row of label clr.*)."""

    check: str
    text: str
    shot: int  # index of the shot (the id in its `{ep}/shot/{id}` ref)
    n: int  # keyframe number inside the shot
    box: Box
    confidence: float
    model_variant: str
    sharpness: float | None = None  # variance of the Laplacian of the text crop
    detection_id: int | None = None  # the row, for the crop image `crops/{id}.jpg`


@dataclass(frozen=True)
class Occurrence:
    check: str
    text: str  # what was read at the best keyframe
    match: Match
    hits: tuple[Hit, ...]
    shots: tuple[int, ...]  # distinct shot indexes, ascending
    frames: tuple[int, int]  # first cell start, last cell end
    screen_frames: int  # frames covered by cells (gaps between hits not counted)
    prominence: float  # 0-1
    featured: bool
    best: Hit  # the keyframe shown as evidence: largest, most central, sharpest view
    confidence: float  # the strongest hit
    severity: int

    @property
    def key(self) -> str:
        """Stable name of the occurrence inside its episode (work unit key, flag fingerprint)."""
        m = self.match.item
        who = f"clr/{m.id}" if m else normalize(self.check, self.text)
        return f"{self.check}/{who}/f{self.frames[0]}"


Geometry = tuple[
    str, tuple[int, int], tuple[tuple[int, int], ...], tuple[tuple[int, int, int], ...]
]  # (episode, fps, shot spans by index, (shot, n, frame) keyframes)


def geometry(tl: Timeline, keyframes: Iterable[tuple[int, int, int]] | None = None) -> Geometry:
    """The shots (by index) and keyframes of a timeline, as hashable tuples. `keyframes` are
    (shot, n, frame); without them the keyframe spans of `tl` are read, which is only right while
    they are single frames (the OCR stage later stretches them to the stretch they stand for)."""
    shots: dict[int, tuple[int, int]] = {}
    kfs: list[tuple[int, int, int]] = [] if keyframes is None else list(keyframes)
    for s in tl.spans:
        if s.frames is None:
            continue
        if s.kind is EvidenceKind.SHOT:
            shots[int(refs.parse(s.ref).id)] = s.frames
        elif s.kind is EvidenceKind.KEYFRAME and keyframes is None:
            shot, _, n = refs.parse(s.ref).id.partition(".")
            kfs.append((int(shot), int(n), s.frames[0]))
    if sorted(shots) != list(range(len(shots))):
        raise ValueError(
            f"{tl.episode}: shot ids are not 0..{len(shots) - 1} (a shot id is its index)"
        )
    return tl.episode, tl.fps, tuple(shots[i] for i in sorted(shots)), tuple(sorted(kfs))


def cell_cap_frames(tl: Timeline, cfg: dict[str, Any]) -> int:
    return round(Fraction(*tl.fps) * Fraction(cfg["cell_cap_s"]).limit_denominator(1000))


def cells(geo: Geometry, cap_frames: int) -> dict[tuple[int, int], tuple[int, int]]:
    """(shot, n) -> [lo, hi): the stretch of the shot a keyframe stands for."""
    _, _, shots, kfs = geo
    by_shot: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for shot, n, f in kfs:
        by_shot[shot].append((f, n))
    out = {}
    for shot, items in by_shot.items():
        a, b = shots[shot]
        items.sort()
        for i, (f, n) in enumerate(items):
            lo = a if i == 0 else (items[i - 1][0] + f + 1) // 2
            hi = b if i == len(items) - 1 else (f + items[i + 1][0] + 1) // 2
            half = max(cap_frames // 2, 1)
            lo, hi = max(lo, f - half), min(hi, f + half)
            out[shot, n] = (lo, max(hi, lo + 1))
    return out


def windows(geo: Geometry, cap_frames: int) -> dict[tuple[int, int], tuple[int, int]]:
    """(shot, n) -> [lo, hi): what a read keyframe's span covers, `cap_frames` centred on the frame
    inside its shot, whatever the sampling density. A flag's claim is this range, so it covers about
    the seconds the text was seen (a denser policy must not make claims narrower)."""
    _, _, shots, kfs = geo
    half = max(cap_frames // 2, 1)
    out = {}
    for shot, n, f in kfs:
        a, b = shots[shot]
        lo, hi = max(a, f - half), min(b, f + half)
        out[shot, n] = (lo, max(hi, lo + 1))
    return out


def view_score(hit: Hit, prom: dict[str, Any]) -> tuple[float, float, float]:
    """(area, centrality, sharpness), each scaled to 0-1."""
    x, y, w, h = hit.box
    area = min(1.0, w * h / prom["area_ref"])
    centrality = max(0.0, 1.0 - math.hypot(x + w / 2 - 0.5, y + h / 2 - 0.5) / math.hypot(0.5, 0.5))
    sharp = 0.5 if hit.sharpness is None else min(1.0, hit.sharpness / prom["sharpness_ref"])
    return area, centrality, sharp


def prominence(hits: tuple[Hit, ...], screen_s: float, prom: dict[str, Any]) -> tuple[float, Hit]:
    """(score, best hit): the best view's area, centrality and sharpness plus the duration."""
    w = prom["weights"]

    def view(hit: Hit) -> float:
        a, c, s = view_score(hit, prom)
        return float(w["area"] * a + w["centrality"] * c + w["sharpness"] * s)

    best = max(hits, key=lambda h: (view(h), h.confidence))
    dur = min(1.0, screen_s / prom["duration_ref_s"])
    return view(best) + w["duration"] * dur, best


def severity(m: Match, featured: bool, sev: dict[str, int]) -> int:
    if m.status in ("denied", "pending"):
        return int(sev[m.status])
    return int(sev["featured" if featured else "background"])


@lru_cache(maxsize=8)
def _analyze(
    hits: tuple[Hit, ...], registry: Registry, geo: Geometry, cfg_json: str
) -> tuple[Occurrence, ...]:
    cfg = json.loads(cfg_json)
    episode, fps_ratio, _, _ = geo
    fps = Fraction(*fps_ratio)
    cell = cells(geo, round(fps * Fraction(cfg["cell_cap_s"]).limit_denominator(1000)))
    gap = fps * Fraction(cfg["occurrence_gap_s"]).limit_denominator(1000)
    groups: dict[tuple[str, str], list[tuple[Hit, Match]]] = defaultdict(list)
    for h in hits:
        if (h.shot, h.n) not in cell:
            log.warning(
                "detection %r at kf %s.%s: no such keyframe in the timeline", h.text, h.shot, h.n
            )
            continue
        m = match(registry, h.check, h.text, episode, cfg["match_threshold"])
        if m.status == "fictional":
            continue  # not a clearance item
        key = f"clr/{m.item.id}" if m.item else normalize(h.check, h.text)
        groups[h.check, key].append((h, m))
    out = []
    for members in groups.values():
        members.sort(key=lambda hm: cell[hm[0].shot, hm[0].n])
        run = [members[0]]
        end = cell[members[0][0].shot, members[0][0].n][1]
        for hm in members[1:]:
            lo, hi = cell[hm[0].shot, hm[0].n]
            if lo - end <= gap:  # a gap of exactly occurrence_gap_s still merges
                run.append(hm)
                end = max(end, hi)
            else:
                out.append(_occurrence(run, cell, fps, cfg))
                run, end = [hm], hi
        out.append(_occurrence(run, cell, fps, cfg))
    out.sort(key=lambda o: (o.frames, o.check, o.text))
    return tuple(out)


def _occurrence(
    run: list[tuple[Hit, Match]],
    cell_of: dict[tuple[int, int], tuple[int, int]],
    fps: Fraction,
    cfg: dict[str, Any],
) -> Occurrence:
    hits = tuple(h for h, _ in run)
    spans = sorted({cell_of[h.shot, h.n] for h in hits})
    covered = 0
    top = spans[0][0]
    for lo, hi in spans:  # cells of different keyframes never overlap; a duplicate cell is one
        covered += hi - max(lo, top)
        top = max(top, hi)
    score, best = prominence(hits, float(covered / fps), cfg["prominence"])
    featured = score >= cfg["prominence"]["featured_min"]
    m = run[0][1]
    return Occurrence(
        check=best.check,
        text=best.text,
        match=m,
        hits=hits,
        shots=tuple(sorted({h.shot for h in hits})),
        frames=(spans[0][0], max(hi for _, hi in spans)),
        screen_frames=covered,
        prominence=score,
        featured=featured,
        best=best,
        confidence=max(h.confidence for h in hits),
        severity=severity(m, featured, cfg["severity"]),
    )


def analyze(
    hits: Sequence[Hit],
    registry: Registry,
    tl: Timeline,
    cfg: dict[str, Any],
    keyframes: Iterable[tuple[int, int, int]] | None = None,
) -> list[Occurrence]:
    """Occurrences of `hits` in the episode of `tl` (`cfg`: the `clearance:` block of
    pipeline.yaml; `keyframes`: (shot, n, frame), see `geometry`). Hits at a keyframe the episode
    lacks are skipped with a warning."""
    geo = geometry(tl, keyframes)
    return list(_analyze(tuple(hits), registry, geo, json.dumps(cfg, sort_keys=True)))


def decode(image: bytes, gray: bool = False) -> "np.ndarray[Any, Any]":
    img = cv2.imdecode(
        np.frombuffer(image, np.uint8), cv2.IMREAD_GRAYSCALE if gray else cv2.IMREAD_COLOR
    )
    if img is None:
        raise ValueError("not a decodable image")
    return img


def crop(img: "np.ndarray[Any, Any]", box: Box, pad: float) -> "np.ndarray[Any, Any]":
    """The region of `box` (normalized [x, y, w, h]), padded by `pad` of its size."""
    h, w = img.shape[:2]
    x, y, bw, bh = box
    x0, x1 = int(max(0, x - pad * bw) * w), int(min(1, x + bw * (1 + pad)) * w)
    y0, y1 = int(max(0, y - pad * bh) * h), int(min(1, y + bh * (1 + pad)) * h)
    return img[y0 : max(y1, y0 + 1), x0 : max(x1, x0 + 1)]


def sharpness(image: bytes, box: Box, pad: float = 0.1) -> float:
    """Variance of the Laplacian of the grayscale crop of `box` (higher: sharper text)."""
    return float(cv2.Laplacian(crop(decode(image, gray=True), box, pad), cv2.CV_64F).var())
