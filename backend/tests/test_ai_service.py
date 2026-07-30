"""Tests for app/services/ai_service.py -- the LLM-routed, Groq-backed
assistant. Groq is always mocked here (no real network calls);
fetch_readiness_data's own behavior is covered by test_matches_router.py.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.auth import AuthenticatedUser
from app.services.ai_service import (
    CATEGORY_DESCRIPTIONS,
    CATEGORY_KEYWORDS,
    FALLBACK_MESSAGE,
    GREETING_MESSAGE,
    OUT_OF_SCOPE_SEASON_MESSAGE,
    PLAYER_NOT_FOUND_MESSAGE,
    ROLE_ALLOWED_CATEGORIES,
    WRITE_ACTION_DECLINE_MESSAGE,
    _classify_intent_by_keywords,
    _is_greeting_or_identity_question,
    _is_out_of_scope_season_or_competition_question,
    _is_write_action_request,
    _resolve_player_names_by_substring,
    answer_question,
    classify_intent,
    out_of_scope_message,
    out_of_scope_message_variants,
    resolve_player_names,
)

ANALYST_USER = AuthenticatedUser(id="user-1", email="analyst@example.com", role="analyst")


def _mock_groq_calls(*contents):
    """One mocked Groq client whose create() returns `contents` in order --
    e.g. (classification, resolution_json, final_answer) for a question
    that needs both classifying and a player name resolved.
    """
    responses = []
    for content in contents:
        r = MagicMock()
        r.choices[0].message.content = content
        responses.append(r)
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = responses
    return mock_client


def _mock_groq_with_content(content):
    return _mock_groq_calls(content)


def _resolution_json(resolved=None, possible=None):
    return json.dumps({"resolved": resolved or [], "possible": possible or []})


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


def test_classify_intent_threads_context_into_the_llm_call():
    # A short confirmation reply ("yes") carries no topic signal on its own
    # -- the recent-conversation context is what lets the classifier keep
    # treating it as the same category as the question it's answering.
    mock_client = _mock_groq_with_content("player_performance")
    context = "Recent conversation:\nUser: How is Sarez performing?\nAssistant: Did you mean Luis Suarez?\n"
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = classify_intent("yes", context=context)

    assert result == "player_performance"
    user_message = mock_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "Recent conversation" in user_message and "yes" in user_message


@pytest.mark.parametrize("question", [
    "Who's a good replacement for Suárez?",
    "Who's a good replacement for Suarez?",
    "Who could we sign instead of Messi?",
    "Who's similar to Messi in playing style?",
    "Can you recommend a replacement for our striker?",
    "What's a good alternative to Suarez?",
])
def test_classify_intent_declines_recommendation_questions_without_calling_llm(question):
    # Recommendation/similarity questions must be declined before any LLM
    # call -- and, more importantly, before name resolution ever runs. Left
    # to the LLM classifier, a question naming a real player ("...for
    # Suárez") risks being misclassified into player_performance or
    # player_comparison, which would resolve his name and answer a narrower
    # question (his own stats) than what was actually asked.
    mock_client = MagicMock()
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        assert classify_intent(question) is None
    mock_client.chat.completions.create.assert_not_called()


# ----------------------- resolve_player_names (LLM + fallback) -----------------------

SAMPLE_PLAYERS = [
    {"id": 1, "name": "Lionel Andrés Messi Cuccittini"},
    {"id": 2, "name": "Sergio Busquets i Burgos"},
    {"id": 3, "name": "Alex Martinez"},
    {"id": 4, "name": "Alex Garcia"},
]


def test_resolve_player_names_resolves_a_confident_single_match():
    mock_client = _mock_groq_with_content(_resolution_json(resolved=["Lionel Andrés Messi Cuccittini"]))
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = resolve_player_names("How is Messi performing?", SAMPLE_PLAYERS)

    assert result.status == "resolved"
    assert [p["id"] for p in result.players] == [1]


def test_resolve_player_names_resolves_a_typo_confidently():
    # "Nemar" is a typo, but unambiguous against this roster -- the LLM
    # resolver (unlike the old substring matcher) is expected to handle
    # this directly rather than declining or asking for clarification.
    players = SAMPLE_PLAYERS + [{"id": 6, "name": "Neymar da Silva Santos Júnior"}]
    mock_client = _mock_groq_with_content(_resolution_json(resolved=["Neymar da Silva Santos Júnior"]))
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = resolve_player_names("How is Nemar doing?", players)

    assert result.status == "resolved"
    assert [p["id"] for p in result.players] == [6]


def test_resolve_player_names_resolves_two_confident_matches_for_comparison():
    resolved_json = _resolution_json(resolved=["Lionel Andrés Messi Cuccittini", "Sergio Busquets i Burgos"])
    mock_client = _mock_groq_with_content(resolved_json)
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = resolve_player_names("Compare Messi and Busquets", SAMPLE_PLAYERS, expected_count=2)

    assert result.status == "resolved"
    assert {p["id"] for p in result.players} == {1, 2}


def test_resolve_player_names_returns_clarify_for_an_ambiguous_surname():
    players = [
        {"id": 5, "name": "Luis Alberto Suárez Díaz"},
        {"id": 7, "name": "Denis Suárez Fernández"},
    ]
    possible_json = _resolution_json(possible=["Luis Alberto Suárez Díaz", "Denis Suárez Fernández"])
    mock_client = _mock_groq_with_content(possible_json)
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = resolve_player_names("How's Sarez doing?", players)

    assert result.status == "clarify"
    assert {p["id"] for p in result.players} == {5, 7}
    assert "Luis Alberto Suárez Díaz" in result.message
    assert "?" in result.message


def test_resolve_player_names_returns_not_found_when_nothing_plausible():
    mock_client = _mock_groq_with_content(_resolution_json())
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = resolve_player_names("How is Xyzzyplonk doing?", SAMPLE_PLAYERS)

    assert result.status == "not_found"
    assert result.players == []


def test_resolve_player_names_ignores_a_name_not_on_the_roster():
    # Defense against hallucination: even if the LLM disobeys the "only
    # from the roster" instruction, an invented name must never survive.
    mock_client = _mock_groq_with_content(_resolution_json(resolved=["Someone Not On The Roster"]))
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = resolve_player_names("How is Messi doing?", SAMPLE_PLAYERS)

    assert result.status == "not_found"


def test_resolve_player_names_handles_markdown_fenced_json_response():
    fenced = "```json\n" + _resolution_json(resolved=["Lionel Andrés Messi Cuccittini"]) + "\n```"
    mock_client = _mock_groq_with_content(fenced)
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = resolve_player_names("How is Messi doing?", SAMPLE_PLAYERS)

    assert result.status == "resolved"
    assert result.players[0]["id"] == 1


def test_resolve_player_names_resolves_a_confirmation_reply_using_context():
    players = [{"id": 5, "name": "Luis Alberto Suárez Díaz"}]
    mock_client = _mock_groq_with_content(_resolution_json(resolved=["Luis Alberto Suárez Díaz"]))
    context = (
        "Recent conversation:\nUser: How's Sarez doing?\n"
        "Assistant: Did you mean Luis Alberto Suárez Díaz? Please confirm or give me the full name.\n"
    )
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = resolve_player_names("yes", players, context=context)

    assert result.status == "resolved"
    assert result.players[0]["id"] == 5
    system_message = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "Recent conversation" in system_message


def test_resolve_player_names_falls_back_to_substring_matching_when_llm_call_raises():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = TimeoutError("Groq timed out")
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = resolve_player_names("How is Messi performing?", SAMPLE_PLAYERS)

    assert result.status == "resolved"
    assert result.players[0]["id"] == 1


def test_resolve_player_names_falls_back_to_not_found_when_llm_call_raises_and_substring_is_ambiguous():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = TimeoutError("Groq timed out")
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = resolve_player_names("How does Alex compare to the rest?", SAMPLE_PLAYERS)

    assert result.status == "not_found"


def test_resolve_player_names_falls_back_when_llm_returns_invalid_json():
    mock_client = _mock_groq_with_content("not valid json")
    with patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = resolve_player_names("How is Messi performing?", SAMPLE_PLAYERS)

    assert result.status == "resolved"
    assert result.players[0]["id"] == 1


# ------------------------ _resolve_player_names_by_substring (fallback only) ------------------------

def test_substring_fallback_finds_exact_single_match():
    result = _resolve_player_names_by_substring("How is Messi performing?", SAMPLE_PLAYERS)

    assert len(result) == 1
    assert result[0]["id"] == 1


def test_substring_fallback_returns_empty_when_no_name_mentioned():
    result = _resolve_player_names_by_substring("How is the team doing overall?", SAMPLE_PLAYERS)

    assert result == []


def test_substring_fallback_returns_all_matches_when_ambiguous():
    result = _resolve_player_names_by_substring("How does Alex compare to the rest?", SAMPLE_PLAYERS)

    assert {p["id"] for p in result} == {3, 4}


def test_substring_fallback_matches_accented_name_typed_without_accent():
    # Real regression found via live verification: a coach typing "Suarez"
    # (plain ASCII, the common casual spelling) must still resolve against
    # the database's real accented name "Suárez".
    players = [{"id": 5, "name": "Luis Alberto Suárez Díaz"}]

    result = _resolve_player_names_by_substring("Compare Messi and Suarez this season", players + SAMPLE_PLAYERS)

    assert {p["id"] for p in result} == {1, 5}


def test_substring_fallback_matches_accented_name_typed_with_its_own_accent():
    players = [{"id": 5, "name": "Luis Alberto Suárez Díaz"}]

    result = _resolve_player_names_by_substring("What are Suárez's stats?", players)

    assert {p["id"] for p in result} == {5}


def test_substring_fallback_finds_two_distinct_matches_for_comparison():
    result = _resolve_player_names_by_substring("Compare Messi and Busquets this season", SAMPLE_PLAYERS)

    assert {p["id"] for p in result} == {1, 2}


# --------------------------------- out_of_scope_message ---------------------------------

def test_out_of_scope_message_is_built_from_role_allowed_categories():
    for role in ("analyst", "coach", "scout"):
        message = out_of_scope_message(role)
        for category in ROLE_ALLOWED_CATEGORIES[role]:
            assert CATEGORY_DESCRIPTIONS[category] in message
        for category in set(CATEGORY_KEYWORDS) - ROLE_ALLOWED_CATEGORIES[role]:
            assert CATEGORY_DESCRIPTIONS[category] not in message


def test_out_of_scope_messages_differ_across_roles():
    messages = {role: out_of_scope_message(role) for role in ("analyst", "coach", "scout")}

    assert len(set(messages.values())) == 3


def test_out_of_scope_message_rotates_across_calls():
    # Not deterministic by nature, but with 3 templates, 50 calls should
    # surface more than one phrasing essentially always.
    messages = {out_of_scope_message("analyst") for _ in range(50)}

    assert len(messages) > 1


# ----------------------------- greeting / identity -----------------------------

@pytest.mark.parametrize("question", [
    "hi",
    "Hi!",
    "hello",
    "hey there",
    "who are you",
    "Who are you?",
    "what can you do",
    "What can you do?",
    "what do you do",
    "how can you help",
])
def test_greeting_or_identity_questions_are_detected(question):
    assert _is_greeting_or_identity_question(question)


@pytest.mark.parametrize("question", [
    "Is the squad ready for Saturday?",
    "How is Messi performing this season?",
    "hiya, is the squad fit for Saturday?",  # "hiya" only matches standalone greetings
])
def test_non_greeting_questions_are_not_detected_as_greetings(question):
    assert not _is_greeting_or_identity_question(question)


def test_greeting_returns_canned_message_without_any_groq_call():
    mock_groq_client = MagicMock()
    with patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("hi", MagicMock(), ANALYST_USER)

    assert result == GREETING_MESSAGE
    mock_groq_client.chat.completions.create.assert_not_called()


def test_who_are_you_returns_canned_message_without_any_groq_call():
    mock_groq_client = MagicMock()
    with patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("Who are you?", MagicMock(), ANALYST_USER)

    assert result == GREETING_MESSAGE
    mock_groq_client.chat.completions.create.assert_not_called()


# ----------------------- out-of-scope season / competition -----------------------

@pytest.mark.parametrize("question", [
    "How did Barcelona do in the 2021/22 season?",
    "What about 2020?",
    "How did we do in the Premier League?",
    "Show me our Champions League results",
    "What happened last season?",
    "What's the plan for next season?",
    "How did we do in 21/22?",
])
def test_out_of_scope_season_or_competition_questions_are_detected(question):
    assert _is_out_of_scope_season_or_competition_question(question)


@pytest.mark.parametrize("question", [
    "How is Messi performing this season?",
    "Compare Messi and Suarez this season",
    "What was the result of our last match?",
    "How did we do in 2015/16?",
    "How did we do in 15/16?",
])
def test_in_scope_season_questions_are_not_flagged(question):
    assert not _is_out_of_scope_season_or_competition_question(question)


def test_out_of_scope_season_question_returns_fixed_message_without_any_groq_call():
    mock_groq_client = MagicMock()
    with patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("How did we do in the 2021/22 season?", MagicMock(), ANALYST_USER)

    assert result == OUT_OF_SCOPE_SEASON_MESSAGE
    mock_groq_client.chat.completions.create.assert_not_called()


# ----------------------------- write-action decline -----------------------------

@pytest.mark.parametrize("question", [
    "Add a note about Messi's finishing",
    "Log a note for Suarez",
    "Can you update the database with his new status?",
    "Delete the note about Busquets",
    "Remove Messi from the roster",
    "Mark Messi as injured",
    "Set Messi's status to doubtful",
    "Please change the status for Suarez",
])
def test_write_action_requests_are_detected(question):
    assert _is_write_action_request(question)


@pytest.mark.parametrize("question", [
    "What are my scouting notes on Messi?",
    "Show me my notes about Suarez",
    "Is Messi available for Saturday's match?",
    "How is Messi performing this season?",
])
def test_read_only_questions_are_not_flagged_as_write_actions(question):
    assert not _is_write_action_request(question)


def test_write_action_request_returns_clean_decline_without_any_groq_call():
    mock_groq_client = MagicMock()
    with patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("Add a note about Messi's finishing", MagicMock(), ANALYST_USER)

    assert result == WRITE_ACTION_DECLINE_MESSAGE
    mock_groq_client.chat.completions.create.assert_not_called()


# --------------------------------- answer_question ---------------------------------

def test_out_of_scope_question_returns_role_message_without_fetching_or_answering():
    # classify_intent always makes one Groq call (classification) -- but a
    # confident "none" must short-circuit before any data fetch or second
    # (answer-generation) Groq call.
    mock_groq_client = _mock_groq_with_content("none")
    with patch("app.services.ai_service.fetch_readiness_data") as mock_fetch, \
         patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question("What's the weather like today?", MagicMock(), ANALYST_USER)

    assert result in out_of_scope_message_variants("analyst")
    mock_fetch.assert_not_called()
    assert mock_groq_client.chat.completions.create.call_count == 1


def test_recommendation_question_naming_a_real_player_is_declined_without_name_resolution():
    # Regression test: "who's a good replacement for Suárez" must decline on
    # the first message rather than resolving "Suárez" and answering his own
    # stats (a narrower question than what was actually asked).
    with patch("app.services.ai_service.resolve_player_names") as mock_resolve, \
         patch("app.services.ai_service.get_groq_client") as mock_get_groq:
        result = answer_question("Who's a good replacement for Suárez?", MagicMock(), ANALYST_USER)

    assert result in out_of_scope_message_variants("analyst")
    mock_resolve.assert_not_called()
    mock_get_groq.assert_not_called()


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
def test_role_gating_blocks_disallowed_category_with_role_specific_message(
    role, question, classified_category, fetch_patch_target,
):
    user = AuthenticatedUser(id="user-1", email="x@example.com", role=role)
    mock_groq_client = _mock_groq_with_content(classified_category)
    with patch(fetch_patch_target) as mock_fetch, \
         patch("app.services.ai_service.get_groq_client", return_value=mock_groq_client):
        result = answer_question(question, MagicMock(), user)

    assert result in out_of_scope_message_variants(role)
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
    mock_client = _mock_groq_calls(
        "player_performance", _resolution_json(resolved=["Lionel Messi"]), "Messi has scored 40 goals.",
    )
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 1, "name": "Lionel Messi"}, {"id": 2, "name": "Luis Suarez"},
    ]

    with patch("app.services.ai_service.fetch_performance_data", return_value=performance_rows), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("How is Messi performing this season?", fake_client, ANALYST_USER)

    assert result == "Messi has scored 40 goals."
    prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "40" in prompt and "Suarez" not in prompt  # filtered to Messi only


def test_player_performance_question_with_unresolvable_name_returns_not_found_message():
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 1, "name": "Lionel Messi"},
    ]
    mock_client = _mock_groq_calls("player_performance", _resolution_json())

    with patch("app.services.ai_service.fetch_performance_data") as mock_fetch, \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("How is Ronaldo performing this season?", fake_client, ANALYST_USER)

    assert result == PLAYER_NOT_FOUND_MESSAGE
    mock_fetch.assert_not_called()
    assert mock_client.chat.completions.create.call_count == 2  # classify + resolve, no wasted answer call


def test_player_comparison_question_resolves_two_names_and_filters_to_both():
    performance_rows = [
        {"player_id": 1, "name": "Lionel Messi", "total_goals": 40},
        {"player_id": 2, "name": "Luis Suarez", "total_goals": 30},
        {"player_id": 3, "name": "Sergio Busquets", "total_goals": 2},
    ]
    mock_client = _mock_groq_calls(
        "player_comparison",
        _resolution_json(resolved=["Lionel Messi", "Luis Suarez"]),
        "Messi has outscored Suarez this season.",
    )
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 1, "name": "Lionel Messi"}, {"id": 2, "name": "Luis Suarez"},
        {"id": 3, "name": "Sergio Busquets"},
    ]

    with patch("app.services.ai_service.fetch_performance_data", return_value=performance_rows), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("Compare Messi and Suarez this season", fake_client, ANALYST_USER)

    assert result == "Messi has outscored Suarez this season."
    prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "Busquets" not in prompt  # only the 2 compared players included


def test_player_trend_question_filters_rolling_xg_data_to_resolved_player():
    trend_data = {
        "query_name": "rolling_xg_trend", "computed_at": "2026-07-26T00:00:00Z",
        "data": [
            {"player_id": 1, "match_date": "2015-08-23", "xg": 0.4, "rolling_3match_avg_xg": 0.3},
            {"player_id": 2, "match_date": "2015-08-23", "xg": 0.1, "rolling_3match_avg_xg": 0.1},
        ],
    }
    mock_client = _mock_groq_calls(
        "player_trend", _resolution_json(resolved=["Lionel Messi"]), "Messi's form is trending up.",
    )
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 1, "name": "Lionel Messi"}, {"id": 2, "name": "Luis Suarez"},
    ]

    with patch("app.services.ai_service.fetch_trends_data", return_value=trend_data), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("What's Messi's recent form like?", fake_client, ANALYST_USER)

    assert result == "Messi's form is trending up."
    prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "0.4" in prompt and "0.1" not in prompt  # only player_id 1's rows kept


def test_scouting_notes_question_without_a_name_returns_all_caller_notes():
    notes = [{"player_id": 1, "note": "Sharp finishing"}, {"player_id": 2, "note": "Needs work off the ball"}]
    mock_client = _mock_groq_calls("scouting_notes", _resolution_json(), "You have 2 scouting notes.")
    scout_user = AuthenticatedUser(id="scout-1", email="scout@example.com", role="scout")
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 1, "name": "Lionel Messi"}, {"id": 2, "name": "Luis Suarez"},
    ]

    with patch("app.services.ai_service.fetch_notes_data", return_value=notes) as mock_fetch, \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("What are my scouting notes?", fake_client, scout_user)

    assert result == "You have 2 scouting notes."
    mock_fetch.assert_called_once_with(fake_client, player_id=None, author_id="scout-1", role="scout")


def test_scouting_notes_question_with_a_name_filters_to_that_player():
    notes = [{"player_id": 1, "note": "Sharp finishing"}, {"player_id": 2, "note": "Needs work off the ball"}]
    mock_client = _mock_groq_calls(
        "scouting_notes", _resolution_json(resolved=["Lionel Messi"]), "You noted Messi's sharp finishing.",
    )
    scout_user = AuthenticatedUser(id="scout-1", email="scout@example.com", role="scout")
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 1, "name": "Lionel Messi"}, {"id": 2, "name": "Luis Suarez"},
    ]

    with patch("app.services.ai_service.fetch_notes_data", return_value=notes), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("What are my scouting notes on Messi?", fake_client, scout_user)

    assert result == "You noted Messi's sharp finishing."
    prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "Needs work off the ball" not in prompt


# ------------------------- name resolution: clarify + follow-up memory -------------------------

def test_misspelled_name_resolves_confidently_end_to_end():
    performance_rows = [{"player_id": 6, "name": "Neymar da Silva Santos Junior", "total_goals": 20}]
    mock_client = _mock_groq_calls(
        "player_performance",
        _resolution_json(resolved=["Neymar da Silva Santos Junior"]),
        "Neymar has scored 20 goals.",
    )
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 6, "name": "Neymar da Silva Santos Junior"},
    ]

    with patch("app.services.ai_service.fetch_performance_data", return_value=performance_rows), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("How is Nemar performing?", fake_client, ANALYST_USER)

    assert result == "Neymar has scored 20 goals."


def test_ambiguous_name_returns_clarifying_question_not_a_flat_decline():
    mock_client = _mock_groq_calls(
        "player_performance",
        _resolution_json(possible=["Luis Alberto Suarez Diaz", "Denis Suarez Fernandez"]),
    )
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 5, "name": "Luis Alberto Suarez Diaz"}, {"id": 7, "name": "Denis Suarez Fernandez"},
    ]

    with patch("app.services.ai_service.fetch_performance_data") as mock_fetch, \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("How is Sarez performing?", fake_client, ANALYST_USER)

    assert result != PLAYER_NOT_FOUND_MESSAGE
    assert "Luis Alberto Suarez Diaz" in result
    assert "?" in result
    mock_fetch.assert_not_called()


def test_followup_confirmation_resolves_the_clarified_player():
    performance_rows = [{"player_id": 5, "name": "Luis Alberto Suarez Diaz", "total_goals": 25}]
    mock_client = _mock_groq_calls(
        "player_performance",
        _resolution_json(resolved=["Luis Alberto Suarez Diaz"]),
        "Suarez has scored 25 goals.",
    )
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 5, "name": "Luis Alberto Suarez Diaz"},
    ]

    with patch("app.services.ai_service.fetch_performance_data", return_value=performance_rows), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question(
            "yes", fake_client, ANALYST_USER,
            previous_question="How is Sarez performing?",
            previous_answer="Did you mean Luis Alberto Suarez Diaz? Please confirm or give me the full name.",
        )

    assert result == "Suarez has scored 25 goals."
    calls = mock_client.chat.completions.create.call_args_list
    assert "Recent conversation" in calls[0].kwargs["messages"][1]["content"]  # classify call
    assert "Recent conversation" in calls[1].kwargs["messages"][0]["content"]  # resolve call


def test_truly_unmatchable_name_still_declines():
    mock_client = _mock_groq_calls("player_performance", _resolution_json())
    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.execute.return_value.data = [
        {"id": 1, "name": "Lionel Messi"},
    ]

    with patch("app.services.ai_service.fetch_performance_data") as mock_fetch, \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("How is Zzyzx performing?", fake_client, ANALYST_USER)

    assert result == PLAYER_NOT_FOUND_MESSAGE
    mock_fetch.assert_not_called()


# ------------------------- regressions from live testing -------------------------
# Each of these reproduces one exact question that failed in real (non-mocked)
# testing before this pass.

def test_season_average_xg_question_classifies_as_player_performance():
    # Real failure: keyword matching has no "average"/"season"/"xg" keyword
    # for player_performance, so this used to fall through to out-of-scope.
    performance_rows = [
        {"player_id": 1, "name": "Lionel Messi", "xg": 27.65},
        {"player_id": 2, "name": "Luis Suarez", "xg": 18.0},
    ]
    mock_client = _mock_groq_calls(
        "player_performance", _resolution_json(resolved=["Lionel Messi"]), "Messi's season xG is 27.65.",
    )
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
    mock_client = _mock_groq_calls("team_season_stats", "Our season PPDA average is 9.3.")

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
    mock_client = _mock_groq_calls("scouting_notes", _resolution_json(), "There are 2 scouting notes on file.")
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
    mock_client = _mock_groq_calls("season_rankings", "Player 2 is outperforming their xG the most.")

    with patch("app.services.ai_service.fetch_rankings_data", return_value=rankings_data), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("Who's outperforming their xG?", MagicMock(), ANALYST_USER)

    assert result == "Player 2 is outperforming their xG the most."
    prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert prompt.index("'goals_minus_xg': 12.0") < prompt.index("'goals_minus_xg': -5.0")


def test_outperforming_xg_question_surfaces_player_names_not_bare_ids():
    # Real failure: rankings rows only ever carried player_id, so a
    # follow-up question referencing "Suarez" by name had nothing to match
    # against, and the answer itself could only cite bare IDs.
    rankings_data = {
        "query_name": "season_rankings", "computed_at": "2026-07-26T00:00:00Z",
        "data": [
            {"player_id": 1, "season_goals": 20, "season_xg": 25.0, "goals_minus_xg": -5.0,
             "name": "Sergio Busquets", "nickname": None},
            {"player_id": 2, "season_goals": 30, "season_xg": 18.0, "goals_minus_xg": 12.0,
             "name": "Luis Suarez", "nickname": "Suarez"},
        ],
    }
    mock_client = _mock_groq_calls("season_rankings", "Luis Suarez is outperforming their xG the most.")

    with patch("app.services.ai_service.fetch_rankings_data", return_value=rankings_data), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("Who's outperforming their xG?", MagicMock(), ANALYST_USER)

    assert result == "Luis Suarez is outperforming their xG the most."
    prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "Luis Suarez" in prompt


def test_availability_question_surfaces_full_squad_with_default_status_and_names():
    # Real failure: players with no player_status row were silently
    # omitted (so "who's available" couldn't be answered for most of the
    # squad), and the rows that did exist only carried a bare player_id.
    statuses = [
        {"player_id": 1, "status": "doubtful", "note": "Tight hamstring", "updated_by": "coach-1",
         "updated_at": "2026-07-26T00:00:00Z", "name": "Lionel Messi", "nickname": "Messi"},
        {"player_id": 2, "status": "available", "note": None, "updated_by": None,
         "updated_at": None, "name": "Luis Suarez", "nickname": "Suarez"},
    ]
    mock_client = _mock_groq_calls("availability", "Messi is doubtful; Suarez is available.")
    coach_user = AuthenticatedUser(id="coach-1", email="coach@example.com", role="coach")

    with patch("app.services.ai_service.fetch_player_statuses_data", return_value=statuses), \
         patch("app.services.ai_service.get_groq_client", return_value=mock_client):
        result = answer_question("Who's available?", MagicMock(), coach_user)

    assert result == "Messi is doubtful; Suarez is available."
    prompt = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
    assert "Lionel Messi" in prompt and "Luis Suarez" in prompt
