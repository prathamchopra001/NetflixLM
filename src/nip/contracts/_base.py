from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_by_name=True, serialize_by_alias=True)


def _half_open(r: tuple[int, int | None]) -> tuple[int, int | None]:
    if r[1] is not None and r[1] <= r[0]:
        raise ValueError(f"range [{r[0]}, {r[1]}) is empty: upper must exceed lower")
    return r


# Half-open [in, out) ranges, as Postgres int8range / int4range. None upper = open-ended.
FrameRange = Annotated[tuple[int, int], AfterValidator(_half_open)]
OpenRange = Annotated[tuple[int, int | None], AfterValidator(_half_open)]
Confidence = Annotated[float, Field(ge=0, le=1)]
