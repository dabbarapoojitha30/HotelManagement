"""
Authentication service — business logic for login, registration, user management, and token refresh.
Uses name and role credentials for authentication.
"""
from datetime import datetime, timezone
import logging
import re
from typing import Optional

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.database import get_user_collection
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_password_hash,
    verify_password,
)
from app.utils.timezone import get_ist_now

logger = logging.getLogger("VVResidencyAPI")


async def authenticate_user(name: str, role: str, password: str) -> dict:
    """
    Validate name + role + password and return a Token dict.
    Raises UnauthorizedException on failure.
    """
    users_col = get_user_collection()
    user = await users_col.find_one({
        "name": {"$regex": f"^{re.escape(name.strip())}$", "$options": "i"},
        "role": role.strip().lower(),
    })

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


async def list_all_users() -> list[dict]:
    """Retrieve all staff users (excludes password hashes)."""
    users_col = get_user_collection()
    users = []
    async for u in users_col.find({}, {"hashed_password": 0}).sort("created_at", -1):
        users.append({
            "id": str(u["_id"]),
            "name": u.get("name"),
            "role": u.get("role"),
            "created_at": u.get("created_at"),
        })
    return users


async def delete_user_by_id(user_id: str, current_user: dict) -> bool:
    """
    Delete a staff user by ID.
    Raises ForbiddenException if trying to delete self.
    Raises NotFoundException if user does not exist.
    """
    current_id = str(current_user.get("id") or current_user.get("_id") or "")
    if current_id == str(user_id):
        raise ForbiddenException("You cannot delete your own active account.")

    try:
        obj_id = ObjectId(user_id)
    except Exception:
        raise BadRequestException("Invalid user ID format.")

    users_col = get_user_collection()
    result = await users_col.delete_one({"_id": obj_id})
    if result.deleted_count == 0:
        raise NotFoundException("User not found.")

    logger.info(f"User {user_id} deleted by owner {current_user.get('name')}")
    return True


async def update_user_profile(
    user_id: str,
    current_password: str,
    new_name: Optional[str] = None,
    new_password: Optional[str] = None,
) -> dict:
    """
    Allow authenticated user to update their own name and/or password.
    Requires validating current_password.
    Generates fresh access & refresh tokens on update.
    """
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        raise BadRequestException("Invalid user ID format.")

    users_col = get_user_collection()
    user = await users_col.find_one({"_id": obj_id})
    if not user:
        raise NotFoundException("User not found.")

    # Validate current password
    if not verify_password(current_password, user.get("hashed_password", "")):
        raise BadRequestException("Current password is incorrect.")

    update_fields = {}
    updated_name = user["name"]

    # Check and update name
    if new_name:
        clean_name = new_name.strip()
        if clean_name and clean_name.lower() != user["name"].lower():
            # Check for conflict with another account having the same name and role
            existing = await users_col.find_one({
                "_id": {"$ne": obj_id},
                "name": {"$regex": f"^{re.escape(clean_name)}$", "$options": "i"},
                "role": user["role"],
            })
            if existing:
                raise BadRequestException(f"A user with the name '{clean_name}' already exists for this role.")
            update_fields["name"] = clean_name
            updated_name = clean_name

    # Check and update password
    if new_password:
        clean_pwd = new_password.strip()
        if len(clean_pwd) < 6:
            raise BadRequestException("New password must be at least 6 characters long.")
        update_fields["hashed_password"] = get_password_hash(clean_pwd)

    if not update_fields:
        # Nothing changed
        user_data = {"name": user["name"], "role": user["role"]}
        return {
            "id": str(user["_id"]),
            "name": user["name"],
            "role": user["role"],
            "access_token": create_access_token(data=user_data),
            "refresh_token": create_refresh_token(data=user_data),
            "message": "No changes were made.",
        }

    update_fields["updated_at"] = get_ist_now()
    await users_col.update_one({"_id": obj_id}, {"$set": update_fields})

    # Generate fresh tokens reflecting the updated user identity
    user_data = {"name": updated_name, "role": user["role"]}
    access_token = create_access_token(data=user_data)
    refresh_token = create_refresh_token(data=user_data)

    logger.info(f"User {user_id} ({updated_name}) updated their profile successfully.")
    return {
        "id": str(user["_id"]),
        "name": updated_name,
        "role": user["role"],
        "access_token": access_token,
        "refresh_token": refresh_token,
        "message": "Profile updated successfully.",
    }

