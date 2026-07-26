"""Unit tests for the pure logic in app.data.bigquery_analytics_v2: the
SQL-building functions and the pagination/row-shaping helpers. No network,
no real BigQuery or Supabase calls.

The BigQuery query logic itself (does RANK() actually rank correctly, does
the rolling window actually average the right 3 matches) is verified
separately by running it for real against the mirrored dev data -- see the
commit message / manual verification, not a test here. These tests only
prove the query *text* is well-formed and adapted to v2's real schema
(goals/xg, not v1's distance_covered/sprints).
"""

from datetime import date
from types import SimpleNamespace

from app.data.bigquery_analytics_v2 import (
    PAGE_SIZE,
    _json_safe,
    _row_to_json_safe_dict,
    build_rolling_xg_trend_query,
    build_season_rankings_query,
    fetch_all_rows,
)


# ----------------------------- query text shape -----------------------------

def test_season_rankings_query_ranks_by_goals_and_xg_separately():
    sql = build_season_rankings_query("proj", "ds")

    assert sql.count("RANK() OVER") == 2
    assert "ORDER BY season_goals DESC" in sql
    assert "ORDER BY season_xg DESC" in sql
    assert "goals_rank" in sql
    assert "xg_rank" in sql
    # not a single combined score
    assert "goals_rank + xg_rank" not in sql and "xg_rank + goals_rank" not in sql


def test_season_rankings_query_targets_v2_schema_not_v1_fields():
    sql = build_season_rankings_query("proj", "ds")

    assert "distance_covered" not in sql
    assert "sprints" not in sql
    assert "`proj.ds.player_match_stats`" in sql
    assert "@team_id" in sql


def test_rolling_xg_trend_query_uses_v1s_window_technique_on_xg_only():
    sql = build_rolling_xg_trend_query("proj", "ds")

    assert "ROWS BETWEEN 2 PRECEDING AND CURRENT ROW" in sql
    assert "PARTITION BY player_id" in sql
    assert "AVG(xg)" in sql
    assert "distance_covered" not in sql
    assert "sprints" not in sql


def test_rolling_xg_trend_query_joins_matches_for_date_ordering():
    sql = build_rolling_xg_trend_query("proj", "ds")

    assert "`proj.ds.matches`" in sql
    assert "ORDER BY match_date" in sql
    assert "@team_id" in sql


# -------------------------------- pagination ---------------------------------

class FakePaginatedTable:
    def __init__(self, all_rows):
        self._all_rows = all_rows
        self._start = None
        self._end = None

    def select(self, *_a, **_kw):
        return self

    def range(self, start, end):
        self._start, self._end = start, end
        return self

    def execute(self):
        return SimpleNamespace(data=self._all_rows[self._start:self._end + 1])


class FakeSupabaseClient:
    def __init__(self, rows_by_table):
        self._rows_by_table = rows_by_table
        self.range_calls = []

    def table(self, name):
        table = FakePaginatedTable(self._rows_by_table[name])
        real_range = table.range

        def tracked_range(start, end):
            self.range_calls.append((start, end))
            return real_range(start, end)

        table.range = tracked_range
        return table


def test_fetch_all_rows_paginates_past_a_single_page():
    rows = [{"id": i} for i in range(1034)]
    client = FakeSupabaseClient({"player_match_stats": rows})

    result = fetch_all_rows(client, "player_match_stats", page_size=500)

    assert len(result) == 1034
    assert result[0]["id"] == 0
    assert result[-1]["id"] == 1033


def test_fetch_all_rows_stops_cleanly_on_exact_page_multiple():
    # 1000 rows with page_size=500: two full pages, then a 3rd request
    # returns empty and the loop must stop there, not loop forever or
    # double-count.
    rows = [{"id": i} for i in range(1000)]
    client = FakeSupabaseClient({"matches": rows})

    result = fetch_all_rows(client, "matches", page_size=500)

    assert len(result) == 1000
    assert client.range_calls == [(0, 499), (500, 999), (1000, 1499)]


def test_fetch_all_rows_single_small_page_makes_one_call():
    rows = [{"id": 1}, {"id": 2}]
    client = FakeSupabaseClient({"team_match_stats": rows})

    result = fetch_all_rows(client, "team_match_stats", page_size=500)

    assert result == rows
    assert client.range_calls == [(0, 499)]


def test_page_size_stays_under_postgrest_default_row_cap():
    assert PAGE_SIZE < 1000


# ------------------------------ row JSON-safety -------------------------------

def test_json_safe_converts_date_to_isoformat():
    assert _json_safe(date(2015, 8, 23)) == "2015-08-23"


def test_json_safe_passes_through_non_date_values():
    assert _json_safe(5246) == 5246
    assert _json_safe(0.4) == 0.4
    assert _json_safe(None) is None


def test_row_to_json_safe_dict_converts_all_date_fields():
    row = {"player_id": 5246, "match_date": date(2015, 8, 23), "xg": 0.4}

    result = _row_to_json_safe_dict(row)

    assert result == {"player_id": 5246, "match_date": "2015-08-23", "xg": 0.4}
