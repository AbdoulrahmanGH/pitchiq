"""Tests for the shared fatigue-risk logic used by both /players/fatigue-risk
and /team/readiness.

Fixtures are 5 hand-built matches for one team, spaced to hit every branch of
the combined rule (MIA's documented rule, not invented numbers):
  at_risk = rest_days_since_last_match < short_rest_days (3)
            AND minutes across the team's last 3 fixtures >= high_minutes (180)

M1 2015-08-01, M2 2015-08-05 (+4d), M3 2015-08-07 (+2d), M4 2015-08-10 (+3d),
M5 2015-08-12 (+2d). Team's last 3 fixtures = M3, M4, M5.
"""

import pytest

from app.services.fatigue import compute_at_risk_players

TEAM_MATCHES = [
    {"id": 1, "date": "2015-08-01"},
    {"id": 2, "date": "2015-08-05"},
    {"id": 3, "date": "2015-08-07"},
    {"id": 4, "date": "2015-08-10"},
    {"id": 5, "date": "2015-08-12"},
]

SHORT_REST_DAYS = 3
HIGH_MINUTES = 180


def pms(match_id, player_id, minutes, name="Player", nickname=None):
    return {"match_id": match_id, "player_id": player_id,
           "minutes_played": minutes, "name": name, "nickname": nickname}


def test_short_rest_and_high_workload_together_flags_at_risk():
    # Player A: plays every match 90 mins. Rest before M5 = 2 days (< 3).
    # Minutes across M3+M4+M5 = 270 (>= 180).
    rows = [pms(m["id"], "A", 90) for m in TEAM_MATCHES]

    at_risk = compute_at_risk_players(TEAM_MATCHES, rows, SHORT_REST_DAYS, HIGH_MINUTES)

    assert len(at_risk) == 1
    assert at_risk[0]["player_id"] == "A"
    assert at_risk[0]["rest_days"] == 2
    assert at_risk[0]["recent_minutes"] == 270


def test_adequate_rest_is_not_at_risk_even_with_high_workload():
    # Player B: plays M1 and M2 only. Rest before their last appearance
    # (M2) = 4 days (not < 3) -- never plays again, so no false positive.
    rows = [pms(1, "B", 90), pms(2, "B", 90)]

    at_risk = compute_at_risk_players(TEAM_MATCHES, rows, SHORT_REST_DAYS, HIGH_MINUTES)

    assert at_risk == []


def test_missed_fixtures_count_as_zero_minutes_in_the_window():
    # Player C: plays M4 and M5 only (misses M3). Rest before M5 = 2 days
    # (< 3). Minutes across M3(0)+M4(90)+M5(90) = 180 -- boundary, >= counts.
    rows = [pms(4, "C", 90), pms(5, "C", 90)]

    at_risk = compute_at_risk_players(TEAM_MATCHES, rows, SHORT_REST_DAYS, HIGH_MINUTES)

    assert len(at_risk) == 1
    assert at_risk[0]["player_id"] == "C"
    assert at_risk[0]["recent_minutes"] == 180


def test_single_appearance_has_no_rest_days_and_is_not_at_risk():
    # Player D: only ever appears in M3. No previous match to measure rest
    # against -- must not be flagged on undefined rest.
    rows = [pms(3, "D", 60)]

    at_risk = compute_at_risk_players(TEAM_MATCHES, rows, SHORT_REST_DAYS, HIGH_MINUTES)

    assert at_risk == []


def test_long_gap_between_appearances_is_not_short_rest():
    # Player E: plays M1, M3, M5 (skips M2, M4). Rest before M5 = 5 days.
    rows = [pms(1, "E", 90), pms(3, "E", 90), pms(5, "E", 90)]

    at_risk = compute_at_risk_players(TEAM_MATCHES, rows, SHORT_REST_DAYS, HIGH_MINUTES)

    assert at_risk == []


def test_at_risk_row_includes_player_name_and_nickname():
    rows = [pms(m["id"], "A", 90, name="Lionel Messi", nickname="Leo") for m in TEAM_MATCHES]

    at_risk = compute_at_risk_players(TEAM_MATCHES, rows, SHORT_REST_DAYS, HIGH_MINUTES)

    assert at_risk[0]["name"] == "Lionel Messi"
    assert at_risk[0]["nickname"] == "Leo"


def test_no_matches_returns_empty():
    assert compute_at_risk_players([], [], SHORT_REST_DAYS, HIGH_MINUTES) == []


def test_fewer_than_three_matches_uses_available_fixtures():
    # Season has only played 2 matches so far -- use both, don't pad or error.
    two_matches = TEAM_MATCHES[:2]
    rows = [pms(1, "A", 90), pms(2, "A", 100)]

    at_risk = compute_at_risk_players(two_matches, rows, SHORT_REST_DAYS, HIGH_MINUTES)

    # rest before M2 = 4 days -- not short, so not at risk, but this must not
    # raise even though there's no 3rd fixture to look back at.
    assert at_risk == []
