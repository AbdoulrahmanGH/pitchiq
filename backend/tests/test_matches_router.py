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
        "season_ppda_avg": None,
        "season_field_tilt_avg": None,
    }


def test_team_info_averages_ppda_and_field_tilt_across_season():
    team_stats_rows = [
        {"ppda": 10.0, "field_tilt_pct": 60.0},
        {"ppda": 8.0, "field_tilt_pct": 70.0},
    ]

    result = build_team_info_response("Barcelona", "La Liga", "2015/2016", team_stats_rows)

    assert result["season_ppda_avg"] == 9.0
    assert result["season_field_tilt_avg"] == 65.0


def test_team_info_ignores_null_ppda_and_field_tilt_in_average():
    # A zero-denominator match stores null (see pipeline_v2), never 0 -- a
    # null must not drag the season average toward zero.
    team_stats_rows = [
        {"ppda": 10.0, "field_tilt_pct": None},
        {"ppda": None, "field_tilt_pct": 70.0},
    ]

    result = build_team_info_response("Barcelona", "La Liga", "2015/2016", team_stats_rows)

    assert result["season_ppda_avg"] == 10.0
    assert result["season_field_tilt_avg"] == 70.0


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


def test_match_detail_shots_resolve_names_and_sort_by_minute():
    shot_rows = [
        {"player_id": 5246, "team_id": 217, "minute": 53, "x": 112.9, "y": 40.5, "outcome": "Goal", "xg": 0.365458},
        {"player_id": 999, "team_id": 215, "minute": 14, "x": 89.2, "y": 35.4, "outcome": "Saved", "xg": 0.031754},
    ]

    result = build_match_detail_response(MATCH_ROW, DETAIL_TEAM_NAMES, [], DETAIL_PLAYERS_BY_ID, shot_rows)

    assert [s["minute"] for s in result["shots"]] == [14, 53]
    goal = result["shots"][1]
    assert goal["player_name"] == "Luis Suarez"  # no nickname, falls back to name
    assert goal["team_id"] == 217
    assert (goal["x"], goal["y"]) == (112.9, 40.5)
    assert goal["outcome"] == "Goal"
    assert goal["xg"] == 0.365458


def test_match_detail_without_shot_rows_returns_empty_shots():
    result = build_match_detail_response(MATCH_ROW, DETAIL_TEAM_NAMES, [], DETAIL_PLAYERS_BY_ID)

    assert result["shots"] == []


def test_match_detail_attaches_ppda_and_field_tilt_per_team():
    team_stats_rows = [
        {"team_id": 215, "ppda": 12.4, "field_tilt_pct": 38.2},
        {"team_id": 217, "ppda": 7.9, "field_tilt_pct": 61.8},
    ]

    result = build_match_detail_response(MATCH_ROW, DETAIL_TEAM_NAMES, [], DETAIL_PLAYERS_BY_ID,
                                         team_stats_rows=team_stats_rows)

    assert result["home_team"]["ppda"] == 12.4
    assert result["home_team"]["field_tilt_pct"] == 38.2
    assert result["away_team"]["ppda"] == 7.9
    assert result["away_team"]["field_tilt_pct"] == 61.8


def test_match_detail_without_team_stats_rows_returns_none_metrics():
    result = build_match_detail_response(MATCH_ROW, DETAIL_TEAM_NAMES, [], DETAIL_PLAYERS_BY_ID)

    assert result["home_team"]["ppda"] is None
    assert result["home_team"]["field_tilt_pct"] is None
    assert result["away_team"]["ppda"] is None
    assert result["away_team"]["field_tilt_pct"] is None
