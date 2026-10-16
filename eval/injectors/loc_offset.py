"""loc.offset: shift every cue of a subtitle file by a constant (skeleton example)."""

import random
from pathlib import Path

import pysubs2

from eval.injectors.base import Injector, Label, Target, register
from nip.contracts import refs

FPS = 24000 / 1001  # ponytail: assumes 23.976; the title's real rate comes with 2.9A (R12)


@register
class LocOffset(Injector):
    id = "loc.offset.v1"
    check = "loc.offset"

    def inject(
        self,
        src: Path,
        dst: Path,
        seed: int,
        *,
        episode: str | None = None,
        lang: str | None = None,
    ) -> list[Label]:
        """`episode` defaults to the corpus title dir, `lang` to the `<lang>_` file prefix."""
        episode = episode or src.parent.name
        lang = lang or src.name.split("_", 1)[0]
        frames = random.Random(seed).choice([-24, -12, 12, 24, 36])
        subs = pysubs2.load(str(src), encoding="utf-8")
        subs.shift(ms=round(frames * 1000 / FPS))
        dst.parent.mkdir(parents=True, exist_ok=True)
        subs.save(str(dst), encoding="utf-8")
        return [
            Label(
                label_id=f"{src.stem}-offset-{seed}",
                title=src.stem,
                episode=episode,
                check=self.check,
                lang=lang,
                target=Target(
                    kind="subtitle_file",
                    refs=[refs.cue(episode, lang, i) for i in range(1, len(subs) + 1)],
                ),
                description=f"All cues shifted by {frames:+d} frames at 23.976 fps",
                injector=self.id,
                seed=seed,
            )
        ]
