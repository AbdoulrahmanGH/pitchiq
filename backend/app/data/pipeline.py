import json
import os
import pandas as pd
from supabase import create_client
from app.config import SUPABASE_URL, SUPABASE_KEY

def extract():
    base_dir = os.path.dirname(__file__)
    seed_path = os.path.join(base_dir, "seed.json")

    with open(seed_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Extracted {len(data)} matches from seed.json")
    return data


def transform(data):
    matches = []
    player_stats = []
    team_stats = []

    for match in data:
        is_home = match["home_team"] == "Al Qadsiah FC"
        opponent = match["away_team"] if is_home else match["home_team"]
        goals_scored = match["score"]["home"] if is_home else match["score"]["away"]
        goals_conceded = match["score"]["away"] if is_home else match["score"]["home"]
        result = (
            "win" if goals_scored > goals_conceded
            else "draw" if goals_scored == goals_conceded
            else "loss"
        )

        matches.append({
            "id": match["match_id"],
            "date": match["date"],
            "opponent": opponent,
            "home_away_neutral": "home" if is_home else "away",
            "result": result,
            "goals_scored": goals_scored,
            "goals_conceded": goals_conceded,
            "stadium": match["venue"]
        })

        for p in match["player_performances"]:
            player_stats.append({
                "id": f"pms-{match['match_id']}-{p['player_id']}",
                "match_id": match["match_id"],
                "player_id": p["player_id"],
                "minutes_played": p["minutes_played"],
                "distance_covered": p["distance_covered_km"],
                "sprints": p["sprints"],
                "passes": p["passes_attempted"],
                "shots": p["shots"],
                "goals": p["goals"],
                "assists": p["assists"],
                "expected_goals": p.get("expected_goals", 0.0),
                "expected_assists": p.get("expected_assists", 0.0),
                "expected_saves": p.get("expected_saves", 0.0),
                "key_passes": p.get("key_passes", 0),
                "progressive_carries": p.get("progressive_carries", 0),
                "dribbles_attempted": p.get("dribbles_attempted", 0),
                "dribbles_completed": p.get("dribbles_completed", 0),
                "tackles": p.get("tackles", 0),
            })

        team_stats.append({
            "id": f"tms-{match['match_id']}",
            "match_id": match["match_id"],
            "possession": match.get("possession", 50.0),
            "total_distance": match.get("total_distance", 110.0),
            "shots_on_target": match.get("shots_on_target", 0)
        })

    matches_df = pd.DataFrame(matches)
    player_df = pd.DataFrame(player_stats)
    team_df = pd.DataFrame(team_stats)

    print(f"Transformed: {len(matches_df)} matches, {len(player_df)} player rows, {len(team_df)} team rows")
    return matches_df, player_df, team_df


def load(matches_df, player_df, team_df):
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    supabase.table("matches").insert(matches_df.to_dict(orient="records")).execute()
    print("Loaded matches")

    supabase.table("player_match_stats").insert(player_df.to_dict(orient="records")).execute()
    print("Loaded player_match_stats")

    supabase.table("team_match_stats").insert(team_df.to_dict(orient="records")).execute()
    print("Loaded team_match_stats")

    print("Pipeline complete.")


def run():
    data = extract()
    matches_df, player_df, team_df = transform(data)
    load(matches_df, player_df, team_df)


if __name__ == "__main__":
    run()