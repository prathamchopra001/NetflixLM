from fastapi import APIRouter

from models import FlagDispositionUpdate

router = APIRouter(tags=["flags"])


@router.get("/flags")
def list_flags():
    return {"flags": []}


@router.put("/flags/{flag_id}/disposition")
def update_flag_disposition(flag_id: str, update: FlagDispositionUpdate):
    return {"flag_id": flag_id, "disposition": update.disposition}
