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


class FakeClient:
    def __init__(self, user=None, raise_on_get_user=False, roles_by_user_id=None,
                 analytics_cache_rows=None):
        self.auth = FakeAuth(user=user, raise_on_get_user=raise_on_get_user)
        self._roles_by_user_id = roles_by_user_id or {}
        self._analytics_cache_rows = analytics_cache_rows or {}

    def table(self, name):
        if name == "user_roles":
            return FakeRolesTable(self._roles_by_user_id)
        if name == "analytics_cache":
            return FakeAnalyticsCacheTable(self._analytics_cache_rows)
        raise AssertionError(f"FakeClient.table() called with unexpected table: {name}")
