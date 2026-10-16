"""Script <-> transcript alignment: script dialogue lines and scenes get frames on the picture axis.

Two interchangeable line matchers (EXP-004), both monotonic (script order = transcript order):
`align_tokens` (difflib over normalized word tokens) and `align_lines` (rapidfuzz partial match of
each line against the transcript text after the previous line). `place_scenes` turns anchored lines
into scene ranges snapped to shot cuts; a scene with a lot of dialogue but no anchored line is
`not_in_cut`.
"""

import json
import re
from bisect import bisect_right
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from fractions import Fraction
from pathlib import Path
from typing import Annotated, Any

import typer
from rapidfuzz import fuzz

from nip.contracts import refs
from nip.contracts.timeline import Timeline
from nip.ingest import parse
from nip.ingest.media import probe
from nip.ingest.script import Script
from nip.timecode import frame_to_smpte
from nip.timeline.asr import TranscriptSegment, TranscriptWord
from nip.timeline.estimate import build_timeline
from nip.timeline.picture import timeline_config

app = typer.Typer(no_args_is_help=True)

LineKey = tuple[int, int]  # (scene index, element index) in script order
_PUNCT = re.compile(r"[^\w\s]|_")
NOT_IN_CUT_WORDS = 8  # fewer dialogue words than this and a missed scene is more likely an ASR miss
MAX_GAP = 6  # token matches further apart than this (transcript words) are not one line's cluster


@dataclass(frozen=True)
class LineMatch:
    frames: tuple[int, int]
    score: float  # token variant: share of the line's tokens in the matched cluster; line: 0-100


@dataclass(frozen=True)
class ScenePlacement:
    frames: tuple[int, int] | None
    in_cut: bool


@dataclass(frozen=True)
class Alignment:
    lines: dict[LineKey, LineMatch]
    scenes: list[ScenePlacement]


def normalize(text: str) -> list[str]:
    """Lowercase word tokens: punctuation dropped, apostrophes joined ("you're" -> "youre")."""
    return _PUNCT.sub("", text.lower().replace("’", "'").replace("'", "")).split()


def dialogue(script: Script) -> list[tuple[LineKey, list[str]]]:
    return [
        ((si, ei), toks)
        for si, sc in enumerate(script.scenes)
        for ei, e in enumerate(sc.elements)
        if e.kind == "dialogue" and (toks := normalize(e.text))
    ]


def _words(segments: Sequence[TranscriptSegment]) -> list[tuple[str, TranscriptWord]]:
    """(normalized token, word) in time order; words that normalize to nothing are dropped and a
    word that normalizes to several tokens ("well-known") keeps its time for each."""
    return [(t, w) for s in segments for w in s.words for t in normalize(w.w)]


def _start(w: TranscriptWord, cap: int | None) -> int:
    """Line start from its first word. Whisper's first word after silence or music starts early
    and runs long (a 1 s "This" on Sintel); its end is the steadier edge, so a word longer than
    `cap` frames starts `cap` frames before it ends."""
    return w.f_in if cap is None else max(w.f_in, w.f_out - cap)


def align_tokens(
    script: Script,
    segments: Sequence[TranscriptSegment],
    min_match: float = 0.5,
    first_word_cap: int | None = None,
) -> dict[LineKey, LineMatch]:
    lines, words = dialogue(script), _words(segments)
    s_tok = [t for _, toks in lines for t in toks]
    owner = [k for k, toks in lines for _ in toks]
    sm = SequenceMatcher(None, s_tok, [t for t, _ in words], autojunk=False)
    # ponytail: difflib is quadratic worst case; fine to ~10k tokens (a feature), swap for a banded
    # DP if a full-length episode is slow.
    hits: dict[LineKey, list[int]] = {}
    for a, b, n in sm.get_matching_blocks():
        for i in range(n):
            hits.setdefault(owner[a + i], []).append(b + i)
    out: dict[LineKey, LineMatch] = {}
    sizes = {k: len(toks) for k, toks in lines}
    for k, idx in hits.items():
        clusters: list[list[int]] = [[idx[0]]]
        for j in idx[1:]:
            if j - clusters[-1][-1] <= MAX_GAP:
                clusters[-1].append(j)
            else:
                clusters.append([j])
        best = max(clusters, key=len)
        ratio = len(best) / sizes[k]
        if ratio >= min_match:
            first, last = words[best[0]][1], words[best[-1]][1]
            out[k] = LineMatch((_start(first, first_word_cap), last.f_out), ratio)
    return out


