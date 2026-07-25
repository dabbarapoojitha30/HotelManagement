"""
Authentication service — business logic for login, registration, and token refresh.
Supports both email-based login (standard) and username-based login (staff shortcut).
"""
from datetime import datetime, timezone
from app.database import get_user_collection
from app.utils.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.core.exceptions import (
    BadRequestException,
    UnauthorizedException,
)
from pymongo.errors import DuplicateKeyError
import logging

logger = logging.getLogger("VVResidencyAPI")

async def authenticate_user(name: str, role: str, password: str) -> dict:
    """
    Validate name + role + password and return a Token dict.
    Raises UnauthorizedException on failure.
    """
    users_col = get_user_collection()
    user = await users_col.find_one({"name": name, "role": role})

    if not user or not verify_password(password, user["hashed_password"]):
        raise UnauthorizedException("Incorrect name, role, or password")

    user_data = {"name": user["name"], "role": user["role"]}
    access_token = create_access_token(data=user_data)
    refresh_token = create_refresh_token(data=user_data)

    redirect_url = "index.html" if user["role"] == "manager" else "owner.html"

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "role": user["role"],
        "name": user["name"],
        "redirect": redirect_url,
    }


async def register_user(name: str, role: str, password: str) -> dict:
    """
    Create a new user. Role is either 'manager' or 'owner'.
    Raises BadRequestException if user with the same name + role already exists.
    """
    users_col = get_user_collection()

    existing = await users_col.find_one({"name": name, "role": role})
    if existing:
        raise BadRequestException("User with this name and role already registered")

    user_dict = {
        "name": name,
        "role": role,
        "hashed_password": get_password_hash(password),
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = await users_col.insert_one(user_dict)
    except DuplicateKeyError:
        raise BadRequestException("User with this name and role already registered")
    user_dict["id"] = str(result.inserted_id)
    logger.info(f"New user registered: {name} ({role})")
    return user_dict


async def refresh_tokens(refresh_token_str: str) -> dict:
    """
    Validate a refresh token and issue a new access + refresh token pair.
    Raises UnauthorizedException on invalid/expired refresh token.
    """
    payload = decode_refresh_token(refresh_token_str)
    if not payload:
        raise UnauthorizedException("Invalid or expired refresh token")

    name = payload.get("name")
    role = payload.get("role")
    if not name or not role:
        raise UnauthorizedException("Invalid refresh token payload")

    users_col = get_user_collection()
    user = await users_col.find_one({"name": name, "role": role})
    if not user:
        raise UnauthorizedException("User not found")

    user_data = {"name": user["name"], "role": user["role"]}
    access_token = create_access_token(data=user_data)
    new_refresh_token = create_refresh_token(data=user_data)

    redirect_url = "index.html" if user["role"] == "manager" else "owner.html"

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "role": user["role"],
        "name": user["name"],
        "redirect": redirect_url,
    }
