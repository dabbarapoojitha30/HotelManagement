"""Booking database model."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, BeforeValidator
from typing_extensions import Annotated
from app.utils.timezone import get_ist_now

PyObjectId = Annotated[str, BeforeValidator(str)]


class BookingDB(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    booking_id: str  # BK-XXXX
    bill_number: Optional[str] = None  # e.g. "001"
    bill_seq: Optional[int] = None     # e.g. 1
    guest_name: str
    guest_email: Optional[str] = ""
    guest_phone: str
    room_id: str  # e.g. "101"
    room_name: str  # e.g. "Deluxe City View"
    checkin: str  # "YYYY-MM-DD"
    checkin_time: Optional[str] = "12:00"  # "HH:MM"
    checkout: str  # "YYYY-MM-DD"
    checkout_time: Optional[str] = "11:00"  # "HH:MM"
    checkin_datetime: Optional[datetime] = None
    checkout_datetime: Optional[datetime] = None
    amount: float
    guests_count: int = 2
    special_requests: Optional[str] = ""
    aadhaar_file: Optional[str] = None
    photo_file: Optional[str] = None
    status: str = "pending"  # "pending", "confirmed", "checkedin", "checkout"
    created_at: datetime = Field(default_factory=get_ist_now)

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

