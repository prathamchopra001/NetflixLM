"""Target <-> source subtitle cue alignment (architecture.md > Stage 2: Target <-> source cues).

A target cue links to the source cues it overlaps in time, so 1:n splits and n:1 merges both come
out as several links. Tracks timed with a constant offset or at the wrong frame rate (loc.offset,
loc.drift) overlap nothing at first sight, so the tracks are first related by a robust line
(`Fit`: target start = (1 + slope) * source start + intercept): the best coincidence of the two
onset patterns over a grid of slopes and offsets gives a first guess, which nearest-start matching
and a Theil-Sen fit refine over a few rounds. Overlap is
then measured with the source cues moved onto that line, so term checks keep working on a drifted
track, and the same line is what `loc.drift` / `loc.offset` classify. The fit is a function of the
two tracks only; `stage` persists the links as `subtitle_cue.aligned_source_cue_ids`.

`ponytail:` one line per track (a track with a mid-episode re-sync is not modelled), slopes within
+-MAX_SLOPE, offsets within +-MAX_OFFSET_S; Theil-Sen samples at most `SAMPLE` cues of a track.
"""

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

import numpy as np
import yaml
from sqlalchemy import Connection, bindparam, select, update

from nip.config import config_dir
from nip.contracts import refs
from nip.contracts.flag import EvidenceKind
from nip.contracts.timeline import Span, Timeline
from nip.store import schema

SAMPLE = 400  # Theil-Sen is quadratic: it fits at most this many points
ROUNDS = (3.0, 2.0, 1.5)  # nearest-start tolerance (s) of each refinement round
TIGHT_S = 0.4  # a target start this close to its source start (on the line) is an exact match
MAX_SLOPE = 0.3  # drift searched: 30 fps timing on a 24 fps picture is 0.25
MAX_OFFSET_S = 60  # offset searched (s)
INLIER_S = 1.5  # a paired cue within this of the line is an inlier
MIN_PAIRS = 3  # fewer matched cues than this: no line


@dataclass(frozen=True)
class Fit:
    """Line through (source start, target start - source start), in seconds of episode time."""

    slope: float  # drift per second of episode time (0.0417 = 25 fps timing on a 24 fps picture)
    intercept_s: float  # target - source at episode time 0
    median_s: float  # median target - source start of the inliers (the offset when slope ~ 0)
    n: int  # inlier pairs
    span_s: float  # source time covered by the inliers


@dataclass(frozen=True)
class Alignment:
    source_lang: str
    target_lang: str
    links: dict[str, tuple[str, ...]]  # target cue ref -> overlapping source cue refs, in order
    fit: Fit | None  # None: too few matching cues to fit a line


@dataclass(frozen=True)
class Group:
    """Cues that overlap each other transitively: 1:1, 1:n, n:1 or n:m. Both tuples are in order."""

    sources: tuple[str, ...]
    targets: tuple[str, ...]


def min_overlap() -> float:
    """Overlap share (of the shorter cue) that links two cues: `timing.align_min_overlap` of the
    base rule pack (the alignment is language-independent)."""
    base = yaml.safe_load((config_dir() / "languages" / "_base.yaml").read_text(encoding="utf-8"))
    return float(base["timing"]["align_min_overlap"])


def cue_idx(ref: str) -> int:
    return int(refs.parse(ref).id)


def track(tl: Timeline, lang: str) -> list[Span]:
    """Placed cues of `lang` in time order."""
    return sorted(
        (s for s in tl.of(EvidenceKind.SUBTITLE_CUE, lang) if s.frames is not None),
        key=lambda s: s.frames or (0, 0),
    )


def _seconds(cues: list[Span], fps: Fraction) -> np.ndarray:
    return np.array([[float(Fraction(f) / fps) for f in c.frames or (0, 0)] for c in cues])


