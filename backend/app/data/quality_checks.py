"""Data quality checks run at the end of every load.

Exists specifically to catch the kind of stale-write issue found by hand
during the Secret Manager migration step -- a handful of players'
primary_position silently stuck at NULL in Supabase despite correct
transform output -- automatically, on every run, instead of relying on
someone noticing.
"""

class QualityCheckFailure(Exception):
    pass


def find_null_primary_positions(client, team_id):
    # Scoped to our own roster: real StatsBomb data has ~80 opponent bench
    # players league-wide who genuinely have no recorded position (they
    # never started and never touched the ball), which is a known data
    # limitation, not a write failure. Our own roster should always resolve.
    pms_rows = client.table("player_match_stats").select("player_id").eq(
        "team_id", team_id
    ).execute().data
    player_ids = sorted({r["player_id"] for r in pms_rows})
    if not player_ids:
        return []

    players_rows = client.table("players").select(
        "id, name, primary_position"
    ).in_("id", player_ids).execute().data
    return [p for p in players_rows if not p.get("primary_position")]


def find_null_team_names(client):
    teams_rows = client.table("teams").select("id, name").execute().data
    return [t for t in teams_rows if not t.get("name")]


def find_matches_missing_scores(client):
    matches_rows = client.table("matches").select(
        "id, date, home_score, away_score"
    ).execute().data
    return [
        m for m in matches_rows
        if m.get("home_score") is None or m.get("away_score") is None
    ]


def run_quality_checks(client, team_id):
    """Returns {check_name: offending_rows} for every failing check. An
    empty dict means the load is clean."""
    failures = {}

    null_positions = find_null_primary_positions(client, team_id)
    if null_positions:
        failures["null_primary_position"] = null_positions

    null_team_names = find_null_team_names(client)
    if null_team_names:
        failures["null_team_names"] = null_team_names

    missing_scores = find_matches_missing_scores(client)
    if missing_scores:
        failures["matches_missing_scores"] = missing_scores

    return failures


def assert_quality(client, team_id):
    """Logs and raises QualityCheckFailure if any check fails. Call at the
    end of a load; the caller should let this propagate so the job process
    exits non-zero rather than silently succeeding."""
    failures = run_quality_checks(client, team_id)

    if failures:
        print("DATA QUALITY CHECK FAILED:")
        for check, rows in failures.items():
            print(f"  [{check}] {len(rows)} row(s): {rows}")
        summary = "; ".join(f"{k} ({len(v)} row(s))" for k, v in failures.items())
        raise QualityCheckFailure(f"Data quality check failed: {summary}")

    print("Data quality checks passed: no null primary_position on our roster, "
          "no null team names, no matches missing scores.")
