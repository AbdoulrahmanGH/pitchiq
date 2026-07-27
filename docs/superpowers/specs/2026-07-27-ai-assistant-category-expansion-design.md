# AI Assistant: Category Expansion + Role Gating

## Goal

Expand the AI assistant from one supported question category
(`team_readiness`) to ten, and gate which categories each role may ask
about — without adding any new backend business logic. Every new category
reuses an existing endpoint's real computation in-process, the same way
`team_readiness` already reuses `fetch_readiness_data`.

## Non-goals

- No new database queries or computations beyond what the existing
  endpoints already do.
- No new endpoints. `POST /api/ai/ask` stays the only route.
- No change to any existing endpoint's public behavior — the DRY
  extractions below only move code into a reusable function; the route
  itself keeps returning the same response it always did.
- No LLM function-calling / tool-use for routing — still simple keyword
  matching, extended to more categories.
- No fuzzy/typo-tolerant name matching — `resolve_player_names` does
  literal whole-word matching against `players.name`, nothing smarter.

## Category → fetch function → reused source

| Category | Fetch function | Reuses (in-process) | Needs name resolution |
|---|---|---|---|
| `team_readiness` | `fetch_readiness_data(client)` (existing) | `app/routers/matches.py` | no |
| `player_fatigue` | `fetch_fatigue_data(client)` (new, thin wrapper) | `get_at_risk_players` in `app/services/fatigue.py` | no |
| `squad_depth` | `fetch_depth_data(client)` (new) | `players.py`'s `/depth` body | no |
| `availability` | `fetch_player_statuses_data(client)` (new) | `players.py`'s `/status` GET body | no |
| `player_performance` | `fetch_performance_data(client)` (new) | `players.py`'s `/performance` body | yes (1) |
| `player_comparison` | `fetch_performance_data(client)` (same as above), filtered to 2 ids | same | yes (2) |
| `season_rankings` | `fetch_rankings_data(client)` (new) | `analytics.py`'s `/rankings` body | no |
| `player_trend` | `fetch_trends_data(client)` (new), filtered to 1 id | `analytics.py`'s `/trends` body | yes (1) |
| `match_summary` | `fetch_matches_summary_data(client)` (new) | `matches.py`'s `/summary` body | no |
| `scouting_notes` | `fetch_scouting_notes_data(client, user_id)` (new) | `scouting.py`'s "my notes" (no `player_id`) path | yes (1, optional — see below) |

Each new fetch function is a straight DRY extraction: the existing
endpoint's body moves into the named function, and the endpoint becomes a
one-line call to it (same refactor already done for
`fetch_readiness_data`/`get_team_readiness`). No behavior changes. Every
category gets a `fetch_x_data(client)`-shaped function (even
`player_fatigue`, where the existing `get_at_risk_players` needs a
`BARCELONA_TEAM_ID` argument baked in) so `ai_service.py` can dispatch on
category through one uniform `{category: fetch_fn}` mapping rather than
special-casing any single category's call signature.

**Categories that never need name resolution** (`team_readiness`,
`player_fatigue`, `squad_depth`, `availability`, `season_rankings`,
`match_summary`) fetch the *whole* dataset (every player, every match,
etc.) and hand it to Groq as-is — Groq locates the specific
player/match the question asks about within that data, exactly like
`team_readiness` already does today for "Is Messi available?".

**`scouting_notes` detail:** always fetches the caller's *own* notes
across all players first (identical to the existing "My Notes" zero-arg
behavior — never another scout's notes). If the question also names a
player, the result is filtered in-process to that player's notes among
the caller's own; if no name is mentioned, all of the caller's notes are
returned. If a name is mentioned but doesn't resolve to a real player,
`PLAYER_NOT_FOUND_MESSAGE` is returned (same as the other name-resolution
categories) — but if it resolves to a real player the caller simply has
no notes about, that's handed to Groq as genuinely empty data (not an
error), consistent with the anti-fabrication rule.

## Name resolution

```python
def resolve_player_names(question: str, players_rows: list[dict]) -> list[dict]:
    ...
```

Scans `players_rows` (`{"id", "name"}` from the `players` table) and
returns every player whose name contains, as a whole word, at least one
capitalized word (length >= 3) from the question — e.g. "Messi" in "How
is Messi performing?" matches "Lionel Andrés Messi Cuccittini" because
"Messi" appears as a whole word inside that name. Matches are deduplicated
by player id (a player matching on two separate name tokens still counts
once).

