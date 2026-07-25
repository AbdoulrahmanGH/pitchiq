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
            from gotrue.errors import AuthApiError
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


class FakeClient:
    def __init__(self, user=None, raise_on_get_user=False, roles_by_user_id=None):
        self.auth = FakeAuth(user=user, raise_on_get_user=raise_on_get_user)
        self._roles_by_user_id = roles_by_user_id or {}

    def table(self, name):
        assert name == "user_roles"
        return FakeRolesTable(self._roles_by_user_id)
