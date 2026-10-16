"""Injector framework: deterministic error injection with ground-truth labels."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Self

from pydantic import BaseModel, model_validator

from nip.contracts import refs


class Target(BaseModel):
    kind: str  # subtitle_cue | shot | script_line ...
    refs: list[str] = []
    frames: tuple[int, int] | None = None  # script-level labels use refs only


class Label(BaseModel):
    """One planted error; one JSON line of eval/labels/<set>/<title>.jsonl.

    The one label model: injectors write it and `eval.metrics.load_labels` reads it, so a label
    that could never match a flag (no episode, no target, a ref outside its episode) is refused.
    """

    label_id: str
    title: str
    episode: str
    check: str
    lang: str | None = None
    target: Target
    description: str
    injector: str  # "<name>.v<N>"
    seed: int
    reviewed: bool = False

    @model_validator(mode="after")
    def _matchable(self) -> Self:
        if not (self.target.refs or self.target.frames):
            raise ValueError("a label needs target refs or frames")
        for r in self.target.refs:
            try:
                ep = refs.parse(r).episode
            except ValueError as e:
                raise ValueError(f"target ref {r!r} is not an evidence ref") from e
            if ep != self.episode:
                raise ValueError(f"target ref {r!r} is outside episode {self.episode!r}")
        return self


class Injector(ABC):
    """Takes an original title and a seed; writes a modified copy and returns its labels.

    Must be deterministic for a given (src, seed).
    """

    id: str  # e.g. "loc.offset.v1"
    check: str  # check ID the injected errors belong to, e.g. "loc.offset"

    @abstractmethod
    def inject(self, src: Path, dst: Path, seed: int) -> list[Label]: ...


REGISTRY: dict[str, Injector] = {}


def register(cls: type[Injector]) -> type[Injector]:
    """Class decorator: instantiate and add to REGISTRY under cls.id."""
    if cls.id in REGISTRY:
        raise ValueError(f"duplicate injector id {cls.id}")
    REGISTRY[cls.id] = cls()
    return cls


def get(injector_id: str) -> Injector:
    return REGISTRY[injector_id]


def write_labels(labels: list[Label], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(lb.model_dump(mode="json")) + "\n" for lb in labels), "utf-8"
    )
