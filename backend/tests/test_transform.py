"""Tests for the v2 transform step.

Fixtures are hand-built tiny StatsBomb-shaped event lists, and every expected
number below was hand-computed from the definitions confirmed against the
football-docs documentation:

- Coordinates: 120x80 yards, acting team always attacks toward x=120.
- xG: sum of shot.statsbomb_xg (taken from the data, never recomputed).
- xA: sum of statsbomb_xg of shots assisted by the player's passes
  (pass.shot_assist -> pass.assisted_shot_id).
- PPDA (Trainor / StatsBomb IQ): opponent passes attempted in the pressing
  zone / pressing team's defensive actions (tackles, interceptions, fouls
  committed) in that zone. Zone = from 40% of pitch length in front of the
  pressing team's own goal, forward: pressing-team actions at x >= 48 in
  their own frame; opponent passes at x <= 72 in the opponent's frame.
  Null (not 0) when the denominator is 0.
- Progressive pass/carry (Wyscout): the ball ends at least 30m closer to the
  opponent goal when start and end are both in own half, 15m when they span
  halves, 10m when both are in the opponent half. StatsBomb units are yards
  (1 yd = 0.9144 m). Own half: x <= 60.
- Field tilt (kloppy recipe): team final-third touches / all final-third
  touches * 100, where touches = Pass, Carry, Shot, Dribble events with
  location x >= 80.
- Pressure regain (StatsBomb IQ): a subsequent event within 5 seconds of a
  Pressure (same period) whose possession_team is the pressing team.
"""

import pytest

from app.data.pipeline_v2 import transform

BARCA = {"id": 217, "name": "Barcelona"}
OPP = {"id": 999, "name": "Test FC"}

MESSI = {"id": 5503, "name": "Lionel Messi"}
SUAREZ = {"id": 5246, "name": "Luis Suarez"}
NEYMAR = {"id": 5211, "name": "Neymar"}
OPP_CB = {"id": 9001, "name": "Opp Defender"}


def ev(index, type_id, type_name, team, timestamp="00:00:00.000", minute=0,
       second=0, period=1, player=None, location=None, possession=1,
       possession_team=None, **extra):
    e = {
        "id": f"ev-{index}",
        "index": index,
        "period": period,
        "timestamp": timestamp,
        "minute": minute,
        "second": second,
        "type": {"id": type_id, "name": type_name},
        "possession": possession,
        "possession_team": possession_team or team,
        "team": team,
        "duration": 0.0,
    }
    if player is not None:
        e["player"] = player
    if location is not None:
        e["location"] = location
    e.update(extra)
    return e


def starting_xi(index, team, lineup):
    return ev(index, 35, "Starting XI", team, tactics={
        "formation": 433,
        "lineup": [
            {"player": p, "position": {"id": 1, "name": pos}, "jersey_number": i + 1}
            for i, (p, pos) in enumerate(lineup)
        ],
    })


MATCH_1 = {
    "match_id": 1,
    "match_date": "2015-09-12",
    "competition": {"competition_id": 11, "country_name": "Spain",
                    "competition_name": "La Liga"},
    "season": {"season_id": 27, "season_name": "2015/2016"},
    "home_team": {"home_team_id": 217, "home_team_name": "Barcelona",
                  "country": {"id": 214, "name": "Spain"}},
    "away_team": {"away_team_id": 999, "away_team_name": "Test FC",
                  "country": {"id": 68, "name": "Testland"}},
    "home_score": 1,
    "away_score": 0,
    "match_week": 3,
    "stadium": {"id": 342, "name": "Camp Nou", "country": {"id": 214, "name": "Spain"}},
}

MATCH_2 = {
    "match_id": 2,
    "match_date": "2015-09-19",
    "competition": {"competition_id": 11, "country_name": "Spain",
                    "competition_name": "La Liga"},
    "season": {"season_id": 27, "season_name": "2015/2016"},
    "home_team": {"home_team_id": 999, "home_team_name": "Test FC",
                  "country": {"id": 68, "name": "Testland"}},
    "away_team": {"away_team_id": 217, "away_team_name": "Barcelona",
                  "country": {"id": 214, "name": "Spain"}},
    "home_score": 0,
    "away_score": 0,
    "match_week": 4,
    "stadium": {"id": 100, "name": "Test Arena", "country": {"id": 68, "name": "Testland"}},
}

