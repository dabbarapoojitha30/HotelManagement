from pydantic import BaseModel
from typing import Optional

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    name: str
    redirect: str

class TokenData(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str
