"""Tests for GET /api/pipeline/status and POST /api/pipeline/refresh --
both Analyst-only (require_role, not just nav hiding), same pattern as
anything else Coach/Scout shouldn't reach.

The Cloud Run Job calls (list_recent_executions, trigger_pipeline_run) are
always mocked here -- these tests must never trigger a real pipeline run
or hit the real Cloud Run Admin API.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.routers.pipeline import build_pipeline_status_response
from tests.fakes_supabase import FakeAuth, FakeResult, FakeRolesTable, FakeUser

client = TestClient(app)


# ------------------------------ pure response shape ------------------------------

def test_build_status_response_empty_tables_returns_none_timestamps():
    result = build_pipeline_status_response([], [], recent_runs=[])

    assert result == {
        "current_data_updated_at": None,
        "analytics_warehouse_updated_at": None,
        "recent_runs": [],
    }


def test_build_status_response_uses_first_row_of_each_table():
    current_data_rows = [{"loaded_at": "2026-07-26T13:38:22Z"}]
    analytics_cache_rows = [{"computed_at": "2026-07-26T11:17:39Z"}]
    recent_runs = [{"id": "pitchiq-pipeline-v2-6m55l", "status": "succeeded"}]

    result = build_pipeline_status_response(current_data_rows, analytics_cache_rows, recent_runs)

    assert result["current_data_updated_at"] == "2026-07-26T13:38:22Z"
    assert result["analytics_warehouse_updated_at"] == "2026-07-26T11:17:39Z"
    assert result["recent_runs"] == recent_runs


# --------------------------------- fakes / setup ---------------------------------

class FakeOrderedTable:
    """select().order().limit().execute() with no real filtering -- the
    caller supplies rows already in the shape/order the real query would
    return. Same "good enough for pure logic" convention as the other
    local fakes in this test suite (test_quality_checks.py,
    test_load_v2.py each define their own).
    """
    def __init__(self, rows):
        self._rows = rows
        self._limit = None

    def select(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        rows = self._rows[:self._limit] if self._limit is not None else self._rows
        return FakeResult(rows)


class FakeClient:
    def __init__(self, user=None, roles_by_user_id=None,
                 player_match_stats_rows=None, analytics_cache_rows=None):
        self.auth = FakeAuth(user=user)
        self._roles_by_user_id = roles_by_user_id or {}
        self._player_match_stats_rows = player_match_stats_rows or []
        self._analytics_cache_rows = analytics_cache_rows or []

    def table(self, name):
        if name == "user_roles":
            return FakeRolesTable(self._roles_by_user_id)
        if name == "player_match_stats":
            return FakeOrderedTable(self._player_match_stats_rows)
        if name == "analytics_cache":
            return FakeOrderedTable(self._analytics_cache_rows)
        raise AssertionError(f"FakeClient.table() called with unexpected table: {name}")


ANALYST = FakeUser(id="user-1", email="analyst@example.com")
COACH = FakeUser(id="user-2", email="coach@example.com")


def _override_get_db(fake_client):
    app.dependency_overrides[get_db] = lambda: fake_client


# ------------------------------------ auth ---------------------------------------

def test_status_requires_auth():
    app.dependency_overrides.clear()

    response = client.get("/api/pipeline/status")

    assert response.status_code == 401


def test_refresh_requires_auth():
    app.dependency_overrides.clear()

    response = client.post("/api/pipeline/refresh")

    assert response.status_code == 401


def test_status_returns_403_for_non_analyst_role():
    _override_get_db(FakeClient(user=COACH, roles_by_user_id={"user-2": "coach"}))

    try:
        response = client.get("/api/pipeline/status",
                              headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_refresh_returns_403_for_non_analyst_role():
    _override_get_db(FakeClient(user=COACH, roles_by_user_id={"user-2": "coach"}))

    try:
        with patch("app.routers.pipeline.trigger_pipeline_run") as mock_trigger:
            response = client.post("/api/pipeline/refresh",
                                   headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    mock_trigger.assert_not_called()


# -------------------------------- status endpoint ---------------------------------

def test_status_returns_real_shape_for_analyst():
    fake = FakeClient(
        user=ANALYST,
        roles_by_user_id={"user-1": "analyst"},
        player_match_stats_rows=[{"loaded_at": "2026-07-26T13:38:22Z"}],
        analytics_cache_rows=[{"computed_at": "2026-07-26T11:17:39Z"}],
    )
    _override_get_db(fake)

    fake_runs = [{"id": "pitchiq-pipeline-v2-6m55l", "status": "succeeded",
                  "duration_seconds": 128.3}]

    try:
        with patch("app.routers.pipeline.list_recent_executions", return_value=fake_runs) as mock_list:
            response = client.get("/api/pipeline/status",
                                  headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["current_data_updated_at"] == "2026-07-26T13:38:22Z"
    assert body["analytics_warehouse_updated_at"] == "2026-07-26T11:17:39Z"
    assert body["recent_runs"] == fake_runs
    mock_list.assert_called_once()


def test_status_never_touches_bigquery_or_cloud_run_client_directly():
    fake = FakeClient(user=ANALYST, roles_by_user_id={"user-1": "analyst"})
    _override_get_db(fake)

    try:
        with patch("google.cloud.run_v2.ExecutionsClient") as mock_ex_client, \
             patch("app.routers.pipeline.list_recent_executions", return_value=[]):
            response = client.get("/api/pipeline/status",
                                  headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    mock_ex_client.assert_not_called()


# -------------------------------- refresh endpoint ---------------------------------

def test_refresh_triggers_the_real_job_function_and_returns_immediately():
    fake = FakeClient(user=ANALYST, roles_by_user_id={"user-1": "analyst"})
    _override_get_db(fake)

    try:
        with patch("app.routers.pipeline.trigger_pipeline_run") as mock_trigger:
            response = client.post("/api/pipeline/refresh",
                                   headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "triggered"}
    mock_trigger.assert_called_once()
