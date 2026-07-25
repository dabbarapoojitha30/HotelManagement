"""Room schemas for request/response validation."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# Valid room statuses — backend stores all of these
VALID_STATUSES = {"avail", "occupied", "booked", "reserved", "maint"}


class RoomCreate(BaseModel):
    """Schema for creating a new room (frontend-compatible)."""
    id: str = Field(..., min_length=1, max_length=20, description="Room ID/Number, e.g. 101")
    floor: Optional[str] = Field(None, max_length=100, description="e.g. 1st Floor")
    price: float = Field(..., gt=0, description="Nightly price, must be positive")
    status: Optional[str] = Field("avail", description="avail | occupied | reserved | maint")
    # Legacy / optional fields kept for backward compatibility
    name: Optional[str] = Field(None, max_length=100, description="e.g. Deluxe City View")
    type: Optional[str] = Field(None, max_length=100, description="e.g. Deluxe Room · Floor 3")
    cls: Optional[str] = Field("r1", description="CSS class key")
    feats: Optional[List[str]] = Field(default_factory=list)
    fcls: Optional[List[str]] = Field(default_factory=list)


class RoomUpdate(BaseModel):
    """Schema for updating a room (all fields optional)."""
    floor: Optional[str] = Field(None, max_length=100)
    price: Optional[float] = Field(None, gt=0)
    status: Optional[str] = None  # avail | occupied | booked | reserved | maint
    name: Optional[str] = Field(None, max_length=100)
    type: Optional[str] = Field(None, max_length=100)
    cls: Optional[str] = None
    feats: Optional[List[str]] = None
    fcls: Optional[List[str]] = None


class RoomStatusUpdate(BaseModel):
    """Schema for the PATCH room status endpoint."""
    status: str = Field(..., description="avail | occupied | booked | reserved | maint")


class RoomResponse(BaseModel):
    """Schema for room response — matches what the frontend expects."""
    id: str
    floor: Optional[str] = ""
    price: float
    status: str           # always one of: avail | occupied | reserved | maint
    name: Optional[str] = ""
    type: Optional[str] = ""
    cls: Optional[str] = "r1"
    feats: Optional[List[str]] = []
    fcls: Optional[List[str]] = []
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda v: v.isoformat()}
