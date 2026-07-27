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
    ROLE_ALLOWED_CATEGORIES,
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
])
def test_classify_intent_matches_expected_category(question, expected_category):
    assert classify_intent(question) == expected_category


@pytest.mark.parametrize("question", [
    "What's the weather like today?",
    "Should we sign a new striker this window?",
    "What formation should we use against Real Madrid?",
    "Who won the league last season?",
    "Have we already played Real Madrid this season?",
])
def test_classify_intent_returns_none_for_out_of_scope_questions(question):
    # The last two cases are regression tests for the whole-word matching
    # fix: "formation" must not match the "form" keyword (player_trend),
    # and "already" must not match the "ready" keyword (team_readiness) --
    # both would false-positive under naive substring matching.
    assert classify_intent(question) is None


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


def test_resolve_player_names_finds_two_distinct_matches_for_comparison():
    result = resolve_player_names("Compare Messi and Busquets this season", SAMPLE_PLAYERS)

    assert {p["id"] for p in result} == {1, 2}


# --------------------------------- answer_question ---------------------------------

def test_out_of_scope_question_returns_fixed_message_without_calling_groq_or_readiness():
    with patch("app.services.ai_service.fetch_readiness_data") as mock_fetch, \
         patch("app.services.ai_service.get_groq_client") as mock_get_client:
        result = answer_question("What's the weather like today?", MagicMock(), ANALYST_USER)

    assert result == OUT_OF_SCOPE_MESSAGE
    mock_fetch.assert_not_called()
    mock_get_client.assert_not_called()


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
        "team_readiness", "player_fatigue", "squad_depth",
        "availability", "player_performance", "match_summary",
    }
    assert ROLE_ALLOWED_CATEGORIES["scout"] == {
        "player_performance", "player_comparison", "season_rankings",
        "player_trend", "match_summary", "scouting_notes",
    }


@pytest.mark.parametrize("role,question,fetch_patch_target", [
    ("coach", "Who tops the season rankings?", "app.services.ai_service.fetch_readiness_data"),
    ("scout", "Is the squad ready for Saturday?", "app.services.ai_service.fetch_readiness_data"),
])
def test_role_gating_blocks_disallowed_category_with_generic_message(role, question, fetch_patch_target):
    user = AuthenticatedUser(id="user-1", email="x@example.com", role=role)
    with patch(fetch_patch_target) as mock_fetch, \
         patch("app.services.ai_service.get_groq_client") as mock_get_client:
        result = answer_question(question, MagicMock(), user)

    assert result == OUT_OF_SCOPE_MESSAGE
    mock_fetch.assert_not_called()
    mock_get_client.assert_not_called()


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
