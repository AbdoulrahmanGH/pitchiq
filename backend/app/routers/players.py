from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import AuthenticatedUser, get_current_user, require_role
from app.db import get_db
from app.services.fatigue import get_at_risk_players

router = APIRouter(prefix="/api/players", tags=["players"])

# Scoped to our own squad for now -- the v2 dataset also carries opponent
# rosters (needed to compute team-level metrics like PPDA), but the squad
# management views are about this team.
BARCELONA_TEAM_ID = 217

# StatsBomb's 25 granular position names, grouped into the four squad-depth
# buckets. Comes from the players table now -- there is no hardcoded
# player-id -> position dict to fall out of sync with anything.
BUCKET_ORDER = ("Goalkeeper", "Defender", "Midfielder", "Forward")

_POSITION_BUCKETS = {
    "Goalkeeper": "Goalkeeper",
    "Right Back": "Defender",
    "Right Center Back": "Defender",
    "Center Back": "Defender",
    "Left Center Back": "Defender",
    "Left Back": "Defender",
    "Right Wing Back": "Defender",
    "Left Wing Back": "Defender",
    "Right Defensive Midfield": "Midfielder",
    "Center Defensive Midfield": "Midfielder",
    "Left Defensive Midfield": "Midfielder",
    "Right Midfield": "Midfielder",
    "Right Center Midfield": "Midfielder",
    "Center Midfield": "Midfielder",
    "Left Center Midfield": "Midfielder",
    "Left Midfield": "Midfielder",
    "Right Attacking Midfield": "Midfielder",
    "Center Attacking Midfield": "Midfielder",
    "Left Attacking Midfield": "Midfielder",
    "Right Wing": "Forward",
    "Left Wing": "Forward",
    "Right Center Forward": "Forward",
    "Center Forward": "Forward",
    "Left Center Forward": "Forward",
    "Secondary Striker": "Forward",
}


def bucket_position(position):
    return _POSITION_BUCKETS.get(position)


def build_depth_response(players_rows):
    """players_rows: [{id, name, nickname, primary_position}, ...].

    total_players is defined as the sum of the four buckets, not an
    independently-counted "every player seen" total -- this is what makes
    the invariant hold structurally instead of by two dicts happening to
    agree. Players whose position can't be resolved are reported separately
    under `unresolved_players` rather than silently dropped or force-fit
    into a bucket.
    """
    depth = {b: [] for b in BUCKET_ORDER}
    unresolved = []
    for p in players_rows:
        entry = {"id": p["id"], "name": p["name"], "nickname": p.get("nickname")}
        bucket = bucket_position(p.get("primary_position"))
        if bucket:
            depth[bucket].append(entry)
        else:
            unresolved.append(entry)

    depth["total_players"] = sum(len(depth[b]) for b in BUCKET_ORDER)
    depth["unresolved_players"] = unresolved
    return depth


