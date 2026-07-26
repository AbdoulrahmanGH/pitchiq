-- schema_v2.sql is the source of truth for fresh installs and already
-- includes this table; this migration exists to bring an already-created
-- pitchiq-v2-dev database (created before this table existed) up to date.
--
-- There is no migration runner wired up in this project yet, so this file
-- must be run by hand once, in the Supabase SQL editor (or via psql against
-- the project's direct connection string).
--
-- Caches the BigQuery window-function analytics query results (season
-- rankings, rolling xG trend -- see app/data/bigquery_analytics_v2.py) so
-- GET /api/analytics/rankings and /api/analytics/trends never query
-- BigQuery on the request path.
create table if not exists analytics_cache (
  id bigserial primary key,
  query_name text not null,
  computed_at timestamptz not null default now(),
  payload jsonb not null
);

create index if not exists idx_analytics_cache_lookup
  on analytics_cache (query_name, computed_at desc);
