"""v2 extract + transform for StatsBomb open data (La Liga 2015/16, Barcelona).

No database writes here: `run()` writes each output table to a CSV under
backend/app/data/output/ for manual inspection.

Metric definitions (confirmed against football-docs, see tests/test_transform.py):
- StatsBomb pitch is 120x80 yards; the acting team always attacks toward x=120.
- xG is read from shot.statsbomb_xg, xA is the xG of shots assisted by a
  player's passes (pass.assisted_shot_id).
- assists counts pass.goal_assist == True only (the shot from that pass was
  a goal) -- narrower than key_passes/xa, which also count shot_assist
  passes whose shot never went in.
- PPDA = opponent passes attempted in the pressing zone / pressing team's
  tackles + interceptions + fouls committed in that zone. The zone starts 40%
  of pitch length from the pressing team's own goal: pressing-team actions at
  x >= 48 (own frame), opponent passes at x <= 72 (opponent's frame).
- Progressive pass/carry (Wyscout): ball ends >= 30m closer to the opponent
  goal when both ends are in the team's own half, >= 15m when the movement
  spans the halves, >= 10m when both ends are in the opponent's half.
- Field tilt: a team's share of final-third touches (Pass/Carry/Shot/Dribble
  events with x >= 80), as a percentage.
- Pressure regain: a subsequent event within 5s of a Pressure (same period)
  whose possession_team is the pressing team.
- Ratio metrics with a zero denominator are null, never 0; count metrics
  default to 0.

match_events expected volume (full 38-match run, verified 2026-07-28):
71,506 rows = 38,830 Pass + 31,704 Carry + 972 Shot. This is the CORRECT
count since the Pass/Carry expansion (every Pass with recipient_id, every
Carry with end coordinates -- previously only key passes and shots were
stored, 1,673 rows total). A future run landing near ~1.7k again would be a
REGRESSION to the old extraction, not a cleanup. 36,737 of the Pass rows
carry a recipient_id (completed passes; incomplete ones have no recipient
in StatsBomb).
"""

import json
import math
import os
import uuid
from datetime import datetime, timezone

import ijson
import pandas as pd
import requests
from google.cloud import bigquery, storage

from app.data.bigquery_analytics_v2 import (
    DATASET as BQ_DATASET,
    MIRROR_TABLES as BQ_MIRROR_TABLES,
    PROJECT as BQ_PROJECT,
    mirror_to_bigquery,
    run_analytics_and_cache,
)
from app.data.load_v2 import load as load_to_supabase
from app.data.quality_checks import assert_bigquery_mirror_quality, assert_quality
from app.db import get_db

BASE_URL = "https://raw.githubusercontent.com/hudl/open-data/master/data"
COMPETITION_ID = 11
SEASON_ID = 27
BARCELONA_TEAM_ID = 217
MATCH_LIMIT = None  # None = process every Barcelona match in the competition/season

# Raw-data landing zone. Every run lands the exact JSON it fetched from
# StatsBomb here first, under a run-scoped prefix -- a durable, inspectable
# record of what was actually ingested -- and transform() reads back from
# here rather than consuming extract()'s in-memory return value directly.
GCS_RAW_BUCKET = os.environ.get("STATSBOMB_RAW_BUCKET", "pitchiq-v2-statsbomb-raw")

KEEP_EVENT_TYPES = {
    "Pass", "Shot", "Dribble", "Carry", "Pressure", "Duel", "Interception",
    "Foul Committed", "Foul Won", "Starting XI", "Substitution",
}

YARDS_TO_METERS = 0.9144
GOAL = (120.0, 40.0)
PPDA_DEF_ACTION_MIN_X = 48.0   # 40% of pitch length from own goal, forward
PPDA_OPP_PASS_MAX_X = 72.0     # the same zone seen from the opponent's frame
FINAL_THIRD_X = 80.0
TOUCH_EVENT_TYPES = {"Pass", "Carry", "Shot", "Dribble"}
DUEL_WON_OUTCOMES = {"Won", "Success", "Success In Play", "Success Out"}


# --------------------------------- helpers ----------------------------------

def _ts_seconds(event):
    h, m, s = event["timestamp"].split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _dist_to_goal(x, y):
    return math.hypot(GOAL[0] - x, GOAL[1] - y)


def _is_progressive(start, end):
    """Wyscout progressive pass/run rule, thresholds in meters."""
    gain_m = (_dist_to_goal(*start) - _dist_to_goal(*end)) * YARDS_TO_METERS
    start_own, end_own = start[0] <= 60.0, end[0] <= 60.0
    if start_own and end_own:
        threshold = 30.0
    elif not start_own and not end_own:
        threshold = 10.0
    else:
        threshold = 15.0
    return gain_m >= threshold


