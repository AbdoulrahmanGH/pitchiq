"""Load step for the v2 pipeline: writes transform() output into Supabase.

Load order matters because of foreign keys:
1. teams, players, matches — upserted by `id`. Never truncated: they hold
   stable StatsBomb ids that later features reference.
2. player_match_stats, team_match_stats, match_events — no natural
   uniqueness, so existing rows for the matches being loaded are deleted,
   then fresh rows are inserted. This is the v1 truncate-and-reload pattern,
   scoped to `match_id in (...)` instead of wiping the whole table. For
   tables that fit under Supabase's per-statement execution ceiling for a
   single RPC call, the delete and insert run inside one Postgres
   transaction (the reload_match_scoped_table RPC function, see
   migrations/0008_split_reload_for_oversized_tables.sql) so a concurrent
   read is never able to land in the gap between them. match_events is too
   large for that (71,506 rows with real FK checks measured at over 87s
   against a call allowed up to 120s -- confirmed empirically, see that
   migration's header) and falls back to inserting the new rows first,
   then deleting only the old ones by id: the table only ever grows until
   one final, fast delete, so a concurrent read still never sees it empty
   -- though it may briefly see old and new rows together. See
   reload_table_for_matches for exactly which path a given table takes.
"""

import math

import pandas as pd
from supabase import create_client

from app.config import SUPABASE_KEY, SUPABASE_URL

CHUNK_SIZE = 500

# Above this row count, a single atomic RPC call risks Supabase's
# per-statement execution ceiling (see reload_table_for_matches). Chosen
# with margin below the smallest row count observed to fail (71,506 rows,
# >87s) and comfortably above the largest observed to succeed well within
# any reasonable timeout.
ATOMIC_RELOAD_ROW_LIMIT = 10_000
RELOAD_CHUNK_SIZE = 5_000

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


def _fetch_ids_for_matches(client, table, match_ids, page_size=1000):
    """All existing row ids for these match_ids, paginated so it isn't cut
    short by PostgREST's default response row cap.
    """
    ids = []
    offset = 0
    while True:
        page = (
            client.table(table).select("id").in_("match_id", match_ids)
            .range(offset, offset + page_size - 1).execute()
        ).data
        ids.extend(row["id"] for row in page)
        if len(page) < page_size:
            return ids
        offset += page_size


def reload_table_for_matches(client, table, df, match_ids):
    """Delete + insert for one match-scoped table.

    Row counts at or under ATOMIC_RELOAD_ROW_LIMIT go through a single RPC
    call (migrations/0008_split_reload_for_oversized_tables.sql) that runs
    the delete and the whole insert inside one Postgres transaction -- a
    concurrent read can never land in the gap between them.

    Above that limit (in practice, only match_events), the full set can't
    reliably finish inside a single top-level statement before Supabase
    cancels it. A plain delete-then-chunked-insert would reopen the empty
    -table gap this whole function exists to close (the delete alone is
    still one call, and the table would sit empty until the first insert
    chunk lands), so instead this inserts every new chunk FIRST, then
    deletes only the ids that existed before this call started. The table
    only ever grows until that final delete, so a concurrent read still
    never sees it empty -- it may briefly see old and new rows together,
    which is the weaker guarantee this path accepts.
    """
    records = _clean(df.to_dict(orient="records"))

    if len(records) <= ATOMIC_RELOAD_ROW_LIMIT:
        client.rpc("reload_match_scoped_table", {
            "p_table_name": table,
            "p_match_ids": match_ids,
            "p_records": records,
        }).execute()
    else:
        old_ids = _fetch_ids_for_matches(client, table, match_ids)

        for chunk in _chunks(records, size=RELOAD_CHUNK_SIZE):
            client.rpc("insert_match_scoped_batch", {
                "p_table_name": table,
                "p_records": chunk,
            }).execute()

        if old_ids:
            client.rpc("delete_rows_by_id", {
                "p_table_name": table,
                "p_ids": old_ids,
            }).execute()

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
