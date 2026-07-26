from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import AuthenticatedUser, get_current_user, require_role
from app.db import get_db

router = APIRouter(prefix="/api/scouting", tags=["scouting"])


class ScoutingNoteCreate(BaseModel):
    player_id: int
    note: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)


@router.get("/notes")
def get_scouting_notes(
    player_id: int,
    _user: AuthenticatedUser = Depends(get_current_user),
    client=Depends(get_db),
):
    return client.table("scouting_notes").select(
        "id, player_id, author_id, note, rating, created_at"
    ).eq("player_id", player_id).order("created_at", desc=True).execute().data


@router.post("/notes")
def create_scouting_note(
    body: ScoutingNoteCreate,
    user: AuthenticatedUser = Depends(require_role("scout")),
    client=Depends(get_db),
):
    payload = {
        "player_id": body.player_id,
        "author_id": user.id,
        "note": body.note,
        "rating": body.rating,
    }
    result = client.table("scouting_notes").insert(payload).execute()
    return result.data[0] if result.data else payload
