"""Routes a natural-language question to a supported data category via
simple keyword matching (not LLM function-calling), fetches that
category's real data in-process, and asks Groq to summarize only that
data. Groq is the only provider -- no fallback chain -- but a failed or
slow call still degrades to a friendly message instead of a raw error or
a hung request. See docs/superpowers/specs/2026-07-27-ai-assistant-
mechanism-design.md for the full design.
"""

from typing import Optional

CATEGORY_KEYWORDS = {
    "team_readiness": [
        "readiness", "ready", "available", "availability", "fit", "fitness",
        "injury", "injured", "injuries", "doubtful", "unavailable", "rest",
        "fatigue", "fatigued", "tired", "rotation", "rotate", "match fit",
        "squad status",
    ],
}


def classify_intent(question: str) -> Optional[str]:
    lowered = question.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return None
