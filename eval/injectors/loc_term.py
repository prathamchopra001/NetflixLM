"""loc.term: replace the approved rendering of a glossary term in k cues with a variant.

Reads the title's sidecar `glossary.csv` (columns term, lang, approved_rendering, notes). A variant
is listed in the notes as `variants: A | B` (a translation or transliteration a translator might
plausibly use); without one the rendering is misspelled by swapping two inner letters. Every
occurrence of the term in the picked cue is replaced, so the approved rendering is gone from it.
"""

import random
import re
from collections.abc import Callable, Collection
from fractions import Fraction
from pathlib import Path

from eval.injectors.base import Injector, Label, Target, register
from eval.injectors.common import SIDECAR, Srt, context, picture_fps
from nip.contracts import refs
from nip.ingest import GlossaryEntry, parse_glossary
from nip.timecode import ms_to_frame


def variants(e: GlossaryEntry) -> list[tuple[str, str]]:
    """(variant, kind) alternatives for an entry: listed in its notes, else a misspelling."""
    m = re.search(r"variants:\s*(.+)", e.notes)
    if m and (listed := [v.strip() for v in m.group(1).split("|") if v.strip()]):
        return [(v, "variant") for v in listed]
    words = e.approved_rendering.split()
    w = max(words, key=len)
    i = next((j for j in range(1, len(w) - 2) if w[j] != w[j + 1]), None)
    if i is None:
        return []
    swapped = w[:i] + w[i + 1] + w[i] + w[i + 2 :]
    return [(e.approved_rendering.replace(w, swapped, 1), "misspelling")]


def _const(v: str) -> Callable[[re.Match[str]], str]:
    return lambda _m: v


def _pattern(term: str) -> re.Pattern[str]:
    return re.compile(r"(?<!\w)" + r"\s+".join(map(re.escape, term.split())) + r"(?!\w)")


@register
class LocTerm(Injector):
    id = "loc.term.v1"
    check = "loc.term"

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
        glossary: Path | None = None,
        k: int = 4,
        avoid: Collection[int] = (),
    ) -> list[Label]:
        """`glossary` defaults to eval/corpus/sidecar/<title dir>/glossary.csv; `avoid` holds
        1-based cue numbers earlier injectors already edited."""
        episode, lang, title = context(src, episode, lang, title)
        fps = fps or picture_fps(src)
        glossary = glossary or SIDECAR / src.parent.name / "glossary.csv"
        parsed = parse_glossary(glossary.read_bytes())
        if not parsed.ok or parsed.data is None:
            raise ValueError(f"{glossary}: {parsed.errors}")
        entries = [e for e in parsed.data if e.lang.split("-")[0] == lang.split("-")[0]]
        srt = Srt(src.read_bytes())
        rng = random.Random(f"{self.id}/{seed}")
        found: list[list[tuple[int, GlossaryEntry]]] = []
        for e in entries:
            pat = _pattern(e.approved_rendering)
            hits = [
                (i, e)
                for i, c in enumerate(srt.cues)
                if i + 1 not in avoid and variants(e) and pat.search("\n".join(c.text))
            ]
            rng.shuffle(hits)
            found.append(hits)
        rng.shuffle(found)
        picks: dict[int, GlossaryEntry] = {}
        while len(picks) < k and any(found):  # round-robin over terms: every term before a repeat
            for hits in found:
                while hits and len(picks) < k:
                    i, e = hits.pop()
                    if i not in picks:
                        picks[i] = e
                        break
        labels = []
        for i, e in sorted(picks.items()):
            variant, kind = rng.choice(variants(e))
            cue = srt.cues[i]
            cue.text = (
                _pattern(e.approved_rendering).sub(_const(variant), "\n".join(cue.text)).split("\n")
            )
            a = ms_to_frame(cue.start_ms, fps)
            labels.append(
                Label(
                    label_id=f"{title}-{lang}-term-s{seed}-{i + 1}",
                    title=title,
                    episode=episode,
                    check=self.check,
                    lang=lang,
                    target=Target(
                        kind="subtitle_cue",
                        refs=[refs.cue(episode, lang, i + 1)],
                        frames=(a, max(ms_to_frame(cue.end_ms, fps), a + 1)),
                    ),
                    description=(
                        f"cue {i + 1}: '{e.approved_rendering}' ({e.term}) -> '{variant}' ({kind})"
                    ),
                    injector=self.id,
                    seed=seed,
                )
            )
        srt.write(dst)
        return labels
