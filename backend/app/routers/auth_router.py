from fastapi import APIRouter, Depends

from app.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/whoami")
def whoami(user: AuthenticatedUser = Depends(get_current_user)):
    return {"id": user.id, "role": user.role}
