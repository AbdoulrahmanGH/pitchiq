"""One-off backfill for player_match_stats.assists (migrations/0001).

Assists were never extracted before that column existed -- pipeline_v2's
Pass handling only ever tracked shot_assist OR goal_assist together, as
key_passes/xa. This script re-fetches each Barcelona match's events (the
same StatsBomb source pipeline_v2 reads from) and counts strictly
pass.goal_assist == True per player, then updates the already-loaded
player_match_stats rows in place.

Run once, after applying migrations/0001_add_player_match_stats_assists.sql
against the database:

    python -m app.data.backfill_assists
"""

from collections import Counter

from app.data.pipeline_v2 import BARCELONA_TEAM_ID, fetch_events, fetch_matches
from app.db import get_db


def count_goal_assists(events):
    """{player_id: assist_count} for one match's kept events."""
    counts = Counter()
    for e in events:
        if e["type"]["name"] != "Pass":
            continue
        if e["pass"].get("goal_assist"):
            counts[e["player"]["id"]] += 1
    return dict(counts)


def run():
    client = get_db()
    all_matches = fetch_matches()
    barca_matches = [
        m for m in all_matches
        if BARCELONA_TEAM_ID in (m["home_team"]["home_team_id"],
                                  m["away_team"]["away_team_id"])
    ]

    total_updates = 0
    for m in barca_matches:
        match_id = m["match_id"]
        counts = count_goal_assists(fetch_events(match_id))
        for player_id, assists in counts.items():
            client.table("player_match_stats").update({"assists": assists}).eq(
                "match_id", match_id
            ).eq("player_id", player_id).execute()
            total_updates += 1
        print(f"match {match_id}: {len(counts)} players with assists")

    print(f"Backfilled assists for {total_updates} (match, player) rows "
          f"across {len(barca_matches)} matches")


if __name__ == "__main__":
    run()
