"""
Authentication routes — login, register, refresh, profile, and user management.
Uses name and role credentials for authentication.
"""
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from app.schemas.user import (
    UserRegister,
    UserResponse,
    UserLogin,
    UserProfileUpdate,
    UserProfileResponse,
)
from app.schemas.auth import Token, RefreshTokenRequest
from app.auth.dependencies import get_current_user, require_roles
from app.services import auth_service
from app.core.exceptions import ForbiddenException

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_403_FORBIDDEN)
async def register():
    """Public registration is disabled. New users can only be created by the owner from the Owner Dashboard."""
    raise ForbiddenException("Public signup is disabled. New users can only be added from the Owner page.")


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


@router.put("/profile", response_model=UserProfileResponse)
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user=Depends(get_current_user),
):
    """
    Update own account profile (display name and/or password).
    Requires validating current password.
    Returns fresh access & refresh tokens on success.
    """
    return await auth_service.update_user_profile(
        user_id=current_user["id"],
        current_password=profile_data.current_password,
        new_name=profile_data.name,
        new_password=profile_data.new_password,
    )


# ── Owner-Only User Management ─────────────────────────────────────
@router.get("/users", response_model=list[UserResponse])
async def get_all_users(current_user=Depends(require_roles(["owner"]))):
    """List all staff users (Owner only)."""
    return await auth_service.list_all_users()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(user_data: UserRegister, current_user=Depends(require_roles(["owner"]))):
    """Create a new staff user (Owner only)."""
    return await auth_service.register_user(
        name=user_data.name,
        role=user_data.role,
        password=user_data.password,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(user_id: str, current_user=Depends(require_roles(["owner"]))):
    """Delete a staff user (Owner only)."""
    await auth_service.delete_user_by_id(user_id=user_id, current_user=current_user)
    return {"message": "User deleted successfully", "id": user_id}

