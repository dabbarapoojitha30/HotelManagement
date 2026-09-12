"""
Dashboard service — business logic for aggregating dashboard statistics.
Returns data that exactly matches what the VV Residency frontend (index.html) expects:
- room_counts: {avail, occupied, reserved, maint}
- today_revenue: float (INR)
- checkins / checkouts: list of recent activity
- recent_bookings: last 10 bookings for dashboard table
"""
from typing import List, Dict, Any
from datetime import datetime, timezone
import logging

from app.database import get_booking_collection, get_room_collection
from app.schemas.booking import BookingDashboardResponse
from app.services.room_service import get_room_status
from app.utils.timezone import get_ist_now, to_ist, format_ist_time_12hr

logger = logging.getLogger("VVResidencyAPI")


def _format_date_str(date_str: str) -> str:
    """Convert 'YYYY-MM-DD' → 'Jun 12' for dashboard display."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%b %d")
    except Exception:
        return date_str


def _format_amount_inr(amount: float) -> str:
    """Format amount as '₹1,350'."""
    return f"₹{amount:,.0f}"


async def get_dashboard_stats() -> dict:
    """
    Aggregate all dashboard statistics needed by the frontend:
    - room_counts: dict of status → count
    - total_rooms: total room count
    - occupancy: percentage occupied
    - today_revenue: sum of amounts from bookings created today in IST (INR)
    - bookings_this_month: count of bookings this month
    - checkins: list of recent check-in activities
    - checkouts: list of recent check-out activities
    - recent_bookings: last 10 formatted for the booking table
    - satisfaction: fixed 4.91 rating
    """
    bookings_col = get_booking_collection()
    rooms_col = get_room_collection()

    now_ist = get_ist_now()
    today_str = now_ist.strftime("%Y-%m-%d")
    today_start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)

    # ── Room counts (Dynamically derived using get_room_status in IST) ──
    rooms_cursor = rooms_col.find({})
    rooms_list = []
    async for r in rooms_cursor:
        rooms_list.append(r)

    active_bookings_cursor = bookings_col.find({"status": {"$in": ["confirmed", "checkedin", "pending"]}})
    active_bookings = []
    async for b in active_bookings_cursor:
        active_bookings.append(b)

    total_rooms = len(rooms_list)
    avail_count = 0
    occupied_count = 0
    reserved_count = 0
    maint_count = 0

    for r in rooms_list:
        status = get_room_status(r, active_bookings, now_ist)
        if status == "avail":
            avail_count += 1
        elif status in ("occupied", "booked"):
            occupied_count += 1
        elif status == "reserved":
            reserved_count += 1
        elif status == "maint":
            maint_count += 1

    occupancy = (occupied_count / total_rooms * 100) if total_rooms > 0 else 0.0

    room_counts = {
        "avail": avail_count,
        "occupied": occupied_count,
        "reserved": reserved_count,
        "maint": maint_count,
    }

    # ── Revenue + booking aggregations ───────────────────────────────
    status_to_class = {
        "pending":   "s-pending",
        "confirmed": "s-confirmed",
        "checkedin": "s-checkedin",
        "checkout":  "s-checkout",
    }

    today_revenue = 0.0
    bookings_this_month = 0
    recent_bookings: List[BookingDashboardResponse] = []
    checkins: List[Dict[str, Any]] = []
    checkouts: List[Dict[str, Any]] = []

    # Sort newest first
    cursor = bookings_col.find().sort("created_at", -1)

    async for b in cursor:
        created_at = b.get("created_at")
        amount = float(b.get("amount", 0.0))
        status = b.get("status", "pending")
        guest_name = b.get("guest_name", "Guest")
        room_id = b.get("room_id", "")

        # Today's revenue — confirmed/checkedin bookings created today in IST
        if created_at and isinstance(created_at, datetime):
            created_ist = to_ist(created_at)
            if created_ist >= today_start_ist and status in ("confirmed", "checkedin", "checkout"):
                today_revenue += amount
            if created_ist.year == now_ist.year and created_ist.month == now_ist.month:
                bookings_this_month += 1

        # Build check-in / check-out activity lists in IST
        time_str = ""
        if created_at and isinstance(created_at, datetime):
            time_str = format_ist_time_12hr(created_at)

        activity = {"guest": guest_name, "room": room_id, "time": time_str}

        if b.get("checkin") == today_str:
            checkins.append(activity)

        # Show in checkouts if: status is 'checkout' AND was updated today in IST
        if status == "checkout":
            updated_at = b.get("updated_at")
            if updated_at and isinstance(updated_at, datetime):
                updated_ist = to_ist(updated_at)
                if updated_ist >= today_start_ist:
                    checkouts.append({"guest": guest_name, "room": room_id, "time": format_ist_time_12hr(updated_ist)})
            elif b.get("checkout") == today_str:
                checkouts.append(activity)

        # Recent bookings for dashboard table
        room_display = f"{room_id} — {b.get('room_name', '')}"
        formatted = BookingDashboardResponse(
            id=b.get("booking_id", ""),
            guest=guest_name,
            room=room_display,
            checkin=_format_date_str(b.get("checkin", "")),
            checkout=_format_date_str(b.get("checkout", "")),
            amount=_format_amount_inr(amount),
            status=status,
            sc=status_to_class.get(status, "s-pending"),
        )
        recent_bookings.append(formatted)

    return {
        "total_rooms": total_rooms,
        "occupancy": round(occupancy, 1),
        "bookings_this_month": bookings_this_month,
        "satisfaction": 4.91,
        "today_revenue": today_revenue,
        "room_counts": room_counts,
        "checkins": checkins[:20],       # Recent 20 check-ins
        "checkouts": checkouts[:20],     # Recent 20 check-outs
        "recent_bookings": recent_bookings[:10],
    }