# ---------------------------------------------------------------------------
# Match 1: attacking metrics. Hand-computed expectations:
#   Messi:  1/1 passes, 1 key pass, 1 progressive pass (50->85 on x, 35 yd =
#           32.0m closer to goal, spanning halves, >= 15m), xa 0.5, 1 assist
#           (the pass is both shot_assist and goal_assist -- Suarez's shot
#           from it was a Goal), 1/1 dribbles, subbed off at 60 -> 60 minutes.
#   Suarez: 2 shots, 1 goal, xg 0.5 + 0.2 = 0.7, 1 progressive carry
#           (50->85, same rule as the pass), 90 minutes.
#   Neymar: on at 60 -> 30 minutes, all counters 0.
#   Team Barca: shots 2, xg 0.7, field tilt 2/3 (touches x>=80: both shots;
#           Opp: carry at 85) = 66.67; possession (pass share) 1/2 = 50;
#           pass completion 100; ppda None (0 defensive actions in zone).
#   match_events: 2 shots + 1 key pass = 3 rows.
# ---------------------------------------------------------------------------
EVENTS_1 = [
    starting_xi(1, BARCA, [(MESSI, "Right Wing"), (SUAREZ, "Center Forward")]),
    starting_xi(2, OPP, [(OPP_CB, "Center Back")]),
    ev(3, 30, "Pass", BARCA, "00:10:00.000", 10, 0, player=MESSI,
       location=[50.0, 40.0], possession=2,
       **{"pass": {"recipient": SUAREZ, "length": 35.0, "angle": 0.0,
                   "height": {"id": 1, "name": "Ground Pass"},
                   "end_location": [85.0, 40.0],
                   "shot_assist": True, "goal_assist": True,
                   "assisted_shot_id": "shot-1"}}),
    ev(4, 16, "Shot", BARCA, "00:10:04.000", 10, 4, player=SUAREZ,
       location=[108.0, 40.0], possession=2, id="shot-1",
       shot={"statsbomb_xg": 0.5, "end_location": [120.0, 40.0, 0.5],
             "outcome": {"id": 97, "name": "Goal"},
             "type": {"id": 87, "name": "Open Play"},
             "key_pass_id": "ev-3"}),
    ev(5, 14, "Dribble", BARCA, "00:15:00.000", 15, 0, player=MESSI,
       location=[70.0, 40.0], possession=3,
       dribble={"outcome": {"id": 8, "name": "Complete"}}),
    ev(6, 16, "Shot", BARCA, "00:20:00.000", 20, 0, player=SUAREZ,
       location=[100.0, 40.0], possession=4, id="shot-2",
       shot={"statsbomb_xg": 0.2, "end_location": [120.0, 45.0, 3.0],
             "outcome": {"id": 98, "name": "Off T"},
             "type": {"id": 87, "name": "Open Play"}}),
    ev(7, 43, "Carry", BARCA, "00:25:00.000", 25, 0, player=SUAREZ,
       location=[50.0, 40.0], possession=5,
       carry={"end_location": [85.0, 40.0]}),
    ev(8, 30, "Pass", OPP, "00:30:00.000", 30, 0, player=OPP_CB,
       location=[30.0, 40.0], possession=6,
       **{"pass": {"recipient": OPP_CB, "length": 5.0, "angle": 0.0,
                   "height": {"id": 1, "name": "Ground Pass"},
                   "end_location": [35.0, 40.0]}}),
    ev(9, 43, "Carry", OPP, "00:35:00.000", 35, 0, player=OPP_CB,
       location=[85.0, 40.0], possession=7,
       carry={"end_location": [86.0, 40.0]}),
    ev(10, 19, "Substitution", BARCA, "00:15:00.000", 60, 0, period=2,
       player=MESSI, possession=8,
       substitution={"outcome": {"id": 103, "name": "Tactical"},
                     "replacement": NEYMAR}),
    ev(11, 17, "Pressure", BARCA, "00:20:00.000", 65, 0, period=2,
       player=NEYMAR, location=[70.0, 30.0], possession=9,
       position={"id": 21, "name": "Left Wing"}),
]

