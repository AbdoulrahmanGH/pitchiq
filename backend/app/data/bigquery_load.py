import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from google.cloud import bigquery
from supabase import create_client
from app.config import SUPABASE_URL, SUPABASE_KEY

PROJECT = "pitchiq-494423"
DATASET = "pitchiq_analytics"

TABLES = ["matches", "team_match_stats", "player_match_stats"]


def fetch_from_supabase(supabase, table_name: str) -> list[dict]:
    response = supabase.table(table_name).select("*").execute()
    return response.data


def load_to_bigquery(client: bigquery.Client, table_name: str, rows: list[dict]) -> None:
    table_ref = f"{PROJECT}.{DATASET}.{table_name}"

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True,
    )

    job = client.load_table_from_json(rows, table_ref, job_config=job_config)
    job.result()

    loaded = client.get_table(table_ref).num_rows
    print(f"  {table_name}: {loaded} rows loaded")


def run():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    bq = bigquery.Client(project=PROJECT)

    for table_name in TABLES:
        print(f"Loading {table_name}...")
        rows = fetch_from_supabase(supabase, table_name)
        if not rows:
            print(f"  {table_name}: no rows found, skipping")
            continue
        load_to_bigquery(bq, table_name, rows)

    print("Done.")


if __name__ == "__main__":
    run()
