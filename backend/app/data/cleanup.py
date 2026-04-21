import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from app.config import SUPABASE_URL, SUPABASE_KEY
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

placeholder_ids = ['player-023', 'player-024', 'player-025', 'player-026']

for pid in placeholder_ids:
    result = supabase.table('player_match_stats').delete().eq('player_id', pid).execute()
    print(f"Deleted rows for {pid}: {result.data}")

print("Cleanup complete.")
