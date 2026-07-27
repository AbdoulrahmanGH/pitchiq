-- Row Level Security is deliberately NOT enabled on any table here. The
-- frontend never talks to Supabase directly -- every request goes through
-- FastAPI, which authenticates the caller and checks their role itself
-- (see backend/app/auth.py). RLS would be defense in depth against an
-- attack surface (direct client-to-Supabase access) that doesn't exist in
-- this design, so it's skipped rather than maintained as dead policy.

create table teams (
  id integer primary key,
  name text not null,
  country text
);

create table players (
  id integer primary key,
  name text not null,
  nickname text,
  primary_position text
);

create table matches (
  id integer primary key,
  competition_id integer not null,
  competition_name text not null,
  season_id integer not null,
  season_name text not null,
  date date,
  home_team_id integer references teams(id),
  away_team_id integer references teams(id),
  home_score integer,
  away_score integer,
  stadium text,
  match_week integer
);

create table player_match_stats (
  id bigserial primary key,
  match_id integer references matches(id) on delete cascade,
  player_id integer references players(id),
  team_id integer references teams(id),
  position text,
  minutes_played integer not null default 0,
  passes_attempted integer not null default 0,
  passes_completed integer not null default 0,
  key_passes integer not null default 0,
  progressive_passes integer not null default 0,
  shots integer not null default 0,
  goals integer not null default 0,
  assists integer not null default 0,
  xg real not null default 0,
  xa real not null default 0,
  dribbles_attempted integer not null default 0,
  dribbles_completed integer not null default 0,
  progressive_carries integer not null default 0,
  tackles integer not null default 0,
  interceptions integer not null default 0,
  pressures integer not null default 0,
  pressure_regains integer not null default 0,
  duels_won integer not null default 0,
  fouls_committed integer not null default 0,
  fouls_won integer not null default 0,
  -- Every real pipeline run does a full delete-then-reinsert of this
  -- table for every match (see load_v2.reload_table_for_matches), so
  -- MAX(loaded_at) is a true "when did Postgres last get written" signal
  -- with no application code needed to maintain it -- the DEFAULT alone
  -- is enough, since these rows are never upserted in place.
  loaded_at timestamptz not null default now()
);

create table team_match_stats (
  id bigserial primary key,
  match_id integer references matches(id) on delete cascade,
  team_id integer references teams(id),
  possession_pct real,
  ppda real,
  field_tilt_pct real,
  shots integer not null default 0,
  xg real not null default 0,
  pass_completion_pct real
);

create table match_events (
  id bigserial primary key,
  match_id integer references matches(id) on delete cascade,
  player_id integer references players(id),
  team_id integer references teams(id),
  event_type text not null,
  minute integer,
  x real, y real,
  end_x real, end_y real,
  outcome text,
  xg real,
  under_pressure boolean not null default false,
  -- added by the recipient_id migration (run manually): the receiving
  -- player of a completed Pass, from StatsBomb's pass.recipient. Null for
  -- incomplete passes and for every non-Pass event type.
  recipient_id integer references players(id)
);

create table rules (
  rule_key text primary key,
  description text not null,
  threshold real not null,
  rule_type text not null
);

create table scouting_notes (
  id bigserial primary key,
  player_id integer references players(id),
  author_id uuid references auth.users(id),
  note text not null,
  rating integer,
  created_at timestamptz not null default now()
);

create table user_roles (
  user_id uuid primary key references auth.users(id),
  role text not null check (role in ('analyst','coach','scout'))
);

create table player_status (
  player_id integer primary key references players(id),
  status text not null check (status in ('available', 'doubtful', 'unavailable')),
  note text,
  updated_by uuid references auth.users(id),
  updated_at timestamptz not null default now()
);

-- Results of the BigQuery window-function analytics queries (season
-- rankings, rolling xG trend -- see app/data/bigquery_analytics_v2.py),
-- cached here so the API never queries BigQuery on the request path. Each
-- run appends a new row rather than updating in place; readers take the
-- latest row per query_name. payload shape is query-specific and is not
-- itself modeled in SQL -- it's whatever list of dicts that query produced,
-- JSON-serialized.
create table analytics_cache (
  id bigserial primary key,
  query_name text not null,
  computed_at timestamptz not null default now(),
  payload jsonb not null
);

create index idx_analytics_cache_lookup on analytics_cache (query_name, computed_at desc);
