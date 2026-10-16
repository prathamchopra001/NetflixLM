"""loc.shot_change: move cue in/out points to 1-11 frames from a shot change.

`cuts` are the first frames of shots 1.. (frames, from the cached picture analysis). A cue is only
edited when nothing else about it changes meaning: both neighbours stay at least MARGIN_MS away (so
no gap-closing or min-gap finding appears), the duration stays within 0.8-1.25x of the original
(reading speed, min/max duration stay clean), and the other end is not itself near a cut. Labels
carry the cue ref and the output cue's frame range.
"""

import bisect
import random
from collections.abc import Collection, Sequence
from fractions import Fraction
from pathlib import Path

from eval.injectors.base import Injector, Label, Target, register
from eval.injectors.common import Srt, context, picture_fps
from nip.contracts import refs
from nip.timecode import frame_to_ms, ms_to_frame

MARGIN_MS = 600
NEAR = 11  # frames: "within 1-11 frames of a shot change"
REACH = 36  # frames: only a cut this close to the cue edge is used


def _dist(cuts: Sequence[int], f: int) -> tuple[int, int]:
    """(cut, |f - cut|) of the cut nearest to frame `f`."""
    i = bisect.bisect_left(cuts, f)
    return min(((c, abs(f - c)) for c in cuts[max(i - 1, 0) : i + 1]), key=lambda t: t[1])


@register
class LocShotChange(Injector):
    id = "loc.shot_change.v1"
    check = "loc.shot_change"

    def inject(
        self,
        src: Path,
        dst: Path,
        seed: int,
        *,
        cuts: Sequence[int] = (),
        episode: str | None = None,
        lang: str | None = None,
        title: str | None = None,
        fps: Fraction | None = None,
        k: int = 3,
        avoid: Collection[int] = (),
    ) -> list[Label]:
        """`avoid`: 1-based cue numbers earlier injectors already edited."""
        episode, lang, title = context(src, episode, lang, title)
        fps = fps or picture_fps(src)
        cuts = sorted(cuts)
        srt = Srt(src.read_bytes())
        cues = srt.cues
        rng = random.Random(f"{self.id}/{seed}")

        def frames(i: int) -> tuple[int, int]:
            a = ms_to_frame(cues[i].start_ms, fps)
            return a, max(ms_to_frame(cues[i].end_ms, fps), a + 1)

        def gap(i: int, j: int) -> float:  # time between cue i's end and cue j's start
            ok = 0 <= i < len(cues) and 0 <= j < len(cues)
            return cues[j].start_ms - cues[i].end_ms if ok else float("inf")

        order = list(range(len(cues)))
        rng.shuffle(order)
        picks: list[int] = []
        labels = []
        for i in order:
            if len(picks) == k:
                break
            c = cues[i]
            dur = c.end_ms - c.start_ms
            if (
                i + 1 in avoid
                or any(abs(i - j) < 2 for j in picks)
                or min(gap(i - 1, i), gap(i, i + 1)) < MARGIN_MS
                or not 1000 <= dur <= 6000
            ):
                continue
            a, b = frames(i)
            sides = ["in", "out"]
            rng.shuffle(sides)
            for side in sides:
                edge, other = (a, b) if side == "in" else (b, a)
                cut, d = _dist(cuts, edge)
                if d <= NEAR or d > REACH or _dist(cuts, other)[1] <= NEAR:
                    continue  # already near a cut (a native finding), too far, or other end near
                new = cut + rng.randint(1, NEAR) * rng.choice((-1, 1))
                s, e = (new, b) if side == "in" else (a, new)
                if e <= s or s < 0:
                    continue
                s_ms, e_ms = frame_to_ms(s, fps), frame_to_ms(e, fps)
                new_dur = e_ms - s_ms
                if not (0.8 * dur <= new_dur <= 1.25 * dur and new_dur >= 1000):
                    continue
                if (i > 0 and s_ms - cues[i - 1].end_ms < MARGIN_MS) or (
                    i + 1 < len(cues) and cues[i + 1].start_ms - e_ms < MARGIN_MS
                ):
                    continue
                c.start_ms, c.end_ms = s_ms, e_ms
                picks.append(i)
                labels.append(
                    Label(
                        label_id=f"{episode}-{lang}-shot-change-s{seed}-{i + 1}",
                        title=title,
                        episode=episode,
                        check=self.check,
                        lang=lang,
                        target=Target(
                            kind="subtitle_cue",
                            refs=[refs.cue(episode, lang, i + 1)],
                            frames=frames(i),
                        ),
                        description=(
                            f"cue {i + 1}: {side}-point {abs(new - cut)} frames "
                            f"{'after' if new > cut else 'before'} the cut at frame {cut}"
                        ),
                        injector=self.id,
                        seed=seed,
                    )
                )
                break
        srt.write(dst)
        return sorted(labels, key=lambda lb: lb.target.frames or (0, 0))