LINEUPS_1 = [
    {"team_id": 217, "team_name": "Barcelona", "lineup": [
        {"player_id": 5503, "player_name": "Lionel Messi",
         "player_nickname": None, "jersey_number": 10,
         "country": {"id": 11, "name": "Argentina"}},
        {"player_id": 5246, "player_name": "Luis Suarez",
         "player_nickname": None, "jersey_number": 9,
         "country": {"id": 242, "name": "Uruguay"}},
        {"player_id": 5211, "player_name": "Neymar da Silva Santos Junior",
         "player_nickname": "Neymar", "jersey_number": 11,
         "country": {"id": 31, "name": "Brazil"}},
    ]},
    {"team_id": 999, "team_name": "Test FC", "lineup": [
        {"player_id": 9001, "player_name": "Opp Defender",
         "player_nickname": None, "jersey_number": 4,
         "country": {"id": 68, "name": "Testland"}},
    ]},
]

# ---------------------------------------------------------------------------
# Match 2: defensive metrics. Hand-computed expectations:
#   Barca PPDA: Opp passes attempted at x <= 72 in Opp's frame = 4 (the pass
#     at x=90 is excluded). Barca defensive actions at x >= 48: tackle at 60,
#     interception at 50, interception at 100 (foul at 40 excluded) = 3.
#     PPDA = 4/3.
#   Opp PPDA: Barca passes at x <= 72 = 2 (both at x=60). Opp defensive
#     actions at x >= 48: foul at 50 = 1. PPDA = 2.0.
#   Suarez: 2 pressures; the 00:10:00 one is followed 3s later by a
#     Barca-possession event -> 1 regain; the 00:20:00 one is only followed
#     10s later -> no regain. tackles 1, interceptions 2, duels_won 1,
#     fouls_committed 1, passes 2/2, 90 minutes.
#   Field tilt: only final-third touch is Opp's pass at x=90 -> Opp 100.0,
#     Barca 0.0.
#   Possession (pass share): Barca 2/7 = 28.5714..., Opp 5/7 = 71.4285...
# ---------------------------------------------------------------------------


def opp_pass(index, ts, minute, x, end_x):
    return ev(index, 30, "Pass", OPP, ts, minute, 0, player=OPP_CB,
              location=[x, 40.0], possession=2,
              **{"pass": {"recipient": OPP_CB, "length": abs(end_x - x),
                          "angle": 0.0,
                          "height": {"id": 1, "name": "Ground Pass"},
                          "end_location": [end_x, 40.0]}})


EVENTS_2 = [
    starting_xi(1, OPP, [(OPP_CB, "Center Back")]),
    starting_xi(2, BARCA, [(SUAREZ, "Center Forward")]),
    opp_pass(3, "00:01:00.000", 1, 30.0, 32.0),
    opp_pass(4, "00:02:00.000", 2, 30.0, 32.0),
    opp_pass(5, "00:03:00.000", 3, 30.0, 32.0),
    opp_pass(6, "00:04:00.000", 4, 30.0, 32.0),
    opp_pass(7, "00:05:00.000", 5, 90.0, 95.0),
    ev(8, 4, "Duel", BARCA, "00:08:00.000", 8, 0, player=SUAREZ,
       location=[60.0, 40.0], possession=3, possession_team=OPP,
       duel={"type": {"id": 11, "name": "Tackle"},
             "outcome": {"id": 4, "name": "Won"}}),
    ev(9, 10, "Interception", BARCA, "00:09:00.000", 9, 0, player=SUAREZ,
       location=[50.0, 40.0], possession=4, possession_team=OPP,
       interception={"outcome": {"id": 4, "name": "Won"}}),
    ev(10, 17, "Pressure", BARCA, "00:10:00.000", 10, 0, player=SUAREZ,
       location=[55.0, 40.0], possession=5, possession_team=OPP),
    ev(11, 30, "Pass", BARCA, "00:10:03.000", 10, 3, player=SUAREZ,
       location=[60.0, 40.0], possession=6,
       **{"pass": {"recipient": SUAREZ, "length": 2.0, "angle": 0.0,
                   "height": {"id": 1, "name": "Ground Pass"},
                   "end_location": [62.0, 40.0]}}),
    ev(12, 22, "Foul Committed", BARCA, "00:15:00.000", 15, 0, player=SUAREZ,
       location=[40.0, 40.0], possession=7, possession_team=OPP),
    ev(13, 22, "Foul Committed", OPP, "00:16:00.000", 16, 0, player=OPP_CB,
       location=[50.0, 40.0], possession=8, possession_team=BARCA),
    ev(14, 17, "Pressure", BARCA, "00:20:00.000", 20, 0, player=SUAREZ,
       location=[55.0, 40.0], possession=9, possession_team=OPP),
    ev(15, 30, "Pass", BARCA, "00:20:10.000", 20, 10, player=SUAREZ,
       location=[60.0, 40.0], possession=10,
       **{"pass": {"recipient": SUAREZ, "length": 2.0, "angle": 0.0,
                   "height": {"id": 1, "name": "Ground Pass"},
                   "end_location": [62.0, 40.0]}}),
    ev(16, 10, "Interception", BARCA, "00:25:00.000", 25, 0, player=SUAREZ,
       location=[100.0, 40.0], possession=11, possession_team=OPP,
       interception={"outcome": {"id": 4, "name": "Won"}}),
]

