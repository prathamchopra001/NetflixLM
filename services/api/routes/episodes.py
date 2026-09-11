from fastapi import APIRouter

from models import EpisodeCreateRequest, EpisodeResponse

router = APIRouter(tags=["episodes"])


@router.post("/episodes")
def create_episode(request: EpisodeCreateRequest):
    return {
        "pipeline_run_id": "run-123",
        "status": "queued",
        "estimated_duration_minutes": 10,
    }


@router.get("/episodes/{show_id}/{season}/{episode}")
def get_episode(show_id: str, season: int, episode: int):
    return EpisodeResponse(
        show_id=show_id, season=season, episode=episode, status="completed"
    )


@router.get("/episodes/{show_id}/{season}/{episode}/versions")
def get_episode_versions(show_id: str, season: int, episode: int):
    return {"versions": []}


@router.get("/episodes/{show_id}/{season}/{episode}/diff")
def get_episode_diff(show_id: str, season: int, episode: int):
    return {"diff": []}
