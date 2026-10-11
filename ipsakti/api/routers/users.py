"""Identity routes."""

from __future__ import annotations

from fastapi import APIRouter

from ipsakti.api.deps import CurrentPrincipal, DbSession
from ipsakti.auth.schemas import UserResponse
from ipsakti.core.errors import AuthenticationError
from ipsakti.db.models.identity import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def read_current_user(principal: CurrentPrincipal, db: DbSession) -> UserResponse:
    """Return the authenticated user's own profile."""
    user = db.get(User, principal.user_id)
    if user is None:
        # The principal was just resolved from this id; a miss means a race with a
        # concurrent delete. Treat as unauthenticated rather than 500.
        raise AuthenticationError("invalid credentials")
    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        status=user.status,
        roles=[role.name.value for role in user.roles],
    )
