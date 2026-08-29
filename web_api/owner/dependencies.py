"""Authorization dependencies for platform OWNER routes."""

from fastapi import Depends, HTTPException, status

from app_database.models import User
from authentication.services import get_current_user


async def owner_required(current_user: User = Depends(get_current_user)) -> User:
    """Require the persisted platform OWNER capability."""
    if not bool(current_user.is_platform_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform OWNER erişimi gerekli.",
        )
    return current_user
