# AI Chat Assistant — Mechanism (Step 1: Single Category)

## Goal

Prove the end-to-end mechanism for an AI chat assistant — one working
question, grounded in real data, with a graceful failure mode — before
building out the full role-guardrail matrix across many question
categories. Any authenticated role may use it in this step; per-role
restrictions are future work, deferred until there is more than one
category to restrict between.

## Non-goals (this step)

- Role-specific access rules for the assistant itself (any authenticated
  user can ask).
- Multi-provider LLM fallback (Groq only, single provider).
- More than one supported question category (`team_readiness` only).
- Conversation memory / multi-turn context (each question is answered
  independently; the frontend keeps a message list for display only).
- Streaming token-by-token output (Groq's response is used whole).

## Architecture

```
User question
   -> POST /api/ai/ask  (gated: Depends(get_current_user), any role)
   -> app/services/ai_service.answer_question(question, client)
        -> classify_intent(question): keyword match -> "team_readiness" | None
        -> None:  return fixed OUT_OF_SCOPE message. No Groq call.
        -> "team_readiness":
             -> fetch_readiness_data(client)   [reuses existing
                get_at_risk_players() + build_readiness_response(),
                same functions /api/team/readiness already calls --
                in-process, no HTTP round-trip to our own API]
             -> build system prompt (data injected, strict
                "summarize only this data" instruction)
             -> call Groq (openai SDK pointed at Groq's OpenAI-
                compatible endpoint), short timeout
             -> success: return Groq's answer text
             -> failure (timeout/auth/rate-limit/network/anything):
                return fixed FALLBACK message. Never raises, never hangs.
   <- {"answer": "..."}
```

`answer_question` never raises — the router can call it directly with no
try/except of its own.

## Backend details

**`backend/app/config.py`** — add `GROQ_API_KEY = os.getenv("GROQ_API_KEY")`,
following this file's existing plain-`os.getenv` style (not the reference
project's pydantic-settings style). The real key goes in `backend/.env`,
added by the user directly — never hardcoded, never requested by the
assistant.

**`backend/app/services/ai_service.py`** (new):
- `CATEGORY_KEYWORDS = {"team_readiness": [...]}` — a small fixed dict.
  Keywords cover readiness/availability/fitness/injury/rest/fatigue/
  rotation phrasing.
- `classify_intent(question: str) -> Optional[str]` — lowercases the
  question, returns the first category whose keyword list has a substring
  match, else `None`. Pure function, no I/O — directly unit-testable.
- `fetch_readiness_data(client) -> dict` — calls `get_at_risk_players`
  (from `app.services.fatigue`) and `build_readiness_response` (from
  `app.routers.matches`) exactly as `GET /api/team/readiness` does, so the
  assistant is grounded in the same real data that endpoint returns.
- `SYSTEM_PROMPT` — adapted from the reference MIA prompt's anti-
  fabrication pattern: strict scope (only the injected readiness JSON),
  no invented players/stats, concise tone, no meta-commentary about being
  an AI. Trimmed to this single category (no tactics/transfers/etc.
  sections needed since those categories don't exist here yet).
- `OUT_OF_SCOPE_MESSAGE` — fixed string, e.g. "I can only help with squad
  readiness questions right now. Try asking about player availability,
  fitness, or fatigue risk." Returned with zero Groq calls and zero data
  fetches when `classify_intent` returns `None`.
- `FALLBACK_MESSAGE` — fixed string, e.g. "The assistant is temporarily
  unavailable. Please try again shortly." Returned on any Groq-call
  exception.
- `get_groq_client()` — builds an `openai.OpenAI` client with
  `api_key=settings-or-env GROQ_API_KEY`, `base_url` = Groq's OpenAI-
  compatible endpoint (`https://api.groq.com/openai/v1/`), constructed
  fresh per call (matches this repo's `get_db()` pattern of a fresh client
  per request rather than a shared global).
- `answer_question(question: str, client) -> str` — orchestrates the
  above, wraps the Groq call in `try/except Exception` with a request
  timeout (e.g. 10s via the SDK's `timeout=` param) returning
  `FALLBACK_MESSAGE` on any failure.

**`backend/app/routers/ai.py`** (new):
- `router = APIRouter(prefix="/api/ai", tags=["ai"])`
- `POST /ask`, body `{question: str}` (Pydantic model, min_length=1),
  `Depends(get_current_user)` + `Depends(get_db)`, calls
  `answer_question(body.question, client)`, returns `{"answer": str}`.
- Registered in `app/main.py` alongside the other routers.

**`backend/requirements.txt`** — add the `openai` package (used as a thin
HTTP client against Groq's compatible endpoint, same mechanism the
reference project uses).

## Frontend details

- **`frontend/src/pages/Assistant.jsx`** (new): message list (user/
  assistant bubbles), text input pinned at the bottom, send button,
  loading indicator while awaiting the response. Structurally modeled on
  the reference `Assistant.jsx` (state shape: `messages`, `input`,
  `loading`; Enter-to-send; scroll-to-bottom on new message) but styled
  with PitchIQ's existing inline-style dark-theme convention (as seen in
  `MyScoutingNotes.jsx`), not the reference's separate CSS classes. No
  typewriter/streaming animation — Groq's response is shown as soon as it
  arrives.
- **`frontend/src/services/api.js`** — add
  `export const askAssistant = (question) => postJSON('/api/ai/ask', { question });`
- **`frontend/src/App.jsx`** — new route `/assistant` inside `AppShell` +
  `RequireAuth`.
- **`frontend/src/components/Sidebar.jsx`** — new nav entry (e.g. 💬
  "Assistant"), added to `NAV_PATHS_BY_ROLE` for all three roles
  (analyst, coach, scout) since any authenticated role can use it.

## Error handling

- No bearer token → existing `get_current_user` 401, unchanged.
- Empty/out-of-scope question → fixed message, 200 response, no Groq call,
  no readiness fetch.
- Groq timeout/auth/rate-limit/network error → fixed fallback message, 200
  response (the endpoint itself never 500s because of a Groq problem).
- The frontend shows whatever string comes back (out-of-scope, fallback,
  or a real answer) as a normal assistant message — it doesn't need to
  distinguish these cases specially.

## Testing

**`backend/tests/test_ai_service.py`** (new, using the existing
`FakeClient`/`FakeUser` doubles from `tests/fakes_supabase.py`, extended
with fake `matches`/`rules`/`player_match_stats` rows as needed for
`fetch_readiness_data`):
- `classify_intent` returns `"team_readiness"` for readiness-style
  questions (availability/fitness/injury/fatigue phrasing).
- `classify_intent` returns `None` for out-of-scope questions (e.g.
  "what's the weather", "who should we sign").
- `answer_question` on an out-of-scope question returns
  `OUT_OF_SCOPE_MESSAGE`, and — via `unittest.mock.patch` on
  `fetch_readiness_data` and the Groq client constructor — proves neither
  is called. This is the "does not silently call it or fabricate an
  answer" guarantee from a black-box test, not just a string match.
- `answer_question` on a readiness question, with the Groq call mocked to
  return a canned string, returns that string (proving the data-fetch →
  prompt → Groq wiring runs).
- `answer_question` with the Groq call mocked to raise returns
  `FALLBACK_MESSAGE`, not an exception.

**`backend/tests/test_ai_router.py`** (new, mirroring
`test_analytics_router.py`'s style): 401 without a token, 200 with one,
using `app.dependency_overrides` for `get_db` and mocking
`ai_service.answer_question` so the router test doesn't also re-test the
service's internals.

## Manual verification (before commit)

Log in as any one demo account in the actual running app, open
`/assistant`, ask a real readiness question (e.g. "who's at risk of
fatigue right now?"), and confirm the answer reflects real current
`/api/team/readiness` data — not a canned or fabricated response.

## Commit / push

Commit the change and push to `origin/v2-dev` once the above passes.
