# Role-Specific Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship three role-specific features on top of the existing FastAPI + Supabase + React stack: Scouting Notes (Scout write / Analyst read-only / Coach hidden), Availability Management (Coach write, feeds into a real Squad Readiness composite), and Opponent Visibility (unscope `/api/players/performance` from Barcelona-only, add a team filter to the Players page).

**Architecture:** Two new API surfaces (`/api/scouting/notes`, `/api/players/status`) following the existing FastAPI router + `Depends(get_current_user)`/`Depends(require_role(...))` pattern from `backend/app/auth.py`. One existing endpoint (`/api/players/performance`) loses its team scoping. One existing endpoint (`/api/team/readiness`) gets a real composite formula instead of fatigue-only. Frontend additions follow the codebase's established inline-style + CSS-variable design system (no Tailwind, no new libraries).

**Tech Stack:** FastAPI, Supabase (Postgres + GoTrue auth, project `pitchiq-v2-dev`), pytest, React 19 + Vite, no frontend test runner (verify via lint/build/manual browser check).

## Global Constraints

- Reuse `get_current_user` / `require_role` from `backend/app/auth.py:48-81` exactly as-is. Do not add a new auth pattern.
- Roles are the string literals `'analyst'`, `'coach'`, `'scout'` (Postgres CHECK constraint, `schema_v2.sql:114`). No enum exists — don't introduce one.
- No migration runner exists. New tables are added to `schema_v2.sql` (source of truth for fresh installs) AND a standalone `backend/app/data/migrations/000N_*.sql` file (for the already-created `pitchiq-v2-dev` project), matching the exact pattern of `migrations/0001`-`0003`. The migration file must be applied by hand via the Supabase SQL editor — there is no way to run DDL through the `supabase-py` client (PostgREST only, no raw SQL RPC exists in this project).
- Frontend has **no Tailwind** — inline `style={}` objects + CSS custom properties from `frontend/src/index.css:3-25` (`--bg`, `--surface`, `--orange` `#FF6B35`, `--text-primary/secondary/muted`, `--green/red/yellow/blue/purple` + `-dim` variants). Cards: `linear-gradient(145deg, #1C2333 0%, #161B22 100%)` background, `1px solid rgba(255,255,255,0.07)` border, `border-radius: 14-18`. Headings/numbers: `Space Grotesk` font, `font-variant-numeric: tabular-nums` on numbers. Follow `redesign-existing-projects` audit: no new accent colors, no generic AI patterns, keep the existing dark-surface + single-orange-accent language, add real hover/loading/empty/error states to every new piece of UI (this codebase already does this well — match it, don't regress it).
- **Confirmed empirically before writing this plan** (ad-hoc script against the real `pitchiq-v2-dev` project, then deleted):
  - `scouting_notes` table **already exists** — no migration needed for it, only wiring.
  - `player_status` table **does not exist** — needs the new migration.
  - `/api/players/performance` **is** scoped to Barcelona (`team_id=217`, 25 players) via `backend/app/routers/players.py:157`. The full dataset has 20 teams, 389 distinct players with match stats (476 rows total in the `players` table, but 87 of those never appear in `player_match_stats` and so will never have a performance row — the real reachable number is 389, not 476).

---

## File Structure

**Backend — create:**
- `backend/app/data/migrations/0004_add_player_status.sql` — new table, manual-apply.
- `backend/app/routers/scouting.py` — `GET/POST /api/scouting/notes`.
- `backend/tests/test_scouting_router.py`
- `backend/tests/test_player_status_router.py`
- `backend/tests/test_players_performance_scope.py` — real-token regression test for the unscoping.

**Backend — modify:**
- `backend/app/data/schema_v2.sql` — add `player_status` table (fresh-install source of truth).
- `backend/app/routers/players.py` — unscope `/performance`, add `position_bucket`/`team_id`/`team_name` to its response, add `GET/POST /status`.
- `backend/app/routers/matches.py` — `build_readiness_response` becomes a real composite of fatigue + manual availability; `get_team_readiness` route fetches `player_status` rows.
- `backend/app/main.py` — register the new scouting router.
- `backend/tests/fakes_supabase.py` — add fake table doubles for `scouting_notes` and `player_status`.
- `backend/tests/test_players_router.py` — update fixtures for the new `team_id`/`position_bucket` fields, add new tests.
- `backend/tests/test_matches_router.py` — add composite-readiness tests.

**Frontend — create:**
- `frontend/src/components/CircularProgress.jsx` — extracted from `Dashboard.jsx` so `SquadDepth.jsx` can reuse it (avoids duplicating the same SVG ring twice).
- `frontend/src/components/ScoutingNotes.jsx` — note list + write form, used inside `PlayerModal`.

**Frontend — modify:**
- `frontend/src/services/api.js` — add `postJSON` helper + 4 new API functions.
- `frontend/src/components/PlayerModal.jsx` — render `<ScoutingNotes>`.
- `frontend/src/pages/SquadDepth.jsx` — Squad Readiness card, inline per-player status editor (Coach only), status badges (everyone else).
- `frontend/src/pages/Players.jsx` — team column + team filter, position resolved from the performance response instead of the Barcelona-scoped `/depth` endpoint.
- `frontend/src/pages/Dashboard.jsx` — use the extracted `CircularProgress`; scope "Top Performers" back to Barcelona now that `/performance` is global (else opponents' stats leak into the "Season Snapshot" card).

**Interfaces summary (for tasks reading out of order):**
- `build_readiness_response(at_risk_players, player_statuses=None)` → `{"readiness_score": int, "at_risk_players": [...], "unavailable_players": [...], "doubtful_players": [...]}`.
- `aggregate_performance(stats_rows, players_by_id)` rows now include `"team_id"` and `"position_bucket"` (one of `"Goalkeeper"/"Defender"/"Midfielder"/"Forward"`/`None`).
- `attach_team_names(performance_rows, teams_by_id)` → mutates+returns rows, adding `"team_name"`.
- Frontend `getScoutingNotes(playerId)`, `postScoutingNote(playerId, note, rating)`, `getPlayerStatuses()`, `postPlayerStatus(playerId, status, note)` in `services/api.js`.

---

## Task 1: `player_status` table (migration + schema)

**Files:**
- Create: `backend/app/data/migrations/0004_add_player_status.sql`
- Modify: `backend/app/data/schema_v2.sql`

- [ ] **Step 1: Write the migration file**

```sql
-- schema_v2.sql is the source of truth for fresh installs and already
-- includes this table; this migration exists to bring an already-created
-- pitchiq-v2-dev database (created before this table existed) up to date.
--
-- There is no migration runner wired up in this project yet, so this file
-- must be run by hand once, in the Supabase SQL editor (or via psql against
-- the project's direct connection string).
--
-- One row per player: their current availability as set by the coaching
-- staff, independent of the fatigue-risk rule (which is computed from match
-- data, see app/services/fatigue.py). player_id is the primary key -- Coach
-- sets a player's *current* status, not a history of past ones, so the
-- POST /api/players/status handler upserts in place rather than appending.
create table if not exists player_status (
  player_id integer primary key references players(id),
  status text not null check (status in ('available', 'doubtful', 'unavailable')),
  note text,
  updated_by uuid references auth.users(id),
  updated_at timestamptz not null default now()
);
```

- [ ] **Step 2: Add the same table to `schema_v2.sql`**

Insert this block into `backend/app/data/schema_v2.sql` immediately after the `user_roles` table (currently ends at line 115, right before the `analytics_cache` comment block):

```sql
create table player_status (
  player_id integer primary key references players(id),
  status text not null check (status in ('available', 'doubtful', 'unavailable')),
  note text,
  updated_by uuid references auth.users(id),
  updated_at timestamptz not null default now()
);
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/data/migrations/0004_add_player_status.sql backend/app/data/schema_v2.sql
git commit -m "Add player_status table for coach-managed availability"
```

**Note for later:** this migration is not yet applied to the live `pitchiq-v2-dev` project (confirmed via direct query — see Task 11). The Availability Management feature will 500 against the real database until Task 11 is done. Backend tests use a fake DB double and are unaffected.

---

## Task 2: Fake DB doubles for the new tables

**Files:**
- Modify: `backend/tests/fakes_supabase.py`

**Interfaces:**
- Produces: `FakeClient(..., scouting_notes=None, player_statuses=None)` — new optional constructor args, dispatched by `FakeClient.table("scouting_notes")` / `FakeClient.table("player_status")`.

- [ ] **Step 1: Add the two fake table classes and wire them into `FakeClient`**

Add to `backend/tests/fakes_supabase.py` (after `FakeAnalyticsCacheTable`, before `FakeClient`):

```python
class FakeScoutingNotesTable:
    """rows: list of dicts shaped like real scouting_notes rows. insert()
    appends and assigns an incrementing id + fixed created_at (deterministic
    for tests) -- order()/eq() operate on whatever select() staged.
    """
    def __init__(self, rows=None):
        self._rows = list(rows or [])
        self._result = None

    def select(self, *_args, **_kwargs):
        self._result = list(self._rows)
        return self

    def eq(self, column, value):
        assert column == "player_id"
        self._result = [r for r in self._result if r["player_id"] == value]
        return self

    def order(self, column, desc=False):
        assert column == "created_at"
        self._result = sorted(self._result, key=lambda r: r["created_at"], reverse=desc)
        return self

    def insert(self, payload):
        row = {**payload, "id": len(self._rows) + 1, "created_at": "2026-07-26T00:00:00Z"}
        self._rows.append(row)
        self._result = [row]
        return self

    def execute(self):
        return FakeResult(self._result if self._result is not None else [])


class FakePlayerStatusTable:
    """rows: list of dicts shaped like real player_status rows. upsert()
    replaces any existing row for that player_id (player_id is the real
    table's primary key, so this mirrors real upsert-on-conflict behavior).
    """
    def __init__(self, rows=None):
        self._rows = list(rows or [])
        self._result = None

    def select(self, *_args, **_kwargs):
        self._result = list(self._rows)
        return self

    def upsert(self, payload, **_kwargs):
        self._rows = [r for r in self._rows if r["player_id"] != payload["player_id"]]
        self._rows.append(payload)
        self._result = [payload]
        return self

    def execute(self):
        return FakeResult(self._result if self._result is not None else [])
```

Then update `FakeClient` (constructor and `table()`):

```python
class FakeClient:
    def __init__(self, user=None, raise_on_get_user=False, roles_by_user_id=None,
                 analytics_cache_rows=None, scouting_notes=None, player_statuses=None):
        self.auth = FakeAuth(user=user, raise_on_get_user=raise_on_get_user)
        self._roles_by_user_id = roles_by_user_id or {}
        self._analytics_cache_rows = analytics_cache_rows or {}
        self._scouting_notes = scouting_notes
        self._player_statuses = player_statuses

    def table(self, name):
        if name == "user_roles":
            return FakeRolesTable(self._roles_by_user_id)
        if name == "analytics_cache":
            return FakeAnalyticsCacheTable(self._analytics_cache_rows)
        if name == "scouting_notes":
            return FakeScoutingNotesTable(self._scouting_notes)
        if name == "player_status":
            return FakePlayerStatusTable(self._player_statuses)
        raise AssertionError(f"FakeClient.table() called with unexpected table: {name}")
```

- [ ] **Step 2: Run the existing auth test suite to confirm nothing broke**

Run: `cd backend && python -m pytest tests/test_auth.py tests/test_whoami.py -v`
Expected: all pass (these tests never construct `FakeClient` with the new args, so the added `=None` defaults are no-ops for them).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/fakes_supabase.py
git commit -m "Add fake scouting_notes/player_status tables for router tests"
```

---

## Task 3: Scouting Notes router (TDD)

**Files:**
- Create: `backend/app/routers/scouting.py`
- Create: `backend/tests/test_scouting_router.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `AuthenticatedUser`, `get_current_user`, `require_role` from `app.auth` (`backend/app/auth.py:24-81`); `get_db` from `app.db`.
- Produces: `router` (APIRouter, prefix `/api/scouting`) importable as `app.routers.scouting.router`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_scouting_router.py`:

```python
"""Tests for GET/POST /api/scouting/notes -- Scout writes, Analyst/Scout
read, Coach is blocked from writing (403). No access-control check is
needed on GET beyond "authenticated" (any role can read); hiding the
section from Coach entirely is a frontend concern, not a backend 403.
"""

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from tests.fakes_supabase import FakeClient, FakeUser

client = TestClient(app)


def test_post_scouting_note_as_coach_returns_403():
    fake_user = FakeUser(id="coach-1", email="coach@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"coach-1": "coach"}
    )
    try:
        response = client.post(
            "/api/scouting/notes",
            json={"player_id": 5503, "note": "Good pace", "rating": 4},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_post_scouting_note_as_scout_succeeds():
    fake_user = FakeUser(id="scout-1", email="scout@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"scout-1": "scout"}, scouting_notes=[]
    )
    try:
        response = client.post(
            "/api/scouting/notes",
            json={"player_id": 5503, "note": "Good pace, needs work off the ball", "rating": 4},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["player_id"] == 5503
    assert body["rating"] == 4
    assert body["author_id"] == "scout-1"


def test_post_scouting_note_rejects_rating_out_of_range():
    fake_user = FakeUser(id="scout-1", email="scout@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"scout-1": "scout"}, scouting_notes=[]
    )
    try:
        response = client.post(
            "/api/scouting/notes",
            json={"player_id": 5503, "note": "Note", "rating": 7},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_get_scouting_notes_as_analyst_returns_notes_for_that_player_only():
    existing = [
        {"id": 1, "player_id": 5503, "author_id": "scout-1", "note": "Sharp finishing",
         "rating": 5, "created_at": "2026-07-20T00:00:00Z"},
        {"id": 2, "player_id": 9999, "author_id": "scout-1", "note": "Different player",
         "rating": 3, "created_at": "2026-07-20T00:00:00Z"},
    ]
    fake_user = FakeUser(id="analyst-1", email="analyst@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"analyst-1": "analyst"}, scouting_notes=existing
    )
    try:
        response = client.get(
            "/api/scouting/notes", params={"player_id": 5503},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["note"] == "Sharp finishing"


def test_get_scouting_notes_requires_auth():
    app.dependency_overrides.clear()
    response = client.get("/api/scouting/notes", params={"player_id": 5503})
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_scouting_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.routers.scouting'` (or import error), since the router doesn't exist yet.

- [ ] **Step 3: Write the router**

Create `backend/app/routers/scouting.py`:

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import AuthenticatedUser, get_current_user, require_role
from app.db import get_db

router = APIRouter(prefix="/api/scouting", tags=["scouting"])


class ScoutingNoteCreate(BaseModel):
    player_id: int
    note: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)


@router.get("/notes")
def get_scouting_notes(
    player_id: int,
    _user: AuthenticatedUser = Depends(get_current_user),
    client=Depends(get_db),
):
    return client.table("scouting_notes").select(
        "id, player_id, author_id, note, rating, created_at"
    ).eq("player_id", player_id).order("created_at", desc=True).execute().data


@router.post("/notes")
def create_scouting_note(
    body: ScoutingNoteCreate,
    user: AuthenticatedUser = Depends(require_role("scout")),
    client=Depends(get_db),
):
    payload = {
        "player_id": body.player_id,
        "author_id": user.id,
        "note": body.note,
        "rating": body.rating,
    }
    result = client.table("scouting_notes").insert(payload).execute()
    return result.data[0] if result.data else payload
```

**Important discovered during implementation:** `players.py`/`matches.py` call `supabase = get_db()` directly inside the route body — a plain function call, invisible to FastAPI's dependency injection, so `app.dependency_overrides[get_db]` has **no effect** on it (confirmed the hard way: the first version of this router used that style and the "success path" test below silently hit the *real* `pitchiq-v2-dev` database). `analytics.py`/`pipeline.py` already use the injectable `client=Depends(get_db)` parameter style instead, which IS overridable. Use `client=Depends(get_db)` for any new route that needs a `FakeClient`-backed test — which both new routers in this plan do.

- [ ] **Step 4: Register the router**

In `backend/app/main.py`, add the import and registration:

```python
from app.routers.scouting import router as scouting_router
```

```python
app.include_router(scouting_router)
```

(Add both lines alongside the existing router imports/registrations — order doesn't matter, FastAPI merges all routers onto one app.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_scouting_router.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/scouting.py backend/app/main.py backend/tests/test_scouting_router.py
git commit -m "Add GET/POST /api/scouting/notes (scout write, any role read)"
```

---

## Task 4: Availability Management router (TDD)

**Files:**
- Modify: `backend/app/routers/players.py`
- Create: `backend/tests/test_player_status_router.py`

**Interfaces:**
- Produces: `GET /api/players/status`, `POST /api/players/status` on the existing `players.router` (prefix `/api/players`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_player_status_router.py`:

```python
"""Tests for GET/POST /api/players/status -- Coach writes (sets a player's
current availability), any authenticated role reads. Analyst and Scout must
both be blocked from writing (403).
"""

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from tests.fakes_supabase import FakeClient, FakeUser

client = TestClient(app)


def test_post_player_status_as_analyst_returns_403():
    fake_user = FakeUser(id="analyst-1", email="analyst@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"analyst-1": "analyst"}
    )
    try:
        response = client.post(
            "/api/players/status",
            json={"player_id": 5503, "status": "doubtful"},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_post_player_status_as_scout_returns_403():
    fake_user = FakeUser(id="scout-1", email="scout@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"scout-1": "scout"}
    )
    try:
        response = client.post(
            "/api/players/status",
            json={"player_id": 5503, "status": "unavailable"},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_post_player_status_as_coach_succeeds():
    fake_user = FakeUser(id="coach-1", email="coach@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"coach-1": "coach"}, player_statuses=[]
    )
    try:
        response = client.post(
            "/api/players/status",
            json={"player_id": 5503, "status": "doubtful", "note": "Tight hamstring"},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["player_id"] == 5503
    assert body["status"] == "doubtful"
    assert body["updated_by"] == "coach-1"


def test_post_player_status_rejects_invalid_status_value():
    fake_user = FakeUser(id="coach-1", email="coach@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"coach-1": "coach"}, player_statuses=[]
    )
    try:
        response = client.post(
            "/api/players/status",
            json={"player_id": 5503, "status": "injured"},
            headers={"Authorization": "Bearer good-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_get_player_statuses_returns_all_rows_for_any_authenticated_role():
    existing = [{"player_id": 5503, "status": "doubtful", "note": None,
                 "updated_by": "coach-1", "updated_at": "2026-07-26T00:00:00Z"}]
    fake_user = FakeUser(id="scout-1", email="scout@example.com")
    app.dependency_overrides[get_db] = lambda: FakeClient(
        user=fake_user, roles_by_user_id={"scout-1": "scout"}, player_statuses=existing
    )
    try:
        response = client.get("/api/players/status", headers={"Authorization": "Bearer good-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == existing


def test_get_player_statuses_requires_auth():
    app.dependency_overrides.clear()
    response = client.get("/api/players/status")
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_player_status_router.py -v`
Expected: FAIL — 404 Not Found for all requests (route doesn't exist yet).

- [ ] **Step 3: Add the endpoints to `players.py`**

In `backend/app/routers/players.py`, the file currently starts with:

```python
from fastapi import APIRouter, Depends

from app.auth import AuthenticatedUser, get_current_user
```

Change it to (two new lines added above, `require_role` added to the existing `app.auth` import — do not duplicate the `fastapi`/`app.auth` lines):

```python
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import AuthenticatedUser, get_current_user, require_role
```

Add this class and these two routes at the end of the file:

```python
class PlayerStatusUpdate(BaseModel):
    player_id: int
    status: Literal["available", "doubtful", "unavailable"]
    note: Optional[str] = None


@router.get("/status")
def get_player_statuses(_user: AuthenticatedUser = Depends(get_current_user), client=Depends(get_db)):
    return client.table("player_status").select(
        "player_id, status, note, updated_by, updated_at"
    ).execute().data


@router.post("/status")
def set_player_status(
    body: PlayerStatusUpdate,
    user: AuthenticatedUser = Depends(require_role("coach")),
    client=Depends(get_db),
):
    payload = {
        "player_id": body.player_id,
        "status": body.status,
        "note": body.note,
        "updated_by": user.id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = client.table("player_status").upsert(payload).execute()
    return result.data[0] if result.data else payload
```

(Use `client=Depends(get_db)` here, not `supabase = get_db()` — see the note at the end of Task 3 explaining why the direct-call style used elsewhere in `players.py` isn't fakeable via `dependency_overrides`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_player_status_router.py -v`
Expected: 6 passed.

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `cd backend && python -m pytest -v`
Expected: all pass (the `Literal`/`Optional`/`BaseModel` imports must not collide with anything else already in `players.py` — check the diff if anything unexpectedly fails).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/players.py backend/tests/test_player_status_router.py
git commit -m "Add GET/POST /api/players/status (coach-only write)"
```

---

## Task 5: Squad Readiness composite (TDD)

**Files:**
- Modify: `backend/app/routers/matches.py`
- Modify: `backend/tests/test_matches_router.py`

**Interfaces:**
- Produces: `build_readiness_response(at_risk_players, player_statuses=None)` — the `player_statuses=None` default keeps the two existing tests (which call it with one argument) passing unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_matches_router.py`, directly after the existing `test_readiness_score_floors_at_zero` (~line 104):

```python
def test_readiness_score_penalizes_unavailable_players():
    result = build_readiness_response(
        at_risk_players=[],
        player_statuses=[{"player_id": 1, "status": "unavailable"}],
    )

    assert result["readiness_score"] == 85
    assert result["unavailable_players"] == [{"player_id": 1, "status": "unavailable"}]
    assert result["doubtful_players"] == []


def test_readiness_score_penalizes_doubtful_players_less_than_unavailable():
    result = build_readiness_response(
        at_risk_players=[],
        player_statuses=[{"player_id": 2, "status": "doubtful"}],
    )

    assert result["readiness_score"] == 93
    assert result["doubtful_players"] == [{"player_id": 2, "status": "doubtful"}]


def test_readiness_does_not_double_penalize_a_player_both_fatigued_and_unavailable():
    # A player already marked unavailable by the coach is definitely not
    # playing -- their fatigue-risk flag would be redundant information, so
    # it must not also cost 5 points on top of the 15-point unavailable
    # penalty.
    result = build_readiness_response(
        at_risk_players=[{"player_id": 1}],
        player_statuses=[{"player_id": 1, "status": "unavailable"}],
    )

    assert result["readiness_score"] == 85  # 100 - 15, not 100 - 15 - 5


def test_readiness_still_counts_fatigue_for_a_doubtful_player():
    # Doubtful is not a confirmed absence -- fatigue risk still applies on
    # top of it.
    result = build_readiness_response(
        at_risk_players=[{"player_id": 2}],
        player_statuses=[{"player_id": 2, "status": "doubtful"}],
    )

    assert result["readiness_score"] == 88  # 100 - 5 (fatigue) - 7 (doubtful)


def test_readiness_with_no_player_statuses_matches_fatigue_only_behavior():
    # Backward-compatible default -- omitting player_statuses entirely must
    # behave exactly like the old fatigue-only formula.
    at_risk = [{"player_id": 1}, {"player_id": 2}]

    result = build_readiness_response(at_risk)

    assert result["readiness_score"] == 90
    assert result["unavailable_players"] == []
    assert result["doubtful_players"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_matches_router.py -k readiness -v`
Expected: FAIL — `TypeError: build_readiness_response() takes 1 positional argument but 2 were given`, and `KeyError`/`AssertionError` on the missing `unavailable_players`/`doubtful_players` keys.

- [ ] **Step 3: Rewrite `build_readiness_response` and the route**

In `backend/app/routers/matches.py`, replace the existing `build_readiness_response` (currently lines 51-53):

```python
def build_readiness_response(at_risk_players, player_statuses=None):
    """at_risk_players: from get_at_risk_players (fatigue rule only).
    player_statuses: player_status rows ({"player_id", "status", ...}),
    the coach's manually-set availability -- independent signal from fatigue.

    A player marked unavailable is definitely not playing, so their fatigue
    flag (if any) is dropped from the fatigue penalty to avoid double-
    counting the same absence twice. Doubtful is not a confirmed absence,
    so fatigue still applies on top of it.
    """
    player_statuses = player_statuses or []
    unavailable = [s for s in player_statuses if s["status"] == "unavailable"]
    doubtful = [s for s in player_statuses if s["status"] == "doubtful"]
    unavailable_ids = {s["player_id"] for s in unavailable}

    counted_at_risk = [p for p in at_risk_players if p["player_id"] not in unavailable_ids]
    fatigue_penalty = 5 * len(counted_at_risk)
    availability_penalty = 15 * len(unavailable) + 7 * len(doubtful)

    score = max(0, 100 - fatigue_penalty - availability_penalty)
    return {
        "readiness_score": score,
        "at_risk_players": at_risk_players,
        "unavailable_players": unavailable,
        "doubtful_players": doubtful,
    }
```

Then update the route (currently lines 224-228):

```python
@team_router.get("/readiness")
def get_team_readiness(_user: AuthenticatedUser = Depends(get_current_user)):
    supabase = get_db()
    at_risk = get_at_risk_players(supabase, BARCELONA_TEAM_ID)

    status_rows = supabase.table("player_status").select(
        "player_id, status, note, updated_by, updated_at, players(name, nickname)"
    ).execute().data
    player_statuses = []
    for r in status_rows:
        joined = r.pop("players", None) or {}
        player_statuses.append({**r, "name": joined.get("name"), "nickname": joined.get("nickname")})

    return build_readiness_response(at_risk, player_statuses)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_matches_router.py -k readiness -v`
Expected: 7 passed (2 original + 5 new).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/matches.py backend/tests/test_matches_router.py
git commit -m "Make Squad Readiness a composite of fatigue-risk and manual availability"
```

---

## Task 6: Unscope `/api/players/performance` (opponent visibility)

**Files:**
- Modify: `backend/app/routers/players.py`
- Modify: `backend/tests/test_players_router.py`
- Create: `backend/tests/test_players_performance_scope.py`

**Interfaces:**
- Produces: `aggregate_performance(...)` rows now carry `"team_id"` and `"position_bucket"`. New pure function `attach_team_names(performance_rows, teams_by_id)`.

- [ ] **Step 1: Update the existing test fixtures (they'll break otherwise)**

In `backend/tests/test_players_router.py`, every `stats_rows` dict in the three existing `aggregate_performance` tests is missing `"team_id"`, and every `players_by_id` dict is missing `"primary_position"` — both become required once the implementation reads them. Update each of the three existing tests:

`test_performance_rows_include_name_and_nickname` (~line 84): add `"team_id": 217` to the stats row, and change `players_by_id` to:
```python
players_by_id = {5503: {"name": "Lionel Messi", "nickname": None, "primary_position": "Right Wing"}}
```
Add these two assertions at the end of the test:
```python
    assert result[0]["team_id"] == 217
    assert result[0]["position_bucket"] == "Forward"
```

`test_performance_rows_sum_real_assists_across_matches` (~line 109): add `"team_id": 217` to both stats rows, and change `players_by_id` to:
```python
players_by_id = {5503: {"name": "Lionel Messi", "nickname": None, "primary_position": "Right Wing"}}
```
(No new assertions needed — this test is about assist summing.)

`test_performance_rows_sum_pressures_and_pressure_regains_across_matches` (~line 136): same two changes (add `"team_id": 217` to both rows, add `"primary_position"` to `players_by_id`).

- [ ] **Step 2: Write the new failing tests**

Add to `backend/tests/test_players_router.py`, after the pressures test:

```python
# --------------------- opponent visibility: team_id / position_bucket ---------------------

def test_performance_rows_position_bucket_is_none_when_unresolvable():
    stats_rows = [
        {"player_id": 42, "team_id": 999, "minutes_played": 10, "passes_attempted": 0,
         "passes_completed": 0, "key_passes": 0, "progressive_passes": 0,
         "shots": 0, "goals": 0, "xg": 0.0, "xa": 0.0, "assists": 0,
         "dribbles_attempted": 0, "dribbles_completed": 0,
         "progressive_carries": 0, "tackles": 0,
         "pressures": 0, "pressure_regains": 0},
    ]
    players_by_id = {42: {"name": "Mystery Sub", "nickname": None, "primary_position": None}}

    result = aggregate_performance(stats_rows, players_by_id)

    assert result[0]["team_id"] == 999
    assert result[0]["position_bucket"] is None


def test_attach_team_names_resolves_team_id_to_name():
    rows = [{"player_id": 1, "team_id": 217}, {"player_id": 2, "team_id": 215}]
    teams_by_id = {217: "Barcelona", 215: "Athletic Club"}

    result = attach_team_names(rows, teams_by_id)

    assert result[0]["team_name"] == "Barcelona"
    assert result[1]["team_name"] == "Athletic Club"


def test_attach_team_names_is_none_for_unknown_team_id():
    rows = [{"player_id": 1, "team_id": 999}]

    result = attach_team_names(rows, {})

    assert result[0]["team_name"] is None
```

Add `attach_team_names` to the import line at the top of the file:
```python
from app.routers.players import (
    BUCKET_ORDER,
    aggregate_performance,
    attach_team_names,
    bucket_position,
    build_depth_response,
)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_players_router.py -v`
Expected: FAIL — `ImportError: cannot import name 'attach_team_names'`, plus `KeyError: 'team_id'` in the three updated tests (implementation doesn't produce these fields yet).

- [ ] **Step 4: Implement in `backend/app/routers/players.py`**

Remove the team scoping constant's use on `/performance` (keep `BARCELONA_TEAM_ID` — it's still used by `/fatigue-risk` and `/depth`, which stay squad-scoped on purpose).

Replace `_players_by_id` (currently lines 139-145):

```python
def _players_by_id(client, player_ids):
    if not player_ids:
        return {}
    rows = client.table("players").select("id, name, nickname, primary_position").in_(
        "id", list(player_ids)
    ).execute().data
    return {r["id"]: {"name": r["name"], "nickname": r["nickname"],
                      "primary_position": r["primary_position"]} for r in rows}
```

In `aggregate_performance`, add `"team_id": row["team_id"]` to the per-player init dict (inside the `if pid not in aggregated:` block, alongside `"player_id": pid`), and add `position_bucket` when building the result list — the final loop currently reads:

```python
        meta = players_by_id.get(p["player_id"], {})
        p["name"] = meta.get("name")
        p["nickname"] = meta.get("nickname")
        result.append(p)
```

Change to:

```python
        meta = players_by_id.get(p["player_id"], {})
        p["name"] = meta.get("name")
        p["nickname"] = meta.get("nickname")
        p["position_bucket"] = bucket_position(meta.get("primary_position"))
        result.append(p)
```

Add a new pure function right after `aggregate_performance`:

```python
def attach_team_names(performance_rows, teams_by_id):
    for row in performance_rows:
        row["team_name"] = teams_by_id.get(row["team_id"])
    return performance_rows
```

Replace the `/performance` route (currently lines 148-160):

```python
@router.get("/performance")
def get_player_performance(_user: AuthenticatedUser = Depends(get_current_user)):
    supabase = get_db()

    stats_rows = supabase.table("player_match_stats").select(
        "player_id, team_id, minutes_played, passes_attempted, passes_completed, "
        "key_passes, progressive_passes, shots, goals, assists, xg, xa, "
        "dribbles_attempted, dribbles_completed, progressive_carries, tackles, "
        "pressures, pressure_regains"
    ).execute().data

    players_by_id = _players_by_id(supabase, {r["player_id"] for r in stats_rows})
    performance = aggregate_performance(stats_rows, players_by_id)

    teams_rows = supabase.table("teams").select("id, name").execute().data
    teams_by_id = {t["id"]: t["name"] for t in teams_rows}
    return attach_team_names(performance, teams_by_id)
```

(Note: `.eq("team_id", BARCELONA_TEAM_ID)` is gone from this query — that's the entire opponent-visibility fix. `/fatigue-risk` and `/depth` below it are untouched.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_players_router.py -v`
Expected: all pass.

- [ ] **Step 6: Write the real-data regression test**

Create `backend/tests/test_players_performance_scope.py`:

```python
"""Integration test proving /api/players/performance is not scoped to a
single team -- regression test for the opponent-visibility fix (it used to
filter to team_id=217/Barcelona only). Uses a real token against the real
pitchiq-v2-dev project, skipped if Supabase isn't configured (mirrors
test_role_gating.py).
"""

import pytest
from fastapi.testclient import TestClient
from supabase import create_client

from app.config import SUPABASE_KEY, SUPABASE_URL
from app.main import app

pytestmark = pytest.mark.skipif(
    not SUPABASE_URL or not SUPABASE_KEY,
    reason="SUPABASE_URL/SUPABASE_KEY not configured",
)

# Same anon/publishable key already used in test_role_gating.py and shipped
# in the frontend -- safe to hardcode, it only grants sign-in.
ANON_KEY = "sb_publishable_QgX_qUdGGp05HNRkgKV9ww_jDz90TdS"

client = TestClient(app)


def test_performance_includes_players_from_more_than_one_team():
    anon = create_client(SUPABASE_URL, ANON_KEY)
    res = anon.auth.sign_in_with_password({"email": "scout@example.com", "password": "Scout123!"})
    token = res.session.access_token

    response = client.get("/api/players/performance", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    team_ids = {p["team_id"] for p in body}
    assert len(team_ids) > 1
    assert len(body) > 25  # more than just Barcelona's squad
```

- [ ] **Step 7: Run it against the real project**

Run: `cd backend && python -m pytest tests/test_players_performance_scope.py -v`
Expected: 1 passed (this hits the real `pitchiq-v2-dev` project — confirms 20 teams / 389 players are all reachable now).

- [ ] **Step 8: Run the full backend suite**

Run: `cd backend && python -m pytest -v`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add backend/app/routers/players.py backend/tests/test_players_router.py backend/tests/test_players_performance_scope.py
git commit -m "Unscope /api/players/performance from Barcelona-only (opponent visibility)"
```

---

## Task 7: Frontend API client additions

**Files:**
- Modify: `frontend/src/services/api.js`

- [ ] **Step 1: Add a JSON-body POST helper and the four new API functions**

In `frontend/src/services/api.js`, add after the existing `post` function (line 39):

```js
async function postJSON(path, body) {
  const headers = {
    'Content-Type': 'application/json',
    ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
  };
  const res = await fetch(`${BASE}${path}`, { method: 'POST', headers, body: JSON.stringify(body) });
  if (!res.ok) {
    const err = new Error(`${res.status} ${res.statusText}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}
```

Add after the existing `export const getPipelineStatus...` block:

```js
export const getScoutingNotes  = (playerId) => get(`/api/scouting/notes?player_id=${playerId}`);
export const postScoutingNote  = (playerId, note, rating) =>
  postJSON('/api/scouting/notes', { player_id: playerId, note, rating });
export const getPlayerStatuses = () => get('/api/players/status');
export const postPlayerStatus  = (playerId, status, note) =>
  postJSON('/api/players/status', { player_id: playerId, status, note });
```

- [ ] **Step 2: Sanity-check with a lint pass**

Run: `cd frontend && npm run lint`
Expected: no new errors from `api.js`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "Add scouting notes and player status API functions"
```

---

## Task 8: Scouting Notes UI on the player modal

**Files:**
- Create: `frontend/src/components/ScoutingNotes.jsx`
- Modify: `frontend/src/components/PlayerModal.jsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/ScoutingNotes.jsx`:

```jsx
import { useState, useEffect } from 'react';
import { useAuth } from '../services/AuthProvider';
import { getScoutingNotes, postScoutingNote } from '../services/api';

const ACC = '#FF6B35';

function RatingPicker({ value, onChange }) {
  return (
    <div style={{ display: 'flex', gap: 6 }}>
      {[1, 2, 3, 4, 5].map(n => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(n)}
          style={{
            width: 28, height: 28, borderRadius: 7, border: '1px solid rgba(255,255,255,0.1)',
            background: value === n ? ACC : 'rgba(255,255,255,0.04)',
            color: value === n ? '#1a0f08' : 'var(--text-secondary)',
            fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 12,
            cursor: 'pointer', transition: 'background 0.15s, color 0.15s',
          }}
        >
          {n}
        </button>
      ))}
    </div>
  );
}

function NoteCard({ note }) {
  const dateStr = new Date(note.created_at).toLocaleDateString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
  });
  return (
    <div style={{
      padding: '12px 14px', background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: '0.08em', color: 'var(--text-muted)' }}>SCOUT</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontFamily: 'Space Grotesk', fontSize: 12, fontWeight: 700, color: ACC }}>{note.rating}/5</span>
          <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{dateStr}</span>
        </div>
      </div>
      <div style={{ fontSize: 12.5, color: 'var(--text-primary)', lineHeight: 1.5 }}>{note.note}</div>
    </div>
  );
}

export default function ScoutingNotes({ playerId }) {
  const { role } = useAuth();
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState('');
  const [rating, setRating] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  const visible = role === 'scout' || role === 'analyst';

  useEffect(() => {
    if (!visible) return;
    setLoading(true);
    getScoutingNotes(playerId)
      .then(setNotes)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [playerId, visible]);

  if (!visible) return null;

  const handleSubmit = async () => {
    if (!draft.trim() || !rating) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await postScoutingNote(playerId, draft.trim(), rating);
      setNotes(prev => [created, ...prev]);
      setDraft('');
      setRating(0);
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: '0 22px 22px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <div style={{ width: 3, height: 16, background: ACC, borderRadius: 2 }} />
        <div style={{ fontFamily: 'Space Grotesk', fontSize: 13.5, fontWeight: 600 }}>Scouting Notes</div>
      </div>

      {role === 'scout' && (
        <div style={{
          marginBottom: 14, padding: 14, background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12,
        }}>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Write a note on this player..."
            rows={3}
            style={{
              width: '100%', resize: 'vertical', padding: '9px 11px', fontSize: 12.5,
              fontFamily: 'inherit', background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8,
              color: 'var(--text-primary)', outline: 'none', marginBottom: 10, boxSizing: 'border-box',
            }}
          />
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
            <RatingPicker value={rating} onChange={setRating} />
            <button
              onClick={handleSubmit}
              disabled={submitting || !draft.trim() || !rating}
              style={{
                padding: '7px 16px', borderRadius: 8, border: 'none',
                background: (!draft.trim() || !rating) ? 'rgba(255,107,53,0.3)' : ACC,
                color: '#1a0f08', fontSize: 12, fontWeight: 700,
                cursor: (!draft.trim() || !rating) ? 'default' : 'pointer',
                transition: 'background 0.15s',
              }}
            >
              {submitting ? 'Saving...' : 'Save Note'}
            </button>
          </div>
        </div>
      )}

      {loading && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Loading notes...</div>}
      {error && <div style={{ fontSize: 12, color: 'var(--red)' }}>{error}</div>}
      {!loading && notes.length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No scouting notes yet.</div>
      )}
      {!loading && notes.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {notes.map(n => <NoteCard key={n.id} note={n} />)}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire it into `PlayerModal.jsx`**

Add the import at the top of `frontend/src/components/PlayerModal.jsx`:

```js
import ScoutingNotes from './ScoutingNotes';
```

Add `<ScoutingNotes playerId={player.player_id} />` immediately after the closing `</div>` of the stats grid (right before the final `</Modal>` at line 67):

```jsx
        </div>
      </div>

      <ScoutingNotes playerId={player.player_id} />
    </Modal>
  );
}
```

- [ ] **Step 3: Lint**

Run: `cd frontend && npm run lint`
Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ScoutingNotes.jsx frontend/src/components/PlayerModal.jsx
git commit -m "Add Scouting Notes section to the player modal"
```

(This will be checked live in Task 13 — real 200/403 responses need the backend running and a real Scout/Analyst/Coach login.)

---

## Task 9: Squad Readiness + inline availability editor on Squad Depth

**Files:**
- Create: `frontend/src/components/CircularProgress.jsx`
- Modify: `frontend/src/pages/Dashboard.jsx`
- Modify: `frontend/src/pages/SquadDepth.jsx`

- [ ] **Step 1: Extract `CircularProgress` out of `Dashboard.jsx`**

Create `frontend/src/components/CircularProgress.jsx` with the existing implementation (currently `Dashboard.jsx:11-31`):

```jsx
import { useState, useEffect } from 'react';

const ACC = '#FF6B35';

export default function CircularProgress({ value, size = 72, stroke = 5 }) {
  const r = (size - stroke * 2) / 2;
  const circ = 2 * Math.PI * r;
  const [animPct, setAnimPct] = useState(0);
  useEffect(() => { const t = setTimeout(() => setAnimPct(value / 100), 100); return () => clearTimeout(t); }, [value]);
  const dash = animPct * circ;
  return (
    <div style={{ position: 'relative', flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={ACC}
          strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={`${dash} ${circ}`}
          style={{ transition: 'stroke-dasharray 1.2s cubic-bezier(0.4,0,0.2,1)', filter: `drop-shadow(0 0 6px ${ACC}88)` }} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'Space Grotesk', fontSize: 12, fontWeight: 700, color: ACC, fontVariantNumeric: 'tabular-nums' }}>
        {value}%
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Update `Dashboard.jsx` to import it instead of defining it locally**

Remove the local `CircularProgress` function definition (`Dashboard.jsx:11-31`) and add the import at the top:

```js
import CircularProgress from '../components/CircularProgress';
```

- [ ] **Step 3: Run lint + start the dev server to visually confirm the Dashboard still renders identically**

Run: `cd frontend && npm run lint`
Expected: no errors, no unused-import warnings.

(Full visual confirmation happens in Task 13 alongside everything else.)

- [ ] **Step 4: Commit the extraction**

```bash
git add frontend/src/components/CircularProgress.jsx frontend/src/pages/Dashboard.jsx
git commit -m "Extract CircularProgress into a shared component"
```

- [ ] **Step 5: Add Squad Readiness + inline status editing to `SquadDepth.jsx`**

Rewrite `frontend/src/pages/SquadDepth.jsx`. Key changes from the current file:
- New imports: `useAuth`, `getTeamReadiness`, `getPlayerStatuses`, `postPlayerStatus`, `CircularProgress`.
- New state: `readiness`, `statusByPlayerId` (built from `getPlayerStatuses()`, keyed by `player_id`).
- New `ReadinessCard` rendered above the existing position-count row.
- `DepthCard`'s player rows gain a `StatusBadge` (read-only, all roles) or `StatusSelect` (Coach only, replaces the badge) next to the existing fit/at-risk dot.

Full file:

```jsx
import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { getSquadDepth, getFatigueRisk, getTeamReadiness, getPlayerStatuses, postPlayerStatus } from '../services/api';
import { useAuth } from '../services/AuthProvider';
import CircularProgress from '../components/CircularProgress';

const ACC = '#FF6B35';

const POSITIONS = [
  { key: 'Goalkeeper', abbr: 'GK',  plural: 'Goalkeepers', colorHex: '#58A6FF', color: 'var(--blue)',   dim: 'var(--blue-dim)'   },
  { key: 'Defender',   abbr: 'DEF', plural: 'Defenders',   colorHex: '#3FB950', color: 'var(--green)',  dim: 'var(--green-dim)'  },
  { key: 'Midfielder', abbr: 'MID', plural: 'Midfielders', colorHex: '#A78BFA', color: 'var(--purple)', dim: 'var(--purple-dim)' },
  { key: 'Forward',    abbr: 'FWD', plural: 'Forwards',    colorHex: '#FF6B35', color: 'var(--orange)', dim: 'var(--orange-dim)' },
];

const STATUS_META = {
  available:   { label: 'AVAILABLE',   color: 'var(--green)',  bg: 'var(--green-dim)'  },
  doubtful:    { label: 'DOUBTFUL',    color: 'var(--yellow)', bg: 'var(--yellow-dim)' },
  unavailable: { label: 'UNAVAILABLE', color: 'var(--red)',    bg: 'var(--red-dim)'    },
};

function StatusBadge({ status }) {
  const meta = STATUS_META[status];
  if (!meta) return null;
  return (
    <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: '0.06em', padding: '2px 6px', borderRadius: 5, background: meta.bg, color: meta.color, whiteSpace: 'nowrap' }}>
      {meta.label}
    </span>
  );
}

function StatusSelect({ playerId, status, onSaved }) {
  const [saving, setSaving] = useState(false);
  const handle = async (e) => {
    const next = e.target.value;
    setSaving(true);
    try {
      await postPlayerStatus(playerId, next);
      onSaved(playerId, next);
    } catch {
      // best-effort UI -- a failed save just leaves the dropdown at its
      // current value, no destructive local state change to undo
    } finally {
      setSaving(false);
    }
  };
  return (
    <select
      value={status || 'available'}
      onChange={handle}
      disabled={saving}
      style={{
        fontSize: 10, fontWeight: 600, padding: '3px 5px', borderRadius: 5,
        background: 'rgba(255,255,255,0.05)', color: 'var(--text-primary)',
        border: '1px solid rgba(255,255,255,0.12)', outline: 'none',
        cursor: saving ? 'default' : 'pointer', flexShrink: 0,
      }}
    >
      <option value="available">Available</option>
      <option value="doubtful">Doubtful</option>
      <option value="unavailable">Unavailable</option>
    </select>
  );
}

function ReadinessCard({ readiness }) {
  const score = readiness?.readiness_score ?? 0;
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 22,
      background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)',
      border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16,
      padding: '20px 24px', marginBottom: 24, boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
    }}>
      <CircularProgress value={score} />
      <div>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
          Squad Readiness
        </div>
        <div style={{ fontSize: 12, color: '#8B949E', marginTop: 5 }}>
          {readiness?.at_risk_players?.length ?? 0} fatigue-flagged · {readiness?.unavailable_players?.length ?? 0} unavailable · {readiness?.doubtful_players?.length ?? 0} doubtful
        </div>
      </div>
    </div>
  );
}

function DepthCard({ pos, players, atRiskIds, statusByPlayerId, isCoach, onStatusSaved }) {
  const [hov, setHov] = useState(false);
  const count = players.length;
  const lowDepth = count < 3;

  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        flex: 1,
        background: hov ? 'linear-gradient(145deg, #202838 0%, #1C2333 100%)' : 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)',
        border: hov ? `1px solid ${pos.colorHex}30` : '1px solid rgba(255,255,255,0.07)',
        borderRadius: 16, overflow: 'hidden',
        transition: 'background 0.2s, border 0.2s, box-shadow 0.2s',
        boxShadow: hov ? `0 8px 32px rgba(0,0,0,0.4), 0 0 20px ${pos.colorHex}0A` : '0 4px 16px rgba(0,0,0,0.25)',
      }}
    >
      <div style={{ height: 3, background: `linear-gradient(90deg, transparent, ${pos.colorHex}88, ${pos.colorHex}, ${pos.colorHex}88, transparent)` }} />
      <div style={{ padding: '18px 20px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', padding: '2px 8px', borderRadius: 4, background: pos.dim, color: pos.color }}>{pos.abbr}</div>
              {lowDepth && (
                <div style={{ fontSize: 9, fontWeight: 600, padding: '2px 7px', borderRadius: 4, background: 'rgba(248,81,73,0.1)', color: 'var(--red)', border: '1px solid rgba(248,81,73,0.2)' }}>⚠ LOW</div>
              )}
            </div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: 28, fontWeight: 700, lineHeight: 1, color: pos.color, letterSpacing: '-0.5px', fontVariantNumeric: 'tabular-nums' }}>{count}</div>
            <div style={{ fontSize: 10.5, color: '#8B949E', marginTop: 2 }}>{pos.plural.toLowerCase()} in squad</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, alignItems: 'flex-end' }}>
            {(() => {
              const atRisk = players.filter(p => atRiskIds.has(p.id)).length;
              const fit    = count - atRisk;
              return (
                <>
                  {fit > 0    && <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: '#8B949E' }}><div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--green)' }}/>{fit} fit</div>}
                  {atRisk > 0 && <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: '#8B949E' }}><div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--yellow)' }}/>{atRisk} at risk</div>}
                </>
              );
            })()}
          </div>
        </div>

        <div style={{ height: 1, background: 'rgba(255,255,255,0.05)', marginBottom: 14 }} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {players.map(p => {
            const isRisk = atRiskIds.has(p.id);
            const status = statusByPlayerId[p.id];
            return (
              <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 22, height: 22, borderRadius: 6, background: 'linear-gradient(135deg, #252D3A, #1A2030)', border: '1px solid rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9.5, fontFamily: 'Space Grotesk', fontWeight: 700, color: '#8B949E', flexShrink: 0 }}>
                  {p.id}
                </div>
                <span style={{ fontSize: 12, fontWeight: 500, color: '#E6EDF3', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</span>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: isRisk ? 'var(--yellow)' : 'var(--green)', flexShrink: 0, boxShadow: `0 0 4px ${isRisk ? 'var(--yellow)' : 'var(--green)'}` }} />
                {isCoach ? (
                  <StatusSelect playerId={p.id} status={status} onSaved={onStatusSaved} />
                ) : (
                  status && status !== 'available' && <StatusBadge status={status} />
                )}
              </div>
            );
          })}
        </div>

        {lowDepth && (
          <div style={{ marginTop: 14, padding: '9px 12px', borderRadius: 8, background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.18)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1L11 10H1L6 1Z" stroke="var(--red)" strokeWidth="1.2" strokeLinejoin="round"/><line x1="6" y1="5" x2="6" y2="7.5" stroke="var(--red)" strokeWidth="1.2" strokeLinecap="round"/><circle cx="6" cy="9" r=".6" fill="var(--red)"/></svg>
            <span style={{ fontSize: 10.5, color: 'var(--red)', fontWeight: 500 }}>Low depth — rotation risk</span>
          </div>
        )}
      </div>
    </div>
  );
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: '#1C2333', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '8px 14px' }}>
      <div style={{ fontFamily: 'Space Grotesk', fontWeight: 700, color: '#E6EDF3', fontSize: 13 }}>{payload[0].value} players</div>
    </div>
  );
};

export default function SquadDepth() {
  const { role } = useAuth();
  const isCoach = role === 'coach';
  const [depth,     setDepth]     = useState(null);
  const [fatigue,   setFatigue]   = useState([]);
  const [readiness, setReadiness] = useState(null);
  const [statusByPlayerId, setStatusByPlayerId] = useState({});
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState(null);

  useEffect(() => {
    Promise.all([getSquadDepth(), getFatigueRisk(), getTeamReadiness(), getPlayerStatuses()])
      .then(([d, f, r, statuses]) => {
        setDepth(d);
        setFatigue(f);
        setReadiness(r);
        setStatusByPlayerId(Object.fromEntries(statuses.map(s => [s.player_id, s.status])));
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleStatusSaved = (playerId, status) => {
    setStatusByPlayerId(prev => ({ ...prev, [playerId]: status }));
    getTeamReadiness().then(setReadiness).catch(() => {});
  };

  const atRiskIds = new Set(fatigue.map(p => p.player_id));

  const chartData = depth ? POSITIONS.map(p => ({
    position: p.plural,
    count:    (depth[p.key] || []).length,
    colorHex: p.colorHex,
  })) : [];
  const chartMax = Math.max(12, ...chartData.map(d => d.count)) + 2;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, padding: '0 20px', minHeight: 60, borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(13,17,23,0.7)', backdropFilter: 'blur(12px)', flexShrink: 0 }}>
        <div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 600 }}>Squad Depth</div>
          <div style={{ fontSize: 11, color: '#8B949E', marginTop: 1 }}>
            {isCoach ? 'Position availability — set player status inline' : 'Position availability across the squad'}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {[['var(--green)', 'FIT'], ['var(--yellow)', 'AT RISK']].map(([c, l]) => (
            <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: c }} />
              <span style={{ fontSize: 10.5, color: '#8B949E', letterSpacing: '0.06em' }}>{l}</span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 20px 48px', minWidth: 0 }}>
        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, height: 200, color: '#8B949E', fontSize: 13 }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: ACC, animation: 'pulse 1.2s ease-in-out infinite' }} />
            Loading squad depth...
          </div>
        )}
        {error   && <div style={{ padding: '16px 20px', background: 'var(--red-dim)', border: '1px solid rgba(248,81,73,0.2)', borderRadius: 12, color: 'var(--red)', fontSize: 13 }}>Failed to load: {error}</div>}

        {!loading && !error && depth && (
          <>
            <ReadinessCard readiness={readiness} />

            <div style={{ display: 'flex', gap: 16, marginBottom: 28, flexWrap: 'wrap' }}>
              {POSITIONS.map(pos => {
                const ids = depth[pos.key] || [];
                return (
                  <div key={pos.key} style={{ flex: 1, background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 14, padding: '18px 22px', position: 'relative', overflow: 'hidden', boxShadow: '0 4px 20px rgba(0,0,0,0.3)' }}>
                    <div style={{ position: 'absolute', top: -24, right: -24, width: 80, height: 80, background: `radial-gradient(circle, ${pos.colorHex}18 0%, transparent 70%)` }} />
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                      <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: '0.1em', padding: '2px 7px', borderRadius: 4, background: pos.dim, color: pos.color }}>{pos.abbr}</div>
                    </div>
                    <div style={{ fontFamily: 'Space Grotesk', fontSize: 38, fontWeight: 700, lineHeight: 1, color: pos.color, letterSpacing: '-1px', fontVariantNumeric: 'tabular-nums' }}>{ids.length}</div>
                    <div style={{ fontSize: 11, color: '#8B949E', marginTop: 6 }}>{pos.plural} available</div>
                  </div>
                );
              })}
            </div>

            <div style={{ background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16, padding: '28px 32px', marginBottom: 24, boxShadow: '0 4px 24px rgba(0,0,0,0.3)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
                <div style={{ width: 3, height: 18, background: ACC, borderRadius: 2 }} />
                <div style={{ fontFamily: 'Space Grotesk', fontSize: 15, fontWeight: 600 }}>Availability by Position</div>
                <div style={{ fontSize: 10.5, color: '#8B949E' }}>
                  {depth.total_players} players appeared in at least one match
                </div>
              </div>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 60, top: 0, bottom: 0 }} barCategoryGap={16} defaultIndex={undefined}>
                  <XAxis
                    type="number" domain={[0, chartMax]}
                    tick={{ fill: '#6E7681', fontSize: 10 }}
                    axisLine={false} tickLine={false}
                  />
                  <YAxis
                    type="category" dataKey="position"
                    tick={{ fill: '#8B949E', fontSize: 12, fontWeight: 500 }}
                    axisLine={false} tickLine={false} width={90}
                  />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} trigger="hover" />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={22}>
                    {chartData.map((entry, idx) => (
                      <Cell key={idx} fill={entry.colorHex} fillOpacity={0.85} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={{ width: 3, height: 18, background: ACC, borderRadius: 2 }} />
              <div style={{ fontFamily: 'Space Grotesk', fontSize: 15, fontWeight: 600 }}>Position Breakdown</div>
            </div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              {POSITIONS.map(pos => (
                <DepthCard
                  key={pos.key}
                  pos={pos}
                  players={depth[pos.key] || []}
                  atRiskIds={atRiskIds}
                  statusByPlayerId={statusByPlayerId}
                  isCoach={isCoach}
                  onStatusSaved={handleStatusSaved}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Lint**

Run: `cd frontend && npm run lint`
Expected: no new errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/SquadDepth.jsx
git commit -m "Make Squad Depth interactive: readiness card + inline coach status editor"
```

---

## Task 10: Team filter/column on Players + fix Dashboard's Top Performers scope

**Files:**
- Modify: `frontend/src/pages/Players.jsx`
- Modify: `frontend/src/pages/Dashboard.jsx`

- [ ] **Step 1: Fix Dashboard's "Top Performers" scope**

`Dashboard.jsx` computes `topPerformers` from `getPlayerPerformance()`, which is now global (Task 6). Without a fix, opponents would appear in the "Season Snapshot" card that's specifically about Barcelona's season. In `frontend/src/pages/Dashboard.jsx`, find:

```js
  const topPerformers = [...performance]
    .filter(p => (p.xg || 0) > 0)
    .sort((a, b) => (b.xg || 0) - (a.xg || 0))
    .slice(0, 3);
```

Replace with:

```js
  const topPerformers = [...performance]
    .filter(p => p.team_name === teamInfo?.team_name && (p.xg || 0) > 0)
    .sort((a, b) => (b.xg || 0) - (a.xg || 0))
    .slice(0, 3);
```

- [ ] **Step 2: Simplify Players.jsx's position resolution (remove Barcelona-scoped dependency)**

In `frontend/src/pages/Players.jsx`, remove the `getSquadDepth` import and the `depth`/`positionByPlayerId` state+memo (they existed only to resolve position, which the performance response now provides directly via `position_bucket`).

Remove this import:
```js
import { getPlayerPerformance, getFatigueRisk, getSquadDepth, getTeamInfo } from '../services/api';
```
Replace with:
```js
import { getPlayerPerformance, getFatigueRisk, getTeamInfo } from '../services/api';
```

Remove the `depth` state (`const [depth, setDepth] = useState(null);`) and update the `useEffect`:

```js
  useEffect(() => {
    Promise.all([getPlayerPerformance(), getFatigueRisk(), getTeamInfo()])
      .then(([perf, risk, t]) => { setPerformance(perf); setFatigueRisk(risk); setTeamInfo(t); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);
```

Remove the entire `positionByPlayerId` memo block (the one built from `depth`).

Update the `players` memo:

```js
  const players = useMemo(() => performance.map(p => ({
    ...p,
    pos:  POS_ABBREV[p.position_bucket] || '???',
    status: atRiskIds.has(p.player_id) ? 'AT RISK' : 'FIT',
  })), [performance, atRiskIds]);
```

- [ ] **Step 3: Add the team filter state and options**

Add alongside the existing `filterPos` state:

```js
  const [filterTeam, setFilterTeam] = useState('ALL');
```

Add a memo for the dropdown options (after the `players` memo):

```js
  const teamOptions = useMemo(() => {
    const names = new Set(players.map(p => p.team_name).filter(Boolean));
    return ['ALL', ...Array.from(names).sort()];
  }, [players]);
```

- [ ] **Step 4: Update the `filtered` memo to filter by position bucket directly and by team**

Replace:

```js
  const filtered = useMemo(() => {
    let result = filterPos === 'ALL'
      ? players
      : players.filter(p => positionByPlayerId[p.player_id] === POS_MAP[filterPos]);

    const query = search.trim().toLowerCase();
    if (query) result = result.filter(p => p.name?.toLowerCase().includes(query));

    return result;
  }, [players, filterPos, search, positionByPlayerId]);
```

With:

```js
  const filtered = useMemo(() => {
    let result = filterPos === 'ALL'
      ? players
      : players.filter(p => p.position_bucket === POS_MAP[filterPos]);

    if (filterTeam !== 'ALL') result = result.filter(p => p.team_name === filterTeam);

    const query = search.trim().toLowerCase();
    if (query) result = result.filter(p => p.name?.toLowerCase().includes(query));

    return result;
  }, [players, filterPos, filterTeam, search]);
```

- [ ] **Step 5: Add the "Team" column**

In the `COLUMNS` array, add a new entry right after `pos`:

```js
const COLUMNS = [
  { key: 'name',                   label: 'Player',    w: 180, center: false },
  { key: 'pos',                    label: 'Pos',       w: 60,  center: true  },
  { key: 'team_name',              label: 'Team',      w: 130, center: false },
  { key: 'matches_played',         label: 'MP',        w: 50,  center: true  },
  ...
```

(Leave the rest of the array unchanged.)

In `TableRow`, add the team cell right after the position badge cell (which is `<div style={{ width: 60, ... }}><PosBadge pos={player.pos} /></div>`):

```jsx
      <div style={{ width: 130, flexShrink: 0, fontSize: 11.5, color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', paddingRight: 8 }}>
        {player.team_name}
      </div>
```

Since `team_name` is a string column, it must be excluded from the numeric `handleSort`/`TABLE_MIN_W` treatment the same way `pos` already is — in the header rendering, the `onClick`/cursor guard currently reads `col.key !== 'status' && col.key !== 'pos'`; update both occurrences to also exclude `'team_name'`:

```jsx
                          onClick={() => col.key !== 'status' && col.key !== 'pos' && col.key !== 'team_name' && handleSort(col.key)}
```
and
```jsx
                          cursor: col.key !== 'status' && col.key !== 'pos' && col.key !== 'team_name' ? 'pointer' : 'default',
```
and the `SortIcon` render guard:
```jsx
                          {col.key !== 'status' && col.key !== 'pos' && col.key !== 'team_name' && (
                            <SortIcon dir={sortKey === col.key ? sortDir : null} />
                          )}
```

- [ ] **Step 6: Add the team filter dropdown next to the position chips**

In the header controls block, right after the closing of the position-chip `.map()` (before the closing `</div>` of that flex container), add:

```jsx
          <select
            value={filterTeam}
            onChange={(e) => setFilterTeam(e.target.value)}
            style={{
              padding: '6px 10px', fontSize: 11, fontWeight: 600,
              background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)',
              borderRadius: 7, color: 'var(--text-primary)', outline: 'none', cursor: 'pointer',
            }}
          >
            {teamOptions.map(t => <option key={t} value={t}>{t === 'ALL' ? 'All Teams' : t}</option>)}
          </select>
```

- [ ] **Step 7: Lint**

Run: `cd frontend && npm run lint`
Expected: no new errors (in particular, no `positionByPlayerId`/`depth`/`getSquadDepth` "unused" or "undefined" errors — confirm every reference was removed).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/Players.jsx frontend/src/pages/Dashboard.jsx
git commit -m "Add team filter/column to Players page; keep Dashboard Top Performers Barcelona-scoped"
```

---

## Task 11: Apply the `player_status` migration to `pitchiq-v2-dev`

This is a **manual step** — there is no migration runner and no way to execute raw DDL through the `supabase-py` client (PostgREST only handles table operations, not arbitrary SQL), matching how migrations 0001-0003 were already handled in this project.

- [ ] **Step 1: Apply the migration**

Open the Supabase SQL editor for the `pitchiq-v2-dev` project and run the contents of `backend/app/data/migrations/0004_add_player_status.sql` (from Task 1) once.

- [ ] **Step 2: Confirm it applied**

Run this from `backend/` (uses the same `SUPABASE_URL`/`SUPABASE_KEY` already in `.env`):

```bash
cd backend && python -c "
from dotenv import load_dotenv
load_dotenv()
import os
from supabase import create_client
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
print(c.table('player_status').select('*').limit(1).execute().data)
"
```

Expected: `[]` (empty list, not an error) — proves the table exists and is queryable.

**If you (the user) would rather run this yourself:** say so and skip straight to Task 12 — Availability Management will 500 on POST until this is applied, but everything else in the plan is unaffected and Task 13's Scout/opponent-visibility verification can proceed without it.

---

## Task 12: Full backend test suite + frontend build check

- [ ] **Step 1: Run the full backend suite**

Run: `cd backend && python -m pytest -v`
Expected: all pass, including the two real-Supabase tests (`test_role_gating.py`, `test_players_performance_scope.py`) since credentials are configured in this environment.

- [ ] **Step 2: Run the frontend build**

Run: `cd frontend && npm run build`
Expected: builds clean, no errors.

---

## Task 13: Live verification (all three features, correct role each time)

Requires Task 11 done (or explicitly skipped per user instruction) for the Availability Management part.

- [ ] **Step 1: Start the backend locally**

Run: `cd backend && python -m uvicorn app.main:app --reload --port 8000`

- [ ] **Step 2: Start the frontend locally, pointed at the local backend**

Run: `cd frontend && VITE_API_BASE=http://localhost:8000 npm run dev`

- [ ] **Step 3: Scout — write a scouting note**

Log in via the frontend's "Demo: Scout" button (`scout@example.com` / `Scout123!`, per `DEMO_ACCOUNTS.md`). Go to Players, open any player (including one from a non-Barcelona team, e.g. filter by team first), write a note with a rating, save it, and confirm it appears in the list immediately without a page reload.

- [ ] **Step 4: Coach — change a player's status and see Squad Readiness move**

Log out, log in as "Demo: Coach" (`coach@example.com` / `Coach123!`). Go to Squad Depth, note the current Squad Readiness score, set an available player to "Unavailable" via the inline dropdown, and confirm the readiness score drops and the "X unavailable" count updates without a manual refresh. Also confirm the Scouting Notes section does **not** appear on the player modal for this role.

- [ ] **Step 5: Confirm opponent visibility + filtering**

As any role, go to Players, confirm the table includes players from teams other than Barcelona (use the new Team dropdown to filter to a non-Barcelona team and confirm rows appear), and confirm the Team column renders correctly for both Barcelona and opponent rows.

- [ ] **Step 6: Confirm the Coach POST 403s stay real, not just unit-tested**

While still logged in as Coach, attempt (via browser devtools console, `fetch`) a `POST /api/scouting/notes` with the Coach's bearer token — confirm a real 403 comes back from the running backend, not just the pytest fake.

If any of these fail, stop and report exactly what broke before touching anything else — do not silently patch around a live failure without understanding it first (see `superpowers:systematic-debugging` if the cause isn't obvious).

---

## Task 14: Commit and push

- [ ] **Step 1: Final status check**

Run: `git status` and `git log --oneline -15` to confirm all task commits from this plan are present and nothing unrelated got swept in.

- [ ] **Step 2: Push**

```bash
git push origin v2-dev
```

(Confirm with the user before pushing if anything about branch state looks unexpected — e.g. origin/v2-dev has diverged.)
