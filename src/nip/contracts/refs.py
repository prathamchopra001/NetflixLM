"""Evidence refs (data-model.md › Evidence Refs): the one place their formats are built and parsed.

Every timeline builder, check, injector and fingerprint goes through here, so a format change is
one edit. Builders exist for the kinds the code builds today; `parse` reads every kind in the table.
"""

from typing import NamedTuple

from nip.contracts.flag import EvidenceKind

_IN_EPISODE = {
    "sc": EvidenceKind.SCENE,
    "line": EvidenceKind.SCRIPT_LINE,
    "shot": EvidenceKind.SHOT,
    "kf": EvidenceKind.KEYFRAME,
    "asr": EvidenceKind.TRANSCRIPT_SEGMENT,
}
_GLOBAL = {"fact": EvidenceKind.FACT, "clr": EvidenceKind.CLEARANCE_ITEM}


def scene(ep: str, no: str) -> str:
    return f"{ep}/sc/{no}"


def shot(ep: str, i: int) -> str:
    return f"{ep}/shot/{i}"


def keyframe(ep: str, shot: int, n: int) -> str:
    return f"{ep}/kf/{shot}.{n}"


def cue(ep: str, lang: str, idx: int) -> str:
    return f"{ep}/{lang}/{idx}"


OCC = "occ-"  # id prefix of an occurrence ref


def occurrence(key: str) -> str:
    """`clr/occ-{key}`: one on-screen clearance occurrence of an episode (a frame range). It is a
    clearance-item ref by kind (the contract has no occurrence kind) with an `occ-` id, so it
    never collides with a numeric `clr/{id}`. `key` is the hash the clearance stage derives from
    the episode, check, item and first keyframe; `load_timeline` rebuilds the span from the
    stored detections under the same ref."""
    return f"clr/{OCC}{key}"


def is_occurrence(ref: str) -> bool:
    return ref.startswith(f"clr/{OCC}")


class Ref(NamedTuple):
    kind: EvidenceKind
    episode: str | None  # None for show-wide objects (fact, clearance item)
    id: str  # "12", "118.0", "212"
    lang: str | None = None  # subtitle cues only


def parse(ref: str) -> Ref:
    """The parts of `ref`; ValueError when it is not an evidence ref."""
    parts = ref.split("/")
    if len(parts) == 2 and parts[0] in _GLOBAL and parts[1]:
        return Ref(_GLOBAL[parts[0]], None, parts[1])
    if len(parts) == 3 and all(parts):
        ep, mid, id_ = parts
        if mid in _IN_EPISODE:
            return Ref(_IN_EPISODE[mid], ep, id_)
        if id_.isdigit():
            return Ref(EvidenceKind.SUBTITLE_CUE, ep, id_, lang=mid)
    raise ValueError(f"not an evidence ref: {ref!r}")
