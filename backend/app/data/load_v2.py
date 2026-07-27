"""Load step for the v2 pipeline: writes transform() output into Supabase.

Load order matters because of foreign keys:
1. teams, players, matches — upserted by `id`. Never truncated: they hold
   stable StatsBomb ids that later features reference.
2. player_match_stats, team_match_stats, match_events — no natural
   uniqueness, so existing rows for the matches being loaded are deleted,
   then fresh rows are inserted. This is the v1 truncate-and-reload pattern,
   scoped to `match_id in (...)` instead of wiping the whole table.
"""

import math

import pandas as pd
from supabase import create_client

from app.config import SUPABASE_KEY, SUPABASE_URL

CHUNK_SIZE = 500

LOOKUP_TABLES = ("teams", "players", "matches")
MATCH_SCOPED_TABLES = ("player_match_stats", "team_match_stats", "match_events")


def _null_or_value(v):
    # NaN from float columns and pd.NA from nullable-Int64 columns
    # (match_events.recipient_id) both become JSON null. Int64 values
    # themselves come out of to_dict() as ints, never "6606.0" floats.
    if v is pd.NA:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _clean(records):
    return [{k: _null_or_value(v) for k, v in r.items()} for r in records]


def _chunks(records, size=CHUNK_SIZE):
    for i in range(0, len(records), size):
        yield records[i:i + size]


def upsert_table(client, table, df, conflict_col="id"):
    records = _clean(df.to_dict(orient="records"))
    for chunk in _chunks(records):
        client.table(table).upsert(chunk, on_conflict=conflict_col).execute()
    return len(records)


def reload_table_for_matches(client, table, df, match_ids):
    client.table(table).delete().in_("match_id", match_ids).execute()
    records = _clean(df.to_dict(orient="records"))
    for chunk in _chunks(records):
        if chunk:
            client.table(table).insert(chunk).execute()
    return len(records)


def load(tables, client=None):
    """Load transform() output into Supabase. Returns row counts per table."""
    client = client or create_client(SUPABASE_URL, SUPABASE_KEY)
    match_ids = tables["matches"]["id"].tolist()

    counts = {}
    counts["teams"] = upsert_table(client, "teams", tables["teams"])
    counts["players"] = upsert_table(client, "players", tables["players"])
    counts["matches"] = upsert_table(client, "matches", tables["matches"])
    for table in MATCH_SCOPED_TABLES:
        counts[table] = reload_table_for_matches(client, table, tables[table], match_ids)
    return counts
