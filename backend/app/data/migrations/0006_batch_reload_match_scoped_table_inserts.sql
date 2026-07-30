-- There is no migration runner wired up in this project yet (see
-- 0004_add_player_status.sql), so this file must be run by hand once, in
-- the Supabase SQL editor (or via psql against the project's direct
-- connection string).
--
-- Fixes a real failure found running the full pipeline against
-- 0005_add_reload_match_scoped_table_function.sql: match_events (71,506
-- rows for a full 38-match run) as one single INSERT...SELECT from
-- jsonb_populate_recordset hit Postgres's statement_timeout ('canceling
-- statement due to statement timeout', code 57014) and the whole call
-- failed. player_match_stats (1,034 rows) and team_match_stats (76 rows)
-- were unaffected -- this only bit the largest table.
--
-- Fix: insert in batches of v_batch_size, looping inside the function.
-- This stays inside the one function call that Postgres already treats as
-- one transaction (see 0005's header), so the delete and every batch of
-- the insert still commit together -- a concurrent reader still never
-- sees a gap. Only the internal execution is now several smaller INSERT
-- statements instead of one large one, so no single statement risks
-- exceeding the timeout.
create or replace function reload_match_scoped_table(
  p_table_name text,
  p_match_ids integer[],
  p_records jsonb
) returns void as $$
declare
  v_columns text;
  v_batch jsonb;
  v_batch_size constant int := 5000;
  v_total int;
  v_start int := 0;
begin
  execute format('delete from %I where match_id = any($1)', p_table_name)
    using p_match_ids;

  v_total := jsonb_array_length(p_records);
  if v_total > 0 then
    select string_agg(quote_ident(key), ', ')
      into v_columns
      from jsonb_object_keys(p_records -> 0) as key;

    while v_start < v_total loop
      select jsonb_agg(elem)
        into v_batch
        from jsonb_array_elements(p_records) with ordinality as t(elem, idx)
        where idx > v_start and idx <= v_start + v_batch_size;

      execute format(
        'insert into %I (%s) select %s from jsonb_populate_recordset(null::%I, $1)',
        p_table_name, v_columns, v_columns, p_table_name
      ) using v_batch;

      v_start := v_start + v_batch_size;
    end loop;
  end if;
end;
$$ language plpgsql;
