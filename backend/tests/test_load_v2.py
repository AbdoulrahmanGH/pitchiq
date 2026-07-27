"""Unit tests for the pure load logic in app.data.load_v2.

These use a fake Supabase client double so they run with no network and no
real database — they prove the *call sequence and payload shape* (chunking,
NaN->None cleaning, delete-before-insert ordering, on_conflict target), not
that Supabase itself behaves as documented. Idempotency against the real
dev database is proven separately in test_load_idempotency.py.
"""

import math

import pandas as pd
import pytest

from app.data.load_v2 import CHUNK_SIZE, load, reload_table_for_matches, upsert_table


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name

    def upsert(self, records, on_conflict=None):
        self.client.calls.append(("upsert", self.name, records, on_conflict))
        return self

    def insert(self, records):
        self.client.calls.append(("insert", self.name, records))
        return self

    def delete(self):
        return self

    def in_(self, column, values):
        self.client.calls.append(("delete_in", self.name, column, list(values)))
        return self

    def execute(self):
        return None


class FakeClient:
    def __init__(self):
        self.calls = []

    def table(self, name):
        return FakeTable(self, name)


def test_upsert_table_targets_id_conflict_column():
    client = FakeClient()
    df = pd.DataFrame([{"id": 1, "name": "Barcelona"}])

    upsert_table(client, "teams", df)

    assert client.calls == [("upsert", "teams", [{"id": 1, "name": "Barcelona"}], "id")]


def test_upsert_table_converts_nan_to_none():
    client = FakeClient()
    df = pd.DataFrame([{"id": 1, "country": float("nan")}])

    upsert_table(client, "teams", df)

    _, _, records, _ = client.calls[0]
    assert records[0]["country"] is None


def test_upsert_table_converts_nullable_int_na_to_none_and_keeps_ints():
    # match_events.recipient_id is a nullable Int64 column: nulls must land
    # as JSON null (not pd.NA, which isn't serializable), and present values
    # must stay integers (not "6606.0", which Postgres rejects).
    client = FakeClient()
    df = pd.DataFrame({"id": [1, 2], "recipient_id": pd.array([6606, None], dtype="Int64")})

    upsert_table(client, "match_events", df)

    _, _, records, _ = client.calls[0]
    assert records[0]["recipient_id"] == 6606
    assert not isinstance(records[0]["recipient_id"], float)
    assert records[1]["recipient_id"] is None


def test_upsert_table_chunks_large_frames():
    client = FakeClient()
    df = pd.DataFrame([{"id": i} for i in range(CHUNK_SIZE + 1)])

    upsert_table(client, "players", df)

    assert len(client.calls) == 2
    assert len(client.calls[0][2]) == CHUNK_SIZE
    assert len(client.calls[1][2]) == 1


def test_reload_deletes_before_inserting():
    client = FakeClient()
    df = pd.DataFrame([{"match_id": 1, "player_id": 5}])

    reload_table_for_matches(client, "player_match_stats", df, match_ids=[1, 2])

    kinds = [c[0] for c in client.calls]
    assert kinds.index("delete_in") < kinds.index("insert")


def test_reload_deletes_scoped_to_given_match_ids():
    client = FakeClient()
    df = pd.DataFrame([{"match_id": 1, "player_id": 5}])

    reload_table_for_matches(client, "player_match_stats", df, match_ids=[1, 2, 3])

    delete_call = next(c for c in client.calls if c[0] == "delete_in")
    assert delete_call[2] == "match_id"
    assert delete_call[3] == [1, 2, 3]


def test_reload_skips_insert_when_no_rows():
    client = FakeClient()
    df = pd.DataFrame(columns=["match_id", "player_id"])

    reload_table_for_matches(client, "player_match_stats", df, match_ids=[1])

    kinds = [c[0] for c in client.calls]
    assert "delete_in" in kinds
    assert "insert" not in kinds


def test_load_upserts_lookup_tables_before_reloading_stats_tables():
    client = FakeClient()
    tables = {
        "teams": pd.DataFrame([{"id": 1, "name": "Barcelona"}]),
        "players": pd.DataFrame([{"id": 10, "name": "Messi"}]),
        "matches": pd.DataFrame([{"id": 100, "home_team_id": 1}]),
        "player_match_stats": pd.DataFrame([{"match_id": 100, "player_id": 10}]),
        "team_match_stats": pd.DataFrame([{"match_id": 100, "team_id": 1}]),
        "match_events": pd.DataFrame([{"match_id": 100, "player_id": 10}]),
    }

    load(tables, client=client)

    order = [(c[0], c[1]) for c in client.calls]
    assert order.index(("upsert", "teams")) < order.index(("upsert", "matches"))
    assert order.index(("upsert", "players")) < order.index(("upsert", "matches"))
    assert order.index(("upsert", "matches")) < order.index(("delete_in", "player_match_stats"))
    assert ("delete_in", "team_match_stats") in order
    assert ("delete_in", "match_events") in order
    # never a truncate-everything call: delete_in is always scoped
    delete_calls = [c for c in client.calls if c[0] == "delete_in"]
    assert all(c[3] == [100] for c in delete_calls)
