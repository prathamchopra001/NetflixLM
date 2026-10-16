"""Timeline read model shared by checks and verification (architecture.md › Stage 2: Timeline).

Every timeline object is a `Span` addressed by its evidence ref (data-model.md › Evidence Refs).
Display fields (`tc_in`/`tc_out`, or `scene` for script estimates) are computed by the timeline
builder, so consumers never need timecode math.
"""

from typing import Literal

from pydantic import PrivateAttr

from nip.contracts._base import Contract, FrameRange
from nip.contracts.flag import EvidenceKind


class Span(Contract):
    kind: EvidenceKind
    ref: str
    frames: FrameRange | None = None  # None: not placed on the frame axis
    lang: str | None = None
    text: str = ""
    tc_in: str | None = None
    tc_out: str | None = None
    scene: str | None = None  # "S01E03 · Sc 12 (script estimate)" replaces tc_in/tc_out


class Timeline(Contract):
    episode: str
    fps: tuple[int, int]  # exact rational: (24000, 1001)
    duration_frames: int
    start_tc_frames: int = 0
    drop_frame: bool = False
    source: Literal["script_estimate", "picture"] = "script_estimate"
    spans: list[Span]  # scenes in script order, then shots, then cues per language

    _by_ref: dict[str, Span] = PrivateAttr(default_factory=dict)

    def model_post_init(self, _: object) -> None:
        self._by_ref = {s.ref: s for s in self.spans}
        if len(self._by_ref) != len(self.spans):
            dup = sorted({s.ref for s in self.spans if self._by_ref[s.ref] is not s})
            raise ValueError(f"duplicate timeline refs: {dup}")

    def resolve(self, ref: str) -> Span | None:
        return self._by_ref.get(ref)

    def of(self, kind: EvidenceKind, lang: str | None = None) -> list[Span]:
        return [s for s in self.spans if s.kind is kind and (lang is None or s.lang == lang)]
