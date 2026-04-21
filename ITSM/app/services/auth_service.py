from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Tuple
import logging

from app.models.user import User
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.schemas.auth import UserCreate, LoginRequest

logger = logging.getLogger(__name__)


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: Session):
        self.db = db

    def register_user(self, user_create: UserCreate) -> User:
        """Register a new user."""

        # Check if user already exists
        existing_user = self.db.query(User).filter(
            (User.username == user_create.username) |
            (User.email == user_create.email)
        ).first()

        if existing_user:
            raise ValueError("Username or email already exists")

        # Hash password and create user
        hashed_password = hash_password(user_create.password)

        db_user = User(
            username=user_create.username,
            email=user_create.email,
            full_name=user_create.full_name,
            hashed_password=hashed_password,
            phone=user_create.phone,
            mobile=user_create.mobile,
            language=user_create.language,
            timezone=user_create.timezone,
            entity_id=user_create.entity_id,
            is_active=True,
        )

        self.db.add(db_user)
        self.db.flush()

        logger.info(f"User {user_create.username} registered successfully")
        return db_user

    def authenticate_user(
        self,
        login_request: LoginRequest,
    ) -> Optional[User]:
        """Authenticate user by username and password."""

        user = self.db.query(User).filter(
            User.username == login_request.username
        ).first()

        if not user:
            return None

        if not verify_password(login_request.password, user.hashed_password):
            return None

        if not user.is_active:
            raise ValueError("User account is inactive")

        # Update last login
        user.last_login = datetime.utcnow()
        self.db.flush()

        logger.info(f"User {user.username} logged in successfully")
        return user

    def create_tokens(self, user: User) -> Tuple[str, str, int]:
        """Create access and refresh tokens for a user."""

        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id}
        )

        refresh_token = create_refresh_token(
            data={"sub": user.username, "user_id": user.id}
        )

        from app.config import settings
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return access_token, refresh_token, expires_in

    def get_user_by_token(self, token: str) -> Optional[User]:
        """Get user from token payload."""

        payload = decode_token(token)
        if not payload:
            return None

        user_id = payload.get("user_id")
        if not user_id:
            return None

        user = self.db.query(User).filter(User.id == user_id).first()
        return user

    def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change user password."""

        if not verify_password(current_password, user.hashed_password):
            raise ValueError("Current password is incorrect")

        user.hashed_password = hash_password(new_password)
        self.db.flush()

        logger.info(f"Password changed for user {user.username}")
        return True
