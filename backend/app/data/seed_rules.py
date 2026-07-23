"""Seeds the `rules` table with the two fatigue thresholds.

Values are MIA's documented combined rule, not tuned/invented numbers:
short rest (< 3 days) AND high recent workload (>= 180 minutes across the
team's last 3 fixtures) together mark a player as at-risk.
"""

from app.db import get_db

RULES = [
    {
        "rule_key": "short-rest-days",
        "description": "Rest days since last match below this value counts as short rest",
        "threshold": 3,
        "rule_type": "fatigue",
    },
    {
        "rule_key": "high-recent-minutes",
        "description": (
            "Minutes across the team's last 3 fixtures at or above this "
            "value counts as high recent workload"
        ),
        "threshold": 180,
        "rule_type": "fatigue",
    },
]


def seed(client=None):
    client = client or get_db()
    client.table("rules").upsert(RULES, on_conflict="rule_key").execute()
    print(f"Seeded {len(RULES)} rule(s) into the rules table.")


if __name__ == "__main__":
    seed()
