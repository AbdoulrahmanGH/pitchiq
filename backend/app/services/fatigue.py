"""Shared fatigue-risk logic for /api/players/fatigue-risk and
/api/team/readiness. There is exactly one place this rule lives now --
the audit's #6/#7 findings (duplicated threshold logic across both routers,
with its own copy of the thresholds each time) go away structurally.

MIA's combined rule, read from the `rules` table rather than hardcoded:
  at_risk = rest_days_since_last_match < short_rest_days
            AND minutes across the team's last 3 fixtures >= high_minutes

rest_days_since_last_match is the gap between a player's most recent
appearance and the one before it (their previous match) -- i.e. how much
rest they had going into their last game. "The team's last 3 fixtures" is
by calendar date, counting 0 minutes for any fixture the player didn't
feature in, so it agrees with rest_days_since_last_match instead of using a
different, contradictory window. Uses however many fixtures exist if the
team has played fewer than 3 so far.
"""

from datetime import date

SHORT_REST_RULE_KEY = "short-rest-days"
HIGH_MINUTES_RULE_KEY = "high-recent-minutes"


def _parse_date(d):
    return d if isinstance(d, date) else date.fromisoformat(d)


def get_thresholds(client):
    rows = client.table("rules").select("rule_key, threshold").in_(
        "rule_key", [SHORT_REST_RULE_KEY, HIGH_MINUTES_RULE_KEY]
    ).execute().data
    values = {r["rule_key"]: r["threshold"] for r in rows}
    return values[SHORT_REST_RULE_KEY], values[HIGH_MINUTES_RULE_KEY]


def compute_at_risk_players(team_matches, player_match_rows,
                            short_rest_days, high_minutes_threshold):
    """
    team_matches: [{"id", "date"}, ...] for one team, any order.
    player_match_rows: [{"match_id", "player_id", "minutes_played",
                         "name", "nickname"}, ...] for that team's players
                        in those matches.
    Returns at-risk players: player_id, name, nickname, rest_days,
    recent_minutes, reason.
    """
    if not team_matches:
        return []

    matches_sorted = sorted(
        ({"id": m["id"], "date": _parse_date(m["date"])} for m in team_matches),
        key=lambda m: m["date"],
    )
    match_date_by_id = {m["id"]: m["date"] for m in matches_sorted}
    last_n_ids = [m["id"] for m in matches_sorted[-3:]]

    appearances = {}
    meta = {}
    for row in player_match_rows:
        pid = row["player_id"]
        appearances.setdefault(pid, []).append({
            "match_id": row["match_id"],
            "date": match_date_by_id[row["match_id"]],
            "minutes_played": row["minutes_played"],
        })
        meta[pid] = {"name": row.get("name"), "nickname": row.get("nickname")}

    at_risk = []
    for pid, apps in appearances.items():
        apps.sort(key=lambda a: a["date"])

        rest_days = (apps[-1]["date"] - apps[-2]["date"]).days if len(apps) >= 2 else None
        minutes_by_match_id = {a["match_id"]: a["minutes_played"] for a in apps}
        recent_minutes = sum(minutes_by_match_id.get(mid, 0) for mid in last_n_ids)

        short_rest = rest_days is not None and rest_days < short_rest_days
        high_workload = recent_minutes >= high_minutes_threshold
        if short_rest and high_workload:
            at_risk.append({
                "player_id": pid,
                "name": meta[pid]["name"],
                "nickname": meta[pid]["nickname"],
                "rest_days": rest_days,
                "recent_minutes": recent_minutes,
                "reason": (
                    f"Short rest — {rest_days} days since last match; "
                    f"High recent workload — {recent_minutes} minutes across "
                    f"the last {len(last_n_ids)} fixtures"
                ),
            })
    return at_risk


def get_at_risk_players(client, team_id):
    thresholds = get_thresholds(client)
    short_rest_days, high_minutes_threshold = thresholds

    matches = client.table("matches").select("id, date").or_(
        f"home_team_id.eq.{team_id},away_team_id.eq.{team_id}"
    ).execute().data
    match_ids = [m["id"] for m in matches]
    if not match_ids:
        return []

    pms_rows = client.table("player_match_stats").select(
        "match_id, player_id, minutes_played, players(name, nickname)"
    ).eq("team_id", team_id).in_("match_id", match_ids).execute().data

    player_rows = []
    for r in pms_rows:
        joined = r.pop("players", None) or {}
        player_rows.append({
            **r,
            "name": joined.get("name"),
            "nickname": joined.get("nickname"),
        })

    return compute_at_risk_players(matches, player_rows,
                                   short_rest_days, high_minutes_threshold)
