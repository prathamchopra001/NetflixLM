"""loc.readability: push k cues past the language rule pack (evaluation.md > Injectors).

Kinds: characters per line, lines per cue, reading speed, min/max duration, minimum gap. Only
"isolated" cues are edited (both neighbours at least MARGIN_MS away, no two picks adjacent), so
an edit never creates a violation on a cue without a label. Labels cite the cue ref (frame-rate
free; cue numbers never change because no cue is added or removed).
"""

import random
from pathlib import Path

import pysubs2

from eval.injectors.base import Injector, Label, Target, register
from nip.agents.localization.readability import rule_pack

MARGIN_MS = 600  # > 1/2 s (gap-closing window) + a frame at any common rate
KINDS = ("chars_per_line", "lines", "reading_speed", "min_duration", "max_duration", "gap")


def _one_line(text: str, longer_than: int) -> str:
    line = text.replace("\n", " ")
    while len(line) <= longer_than:
        line += " " + text.replace("\n", " ")
    return line


@register
class LocReadability(Injector):
    id = "loc.readability.v1"
    check = "loc.readability"

    def inject(
        self,
        src: Path,
        dst: Path,
        seed: int,
        *,
        episode: str | None = None,
        lang: str | None = None,
        k: int = 6,
    ) -> list[Label]:
        """`episode` defaults to the corpus title dir, `lang` to the `<lang>_` file prefix."""
        episode = episode or src.parent.name
        lang = lang or src.name.split("_", 1)[0]
        r = rule_pack(lang)["readability"]
        cps = float(r["reading_speed_cps"]["adult"])
        max_ms = round(float(r["max_duration_s"]) * 1000)
        subs = pysubs2.load(str(src), encoding="utf-8", format_=src.suffix[1:].lower())
        ev = list(subs)

        def gap_before(i: int) -> float:
            return ev[i].start - ev[i - 1].end if i > 0 else float("inf")

        def gap_after(i: int) -> float:
            return ev[i + 1].start - ev[i].end if i + 1 < len(ev) else float("inf")

        def eligible(i: int, kind: str) -> bool:
            e = ev[i]
            if kind == "reading_speed":  # 0.9 s at 1.3x the limit must be reachable
                return len(e.plaintext.replace("\n", "")) >= 1.3 * cps * 0.9
            if kind == "max_duration":
                return gap_after(i) - (max_ms + 1000 - e.duration) >= MARGIN_MS
            if kind == "gap":
                return i > 0
            return True

        rng = random.Random(seed)
        isolated = [
            i
            for i, e in enumerate(ev)
            if min(gap_before(i), gap_after(i)) >= MARGIN_MS and 1000 <= e.duration <= 6000
        ]
        rng.shuffle(isolated)
        picks: list[tuple[int, str]] = []
        kinds = list(KINDS)
        rng.shuffle(kinds)
        for i in isolated:
            if len(picks) == k:
                break
            if any(abs(i - j) < 2 for j, _ in picks):
                continue
            kind = next((kd for kd in kinds if eligible(i, kd)), None)
            if kind is not None:
                kinds.remove(kind)
                kinds.append(kind)  # rotate: every kind before any repeats
                picks.append((i, kind))

        labels = []
        for i, kind in sorted(picks):
            e = ev[i]
            if kind == "chars_per_line":
                e.text = _one_line(e.plaintext, r["max_chars_per_line"] + 2)
            elif kind == "lines":
                words = e.plaintext.split()
                n = r["max_lines"] + 1
                words = (words * n)[: max(len(words), n)]
                parts = [words[j * len(words) // n : (j + 1) * len(words) // n] for j in range(n)]
                e.text = r"\N".join(" ".join(p) for p in parts)
            elif kind == "reading_speed":
                chars = len(e.plaintext.replace("\n", ""))
                e.end = e.start + int(min(e.duration, max(900, chars / (1.5 * cps) * 1000)))
            elif kind == "min_duration":
                e.end = e.start + 500
            elif kind == "max_duration":
                e.end = e.start + max_ms + 1000
            else:  # gap: move the whole cue to 20 ms (< 1 frame) after the previous one
                e.shift(ms=ev[i - 1].end + 20 - e.start)
            labels.append(
                Label(
                    label_id=f"{episode}-{lang}-readability-s{seed}-{i + 1}",
                    title=episode,
                    episode=episode,
                    check=self.check,
                    lang=lang,
                    target=Target(kind="subtitle_cue", refs=[f"{episode}/{lang}/{i + 1}"]),
                    description=f"cue {i + 1}: {kind}",
                    injector=self.id,
                    seed=seed,
                )
            )
        dst.parent.mkdir(parents=True, exist_ok=True)
        subs.save(str(dst), encoding="utf-8")
        return labels