def _pass_completed(event):
    return "outcome" not in event.get("pass", {})


# --------------------------------- extract ----------------------------------

def fetch_matches(competition_id=COMPETITION_ID, season_id=SEASON_ID):
    url = f"{BASE_URL}/matches/{competition_id}/{season_id}.json"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def fetch_events(match_id):
    """Stream-parse an events file, keeping only KEEP_EVENT_TYPES in memory."""
    url = f"{BASE_URL}/events/{match_id}.json"
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    resp.raw.decode_content = True
    kept = []
    for event in ijson.items(resp.raw, "item", use_float=True):
        if event.get("type", {}).get("name") in KEEP_EVENT_TYPES:
            kept.append(event)
    return kept


def fetch_lineups(match_id):
    url = f"{BASE_URL}/lineups/{match_id}.json"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def extract(limit=MATCH_LIMIT):
    all_matches = fetch_matches()
    barca = [
        m for m in all_matches
        if BARCELONA_TEAM_ID in (m["home_team"]["home_team_id"],
                                 m["away_team"]["away_team_id"])
    ]
    barca.sort(key=lambda m: (m["match_date"], m["match_id"]))
    selected = barca[:limit] if limit else barca
    print(f"{len(barca)} Barcelona matches found; processing {len(selected)}")

    events_by_match, lineups_by_match = {}, {}
    for m in selected:
        mid = m["match_id"]
        events_by_match[mid] = fetch_events(mid)
        lineups_by_match[mid] = fetch_lineups(mid)
        print(f"match {mid} ({m['home_team']['home_team_name']} vs "
              f"{m['away_team']['away_team_name']}): "
              f"{len(events_by_match[mid])} kept events")
    return selected, events_by_match, lineups_by_match


# -------------------------------- transform ---------------------------------

def _new_player_stat(match_id, player_id, team_id, position):
    return {
        "match_id": match_id, "player_id": player_id, "team_id": team_id,
        "position": position, "minutes_played": 0,
        "passes_attempted": 0, "passes_completed": 0, "key_passes": 0,
        "progressive_passes": 0, "shots": 0, "goals": 0, "assists": 0,
        "xg": 0.0, "xa": 0.0,
        "dribbles_attempted": 0, "dribbles_completed": 0,
        "progressive_carries": 0, "tackles": 0, "interceptions": 0,
        "pressures": 0, "pressure_regains": 0, "duels_won": 0,
        "fouls_committed": 0, "fouls_won": 0,
    }


def _minutes_played(events, match_length):
    """Minutes per player from Starting XI and Substitution events."""
    minutes = {}
    for e in events:
        if e["type"]["name"] == "Starting XI":
            for entry in e.get("tactics", {}).get("lineup", []):
                minutes[entry["player"]["id"]] = match_length
    for e in events:
        if e["type"]["name"] == "Substitution":
            off_id = e["player"]["id"]
            if off_id in minutes:
                minutes[off_id] = min(minutes[off_id], e["minute"])
            replacement = e["substitution"]["replacement"]
            minutes[replacement["id"]] = match_length - e["minute"]
    return minutes


