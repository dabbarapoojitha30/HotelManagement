"""Booking database model."""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, BeforeValidator
from typing_extensions import Annotated

PyObjectId = Annotated[str, BeforeValidator(str)]


class BookingDB(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    booking_id: str  # BK-XXXX
    guest_name: str
    guest_email: str
    guest_phone: str
    room_id: str  # e.g. "101"
    room_name: str  # e.g. "Deluxe City View"
    checkin: str  # "YYYY-MM-DD"
    checkout: str  # "YYYY-MM-DD"
    amount: float
    guests_count: int = 2
    special_requests: Optional[str] = ""
    status: str = "pending"  # "pending", "confirmed", "checkedin", "checkout"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}