def theil_sen(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """(slope, intercept) of the median pairwise slope line through (x, y)."""
    if len(x) > SAMPLE:
        keep = np.linspace(0, len(x) - 1, SAMPLE).astype(int)
        x, y = x[keep], y[keep]
    i, j = np.triu_indices(len(x), 1)
    dx = x[j] - x[i]
    ok = dx > 1e-6
    m = float(np.median((y[j] - y[i])[ok] / dx[ok])) if ok.any() else 0.0
    return m, float(np.median(y - m * x))


def _nearest(sx: np.ndarray, pred: np.ndarray) -> np.ndarray:
    """Index of the source start nearest to each predicted source time."""
    k = np.clip(np.searchsorted(sx, pred), 1, len(sx) - 1)
    return np.where(np.abs(sx[k] - pred) < np.abs(sx[k - 1] - pred), k, k - 1)


def _coarse(sx: np.ndarray, tx: np.ndarray) -> tuple[float, float]:
    """(slope, offset) of the pairing of the two onset patterns that coincides most.

    Both tracks' cue starts are binned to whole seconds; for every slope of the grid the scaled
    source onsets are cross-correlated with the target onsets (FFT) over offsets of +-MAX_OFFSET_S.
    Neither cue counts nor ranks matter, so merges and splits cannot lose the pairing."""
    span = float(max(tx.max(), sx.max()))
    step = 0.5 / max(span, 1.0)  # a step in slope moves the last cue by half a bin
    n = int(np.ceil(span * (1 + MAX_SLOPE))) + 2 * MAX_OFFSET_S + 8
    size = 1 << int(np.ceil(np.log2(n)))
    tgt = np.bincount((tx + MAX_OFFSET_S).astype(int), minlength=size)[:size].astype(float)
    tgt = tgt + np.roll(tgt, 1) + np.roll(tgt, -1)  # a start within a bin of another coincides
    spec = np.conj(np.fft.rfft(tgt))
    slopes = np.arange(-MAX_SLOPE, MAX_SLOPE + step / 2, step)
    slopes = slopes[np.argsort(np.abs(slopes), kind="stable")]  # ties keep the smaller slope
    lags = np.arange(-MAX_OFFSET_S, MAX_OFFSET_S + 1)
    best = (-1.0, 0.0, 0.0)
    for m in slopes:
        idx = ((1 + m) * sx + MAX_OFFSET_S).astype(int)
        src = np.bincount(idx[(idx >= 0) & (idx < size)], minlength=size).astype(float)
        corr = np.fft.irfft(np.fft.rfft(src) * spec, size)  # corr[k] = sum_i src[i] * tgt[i - k]
        score = corr[(-lags) % size]  # lag d: target = source + d
        k = int(np.argmax(score - 1e-6 * np.abs(lags)))  # ties keep the smaller offset
        if score[k] > best[0]:
            best = (float(score[k]), float(m), float(lags[k]))
    return best[1], best[2]


def _refine(
    sx: np.ndarray, tx: np.ndarray, m: float, a: float
) -> tuple[int, float, float, np.ndarray]:
    """Nearest-start pairing and Theil-Sen rounds from the line (m, a): (target starts within
    TIGHT_S of their source under the final line, slope, intercept, source index per target)."""
    for tol in ROUNDS:
        pred = (tx - a) / (1 + m)
        k = _nearest(sx, pred)
        ok = np.abs(sx[k] - pred) <= tol
        if ok.sum() < MIN_PAIRS:
            return 0, m, a, k
        m, a = theil_sen(sx[k][ok], (tx - sx[k])[ok])
    k = _nearest(sx, (tx - a) / (1 + m))
    tight = int((np.abs(tx - (sx[k] * (1 + m) + a)) <= TIGHT_S).sum())
    return tight, m, a, k


def estimate(sx: np.ndarray, tx: np.ndarray) -> Fit | None:
    """The line relating sorted source starts `sx` to sorted target starts `tx`, or None.

    Two starting lines are refined: "same timing" and the best onset coincidence (`_coarse`); the
    one that puts more target starts within `TIGHT_S` of a source start wins, "same timing" on a
    tie. (On a short track a coarse search over thousands of lines finds a coincidence anywhere.)"""
    if len(sx) < 2 or len(tx) < 2:
        return None
    start = [(0.0, 0.0), _coarse(sx, tx)]
    tight, m, a, k = max((_refine(sx, tx, *s0) for s0 in start), key=lambda r: r[0])
    if tight < MIN_PAIRS:
        return None
    y = tx - sx[k]
    inl = np.abs(y - (m * sx[k] + a)) <= INLIER_S
    x = sx[k][inl]
    return Fit(m, a, float(np.median(y[inl])), int(inl.sum()), float(x.max() - x.min()))


def align(tl: Timeline, source_lang: str, target_lang: str) -> Alignment:
    """Links of every target cue to the source cues it overlaps (after moving the source onto the
    fitted line). A cue overlapping nothing links to ()."""
    fps = Fraction(*tl.fps)
    src, tgt = track(tl, source_lang), track(tl, target_lang)
    if not src or not tgt:
        return Alignment(source_lang, target_lang, {t.ref: () for t in tgt}, None)
    s, t = _seconds(src, fps), _seconds(tgt, fps)
    fit = estimate(s[:, 0], t[:, 0])
    m, a = (fit.slope, fit.intercept_s) if fit else (0.0, 0.0)
    s = s * (1 + m) + a
    share = min_overlap()
    reach = float((s[:, 1] - s[:, 0]).max())
    links: dict[str, tuple[str, ...]] = {}
    for j, (ts, te) in enumerate(t):
        lo = np.searchsorted(s[:, 0], ts - reach, "left")
        hi = np.searchsorted(s[:, 0], te, "left")
        hits = []
        for i in range(lo, hi):
            ov = min(s[i, 1], te) - max(s[i, 0], ts)
            if ov > 0 and ov >= share * min(s[i, 1] - s[i, 0], te - ts):
                hits.append(src[i].ref)
        links[tgt[j].ref] = tuple(sorted(hits, key=cue_idx))
    return Alignment(source_lang, target_lang, links, fit)


_CACHE: dict[tuple[int, str, str], tuple[Timeline, Alignment]] = {}


def aligned(tl: Timeline, source_lang: str, target_lang: str) -> Alignment:
    """`align`, remembered for the last few timelines: drift, offset and term checks of one run
    share one alignment per track. A timeline is immutable, so the entry holds it by identity."""
    key = (id(tl), source_lang, target_lang)
    hit = _CACHE.get(key)
    if hit is None or hit[0] is not tl:
        if len(_CACHE) >= 16:
            _CACHE.clear()
        hit = _CACHE[key] = (tl, align(tl, source_lang, target_lang))
    return hit[1]


def groups(al: Alignment) -> list[Group]:
    """Connected groups of the links, ordered by their first target cue; target cues linked to
    nothing and source cues linked to nothing are not groups."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for t, ss in al.links.items():
        for s in ss:
            parent[find(s)] = find(t)
    by_root: dict[str, tuple[set[str], set[str]]] = defaultdict(lambda: (set(), set()))
    for t, ss in al.links.items():
        if ss:
            by_root[find(t)][1].add(t)
            for s in ss:
                by_root[find(s)][0].add(s)
    out = [
        Group(tuple(sorted(ss, key=cue_idx)), tuple(sorted(ts, key=cue_idx)))
        for ss, ts in by_root.values()
    ]
    return sorted(out, key=lambda g: cue_idx(g.targets[0]))


def write_alignment(conn: Connection, episode_id: int, als: list[Alignment]) -> None:
    """Set `aligned_source_cue_ids` of every target cue ([] = aligned to nothing)."""
    tr, cue = schema.subtitle_track, schema.subtitle_cue
    ids = {
        (lang, idx): cid
        for lang, idx, cid in conn.execute(
            select(tr.c.lang, cue.c.idx, cue.c.id)
            .join(cue, cue.c.track_id == tr.c.id)
            .where(tr.c.episode_id == episode_id)
        )
    }
    rows = [
        {
            "b_id": ids[(al.target_lang, cue_idx(t))],
            "b_ids": [ids[(al.source_lang, cue_idx(s))] for s in ss],
        }
        for al in als
        for t, ss in al.links.items()
    ]
    if rows:
        conn.execute(
            update(cue)
            .where(cue.c.id == bindparam("b_id"))
            .values(aligned_source_cue_ids=bindparam("b_ids")),
            rows,
        )


def stage(ep: Any) -> None:
    """Pipeline stage (`add_stage("timeline.cue_align", cue_align.stage, before="checks")`):
    persist the alignment of every target track with the source track, one work unit per track."""
    tr = schema.subtitle_track
    tracks = ep.conn.execute(
        select(tr.c.lang, tr.c.role).where(tr.c.episode_id == ep.episode_id).order_by(tr.c.id)
    ).all()
    source = next((lang for lang, role in tracks if role == "source"), None)
    if source is None:
        return
    for lang in (lang for lang, role in tracks if role == "target"):
        with ep.unit("timeline.cue_align", f"{ep.episode}/{lang}"):
            write_alignment(ep.conn, ep.episode_id, [aligned(ep.timeline, source, lang)])
