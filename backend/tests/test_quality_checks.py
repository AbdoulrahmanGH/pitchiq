"""Tests for the post-load data quality check. This exists specifically to
catch the kind of stale-write issue found by hand during the Secret Manager
migration step (3 players' primary_position silently stuck at NULL in
Supabase despite correct transform output) -- automatically, not by someone
noticing.

Uses a fake Supabase client double -- no real network calls.
"""

import pytest

from app.data.quality_checks import (
    QualityCheckFailure,
    assert_bigquery_mirror_quality,
    assert_quality,
    find_bigquery_mirror_count_mismatches,
    find_matches_missing_scores,
    find_null_primary_positions,
    find_null_team_names,
    run_quality_checks,
)

TEAM_ID = 217


class FakeResult:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count if count is not None else len(data)


class FakeTable:
    def __init__(self, rows):
        self._rows = rows
        self._filtered = rows

    def select(self, *_args, **_kwargs):
        self._filtered = self._rows
        return self

    def eq(self, column, value):
        self._filtered = [r for r in self._filtered if r.get(column) == value]
        return self

    def in_(self, column, values):
        values = set(values)
        self._filtered = [r for r in self._filtered if r.get(column) in values]
        return self

    def limit(self, _n):
        return self

    def execute(self):
        return FakeResult(self._filtered)


class FakeClient:
    def __init__(self, tables):
        self._tables = tables

    def table(self, name):
        return FakeTable(self._tables[name])


def make_client(pms=None, players=None, teams=None, matches=None, team_match_stats=None):
    return FakeClient({
        "player_match_stats": pms or [],
        "players": players or [],
        "teams": teams or [],
        "matches": matches or [],
        "team_match_stats": team_match_stats or [],
    })


class FakeBigQueryResult:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class FakeBigQueryClient:
    """counts_by_table: {table_name: row_count}. query() matches the table
    name embedded in the SQL string -- good enough for these pure-logic
    tests without parsing real SQL."""
    def __init__(self, counts_by_table):
        self._counts_by_table = counts_by_table

    def query(self, sql, job_config=None):
        for table_name, count in self._counts_by_table.items():
            if f".{table_name}`" in sql:
                return FakeBigQueryResult([{"n": count}])
        raise AssertionError(f"unexpected BigQuery query: {sql}")


# --------------------------- null primary_position ---------------------------

def test_finds_roster_players_with_null_position():
    client = make_client(
        pms=[{"player_id": 1, "team_id": TEAM_ID}, {"player_id": 2, "team_id": TEAM_ID}],
        players=[
            {"id": 1, "name": "Has Position", "primary_position": "Right Wing"},
            {"id": 2, "name": "Missing Position", "primary_position": None},
        ],
    )

    result = find_null_primary_positions(client, TEAM_ID)

    assert len(result) == 1
    assert result[0]["id"] == 2


def test_does_not_flag_opponent_players_outside_our_roster():
    # Real StatsBomb data has ~80 opponent bench players league-wide with
    # genuinely no position data -- the check must only cover our own roster.
    client = make_client(
        pms=[{"player_id": 1, "team_id": TEAM_ID}],
        players=[
            {"id": 1, "name": "Ours", "primary_position": "Center Back"},
            {"id": 99, "name": "Opponent sub", "primary_position": None},
        ],
    )

    result = find_null_primary_positions(client, TEAM_ID)

    assert result == []


# ------------------------------ null team names -------------------------------

def test_finds_teams_with_null_name():
    client = make_client(teams=[
        {"id": 1, "name": "Barcelona"},
        {"id": 2, "name": None},
    ])

    result = find_null_team_names(client)

    assert len(result) == 1
    assert result[0]["id"] == 2


# --------------------------- matches missing scores ----------------------------

def test_finds_matches_with_missing_scores():
    client = make_client(matches=[
        {"id": 1, "home_score": 1, "away_score": 0},
        {"id": 2, "home_score": None, "away_score": 2},
        {"id": 3, "home_score": 1, "away_score": None},
    ])

    result = find_matches_missing_scores(client)

    assert {m["id"] for m in result} == {2, 3}


