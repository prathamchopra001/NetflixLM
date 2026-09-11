from pydantic import BaseModel


class EpisodeCreateRequest(BaseModel):
    show_id: str
    season: int
    episode: int


class EpisodeResponse(BaseModel):
    show_id: str
    season: int
    episode: int
    status: str


class FlagDispositionUpdate(BaseModel):
    disposition: str
    notes: str | None = None


class RecapPublishRequest(BaseModel):
    publish: bool
    publish_time: str | None = None


class KGCorrectionRequest(BaseModel):
    entity_id: str
    correction: str
