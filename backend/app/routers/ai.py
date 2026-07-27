"""POST /api/ai/ask -- the AI assistant endpoint. Gated to any
authenticated role (category access is role-gated inside answer_question).
previous_question/previous_answer are the immediately preceding chat turn,
echoed back by the frontend -- short-term follow-up memory for player-name
clarification, not a full server-side session. See app.services.ai_service
for the routing/Groq logic itself.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import AuthenticatedUser, get_current_user
from app.db import get_db
from app.services.ai_service import answer_question

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    previous_question: Optional[str] = None
    previous_answer: Optional[str] = None


@router.post("/ask")
def ask(
    body: AskRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    client=Depends(get_db),
):
    answer = answer_question(
        body.question, client, user,
        previous_question=body.previous_question,
        previous_answer=body.previous_answer,
    )
    return {"answer": answer}
