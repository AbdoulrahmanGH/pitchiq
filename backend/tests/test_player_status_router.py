"""Tests for GET/POST /api/players/status -- Coach writes (sets a player's
current availability), any authenticated role reads. Analyst and Scout must
both be blocked from writing (403).
"""

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from tests.fakes_supabase import FakeClient, FakeUser

client = TestClient(app)


def test_post_player_status_as_analyst_returns_403():
    fake_user = FakeUser(id="analyst-1", email="analyst@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"analyst-1": "analyst"}
    )
    try:
        response = client.post(
            "/api/players/status",
            json={"player_id": 5503, "status": "doubtful"},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_post_player_status_as_scout_returns_403():
    fake_user = FakeUser(id="scout-1", email="scout@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"scout-1": "scout"}
    )
    try:
        response = client.post(
            "/api/players/status",
            json={"player_id": 5503, "status": "unavailable"},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_post_player_status_as_coach_succeeds():
    fake_user = FakeUser(id="coach-1", email="coach@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"coach-1": "coach"}, player_statuses=[]
    )
    try:
        response = client.post(
            "/api/players/status",
            json={"player_id": 5503, "status": "doubtful", "note": "Tight hamstring"},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["player_id"] == 5503
    assert body["status"] == "doubtful"
    assert body["updated_by"] == "coach-1"


def test_post_player_status_rejects_invalid_status_value():
    fake_user = FakeUser(id="coach-1", email="coach@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"coach-1": "coach"}, player_statuses=[]
    )
    try:
        response = client.post(
            "/api/players/status",
            json={"player_id": 5503, "status": "injured"},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_get_player_statuses_attaches_names_and_defaults_missing_players_to_available():
    # A player nobody has ever flagged still needs to show up (as
    # "available", the implicit default) with their real name attached --
    # not silently omitted, and never just a bare player_id.
    players_rows = [
        {"id": 5503, "name": "Lionel Messi", "nickname": "Messi", "primary_position": "Right Wing"},
        {"id": 9999, "name": "Backup Keeper", "nickname": None, "primary_position": "Goalkeeper"},
    ]
    player_match_stats_rows = [
        {"player_id": 5503, "team_id": 217},
        {"player_id": 9999, "team_id": 217},
    ]
    existing = [{"player_id": 5503, "status": "doubtful", "note": "Tight hamstring",
                 "updated_by": "coach-1", "updated_at": "2026-07-26T00:00:00Z"}]
    fake_user = FakeUser(id="scout-1", email="scout@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"scout-1": "scout"}, player_statuses=existing,
        players_rows=players_rows, player_match_stats_rows=player_match_stats_rows,
    )
    try:
        response = client.get("/api/players/status", headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    by_id = {row["player_id"]: row for row in body}
    assert by_id[5503]["status"] == "doubtful"
    assert by_id[5503]["name"] == "Lionel Messi"
    assert by_id[9999]["status"] == "available"
    assert by_id[9999]["name"] == "Backup Keeper"
    assert by_id[9999]["note"] is None
    assert by_id[9999]["updated_by"] is None


def test_get_player_statuses_requires_auth():
    app.dependency_overrides.clear()
    response = client.get("/api/players/status")
    assert response.status_code == 401
