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
    ppda_by_match = {r["match_id"]: r.get("ppda") for r in team_stats_rows}

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
            "ppda": ppda_by_match.get(m["id"]),
        })
    return result


def build_readiness_response(at_risk_players, player_statuses=None):
    """at_risk_players: from get_at_risk_players (fatigue rule only).
    player_statuses: player_status rows ({"player_id", "status", ...}),
    the coach's manually-set availability -- independent signal from fatigue.

    A player marked unavailable is definitely not playing, so their fatigue
    flag (if any) is dropped from the fatigue penalty to avoid double-
    counting the same absence twice. Doubtful is not a confirmed absence,
    so fatigue still applies on top of it.
    """
    player_statuses = player_statuses or []
    unavailable = [s for s in player_statuses if s["status"] == "unavailable"]
    doubtful = [s for s in player_statuses if s["status"] == "doubtful"]
    unavailable_ids = {s["player_id"] for s in unavailable}

    counted_at_risk = [p for p in at_risk_players if p["player_id"] not in unavailable_ids]
    fatigue_penalty = 5 * len(counted_at_risk)
    availability_penalty = 15 * len(unavailable) + 7 * len(doubtful)

    score = max(0, 100 - fatigue_penalty - availability_penalty)
    return {
        "readiness_score": score,
        "at_risk_players": at_risk_players,
        "unavailable_players": unavailable,
        "doubtful_players": doubtful,
    }


def _average(values):
    return round(sum(values) / len(values), 2) if values else None


def build_team_info_response(team_name, competition_name, season_name,
                             team_stats_rows=None):
    """Real values for what used to be hardcoded on the frontend (team name,
    league, season) -- team_name from the teams table, competition/season
    from any matches row since every match this squad plays is in the same
    competition/season.

    team_stats_rows: this team's team_match_stats rows across the whole
    season (ppda, field_tilt_pct only). Averaged for the Dashboard's Season
    Snapshot -- both metrics are already computed and stored per match by
    the pipeline, this just aggregates across matches. Nulls (a zero-
    denominator match, see pipeline_v2's PPDA/field-tilt comments) are
    excluded from the average rather than treated as 0.
    """
    ppda_values = [r["ppda"] for r in (team_stats_rows or []) if r["ppda"] is not None]
    tilt_values = [r["field_tilt_pct"] for r in (team_stats_rows or []) if r["field_tilt_pct"] is not None]
    return {
        "team_name": team_name,
        "competition_name": competition_name,
        "season_name": season_name,
        "season_ppda_avg": _average(ppda_values),
        "season_field_tilt_avg": _average(tilt_values),
    }


