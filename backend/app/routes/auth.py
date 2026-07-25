"""
Authentication routes — login, register, refresh, profile.
Includes /login-staff for username-based authentication from the frontend.
"""
from fastapi import APIRouter, Depends, status
from app.schemas.user import UserRegister, UserResponse, UserLogin
from app.schemas.auth import Token, RefreshTokenRequest
from app.auth.dependencies import get_current_user
from app.services import auth_service
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    """
    Register a new user (manager or owner).
    """
    user = await auth_service.register_user(
        name=user_data.name,
        role=user_data.role,
        password=user_data.password,
    )
    return user


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """Authenticate with name, role and password, receive JWT tokens and redirect page."""
    result = await auth_service.authenticate_user(
        name=credentials.name,
        role=credentials.role,
        password=credentials.password,
    )
    return Token(**result)


@router.post("/refresh", response_model=Token)
async def refresh(refresh_req: RefreshTokenRequest):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    result = await auth_service.refresh_tokens(refresh_req.refresh_token)
    return Token(**result)


@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    """
    Return the currently authenticated user's profile.
    Frontend uses this on page load to restore session state from a stored token.
    """
    return {
        "id": current_user.get("id"),
        "name": current_user.get("name"),
        "role": current_user.get("role"),
    }
