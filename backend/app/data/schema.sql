CREATE TABLE matches (
    id TEXT PRIMARY KEY,
    date DATE,
    opponent TEXT,
    home_away_neutral TEXT check (home_away_neutral IN ('home', 'away', 'neutral')),
    result TEXT CHECK (result IN ('win', 'draw', 'loss')),
    goals_scored INTEGER DEFAULT 0,
    goals_conceded INTEGER DEFAULT 0,
    stadium TEXT
) CREATE TABLE player_match_stats (
    id TEXT PRIMARY KEY,
    match_id text NOT NULL,
    player_id text not null,
    minutes_played INTEGER NOT NULL,
    distance_covered real,
    sprints integer default 0,
    passes integer default 0,
    shots integer default 0,
    goals integer default 0,
    assists integer default 0,
    foreign key (match_id) references matches(id) on delete cascade
) create table team_match_stats(
    id text primary key,
    match_id text not null,
    possession real check (
        possession >= 0
        and possession <= 100
    ),
    total_distance real,
    shots_on_target integer not null default 0,
    foreign key (match_id) references matches(id) on delete cascade
)