def build_match_detail_response(match_row, team_names_by_id, stats_rows, players_by_id,
                                shot_rows=None, team_stats_rows=None):
    """match_row: single `matches` row. team_names_by_id: {team_id: name}.
    stats_rows: player_match_stats rows for this match_id, both teams mixed
    together. players_by_id: {player_id: {"name", "nickname"}}.
    shot_rows: match_events rows for this match_id with event_type='Shot',
    both teams mixed together.
    team_stats_rows: team_match_stats rows for this match_id, both teams
    mixed together (team_id, ppda, field_tilt_pct).

    Splits the mixed stats_rows into a per-team lineup, each entry carrying
    the real name/nickname/goals/assists for that match -- this is what
    powers the match modal's "who scored, who assisted" view. shot_rows pass
    through as a flat `shots` list (raw StatsBomb pitch coordinates -- each
    shot is in its own team's attacking frame, toward x=120; the frontend
    mirrors one team for display) with player names resolved. team_stats_rows
    attaches each team's own ppda/field_tilt_pct for this match.
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

    shots = []
    for s in shot_rows or []:
        meta = players_by_id.get(s["player_id"], {})
        shots.append({
            "player_id": s["player_id"],
            "player_name": meta.get("nickname") or meta.get("name"),
            "team_id": s["team_id"],
            "minute": s["minute"],
            "x": s["x"],
            "y": s["y"],
            "outcome": s["outcome"],
            "xg": s["xg"],
        })
    shots.sort(key=lambda s: s["minute"])

    team_stats_by_team_id = {r["team_id"]: r for r in (team_stats_rows or [])}

    def team_metrics(team_id):
        row = team_stats_by_team_id.get(team_id, {})
        return {"ppda": row.get("ppda"), "field_tilt_pct": row.get("field_tilt_pct")}

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
            **team_metrics(home_id),
        },
        "away_team": {
            "id": away_id,
            "name": team_names_by_id.get(away_id),
            "score": match_row["away_score"],
            "lineup": lineup_for(away_id),
            **team_metrics(away_id),
        },
        "shots": shots,
    }


def fetch_matches_summary_data(client):
    matches_rows = client.table("matches").select(
        "id, date, home_team_id, away_team_id, home_score, away_score, stadium, match_week"
    ).execute().data

    team_ids = {m["home_team_id"] for m in matches_rows} | {m["away_team_id"] for m in matches_rows}
    teams_rows = client.table("teams").select("id, name").in_("id", list(team_ids)).execute().data
    team_names_by_id = {t["id"]: t["name"] for t in teams_rows}

    match_ids = [m["id"] for m in matches_rows]
    team_stats_rows = client.table("team_match_stats").select(
        "match_id, team_id, possession_pct, ppda"
    ).eq("team_id", BARCELONA_TEAM_ID).in_("match_id", match_ids).execute().data

    return build_matches_response(matches_rows, team_stats_rows, team_names_by_id, BARCELONA_TEAM_ID)


@matches_router.get("/summary")
def get_matches_summary(_user: AuthenticatedUser = Depends(get_current_user), client=Depends(get_db)):
    return fetch_matches_summary_data(client)


@matches_router.get("/{match_id}/detail")
def get_match_detail(match_id: int, _user: AuthenticatedUser = Depends(get_current_user), supabase=Depends(get_db)):
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

    shot_rows = supabase.table("match_events").select(
        "player_id, team_id, minute, x, y, outcome, xg"
    ).eq("match_id", match_id).eq("event_type", "Shot").execute().data

    team_stats_rows = supabase.table("team_match_stats").select(
        "team_id, ppda, field_tilt_pct"
    ).eq("match_id", match_id).execute().data

    player_ids = list({r["player_id"] for r in stats_rows}
                      | {s["player_id"] for s in shot_rows})
    players_rows = supabase.table("players").select("id, name, nickname").in_(
        "id", player_ids
    ).execute().data if player_ids else []
    players_by_id = {p["id"]: {"name": p["name"], "nickname": p["nickname"]} for p in players_rows}

    return build_match_detail_response(match_row, team_names_by_id, stats_rows, players_by_id,
                                       shot_rows, team_stats_rows)


# ------------------------------ pass network ------------------------------

# Minimum completed passes between a pair before an edge is drawn -- matches
# the reference pass-network example's own 3+ cutoff. Below it a pairing is
# noise, not a combination.
PASS_EDGE_MIN = 3

# PostgREST caps a single response at 1000 rows. A match has ~1000-1900
# Pass/Carry events since the match_events expansion, so event queries MUST
# page or they silently truncate -- the pass-network/progressive endpoints
# initially lost ~60% of the Clasico's rows exactly this way.
_PAGE_SIZE = 1000


def _fetch_all_pages(query):
    """query: a PostgREST select builder, fully filtered. Returns every row,
    paging by _PAGE_SIZE until a short page arrives."""
    rows, page = [], 0
    while True:
        chunk = query.range(page * _PAGE_SIZE, page * _PAGE_SIZE + _PAGE_SIZE - 1).execute().data
        rows.extend(chunk)
        if len(chunk) < _PAGE_SIZE:
            return rows
        page += 1


def build_pass_network_response(match_id, pass_rows, players_by_id):
    """pass_rows: match_events rows for this match with event_type='Pass',
    outcome='Complete' and recipient_id set -- only real completed passes
    between resolved players. players_by_id: {player_id: {"name", "nickname"}}.

    Per team: a node per player who made or received a completed pass,
    positioned at the average of their involvements (own pass origins +
    received-pass end points); an undirected edge per pair with >=
    PASS_EDGE_MIN completed passes between them (both directions summed).
    """
    by_team = {}
    for r in pass_rows:
        if r.get("recipient_id") is None or r.get("outcome") != "Complete":
            continue
        t = by_team.setdefault(r["team_id"], {"positions": {}, "passes": {}, "pairs": {}})
        t["positions"].setdefault(r["player_id"], []).append((r["x"], r["y"]))
        t["positions"].setdefault(r["recipient_id"], []).append((r["end_x"], r["end_y"]))
        t["passes"][r["player_id"]] = t["passes"].get(r["player_id"], 0) + 1
        pair = tuple(sorted((r["player_id"], r["recipient_id"])))
        t["pairs"][pair] = t["pairs"].get(pair, 0) + 1

    teams = []
    for team_id, t in by_team.items():
        nodes = []
        for pid, points in t["positions"].items():
            meta = players_by_id.get(pid, {})
            nodes.append({
                "player_id": pid,
                "name": meta.get("name"),
                "nickname": meta.get("nickname"),
                "x": sum(p[0] for p in points) / len(points),
                "y": sum(p[1] for p in points) / len(points),
                "passes": t["passes"].get(pid, 0),
            })
        nodes.sort(key=lambda n: n["passes"], reverse=True)
        edges = [
            {"a": a, "b": b, "count": count}
            for (a, b), count in sorted(t["pairs"].items(), key=lambda kv: -kv[1])
            if count >= PASS_EDGE_MIN
        ]
        teams.append({"team_id": team_id, "nodes": nodes, "edges": edges})

    teams.sort(key=lambda t: t["team_id"])
    return {"match_id": match_id, "teams": teams}


@matches_router.get("/{match_id}/pass-network")
def get_pass_network(match_id: int, _user: AuthenticatedUser = Depends(get_current_user),
                     client=Depends(get_db)):
    pass_rows = _fetch_all_pages(
        client.table("match_events").select(
            "match_id, player_id, recipient_id, team_id, event_type, outcome, "
            "x, y, end_x, end_y, minute"
        ).eq("match_id", match_id).eq("event_type", "Pass").eq(
            "outcome", "Complete"
        ).not_.is_("recipient_id", "null").order("id")
    )

    player_ids = ({r["player_id"] for r in pass_rows}
                  | {r["recipient_id"] for r in pass_rows})
    players_rows = client.table("players").select("id, name, nickname").in_(
        "id", list(player_ids)
    ).execute().data if player_ids else []
    players_by_id = {p["id"]: {"name": p["name"], "nickname": p["nickname"]}
                     for p in players_rows}

    return build_pass_network_response(match_id, pass_rows, players_by_id)


def fetch_readiness_data(client):
    """Runs the full /api/team/readiness computation against real tables.
    Used by the route below and, in-process, by app.services.ai_service
    for the AI assistant's readiness answers -- one implementation, not
    two copies of the player_status join logic.
    """
    at_risk = get_at_risk_players(client, BARCELONA_TEAM_ID)

    status_rows = client.table("player_status").select(
        "player_id, status, note, updated_by, updated_at, players(name, nickname)"
    ).execute().data
    player_statuses = []
    for r in status_rows:
        joined = r.pop("players", None) or {}
        player_statuses.append({**r, "name": joined.get("name"), "nickname": joined.get("nickname")})

    return build_readiness_response(at_risk, player_statuses)


@team_router.get("/readiness")
def get_team_readiness(_user: AuthenticatedUser = Depends(get_current_user), client=Depends(get_db)):
    return fetch_readiness_data(client)


def fetch_team_info_data(client):
    """Runs the full /api/team/info computation against real tables. Used
    by the route below and, in-process, by app.services.ai_service for the
    AI assistant's team_season_stats answers.
    """
    team_rows = client.table("teams").select("id, name").eq(
        "id", BARCELONA_TEAM_ID
    ).execute().data
    team_name = team_rows[0]["name"] if team_rows else None

    match_rows = client.table("matches").select(
        "competition_name, season_name"
    ).limit(1).execute().data
    competition_name = match_rows[0]["competition_name"] if match_rows else None
    season_name = match_rows[0]["season_name"] if match_rows else None

    team_stats_rows = client.table("team_match_stats").select(
        "ppda, field_tilt_pct"
    ).eq("team_id", BARCELONA_TEAM_ID).execute().data

    return build_team_info_response(team_name, competition_name, season_name, team_stats_rows)


@team_router.get("/info")
def get_team_info(_user: AuthenticatedUser = Depends(get_current_user), client=Depends(get_db)):
    return fetch_team_info_data(client)