def _transform_match(match, events, lineups, teams, players,
                     player_stats, team_stats, match_events):
    match_id = match["match_id"]
    home_id = match["home_team"]["home_team_id"]
    away_id = match["away_team"]["away_team_id"]

    teams[home_id] = {"id": home_id,
                      "name": match["home_team"]["home_team_name"],
                      "country": match["home_team"].get("country", {}).get("name")}
    teams[away_id] = {"id": away_id,
                      "name": match["away_team"]["away_team_name"],
                      "country": match["away_team"].get("country", {}).get("name")}

    positions = {}
    for e in events:
        if e["type"]["name"] == "Starting XI":
            for entry in e.get("tactics", {}).get("lineup", []):
                positions[entry["player"]["id"]] = entry["position"]["name"]
    # Substitutes never appear in a Starting XI lineup. Fall back to the
    # `position` field StatsBomb attaches to any on-ball event, so a player
    # who only ever came off the bench still gets a position.
    for e in events:
        pid = e.get("player", {}).get("id")
        pos = e.get("position", {}).get("name")
        if pid is not None and pos and pid not in positions:
            positions[pid] = pos

    player_team = {}
    for team_lineup in lineups:
        for p in team_lineup["lineup"]:
            pid = p["player_id"]
            player_team[pid] = team_lineup["team_id"]
            if pid not in players:
                players[pid] = {"id": pid, "name": p["player_name"],
                                "nickname": p.get("player_nickname"),
                                "primary_position": positions.get(pid)}
            elif players[pid]["primary_position"] is None:
                players[pid]["primary_position"] = positions.get(pid)

    match_length = max(90, max((e["minute"] for e in events), default=90))
    minutes = _minutes_played(events, match_length)

    stats = {}

    def stat(player_id, team_id):
        if player_id not in stats:
            stats[player_id] = _new_player_stat(
                match_id, player_id, team_id, positions.get(player_id))
        return stats[player_id]

    for pid, mins in minutes.items():
        team_id = player_team.get(pid)
        if team_id is None:
            for e in events:
                if e.get("player", {}).get("id") == pid:
                    team_id = e["team"]["id"]
                    break
        stat(pid, team_id)["minutes_played"] = mins

    shot_xg_by_id = {
        e["id"]: e["shot"].get("statsbomb_xg", 0.0)
        for e in events if e["type"]["name"] == "Shot"
    }

    per_team = {
        tid: {"passes_attempted": 0, "passes_completed": 0, "shots": 0,
              "xg": 0.0, "final_third_touches": 0,
              "ppda_passes": 0, "ppda_def_actions": 0}
        for tid in (home_id, away_id)
    }

    timed = sorted(events, key=lambda e: (e["period"], _ts_seconds(e), e["index"]))

    for e in events:
        etype = e["type"]["name"]
        team_id = e["team"]["id"]
        pid = e.get("player", {}).get("id")
        loc = e.get("location")
        ps = stat(pid, team_id) if pid is not None else None
        ts = per_team[team_id]

        if loc and etype in TOUCH_EVENT_TYPES and loc[0] >= FINAL_THIRD_X:
            ts["final_third_touches"] += 1

        if etype == "Pass":
            pas = e["pass"]
            ts["passes_attempted"] += 1
            ps["passes_attempted"] += 1
            if _pass_completed(e):
                ts["passes_completed"] += 1
                ps["passes_completed"] += 1
            if pas.get("shot_assist") or pas.get("goal_assist"):
                ps["key_passes"] += 1
                ps["xa"] += shot_xg_by_id.get(pas.get("assisted_shot_id"), 0.0)
            if pas.get("goal_assist"):
                ps["assists"] += 1
            if loc and _is_progressive(loc, pas["end_location"]):
                ps["progressive_passes"] += 1
            if loc and loc[0] <= PPDA_OPP_PASS_MAX_X:
                ts["ppda_passes"] += 1
            # Every Pass lands in match_events (not just key passes), with
            # the receiver resolved from pass.recipient -- incomplete passes
            # have no recipient in StatsBomb and stay null. Powers the pass
            # network and (via the same _is_progressive rule, applied at
            # query time) the progressive-actions map.
            if loc:
                match_events.append({
                    "match_id": match_id, "player_id": pid, "team_id": team_id,
                    "event_type": "Pass", "minute": e["minute"],
                    "x": loc[0], "y": loc[1],
                    "end_x": pas["end_location"][0], "end_y": pas["end_location"][1],
                    "outcome": pas.get("outcome", {}).get("name", "Complete"),
                    "xg": None,
                    "recipient_id": pas.get("recipient", {}).get("id"),
                    "under_pressure": bool(e.get("under_pressure", False)),
                })

        elif etype == "Shot":
            shot = e["shot"]
            xg = shot.get("statsbomb_xg", 0.0)
            ts["shots"] += 1
            ts["xg"] += xg
            ps["shots"] += 1
            ps["xg"] += xg
            if shot.get("outcome", {}).get("name") == "Goal":
                ps["goals"] += 1
            end = shot.get("end_location", [None, None])
            match_events.append({
                "match_id": match_id, "player_id": pid, "team_id": team_id,
                "event_type": "Shot", "minute": e["minute"],
                "x": loc[0], "y": loc[1],
                "end_x": end[0], "end_y": end[1],
                "outcome": shot.get("outcome", {}).get("name"),
                "xg": xg,
                "recipient_id": None,
                "under_pressure": bool(e.get("under_pressure", False)),
            })

        elif etype == "Carry":
            end = e["carry"]["end_location"]
            if loc and _is_progressive(loc, end):
                ps["progressive_carries"] += 1
            if loc:
                match_events.append({
                    "match_id": match_id, "player_id": pid, "team_id": team_id,
                    "event_type": "Carry", "minute": e["minute"],
                    "x": loc[0], "y": loc[1],
                    "end_x": end[0], "end_y": end[1],
                    "outcome": None,
                    "xg": None,
                    "recipient_id": None,
                    "under_pressure": bool(e.get("under_pressure", False)),
                })

        elif etype == "Dribble":
            ps["dribbles_attempted"] += 1
            if e["dribble"].get("outcome", {}).get("name") == "Complete":
                ps["dribbles_completed"] += 1

        elif etype == "Duel":
            in_zone = loc and loc[0] >= PPDA_DEF_ACTION_MIN_X
            if e.get("duel", {}).get("type", {}).get("name") == "Tackle":
                ps["tackles"] += 1
                if in_zone:
                    ts["ppda_def_actions"] += 1
            if e.get("duel", {}).get("outcome", {}).get("name") in DUEL_WON_OUTCOMES:
                ps["duels_won"] += 1

        elif etype == "Interception":
            ps["interceptions"] += 1
            if loc and loc[0] >= PPDA_DEF_ACTION_MIN_X:
                ts["ppda_def_actions"] += 1

        elif etype == "Foul Committed":
            if ps:
                ps["fouls_committed"] += 1
            if loc and loc[0] >= PPDA_DEF_ACTION_MIN_X:
                ts["ppda_def_actions"] += 1

        elif etype == "Foul Won":
            ps["fouls_won"] += 1

        elif etype == "Pressure":
            ps["pressures"] += 1
            t0 = _ts_seconds(e)
            for e2 in timed:
                if e2["period"] != e["period"]:
                    continue
                t2 = _ts_seconds(e2)
                if t2 <= t0 or t2 > t0 + 5:
                    continue
                if e2["possession_team"]["id"] == team_id:
                    ps["pressure_regains"] += 1
                    break

    total_passes = sum(t["passes_attempted"] for t in per_team.values())
    total_ft_touches = sum(t["final_third_touches"] for t in per_team.values())
    for team_id, opp_id in ((home_id, away_id), (away_id, home_id)):
        t, opp = per_team[team_id], per_team[opp_id]
        team_stats.append({
            "match_id": match_id,
            "team_id": team_id,
            "possession_pct": (100.0 * t["passes_attempted"] / total_passes
                               if total_passes else None),
            "ppda": (opp["ppda_passes"] / t["ppda_def_actions"]
                     if t["ppda_def_actions"] else None),
            "field_tilt_pct": (100.0 * t["final_third_touches"] / total_ft_touches
                               if total_ft_touches else None),
            "shots": t["shots"],
            "xg": t["xg"],
            "pass_completion_pct": (100.0 * t["passes_completed"] / t["passes_attempted"]
                                    if t["passes_attempted"] else None),
        })

    player_stats.extend(stats.values())


