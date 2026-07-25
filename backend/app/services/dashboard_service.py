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
from app.database import get_booking_collection, get_room_collection
from app.schemas.booking import BookingDashboardResponse
import logging

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


def _format_time(dt: datetime) -> str:
    """Format datetime as '7:40 PM'."""
    try:
        return dt.strftime("%-I:%M %p")  # Linux/Mac
    except ValueError:
        return dt.strftime("%I:%M %p").lstrip("0")


async def get_dashboard_stats() -> dict:
    """
    Aggregate all dashboard statistics needed by the frontend:
    - room_counts: dict of status → count
    - total_rooms: total room count
    - occupancy: percentage occupied
    - today_revenue: sum of amounts from bookings created today (INR)
    - bookings_this_month: count of bookings this month
    - checkins: list of recent check-in activities
    - checkouts: list of recent check-out activities
    - recent_bookings: last 10 formatted for the booking table
    - satisfaction: fixed 4.91 rating
    """
    bookings_col = get_booking_collection()
    rooms_col = get_room_collection()

    # ── Room counts (Dynamically derived using get_room_status) ──────
    rooms_cursor = rooms_col.find({})
    rooms_list = []
    async for r in rooms_cursor:
        rooms_list.append(r)

    active_bookings_cursor = bookings_col.find({"status": {"$in": ["confirmed", "checkedin", "pending"]}})
    active_bookings = []
    async for b in active_bookings_cursor:
        active_bookings.append(b)

    from app.services.room_service import get_room_status
    today = datetime.now().date()
    today_str = today.strftime("%Y-%m-%d")

    total_rooms = len(rooms_list)
    avail_count = 0
    occupied_count = 0
    reserved_count = 0
    maint_count = 0

    for r in rooms_list:
        status = get_room_status(r, active_bookings, today)
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
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

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

        # Today's revenue — confirmed/checkedin bookings created today
        if created_at and isinstance(created_at, datetime):
            # Make timezone-aware for comparison
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at >= today_start and status in ("confirmed", "checkedin", "checkout"):
                today_revenue += amount
            if created_at.year == now.year and created_at.month == now.month:
                bookings_this_month += 1

        # Build check-in / check-out activity lists
        time_str = ""
        if created_at:
            try:
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                local_dt = created_at.astimezone()
                time_str = local_dt.strftime("%I:%M %p").lstrip("0") or local_dt.strftime("%I:%M %p")
            except Exception:
                time_str = ""

        activity = {"guest": guest_name, "room": room_id, "time": time_str}

        if b.get("checkin") == today_str:
            checkins.append(activity)

        # Show in checkouts if: status is 'checkout' AND was updated today
        if status == "checkout":
            updated_at = b.get("updated_at")
            if updated_at and isinstance(updated_at, datetime):
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                if updated_at >= today_start:
                    # Use updated_at time for display
                    try:
                        local_upd = updated_at.astimezone()
                        upd_time_str = local_upd.strftime("%I:%M %p").lstrip("0") or local_upd.strftime("%I:%M %p")
                    except Exception:
                        upd_time_str = time_str
                    checkouts.append({"guest": guest_name, "room": room_id, "time": upd_time_str})
            elif b.get("checkout") == today_str:
                # Fallback: if no updated_at, use scheduled date match
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
