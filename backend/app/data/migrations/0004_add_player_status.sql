-- schema_v2.sql is the source of truth for fresh installs and already
-- includes this table; this migration exists to bring an already-created
-- pitchiq-v2-dev database (created before this table existed) up to date.
--
-- There is no migration runner wired up in this project yet, so this file
-- must be run by hand once, in the Supabase SQL editor (or via psql against
-- the project's direct connection string).
--
-- One row per player: their current availability as set by the coaching
-- staff, independent of the fatigue-risk rule (which is computed from match
-- data, see app/services/fatigue.py). player_id is the primary key -- Coach
-- sets a player's *current* status, not a history of past ones, so the
-- POST /api/players/status handler upserts in place rather than appending.
create table if not exists player_status (
  player_id integer primary key references players(id),
  status text not null check (status in ('available', 'doubtful', 'unavailable')),
  note text,
  updated_by uuid references auth.users(id),
  updated_at timestamptz not null default now()
);
