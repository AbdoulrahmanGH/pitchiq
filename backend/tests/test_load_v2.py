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

from app.data.load_v2 import (
    ATOMIC_RELOAD_ROW_LIMIT,
    CHUNK_SIZE,
    RELOAD_CHUNK_SIZE,
    load,
    reload_table_for_matches,
    upsert_table,
)


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self._range = None

    def upsert(self, records, on_conflict=None):
        self.client.calls.append(("upsert", self.name, records, on_conflict))
        return self

    def select(self, *_args, **_kwargs):
        return self

    def in_(self, column, values):
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def execute(self):
        if self._range is not None:
            start, end = self._range
            existing_ids = self.client.existing_ids_by_table.get(self.name, [])
            page = existing_ids[start:end + 1]
            return FakeResult([{"id": i} for i in page])
        return None


class FakeRpc:
    def __init__(self, client, fn_name, params):
        self.client = client
        self.fn_name = fn_name
        self.params = params

    def execute(self):
        self.client.calls.append(("rpc", self.fn_name, self.params))
        return None


class FakeClient:
    def __init__(self, existing_ids_by_table=None):
        self.calls = []
        self.existing_ids_by_table = existing_ids_by_table or {}

    def table(self, name):
        return FakeTable(self, name)

    def rpc(self, fn_name, params):
        return FakeRpc(self, fn_name, params)


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


def test_reload_issues_a_single_rpc_call_carrying_both_delete_and_insert():
    # The delete and insert happen inside the reload_match_scoped_table
    # Postgres function (one call = one transaction, see
    # migrations/0008_split_reload_for_oversized_tables.sql) rather
    # than as separate delete()/insert() requests -- a concurrent read
    # could otherwise land in the gap between two independent HTTP calls.
    # This table's row count is well under ATOMIC_RELOAD_ROW_LIMIT, so it
    # always takes this path.
    client = FakeClient()
    df = pd.DataFrame([{"match_id": 1, "player_id": 5}])

    reload_table_for_matches(client, "player_match_stats", df, match_ids=[1, 2])

    assert len(client.calls) == 1
    kind, fn_name, params = client.calls[0]
    assert kind == "rpc"
    assert fn_name == "reload_match_scoped_table"
    assert params["p_table_name"] == "player_match_stats"
    assert params["p_records"] == [{"match_id": 1, "player_id": 5}]


def test_reload_deletes_scoped_to_given_match_ids():
    client = FakeClient()
    df = pd.DataFrame([{"match_id": 1, "player_id": 5}])

    reload_table_for_matches(client, "player_match_stats", df, match_ids=[1, 2, 3])

    _, _, params = client.calls[0]
    assert params["p_match_ids"] == [1, 2, 3]


def test_reload_still_issues_the_rpc_call_when_there_are_no_rows():
    # Empty p_records still deletes any existing rows for these match_ids --
    # the SQL function itself skips the insert when the array is empty.
    client = FakeClient()
    df = pd.DataFrame(columns=["match_id", "player_id"])

    reload_table_for_matches(client, "player_match_stats", df, match_ids=[1])

    assert len(client.calls) == 1
    _, _, params = client.calls[0]
    assert params["p_records"] == []


# ------------------- oversized-table fallback (match_events-scale) -------------------
# Above ATOMIC_RELOAD_ROW_LIMIT, a single atomic RPC call risks Supabase's
# per-statement execution ceiling (confirmed empirically against the real
# database -- see migrations/0008_split_reload_for_oversized_tables.sql).
# reload_table_for_matches falls back to inserting every new chunk FIRST,
# then deleting only the previously-existing ids -- never a plain delete
# followed by inserts, which would reopen the empty-table gap this whole
# module exists to close.

def test_reload_inserts_new_chunks_before_deleting_old_rows_above_the_atomic_limit():
    client = FakeClient(existing_ids_by_table={"match_events": [901, 902, 903]})
    row_count = ATOMIC_RELOAD_ROW_LIMIT + 1
    df = pd.DataFrame([{"match_id": 1, "event_type": "Pass"} for _ in range(row_count)])

    reload_table_for_matches(client, "match_events", df, match_ids=[1])

    fn_names = [c[1] for c in client.calls]
    assert all(fn == "insert_match_scoped_batch" for fn in fn_names[:-1])
    assert fn_names[-1] == "delete_rows_by_id"  # cleanup happens last, after every insert
    assert len(fn_names) > 2  # more than one insert chunk, plus the final delete

    insert_calls = client.calls[:-1]
    assert sum(len(c[2]["p_records"]) for c in insert_calls) == row_count
    assert all(len(c[2]["p_records"]) <= RELOAD_CHUNK_SIZE for c in insert_calls)

    delete_params = client.calls[-1][2]
    assert delete_params["p_table_name"] == "match_events"
    assert delete_params["p_ids"] == [901, 902, 903]


def test_reload_skips_the_final_delete_when_there_were_no_old_rows():
    client = FakeClient(existing_ids_by_table={"match_events": []})
    row_count = ATOMIC_RELOAD_ROW_LIMIT + 1
    df = pd.DataFrame([{"match_id": 1, "event_type": "Pass"} for _ in range(row_count)])

    reload_table_for_matches(client, "match_events", df, match_ids=[1])

    assert "delete_rows_by_id" not in [c[1] for c in client.calls]


def test_reload_at_exactly_the_atomic_limit_still_uses_the_single_call_path():
    client = FakeClient()
    df = pd.DataFrame([{"match_id": 1} for _ in range(ATOMIC_RELOAD_ROW_LIMIT)])

    reload_table_for_matches(client, "match_events", df, match_ids=[1])

    assert len(client.calls) == 1
    assert client.calls[0][1] == "reload_match_scoped_table"


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

    def reload_index(table_name):
        return next(
            i for i, c in enumerate(client.calls)
            if c[0] == "rpc" and c[2]["p_table_name"] == table_name
        )

    upsert_order = [(c[0], c[1]) for c in client.calls if c[0] == "upsert"]
    assert upsert_order.index(("upsert", "teams")) < upsert_order.index(("upsert", "matches"))
    assert upsert_order.index(("upsert", "players")) < upsert_order.index(("upsert", "matches"))

    matches_upsert_index = next(i for i, c in enumerate(client.calls) if c[:2] == ("upsert", "matches"))
    assert matches_upsert_index < reload_index("player_match_stats")
    assert reload_index("team_match_stats") is not None
    assert reload_index("match_events") is not None

    # never a truncate-everything call: every reload is scoped to match_ids
    reload_calls = [c for c in client.calls if c[0] == "rpc"]
    assert all(c[2]["p_match_ids"] == [100] for c in reload_calls)
