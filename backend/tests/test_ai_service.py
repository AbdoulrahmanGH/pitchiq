"""Tests for app/services/ai_service.py -- the keyword-routed, Groq-backed
assistant. Groq and the readiness data fetch are always mocked here (no
real network calls); fetch_readiness_data's own behavior is covered by
test_matches_router.py.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.auth import AuthenticatedUser
from app.services.ai_service import (
    CATEGORY_KEYWORDS,
    FALLBACK_MESSAGE,
    OUT_OF_SCOPE_MESSAGE,
    PLAYER_NOT_FOUND_MESSAGE,
    ROLE_ALLOWED_CATEGORIES,
    _classify_intent_by_keywords,
    answer_question,
    classify_intent,
    resolve_player_names,
)

ANALYST_USER = AuthenticatedUser(id="user-1", email="analyst@example.com", role="analyst")


@pytest.mark.parametrize("question,expected_category", [
    ("Is the squad ready for Saturday?", "team_readiness"),
    ("How fit is the squad for the next game?", "team_readiness"),
    ("Who's at risk of fatigue right now?", "player_fatigue"),
    ("Is anyone overworked this month?", "player_fatigue"),
    ("How much depth do we have at center back?", "squad_depth"),
    ("Who's our backup goalkeeper?", "squad_depth"),
    ("Is Messi available for Saturday's match?", "availability"),
    ("Which players are doubtful this week?", "availability"),
    ("Any injuries I should know about before matchday?", "availability"),
    ("How is Messi performing this season?", "player_performance"),
    ("What are Suarez's stats?", "player_performance"),
    ("Compare Messi and Suarez this season", "player_comparison"),
    ("Who is better, Messi or Suarez?", "player_comparison"),
    ("Who tops the season rankings?", "season_rankings"),
    ("What's the goal ranking this season?", "season_rankings"),
    ("What's Messi's recent form like?", "player_trend"),
    ("Is Suarez trending up in xG?", "player_trend"),
    ("How did we do against Real Madrid?", "match_summary"),
    ("What was the result of our last match?", "match_summary"),
    ("What are my scouting notes on Messi?", "scouting_notes"),
    ("Show me my notes about Suarez", "scouting_notes"),
    ("What's our PPDA like this season?", "team_season_stats"),
    ("How's our field tilt trending?", "team_season_stats"),
])
def test_keyword_classifier_matches_expected_category(question, expected_category):
    # These exercise _classify_intent_by_keywords directly -- the fallback
    # path used only when the LLM classifier call fails. classify_intent
    # itself always tries the LLM first (see the classify_intent tests
    # below), so testing it directly here would make a real network call.
    assert _classify_intent_by_keywords(question) == expected_category


@pytest.mark.parametrize("question", [
    "What's the weather like today?",
    "Should we sign a new striker this window?",
    "What formation should we use against Real Madrid?",
    "Who won the league last season?",
    "Have we already played Real Madrid this season?",
])
def test_keyword_classifier_returns_none_for_out_of_scope_questions(question):
    # The last two cases are regression tests for the whole-word matching
    # fix: "formation" must not match the "form" keyword (player_trend),
    # and "already" must not match the "ready" keyword (team_readiness) --
    # both would false-positive under naive substring matching.
    assert _classify_intent_by_keywords(question) is None


# ----------------------------- classify_intent (LLM + fallback) -----------------------------

def _mock_groq_with_content(content):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


def test_classify_intent_trusts_the_llm_even_where_keywords_would_miss():
    # "season average xg" contains none of player_performance's keywords --
    # a real failure found in live testing that motivated the LLM
    # classifier in the first place.
    mock_client = _mock_groq_with_content("player_performance")
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        assert classify_intent("What's Messi's season average xg?") == "player_performance"


def test_classify_intent_trusts_a_confident_none_without_falling_back():
    # Even though the keyword matcher would classify this as team_readiness,
    # a confident "none" from the LLM must be trusted as-is, not second-
    # guessed via the keyword fallback.
    mock_client = _mock_groq_with_content("none")
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        assert classify_intent("Is the squad ready for Saturday?") is None


def test_classify_intent_falls_back_to_keywords_when_llm_call_raises():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = TimeoutError("Groq timed out")
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        assert classify_intent("Is the squad ready for Saturday?") == "team_readiness"


def test_classify_intent_falls_back_to_keywords_when_llm_returns_invalid_category():
    mock_client = _mock_groq_with_content("definitely not a real category")
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        assert classify_intent("Is the squad ready for Saturday?") == "team_readiness"


# ----------------------------- resolve_player_names -----------------------------

SAMPLE_PLAYERS = [
    {"id": 1, "name": "Lionel Andrés Messi Cuccittini"},
    {"id": 2, "name": "Sergio Busquets i Burgos"},
    {"id": 3, "name": "Alex Martinez"},
    {"id": 4, "name": "Alex Garcia"},
]


def test_resolve_player_names_finds_exact_single_match():
    result = resolve_player_names("How is Messi performing?", SAMPLE_PLAYERS)

    assert len(result) == 1
    assert result[0]["id"] == 1


def test_resolve_player_names_returns_empty_when_no_name_mentioned():
    result = resolve_player_names("How is the team doing overall?", SAMPLE_PLAYERS)

    assert result == []


def test_resolve_player_names_returns_all_matches_when_ambiguous():
    # Both "Alex Martinez" and "Alex Garcia" share the token "Alex" --
    # resolve_player_names returns both, leaving the arity check (exactly
    # 1 expected) to the caller, which is what produces the ambiguous
    # "couldn't find" behavior downstream.
    result = resolve_player_names("How does Alex compare to the rest?", SAMPLE_PLAYERS)

    assert {p["id"] for p in result} == {3, 4}


def test_resolve_player_names_matches_accented_name_typed_without_accent():
    # Real regression found via live verification: a coach typing "Suarez"
    # (plain ASCII, the common casual spelling) must still resolve against
    # the database's real accented name "Suárez".
    players = [{"id": 5, "name": "Luis Alberto Suárez Díaz"}]

    result = resolve_player_names("Compare Messi and Suarez this season", players + SAMPLE_PLAYERS)

    assert {p["id"] for p in result} == {1, 5}


def test_resolve_player_names_matches_accented_name_typed_with_its_own_accent():
    # The other direction of the accent-folding fix: a question that types
    # the name correctly (with its accent) must still resolve, proving the
    # fold is applied symmetrically to both sides, not just the ASCII case.
    players = [{"id": 5, "name": "Luis Alberto Suárez Díaz"}]

    result = resolve_player_names("What are Suárez's stats?", players)

    assert {p["id"] for p in result} == {5}


def test_resolve_player_names_finds_two_distinct_matches_for_comparison():
    result = resolve_player_names("Compare Messi and Busquets this season", SAMPLE_PLAYERS)

    assert {p["id"] for p in result} == {1, 2}


# --------------------------------- answer_question ---------------------------------

def test_out_of_scope_question_returns_fixed_message_without_fetching_or_answering():
    # classify_intent always makes one Groq call (classification) -- but a
    # confident "none" must short-circuit before any data fetch or second
    # (answer-generation) Groq call.
    mock_groq_client = _mock_groq_with_content("none")
    with patch("app.services.ai_service.fetch_readiness_data") as mock_fetch, \
         patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("What's the weather like today?", MagicMock(), ANALYST_USER)

    assert result == OUT_OF_SCOPE_MESSAGE
    mock_fetch.assert_not_called()
    assert mock_groq_client.chat.completions.create.call_count == 1


def test_readiness_question_summarizes_real_fetched_data_via_groq():
    fake_readiness_data = {"readiness_score": 82, "at_risk_players": []}
    mock_groq_response = MagicMock()
    mock_groq_response.choices[0].message.content = "Squad readiness is 82/100."

    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create.return_value = mock_groq_response

    with patch("app.services.ai_service.fetch_readiness_data", return_value=fake_readiness_data) as mock_fetch, \
         patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("How is squad readiness looking?", MagicMock(), ANALYST_USER)

    assert result == "Squad readiness is 82/100."
    mock_fetch.assert_called_once()
    call_kwargs = mock_groq_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["temperature"] == 0.2
    assert call_kwargs["max_tokens"] == 400
    assert "82" in call_kwargs["messages"][0]["content"]  # readiness data reached the prompt
    assert call_kwargs["messages"][1] == {"role": "user", "content": "How is squad readiness looking?"}


def test_groq_failure_returns_fallback_message_not_an_exception():
    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create.side_effect = TimeoutError("Groq timed out")

    with patch("app.services.ai_service.fetch_readiness_data", return_value={}), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("How is squad readiness looking?", MagicMock(), ANALYST_USER)

    assert result == FALLBACK_MESSAGE


# ----------------------------------- role gating -----------------------------------

def test_role_allowed_categories_matches_the_spec():
    assert ROLE_ALLOWED_CATEGORIES["analyst"] == set(CATEGORY_KEYWORDS.keys())
    assert ROLE_ALLOWED_CATEGORIES["coach"] == {
        "team_readiness", "team_season_stats", "player_fatigue", "squad_depth",
        "availability", "player_performance", "match_summary",
    }
    assert ROLE_ALLOWED_CATEGORIES["scout"] == {
        "player_performance", "player_comparison", "season_rankings",
        "player_trend", "match_summary", "scouting_notes",
    }


@pytest.mark.parametrize("role,question,classified_category,fetch_patch_target", [
    ("coach", "Who tops the season rankings?", "season_rankings", "app.services.ai_service.fetch_rankings_data"),
    ("scout", "Is the squad ready for Saturday?", "team_readiness", "app.services.ai_service.fetch_readiness_data"),
])
def test_role_gating_blocks_disallowed_category_with_generic_message(
    role, question, classified_category, fetch_patch_target,
):
    user = AuthenticatedUser(id="user-1", email="x@example.com", role=role)
    mock_groq_client = _mock_groq_with_content(classified_category)
    with patch(fetch_patch_target) as mock_fetch, \
         patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question(question, MagicMock(), user)

    assert result == OUT_OF_SCOPE_MESSAGE
    mock_fetch.assert_not_called()
    assert mock_groq_client.chat.completions.create.call_count == 1


def test_role_gating_allows_coach_to_ask_team_readiness():
    fake_readiness_data = {"readiness_score": 90}
    mock_groq_response = MagicMock()
    mock_groq_response.choices[0].message.content = "Readiness is 90/100."
    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create.return_value = mock_groq_response
    coach_user = AuthenticatedUser(id="user-2", email="coach@example.com", role="coach")

    with patch("app.services.ai_service.fetch_readiness_data", return_value=fake_readiness_data), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("Is the squad ready for Saturday?", MagicMock(), coach_user)

    assert result == "Readiness is 90/100."


# ------------------------------ category data dispatch ------------------------------

def test_squad_depth_question_calls_fetch_depth_data():
    fake_depth = {"Goalkeeper": [], "Defender": [], "Midfielder": [], "Forward": [],
                  "total_players": 0, "unresolved_players": []}
    mock_groq_response = MagicMock()
    mock_groq_response.choices[0].message.content = "No depth data yet."
    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create.return_value = mock_groq_response

    with patch("app.services.ai_service.fetch_depth_data", return_value=fake_depth) as mock_fetch, \
         patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("How much depth do we have at center back?", MagicMock(), ANALYST_USER)

    assert result == "No depth data yet."
    mock_fetch.assert_called_once()


def test_player_performance_question_resolves_name_and_filters_to_that_player():
    performance_rows = [
        {"player_id": 1, "name": "Lionel Messi", "total_goals": 40},
        {"player_id": 2, "name": "Luis Suarez", "total_goals": 30},
    ]
    mock_groq_response = MagicMock()
    mock_groq_response.choices[0].message.content = "Messi has scored 40 goals."
    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create.return_value = mock_groq_response
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 1, "name": "Lionel Messi"}, {"id": 2, "name": "Luis Suarez"},
    ]

    with patch("app.services.ai_service.fetch_performance_data", return_value=performance_rows), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("How is Messi performing this season?", fake_client, ANALYST_USER)

    assert result == "Messi has scored 40 goals."
    prompt = mock_groq_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "40" in prompt and "Suarez" not in prompt  # filtered to Messi only


def test_player_performance_question_with_unresolvable_name_returns_not_found_message():
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 1, "name": "Lionel Messi"},
    ]
    mock_groq_client = _mock_groq_with_content("player_performance")

    with patch("app.services.ai_service.fetch_performance_data") as mock_fetch, \
         patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("How is Ronaldo performing this season?", fake_client, ANALYST_USER)

    assert result == PLAYER_NOT_FOUND_MESSAGE
    mock_fetch.assert_not_called()
    assert mock_groq_client.chat.completions.create.call_count == 1  # classification only, no wasted answer call


def test_player_comparison_question_resolves_two_names_and_filters_to_both():
    performance_rows = [
        {"player_id": 1, "name": "Lionel Messi", "total_goals": 40},
        {"player_id": 2, "name": "Luis Suarez", "total_goals": 30},
        {"player_id": 3, "name": "Sergio Busquets", "total_goals": 2},
    ]
    mock_groq_response = MagicMock()
    mock_groq_response.choices[0].message.content = "Messi has outscored Suarez this season."
    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create.return_value = mock_groq_response
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 1, "name": "Lionel Messi"}, {"id": 2, "name": "Luis Suarez"},
        {"id": 3, "name": "Sergio Busquets"},
    ]

    with patch("app.services.ai_service.fetch_performance_data", return_value=performance_rows), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("Compare Messi and Suarez this season", fake_client, ANALYST_USER)

    assert result == "Messi has outscored Suarez this season."
    prompt = mock_groq_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "Busquets" not in prompt  # only the 2 compared players included


def test_player_trend_question_filters_rolling_xg_data_to_resolved_player():
    trend_data = {
        "query_name": "rolling_xg_trend", "computed_at": "2026-07-26T00:00:00Z",
        "data": [
            {"player_id": 1, "match_date": "2015-08-23", "xg": 0.4, "rolling_3match_avg_xg": 0.3},
            {"player_id": 2, "match_date": "2015-08-23", "xg": 0.1, "rolling_3match_avg_xg": 0.1},
        ],
    }
    mock_groq_response = MagicMock()
    mock_groq_response.choices[0].message.content = "Messi's form is trending up."
    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create.return_value = mock_groq_response
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 1, "name": "Lionel Messi"}, {"id": 2, "name": "Luis Suarez"},
    ]

    with patch("app.services.ai_service.fetch_trends_data", return_value=trend_data), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("What's Messi's recent form like?", fake_client, ANALYST_USER)

    assert result == "Messi's form is trending up."
    prompt = mock_groq_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "0.4" in prompt and "0.1" not in prompt  # only player_id 1's rows kept


def test_scouting_notes_question_without_a_name_returns_all_caller_notes():
    notes = [{"player_id": 1, "note": "Sharp finishing"}, {"player_id": 2, "note": "Needs work off the ball"}]
    mock_groq_response = MagicMock()
    mock_groq_response.choices[0].message.content = "You have 2 scouting notes."
    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create.return_value = mock_groq_response
    scout_user = AuthenticatedUser(id="scout-1", email="scout@example.com", role="scout")
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 1, "name": "Lionel Messi"}, {"id": 2, "name": "Luis Suarez"},
    ]

    with patch("app.services.ai_service.fetch_notes_data", return_value=notes) as mock_fetch, \
         patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("What are my scouting notes?", fake_client, scout_user)

    assert result == "You have 2 scouting notes."
    mock_fetch.assert_called_once_with(fake_client, player_id=None, author_id="scout-1", role="scout")


def test_scouting_notes_question_with_a_name_filters_to_that_player():
    notes = [{"player_id": 1, "note": "Sharp finishing"}, {"player_id": 2, "note": "Needs work off the ball"}]
    mock_groq_response = MagicMock()
    mock_groq_response.choices[0].message.content = "You noted Messi's sharp finishing."
    mock_groq_client = MagicMock()
    mock_groq_client.chat.completions.create.return_value = mock_groq_response
    scout_user = AuthenticatedUser(id="scout-1", email="scout@example.com", role="scout")
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 1, "name": "Lionel Messi"}, {"id": 2, "name": "Luis Suarez"},
    ]

    with patch("app.services.ai_service.fetch_notes_data", return_value=notes), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("What are my scouting notes on Messi?", fake_client, scout_user)

    assert result == "You noted Messi's sharp finishing."
    prompt = mock_groq_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "Needs work off the ball" not in prompt


# ------------------------- regressions from live testing -------------------------
# Each of these reproduces one exact question that failed in real (non-mocked)
# testing before this pass. The mocked groq client's create() side_effect is a
# 2-item list: the first call is classify_intent's classification call, the
# second is the final answer-generation call -- this lets each test control
# both independently instead of relying on one shared return_value.

def _mock_groq_two_calls(classification, answer_text):
    classify_response = MagicMock()
    classify_response.choices[0].message.content = classification
    answer_response = MagicMock()
    answer_response.choices[0].message.content = answer_text
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [classify_response, answer_response]
    return mock_client


def test_season_average_xg_question_classifies_as_player_performance():
    # Real failure: keyword matching has no "average"/"season"/"xg" keyword
    # for player_performance, so this used to fall through to out-of-scope.
    performance_rows = [
        {"player_id": 1, "name": "Lionel Messi", "xg": 27.65},
        {"player_id": 2, "name": "Luis Suarez", "xg": 18.0},
    ]
    mock_client = _mock_groq_two_calls("player_performance", "Messi's season xG is 27.65.")
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 1, "name": "Lionel Messi"}, {"id": 2, "name": "Luis Suarez"},
    ]

    with patch("app.services.ai_service.fetch_performance_data", return_value=performance_rows), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("What's Messi's season average xg?", fake_client, ANALYST_USER)

    assert result == "Messi's season xG is 27.65."
    prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "27.65" in prompt and "18.0" not in prompt  # filtered to Messi only


def test_ppda_trend_question_classifies_as_team_season_stats():
    # Real failure: no category existed for team-wide PPDA/field-tilt
    # questions at all.
    team_info = {"team_name": "Barcelona", "season_ppda_avg": 9.3, "season_field_tilt_avg": 61.2}
    mock_client = _mock_groq_two_calls("team_season_stats", "Our season PPDA average is 9.3.")

    with patch("app.services.ai_service.fetch_team_info_data", return_value=team_info) as mock_fetch, \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("What's our PPDA trend?", MagicMock(), ANALYST_USER)

    assert result == "Our season PPDA average is 9.3."
    mock_fetch.assert_called_once()


def test_analyst_asking_about_notes_on_this_player_gets_every_scouts_notes():
    # Real failure: analyst got filtered to "my notes" (their own author_id),
    # which is always empty since analysts don't write scouting notes.
    all_notes = [
        {"player_id": 1, "author_id": "scout-1", "note": "Sharp finishing"},
        {"player_id": 2, "author_id": "scout-2", "note": "Needs work off the ball"},
    ]
    mock_client = _mock_groq_two_calls("scouting_notes", "There are 2 scouting notes on file.")
    analyst_user = AuthenticatedUser(id="analyst-1", email="analyst@example.com", role="analyst")
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 1, "name": "Lionel Messi"}, {"id": 2, "name": "Luis Suarez"},
    ]

    with patch("app.services.ai_service.fetch_notes_data", return_value=all_notes) as mock_fetch, \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("What have I noted about this player?", fake_client, analyst_user)

    assert result == "There are 2 scouting notes on file."
    mock_fetch.assert_called_once_with(fake_client, player_id=None, author_id="analyst-1", role="analyst")


def test_outperforming_xg_question_sorts_rankings_by_goals_minus_xg_desc():
    # Real requirement: "who's outperforming their xG" should surface the
    # biggest positive goals-minus-xG gap first, not whatever order the
    # cached payload happens to be in.
    rankings_data = {
        "query_name": "season_rankings", "computed_at": "2026-07-26T00:00:00Z",
        "data": [
            {"player_id": 1, "season_goals": 20, "season_xg": 25.0, "goals_minus_xg": -5.0},
            {"player_id": 2, "season_goals": 30, "season_xg": 18.0, "goals_minus_xg": 12.0},
        ],
    }
    mock_client = _mock_groq_two_calls("season_rankings", "Player 2 is outperforming their xG the most.")

    with patch("app.services.ai_service.fetch_rankings_data", return_value=rankings_data), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("Who's outperforming their xG?", MagicMock(), ANALYST_USER)

    assert result == "Player 2 is outperforming their xG the most."
    prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert prompt.index("'goals_minus_xg': 12.0") < prompt.index("'goals_minus_xg': -5.0")
