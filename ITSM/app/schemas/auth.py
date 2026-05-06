from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    """Request model for user login."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    """Response model for token generation."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserBase(BaseModel):
    """Base user schema."""
    username: str = Field(..., min_length=3, max_length=100)
    email: str
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = None
    mobile: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None
    profile_image: Optional[str] = None
    language: str = "en"
    timezone: str = "UTC"


class UserCreate(UserBase):
    """Schema for creating a user."""
    password: str = Field(..., min_length=8)
    entity_id: Optional[int] = None


class UserUpdate(BaseModel):
    """Schema for updating user."""
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    profile_image: Optional[str] = None


class UserResponse(UserBase):
    """Schema for user response."""
    id: int
    entity_id: Optional[int]
    location_id: Optional[int]
    is_active: bool
    role: str
    assigned_pages: Optional[str]
    last_login: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
