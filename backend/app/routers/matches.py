from fastapi import APIRouter
from app.config import SUPABASE_URL, SUPABASE_KEY
from supabase import create_client

matches_router = APIRouter(prefix="/api/matches", tags=["matches"])
team_router = APIRouter(prefix="/api/team", tags=["team"])

def get_db():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


@matches_router.get("/summary")
def get_matches_summary():
    supabase = get_db()

    matches = supabase.table("matches").select(
        "id, date, opponent, home_away_neutral, result, goals_scored, goals_conceded"
    ).execute().data

    team_stats = supabase.table("team_match_stats").select(
        "match_id, possession"
    ).execute().data

    possession_by_match = {row["match_id"]: row["possession"] for row in team_stats}

    for match in matches:
        match["possession"] = possession_by_match.get(match["id"])

    return matches


@team_router.get("/readiness")
def get_team_readiness():
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

    at_risk = []
    for pid, stats in aggregated.items():
        avg_sprints = round(sum(stats["sprints_list"]) / stats["matches"], 2)
        total_minutes = stats["total_minutes"]
        reasons = []
        if total_minutes > 400:
            reasons.append(f"High workload — {total_minutes} minutes played")
        if avg_sprints > 40:
            reasons.append(f"High sprint load — averaging {int(avg_sprints)} sprints per match")
        if reasons:
            at_risk.append({
                "player_id": pid,
                "total_minutes": total_minutes,
                "avg_sprints": avg_sprints,
                "reason": "; ".join(reasons),
            })

    score = max(0, 100 - (5 * len(at_risk)))
    return {"readiness_score": score, "at_risk_players": at_risk}
