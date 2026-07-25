from fastapi import APIRouter, Depends, HTTPException

from app.auth import AuthenticatedUser, get_current_user
from app.db import get_db
from app.services.fatigue import get_at_risk_players

matches_router = APIRouter(prefix="/api/matches", tags=["matches"])
team_router = APIRouter(prefix="/api/team", tags=["team"])

# Scoped to our own squad, same as players.py.
BARCELONA_TEAM_ID = 217


def build_matches_response(matches_rows, team_stats_rows, team_names_by_id, our_team_id):
    """matches_rows: schema_v2 matches rows (team-agnostic home/away/score).
    team_stats_rows: team_match_stats rows for our_team_id only.
    team_names_by_id: {team_id: name}, used to resolve the opponent's name.

    Reshapes the team-agnostic match rows into v1's opponent-relative shape
    (opponent/home_away_neutral/result/goals_scored/goals_conceded), and
    actually includes stadium now -- the audit's #3 bug (never selected,
    so the frontend's venue always fell back to a generic 'Home' string).
    """
    possession_by_match = {r["match_id"]: r["possession_pct"] for r in team_stats_rows}

    result = []
    for m in matches_rows:
        is_home = m["home_team_id"] == our_team_id
        opponent_id = m["away_team_id"] if is_home else m["home_team_id"]
        goals_scored = m["home_score"] if is_home else m["away_score"]
        goals_conceded = m["away_score"] if is_home else m["home_score"]
        outcome = (
            "win" if goals_scored > goals_conceded
            else "draw" if goals_scored == goals_conceded
            else "loss"
        )
        result.append({
            "id": m["id"],
            "date": m["date"],
            "opponent": team_names_by_id.get(opponent_id, opponent_id),
            "home_away_neutral": "home" if is_home else "away",
            "result": outcome,
            "goals_scored": goals_scored,
            "goals_conceded": goals_conceded,
            "stadium": m["stadium"],
            "possession_pct": possession_by_match.get(m["id"]),
        })
    return result


def build_readiness_response(at_risk_players):
    score = max(0, 100 - (5 * len(at_risk_players)))
    return {"readiness_score": score, "at_risk_players": at_risk_players}


def build_team_info_response(team_name, competition_name, season_name):
    """Real values for what used to be hardcoded on the frontend (team name,
    league, season) -- team_name from the teams table, competition/season
    from any matches row since every match this squad plays is in the same
    competition/season.
    """
    return {
        "team_name": team_name,
        "competition_name": competition_name,
        "season_name": season_name,
    }


def build_match_detail_response(match_row, team_names_by_id, stats_rows, players_by_id):
    """match_row: single `matches` row. team_names_by_id: {team_id: name}.
    stats_rows: player_match_stats rows for this match_id, both teams mixed
    together. players_by_id: {player_id: {"name", "nickname"}}.

    Splits the mixed stats_rows into a per-team lineup, each entry carrying
    the real name/nickname/goals/assists for that match -- this is what
    powers the match modal's "who scored, who assisted" view.
    """
    def lineup_for(team_id):
        entries = []
        for row in stats_rows:
            if row["team_id"] != team_id:
                continue
            meta = players_by_id.get(row["player_id"], {})
            entries.append({
                "player_id": row["player_id"],
                "name": meta.get("name"),
                "nickname": meta.get("nickname"),
                "position": row.get("position"),
                "minutes_played": row.get("minutes_played") or 0,
                "goals": row.get("goals") or 0,
                "assists": row.get("assists") or 0,
            })
        entries.sort(key=lambda p: p["minutes_played"], reverse=True)
        return entries

    home_id = match_row["home_team_id"]
    away_id = match_row["away_team_id"]
    return {
        "id": match_row["id"],
        "date": match_row["date"],
        "stadium": match_row["stadium"],
        "home_team": {
            "id": home_id,
            "name": team_names_by_id.get(home_id),
            "score": match_row["home_score"],
            "lineup": lineup_for(home_id),
        },
        "away_team": {
            "id": away_id,
            "name": team_names_by_id.get(away_id),
            "score": match_row["away_score"],
            "lineup": lineup_for(away_id),
        },
    }


@matches_router.get("/summary")
def get_matches_summary(_user: AuthenticatedUser = Depends(get_current_user)):
    supabase = get_db()

    matches_rows = supabase.table("matches").select(
        "id, date, home_team_id, away_team_id, home_score, away_score, stadium, match_week"
    ).execute().data

    team_ids = {m["home_team_id"] for m in matches_rows} | {m["away_team_id"] for m in matches_rows}
    teams_rows = supabase.table("teams").select("id, name").in_("id", list(team_ids)).execute().data
    team_names_by_id = {t["id"]: t["name"] for t in teams_rows}

    match_ids = [m["id"] for m in matches_rows]
    team_stats_rows = supabase.table("team_match_stats").select(
        "match_id, team_id, possession_pct"
    ).eq("team_id", BARCELONA_TEAM_ID).in_("match_id", match_ids).execute().data

    return build_matches_response(matches_rows, team_stats_rows, team_names_by_id, BARCELONA_TEAM_ID)


@matches_router.get("/{match_id}/detail")
def get_match_detail(match_id: int, _user: AuthenticatedUser = Depends(get_current_user)):
    supabase = get_db()

    match_rows = supabase.table("matches").select(
        "id, date, home_team_id, away_team_id, home_score, away_score, stadium"
    ).eq("id", match_id).execute().data
    if not match_rows:
        raise HTTPException(status_code=404, detail="Match not found")
    match_row = match_rows[0]

    team_ids = [match_row["home_team_id"], match_row["away_team_id"]]
    teams_rows = supabase.table("teams").select("id, name").in_("id", team_ids).execute().data
    team_names_by_id = {t["id"]: t["name"] for t in teams_rows}

    stats_rows = supabase.table("player_match_stats").select(
        "player_id, team_id, position, minutes_played, goals, assists"
    ).eq("match_id", match_id).execute().data

    player_ids = list({r["player_id"] for r in stats_rows})
    players_rows = supabase.table("players").select("id, name, nickname").in_(
        "id", player_ids
    ).execute().data if player_ids else []
    players_by_id = {p["id"]: {"name": p["name"], "nickname": p["nickname"]} for p in players_rows}

    return build_match_detail_response(match_row, team_names_by_id, stats_rows, players_by_id)


@team_router.get("/readiness")
def get_team_readiness(_user: AuthenticatedUser = Depends(get_current_user)):
    supabase = get_db()
    at_risk = get_at_risk_players(supabase, BARCELONA_TEAM_ID)
    return build_readiness_response(at_risk)


@team_router.get("/info")
def get_team_info(_user: AuthenticatedUser = Depends(get_current_user)):
    supabase = get_db()

    team_rows = supabase.table("teams").select("id, name").eq(
        "id", BARCELONA_TEAM_ID
    ).execute().data
    team_name = team_rows[0]["name"] if team_rows else None

    match_rows = supabase.table("matches").select(
        "competition_name, season_name"
    ).limit(1).execute().data
    competition_name = match_rows[0]["competition_name"] if match_rows else None
    season_name = match_rows[0]["season_name"] if match_rows else None

    return build_team_info_response(team_name, competition_name, season_name)
