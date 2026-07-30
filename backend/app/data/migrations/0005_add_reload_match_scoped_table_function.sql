-- There is no migration runner wired up in this project yet (see
-- 0004_add_player_status.sql), so this file must be run by hand once, in
-- the Supabase SQL editor (or via psql against the project's direct
-- connection string).
--
-- Backs app.data.load_v2.reload_table_for_matches: previously that function
-- issued a DELETE and then a separate chunked INSERT as independent
-- PostgREST requests, each its own implicit transaction -- a concurrent
-- read landing between them would see the table with those match_ids'
-- rows entirely missing. A single function call is one Postgres statement
-- and therefore one transaction: the DELETE and every row of the INSERT
-- commit together, so a concurrent reader only ever sees the old, complete
-- data or the new, complete data, never a gap.
--
-- p_records carries the full row set for one reload in a single call
-- (rather than the 500-row chunks used for teams/players/matches upserts)
-- specifically so that whole set commits atomically -- splitting it across
-- multiple PostgREST requests would reintroduce the same gap this function
-- exists to close, since separate HTTP requests can't share one transaction.
--
-- The insert column list is derived from the keys of the first record
-- rather than using `SELECT *` from jsonb_populate_recordset: these tables
-- have DB-generated columns (bigserial id, and player_match_stats.loaded_at
-- defaulting to now()) that are never present in the payload. Selecting
-- `*` would pull those in as explicit NULLs and violate their NOT NULL
-- constraints; naming only the payload's own columns leaves them correctly
-- unmentioned so their DEFAULTs apply.
create or replace function reload_match_scoped_table(
  p_table_name text,
  p_match_ids integer[],
  p_records jsonb
) returns void as $$
declare
  v_columns text;
begin
  execute format('delete from %I where match_id = any($1)', p_table_name)
    using p_match_ids;

  if jsonb_array_length(p_records) > 0 then
    select string_agg(quote_ident(key), ', ')
      into v_columns
      from jsonb_object_keys(p_records -> 0) as key;

    execute format(
      'insert into %I (%s) select %s from jsonb_populate_recordset(null::%I, $1)',
      p_table_name, v_columns, v_columns, p_table_name
    ) using p_records;
  end if;
end;
$$ language plpgsql;
