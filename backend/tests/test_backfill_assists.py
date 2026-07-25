"""Regression test for the assists backfill (see migrations/0001 and
app/data/backfill_assists.py). Assists were never extracted before this
column existed, so existing player_match_stats rows need real values
computed from each match's already-fetched events, not just new rows going
forward.
"""

from app.data.backfill_assists import count_goal_assists


def test_counts_only_goal_assist_passes_not_shot_assist():
    # A shot_assist pass whose shot missed must not count as an assist --
    # that's exactly the distinction this backfill exists to fix (the old
    # code only ever tracked the broader shot_assist-or-goal_assist union).
    events = [
        {"type": {"name": "Pass"}, "player": {"id": 1},
         "pass": {"goal_assist": True}},
        {"type": {"name": "Pass"}, "player": {"id": 2},
         "pass": {"shot_assist": True}},
        {"type": {"name": "Shot"}, "player": {"id": 3}, "shot": {}},
    ]

    counts = count_goal_assists(events)

    assert counts == {1: 1}


def test_sums_multiple_goal_assists_by_the_same_player():
    events = [
        {"type": {"name": "Pass"}, "player": {"id": 1},
         "pass": {"goal_assist": True}},
        {"type": {"name": "Pass"}, "player": {"id": 1},
         "pass": {"goal_assist": True}},
    ]

    counts = count_goal_assists(events)

    assert counts == {1: 2}


def test_returns_empty_dict_when_no_goal_assists():
    events = [
        {"type": {"name": "Pass"}, "player": {"id": 1}, "pass": {}},
    ]

    counts = count_goal_assists(events)

    assert counts == {}
