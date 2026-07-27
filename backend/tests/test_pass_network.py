"""Tests for the match pass-network builder. Only real completed passes
between resolved players (recipient_id present) ever enter the network --
nothing inferred. Expected numbers hand-computed.
"""

import pytest

from app.routers.matches import PASS_EDGE_MIN, build_pass_network_response


def pass_row(player_id, recipient_id, team_id, x, y, end_x, end_y):
    return {
        "match_id": 1, "player_id": player_id, "recipient_id": recipient_id,
        "team_id": team_id, "event_type": "Pass", "outcome": "Complete",
        "x": x, "y": y, "end_x": end_x, "end_y": end_y, "minute": 10,
    }


PLAYERS_BY_ID = {
    1: {"name": "Passer One", "nickname": None},
    2: {"name": "Receiver Two", "nickname": "R2"},
    3: {"name": "Occasional Three", "nickname": None},
    9: {"name": "Opp Player", "nickname": None},
}

# Team 217: 1->2 three times (meets the 3+ threshold), 2->1 once (folds into
# the same undirected edge -> count 4), 1->3 once (below threshold, no edge,
# but 3 still gets a node -- they touched the ball). No rows for any other
# team: a team with no completed passes simply doesn't appear.
ROWS = [
    pass_row(1, 2, 217, 60.0, 40.0, 80.0, 40.0),
    pass_row(1, 2, 217, 62.0, 42.0, 82.0, 38.0),
    pass_row(1, 2, 217, 64.0, 38.0, 84.0, 42.0),
    pass_row(2, 1, 217, 90.0, 40.0, 60.0, 40.0),
    pass_row(1, 3, 217, 50.0, 20.0, 55.0, 25.0),
]


def team(resp, team_id):
    matches = [t for t in resp["teams"] if t["team_id"] == team_id]
    assert len(matches) == 1
    return matches[0]


def node(t, player_id):
    matches = [n for n in t["nodes"] if n["player_id"] == player_id]
    assert len(matches) == 1
    return matches[0]


def test_edge_requires_min_completed_passes():
    assert PASS_EDGE_MIN == 3
    resp = build_pass_network_response(1, ROWS, PLAYERS_BY_ID)
    t = team(resp, 217)
    assert len(t["edges"]) == 1
    edge = t["edges"][0]
    # undirected: 3 passes 1->2 plus 1 pass 2->1 = 4 between the pair
    assert {edge["a"], edge["b"]} == {1, 2}
    assert edge["count"] == 4


def test_node_position_is_average_of_pass_involvements():
    resp = build_pass_network_response(1, ROWS, PLAYERS_BY_ID)
    t = team(resp, 217)

    # Player 1: origins (60,40),(62,42),(64,38),(50,20) + received end (60,40)
    # -> x = (60+62+64+50+60)/5 = 59.2, y = (40+42+38+20+40)/5 = 36.0
    n1 = node(t, 1)
    assert n1["x"] == pytest.approx(59.2)
    assert n1["y"] == pytest.approx(36.0)
    assert n1["name"] == "Passer One"

    # Player 3 only received once: end of 1->3 = (55,25)
    n3 = node(t, 3)
    assert n3["x"] == pytest.approx(55.0)
    assert n3["y"] == pytest.approx(25.0)


def test_node_passes_counts_own_completed_passes():
    resp = build_pass_network_response(1, ROWS, PLAYERS_BY_ID)
    t = team(resp, 217)
    assert node(t, 1)["passes"] == 4
    assert node(t, 2)["passes"] == 1
    assert node(t, 3)["passes"] == 0


def test_rows_without_recipient_are_ignored():
    rows = ROWS + [{
        "match_id": 1, "player_id": 1, "recipient_id": None, "team_id": 217,
        "event_type": "Pass", "outcome": "Incomplete",
        "x": 10.0, "y": 10.0, "end_x": 20.0, "end_y": 20.0, "minute": 5,
    }]
    resp = build_pass_network_response(1, rows, PLAYERS_BY_ID)
    t = team(resp, 217)
    # identical to the clean fixture: the incomplete pass changed nothing
    assert node(t, 1)["passes"] == 4
    assert node(t, 1)["x"] == pytest.approx(59.2)


def test_teams_split_and_empty_team_absent():
    resp = build_pass_network_response(1, ROWS, PLAYERS_BY_ID)
    assert [t["team_id"] for t in resp["teams"]] == [217]
    assert resp["match_id"] == 1