def transform(matches, events_by_match, lineups_by_match):
    """Turn raw StatsBomb matches/events/lineups into schema_v2 tables.

    Returns a dict of DataFrames keyed by table name: teams, players,
    matches, player_match_stats, team_match_stats, match_events.
    """
    teams, players = {}, {}
    match_rows, player_stats, team_stats, match_events = [], [], [], []

    for match in matches:
        match_id = match["match_id"]
        match_rows.append({
            "id": match_id,
            "competition_id": match["competition"]["competition_id"],
            "competition_name": match["competition"]["competition_name"],
            "season_id": match["season"]["season_id"],
            "season_name": match["season"]["season_name"],
            "date": match["match_date"],
            "home_team_id": match["home_team"]["home_team_id"],
            "away_team_id": match["away_team"]["away_team_id"],
            "home_score": match["home_score"],
            "away_score": match["away_score"],
            "stadium": (match.get("stadium") or {}).get("name"),
            "match_week": match.get("match_week"),
        })
        _transform_match(match, events_by_match[match_id],
                         lineups_by_match[match_id], teams, players,
                         player_stats, team_stats, match_events)

    match_events_df = pd.DataFrame(match_events)
    if not match_events_df.empty:
        # Nullable Int64, not int64: recipient_id is null on every non-Pass
        # row, and plain int64-with-NaN silently becomes float64 -- which
        # Postgres then rejects ('invalid input syntax for type integer:
        # "6606.0"') on load.
        match_events_df["recipient_id"] = match_events_df["recipient_id"].astype("Int64")

    return {
        "teams": pd.DataFrame(sorted(teams.values(), key=lambda t: t["id"])),
        "players": pd.DataFrame(sorted(players.values(), key=lambda p: p["id"])),
        "matches": pd.DataFrame(match_rows),
        "player_match_stats": pd.DataFrame(player_stats),
        "team_match_stats": pd.DataFrame(team_stats),
        "match_events": match_events_df,
    }


