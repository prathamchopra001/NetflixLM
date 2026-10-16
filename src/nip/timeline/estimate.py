"""Script-estimate timeline (architecture.md › Script-estimate mode, D-007).

Scene lengths come from page length: each scene is laid out in standard screenplay format
(Courier 12 pt, 55 lines per page) and one page counts as one minute. Scenes are placed back to
back from frame 0 in script order. With a media probe the picture's frame rate and length are
used (scenes that start past the end of the picture get no frames); without one, 24 fps.
Subtitle cues are placed by exact ms -> frame conversion at the same frame rate.
"""

import textwrap
from collections.abc import Mapping, Sequence
from fractions import Fraction
from itertools import accumulate

from nip.contracts.flag import EvidenceKind
from nip.contracts.timeline import Span, Timeline
from nip.ingest.media import MediaInfo
from nip.ingest.script import Scene, Script
from nip.ingest.subtitles import SubtitleTrack
from nip.timecode import frame_to_smpte, ms_to_frame

LINES_PER_PAGE = 55
MS_PER_PAGE = 60_000  # one page ≈ one minute
NO_PICTURE_FPS = Fraction(24)
# Column widths in Courier 12 pt characters (10 per inch): action 6", dialogue 3.5",
# parenthetical 2.5". Headings and transitions use the action width.
_WIDTH = {"heading": 60, "action": 60, "transition": 60, "dialogue": 35, "parenthetical": 25}
_SPEECH = ("dialogue", "parenthetical")


def _wrapped(text: str, width: int) -> int:
    return sum(len(textwrap.wrap(p, width)) or 1 for p in text.split("\n"))


def scene_lines(scene: Scene) -> int:
    """Printed lines of `scene`: a blank line before each block, plus a character cue per speech."""
    n = 1 + _wrapped(scene.heading, _WIDTH["heading"])
    prev = None
    for e in scene.elements:
        speech = e.kind in _SPEECH
        same_speech = speech and prev is not None and prev.kind in _SPEECH
        if not (same_speech and prev is not None and prev.speaker == e.speaker):
            n += 2 if speech else 1  # blank line (+ character cue)
        n += _wrapped(f"({e.text})" if e.kind == "parenthetical" else e.text, _WIDTH[e.kind])
        prev = e
    return n


def scene_bounds(script: Script, fps: Fraction) -> list[int]:
    """Frame boundaries [0, end_1, ..., end_n]; scene i spans [b[i], b[i+1]).

    Boundaries come from cumulative line counts, so rounding never accumulates.
    """
    cum = accumulate((scene_lines(s) for s in script.scenes), initial=0)
    return [ms_to_frame(Fraction(lines * MS_PER_PAGE, LINES_PER_PAGE), fps) for lines in cum]


def build_timeline(
    episode: str,
    script: Script,
    media: MediaInfo | None = None,
    subtitles: Mapping[str, SubtitleTrack] | None = None,
    shots: Sequence[tuple[int, int]] = (),
    keyframes: Sequence[tuple[int, int, int]] = (),
) -> Timeline:
    """Timeline with estimated scene spans, plus shots, keyframes and subtitle cues (by language).

    `shots` are [in, out) frame ranges from shot detection; a shot's ref id is its index.
    `keyframes` are (shot index, n, frame) as written by `extract_keyframes` (ref `kf/{shot}.{n}`).
    """
    fps = media.fps if media else NO_PICTURE_FPS
    start, drop = (media.start_tc_frames, media.drop_frame) if media else (0, False)

    def timed(kind: EvidenceKind, ref: str, f: tuple[int, int], **kw: str) -> Span:
        tc_in, tc_out = (frame_to_smpte(x + start, fps, drop) for x in f)  # out is exclusive
        return Span(kind=kind, ref=ref, frames=f, tc_in=tc_in, tc_out=tc_out, **kw)

    timed_spans = [timed(EvidenceKind.SHOT, f"{episode}/shot/{i}", s) for i, s in enumerate(shots)]
    timed_spans += [
        timed(EvidenceKind.KEYFRAME, f"{episode}/kf/{i}.{n}", (f, f + 1)) for i, n, f in keyframes
    ]
    for lang, track in (subtitles or {}).items():
        for c in track.cues:
            a = ms_to_frame(c.start_ms, fps)
            f = (a, max(ms_to_frame(c.end_ms, fps), a + 1))  # a sub-frame cue keeps one frame
            ref = f"{episode}/{lang}/{c.idx}"
            timed_spans.append(timed(EvidenceKind.SUBTITLE_CUE, ref, f, lang=lang, text=c.text))

    bounds = scene_bounds(script, fps)
    end = (
        media.duration_frames
        if media
        else max([bounds[-1], *(s.frames[1] for s in timed_spans if s.frames)])
    )
    scenes = [
        Span(
            kind=EvidenceKind.SCENE,
            ref=f"{episode}/sc/{s.number}",
            frames=(a, min(b, end)) if a < end else None,
            text=s.heading,
            scene=f"{episode} · Sc {s.number} (script estimate)",
        )
        for s, a, b in zip(script.scenes, bounds, bounds[1:], strict=False)
    ]
    return Timeline(
        episode=episode,
        fps=(fps.numerator, fps.denominator),
        duration_frames=end,
        start_tc_frames=start,
        drop_frame=drop,
        spans=scenes + timed_spans,
    )
