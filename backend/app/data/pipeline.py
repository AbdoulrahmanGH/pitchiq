import json
import os
import pandas as pd

#extract data from seed.json 
def extract():
    base_dir = os.path.dirname(__file__)
    seed_path = os.path.join(base_dir, "seed.json")
 
    with open(seed_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"Extracted {len(data)} matches from seed.json")
    return data   


#tranform the data
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
        'win' if goals_scored > goals_conceded
        else 'draw' if goals_scored == goals_conceded
        else 'loss'
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
                "assists": p["assists"]
            })   
    
    matches_df = pd.DataFrame(matches)
    
    # we'll do player and team dataframes after
    return matches_df    
 
# #load()
# #takes those 3 dataframes and inserts them into Supabase sql db
 
# def load(matches_df, player_df, team_df):
#     return ('store in db...', matches_df, player_df, team_df)
 
# #run()
# #main entry point to finally run the pipeline
 
# def run():
#     data = extract()  
#     matches_df, player_df, team_df =   transform(data)
#     load (matches_df, player_df, team_df)
    
# if __name__ == "__main__":
#     run()    
    

