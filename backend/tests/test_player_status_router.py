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


def test_get_player_statuses_returns_all_rows_for_any_authenticated_role():
    existing = [{"player_id": 5503, "status": "doubtful", "note": None,
                 "updated_by": "coach-1", "updated_at": "2026-07-26T00:00:00Z"}]
    fake_user = FakeUser(id="scout-1", email="scout@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"scout-1": "scout"}, player_statuses=existing
    )
    try:
        response = client.get("/api/players/status", headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == existing


def test_get_player_statuses_requires_auth():
    app.dependency_overrides.clear()
    response = client.get("/api/players/status")
    assert response.status_code == 401