def align_lines(
    script: Script,
    segments: Sequence[TranscriptSegment],
    min_score: float = 75.0,
    first_word_cap: int | None = None,
) -> dict[LineKey, LineMatch]:
    words = _words(segments)
    text, starts, pos = "", [], 0
    for tok, _ in words:
        starts.append(pos)
        text += tok + " "
        pos += len(tok) + 1
    out: dict[LineKey, LineMatch] = {}
    cursor = 0
    for k, toks in dialogue(script):
        line = " ".join(toks)
        region = text[cursor : cursor + 400 + 6 * len(line)]
        if len(region) < len(line):
            continue
        m = fuzz.partial_ratio_alignment(line, region, score_cutoff=min_score)
        if m is None:
            continue
        a = bisect_right(starts, cursor + m.dest_start) - 1
        b = bisect_right(starts, cursor + m.dest_end - 1) - 1
        while a < b and words[a][0] not in toks:  # the fuzzy window can start on a stray word
            a += 1
        while b > a and words[b][0] not in toks:
            b -= 1
        out[k] = LineMatch((_start(words[a][1], first_word_cap), words[b][1].f_out), m.score)
        cursor += m.dest_end
    return out


VARIANTS: dict[str, Callable[..., dict[LineKey, LineMatch]]] = {
    "token": align_tokens,
    "line": align_lines,
}


def place_scenes(
    script: Script,
    lines: dict[LineKey, LineMatch],
    shots: Sequence[tuple[int, int]],
    duration_frames: int,
) -> list[ScenePlacement]:
    """Scene ranges from anchored lines. A scene starts at the latest shot cut at or before its
    first line (and after the previous anchored scene's last line), so no spoken line is cut off;
    it ends where the next anchored scene starts. Scenes in between that have no dialogue share
    that gap. A scene with at least NOT_IN_CUT_WORDS dialogue words but no anchored line is
    `not_in_cut`; a shorter one is more likely an ASR miss, so it stays in the cut (unplaced when
    there is no gap to share)."""
    cuts = sorted({0, duration_frames, *(a for a, _ in shots)})
    anch: list[tuple[int, int, int]] = []  # (scene index, first start, last end)
    for si in range(len(script.scenes)):
        fr = [m.frames for (s, _), m in lines.items() if s == si]
        if fr:
            anch.append((si, min(a for a, _ in fr), max(b for _, b in fr)))
    start: dict[int, int] = {}
    end: dict[int, int] = {}
    prev_end = 0
    for n, (si, first, last) in enumerate(anch):
        start[si] = max((c for c in cuts if prev_end <= c <= first), default=first)
        nxt = anch[n + 1][1] if n + 1 < len(anch) else duration_frames
        end[si] = min((c for c in cuts if last <= c <= nxt), default=last)
        prev_end = last
    anchored = [si for si, _, _ in anch]
    place: list[ScenePlacement] = []
    for si, sc in enumerate(script.scenes):
        if si in start:
            e = end[si]
            if si + 1 in start:
                e = start[si + 1]  # neighbours tile: the gap belongs to the scene that just ended
            place.append(ScenePlacement((start[si], max(e, start[si] + 1)), True))
        else:
            words = sum(len(normalize(e.text)) for e in sc.elements if e.kind == "dialogue")
            spoken = words >= NOT_IN_CUT_WORDS
            place.append(ScenePlacement(None, not spoken))
    return _fill_silent(script, place, anchored, duration_frames)


