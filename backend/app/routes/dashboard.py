"""
Dashboard routes — aggregated hotel statistics, room counts, and recent activity.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.booking import BookingDashboardResponse
from app.services import dashboard_service
from app.services.room_service import sync_room_statuses_and_bookings
from app.utils.timezone import get_ist_now

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class RoomCounts(BaseModel):
    """Room count by status."""
    avail: int
    occupied: int
    reserved: int
    maint: int


class ActivityItem(BaseModel):
    """A single check-in or check-out activity entry."""
    guest: str
    room: str
    time: str


class DashboardStats(BaseModel):
    """Full dashboard statistics response — matches what frontend expects."""
    total_rooms: int
    occupancy: float
    bookings_this_month: int
    satisfaction: float
    today_revenue: float
    room_counts: RoomCounts
    checkins: List[ActivityItem]
    checkouts: List[ActivityItem]
    recent_bookings: List[BookingDashboardResponse]


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """
    Get aggregated dashboard statistics:
    - Total room count and occupancy percentage
    - Room counts per status (avail/occupied/reserved/maint)
    - Today's revenue (INR) from confirmed/checkedin bookings
    - Total booking count this month
    - Recent check-in and check-out activity lists
    - Last 10 bookings formatted for the dashboard table
    """
    await sync_room_statuses_and_bookings(get_ist_now())
    stats = await dashboard_service.get_dashboard_stats()
    return DashboardStats(**stats)