# ------------------------------- GCS landing --------------------------------

def _run_prefix():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"raw/{stamp}-{uuid.uuid4().hex[:8]}"


def _upload_json(bucket, path, data):
    bucket.blob(path).upload_from_string(json.dumps(data), content_type="application/json")


def _download_json(bucket, path):
    return json.loads(bucket.blob(path).download_as_text())


def land_raw_data_in_gcs(matches, events_by_match, lineups_by_match,
                         storage_client=None, bucket_name=GCS_RAW_BUCKET):
    """Writes exactly what extract() fetched from StatsBomb to GCS, under a
    run-scoped prefix so successive runs don't clobber each other's record.
    """
    client = storage_client or storage.Client()
    bucket = client.bucket(bucket_name)
    run_prefix = _run_prefix()

    _upload_json(bucket, f"{run_prefix}/matches.json", matches)
    for m in matches:
        mid = m["match_id"]
        _upload_json(bucket, f"{run_prefix}/events/{mid}.json", events_by_match[mid])
        _upload_json(bucket, f"{run_prefix}/lineups/{mid}.json", lineups_by_match[mid])

    print(f"Landed raw StatsBomb data for {len(matches)} matches in "
          f"gs://{bucket_name}/{run_prefix}/")
    return run_prefix


def read_raw_from_gcs(run_prefix, storage_client=None, bucket_name=GCS_RAW_BUCKET):
    """Reads back exactly what land_raw_data_in_gcs() just wrote. This is
    transform()'s actual data source for a pipeline run -- not a fresh
    GitHub fetch."""
    client = storage_client or storage.Client()
    bucket = client.bucket(bucket_name)

    matches = _download_json(bucket, f"{run_prefix}/matches.json")
    events_by_match, lineups_by_match = {}, {}
    for m in matches:
        mid = m["match_id"]
        events_by_match[mid] = _download_json(bucket, f"{run_prefix}/events/{mid}.json")
        lineups_by_match[mid] = _download_json(bucket, f"{run_prefix}/lineups/{mid}.json")

    print(f"Read raw StatsBomb data for {len(matches)} matches back from "
          f"gs://{bucket_name}/{run_prefix}/")
    return matches, events_by_match, lineups_by_match


# ----------------------------------- run ------------------------------------

def run(write_csv=True, write_db=True):
    matches, events_by_match, lineups_by_match = extract()
    run_prefix = land_raw_data_in_gcs(matches, events_by_match, lineups_by_match)
    matches, events_by_match, lineups_by_match = read_raw_from_gcs(run_prefix)
    tables = transform(matches, events_by_match, lineups_by_match)

    if write_csv:
        out_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(out_dir, exist_ok=True)
        print("\nRow counts (CSV):")
        for name, df in tables.items():
            path = os.path.join(out_dir, f"{name}.csv")
            df.to_csv(path, index=False)
            print(f"  {name}: {len(df)} rows -> {path}")

    if write_db:
        db_client = get_db()

        print("\nLoading into Supabase...")
        counts = load_to_supabase(tables, client=db_client)
        print("Row counts (Supabase load):")
        for name, count in counts.items():
            print(f"  {name}: {count} rows")

        print("\nRunning data quality checks...")
        assert_quality(db_client, BARCELONA_TEAM_ID)

        # Everything below here is the BigQuery analytics stage: a mirror
        # of matches/player_match_stats/team_match_stats, verified against
        # Postgres, then the two window-function queries cached for the
        # API. It only runs once the Postgres load and quality checks
        # above have already succeeded -- assert_quality raising propagates
        # straight out of run(), so this stage never executes against a
        # load that didn't pass.
        bq_client = bigquery.Client(project=BQ_PROJECT)

        print("\nMirroring to BigQuery...")
        mirror_to_bigquery(supabase_client=db_client, bq_client=bq_client)

        print("\nVerifying BigQuery mirror against Postgres...")
        assert_bigquery_mirror_quality(
            db_client, bq_client, BQ_PROJECT, BQ_DATASET, BQ_MIRROR_TABLES
        )

        print("\nRunning BigQuery analytics queries and caching results...")
        run_analytics_and_cache(bq_client=bq_client, supabase_client=db_client)

    return tables


if __name__ == "__main__":
    run()
