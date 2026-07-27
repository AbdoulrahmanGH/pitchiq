"""Tests for POST /api/ai/ask -- auth gating and response wiring. The
routing/Groq logic itself is tested in test_ai_service.py; here
answer_question is mocked so this test only proves the endpoint's plumbing.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from tests.fakes_supabase import FakeClient, FakeUser

client = TestClient(app)


def test_ask_requires_auth():
    app.dependency_overrides.clear()

    response = client.post("/api/ai/ask", json={"question": "Is the squad ready?"})

    assert response.status_code == 401


def test_ask_returns_answer_for_any_authenticated_role():
    fake_user = FakeUser(id="scout-1", email="scout@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"scout-1": "scout"}
    )

    try:
        with patch("app.routers.ai.answer_question", return_value="Squad readiness is 90/100."):
            response = client.post(
                "/api/ai/ask",
                json={"question": "Is the squad ready?"},
                headers={"Authorization": "Bearer good-token"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"answer": "Squad readiness is 90/100."}


def test_ask_rejects_empty_question():
    fake_user = FakeUser(id="coach-1", email="coach@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"coach-1": "coach"}
    )

    try:
        response = client.post(
            "/api/ai/ask",
            json={"question": ""},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
