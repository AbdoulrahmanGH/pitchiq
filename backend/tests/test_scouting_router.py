"""Tests for GET/POST /api/scouting/notes -- Scout writes, Analyst/Scout
read, Coach is blocked from writing (403). No access-control check is
needed on GET beyond "authenticated" (any role can read); hiding the
section from Coach entirely is a frontend concern, not a backend 403.
"""

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from tests.fakes_supabase import FakeClient, FakeUser

client = TestClient(app)


def test_post_scouting_note_as_coach_returns_403():
    fake_user = FakeUser(id="coach-1", email="coach@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"coach-1": "coach"}
    )
    try:
        response = client.post(
            "/api/scouting/notes",
            json={"player_id": 5503, "note": "Good pace", "rating": 4},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_post_scouting_note_as_scout_succeeds():
    fake_user = FakeUser(id="scout-1", email="scout@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"scout-1": "scout"}, scouting_notes=[]
    )
    try:
        response = client.post(
            "/api/scouting/notes",
            json={"player_id": 5503, "note": "Good pace, needs work off the ball", "rating": 4},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["player_id"] == 5503
    assert body["rating"] == 4
    assert body["author_id"] == "scout-1"


def test_post_scouting_note_rejects_rating_out_of_range():
    fake_user = FakeUser(id="scout-1", email="scout@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"scout-1": "scout"}, scouting_notes=[]
    )
    try:
        response = client.post(
            "/api/scouting/notes",
            json={"player_id": 5503, "note": "Note", "rating": 7},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_get_scouting_notes_as_analyst_returns_notes_for_that_player_only():
    existing = [
        {"id": 1, "player_id": 5503, "author_id": "scout-1", "note": "Sharp finishing",
         "rating": 5, "created_at": "2026-07-20T00:00:00Z"},
        {"id": 2, "player_id": 9999, "author_id": "scout-1", "note": "Different player",
         "rating": 3, "created_at": "2026-07-20T00:00:00Z"},
    ]
    fake_user = FakeUser(id="analyst-1", email="analyst@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"analyst-1": "analyst"}, scouting_notes=existing
    )
    try:
        response = client.get(
            "/api/scouting/notes", params={"player_id": 5503},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["note"] == "Sharp finishing"


def test_get_scouting_notes_requires_auth():
    app.dependency_overrides.clear()
    response = client.get("/api/scouting/notes", params={"player_id": 5503})
    assert response.status_code == 401
