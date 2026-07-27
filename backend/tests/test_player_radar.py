"""Tests for the player radar response builder (per-90 rates, percentile-
ranked against players sharing the same primary_position). All expected
numbers hand-computed.

Percentile convention: percentile rank with ties, 100 * (below + 0.5 * at) / n,
where n is the comparison pool size (qualifying peers, always including the
target player). Pool floor: RADAR_MIN_MINUTES total minutes -- a 20-minute
substitute's 90-per-90 rates shouldn't distort everyone else's percentiles,
but the target player is always ranked even when below the floor.
"""

import pytest

from app.routers.players import (
    RADAR_METRICS,
    RADAR_MIN_MINUTES,
    build_radar_response,
    percentile_rank,
)


def pms_row(player_id, minutes, goals=0, xg=0.0, key_passes=0,
            progressive_passes=0, progressive_carries=0, pressures=0):
    return {
        "player_id": player_id, "minutes_played": minutes, "goals": goals,
        "xg": xg, "key_passes": key_passes,
        "progressive_passes": progressive_passes,
        "progressive_carries": progressive_carries, "pressures": pressures,
    }


PLAYERS_BY_ID = {
    1: {"name": "Target Winger", "nickname": None, "primary_position": "Right Wing"},
    2: {"name": "Peer Winger", "nickname": None, "primary_position": "Right Wing"},
    3: {"name": "Cameo Winger", "nickname": None, "primary_position": "Right Wing"},
    4: {"name": "Some Striker", "nickname": None, "primary_position": "Center Forward"},
}

# Player 1 (target): 900 min total across two rows; goals 5 -> 0.5/90,
# xg 4.5 -> 0.45, key passes 18 -> 1.8, prog passes 27 -> 2.7,
# prog carries 36 -> 3.6, pressures 90 -> 9.0.
# Player 2: 450 min; goals 1 -> 0.2, xg 0.9 -> 0.18, kp 5 -> 1.0,
# pp 10 -> 2.0, pc 5 -> 1.0, pressures 50 -> 10.0.
# Player 3: 60 min (< RADAR_MIN_MINUTES) -- excluded from the pool.
# Player 4: different position -- never a peer.
STATS_ROWS = [
    pms_row(1, 600, goals=3, xg=3.0, key_passes=12, progressive_passes=20,
            progressive_carries=24, pressures=60),
    pms_row(1, 300, goals=2, xg=1.5, key_passes=6, progressive_passes=7,
            progressive_carries=12, pressures=30),
    pms_row(2, 450, goals=1, xg=0.9, key_passes=5, progressive_passes=10,
            progressive_carries=5, pressures=50),
    pms_row(3, 60, goals=3, xg=2.0, key_passes=4, progressive_passes=4,
            progressive_carries=4, pressures=40),
    pms_row(4, 900, goals=20, xg=18.0, key_passes=10, progressive_passes=10,
            progressive_carries=10, pressures=10),
]


def metric(resp, key):
    matches = [m for m in resp["metrics"] if m["key"] == key]
    assert len(matches) == 1
    return matches[0]


def test_percentile_rank_with_ties():
    # standard percentile-rank-with-ties formula: 100 * (below + 0.5*at) / n
    assert percentile_rank(0.5, [0.2, 0.5]) == pytest.approx(75.0)
    assert percentile_rank(0.2, [0.2, 0.5]) == pytest.approx(25.0)
    assert percentile_rank(1.0, [1.0, 1.0]) == pytest.approx(50.0)
    assert percentile_rank(3.0, [1.0, 2.0, 3.0]) == pytest.approx(100 * 2.5 / 3)


def test_radar_has_all_six_metrics_in_order():
    resp = build_radar_response(1, STATS_ROWS, PLAYERS_BY_ID)
    assert [m["key"] for m in resp["metrics"]] == [k for k, _label, _col in RADAR_METRICS]


def test_radar_per90_rates_aggregate_across_matches():
    resp = build_radar_response(1, STATS_ROWS, PLAYERS_BY_ID)
    assert resp["minutes"] == 900
    assert metric(resp, "goals_per90")["value"] == pytest.approx(0.5)
    assert metric(resp, "xg_per90")["value"] == pytest.approx(0.45)
    assert metric(resp, "key_passes_per90")["value"] == pytest.approx(1.8)
    assert metric(resp, "progressive_passes_per90")["value"] == pytest.approx(2.7)
    assert metric(resp, "progressive_carries_per90")["value"] == pytest.approx(3.6)
    assert metric(resp, "pressures_per90")["value"] == pytest.approx(9.0)


def test_radar_percentiles_against_same_position_pool_only():
    # Pool is exactly {player 1, player 2}: player 3 is under the minutes
    # floor, player 4 plays a different position. n = 2.
    resp = build_radar_response(1, STATS_ROWS, PLAYERS_BY_ID)
    assert resp["primary_position"] == "Right Wing"
    assert resp["pool_size"] == 2
    # goals 0.5 vs 0.2: below=1, at=1 -> 100 * 1.5 / 2 = 75
    assert metric(resp, "goals_per90")["percentile"] == pytest.approx(75.0)
    # pressures 9.0 vs 10.0: below=0, at=1 -> 25
    assert metric(resp, "pressures_per90")["percentile"] == pytest.approx(25.0)


def test_radar_target_below_minutes_floor_is_still_ranked():
    # Player 3 has 60 minutes -- below the floor -- but asking for their
    # radar must still work: they join the pool themselves (n = 3).
    assert 60 < RADAR_MIN_MINUTES
    resp = build_radar_response(3, STATS_ROWS, PLAYERS_BY_ID)
    assert resp["pool_size"] == 3
    assert resp["minutes"] == 60
    # goals: 3 in 60 min -> 4.5/90 vs pool rates [0.5, 0.2, 4.5]
    assert metric(resp, "goals_per90")["value"] == pytest.approx(4.5)
    # 100 * 2.5 / 3 = 83.33..., rounded to one decimal in the response
    assert metric(resp, "goals_per90")["percentile"] == pytest.approx(83.3)


def test_radar_unknown_player_returns_none():
    assert build_radar_response(999, STATS_ROWS, PLAYERS_BY_ID) is None


def test_radar_player_with_no_position_returns_none():
    players = {1: {"name": "Mystery", "nickname": None, "primary_position": None}}
    assert build_radar_response(1, [pms_row(1, 90)], players) is None


def test_radar_player_with_no_minutes_returns_none():
    players = {1: {"name": "Bench Only", "nickname": None, "primary_position": "Right Wing"}}
    assert build_radar_response(1, [pms_row(1, 0)], players) is None