def aggregate_performance(stats_rows, players_by_id):
    """stats_rows: player_match_stats rows for the team.
    players_by_id: {player_id: {"name", "nickname"}}.
    """
    aggregated = {}
    for row in stats_rows:
        pid = row["player_id"]
        if pid not in aggregated:
            aggregated[pid] = {
                "player_id": pid,
                "total_minutes": 0,
                "total_goals": 0,
                "total_assists": 0,
                "total_shots": 0,
                "total_passes_attempted": 0,
                "total_passes_completed": 0,
                "total_key_passes": 0,
                "total_progressive_passes": 0,
                "total_progressive_carries": 0,
                "total_tackles": 0,
                "total_pressures": 0,
                "total_pressure_regains": 0,
                "xg": 0.0,
                "xa": 0.0,
                "matches_played": 0,
                "_dribbles_attempted": 0,
                "_dribbles_completed": 0,
            }
        p = aggregated[pid]
        p["total_minutes"] += row["minutes_played"] or 0
        p["total_goals"] += row["goals"] or 0
        p["total_assists"] += row["assists"] or 0
        p["total_shots"] += row["shots"] or 0
        p["total_passes_attempted"] += row["passes_attempted"] or 0
        p["total_passes_completed"] += row["passes_completed"] or 0
        p["total_key_passes"] += row["key_passes"] or 0
        p["total_progressive_passes"] += row["progressive_passes"] or 0
        p["total_progressive_carries"] += row["progressive_carries"] or 0
        p["total_tackles"] += row["tackles"] or 0
        p["total_pressures"] += row["pressures"] or 0
        p["total_pressure_regains"] += row["pressure_regains"] or 0
        p["xg"] += row["xg"] or 0.0
        p["xa"] += row["xa"] or 0.0
        p["matches_played"] += 1
        p["_dribbles_attempted"] += row["dribbles_attempted"] or 0
        p["_dribbles_completed"] += row["dribbles_completed"] or 0

    result = []
    for p in aggregated.values():
        attempted = p.pop("_dribbles_attempted")
        completed = p.pop("_dribbles_completed")
        p["dribble_success_rate"] = round((completed / attempted * 100), 1) if attempted > 0 else 0.0
        p["xg"] = round(p["xg"], 2)
        p["xa"] = round(p["xa"], 2)
        meta = players_by_id.get(p["player_id"], {})
        p["name"] = meta.get("name")
        p["nickname"] = meta.get("nickname")
        result.append(p)

    return result


def _players_by_id(client, player_ids):
    if not player_ids:
        return {}
    rows = client.table("players").select("id, name, nickname").in_(
        "id", list(player_ids)
    ).execute().data
    return {r["id"]: {"name": r["name"], "nickname": r["nickname"]} for r in rows}


@router.get("/performance")
def get_player_performance(_user: AuthenticatedUser = Depends(get_current_user)):
    supabase = get_db()

    stats_rows = supabase.table("player_match_stats").select(
        "player_id, minutes_played, passes_attempted, passes_completed, "
        "key_passes, progressive_passes, shots, goals, assists, xg, xa, "
        "dribbles_attempted, dribbles_completed, progressive_carries, tackles, "
        "pressures, pressure_regains"
    ).eq("team_id", BARCELONA_TEAM_ID).execute().data

    players_by_id = _players_by_id(supabase, {r["player_id"] for r in stats_rows})
    return aggregate_performance(stats_rows, players_by_id)


@router.get("/fatigue-risk")
def get_fatigue_risk(_user: AuthenticatedUser = Depends(get_current_user)):
    supabase = get_db()
    return get_at_risk_players(supabase, BARCELONA_TEAM_ID)


@router.get("/depth")
def get_squad_depth(_user: AuthenticatedUser = Depends(get_current_user)):
    supabase = get_db()

    pms_rows = supabase.table("player_match_stats").select("player_id").eq(
        "team_id", BARCELONA_TEAM_ID
    ).execute().data
    player_ids = sorted({r["player_id"] for r in pms_rows})

    players_rows = supabase.table("players").select(
        "id, name, nickname, primary_position"
    ).in_("id", player_ids).execute().data

    return build_depth_response(players_rows)


class PlayerStatusUpdate(BaseModel):
    player_id: int
    status: Literal["available", "doubtful", "unavailable"]
    note: Optional[str] = None


@router.get("/status")
def get_player_statuses(_user: AuthenticatedUser = Depends(get_current_user), client=Depends(get_db)):
    return client.table("player_status").select(
        "player_id, status, note, updated_by, updated_at"
    ).execute().data


@router.post("/status")
def set_player_status(
    body: PlayerStatusUpdate,
    user: AuthenticatedUser = Depends(require_role("coach")),
    client=Depends(get_db),
):
    payload = {
        "player_id": body.player_id,
        "status": body.status,
        "note": body.note,
        "updated_by": user.id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = client.table("player_status").upsert(payload).execute()
    return result.data[0] if result.data else payload
