"""
Authentication dependencies for FastAPI dependency injection.
Extracted from routes/auth.py to be reusable across all route modules.
"""
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import get_user_collection
from app.utils.security import decode_access_token

security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security_bearer),
):
    """
    Decode the JWT access token from the Authorization header and return
    the corresponding user document from MongoDB.
    Raises 401 if token is missing, invalid, expired, or user not found.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    name = payload.get("name")
    role = payload.get("role")
    if not name or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    users_col = get_user_collection()
    user = await users_col.find_one({"name": name, "role": role})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    # Convert _id to string for standard dict usage
    user["id"] = str(user["_id"])
    return user


def require_roles(allowed_roles: list):
    """
    FastAPI dependency factory — returns a dependency that ensures
    the authenticated user has one of the specified roles.
    Usage: current_user = Depends(require_roles(["admin", "staff"]))
    """
    async def role_checker(user=Depends(get_current_user)):
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Insufficient permissions",
            )
        return user
    return role_checker
