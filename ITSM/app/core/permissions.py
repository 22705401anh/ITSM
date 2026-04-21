from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.models.user import User, Profile, Permission

logger = logging.getLogger(__name__)


def check_user_permission(
    user: User,
    module: str,
    action: str,
    db: Session,
) -> bool:
    """Check if a user has a specific permission."""

    # Super admin has all permissions
    if _is_super_admin(user, db):
        return True

    # Check if user's profiles have the required permission
    for profile in user.profiles:
        has_permission = db.query(Permission).filter(
            Permission.profile_id == profile.id,
            Permission.module == module,
            Permission.action == action,
        ).first()

        if has_permission:
            return True

    return False


def require_permission(module: str, action: str):
    """Dependency for checking permissions."""
    def _require_permission(user: User, db: Session) -> User:
        if not check_user_permission(user, module, action, db):
            logger.warning(
                f"User {user.id} ({user.username}) denied access to {module}.{action}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {module}.{action}",
            )
        return user

    return _require_permission


def check_entity_scope(user: User, entity_id: int, db: Session) -> bool:
    """Check if user can access a specific entity."""

    # Super admin can access all entities
    if _is_super_admin(user, db):
        return True

    # User can access their own entity
    if user.entity_id == entity_id:
        return True

    # TODO: Check recursive entity visibility
    # This requires checking parent entities

    return False


def _is_super_admin(user: User, db: Session) -> bool:
    """Check if user has Super Admin profile."""
    admin_profile = db.query(Profile).filter(
        Profile.profile_type == "Super Admin"
    ).first()

    if not admin_profile:
        return False

    return admin_profile in user.profiles


def get_accessible_entities(user: User, db: Session) -> List[int]:
    """Get list of entity IDs that user can access."""

    # Super admin can access all
    if _is_super_admin(user, db):
        from app.models.user import Entity
        all_entities = db.query(Entity.id).all()
        return [e[0] for e in all_entities]

    # User can access their own entity
    if user.entity_id:
        return [user.entity_id]

    return []