- `player_performance`, `player_trend`, `scouting_notes` (when a name is
  present): require exactly 1 match. 0 or 2+ → `PLAYER_NOT_FOUND_MESSAGE`.
- `player_comparison`: requires exactly 2 matches. Any other count →
  the same message.

`PLAYER_NOT_FOUND_MESSAGE` is returned directly with **no Groq call** —
same reasoning as `OUT_OF_SCOPE_MESSAGE`: don't ask the model to guess
when we can't ground the answer.

## `classify_intent` correctness fix

Today's implementation does raw substring matching
(`keyword in question.lower()`), which works for the multi-word phrases
already in use ("squad status") but would false-positive once more
single-word keywords are added across 9 more categories — e.g. "ready"
matching inside "already". The fix: tokenize the question into whole
words (`re.findall(r"[a-z']+", question.lower())`) and require single-word
keywords to appear as a complete token; multi-word keyword phrases keep
using substring matching against the full lowered question (tokenizing
doesn't make sense for a phrase). `CATEGORY_KEYWORDS` values may freely mix
single words and short phrases as before — only the matching logic
changes, not the data shape.

Exact keyword lists per category are pinned down by the tests themselves
(TDD), not enumerated here — same approach as the original single-category
spec.

## Role gating

```python
ROLE_ALLOWED_CATEGORIES = {
    "analyst": {all ten categories},
    "coach": {"team_readiness", "player_fatigue", "squad_depth",
              "availability", "player_performance", "match_summary"},
    "scout": {"player_performance", "player_comparison", "season_rankings",
              "player_trend", "match_summary", "scouting_notes"},
}
```

In `answer_question`, immediately after `classify_intent` returns a
category (i.e. before any fetch or Groq call):

```python
if category not in ROLE_ALLOWED_CATEGORIES.get(role, set()):
    return OUT_OF_SCOPE_MESSAGE
```

This is the exact same message used for a genuinely unmatched question —
never a distinct "you're not allowed to ask that" message, and never a
403. A coach asking a scout-only question gets an indistinguishable
generic redirect, so the assistant never reveals what it *could* answer
for a different role.

`answer_question`'s signature changes from `(question, client)` to
`(question, client, role: Optional[str])`. `app/routers/ai.py` passes
`user.role` (already available on `AuthenticatedUser` from
`get_current_user`, no auth changes needed).

## System prompt

Add a short section listing the newly available topics (squad depth,
player performance/comparison/trend, season rankings, match summaries,
scouting notes) alongside the existing readiness/availability/fatigue
description, so Groq's own understanding of "what's in scope" matches the
keyword router. The injection-resistance section and style rules (3-6
lines, plain text, no AI disclaimers) are unchanged verbatim.

## Testing

- **`classify_intent`**: at least one passing example per new category,
  plus regression cases proving the whole-word fix (e.g. a question
  containing "already" is not misclassified as `team_readiness`).
- **`resolve_player_names`**: exact-one-match, zero-match, and
  ambiguous-two-plus-match cases, each asserting the returned list shape.
- **Role gating**: parametrized test — for each role, at least one
  allowed and one disallowed category, asserting the disallowed case
  returns exactly `OUT_OF_SCOPE_MESSAGE` (not a 403, not a distinct
  message, and — via mocking, same technique as the original
  out-of-scope test — that neither the fetch function nor Groq is ever
  called).
- **Existing tests**: the original single-category tests
  (`test_ai_service.py`, `test_ai_router.py`, `test_matches_router.py`)
  keep passing; any of the original `classify_intent` example questions
  that legitimately reclassify under the finer-grained categories (e.g. a
  pure fatigue question moving from `team_readiness` to `player_fatigue`)
  get their expected category updated to match — that's the intended
  effect of splitting one category into several, not a regression.

## Manual verification

Logged in as each of the three demo accounts separately: ask 2-3 questions
from that role's own allowed category list (confirm the answer reflects
real current data, same cross-check method as before — compare against
the real endpoint's response) and 1 question outside that role's scope
(confirm the generic redirect message, not an error or role-revealing
text). Commit and push to `origin/v2-dev` once all three roles check out.