LINEUPS_2 = [
    {"team_id": 999, "team_name": "Test FC", "lineup": [
        {"player_id": 9001, "player_name": "Opp Defender",
         "player_nickname": None, "jersey_number": 4,
         "country": {"id": 68, "name": "Testland"}},
    ]},
    {"team_id": 217, "team_name": "Barcelona", "lineup": [
        {"player_id": 5246, "player_name": "Luis Suarez",
         "player_nickname": None, "jersey_number": 9,
         "country": {"id": 242, "name": "Uruguay"}},
    ]},
]


@pytest.fixture(scope="module")
def result():
    return transform(
        [MATCH_1, MATCH_2],
        {1: EVENTS_1, 2: EVENTS_2},
        {1: LINEUPS_1, 2: LINEUPS_2},
    )


def row(df, **filters):
    out = df
    for k, v in filters.items():
        out = out[out[k] == v]
    assert len(out) == 1, f"expected exactly 1 row for {filters}, got {len(out)}"
    return out.iloc[0]


# ------------------------------ teams / players -----------------------------

def test_teams_deduped(result):
    teams = result["teams"]
    assert len(teams) == 2
    assert row(teams, id=217)["name"] == "Barcelona"
    assert row(teams, id=217)["country"] == "Spain"
    assert row(teams, id=999)["country"] == "Testland"


def test_players_deduped_across_matches(result):
    players = result["players"]
    assert len(players) == 4
    assert row(players, id=5211)["nickname"] == "Neymar"
    assert row(players, id=5503)["primary_position"] == "Right Wing"
    # Suarez appears in both lineups but must produce a single row
    assert row(players, id=5246)["name"] == "Luis Suarez"


def test_substitute_position_falls_back_to_event_position(result):
    # Neymar never appears in a Starting XI lineup in these fixtures -- his
    # position must come from the `position` field StatsBomb attaches to the
    # events he's involved in after coming on, not be left null.
    p = row(result["players"], id=5211)
    assert p["primary_position"] == "Left Wing"


# --------------------------------- matches ----------------------------------

def test_match_rows(result):
    m = row(result["matches"], id=1)
    assert m["competition_id"] == 11
    assert m["season_id"] == 27
    assert m["home_team_id"] == 217
    assert m["away_team_id"] == 999
    assert m["home_score"] == 1
    assert m["away_score"] == 0
    assert m["stadium"] == "Camp Nou"
    assert m["match_week"] == 3
    assert m["date"] == "2015-09-12"


# ---------------------------- player_match_stats ----------------------------

def test_messi_match1(result):
    p = row(result["player_match_stats"], match_id=1, player_id=5503)
    assert p["team_id"] == 217
    assert p["position"] == "Right Wing"
    assert p["minutes_played"] == 60
    assert p["passes_attempted"] == 1
    assert p["passes_completed"] == 1
    assert p["key_passes"] == 1
    assert p["progressive_passes"] == 1
    assert p["xa"] == pytest.approx(0.5)
    assert p["assists"] == 1
    assert p["dribbles_attempted"] == 1
    assert p["dribbles_completed"] == 1
    assert p["shots"] == 0
    assert p["goals"] == 0
    assert p["xg"] == pytest.approx(0.0)


