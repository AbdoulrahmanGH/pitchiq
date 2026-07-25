"""Tests for the JWT auth + role dependency (app/auth.py).

get_current_user and require_role() are plain functions whose Depends(...)
defaults are only resolved by FastAPI's DI at request time -- called
directly here with fake credentials/client, they run with no network.
"""

import pytest
from fastapi import HTTPException

from app.auth import AuthenticatedUser, _require_bearer_token, get_current_user, require_role
from tests.fakes_supabase import FakeClient, FakeCredentials, FakeUser

# ------------------------------- _require_bearer_token --------------------------------

def test_require_bearer_token_raises_401_when_credentials_missing():
    with pytest.raises(HTTPException) as exc_info:
        _require_bearer_token(credentials=None)

    assert exc_info.value.status_code == 401


def test_require_bearer_token_returns_token_string_when_present():
    result = _require_bearer_token(credentials=FakeCredentials("good-token"))

    assert result == "good-token"


# --------------------------------- get_current_user ---------------------------------

def test_invalid_token_raises_401():
    client = FakeClient(raise_on_get_user=True)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token="bad-token", client=client)

    assert exc_info.value.status_code == 401


def test_valid_token_returns_authenticated_user_with_role():
    user = FakeUser(id="user-1", email="analyst@example.com")
    client = FakeClient(user=user, roles_by_user_id={"user-1": "analyst"})

    result = get_current_user(token="good-token", client=client)

    assert isinstance(result, AuthenticatedUser)
    assert result.id == "user-1"
    assert result.email == "analyst@example.com"
    assert result.role == "analyst"


def test_valid_token_with_no_role_row_has_none_role():
    user = FakeUser(id="user-2", email="norole@example.com")
    client = FakeClient(user=user, roles_by_user_id={})

    result = get_current_user(token="good-token", client=client)

    assert result.role is None


# ------------------------------------ require_role -----------------------------------

def test_require_role_rejects_wrong_role():
    user = AuthenticatedUser(id="u", email="e", role="coach")
    dependency = require_role("analyst")

    with pytest.raises(HTTPException) as exc_info:
        dependency(user=user)

    assert exc_info.value.status_code == 403


def test_require_role_rejects_no_role():
    user = AuthenticatedUser(id="u", email="e", role=None)
    dependency = require_role("analyst")

    with pytest.raises(HTTPException) as exc_info:
        dependency(user=user)

    assert exc_info.value.status_code == 403


def test_require_role_accepts_matching_role():
    user = AuthenticatedUser(id="u", email="e", role="scout")
    dependency = require_role("scout")

    result = dependency(user=user)

    assert result is user
