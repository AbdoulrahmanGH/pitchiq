-- There is no migration runner wired up in this project yet (see
-- 0004_add_player_status.sql), so this file must be run by hand once, in
-- the Supabase SQL editor (or via psql against the project's direct
-- connection string).
--
-- Empirically confirmed against the real database: a single
-- reload_match_scoped_table() call carrying match_events' full row set
-- (71,506 rows for a 38-match run, each needing real FK checks against
-- players/teams) took at least 87.7s and was still cancelled by
-- 'canceling statement due to statement timeout' (57014) -- even with
-- 0007's SET LOCAL statement_timeout raised to 120s. That means Supabase
-- enforces a hard ceiling on a single top-level statement's execution
-- time for API-role calls that SET LOCAL cannot override. player_match_stats
-- (1,034 rows) and team_match_stats (76 rows) are nowhere near that
-- ceiling and stay fully atomic.
--
-- This simplifies reload_match_scoped_table back to one INSERT...SELECT
-- pass (0006's manual batching loop was actively counterproductive:
-- jsonb_array_elements has no random access into a jsonb array, so
-- re-running it once per batch re-decoded the entire array from scratch
-- every iteration), and adds two new functions used only for tables too
-- large to fit in one call:
--   - insert_match_scoped_batch: insert of one batch, no delete, callable
--     multiple times.
--   - delete_rows_by_id: delete by explicit id list, not by match_id --
--     used to clean up the *previous* rows only after every new batch has
--     landed, so the table only ever grows during the reload rather than
--     going empty first. See app.data.load_v2.reload_table_for_matches for
--     the full sequence and what guarantee each path gives.
--
-- Drops delete_match_scoped_rows, added by an earlier version of this same
-- migration file (a plain delete-then-chunked-insert design) before this
-- version replaced it with the insert-first sequence above.
drop function if exists delete_match_scoped_rows(text, integer[]);

create or replace function reload_match_scoped_table(
  p_table_name text,
  p_match_ids integer[],
  p_records jsonb
) returns void as $$
declare
  v_columns text;
begin
  set local statement_timeout = '120s';

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

create or replace function delete_rows_by_id(
  p_table_name text,
  p_ids bigint[]
) returns void as $$
begin
  execute format('delete from %I where id = any($1)', p_table_name)
    using p_ids;
end;
$$ language plpgsql;

create or replace function insert_match_scoped_batch(
  p_table_name text,
  p_records jsonb
) returns void as $$
declare
  v_columns text;
begin
  if jsonb_array_length(p_records) = 0 then
    return;
  end if;

  select string_agg(quote_ident(key), ', ')
    into v_columns
    from jsonb_object_keys(p_records -> 0) as key;

  execute format(
    'insert into %I (%s) select %s from jsonb_populate_recordset(null::%I, $1)',
    p_table_name, v_columns, v_columns, p_table_name
  ) using p_records;
end;
$$ language plpgsql;