def test_suarez_match1(result):
    p = row(result["player_match_stats"], match_id=1, player_id=5246)
    assert p["minutes_played"] == 90
    assert p["shots"] == 2
    assert p["goals"] == 1
    assert p["xg"] == pytest.approx(0.7)
    assert p["xa"] == pytest.approx(0.0)
    assert p["assists"] == 0
    assert p["progressive_carries"] == 1
    assert p["progressive_passes"] == 0


def test_substitute_gets_row_with_zero_counters(result):
    p = row(result["player_match_stats"], match_id=1, player_id=5211)
    assert p["minutes_played"] == 30
    assert p["passes_attempted"] == 0
    assert p["shots"] == 0
    assert p["xg"] == pytest.approx(0.0)
    # Neymar's one fixture event (a Pressure, added for the position-fallback
    # test below) is his only recorded action in this match.
    assert p["pressures"] == 1


def test_suarez_match2_defensive(result):
    p = row(result["player_match_stats"], match_id=2, player_id=5246)
    assert p["minutes_played"] == 90
    assert p["tackles"] == 1
    assert p["interceptions"] == 2
    assert p["duels_won"] == 1
    assert p["fouls_committed"] == 1
    assert p["fouls_won"] == 0
    assert p["pressures"] == 2
    assert p["pressure_regains"] == 1
    assert p["passes_attempted"] == 2
    assert p["passes_completed"] == 2


# ----------------------------- team_match_stats -----------------------------

def test_team_stats_match1(result):
    b = row(result["team_match_stats"], match_id=1, team_id=217)
    assert b["shots"] == 2
    assert b["xg"] == pytest.approx(0.7)
    assert b["field_tilt_pct"] == pytest.approx(100 * 2 / 3)
    assert b["possession_pct"] == pytest.approx(50.0)
    assert b["pass_completion_pct"] == pytest.approx(100.0)
    # no defensive actions in the PPDA zone -> null, never 0
    assert b["ppda"] is None or b["ppda"] != b["ppda"]  # None or NaN

    o = row(result["team_match_stats"], match_id=1, team_id=999)
    assert o["shots"] == 0
    assert o["xg"] == pytest.approx(0.0)
    assert o["field_tilt_pct"] == pytest.approx(100 * 1 / 3)


def test_team_ppda_match2(result):
    b = row(result["team_match_stats"], match_id=2, team_id=217)
    assert b["ppda"] == pytest.approx(4 / 3)
    o = row(result["team_match_stats"], match_id=2, team_id=999)
    assert o["ppda"] == pytest.approx(2.0)


def test_team_possession_and_tilt_match2(result):
    b = row(result["team_match_stats"], match_id=2, team_id=217)
    o = row(result["team_match_stats"], match_id=2, team_id=999)
    assert b["possession_pct"] == pytest.approx(100 * 2 / 7)
    assert o["possession_pct"] == pytest.approx(100 * 5 / 7)
    assert b["field_tilt_pct"] == pytest.approx(0.0)
    assert o["field_tilt_pct"] == pytest.approx(100.0)


# ------------------------------- match_events -------------------------------

def test_match_events_rows(result):
    me = result["match_events"]
    assert len(me) == 3

    goal = row(me, match_id=1, event_type="Shot", outcome="Goal")
    assert goal["player_id"] == 5246
    assert goal["team_id"] == 217
    assert goal["minute"] == 10
    assert goal["x"] == pytest.approx(108.0)
    assert goal["y"] == pytest.approx(40.0)
    assert goal["end_x"] == pytest.approx(120.0)
    assert goal["end_y"] == pytest.approx(40.0)
    assert goal["xg"] == pytest.approx(0.5)
    assert bool(goal["under_pressure"]) is False

    off_t = row(me, match_id=1, event_type="Shot", outcome="Off T")
    assert off_t["xg"] == pytest.approx(0.2)

    kp = row(me, match_id=1, event_type="Pass")
    assert kp["player_id"] == 5503
    assert kp["outcome"] == "Complete"
    assert kp["end_x"] == pytest.approx(85.0)
