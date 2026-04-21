from passlib.context import CryptContext
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
import logging
import hashlib

from app.config import settings

logger = logging.getLogger(__name__)

# Simple and reliable password hashing for development
def hash_password(password: str) -> str:
    """Hash a password using PBKDF2 (compatible with passlib)."""
    try:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
        return pwd_context.hash(password)
    except Exception as e:
        logger.warning(f"PBKDF2 hashing failed: {e}, using sha256")
        # Fallback for dev/testing only
        return f"sha256${hashlib.sha256(password.encode()).hexdigest()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    try:
        # Try pbkdf2 first
        pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        # Fallback for sha256 hashes (dev/testing only)
        if hashed_password.startswith("sha256$"):
            stored_hash = hashed_password.split("$")[1]
            computed_hash = hashlib.sha256(plain_password.encode()).hexdigest()
            return stored_hash == computed_hash
        logger.error(f"Error verifying password: {e}")
        return False


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError as e:
        logger.warning(f"Invalid token: {str(e)}")
        return None
