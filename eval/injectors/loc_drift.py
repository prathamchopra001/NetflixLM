"""loc.drift: rescale every cue time by a frame-rate confusion ratio relative to the picture's rate.

docs/evaluation.md names 25025/24000 (25 fps timing on a 23.976 picture) and 1001/1000 (SMPTE-24 vs
23.976 media time). Those ratios assume a 23.976 picture; the ratio is always
`confused rate / probed rate`, so a 24 fps film gets 25/24 and 1000/1001. The label is track-level
(R12), like loc.offset.
"""

import random
from fractions import Fraction
from pathlib import Path

from eval.injectors.base import Injector, Label, Target, register
from eval.injectors.common import Srt, context, picture_fps
from nip.contracts import refs

NTSC_FILM = Fraction(24000, 1001)


def confusions(fps: Fraction) -> list[tuple[Fraction, str]]:
    """(ratio, what went wrong) pairs that apply to a picture of rate `fps`."""
    out = [(Fraction(25) / fps, f"25 fps timing on a {fps} fps picture")]
    if fps == NTSC_FILM:
        out.append((Fraction(1001, 1000), "24 fps media time on a 23.976 fps picture"))
    elif fps == 24:
        out.append((Fraction(1000, 1001), "23.976 fps media time on a 24 fps picture"))
    return out


@register
class LocDrift(Injector):
    id = "loc.drift.v1"
    check = "loc.drift"

    def inject(
        self,
        src: Path,
        dst: Path,
        seed: int,
        *,
        episode: str | None = None,
        lang: str | None = None,
        title: str | None = None,
        fps: Fraction | None = None,
    ) -> list[Label]:
        episode, lang, title = context(src, episode, lang, title)
        fps = fps or picture_fps(src)
        ratio, why = random.Random(f"{self.id}/{seed}").choice(confusions(fps))
        srt = Srt(src.read_bytes())
        last = srt.cues[-1].end_ms
        for c in srt.cues:
            c.start_ms = round(c.start_ms * ratio)
            c.end_ms = round(c.end_ms * ratio)
        srt.write(dst)
        return [
            Label(
                label_id=f"{title}-{lang}-drift-s{seed}",
                title=title,
                episode=episode,
                check=self.check,
                lang=lang,
                target=Target(
                    kind="subtitle_track",
                    refs=[refs.cue(episode, lang, i) for i in range(1, len(srt.cues) + 1)],
                ),
                description=(
                    f"all cue times rescaled by {ratio} ({why}); the last cue ends "
                    f"{srt.cues[-1].end_ms - last:+d} ms off"
                ),
                injector=self.id,
                seed=seed,
            )
        ]
