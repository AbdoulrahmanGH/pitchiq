"""Integration tests for GET /api/whoami through the real FastAPI app,
proving the auth dependency works through actual request handling (not just
direct function calls, which test_auth.py already covers).
"""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, get_current_user, require_role
from app.db import get_db
from app.main import app
from tests.fakes_supabase import FakeClient, FakeUser

client = TestClient(app)


def test_whoami_without_token_returns_401():
    app.dependency_overrides.clear()

    response = client.get("/api/whoami")

    assert response.status_code == 401


def test_whoami_without_token_never_touches_the_db_client():
    # A missing token must be rejected before any dependency tries to reach
    # Supabase at all -- otherwise a request with no token could 500 (real
    # bug: get_db() raises if SUPABASE_URL/KEY aren't configured, e.g. in a
    # CI environment with no secrets) instead of cleanly 401ing.
    def poisoned_get_db():
        raise AssertionError("get_db() should never be called for a missing token")

    app.dependency_overrides[get_db] = poisoned_get_db

    try:
        response = client.get("/api/whoami")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_whoami_with_valid_token_returns_id_and_role():
    fake_user = FakeUser(id="user-42", email="coach@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"user-42": "coach"}
    )

    try:
        response = client.get("/api/whoami", headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "user-42"
    assert body["role"] == "coach"


def test_whoami_with_invalid_token_returns_401():
    app.dependency_overrides[get_db] = lambda: FakeClient(raise_on_get_user=True)

    try:
        response = client.get("/api/whoami", headers={"Authorization": "Bearer bad-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


# ---- proving require_role's 403 behavior through real HTTP request handling ----
# (whoami itself accepts any authenticated user -- role gating is exercised via
# a throwaway route on a separate test-only app, not mounted on the real app)

role_test_app = FastAPI()


@role_test_app.get("/needs-analyst-role")
def _needs_analyst_role(user: AuthenticatedUser = Depends(require_role("analyst"))):
    return {"id": user.id, "role": user.role}


role_test_client = TestClient(role_test_app)


def test_route_requiring_specific_role_returns_403_for_wrong_role():
    fake_user = FakeUser(id="user-7", email="scout@example.com")
    role_test_app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"user-7": "scout"}
    )

    try:
        response = role_test_client.get(
            "/needs-analyst-role", headers={"Authorization": "Bearer good-token"}
        )
    finally:
        role_test_app.dependency_overrides.clear()

    assert response.status_code == 403


def test_route_requiring_specific_role_succeeds_for_matching_role():
    fake_user = FakeUser(id="user-8", email="analyst@example.com")
    role_test_app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"user-8": "analyst"}
    )

    try:
        response = role_test_client.get(
            "/needs-analyst-role", headers={"Authorization": "Bearer good-token"}
        )
    finally:
        role_test_app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["role"] == "analyst"
