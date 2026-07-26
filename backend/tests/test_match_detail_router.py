"""Integration tests for GET /api/matches/{match_id}/detail through the real
FastAPI app against the real pitchiq-v2-dev project -- same pattern as
test_role_gating.py, skipped if Supabase isn't configured. Covers the 404
case for an invalid match_id (unit-testable business logic lives in
build_match_detail_response, see test_matches_router.py) and the real,
authenticated 200 case with actual lineup/goals/assists data.
"""

import pytest
from fastapi.testclient import TestClient
from supabase import create_client

from app.config import SUPABASE_KEY, SUPABASE_URL
from app.main import app

pytestmark = pytest.mark.skipif(
    not SUPABASE_URL or not SUPABASE_KEY,
    reason="SUPABASE_URL/SUPABASE_KEY not configured",
)

ANON_KEY = "sb_publishable_QgX_qUdGGp05HNRkgKV9ww_jDz90TdS"
ANALYST = ("analyst@example.com", "Analyst123!")

client = TestClient(app)


@pytest.fixture(scope="module")
def analyst_token():
    anon = create_client(SUPABASE_URL, ANON_KEY)
    email, password = ANALYST
    res = anon.auth.sign_in_with_password({"email": email, "password": password})
    return res.session.access_token


def test_match_detail_requires_auth():
    response = client.get("/api/matches/266236/detail")
    assert response.status_code == 401


def test_match_detail_returns_404_for_invalid_match_id(analyst_token):
    response = client.get(
        "/api/matches/999999999/detail",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert response.status_code == 404


def test_match_detail_returns_real_lineup_for_a_real_match(analyst_token):
    # A handful of matches in the live dataset have no player_match_stats
    # rows at all (a pre-existing pipeline load gap, unrelated to this
    # endpoint -- see CODEBASE_AUDIT.md). Scan for a match that actually has
    # data rather than assuming matches[0] does, so this test verifies the
    # endpoint's real behavior and isn't coupled to that gap.
    headers = {"Authorization": f"Bearer {analyst_token}"}

    summary = client.get("/api/matches/summary", headers=headers)
    assert summary.status_code == 200
    matches = summary.json()
    assert len(matches) > 0

    body = None
    for m in matches:
        response = client.get(f"/api/matches/{m['id']}/detail", headers=headers)
        assert response.status_code == 200
        candidate = response.json()
        if candidate["home_team"]["lineup"] and candidate["away_team"]["lineup"]:
            body = candidate
            break
    assert body is not None, "expected at least one match with real lineup data"

    for side in ("home_team", "away_team"):
        assert body[side]["name"]
        assert isinstance(body[side]["lineup"], list)
        assert len(body[side]["lineup"]) > 0
        for player in body[side]["lineup"]:
            assert player["name"]
            assert isinstance(player["goals"], int)
            assert isinstance(player["assists"], int)


def test_match_detail_shots_include_known_suarez_goal(analyst_token):
    # Athletic Club 0-1 Barcelona, 2015-08-23: the only goal is Luis Suarez
    # in the 54th minute (StatsBomb minute=53, 0-indexed). Raw StatsBomb shot
    # coordinates are in the shooter's own attacking frame (toward x=120), so
    # this goal must sit close to x=120 in the raw data even though Barcelona
    # were the away team -- the frontend mirrors away shots for display.
    response = client.get(
        "/api/matches/266236/detail",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert response.status_code == 200
    body = response.json()

    shots = body["shots"]
    assert len(shots) > 0
    goals = [s for s in shots if s["outcome"] == "Goal"]
    assert len(goals) == 1
    goal = goals[0]
    assert goal["minute"] == 53
    assert goal["team_id"] == body["away_team"]["id"]  # Barcelona
    assert "Su" in goal["player_name"]  # Luis Suarez (accented in the data)
    assert goal["x"] > 100  # own attacking frame: near the goal at x=120
    assert goal["xg"] > 0
    # every shot in the match, both teams, is in its own attacking frame
    assert all(s["x"] > 60 for s in shots)
