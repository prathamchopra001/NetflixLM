"""The store-backed `Timeline` (B-057): what checks and verification read in `nip run --show`.

Spans in this order, the first three exactly as `build_timeline` builds them from the same files:
scenes (script order), shots then keyframes, subtitle cues per track (ingest order); then script
lines `{ep}/line/{scene}.{seq}`, transcript segments `{ep}/asr/{id}`, the show's active facts
`fact/{id}` (text = the source events' quotes, one per line; no frames) and clearance items
`clr/{id}` (text = the item name; no frames), so `emit` and `verify` resolve those refs unchanged.

Display: objects with frames get SMPTE `tc_in`/`tc_out`; scenes keep the script-estimate label
until alignment sets `episode.timeline_source = 'picture'` (B-061). Shot ref id = index (B-062).
"""

from fractions import Fraction
from typing import Any

from sqlalchemy import Connection, func, select
from sqlalchemy.dialects.postgresql import aggregate_order_by

from nip.contracts import refs
from nip.contracts.flag import EvidenceKind
from nip.contracts.timeline import Span, Timeline
from nip.store import schema
from nip.timecode import frame_to_smpte
from nip.timeline.estimate import NO_PICTURE_FPS

K = EvidenceKind


def _frames(r: Any) -> tuple[int, int] | None:
    return None if r is None else (r.lower, r.upper)


def episode_row(conn: Connection, show: str, episode: str) -> Any:
    """The `episode` row of (show slug, ref); LookupError when it was never ingested."""
    e = schema.episode
    row = conn.execute(
        select(e).join(schema.show).where(schema.show.c.slug == show, e.c.ref == episode)
    ).one_or_none()
    if row is None:
        raise LookupError(f"no episode {episode} of show {show!r}; run `nip ingest` first")
    return row


def load_timeline(conn: Connection, show: str, episode: str) -> Timeline:
    ep = episode_row(conn, show, episode)
    fps = Fraction(ep.fps_num, ep.fps_den) if ep.fps_num else NO_PICTURE_FPS
    start, drop = ep.start_tc_frames or 0, bool(ep.drop_frame)
    estimate = ep.timeline_source != "picture"

    def span(kind: K, ref: str, f: tuple[int, int] | None, **kw: Any) -> Span:
        if f is None:
            return Span(kind=kind, ref=ref, **kw)
        tc_in, tc_out = (frame_to_smpte(x + start, fps, drop) for x in f)  # out is exclusive
        return Span(kind=kind, ref=ref, frames=f, tc_in=tc_in, tc_out=tc_out, **kw)

    sh = schema.shot
    shots = conn.execute(
        select(sh.c.frames, sh.c.keyframes)
        .where(sh.c.episode_id == ep.id)
        .order_by(func.lower(sh.c.frames), sh.c.id)
    ).all()
    timed = [span(K.SHOT, refs.shot(episode, i), _frames(s.frames)) for i, s in enumerate(shots)]
    timed += [
        span(K.KEYFRAME, refs.keyframe(episode, i, k["n"]), (k["frame"], k["frame"] + 1))
        for i, s in enumerate(shots)
        for k in s.keyframes
    ]
    tr, cue = schema.subtitle_track, schema.subtitle_cue
    for lang, idx, f, text in conn.execute(
        select(tr.c.lang, cue.c.idx, cue.c.frames, cue.c.text)
        .join(cue, cue.c.track_id == tr.c.id)
        .where(tr.c.episode_id == ep.id)
        .order_by(tr.c.id, cue.c.idx)
    ):
        timed.append(span(K.SUBTITLE_CUE, refs.cue(episode, lang, idx), _frames(f), lang=lang,
                          text=text))  # fmt: skip

    sc = schema.scene
    scenes = conn.execute(
        select(sc.c.id, sc.c.script_scene_no, sc.c.heading, sc.c.frames)
        .where(sc.c.episode_id == ep.id)
        .order_by(sc.c.id)
    ).all()
    estimated = [_frames(s.frames) for s in scenes]
    end = (
        ep.duration_frames
        if ep.fps_num
        else max([0, *(f[1] for f in estimated if f), *(s.frames[1] for s in timed if s.frames)])
    )
    spans = []
    for s, f in zip(scenes, estimated, strict=True):
        f = (f[0], min(f[1], end)) if f and f[0] < end else None
        label = f"{episode} · Sc {s.script_scene_no} (script estimate)" if estimate else None
        ref = refs.scene(episode, s.script_scene_no)
        spans.append(
            Span(kind=K.SCENE, ref=ref, frames=f, text=s.heading, scene=label)
            if estimate
            else span(K.SCENE, ref, f, text=s.heading)
        )
    spans += timed

    ln = schema.script_line
    for no, seq, f, text in conn.execute(
        select(sc.c.script_scene_no, ln.c.seq, ln.c.frames, ln.c.text)
        .join(ln, ln.c.scene_id == sc.c.id)
        .where(sc.c.episode_id == ep.id)
        .order_by(sc.c.id, ln.c.seq)
    ):
        spans.append(span(K.SCRIPT_LINE, f"{episode}/line/{no}.{seq}", _frames(f), text=text))
    ts = schema.transcript_segment
    for sid, f, lang, text in conn.execute(
        select(ts.c.id, ts.c.frames, ts.c.lang, ts.c.text)
        .where(ts.c.episode_id == ep.id)
        .order_by(ts.c.id)
    ):
        spans.append(
            span(K.TRANSCRIPT_SEGMENT, f"{episode}/asr/{sid}", _frames(f), lang=lang, text=text)
        )
    fa, fe = schema.fact, schema.fact_event
    for fid, quotes in conn.execute(
        select(
            fa.c.id,
            func.array_agg(aggregate_order_by(fe.c.quote, fe.c.id)).filter(fe.c.id.is_not(None)),
        )
        .outerjoin(fe, fe.c.id == fa.c.source_event_ids.any_())
        .where(fa.c.show_id == ep.show_id, fa.c.status == "active")
        .group_by(fa.c.id)
        .order_by(fa.c.id)
    ):
        spans.append(Span(kind=K.FACT, ref=f"fact/{fid}", text="\n".join(quotes or [])))
    ci = schema.clearance_item
    for cid, name in conn.execute(
        select(ci.c.id, ci.c.name).where(ci.c.show_id == ep.show_id).order_by(ci.c.id)
    ):
        spans.append(Span(kind=K.CLEARANCE_ITEM, ref=f"clr/{cid}", text=name))

    return Timeline(
        episode=episode,
        fps=(fps.numerator, fps.denominator),
        duration_frames=end,
        start_tc_frames=start,
        drop_frame=drop,
        source="script_estimate" if estimate else "picture",
        spans=tuple(spans),
    )
