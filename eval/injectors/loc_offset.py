"""loc.offset: shift every cue of a subtitle file by a constant number of frames.

The frame rate is the picture's (probed, never assumed): "+12 frames" is 500 ms at 24 fps and
500.5 ms at 24000/1001. The label is track-level (R12): it lists every cue ref of the track, so a
flag that claims the first and/or the last cue matches it.
"""

import random
from fractions import Fraction
from pathlib import Path

from eval.injectors.base import Injector, Label, Target, register
from eval.injectors.common import Srt, context, picture_fps
from nip.contracts import refs
from nip.timecode import frame_to_ms

SHIFTS = (-24, -12, 12, 24, 36)  # frames


@register
class LocOffset(Injector):
    id = "loc.offset.v2"
    check = "loc.offset"

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
        """`episode` defaults to the corpus title dir, `lang` to the `<lang>_` file prefix, `fps`
        to the probe of the picture next to `src`."""
        episode, lang, title = context(src, episode, lang, title)
        fps = fps or picture_fps(src)
        srt = Srt(src.read_bytes())
        first = min(c.start_ms for c in srt.cues)
        ok = [f for f in SHIFTS if f > 0 or frame_to_ms(-f, fps) <= first]  # no negative times
        frames = random.Random(f"{self.id}/{seed}").choice(ok)
        ms = frame_to_ms(abs(frames), fps) * (1 if frames > 0 else -1)
        for c in srt.cues:
            c.start_ms += ms
            c.end_ms += ms
        srt.write(dst)
        return [
            Label(
                label_id=f"{episode}-{lang}-offset-s{seed}",
                title=title,
                episode=episode,
                check=self.check,
                lang=lang,
                target=Target(
                    kind="subtitle_track",
                    refs=[refs.cue(episode, lang, i) for i in range(1, len(srt.cues) + 1)],
                ),
                description=f"all cues shifted by {frames:+d} frames ({ms:+d} ms at {fps} fps)",
                injector=self.id,
                seed=seed,
            )
        ]
