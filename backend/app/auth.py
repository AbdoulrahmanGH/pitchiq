"""Auth + role-checking dependency for FastAPI routes.

Token validation is delegated to Supabase itself (auth.get_user(token),
GoTrue's /auth/v1/user endpoint) rather than verifying the JWT signature
locally -- this avoids re-implementing JWKS/key-rotation handling and stays
correct regardless of which signing scheme the project uses.

Two dependency shapes, as needed:
- Depends(get_current_user)     -- any authenticated user
- Depends(require_role("coach")) -- must be exactly this role
"""

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import get_db

security = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    id: str
    email: str
    role: Optional[str]


def _require_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    # A dependency of its own, not a check inside get_current_user's body:
    # FastAPI resolves sibling Depends(...) params (like client=Depends(get_db)
    # below) independently of each other, so a check written inside the
    # function body would run too late to stop get_db() from being called
    # first. Raising here, before get_db is ever reached, means a request
    # with no token never touches Supabase at all.
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    return credentials.credentials


def get_current_user(
    token: str = Depends(_require_bearer_token),
    client=Depends(get_db),
) -> AuthenticatedUser:
    try:
        user_response = client.auth.get_user(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = user_response.user if user_response else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    role_rows = client.table("user_roles").select("role").eq("user_id", user.id).execute().data
    role = role_rows[0]["role"] if role_rows else None

    return AuthenticatedUser(id=user.id, email=user.email, role=role)


def require_role(required_role: str):
    def _dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {required_role}",
            )
        return user
    return _dependency
