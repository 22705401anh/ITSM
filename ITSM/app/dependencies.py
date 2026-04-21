from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.models.user import User


async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(None),  # Will be updated with actual auth logic
) -> User:
    """Get the current authenticated user."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # This will be implemented properly in the security module
    user = db.query(User).filter(User.id == 1).first()  # Placeholder
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current user and verify they have admin profile."""
    # Check if user has admin profile
    # This will be implemented properly after profile integration
    return current_user


def check_permission(module: str, action: str):
    """Factory for permission checking dependency."""
    async def _check_permission(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        # Will be implemented in permissions.py
        return current_user

    return _check_permission
