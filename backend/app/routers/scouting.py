from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import AuthenticatedUser, get_current_user, require_role
from app.db import get_db

router = APIRouter(prefix="/api/scouting", tags=["scouting"])


class ScoutingNoteCreate(BaseModel):
    player_id: int
    note: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)


def build_notes_response(notes, players_by_id, teams_by_id):
    """notes: scouting_notes rows. players_by_id: {player_id: {"name",
    "nickname", "team_id"}}. teams_by_id: {team_id: name}.

    Attaches player_name/player_nickname/team_name to each note -- a note
    only carries player_id, and the "My Scouting Notes" view (all of a
    scout's notes across every player) has no other context to show which
    player/team a row is about.
    """
    result = []
    for n in notes:
        meta = players_by_id.get(n["player_id"], {})
        result.append({
            **n,
            "player_name": meta.get("name"),
            "player_nickname": meta.get("nickname"),
            "team_name": teams_by_id.get(meta.get("team_id")),
        })
    return result


def fetch_notes_data(client, player_id=None, author_id=None):
    query = client.table("scouting_notes").select(
        "id, player_id, author_id, note, rating, created_at"
    )
    # No player_id means "my notes" -- every note this caller has authored,
    # across all players, for the Scout's "My Scouting Notes" view.
    query = query.eq("player_id", player_id) if player_id is not None else query.eq("author_id", author_id)
    notes = query.order("created_at", desc=True).execute().data

    player_ids = list({n["player_id"] for n in notes})
    if not player_ids:
        return notes

    players_rows = client.table("players").select("id, name, nickname").in_(
        "id", player_ids
    ).execute().data
    pms_rows = client.table("player_match_stats").select("player_id, team_id").in_(
        "player_id", player_ids
    ).execute().data
    team_id_by_player = {}
    for r in pms_rows:
        team_id_by_player.setdefault(r["player_id"], r["team_id"])
    players_by_id = {
        p["id"]: {"name": p["name"], "nickname": p["nickname"], "team_id": team_id_by_player.get(p["id"])}
        for p in players_rows
    }

    team_ids = list({v["team_id"] for v in players_by_id.values() if v["team_id"] is not None})
    teams_rows = client.table("teams").select("id, name").in_("id", team_ids).execute().data if team_ids else []
    teams_by_id = {t["id"]: t["name"] for t in teams_rows}

    return build_notes_response(notes, players_by_id, teams_by_id)


@router.get("/notes")
def get_scouting_notes(
    player_id: Optional[int] = None,
    user: AuthenticatedUser = Depends(get_current_user),
    client=Depends(get_db),
):
    return fetch_notes_data(client, player_id=player_id, author_id=user.id)


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
