-- There is no migration runner wired up in this project yet (see
-- 0004_add_player_status.sql), so this file must be run by hand once, in
-- the Supabase SQL editor (or via psql against the project's direct
-- connection string).
--
-- 0006's internal batching still hit 'canceling statement due to
-- statement timeout' (57014) on the real match_events reload (71,506
-- rows). Postgres's statement_timeout is measured for the entire
-- top-level command received from the client -- calling this function is
-- ONE command, so the clock covers every batch inside the loop, not each
-- batch individually. Batching alone can't fix a wall-clock limit; only
-- raising the limit for this call can.
--
-- SET LOCAL scopes the higher timeout to this function's own transaction
-- only (the transaction that already wraps the whole delete+insert, see
-- 0005's header) -- it reverts automatically once the call returns, so it
-- doesn't affect any other query on the connection.
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
  set local statement_timeout = '120s';

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
