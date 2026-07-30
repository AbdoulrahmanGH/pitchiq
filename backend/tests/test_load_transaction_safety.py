"""Proves reload_table_for_matches (app.data.load_v2) against the real
pitchiq-v2-dev database, for both of its paths (see that function's
docstring):

- At or under ATOMIC_RELOAD_ROW_LIMIT (player_match_stats, team_match_stats
  in practice): a concurrent read landing between the delete and the
  insert must see either the complete old data or the complete new data,
  never an empty or partial row count.
- Above that limit (match_events in practice, too large to fit inside
  Supabase's per-statement execution ceiling for one RPC call -- see
  migrations/0008_split_reload_for_oversized_tables.sql): a weaker but
  still real guarantee -- rows are never lost, so the count must never
  drop to 0, even though it may sit anywhere between the old and new
  counts while the chunks land.

Requires migrations/0008_split_reload_for_oversized_tables.sql to have
been applied by hand (see that file's header) -- skipped with a clear
reason if the functions don't exist yet, on top of the usual
credentials-not-configured skip test_load_idempotency.py also uses.

Intentionally real, timing-based integration tests (no mocks): each starts
a reload in the main thread's call path and polls row counts from a
separate client on a background thread while it runs.
"""

import threading
import time

import pandas as pd
import pytest
from supabase import create_client

from app.config import SUPABASE_KEY, SUPABASE_URL
from app.data.load_v2 import ATOMIC_RELOAD_ROW_LIMIT, reload_table_for_matches

pytestmark = pytest.mark.skipif(
    not SUPABASE_URL or not SUPABASE_KEY,
    reason="SUPABASE_URL/SUPABASE_KEY not configured",
)

# Far outside real StatsBomb match ids -- safe to create and discard.
ATOMIC_TEST_MATCH_ID = 999999901
OVERSIZED_TEST_MATCH_ID = 999999902
ROW_COUNT = 4000
OVERSIZED_ROW_COUNT = ATOMIC_RELOAD_ROW_LIMIT + 5_000


def _seed_matches_row(client, match_id, name):
    client.table("matches").upsert({
        "id": match_id,
        "competition_id": 0,
        "competition_name": name,
        "season_id": 0,
        "season_name": "Test",
    }, on_conflict="id").execute()


def _count_for_match(client, table, match_id):
    return (
        client.table(table)
        .select("id", count="exact")
        .eq("match_id", match_id)
        .limit(1)
        .execute()
        .count
    )


def _skip_if_function_missing(exc):
    message = str(exc).lower()
    if "match_scoped" in message or "could not find" in message:
        pytest.skip(
            "The reload_match_scoped_table/delete_match_scoped_rows/"
            "insert_match_scoped_batch functions aren't installed on this "
            "database yet -- apply "
            "migrations/0008_split_reload_for_oversized_tables.sql in the "
            "Supabase SQL editor first."
        )
    raise exc


def _make_player_match_stats_df(n, label):
    # No player_id/team_id -- both are FK columns and this test's ids don't
    # correspond to real players/teams. `position` is a plain nullable text
    # column, safe to use as an "old batch" vs "new batch" content marker.
    return pd.DataFrame([{"match_id": ATOMIC_TEST_MATCH_ID, "position": label} for _ in range(n)])


def _make_match_events_df(n, label):
    # event_type is NOT NULL and has no FK, so it doubles as a safe content
    # marker here the same way `position` does for player_match_stats above.
    return pd.DataFrame([{"match_id": OVERSIZED_TEST_MATCH_ID, "event_type": label} for _ in range(n)])


@pytest.fixture
def real_client():
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    _seed_matches_row(client, ATOMIC_TEST_MATCH_ID, "Transaction Safety Test (atomic)")
    yield client
    client.table("player_match_stats").delete().eq("match_id", ATOMIC_TEST_MATCH_ID).execute()
    client.table("matches").delete().eq("id", ATOMIC_TEST_MATCH_ID).execute()


