from fastapi import APIRouter

from models import RecapPublishRequest

router = APIRouter(tags=["recaps"])


@router.get("/recaps/{show_id}/{season}/{episode}")
def get_recap(show_id: str, season: int, episode: int):
    return {"show_id": show_id, "season": season, "episode": episode, "recap": ""}


@router.put("/recaps/{recap_id}/publish")
def publish_recap(recap_id: str, request: RecapPublishRequest):
    return {"recap_id": recap_id, "published": request.publish}