# --------------------------------- combined ------------------------------------

def test_run_quality_checks_returns_empty_dict_when_clean():
    client = make_client(
        pms=[{"player_id": 1, "team_id": TEAM_ID}],
        players=[{"id": 1, "name": "Fine", "primary_position": "Center Back"}],
        teams=[{"id": 1, "name": "Barcelona"}],
        matches=[{"id": 1, "home_score": 1, "away_score": 0}],
    )

    assert run_quality_checks(client, TEAM_ID) == {}


def test_run_quality_checks_reports_every_failing_check():
    client = make_client(
        pms=[{"player_id": 1, "team_id": TEAM_ID}],
        players=[{"id": 1, "name": "Bad", "primary_position": None}],
        teams=[{"id": 1, "name": None}],
        matches=[{"id": 1, "home_score": None, "away_score": None}],
    )

    failures = run_quality_checks(client, TEAM_ID)

    assert set(failures.keys()) == {
        "null_primary_position", "null_team_names", "matches_missing_scores",
    }


def test_assert_quality_raises_when_dirty():
    client = make_client(
        pms=[{"player_id": 1, "team_id": TEAM_ID}],
        players=[{"id": 1, "name": "Bad", "primary_position": None}],
    )

    with pytest.raises(QualityCheckFailure):
        assert_quality(client, TEAM_ID)


def test_assert_quality_does_not_raise_when_clean():
    client = make_client(
        pms=[{"player_id": 1, "team_id": TEAM_ID}],
        players=[{"id": 1, "name": "Fine", "primary_position": "Center Back"}],
        teams=[{"id": 1, "name": "Barcelona"}],
        matches=[{"id": 1, "home_score": 1, "away_score": 0}],
    )

    assert_quality(client, TEAM_ID)  # must not raise


# --------------------------- BigQuery mirror quality ---------------------------

MIRROR_TABLES = ("matches", "player_match_stats", "team_match_stats")


def test_bigquery_mirror_counts_finds_no_mismatch_when_equal():
    supabase = make_client(
        matches=[{"id": 1}, {"id": 2}],
        pms=[{"id": 1}, {"id": 2}, {"id": 3}],
        team_match_stats=[{"id": 1}, {"id": 2}],
    )
    bq = FakeBigQueryClient({"matches": 2, "player_match_stats": 3, "team_match_stats": 2})

    result = find_bigquery_mirror_count_mismatches(
        supabase, bq, "proj", "ds", MIRROR_TABLES
    )

    assert result == {}


def test_bigquery_mirror_counts_flags_a_short_mirror():
    # A WRITE_TRUNCATE load that landed fewer rows than Postgres has --
    # e.g. a truncated/partial BigQuery load job.
    supabase = make_client(
        matches=[{"id": 1}, {"id": 2}],
        pms=[{"id": 1}, {"id": 2}, {"id": 3}],
        team_match_stats=[{"id": 1}, {"id": 2}],
    )
    bq = FakeBigQueryClient({"matches": 2, "player_match_stats": 2, "team_match_stats": 2})

    result = find_bigquery_mirror_count_mismatches(
        supabase, bq, "proj", "ds", MIRROR_TABLES
    )

    assert result == {"player_match_stats": {"postgres": 3, "bigquery": 2}}


def test_assert_bigquery_mirror_quality_raises_on_mismatch():
    supabase = make_client(matches=[{"id": 1}])
    bq = FakeBigQueryClient({"matches": 0, "player_match_stats": 0, "team_match_stats": 0})

    with pytest.raises(QualityCheckFailure):
        assert_bigquery_mirror_quality(supabase, bq, "proj", "ds", MIRROR_TABLES)


def test_assert_bigquery_mirror_quality_does_not_raise_when_clean():
    supabase = make_client(
        matches=[{"id": 1}],
        pms=[{"id": 1}],
        team_match_stats=[{"id": 1}],
    )
    bq = FakeBigQueryClient({"matches": 1, "player_match_stats": 1, "team_match_stats": 1})

    assert_bigquery_mirror_quality(supabase, bq, "proj", "ds", MIRROR_TABLES)  # must not raise
