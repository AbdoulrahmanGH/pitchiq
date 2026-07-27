"""POST /api/ai/ask -- the AI assistant endpoint. Gated to any
authenticated role (no role-specific restrictions yet -- there's only one
supported question category so far). See app.services.ai_service for the
routing/Groq logic itself.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import AuthenticatedUser, get_current_user
from app.db import get_db
from app.services.ai_service import answer_question

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1)


@router.post("/ask")
def ask(
    body: AskRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    client=Depends(get_db),
):
    return {"answer": answer_question(body.question, client, user)}
