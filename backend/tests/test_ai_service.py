"""Tests for app/services/ai_service.py -- the keyword-routed, Groq-backed
assistant. Groq and the readiness data fetch are always mocked here (no
real network calls); fetch_readiness_data's own behavior is covered by
test_matches_router.py.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.ai_service import FALLBACK_MESSAGE, OUT_OF_SCOPE_MESSAGE, answer_question, classify_intent


@pytest.mark.parametrize("question", [
    "Who's at risk of fatigue right now?",
    "Is Messi available for Saturday's match?",
    "Which players are doubtful this week?",
    "How fit is the squad for the next game?",
    "Any injuries I should know about before matchday?",
])
def test_classify_intent_matches_readiness_questions(question):
    assert classify_intent(question) == "team_readiness"


@pytest.mark.parametrize("question", [
    "What's the weather like today?",
    "Should we sign a new striker this window?",
    "What formation should we use against Real Madrid?",
    "Who won the league last season?",
])
def test_classify_intent_returns_none_for_out_of_scope_questions(question):
    assert classify_intent(question) is None


# --------------------------------- answer_question ---------------------------------

def test_out_of_scope_question_returns_fixed_message_without_calling_groq_or_readiness():
    with patch("app.services.ai_service.fetch_readiness_data") as mock_fetch, \
         patch("app.services.ai_service.get_groq_client") as mock_get_client:
        result = answer_question("What's the weather like today?", client=MagicMock())

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
        result = answer_question("How is squad readiness looking?", client=MagicMock())

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
        result = answer_question("How is squad readiness looking?", client=MagicMock())

    assert result == FALLBACK_MESSAGE
