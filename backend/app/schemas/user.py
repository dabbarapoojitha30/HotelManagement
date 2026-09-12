from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class UserRegister(BaseModel):
    """Schema for user registration."""
    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    role: str = Field(..., description="manager or owner")
    password: str = Field(..., min_length=6, max_length=128, description="Minimum 6 characters")


class UserLogin(BaseModel):
    """Schema for user login."""
    name: str = Field(..., min_length=1)
    role: str = Field(..., description="manager or owner")
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    """Schema for user response (no password)."""
    id: str
    name: str
    role: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    """Schema for updating own profile (name, password)."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="New display name")
    current_password: str = Field(..., min_length=1, description="Current password for verification")
    new_password: Optional[str] = Field(None, min_length=6, max_length=128, description="New password (optional)")


class UserProfileResponse(BaseModel):
    """Schema for response after updating own profile."""
    id: str
    name: str
    role: str
    access_token: str
    refresh_token: str
    message: str
