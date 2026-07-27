"""Shared fake Supabase client double for auth tests. No network calls."""


class FakeCredentials:
    def __init__(self, token):
        self.credentials = token


class FakeUser:
    def __init__(self, id, email):
        self.id = id
        self.email = email


class FakeUserResponse:
    def __init__(self, user):
        self.user = user


class FakeAuth:
    def __init__(self, user=None, raise_on_get_user=False):
        self._user = user
        self._raise = raise_on_get_user

    def get_user(self, jwt):
        if self._raise:
            from supabase_auth.errors import AuthApiError
            raise AuthApiError("invalid JWT", 401, "invalid_token")
        return FakeUserResponse(self._user)


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeRolesTable:
    def __init__(self, roles_by_user_id):
        self._roles = roles_by_user_id
        self._filtered = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        assert column == "user_id"
        role = self._roles.get(value)
        self._filtered = [{"role": role}] if role else []
        return self

    def execute(self):
        return FakeResult(self._filtered)


class FakeAnalyticsCacheTable:
    """rows_by_query_name: {query_name: [rows...]}, each row shaped like a
    real analytics_cache row ({"computed_at": ..., "payload": ...}), already
    in newest-first order -- matching what a real .order(desc=True) would
    return, since this fake doesn't do any actual sorting itself.
    """
    def __init__(self, rows_by_query_name):
        self._rows_by_query_name = rows_by_query_name
        self._query_name = None
        self._limit = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        assert column == "query_name"
        self._query_name = value
        return self

    def order(self, column, desc=False):
        assert column == "computed_at"
        assert desc is True
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        rows = self._rows_by_query_name.get(self._query_name, [])
        return FakeResult(rows[:self._limit] if self._limit is not None else rows)


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
        assert column in ("player_id", "author_id")
        self._result = [r for r in self._result if r[column] == value]
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


class FakeSimpleSelectTable:
    """Generic read-only fake for tables only ever queried as
    select(...).in_(column, values).execute() -- used for the players/
    player_match_stats/teams lookups that enrich scouting notes with a
    player name and team. rows: the full table contents this fake serves
    from; in_() filters down to matching values.
    """
    def __init__(self, rows=None):
        self._rows = list(rows or [])
        self._result = None

    def select(self, *_args, **_kwargs):
        self._result = list(self._rows)
        return self

    def in_(self, column, values):
        values = set(values)
        self._result = [r for r in self._result if r.get(column) in values]
        return self

    def eq(self, column, value):
        self._result = [r for r in self._result if r.get(column) == value]
        return self

    def execute(self):
        return FakeResult(self._result if self._result is not None else [])


class FakeClient:
    def __init__(self, user=None, raise_on_get_user=False, roles_by_user_id=None,
                 analytics_cache_rows=None, scouting_notes=None, player_statuses=None,
                 players_rows=None, player_match_stats_rows=None, teams_rows=None):
        self.auth = FakeAuth(user=user, raise_on_get_user=raise_on_get_user)
        self._roles_by_user_id = roles_by_user_id or {}
        self._analytics_cache_rows = analytics_cache_rows or {}
        self._scouting_notes = scouting_notes
        self._player_statuses = player_statuses
        self._players_rows = players_rows
        self._player_match_stats_rows = player_match_stats_rows
        self._teams_rows = teams_rows

    def table(self, name):
        if name == "user_roles":
            return FakeRolesTable(self._roles_by_user_id)
        if name == "analytics_cache":
            return FakeAnalyticsCacheTable(self._analytics_cache_rows)
        if name == "scouting_notes":
            return FakeScoutingNotesTable(self._scouting_notes)
        if name == "player_status":
            return FakePlayerStatusTable(self._player_statuses)
        if name == "players":
            return FakeSimpleSelectTable(self._players_rows)
        if name == "player_match_stats":
            return FakeSimpleSelectTable(self._player_match_stats_rows)
        if name == "teams":
            return FakeSimpleSelectTable(self._teams_rows)
        raise AssertionError(f"FakeClient.table() called with unexpected table: {name}")
