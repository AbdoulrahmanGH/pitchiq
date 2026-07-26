"""Pipeline Visibility endpoints -- Analyst-only, same role-gating pattern
as anything else Coach/Scout shouldn't see (require_role, not just nav
hiding on the frontend).

GET /status backs the dual freshness clock and run history: "current data"
freshness comes from MAX(player_match_stats.loaded_at) (Postgres, refreshed
by every real pipeline run's full delete-then-reinsert -- see schema_v2.sql
and load_v2.reload_table_for_matches), "analytics warehouse" freshness
comes from MAX(analytics_cache.computed_at) (already existed for the
analytics endpoints). Run history comes straight from the Cloud Run Admin
API via app.services.cloud_run_jobs -- no local run-tracking table.

POST /refresh triggers the real Cloud Run Job and returns immediately
without waiting for it to finish; the frontend polls GET /status to watch
the new execution progress.
"""

from fastapi import APIRouter, Depends

from app.auth import AuthenticatedUser, require_role
from app.db import get_db
from app.services.cloud_run_jobs import list_recent_executions, trigger_pipeline_run

pipeline_router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


def build_pipeline_status_response(current_data_rows, analytics_cache_rows, recent_runs):
    """current_data_rows: player_match_stats rows selected as
    [{"loaded_at": ...}], newest first, limited to 1 by the caller's query.
    analytics_cache_rows: same shape for analytics_cache.computed_at.
    Either being empty means that table has no rows yet -- not an error.
    """
    return {
        "current_data_updated_at": current_data_rows[0]["loaded_at"] if current_data_rows else None,
        "analytics_warehouse_updated_at": (
            analytics_cache_rows[0]["computed_at"] if analytics_cache_rows else None
        ),
        "recent_runs": recent_runs,
    }


@pipeline_router.get("/status")
def get_pipeline_status(
    _user: AuthenticatedUser = Depends(require_role("analyst")),
    client=Depends(get_db),
):
    current_data_rows = client.table("player_match_stats").select("loaded_at").order(
        "loaded_at", desc=True
    ).limit(1).execute().data

    analytics_cache_rows = client.table("analytics_cache").select("computed_at").order(
        "computed_at", desc=True
    ).limit(1).execute().data

    recent_runs = list_recent_executions()

    return build_pipeline_status_response(current_data_rows, analytics_cache_rows, recent_runs)


@pipeline_router.post("/refresh")
def refresh_pipeline(_user: AuthenticatedUser = Depends(require_role("analyst"))):
    trigger_pipeline_run()
    return {"status": "triggered"}
