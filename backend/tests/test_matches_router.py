"""Regression test for the audit's #3 bug: /api/matches/summary never
selected the stadium column, so match.venue was always undefined on the
frontend and silently fell back to a generic string.

Also covers keeping the rest of the response shape close to v1's
(opponent/home_away_neutral/result/goals_scored/goals_conceded relative to
our own team), now computed from schema_v2's team-agnostic match rows.
"""

from app.routers.matches import (
    BARCELONA_TEAM_ID,
    build_match_detail_response,
    build_matches_response,
    build_readiness_response,
    build_team_info_response,
)

TEAM_NAMES = {215: "Athletic Club", 217: "Barcelona", 223: "Malaga"}


def test_matches_summary_includes_real_stadium_value():
    matches_rows = [
        {"id": 266236, "date": "2015-08-23", "home_team_id": 215,
         "away_team_id": 217, "home_score": 0, "away_score": 1,
         "stadium": "San Mames", "match_week": 1},
    ]
    team_stats_rows = [{"match_id": 266236, "team_id": 217, "possession_pct": 67.58}]

    result = build_matches_response(matches_rows, team_stats_rows, TEAM_NAMES, BARCELONA_TEAM_ID)

    assert len(result) == 1
    assert result[0]["stadium"] == "San Mames"
    assert result[0]["stadium"] != "Home"
    assert result[0]["stadium"] is not None


def test_matches_summary_computes_result_relative_to_our_team():
    matches_rows = [
        {"id": 1, "date": "2015-08-23", "home_team_id": 215, "away_team_id": 217,
         "home_score": 0, "away_score": 1, "stadium": "San Mames", "match_week": 1},
        {"id": 2, "date": "2015-08-29", "home_team_id": 217, "away_team_id": 223,
         "home_score": 1, "away_score": 1, "stadium": "Camp Nou", "match_week": 2},
    ]

    result = build_matches_response(matches_rows, [], TEAM_NAMES, BARCELONA_TEAM_ID)

    away_win = result[0]
    assert away_win["home_away_neutral"] == "away"
    assert away_win["opponent"] == "Athletic Club"
    assert away_win["result"] == "win"
    assert away_win["goals_scored"] == 1
    assert away_win["goals_conceded"] == 0

    home_draw = result[1]
    assert home_draw["home_away_neutral"] == "home"
    assert home_draw["opponent"] == "Malaga"
    assert home_draw["result"] == "draw"


def test_matches_summary_possession_is_none_when_missing():
    matches_rows = [
        {"id": 1, "date": "2015-08-23", "home_team_id": 215, "away_team_id": 217,
         "home_score": 0, "away_score": 1, "stadium": "San Mames", "match_week": 1},
    ]

    result = build_matches_response(matches_rows, [], TEAM_NAMES, BARCELONA_TEAM_ID)

    assert result[0]["possession_pct"] is None


def test_matches_summary_attaches_possession_by_match():
    matches_rows = [
        {"id": 1, "date": "2015-08-23", "home_team_id": 215, "away_team_id": 217,
         "home_score": 0, "away_score": 1, "stadium": "San Mames", "match_week": 1},
        {"id": 2, "date": "2015-08-29", "home_team_id": 217, "away_team_id": 223,
         "home_score": 1, "away_score": 0, "stadium": "Camp Nou", "match_week": 2},
    ]
    team_stats_rows = [
        {"match_id": 1, "team_id": 217, "possession_pct": 67.58},
        {"match_id": 2, "team_id": 217, "possession_pct": 72.91},
    ]

    result = build_matches_response(matches_rows, team_stats_rows, TEAM_NAMES, BARCELONA_TEAM_ID)

    assert result[0]["possession_pct"] == 67.58
    assert result[1]["possession_pct"] == 72.91


def test_readiness_score_penalizes_five_points_per_at_risk_player():
    at_risk = [{"player_id": 1}, {"player_id": 2}]

    result = build_readiness_response(at_risk)

    assert result["readiness_score"] == 90
    assert result["at_risk_players"] == at_risk


