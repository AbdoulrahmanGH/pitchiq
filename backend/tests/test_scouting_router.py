"""Tests for GET/POST /api/scouting/notes -- Scout writes, Analyst/Scout
read, Coach is blocked from writing (403). No access-control check is
needed on GET beyond "authenticated" (any role can read); hiding the
section from Coach entirely is a frontend concern, not a backend 403.
"""

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.routers.scouting import build_notes_response
from tests.fakes_supabase import FakeClient, FakeUser

client = TestClient(app)


def test_build_notes_response_attaches_player_name_and_team():
    notes = [{"id": 1, "player_id": 5503, "author_id": "scout-1",
              "note": "Sharp finishing", "rating": 5, "created_at": "2026-07-20T00:00:00Z"}]
    players_by_id = {5503: {"name": "Lionel Messi", "nickname": "Messi", "team_id": 217}}
    teams_by_id = {217: "Barcelona"}

    result = build_notes_response(notes, players_by_id, teams_by_id)

    assert result[0]["player_name"] == "Lionel Messi"
    assert result[0]["player_nickname"] == "Messi"
    assert result[0]["team_name"] == "Barcelona"
    assert result[0]["note"] == "Sharp finishing"


def test_build_notes_response_handles_unknown_player():
    notes = [{"id": 1, "player_id": 42, "author_id": "scout-1",
              "note": "Note", "rating": 3, "created_at": "2026-07-20T00:00:00Z"}]

    result = build_notes_response(notes, {}, {})

    assert result[0]["player_name"] is None
    assert result[0]["player_nickname"] is None
    assert result[0]["team_name"] is None


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


# --------------------- "My Scouting Notes" (no player_id) ---------------------

def test_get_scouting_notes_without_player_id_returns_only_the_callers_own_notes():
    existing = [
        {"id": 1, "player_id": 5503, "author_id": "scout-1", "note": "By scout-1",
         "rating": 5, "created_at": "2026-07-20T00:00:00Z"},
        {"id": 2, "player_id": 9999, "author_id": "scout-2", "note": "By scout-2",
         "rating": 3, "created_at": "2026-07-20T00:00:00Z"},
    ]
    fake_user = FakeUser(id="scout-1", email="scout@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"scout-1": "scout"}, scouting_notes=existing
    )
    try:
        response = client.get("/api/scouting/notes", headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["note"] == "By scout-1"


def test_get_scouting_notes_without_player_id_and_no_notes_returns_empty_list():
    fake_user = FakeUser(id="scout-3", email="scout3@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"scout-3": "scout"}, scouting_notes=[]
    )
    try:
        response = client.get("/api/scouting/notes", headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []


def test_get_scouting_notes_enriches_with_player_name_and_team():
    existing = [
        {"id": 1, "player_id": 5503, "author_id": "scout-1", "note": "Sharp finishing",
         "rating": 5, "created_at": "2026-07-20T00:00:00Z"},
    ]
    players_rows = [{"id": 5503, "name": "Lionel Messi", "nickname": "Messi"}]
    player_match_stats_rows = [{"player_id": 5503, "team_id": 217}]
    teams_rows = [{"id": 217, "name": "Barcelona"}]
    fake_user = FakeUser(id="scout-1", email="scout@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"scout-1": "scout"}, scouting_notes=existing,
        players_rows=players_rows, player_match_stats_rows=player_match_stats_rows,
        teams_rows=teams_rows,
    )
    try:
        response = client.get("/api/scouting/notes", headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body[0]["player_name"] == "Lionel Messi"
    assert body[0]["player_nickname"] == "Messi"
    assert body[0]["team_name"] == "Barcelona"
