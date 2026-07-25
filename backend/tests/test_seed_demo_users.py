"""Tests for the demo-user seed script's idempotency logic. Uses fake admin
and Supabase clients -- no real network calls, no real Auth Admin API.
"""

import pytest

from app.data.seed_demo_users import DEMO_USERS, _find_existing_user, ensure_role, ensure_user


class FakeCreatedUser:
    def __init__(self, id, email):
        self.id = id
        self.email = email


class FakeCreateUserResult:
    def __init__(self, user):
        self.user = user


class FakeAdminAPI:
    """Stateful: create_user() actually appends, so re-running ensure_user
    against the same instance is a real idempotency test, not just a mock
    call-count check."""

    def __init__(self, existing_users=None):
        self._users = list(existing_users or [])
        self.create_user_calls = []

    def list_users(self, page=1, per_page=50):
        start = (page - 1) * per_page
        return self._users[start:start + per_page]

    def create_user(self, attributes):
        self.create_user_calls.append(attributes)
        new_id = f"generated-{len(self._users) + 1}"
        user = FakeCreatedUser(id=new_id, email=attributes["email"])
        self._users.append(user)
        return FakeCreateUserResult(user)


class FakeAuth:
    def __init__(self, existing_users=None):
        self.admin = FakeAdminAPI(existing_users=existing_users)


class FakeAdminClient:
    def __init__(self, existing_users=None):
        self.auth = FakeAuth(existing_users=existing_users)


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeRolesTable:
    def __init__(self, store):
        self.store = store

    def upsert(self, record, on_conflict=None):
        assert on_conflict == "user_id"
        self.store[record["user_id"]] = record["role"]
        return self

    def execute(self):
        return FakeResult(None)


class FakeDbClient:
    def __init__(self):
        self.roles_by_user_id = {}

    def table(self, name):
        assert name == "user_roles"
        return FakeRolesTable(self.roles_by_user_id)


# ------------------------------ _find_existing_user ---------------------------

def test_find_existing_user_returns_none_when_no_users():
    admin = FakeAdminClient(existing_users=[])
    assert _find_existing_user(admin, "nobody@example.com") is None


def test_find_existing_user_finds_match_on_first_page():
    users = [FakeCreatedUser("id-1", "analyst@example.com")]
    admin = FakeAdminClient(existing_users=users)

    found = _find_existing_user(admin, "analyst@example.com")

    assert found.id == "id-1"


def test_find_existing_user_paginates_across_full_pages():
    # 3 full pages of unrelated users (per_page=2), target on page 3.
    users = [FakeCreatedUser(f"id-{i}", f"user{i}@example.com") for i in range(5)]
    users.append(FakeCreatedUser("target-id", "target@example.com"))
    admin = FakeAdminClient(existing_users=users)

    found = _find_existing_user(admin, "target@example.com", per_page=2)

    assert found.id == "target-id"


# ---------------------------------- ensure_user --------------------------------

def test_ensure_user_creates_when_not_exists():
    admin = FakeAdminClient(existing_users=[])

    user_id = ensure_user(admin, "coach@example.com", "Coach123!")

    assert len(admin.auth.admin.create_user_calls) == 1
    call = admin.auth.admin.create_user_calls[0]
    assert call["email"] == "coach@example.com"
    assert call["password"] == "Coach123!"
    assert call["email_confirm"] is True
    assert user_id is not None


def test_ensure_user_is_idempotent_on_rerun():
    admin = FakeAdminClient(existing_users=[])

    first_id = ensure_user(admin, "scout@example.com", "Scout123!")
    second_id = ensure_user(admin, "scout@example.com", "Scout123!")

    assert first_id == second_id
    assert len(admin.auth.admin.create_user_calls) == 1  # not created twice


# ---------------------------------- ensure_role ---------------------------------

def test_ensure_role_upserts_on_user_id_conflict():
    db = FakeDbClient()

    ensure_role(db, "user-1", "analyst")

    assert db.roles_by_user_id["user-1"] == "analyst"


def test_ensure_role_is_idempotent_on_rerun():
    db = FakeDbClient()

    ensure_role(db, "user-1", "analyst")
    ensure_role(db, "user-1", "analyst")

    assert db.roles_by_user_id == {"user-1": "analyst"}


# ------------------------------ demo account definitions ------------------------

def test_demo_users_match_the_three_required_accounts():
    by_email = {u["email"]: u for u in DEMO_USERS}
    assert by_email["analyst@example.com"]["role"] == "analyst"
    assert by_email["coach@example.com"]["role"] == "coach"
    assert by_email["scout@example.com"]["role"] == "scout"
    assert by_email["analyst@example.com"]["password"] == "Analyst123!"
    assert by_email["coach@example.com"]["password"] == "Coach123!"
    assert by_email["scout@example.com"]["password"] == "Scout123!"
