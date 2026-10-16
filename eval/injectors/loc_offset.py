"""loc.offset: shift every cue of a subtitle file by a constant (skeleton example)."""

import random
from pathlib import Path

import pysubs2

from eval.injectors.base import Injector, Label, Target, register

FPS = 24000 / 1001


@register
class LocOffset(Injector):
    id = "loc.offset.v1"
    check = "loc.offset"

    def inject(self, src: Path, dst: Path, seed: int) -> list[Label]:
        frames = random.Random(seed).choice([-24, -12, 12, 24, 36])
        subs = pysubs2.load(str(src), encoding="utf-8")
        subs.shift(ms=round(frames * 1000 / FPS))
        dst.parent.mkdir(parents=True, exist_ok=True)
        subs.save(str(dst), encoding="utf-8")
        return [
            Label(
                label_id=f"{src.stem}-offset-{seed}",
                title=src.stem,
                check=self.check,
                target=Target(kind="subtitle_file", refs=[src.name]),
                description=f"All cues shifted by {frames:+d} frames at 23.976 fps",
                injector=self.id,
                seed=seed,
            )
        ]