def _fill_silent(
    script: Script, place: list[ScenePlacement], anchored: list[int], duration: int
) -> list[ScenePlacement]:
    """Dialogue-free scenes between two anchored scenes share the gap equally."""
    out = list(place)
    for a, b in zip(anchored, anchored[1:], strict=False):
        mid = [i for i in range(a + 1, b) if place[i].in_cut and place[i].frames is None]
        lo, hi = place[a].frames, place[b].frames
        if not mid or lo is None or hi is None or hi[0] <= lo[1]:
            continue
        cut = [lo[1] + (hi[0] - lo[1]) * k // len(mid) for k in range(len(mid) + 1)]
        for k, i in enumerate(mid):
            out[i] = ScenePlacement((cut[k], max(cut[k + 1], cut[k] + 1)), True)
    return out


def align(
    script: Script,
    segments: Sequence[TranscriptSegment],
    shots: Sequence[tuple[int, int]],
    duration_frames: int,
    variant: str = "token",
    **kw: Any,
) -> Alignment:
    lines = VARIANTS[variant](script, segments, **kw)
    return Alignment(lines, place_scenes(script, lines, shots, duration_frames))


def align_episode(
    script: Script,
    segments: Sequence[TranscriptSegment],
    shots: Sequence[tuple[int, int]],
    fps: Fraction,
    duration_frames: int,
    cfg: dict[str, Any] | None = None,
) -> Alignment:
    """`align` with the `timeline.align` settings of config/pipeline.yaml."""
    cfg = cfg or timeline_config()["align"]
    kw: dict[str, Any] = {"first_word_cap": round(cfg["first_word_cap_s"] * fps)}
    kw |= (
        {"min_match": cfg["min_match"]}
        if cfg["variant"] == "token"
        else {"min_score": cfg["min_score"]}
    )
    return align(script, segments, shots, duration_frames, cfg["variant"], **kw)


def segment_lines(result: Alignment, segments: Sequence[TranscriptSegment]) -> list[LineKey | None]:
    """The line each transcript segment overlaps most (`transcript_segment.aligned_line_id`)."""
    out: list[LineKey | None] = []
    for s in segments:
        best, key = 0, None
        for k, m in result.lines.items():
            ov = min(s.frames[1], m.frames[1]) - max(s.frames[0], m.frames[0])
            if ov > best:
                best, key = ov, k
        out.append(key)
    return out


def with_picture_timing(tl: Timeline, script: Script, result: Alignment) -> Timeline:
    """`tl` with scene spans on the frame axis (SMPTE labels, not the script-estimate label)."""
    by_ref = {
        refs.scene(tl.episode, sc.number): p
        for sc, p in zip(script.scenes, result.scenes, strict=True)
    }
    f = Fraction(*tl.fps)

    def tc(x: int) -> str:
        return frame_to_smpte(x + tl.start_tc_frames, f, tl.drop_frame)

    spans = []
    for s in tl.spans:
        p = by_ref.get(s.ref)
        if p is None:
            spans.append(s)
        elif p.frames is None:
            spans.append(
                s.model_copy(
                    update={
                        "frames": None,
                        "tc_in": None,
                        "tc_out": None,
                        "scene": f"{s.ref} (not in cut)",
                    }
                )
            )
        else:
            spans.append(
                s.model_copy(
                    update={
                        "frames": p.frames,
                        "tc_in": tc(p.frames[0]),
                        "tc_out": tc(p.frames[1]),
                        "scene": None,
                    }
                )
            )
    return tl.model_copy(update={"spans": tuple(spans), "source": "picture"})


def persist_alignment(
    conn: Any, episode_id: int, result: Alignment, segments: Sequence[TranscriptSegment]
) -> None:
    """Write transcript segments, `script_line.frames`, `scene.frames` / `in_cut` and
    `episode.timeline_source = 'picture'` for an ingested episode. Scenes and lines are matched to
    `result` by position (scene id order, line `seq` order within a scene)."""
    from sqlalchemy import delete, insert, select, update
    from sqlalchemy.dialects.postgresql import Range

    from nip.store.schema import episode, scene, script_line, transcript_segment

    def rng(f: tuple[int, int] | None) -> Any:
        return None if f is None else Range(f[0], f[1], bounds="[)")

    scene_ids = (
        conn.execute(
            select(scene.c.id).where(scene.c.episode_id == episode_id).order_by(scene.c.id)
        )
        .scalars()
        .all()
    )
    if len(scene_ids) != len(result.scenes):
        raise ValueError(
            f"episode {episode_id} has {len(scene_ids)} scenes, alignment {len(result.scenes)}"
        )
    line_ids: dict[LineKey, int] = {}
    for si, sid in enumerate(scene_ids):
        conn.execute(
            update(scene)
            .where(scene.c.id == sid)
            .values(frames=rng(result.scenes[si].frames), in_cut=result.scenes[si].in_cut)
        )
        rows = (
            conn.execute(
                select(script_line.c.id)
                .where(script_line.c.scene_id == sid)
                .order_by(script_line.c.seq)
            )
            .scalars()
            .all()
        )
        for ei, lid in enumerate(rows):
            line_ids[(si, ei)] = lid
            m = result.lines.get((si, ei))
            conn.execute(
                update(script_line)
                .where(script_line.c.id == lid)
                .values(frames=rng(m.frames if m else None))
            )
    conn.execute(delete(transcript_segment).where(transcript_segment.c.episode_id == episode_id))
    for s, key in zip(segments, segment_lines(result, segments), strict=True):
        conn.execute(
            insert(transcript_segment).values(
                **s.to_row(episode_id), aligned_line_id=line_ids.get(key) if key else None
            )
        )
    conn.execute(
        update(episode).where(episode.c.id == episode_id).values(timeline_source="picture")
    )


@app.command("align")
def align_command(
    script: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="fountain/fdx/pdf")],
    video: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    picture: Annotated[Path, typer.Option(help="picture.json from `nip timeline picture`")],
    transcript: Annotated[Path, typer.Option(help="transcript.json from `nip timeline asr`")],
    out_dir: Annotated[Path, typer.Option(help="alignment.json and timeline.json go here")],
    episode: Annotated[str, typer.Option(help="episode ref, e.g. S01E01")] = "EP1",
) -> None:
    """Place a script's dialogue lines and scenes on the picture axis."""
    fmt = script.suffix.lstrip(".").lower()
    parsed = parse(fmt, script.read_bytes())
    if parsed.errors or parsed.data is None:
        typer.echo(f"INPUT_REJECTED: {script}: {parsed.errors}", err=True)
        raise typer.Exit(1)
    sc: Script = parsed.data
    media, pic = probe(video), json.loads(picture.read_text(encoding="utf-8"))
    segs = [
        TranscriptSegment(
            tuple(s["frames"]), s["lang"], s["text"], tuple(TranscriptWord(**w) for w in s["words"])
        )
        for s in json.loads(transcript.read_text(encoding="utf-8"))
    ]
    shots = [tuple(x) for x in pic["shots"]]
    res = align_episode(sc, segs, shots, media.fps, media.duration_frames)
    tl = build_timeline(
        episode,
        sc,
        media,
        shots=shots,
        keyframes=[(k["shot"], k["n"], k["frame"]) for k in pic["keyframes"]],
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "timeline.json").write_text(
        with_picture_timing(tl, sc, res).model_dump_json(), encoding="utf-8"
    )
    (out_dir / "alignment.json").write_text(
        json.dumps(
            {
                "lines": {f"{si}.{ei}": [*m.frames, m.score] for (si, ei), m in res.lines.items()},
                "scenes": [{"frames": p.frames, "in_cut": p.in_cut} for p in res.scenes],
                "segment_lines": [
                    f"{k[0]}.{k[1]}" if k else None for k in segment_lines(res, segs)
                ],
            }
        ),
        encoding="utf-8",
    )
    n = sum(e.kind == "dialogue" for s in sc.scenes for e in s.elements)
    placed_scenes = sum(p.in_cut for p in res.scenes)
    typer.echo(
        f"{len(res.lines)}/{n} dialogue lines placed, {placed_scenes}/{len(res.scenes)} scenes"
        f" -> {out_dir}"
    )
