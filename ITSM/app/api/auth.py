from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session
import logging
import spnego
import base64
from datetime import datetime
from authlib.integrations.starlette_client import OAuth

from app.db import get_db
from app.schemas.auth import (
    LoginRequest,
    UserCreate,
    UserUpdate,
    UserResponse,
    TokenResponse,
)
from app.services.auth_service import AuthService
from app.models.user import User
from app.config import settings

import uuid

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

# In-memory store for SSPI contexts (safe for single-worker Uvicorn)
sso_contexts = {}

@router.get("/sso/windows")
async def sso_windows(request: Request, db: Session = Depends(get_db)):
    """Handle Seamless Windows Authentication (Negotiate/NTLM)."""
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Negotiate "):
        # Initialize a new SSO session
        session_id = str(uuid.uuid4())
        request.session['sso_session_id'] = session_id
        if session_id in sso_contexts:
            del sso_contexts[session_id]
            
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": "Negotiate"}
        )
    
    session_id = request.session.get('sso_session_id')
    if not session_id:
        return Response(status_code=401, headers={"WWW-Authenticate": "Negotiate"})

    try:
        in_token_b64 = auth_header.split(" ", 1)[1]
        in_token = base64.b64decode(in_token_b64)
        
        if session_id not in sso_contexts:
            sso_contexts[session_id] = spnego.server(hostname="localhost")
            
        c = sso_contexts[session_id]
        
        out_token = c.step(in_token)
        
        if not c.complete:
            # Send challenge back to client
            headers = {}
            if out_token:
                headers["WWW-Authenticate"] = f"Negotiate {base64.b64encode(out_token).decode()}"
            return Response(status_code=401, headers=headers)
            
        # Success! Extract the username and cleanup context
        if session_id in sso_contexts:
            del sso_contexts[session_id]
            
        client_principal = c.client_principal
        
        if '\\' in client_principal:
            username = client_principal.split('\\')[1]
        elif '@' in client_principal:
            username = client_principal.split('@')[0]
        else:
            username = client_principal
            
        auth_service = AuthService(db)
        user = db.query(User).filter(User.username == username).first()
        
        if not user or not user.is_active:
            # User must be granted access via Platform Access Management
            return RedirectResponse(url="/login?error=sso_unauthorized")
            
        # Create tokens and log in
        access_token, refresh_token, expires_in = auth_service.create_tokens(user)
        user.last_login = datetime.utcnow()
        db.commit()
        
        return RedirectResponse(url=f"/?access_token={access_token}&refresh_token={refresh_token}")
        
    except Exception as e:
        logger.error(f"Windows SSO failed: {str(e)}", exc_info=True)
        return RedirectResponse(url="/login?error=sso_failed")

oauth = OAuth()
if settings.SSO_ENABLED and settings.SSO_CLIENT_ID:
    oauth.register(
        name='sso',
        client_id=settings.SSO_CLIENT_ID,
        client_secret=settings.SSO_CLIENT_SECRET,
        server_metadata_url=f"{settings.SSO_AUTHORITY.format(tenant=settings.SSO_TENANT_ID)}/.well-known/openid-configuration",
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

@router.get("/sso/login")
async def sso_login(request: Request):
    """Redirect to SSO login."""
    if not settings.SSO_ENABLED or not settings.SSO_CLIENT_ID:
        raise HTTPException(status_code=400, detail="SSO is not configured")
    redirect_uri = settings.SSO_REDIRECT_URI
    return await oauth.sso.authorize_redirect(request, redirect_uri)

@router.get("/sso/callback")
async def sso_callback(request: Request, db: Session = Depends(get_db)):
    """Handle SSO callback."""
    try:
        token = await oauth.sso.authorize_access_token(request)
        user_info = token.get('userinfo')
        if not user_info:
            user_info = await oauth.sso.parse_id_token(request, token)
        
        email = user_info.get('email') or user_info.get('preferred_username')
        name = user_info.get('name')

        if not email:
            raise ValueError("Email not provided by SSO provider")

        auth_service = AuthService(db)
        user = auth_service.authenticate_sso_user(email, name)

        access_token, refresh_token, expires_in = auth_service.create_tokens(user)
        db.commit()

        # Redirect back to frontend with tokens as query params
        # In production, using a secure cookie or postMessage is safer, but this works for SPA redirect
        return RedirectResponse(url=f"/?access_token={access_token}&refresh_token={refresh_token}")

    except Exception as e:
        logger.error(f"SSO Callback failed: {e}")
        return RedirectResponse(url="/login?error=sso_failed")


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
                detail="Incorrect username or password. Please try again.",
            )

        access_token, refresh_token, expires_in = auth_service.create_tokens(user)

        db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed",
        )


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    user_create: UserCreate,
    db: Session = Depends(get_db),
):
    """Public registration is disabled. Only admins can create users."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Public registration is disabled. Please contact your administrator.",
    )


@router.post("/logout")
async def logout():
    """Logout current user."""
    # Session cleanup would happen on client side
    return {"message": "Logged out successfully"}

from app.dependencies import get_current_user

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user."""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current authenticated user."""
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)
    
    db.commit()
    db.refresh(current_user)
    return current_user

