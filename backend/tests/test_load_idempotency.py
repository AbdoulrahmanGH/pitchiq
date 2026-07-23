"""Proves load() is idempotent against the real pitchiq-v2-dev database.

This is intentionally an integration test (real network, real Supabase) and
is skipped if credentials aren't configured. It uses 3 real StatsBomb matches
(fast) rather than the full 38-match season -- idempotency is a property of
load(), not of the extract volume, so re-running the load for the same
tables dict twice is sufficient proof.
"""

import os

import pytest

from app.config import SUPABASE_KEY, SUPABASE_URL
from app.data.load_v2 import load
from app.data.pipeline_v2 import extract, transform
from supabase import create_client

pytestmark = pytest.mark.skipif(
    not SUPABASE_URL or not SUPABASE_KEY,
    reason="SUPABASE_URL/SUPABASE_KEY not configured",
)

TABLE_NAMES = ("teams", "players", "matches", "player_match_stats",
              "team_match_stats", "match_events")


def _table_counts(client, match_ids):
    counts = {}
    for t in ("teams", "players"):
        counts[t] = client.table(t).select("id", count="exact").limit(1).execute().count
    counts["matches"] = (
        client.table("matches").select("id", count="exact")
        .in_("id", match_ids).limit(1).execute().count
    )
    for t in ("player_match_stats", "team_match_stats", "match_events"):
        counts[t] = (
            client.table(t).select("*", count="exact")
            .in_("match_id", match_ids).limit(1).execute().count
        )
    return counts


@pytest.fixture(scope="module")
def real_tables():
    matches, events_by_match, lineups_by_match = extract(limit=3)
    return transform(matches, events_by_match, lineups_by_match)


def test_load_twice_yields_identical_row_counts(real_tables):
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    match_ids = real_tables["matches"]["id"].tolist()

    load(real_tables, client=client)
    first_counts = _table_counts(client, match_ids)

    load(real_tables, client=client)
    second_counts = _table_counts(client, match_ids)

    assert first_counts == second_counts
    for t in ("player_match_stats", "team_match_stats", "match_events"):
        assert second_counts[t] == len(real_tables[t])
