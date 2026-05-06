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
        """Authenticate user by username and password.
        Supports both local and LDAP (Active Directory) authentication.
        """

        user = self.db.query(User).filter(
            User.username == login_request.username
        ).first()

        if not user:
            return None

        if not user.is_active:
            raise ValueError("User account is inactive")

        # Check if this is an AD-managed user
        if user.hashed_password == "AD_MANAGED_USER":
            # Authenticate against LDAP
            if not self._ldap_authenticate(login_request.username, login_request.password):
                return None
        else:
            # Local password authentication
            if not verify_password(login_request.password, user.hashed_password):
                return None

        # Update last login
        user.last_login = datetime.utcnow()
        self.db.flush()

        logger.info(f"User {user.username} logged in successfully")
        return user

    def _ldap_authenticate(self, username: str, password: str) -> bool:
        """Authenticate a user against Active Directory via LDAP bind.
        Tries NTLM (DOMAIN\\user) first, falls back to simple bind with UPN.
        """
        from ldap3 import Server, Connection, NTLM, SIMPLE
        from app.utils.ldap_config import get_ldap_config

        ldap_cfg = get_ldap_config(self.db)

        server = Server(
            ldap_cfg['server'], 
            port=ldap_cfg['port'], 
            connect_timeout=5
        )

        # Extract domain info from LDAP_BASE_DN
        domain_parts = [p.strip().replace("DC=", "") for p in ldap_cfg['base_dn'].split(",") if p.strip().startswith("DC=")]
        domain_short = domain_parts[0].upper() if domain_parts else "MA"
        domain_fqdn = ".".join(domain_parts)  # e.g. ma.kostal.int

        # Attempt 1: NTLM with DOMAIN\username
        try:
            bind_user = f"{domain_short}\\{username}"
            logger.info(f"LDAP auth attempt (NTLM): {bind_user} -> {ldap_cfg['server']}")
            user_conn = Connection(
                server,
                user=bind_user,
                password=password,
                authentication=NTLM,
                auto_bind=True,
                receive_timeout=5
            )
            user_conn.unbind()
            logger.info(f"LDAP authentication successful for {username} (NTLM)")
            return True
        except Exception as e:
            logger.warning(f"LDAP NTLM bind failed for {username}: {str(e)}")

        # Attempt 2: Simple bind with UPN (user@domain.fqdn)
        try:
            bind_user = f"{username}@{domain_fqdn}"
            logger.info(f"LDAP auth attempt (UPN): {bind_user} -> {ldap_cfg['server']}")
            user_conn = Connection(
                server,
                user=bind_user,
                password=password,
                authentication=SIMPLE,
                auto_bind=True,
                receive_timeout=5
            )
            user_conn.unbind()
            logger.info(f"LDAP authentication successful for {username} (UPN)")
            return True
        except Exception as e:
            logger.warning(f"LDAP UPN bind failed for {username}: {str(e)}")

        logger.error(f"All LDAP authentication methods failed for {username}")
        return False

    def authenticate_sso_user(self, email: str, name: str = None) -> User:
        """
        Authenticate a user via SSO.
        Finds the user by email, or creates a new AD_MANAGED_USER stub.
        """
        user = self.db.query(User).filter(User.email == email).first()

        if user:
            if not user.is_active:
                raise ValueError("User account is inactive")
            user.last_login = datetime.utcnow()
            self.db.flush()
            logger.info(f"User {user.username} logged in successfully via SSO")
            return user

        # Auto-provision SSO user
        username = email.split('@')[0]
        
        # Check if username already exists
        existing_username = self.db.query(User).filter(User.username == username).first()
        if existing_username:
            # Append random string to username if conflict
            import random, string
            suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
            username = f"{username}_{suffix}"

        db_user = User(
            username=username,
            email=email,
            full_name=name or username,
            hashed_password="AD_MANAGED_USER", # Managed externally
            is_active=True,
            last_login=datetime.utcnow()
        )

        self.db.add(db_user)
        self.db.flush()

        logger.info(f"New user {username} provisioned automatically via SSO")
        return db_user

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
