"""Read-only endpoints over analytics_cache -- the results of the BigQuery
window-function queries in app/data/bigquery_analytics_v2.py. This router
never imports or calls BigQuery; it only reads the Postgres cache table
those queries were written into, so the request path stays fast and has no
GCP dependency at all.
"""

from fastapi import APIRouter, Depends

from app.auth import AuthenticatedUser, get_current_user
from app.data.bigquery_analytics_v2 import ROLLING_XG_TREND, SEASON_RANKINGS
from app.db import get_db

analytics_router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def build_analytics_response(cache_rows, query_name):
    """cache_rows: analytics_cache rows for one query_name, ordered newest
    first (computed_at desc), already limited to at most one row by the
    caller's query. Empty means the query hasn't been run yet -- not an
    error, just nothing cached.
    """
    if not cache_rows:
        return {"query_name": query_name, "computed_at": None, "data": []}
    row = cache_rows[0]
    return {
        "query_name": query_name,
        "computed_at": row["computed_at"],
        "data": row["payload"],
    }


def _latest_cache_rows(client, query_name):
    return client.table("analytics_cache").select("computed_at, payload").eq(
        "query_name", query_name
    ).order("computed_at", desc=True).limit(1).execute().data


@analytics_router.get("/rankings")
def get_rankings(_user: AuthenticatedUser = Depends(get_current_user), client=Depends(get_db)):
    rows = _latest_cache_rows(client, SEASON_RANKINGS)
    return build_analytics_response(rows, SEASON_RANKINGS)


@analytics_router.get("/trends")
def get_trends(_user: AuthenticatedUser = Depends(get_current_user), client=Depends(get_db)):
    rows = _latest_cache_rows(client, ROLLING_XG_TREND)
    return build_analytics_response(rows, ROLLING_XG_TREND)
