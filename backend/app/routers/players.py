from fastapi import APIRouter
from app.config import SUPABASE_URL, SUPABASE_KEY
from supabase import create_client

router = APIRouter(prefix="/api/players", tags=["players"])

def get_db():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

PLAYER_POSITIONS = {
    "player-001": "Forward",    "player-002": "Forward",    "player-003": "Defender",
    "player-004": "Midfielder", "player-005": "Goalkeeper", "player-006": "Goalkeeper",
    "player-007": "Defender",   "player-008": "Defender",   "player-009": "Defender",
    "player-010": "Defender",   "player-011": "Defender",   "player-012": "Midfielder",
    "player-013": "Midfielder", "player-014": "Midfielder", "player-015": "Midfielder",
    "player-016": "Midfielder", "player-017": "Forward",    "player-018": "Forward",
    "player-019": "Forward",    "player-020": "Forward",    "player-021": "Forward",
    "player-022": "Midfielder", "player-027": "Defender",
    "player-028": "Defender",   "player-029": "Defender",   "player-030": "Defender",
    "player-031": "Midfielder", "player-032": "Midfielder", "player-033": "Midfielder",
    "player-034": "Midfielder", "player-035": "Forward",    "player-036": "Forward",
    "player-037": "Forward",    "player-038": "Forward",    "player-039": "Goalkeeper",
    "player-040": "Goalkeeper",
}


@router.get("/performance")
def get_player_performance():
    supabase = get_db()

    response = supabase.table("player_match_stats").select(
        "player_id, minutes_played, distance_covered, sprints, passes, shots, goals, assists, "
        "expected_goals, expected_assists, key_passes, progressive_carries, "
        "dribbles_attempted, dribbles_completed, tackles"
    ).execute()

    aggregated = {}
    for row in response.data:
        pid = row["player_id"]
        if pid not in aggregated:
            aggregated[pid] = {
                "player_id": pid,
                "total_minutes": 0,
                "total_goals": 0,
                "total_assists": 0,
                "total_shots": 0,
                "total_passes": 0,
                "total_sprints": 0,
                "avg_distance": [],
                "matches_played": 0,
                "total_expected_goals": 0.0,
                "total_expected_assists": 0.0,
                "total_key_passes": 0,
                "total_progressive_carries": 0,
                "total_tackles": 0,
                "total_dribbles_attempted": 0,
                "total_dribbles_completed": 0,
            }
        p = aggregated[pid]
        p["total_minutes"] += row["minutes_played"]
        p["total_goals"] += row["goals"]
        p["total_assists"] += row["assists"]
        p["total_shots"] += row["shots"]
        p["total_passes"] += row["passes"]
        p["total_sprints"] += row["sprints"]
        p["avg_distance"].append(row["distance_covered"])
        p["matches_played"] += 1
        p["total_expected_goals"] += row.get("expected_goals") or 0.0
        p["total_expected_assists"] += row.get("expected_assists") or 0.0
        p["total_key_passes"] += row.get("key_passes") or 0
        p["total_progressive_carries"] += row.get("progressive_carries") or 0
        p["total_tackles"] += row.get("tackles") or 0
        p["total_dribbles_attempted"] += row.get("dribbles_attempted") or 0
        p["total_dribbles_completed"] += row.get("dribbles_completed") or 0

    result = []
    for p in aggregated.values():
        p["avg_distance"] = round(sum(p["avg_distance"]) / len(p["avg_distance"]), 2)
        p["total_expected_goals"] = round(p["total_expected_goals"], 2)
        p["total_expected_assists"] = round(p["total_expected_assists"], 2)
        attempted = p.pop("total_dribbles_attempted")
        completed = p.pop("total_dribbles_completed")
        p["dribble_success_rate"] = round((completed / attempted * 100), 1) if attempted > 0 else 0.0
        result.append(p)

    return result


@router.get("/fatigue-risk")
def get_fatigue_risk():
    supabase = get_db()

    response = supabase.table("player_match_stats").select(
        "player_id, minutes_played, sprints"
    ).execute()

    aggregated = {}
    for row in response.data:
        pid = row["player_id"]
        if pid not in aggregated:
            aggregated[pid] = {"total_minutes": 0, "sprints_list": [], "matches": 0}
        aggregated[pid]["total_minutes"] += row["minutes_played"]
        aggregated[pid]["sprints_list"].append(row["sprints"])
        aggregated[pid]["matches"] += 1

    result = []
    for pid, stats in aggregated.items():
        avg_sprints = round(sum(stats["sprints_list"]) / stats["matches"], 2)
        total_minutes = stats["total_minutes"]
        reasons = []
        if total_minutes > 400:
            reasons.append(f"High workload — {total_minutes} minutes played")
        if avg_sprints > 40:
            reasons.append(f"High sprint load — averaging {int(avg_sprints)} sprints per match")
        if reasons:
            result.append({
                "player_id": pid,
                "total_minutes": total_minutes,
                "avg_sprints": avg_sprints,
                "reason": "; ".join(reasons),
            })

    return result


@router.get("/depth")
def get_squad_depth():
    supabase = get_db()

    response = supabase.table("player_match_stats").select("player_id").execute()

    seen = set()
    depth = {"Goalkeeper": [], "Defender": [], "Midfielder": [], "Forward": []}
    for row in response.data:
        pid = row["player_id"]
        if pid not in seen:
            seen.add(pid)
            pos = PLAYER_POSITIONS.get(pid)
            if pos in depth:
                depth[pos].append(pid)

    depth["total_players"] = len(seen)
    return depth
