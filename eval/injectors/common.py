"""Shared pieces of the subtitle injectors: the title's real frame rate, an SRT editor that keeps
the file's own cue numbers, and the corpus sidecar location."""

import re
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from nip.ingest import parse_srt
from nip.ingest.common import decode_text
from nip.ingest.media import probe

SIDECAR = Path(__file__).resolve().parents[1] / "corpus" / "sidecar"
PICTURE_SUFFIXES = (".mkv", ".mov", ".mp4", ".m4v", ".mxf")


def picture_fps(src: Path) -> Fraction:
    """Probed frame rate of the picture that sits next to subtitle file `src` (corpus layout:
    data/corpus/<title>/<picture>, <lang>_<name>.srt). Never a constant: Sintel and Tears of Steel
    are 24/1, other titles 24000/1001."""
    for p in sorted(src.parent.iterdir()):
        if p.suffix.lower() in PICTURE_SUFFIXES:
            return Fraction(probe(p).fps)
    raise FileNotFoundError(f"no picture next to {src}: pass fps=")


FILM_EPISODE = "S01E01"  # a film is ingested as show=<title slug>, episode S01E01 (2.0 store)


def context(
    src: Path, episode: str | None, lang: str | None, title: str | None
) -> tuple[str, str, str]:
    """(episode, lang, title): episode defaults to S01E01 (the store only accepts SxxEyy), title
    to the title dir, lang to the `<lang>_` prefix."""
    return episode or FILM_EPISODE, lang or src.name.split("_", 1)[0], title or src.parent.name


def _fmt(ms: int) -> str:
    h, r = divmod(ms, 3_600_000)
    m, r = divmod(r, 60_000)
    return f"{h:02d}:{m:02d}:{r // 1000:02d},{r % 1000:03d}"


def _ms(h: str, m: str, s: str, ms: str) -> int:
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


_TIMING = re.compile(
    r"^(\d+):(\d\d):(\d\d)[,.](\d{3})(\s*-->\s*)(\d+):(\d\d):(\d\d)[,.](\d{3})(.*)$", re.DOTALL
)


@dataclass
class SrtCue:
    pre: list[str]  # the cue-number line and any blank lines before the timing line
    start_ms: int
    end_ms: int
    arrow: str
    tail: str  # anything after the end time (position tags)
    text: list[str] = field(default_factory=list)


class Srt:
    """SRT text edited in place: only the timing and text of touched cues change, so the file's
    own cue numbers, line endings and untouched cues survive (pysubs2 renumbers on save).

    `cues[i]` is cue `i + 1`, the numbering `nip.ingest.parse_srt` (and so the timeline) uses.
    """

    def __init__(self, data: bytes | str):
        text = decode_text(data)
        self.eol = "\r\n" if "\r\n" in text else "\n"
        self.cues: list[SrtCue] = []
        pre: list[str] = []
        lines = text.replace("\r\n", "\n").split("\n")
        i = 0
        while i < len(lines):
            m = _TIMING.match(lines[i])
            if not m:
                pre.append(lines[i])
                i += 1
                continue
            g = m.groups()
            cue = SrtCue(pre, _ms(*g[0:4]), _ms(*g[5:9]), g[4], g[9])
            pre = []
            i += 1
            while i < len(lines) and lines[i].strip():
                cue.text.append(lines[i])
                i += 1
            self.cues.append(cue)
        self.tail = pre
        parsed = parse_srt(text)
        if not parsed.ok or parsed.data is None or len(parsed.data.cues) != len(self.cues):
            raise ValueError(f"SRT does not parse cleanly: {parsed.errors or 'cue count differs'}")

    def render(self) -> str:
        out: list[str] = []
        for c in self.cues:
            out += [*c.pre, f"{_fmt(c.start_ms)}{c.arrow}{_fmt(c.end_ms)}{c.tail}", *c.text]
        return self.eol.join([*out, *self.tail])

    def write(self, dst: Path) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(self.render().encode("utf-8"))
