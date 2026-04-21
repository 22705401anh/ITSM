from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.db import get_db
from app.schemas.auth import (
    LoginRequest,
    UserCreate,
    UserResponse,
    TokenResponse,
)
from app.services.auth_service import AuthService
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    login_request: LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate user and return tokens."""

    try:
        auth_service = AuthService(db)
        user = auth_service.authenticate_user(login_request)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        access_token, refresh_token, expires_in = auth_service.create_tokens(user)

        db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed",
        )


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    user_create: UserCreate,
    db: Session = Depends(get_db),
):
    """Register a new user."""

    try:
        auth_service = AuthService(db)
        user = auth_service.register_user(user_create)
        db.commit()

        return UserResponse.model_validate(user)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post("/logout")
async def logout():
    """Logout current user."""
    # Session cleanup would happen on client side
    return {"message": "Logged out successfully"}
