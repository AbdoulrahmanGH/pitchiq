"""Regression tests for the audit bugs fixed in players.py, against the pure
response-building functions (no network).
"""

import pytest

from app.routers.players import (
    BUCKET_ORDER,
    aggregate_performance,
    bucket_position,
    build_depth_response,
)


# --------------------------- bug 1: position depth ---------------------------

def test_all_four_statsbomb_position_families_bucket_correctly():
    assert bucket_position("Goalkeeper") == "Goalkeeper"
    assert bucket_position("Right Back") == "Defender"
    assert bucket_position("Center Back") == "Defender"
    assert bucket_position("Left Wing Back") == "Defender"
    assert bucket_position("Center Defensive Midfield") == "Midfielder"
    assert bucket_position("Right Attacking Midfield") == "Midfielder"
    assert bucket_position("Left Wing") == "Forward"
    assert bucket_position("Center Forward") == "Forward"
    assert bucket_position("Secondary Striker") == "Forward"


def test_depth_buckets_sum_to_exactly_total_players():
    # This is the regression test for the audit's core /depth bug: v1 had
    # two independently-maintained PLAYER_POSITIONS dicts that disagreed, so
    # total_players (every distinct id seen) didn't equal the sum of the
    # four position arrays. There is no dict here at all now -- position
    # comes from the players table, and total_players is defined as the sum
    # of the four buckets by construction.
    players_rows = [
        {"id": 1, "name": "GK One", "nickname": None, "primary_position": "Goalkeeper"},
        {"id": 2, "name": "Def One", "nickname": None, "primary_position": "Right Back"},
        {"id": 3, "name": "Def Two", "nickname": None, "primary_position": "Center Back"},
        {"id": 4, "name": "Mid One", "nickname": None, "primary_position": "Left Midfield"},
        {"id": 5, "name": "Fwd One", "nickname": None, "primary_position": "Center Forward"},
        {"id": 6, "name": "Fwd Two", "nickname": "F2", "primary_position": "Right Wing"},
    ]

    depth = build_depth_response(players_rows)

    bucket_sum = sum(len(depth[b]) for b in BUCKET_ORDER)
    assert bucket_sum == depth["total_players"]
    assert depth["total_players"] == 6
    assert len(depth["Goalkeeper"]) == 1
    assert len(depth["Defender"]) == 2
    assert len(depth["Midfielder"]) == 1
    assert len(depth["Forward"]) == 2


def test_depth_excludes_unresolvable_positions_from_total_but_reports_them():
    # A player with no primary_position (e.g. a pure substitute the pipeline
    # genuinely has no position data for) must not be silently counted into
    # total_players nor silently dropped without a trace.
    players_rows = [
        {"id": 1, "name": "GK One", "nickname": None, "primary_position": "Goalkeeper"},
        {"id": 2, "name": "Mystery", "nickname": None, "primary_position": None},
    ]

    depth = build_depth_response(players_rows)

    assert depth["total_players"] == 1
    assert sum(len(depth[b]) for b in BUCKET_ORDER) == depth["total_players"]
    assert depth["unresolved_players"] == [{"id": 2, "name": "Mystery", "nickname": None}]


def test_depth_entries_include_player_name():
    players_rows = [
        {"id": 5503, "name": "Lionel Messi", "nickname": None, "primary_position": "Right Wing"},
    ]

    depth = build_depth_response(players_rows)

    assert depth["Forward"] == [{"id": 5503, "name": "Lionel Messi", "nickname": None}]


# ------------------------------ bug 2: names ------------------------------

def test_performance_rows_include_name_and_nickname():
    stats_rows = [
        {"player_id": 5503, "minutes_played": 90, "passes_attempted": 40,
         "passes_completed": 35, "key_passes": 2, "progressive_passes": 5,
         "shots": 3, "goals": 1, "xg": 0.4, "xa": 0.2, "assists": 0,
         "dribbles_attempted": 4, "dribbles_completed": 3,
         "progressive_carries": 2, "tackles": 0,
         "pressures": 5, "pressure_regains": 1},
    ]
    players_by_id = {5503: {"name": "Lionel Messi", "nickname": None}}

    result = aggregate_performance(stats_rows, players_by_id)

    assert len(result) == 1
    assert result[0]["player_id"] == 5503
    assert result[0]["name"] == "Lionel Messi"
    assert result[0]["nickname"] is None
    assert result[0]["matches_played"] == 1
    assert result[0]["total_goals"] == 1
    assert result[0]["xg"] == pytest.approx(0.4)
    assert result[0]["dribble_success_rate"] == pytest.approx(75.0)


# ------------------------------ bug 3: assists ------------------------------

def test_performance_rows_sum_real_assists_across_matches():
    # Assists is a genuine column on player_match_stats (goal_assist Pass
    # events, backfilled via migrations/0001) -- not derived from key_passes,
    # which also counts shot_assist passes that never became a goal.
    stats_rows = [
        {"player_id": 5503, "minutes_played": 90, "passes_attempted": 40,
         "passes_completed": 35, "key_passes": 2, "progressive_passes": 5,
         "shots": 3, "goals": 1, "xg": 0.4, "xa": 0.2, "assists": 1,
         "dribbles_attempted": 4, "dribbles_completed": 3,
         "progressive_carries": 2, "tackles": 0,
         "pressures": 5, "pressure_regains": 1},
        {"player_id": 5503, "minutes_played": 90, "passes_attempted": 30,
         "passes_completed": 28, "key_passes": 1, "progressive_passes": 3,
         "shots": 1, "goals": 0, "xg": 0.1, "xa": 0.0, "assists": 2,
         "dribbles_attempted": 2, "dribbles_completed": 1,
         "progressive_carries": 1, "tackles": 1,
         "pressures": 3, "pressure_regains": 0},
    ]
    players_by_id = {5503: {"name": "Lionel Messi", "nickname": None}}

    result = aggregate_performance(stats_rows, players_by_id)

    assert result[0]["total_assists"] == 3


# ------------------------- pressures / pressure regains -------------------------

def test_performance_rows_sum_pressures_and_pressure_regains_across_matches():
    stats_rows = [
        {"player_id": 5503, "minutes_played": 90, "passes_attempted": 40,
         "passes_completed": 35, "key_passes": 2, "progressive_passes": 5,
         "shots": 3, "goals": 1, "xg": 0.4, "xa": 0.2, "assists": 0,
         "dribbles_attempted": 4, "dribbles_completed": 3,
         "progressive_carries": 2, "tackles": 0,
         "pressures": 12, "pressure_regains": 3},
        {"player_id": 5503, "minutes_played": 90, "passes_attempted": 30,
         "passes_completed": 28, "key_passes": 1, "progressive_passes": 3,
         "shots": 1, "goals": 0, "xg": 0.1, "xa": 0.0, "assists": 0,
         "dribbles_attempted": 2, "dribbles_completed": 1,
         "progressive_carries": 1, "tackles": 1,
         "pressures": 8, "pressure_regains": 2},
    ]
    players_by_id = {5503: {"name": "Lionel Messi", "nickname": None}}

    result = aggregate_performance(stats_rows, players_by_id)

    assert result[0]["total_pressures"] == 20
    assert result[0]["total_pressure_regains"] == 5
