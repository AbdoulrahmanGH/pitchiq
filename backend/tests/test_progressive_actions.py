"""Tests for the match progressive-actions builder. The progressive
definition is pipeline_v2._is_progressive -- the exact same Wyscout rule that
computes player_match_stats.progressive_passes/carries -- applied per event
at query time. No new threshold exists anywhere.
"""

import pytest

from app.data.pipeline_v2 import _is_progressive
from app.routers.matches import build_progressive_actions_response


def event_row(player_id, team_id, event_type, x, y, end_x, end_y,
              outcome=None, minute=10):
    return {
        "match_id": 1, "player_id": player_id, "team_id": team_id,
        "event_type": event_type, "outcome": outcome, "minute": minute,
        "x": x, "y": y, "end_x": end_x, "end_y": end_y,
    }


PLAYERS_BY_ID = {
    1: {"name": "Progressor", "nickname": None},
    2: {"name": "Short Passer", "nickname": None},
}

# (50,40)->(85,40): 35 yd = 32.0 m closer, spans halves, >= 15 m -> progressive.
# (60,40)->(62,40): ~1.8 m -> not progressive.
ROWS = [
    event_row(1, 217, "Pass", 50.0, 40.0, 85.0, 40.0, outcome="Complete"),
    event_row(2, 217, "Pass", 60.0, 40.0, 62.0, 40.0, outcome="Complete"),
    event_row(1, 217, "Carry", 50.0, 40.0, 85.0, 40.0),
    event_row(1, 217, "Carry", 60.0, 40.0, 61.0, 40.0),
    event_row(1, 217, "Pass", 50.0, 40.0, 85.0, 40.0, outcome="Incomplete"),
]


def test_uses_the_pipeline_progressive_rule():
    assert _is_progressive((50.0, 40.0), (85.0, 40.0)) is True
    assert _is_progressive((60.0, 40.0), (62.0, 40.0)) is False


def test_only_progressive_passes_and_carries_returned():
    resp = build_progressive_actions_response(1, ROWS, PLAYERS_BY_ID)
    assert resp["match_id"] == 1
    actions = resp["actions"]
    # both progressive passes (completed AND incomplete -- exactly what
    # player_match_stats.progressive_passes counts, so the map reconciles
    # with the stored stat) + the progressive carry; the short pass and
    # short carry are excluded
    assert len(actions) == 3
    passes = [a for a in actions if a["event_type"] == "Pass"]
    assert sorted(p["completed"] for p in passes) == [False, True]
    carries = [a for a in actions if a["event_type"] == "Carry"]
    assert len(carries) == 1
    assert carries[0]["completed"] is True  # a carry always arrives


def test_actions_carry_player_name_and_coordinates():
    resp = build_progressive_actions_response(1, ROWS, PLAYERS_BY_ID)
    p = [a for a in resp["actions"]
         if a["event_type"] == "Pass" and a["completed"]][0]
    assert p["player_id"] == 1
    assert p["player_name"] == "Progressor"
    assert p["team_id"] == 217
    assert p["x"] == pytest.approx(50.0)
    assert p["end_x"] == pytest.approx(85.0)
    assert p["minute"] == 10


def test_rows_with_missing_end_coordinates_are_skipped():
    rows = [event_row(1, 217, "Pass", 50.0, 40.0, None, None, outcome="Complete")]
    resp = build_progressive_actions_response(1, rows, PLAYERS_BY_ID)
    assert resp["actions"] == []
