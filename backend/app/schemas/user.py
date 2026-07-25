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