def test_readiness_score_floors_at_zero():
    at_risk = [{"player_id": i} for i in range(25)]

    result = build_readiness_response(at_risk)

    assert result["readiness_score"] == 0


# --------------------------- bug: hardcoded team/league name ---------------------------

def test_team_info_returns_real_team_competition_and_season():
    # Regression test for the frontend's hardcoded "Al Qadsiah" / "Saudi Pro
    # League" strings -- this is the real data they must be replaced with.
    result = build_team_info_response("Barcelona", "La Liga", "2015/2016")

    assert result == {
        "team_name": "Barcelona",
        "competition_name": "La Liga",
        "season_name": "2015/2016",
    }


# --------------------------- match detail (lineups, scorers, assists) ---------------------------

MATCH_ROW = {
    "id": 266236, "date": "2015-08-23", "home_team_id": 215, "away_team_id": 217,
    "home_score": 0, "away_score": 1, "stadium": "San Mames",
}
DETAIL_TEAM_NAMES = {215: "Athletic Club", 217: "Barcelona"}
DETAIL_PLAYERS_BY_ID = {
    5503: {"name": "Lionel Messi", "nickname": "Messi"},
    5246: {"name": "Luis Suarez", "nickname": None},
    999:  {"name": "Iker Muniain", "nickname": None},
}


def test_match_detail_splits_lineup_by_team():
    stats_rows = [
        {"player_id": 5503, "team_id": 217, "position": "Right Wing", "minutes_played": 90, "goals": 1, "assists": 0},
        {"player_id": 5246, "team_id": 217, "position": "Center Forward", "minutes_played": 90, "goals": 0, "assists": 1},
        {"player_id": 999,  "team_id": 215, "position": "Right Wing", "minutes_played": 90, "goals": 0, "assists": 0},
    ]

    result = build_match_detail_response(MATCH_ROW, DETAIL_TEAM_NAMES, stats_rows, DETAIL_PLAYERS_BY_ID)

    assert result["id"] == 266236
    assert result["stadium"] == "San Mames"
    assert result["home_team"]["name"] == "Athletic Club"
    assert result["home_team"]["score"] == 0
    assert [p["player_id"] for p in result["home_team"]["lineup"]] == [999]
    assert result["away_team"]["name"] == "Barcelona"
    assert result["away_team"]["score"] == 1
    assert {p["player_id"] for p in result["away_team"]["lineup"]} == {5503, 5246}


def test_match_detail_includes_real_names_goals_and_assists():
    stats_rows = [
        {"player_id": 5503, "team_id": 217, "position": "Right Wing", "minutes_played": 90, "goals": 1, "assists": 0},
        {"player_id": 5246, "team_id": 217, "position": "Center Forward", "minutes_played": 90, "goals": 0, "assists": 1},
    ]

    result = build_match_detail_response(MATCH_ROW, DETAIL_TEAM_NAMES, stats_rows, DETAIL_PLAYERS_BY_ID)

    by_id = {p["player_id"]: p for p in result["away_team"]["lineup"]}
    assert by_id[5503]["name"] == "Lionel Messi"
    assert by_id[5503]["nickname"] == "Messi"
    assert by_id[5503]["goals"] == 1
    assert by_id[5503]["assists"] == 0
    assert by_id[5246]["goals"] == 0
    assert by_id[5246]["assists"] == 1


def test_match_detail_lineup_sorted_by_minutes_played_desc():
    stats_rows = [
        {"player_id": 5246, "team_id": 217, "position": "Center Forward", "minutes_played": 60, "goals": 0, "assists": 0},
        {"player_id": 5503, "team_id": 217, "position": "Right Wing", "minutes_played": 90, "goals": 0, "assists": 0},
    ]

    result = build_match_detail_response(MATCH_ROW, DETAIL_TEAM_NAMES, stats_rows, DETAIL_PLAYERS_BY_ID)

    assert [p["player_id"] for p in result["away_team"]["lineup"]] == [5503, 5246]
