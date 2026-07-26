-- schema_v2.sql is the source of truth for fresh installs and already
-- includes this column; this migration exists to bring an already-created
-- pitchiq-v2-dev database (created before this column existed) up to date.
--
-- There is no migration runner wired up in this project yet, so this file
-- must be run by hand once, in the Supabase SQL editor (or via psql against
-- the project's direct connection string).
--
-- Backs the Pipeline Visibility page's "Current data" freshness clock:
-- player_match_stats is fully delete-then-reinserted for every match on
-- every real pipeline run (see load_v2.reload_table_for_matches), so
-- MAX(loaded_at) is exactly "when did Postgres last get written", with no
-- application code required to keep it correct -- the column default
-- alone does the job, since these rows are never upserted in place.
alter table player_match_stats
  add column if not exists loaded_at timestamptz not null default now();