@pytest.fixture
def real_client_oversized():
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    _seed_matches_row(client, OVERSIZED_TEST_MATCH_ID, "Transaction Safety Test (oversized)")
    yield client
    client.table("match_events").delete().eq("match_id", OVERSIZED_TEST_MATCH_ID).execute()
    client.table("matches").delete().eq("id", OVERSIZED_TEST_MATCH_ID).execute()


def test_concurrent_read_never_sees_a_partial_or_empty_state(real_client):
    old_df = _make_player_match_stats_df(ROW_COUNT, "old-batch")
    new_df = _make_player_match_stats_df(ROW_COUNT, "new-batch")

    try:
        reload_table_for_matches(real_client, "player_match_stats", old_df, match_ids=[ATOMIC_TEST_MATCH_ID])
    except Exception as exc:
        _skip_if_function_missing(exc)
    assert _count_for_match(real_client, "player_match_stats", ATOMIC_TEST_MATCH_ID) == ROW_COUNT

    reader_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    observed_counts = []
    stop = threading.Event()

    def poll():
        while not stop.is_set():
            observed_counts.append(_count_for_match(reader_client, "player_match_stats", ATOMIC_TEST_MATCH_ID))
            time.sleep(0.01)

    poller = threading.Thread(target=poll, daemon=True)
    poller.start()
    time.sleep(0.05)  # let the poller take at least one reading before the reload starts

    reload_table_for_matches(real_client, "player_match_stats", new_df, match_ids=[ATOMIC_TEST_MATCH_ID])

    stop.set()
    poller.join(timeout=5)

    assert _count_for_match(real_client, "player_match_stats", ATOMIC_TEST_MATCH_ID) == ROW_COUNT
    sample = (
        real_client.table("player_match_stats")
        .select("position").eq("match_id", ATOMIC_TEST_MATCH_ID).limit(1).execute().data
    )
    assert sample[0]["position"] == "new-batch"  # the swap actually happened, not a no-op

    assert observed_counts, "poller never got a chance to read during the reload"
    bad_counts = sorted({c for c in observed_counts if c != ROW_COUNT})
    assert not bad_counts, f"observed a partial/empty row count during the reload: {bad_counts}"


def test_oversized_table_reload_never_drops_to_zero_rows(real_client_oversized):
    # match_events-scale reload (above ATOMIC_RELOAD_ROW_LIMIT): this
    # fallback can't guarantee a concurrent read never sees a partial
    # count, but it must never see zero -- new chunks are inserted first
    # (old rows stay untouched while they land) and only the previously-
    # existing rows are deleted afterward, by id, in one final call.
    old_df = _make_match_events_df(OVERSIZED_ROW_COUNT, "old-batch")
    new_df = _make_match_events_df(OVERSIZED_ROW_COUNT, "new-batch")

    try:
        reload_table_for_matches(real_client_oversized, "match_events", old_df, match_ids=[OVERSIZED_TEST_MATCH_ID])
    except Exception as exc:
        _skip_if_function_missing(exc)
    assert _count_for_match(real_client_oversized, "match_events", OVERSIZED_TEST_MATCH_ID) == OVERSIZED_ROW_COUNT

    reader_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    observed_counts = []
    stop = threading.Event()

    def poll():
        while not stop.is_set():
            observed_counts.append(_count_for_match(reader_client, "match_events", OVERSIZED_TEST_MATCH_ID))
            time.sleep(0.05)

    poller = threading.Thread(target=poll, daemon=True)
    poller.start()
    time.sleep(0.1)

    reload_table_for_matches(real_client_oversized, "match_events", new_df, match_ids=[OVERSIZED_TEST_MATCH_ID])

    stop.set()
    poller.join(timeout=10)

    assert _count_for_match(real_client_oversized, "match_events", OVERSIZED_TEST_MATCH_ID) == OVERSIZED_ROW_COUNT
    sample = (
        real_client_oversized.table("match_events")
        .select("event_type").eq("match_id", OVERSIZED_TEST_MATCH_ID).limit(1).execute().data
    )
    assert sample[0]["event_type"] == "new-batch"

    assert observed_counts, "poller never got a chance to read during the reload"
    assert 0 not in observed_counts, "row count dropped to zero during the oversized-table reload"
