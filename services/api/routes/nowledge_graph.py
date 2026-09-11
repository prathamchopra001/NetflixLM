from fastapi import APIRouter

from models import KGCorrectionRequest

router = APIRouter(tags=["knowledge_graph"])


@router.get("/kg/{show_id}/entities")
def get_kg_entities(show_id: str):
    return {"show_id": showbtn_id, "entities": []}


@router.get("/kg/{show_id}/constraints/violations")
def get_kg_constraint_violations(show_id: str):
    return {"show_id": show_id, "violations": []}


@router.post("/kg/{show_id}/corrections")
def create_kg_correction(show_id: str, request: KGCorrectionRequest):
    return {"show_id": show_id, "entity_id": request.entity_id, "status": "accepted"}
