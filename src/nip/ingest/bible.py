"""`bible.yaml` reader (docs/data-model.md, Show bible); unknown keys are warnings."""

from collections.abc import Iterator
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from nip.ingest.common import Issue, Parsed, decode_text, fail

EpisodeRef = Annotated[str, StringConstraints(pattern=r"^S\d+E\d+$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="allow")  # unknown keys are reported as warnings


class Character(_Model):
    id: str
    name: str
    aliases: list[str] = []
    gender: str | None = None
    pronouns: dict[str, str] = {}
    identity_hidden_until: EpisodeRef | None = None


class RelationshipStep(_Model):
    from_: EpisodeRef = Field(alias="from")
    kind: str
    register_: dict[str, str] = Field({}, alias="register")


class Relationship(_Model):
    between: Annotated[list[str], Field(min_length=2, max_length=2)]
    timeline: list[RelationshipStep] = []


class Secret(_Model):
    id: str
    description: str
    revealed_on_screen: EpisodeRef | None = None


class Fictional(_Model):
    brands: list[str] = []
    orgs: list[str] = []
    places: list[str] = []


class StoryOverride(_Model):
    scene: str
    markers: list[str] = []
    story_day: int | None = None


class Bible(_Model):
    show: str
    characters: list[Character] = []
    relationships: list[Relationship] = []
    secrets: list[Secret] = []
    fictional: Fictional = Fictional()
    story_overrides: list[StoryOverride] = []


def _extras(m: Any, path: str = "") -> Iterator[str]:
    if isinstance(m, BaseModel):
        for k in m.model_extra or {}:
            yield f"{path}{k}"
        for k in type(m).model_fields:
            yield from _extras(getattr(m, k), f"{path}{k}.")
    elif isinstance(m, list):
        for i, x in enumerate(m):
            yield from _extras(x, f"{path[:-1]}[{i}].")


def _dupes(ids: list[str]) -> set[str]:
    return {i for i in ids if ids.count(i) > 1}


def parse_bible(data: bytes | str) -> Parsed[Bible]:
    try:
        raw = yaml.safe_load(decode_text(data))
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        return fail(f"Invalid YAML: {getattr(e, 'problem', e)}", mark.line + 1 if mark else None)
    except ValueError as e:
        return fail(str(e))
    if not isinstance(raw, dict):
        return fail("bible.yaml must be a mapping at the top level", 1)
    try:
        bible = Bible.model_validate(raw)
    except ValidationError as e:
        return Parsed(
            errors=[
                Issue(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}") for err in e.errors()
            ]
        )
    p = Parsed(bible, warnings=[f"Unknown key '{k}'" for k in _extras(bible)])
    ids = [c.id for c in bible.characters]
    p.errors += [Issue(f"Duplicate character id '{i}'") for i in sorted(_dupes(ids))]
    p.errors += [
        Issue(f"Duplicate secret id '{i}'") for i in sorted(_dupes([s.id for s in bible.secrets]))
    ]
    for r in bible.relationships:
        p.errors += [
            Issue(f"Relationship references unknown character '{c}'")
            for c in r.between
            if c not in ids
        ]
    return p
