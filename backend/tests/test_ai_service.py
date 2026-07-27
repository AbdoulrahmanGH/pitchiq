"""Tests for app/services/ai_service.py -- the keyword-routed, Groq-backed
assistant. Groq and the readiness data fetch are always mocked here (no
real network calls); fetch_readiness_data's own behavior is covered by
test_matches_router.py.
"""

import pytest

from app.services.ai_service import classify_intent


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
