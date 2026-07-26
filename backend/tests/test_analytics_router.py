"""Tests for GET /api/analytics/rankings and /api/analytics/trends.

Both endpoints only ever read the analytics_cache table -- they must never
touch BigQuery on the request path (that's the whole point of caching the
query results in Postgres). test_analytics_endpoints_never_touch_bigquery
proves this with a mock, not just by inspecting the router's imports.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.data.bigquery_analytics_v2 import ROLLING_XG_TREND, SEASON_RANKINGS
from app.db import get_db
from app.main import app
from app.routers.analytics import build_analytics_response
from tests.fakes_supabase import FakeClient, FakeUser

client = TestClient(app)


# --------------------------- build_analytics_response ---------------------------

def test_build_analytics_response_empty_cache_returns_empty_data():
    result = build_analytics_response([], SEASON_RANKINGS)

    assert result == {"query_name": SEASON_RANKINGS, "computed_at": None, "data": []}


def test_build_analytics_response_returns_latest_row_payload():
    cache_rows = [
        {"computed_at": "2026-07-26T12:00:00Z", "payload": [{"player_id": 5246, "xg_rank": 1}]},
    ]

    result = build_analytics_response(cache_rows, SEASON_RANKINGS)

    assert result["query_name"] == SEASON_RANKINGS
    assert result["computed_at"] == "2026-07-26T12:00:00Z"
    assert result["data"] == [{"player_id": 5246, "xg_rank": 1}]


# --------------------------------- endpoints ---------------------------------

FAKE_USER = FakeUser(id="user-1", email="analyst@example.com")


def _override_get_db(fake_client):
    app.dependency_overrides[get_db] = lambda: fake_client


def test_rankings_requires_auth():
    app.dependency_overrides.clear()

    response = client.get("/api/analytics/rankings")

    assert response.status_code == 401


def test_trends_requires_auth():
    app.dependency_overrides.clear()

    response = client.get("/api/analytics/trends")

    assert response.status_code == 401


def test_rankings_returns_latest_cached_payload():
    fake = FakeClient(
        user=FAKE_USER,
        roles_by_user_id={"user-1": "analyst"},
        analytics_cache_rows={
            SEASON_RANKINGS: [
                {"computed_at": "2026-07-26T12:00:00Z",
                 "payload": [{"player_id": 5246, "season_goals": 40, "goals_rank": 1,
                              "season_xg": 27.65, "xg_rank": 1}]},
            ],
        },
    )
    _override_get_db(fake)

    try:
        response = client.get("/api/analytics/rankings",
                              headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["query_name"] == SEASON_RANKINGS
    assert body["data"] == [{"player_id": 5246, "season_goals": 40, "goals_rank": 1,
                             "season_xg": 27.65, "xg_rank": 1}]


def test_trends_returns_latest_cached_payload():
    fake = FakeClient(
        user=FAKE_USER,
        roles_by_user_id={"user-1": "analyst"},
        analytics_cache_rows={
            ROLLING_XG_TREND: [
                {"computed_at": "2026-07-26T12:00:00Z",
                 "payload": [{"player_id": 5246, "match_date": "2015-08-23",
                              "xg": 0.03, "rolling_3match_avg_xg": 0.03}]},
            ],
        },
    )
    _override_get_db(fake)

    try:
        response = client.get("/api/analytics/trends",
                              headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["query_name"] == ROLLING_XG_TREND
    assert len(body["data"]) == 1
    assert body["data"][0]["player_id"] == 5246


def test_rankings_returns_empty_when_cache_not_yet_populated():
    fake = FakeClient(user=FAKE_USER, roles_by_user_id={"user-1": "analyst"})
    _override_get_db(fake)

    try:
        response = client.get("/api/analytics/rankings",
                              headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_analytics_endpoints_never_touch_bigquery():
    fake = FakeClient(
        user=FAKE_USER,
        roles_by_user_id={"user-1": "analyst"},
        analytics_cache_rows={
            SEASON_RANKINGS: [{"computed_at": "2026-07-26T12:00:00Z", "payload": []}],
            ROLLING_XG_TREND: [{"computed_at": "2026-07-26T12:00:00Z", "payload": []}],
        },
    )
    _override_get_db(fake)

    try:
        with patch("google.cloud.bigquery.Client") as mock_bq_client:
            rankings_response = client.get("/api/analytics/rankings",
                                           headers={"Authorization": "Bearer good-token"})
            trends_response = client.get("/api/analytics/trends",
                                        headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert rankings_response.status_code == 200
    assert trends_response.status_code == 200
    mock_bq_client.assert_not_called()
