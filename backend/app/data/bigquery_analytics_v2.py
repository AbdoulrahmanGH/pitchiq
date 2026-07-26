"""BigQuery analytics step for the v2 pipeline -- mirrors schema_v2's
Postgres tables into BigQuery, then runs the two window-function queries
v1 proved out (RANK() OVER season rankings; ROWS BETWEEN 2 PRECEDING AND
CURRENT ROW rolling trend), caching their results in Postgres so the API
never queries BigQuery on the request path.

Deliberately NOT wired into pipeline_v2.py's run() or the Cloud Run Job --
this is being proven standalone first, the same way pipeline_v2 itself was
proven locally (extract/transform/load run directly, output inspected)
before being automated. Invoke by hand:

    python -m app.data.bigquery_analytics_v2

v1's original queries (see README.md "BigQuery queries") ranked players by
distance_covered and tracked distance/sprint/xG trends -- schema_v2 has no
distance_covered or sprints (StatsBomb event data doesn't carry them), so
this adapts the same RANK()/ROWS BETWEEN techniques to real v2 metrics:
season goals and season xG (two separate rankings) for the first query,
rolling 3-match average xG for the second.

Mirror scope is intentionally just the three tables named in the task:
matches, player_match_stats, team_match_stats. Postgres stays the source
of truth for everything operational; this is a read-only analytical copy.
"""

import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from google.cloud import bigquery

from app.db import get_db

PROJECT = "pitchiq-494423"
DATASET = "pitchiq_analytics_v2_dev"

# Scoped to our own squad, same convention as matches.py/players.py/pipeline_v2.py.
BARCELONA_TEAM_ID = 217

MIRROR_TABLES = ("matches", "player_match_stats", "team_match_stats")
PAGE_SIZE = 500  # Postgrest's default max-rows cap is 1000; stay safely under it.

SEASON_RANKINGS = "season_rankings"
ROLLING_XG_TREND = "rolling_xg_trend"


# ------------------------------ mirror step ---------------------------------

def fetch_all_rows(supabase_client, table_name, page_size=PAGE_SIZE):
    """Paginated select("*") -- player_match_stats alone is 1000+ rows in
    the real dev dataset, past Postgrest's default per-request row cap.
    """
    rows = []
    offset = 0
    while True:
        page = supabase_client.table(table_name).select("*").range(
            offset, offset + page_size - 1
        ).execute().data
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def mirror_table_to_bigquery(bq_client, table_name, rows, project=PROJECT, dataset=DATASET):
    """WRITE_TRUNCATE load -- this is a mirror, not an incremental sync.
    Same pattern as v1's bigquery_load.py, retargeted to the v2 dataset.
    """
    table_ref = f"{project}.{dataset}.{table_name}"
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True,
    )
    job = bq_client.load_table_from_json(rows, table_ref, job_config=job_config)
    job.result()
    return bq_client.get_table(table_ref).num_rows


def mirror_to_bigquery(supabase_client=None, bq_client=None):
    """Mirrors matches/player_match_stats/team_match_stats from Postgres
    (the source of truth) into BigQuery. Returns row counts per table.
    """
    supabase_client = supabase_client or get_db()
    bq_client = bq_client or bigquery.Client(project=PROJECT)

    counts = {}
    for table_name in MIRROR_TABLES:
        rows = fetch_all_rows(supabase_client, table_name)
        if not rows:
            print(f"  {table_name}: no rows found, skipping")
            counts[table_name] = 0
            continue
        loaded = mirror_table_to_bigquery(bq_client, table_name, rows)
        print(f"  {table_name}: {loaded} rows mirrored")
        counts[table_name] = loaded
    return counts


# ------------------------------ analytics queries ----------------------------

def build_season_rankings_query(project=PROJECT, dataset=DATASET):
    """Two separate RANK() OVER rankings (goals, xG) -- not a combined
    score. No PARTITION BY: the appropriate partition here is already
    applied via the team_id filter (one team, one season in this dataset).
    """
    return f"""
    WITH season_totals AS (
      SELECT
        player_id,
        SUM(goals) AS season_goals,
        SUM(xg) AS season_xg
      FROM `{project}.{dataset}.player_match_stats`
      WHERE team_id = @team_id
      GROUP BY player_id
    )
    SELECT
      player_id,
      season_goals,
      season_xg,
      RANK() OVER (ORDER BY season_goals DESC) AS goals_rank,
      RANK() OVER (ORDER BY season_xg DESC) AS xg_rank
    FROM season_totals
    ORDER BY xg_rank
    """


def build_rolling_xg_trend_query(project=PROJECT, dataset=DATASET):
    """Rolling 3-match average xG per player, in match order -- v1's
    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW technique, applied to xG only
    (v1 also tracked distance/sprint here; schema_v2 has neither field).
    """
    return f"""
    WITH player_matches AS (
      SELECT
        pms.player_id,
        m.date AS match_date,
        pms.xg
      FROM `{project}.{dataset}.player_match_stats` pms
      JOIN `{project}.{dataset}.matches` m ON pms.match_id = m.id
      WHERE pms.team_id = @team_id
    )
    SELECT
      player_id,
      match_date,
      xg,
      AVG(xg) OVER (
        PARTITION BY player_id
        ORDER BY match_date
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
      ) AS rolling_3match_avg_xg
    FROM player_matches
    ORDER BY player_id, match_date
    """


def _json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _row_to_json_safe_dict(row):
    return {k: _json_safe(v) for k, v in row.items()}


def run_query(bq_client, sql, team_id):
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("team_id", "INT64", team_id)]
    )
    result = bq_client.query(sql, job_config=job_config).result()
    return [_row_to_json_safe_dict(row) for row in result]


# ------------------------------- caching -------------------------------------

def cache_result(supabase_client, query_name, payload):
    supabase_client.table("analytics_cache").insert({
        "query_name": query_name,
        "payload": payload,
    }).execute()


def run_analytics_and_cache(bq_client=None, supabase_client=None, team_id=BARCELONA_TEAM_ID):
    bq_client = bq_client or bigquery.Client(project=PROJECT)
    supabase_client = supabase_client or get_db()

    rankings = run_query(bq_client, build_season_rankings_query(), team_id)
    cache_result(supabase_client, SEASON_RANKINGS, rankings)
    print(f"  {SEASON_RANKINGS}: {len(rankings)} players cached")

    trend = run_query(bq_client, build_rolling_xg_trend_query(), team_id)
    cache_result(supabase_client, ROLLING_XG_TREND, trend)
    print(f"  {ROLLING_XG_TREND}: {len(trend)} rows cached")

    return {SEASON_RANKINGS: rankings, ROLLING_XG_TREND: trend}


# ----------------------------------- run ------------------------------------

def run():
    print("Mirroring Postgres -> BigQuery...")
    mirror_to_bigquery()

    print("\nRunning analytics queries against BigQuery and caching results...")
    run_analytics_and_cache()

    print("\nDone.")


if __name__ == "__main__":
    run()
