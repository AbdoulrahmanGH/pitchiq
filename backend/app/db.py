from supabase import create_client

from app.config import SUPABASE_KEY, SUPABASE_URL


def get_db():
    return create_client(SUPABASE_URL, SUPABASE_KEY)
