-- schema_v2.sql is the source of truth for fresh installs and already
-- includes this column; this migration exists to bring an already-created
-- pitchiq-v2-dev database (created before this column existed) up to date.
--
-- There is no migration runner wired up in this project yet, so this file
-- must be run by hand once, in the Supabase SQL editor (or via psql against
-- the project's direct connection string) before running
-- app/data/backfill_assists.py.
--
-- assists means pass.goal_assist == True (the pass immediately preceding a
-- goal) -- narrower than the existing key_passes/xa, which also count
-- shot_assist passes whose shot never went in. See pipeline_v2.py.
alter table player_match_stats
  add column if not exists assists integer not null default 0;
