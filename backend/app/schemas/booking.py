"""Booking schemas for request/response validation."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class BookingCreate(BaseModel):
    """Schema for creating a new booking (public, no auth)."""
    guest_name: str = Field(..., min_length=1, max_length=200, description="Full guest name")
    guest_email: Optional[str] = Field("", description="Guest email address (optional)")
    guest_phone: str = Field(..., min_length=1, max_length=30, description="Guest phone number")
    room_id: str = Field(..., min_length=1, description="Room ID or category (Standard/Deluxe/Suite)")
    checkin: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Check-in date YYYY-MM-DD")
    checkin_time: Optional[str] = Field("12:00", description="Check-in time (HH:MM)")
    checkout: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Check-out date YYYY-MM-DD")
    checkout_time: Optional[str] = Field("11:00", description="Check-out time (HH:MM)")
    guests_count: Optional[int] = Field(2, ge=1, le=10, description="Number of guests")
    special_requests: Optional[str] = Field("", max_length=500)
    amount: Optional[float] = Field(None, ge=0, description="Custom booking amount in INR (optional)")
    aadhaar_file: Optional[str] = Field(None, description="Path to uploaded Aadhaar document")
    photo_file: Optional[str] = Field(None, description="Path to uploaded live guest photo (optional)")


class BookingUpdateStatus(BaseModel):
    """Schema for updating booking status."""
    status: str = Field(
        ...,
        description="Must be one of: pending, confirmed, checkedin, checkout",
    )


class BookingResponse(BaseModel):
    """Full booking response schema."""
    id: str
    booking_id: str
    bill_number: Optional[str] = None
    bill_seq: Optional[int] = None
    guest_name: str
    guest_email: Optional[str] = ""
    guest_phone: str
    room_id: str
    room_name: str
    checkin: str
    checkin_time: Optional[str] = "12:00"
    checkout: str
    checkout_time: Optional[str] = "11:00"
    checkin_datetime: Optional[datetime] = None
    checkout_datetime: Optional[datetime] = None
    amount: float
    guests_count: int
    special_requests: Optional[str] = ""
    status: str
    aadhaar_file: Optional[str] = None
    photo_file: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class BookingDashboardResponse(BaseModel):
    """
    Booking response shaped for the frontend dashboard table.
    Field names match what the frontend renderBookings() function expects.
    """
    id: str          # BK-XXXX
    guest: str       # Guest name
    room: str        # "205 — Ocean Suite"
    checkin: str     # "Jun 12"
    checkout: str    # "Jun 15"
    amount: str      # "$1,350"
    status: str      # "confirmed", "pending", etc.
    sc: str          # CSS class: "s-checkedin"
