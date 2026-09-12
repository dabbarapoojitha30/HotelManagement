"""
Room service — business logic for room CRUD operations and availability search.
Supports frontend status values: avail | occupied | reserved | maint
Backend also accepts 'booked' as an alias for 'occupied'.
"""
from datetime import datetime, timezone
from typing import List, Optional
import logging

from app.database import get_room_collection, get_booking_collection
from app.core.exceptions import NotFoundException, BadRequestException
from app.utils.timezone import (
    get_ist_now,
    to_ist,
    parse_ist_datetime,
    extract_booking_datetimes as _extract_booking_datetimes,
)

logger = logging.getLogger("VVResidencyAPI")

# All statuses the frontend may send or display
VALID_STATUSES = {"avail", "occupied", "booked", "reserved", "maint"}


def _normalize_status(status: str) -> str:
    """
    Normalize status for storage.
    'booked' → 'occupied' so the frontend always gets 'occupied' back.
    """
    s = status.lower().strip()
    if s == "booked":
        return "occupied"
    return s


def _serialize_room(doc: dict) -> dict:
    """Convert MongoDB doc to a JSON-safe dict for RoomResponse."""
    doc = dict(doc)
    doc.pop("_id", None)
    if "id" not in doc or doc["id"] is None:
        doc["id"] = ""
    doc.setdefault("floor", "")
    doc.setdefault("feats", [])
    doc.setdefault("fcls", [])
    doc.setdefault("cls", "r1")
    doc.setdefault("name", "")
    doc.setdefault("type", "")
    # Normalize booked → occupied on read
    if doc.get("status") == "booked":
        doc["status"] = "occupied"
    return doc


async def get_all_rooms(status_filter: Optional[str] = None) -> List[dict]:
    """
    Retrieve all rooms with optional status filter.
    Accepts: 'all' | 'avail' | 'occupied' | 'booked' | 'reserved' | 'maint'
    """
    rooms_col = get_room_collection()
    query: dict = {}

    if status_filter and status_filter not in ("all", ""):
        norm = _normalize_status(status_filter)
        # Query for both 'occupied' and 'booked' when filtering occupied
        if norm == "occupied":
            query["status"] = {"$in": ["occupied", "booked"]}
        else:
            query["status"] = norm

    cursor = rooms_col.find(query)
    rooms = []
    async for doc in cursor:
        rooms.append(_serialize_room(doc))
    return rooms


async def get_room_by_id(room_id: str) -> dict:
    """Get a single room by its room number/ID. Raises NotFoundException."""
    rooms_col = get_room_collection()
    doc = await rooms_col.find_one({"id": room_id})
    if not doc:
        raise NotFoundException(f"Room {room_id} not found")
    return _serialize_room(doc)


async def search_available_rooms(
    checkin: Optional[str] = None,
    checkout: Optional[str] = None,
    room_type: Optional[str] = None,
    checkin_time: Optional[str] = "12:00",
    checkout_time: Optional[str] = "11:00",
) -> List[dict]:
    """
    Search available rooms by date/time range and type in IST.
    Excludes rooms that have overlapping active bookings.
    """
    rooms_col = get_room_collection()
    bookings_col = get_booking_collection()

    # Only avail and reserved rooms are bookable
    query: dict = {"status": {"$in": ["avail", "reserved"]}}

    if room_type and room_type.lower() not in ("all", ""):
        query["type"] = {"$regex": room_type, "$options": "i"}

    cursor = rooms_col.find(query)
    candidate_rooms = []
    async for doc in cursor:
        candidate_rooms.append(_serialize_room(doc))

    # If dates provided, exclude rooms booked within that range
    if checkin and checkout:
        ci_search = parse_ist_datetime(checkin, checkin_time or "12:00")
        co_search = parse_ist_datetime(checkout, checkout_time or "11:00")
        if ci_search >= co_search:
            raise BadRequestException("Check-out date/time must be after check-in date/time")

        booked_room_ids = set()
        booking_cursor = bookings_col.find({
            "status": {"$in": ["confirmed", "checkedin", "pending"]},
        })
        async for b in booking_cursor:
            b_ci, b_co = _extract_booking_datetimes(b)
            # Two intervals overlap if and only if b_ci < co_search and b_co > ci_search
            if b_ci < co_search and b_co > ci_search:
                booked_room_ids.add(b.get("room_id"))

        candidate_rooms = [r for r in candidate_rooms if r.get("id") not in booked_room_ids]

    return candidate_rooms


async def create_room(room_data: dict) -> dict:
    """
    Create a new room. Raises BadRequestException if room ID already exists.
    """
    rooms_col = get_room_collection()

    existing = await rooms_col.find_one({"id": room_data["id"]})
    if existing:
        raise BadRequestException(f"Room with ID {room_data['id']} already exists")

    # Normalize status
    if "status" in room_data:
        room_data["status"] = _normalize_status(room_data["status"])

    room_data["created_at"] = get_ist_now()
    await rooms_col.insert_one(room_data)
    logger.info(f"Room created: {room_data['id']}")
    return _serialize_room(room_data)


async def update_room(room_id: str, update_data: dict) -> dict:
    """Update a room's properties. Raises NotFoundException."""
    rooms_col = get_room_collection()

    existing = await rooms_col.find_one({"id": room_id})
    if not existing:
        raise NotFoundException(f"Room {room_id} not found")

    # Normalize status if being updated
    if "status" in update_data and update_data["status"]:
        update_data["status"] = _normalize_status(update_data["status"])

    filtered = {k: v for k, v in update_data.items() if v is not None}
    filtered["updated_at"] = get_ist_now()

    if filtered:
        await rooms_col.update_one({"id": room_id}, {"$set": filtered})

    updated = await rooms_col.find_one({"id": room_id})
    return _serialize_room(updated)


async def update_room_status(room_id: str, new_status: str) -> dict:
    """
    Update only a room's status field.
    Valid values: avail, occupied, booked, reserved, maint.
    """
    norm = _normalize_status(new_status)
    if norm not in VALID_STATUSES:
        raise BadRequestException(f"Status must be one of: {', '.join(VALID_STATUSES)}")

    rooms_col = get_room_collection()
    existing = await rooms_col.find_one({"id": room_id})
    if not existing:
        raise NotFoundException(f"Room {room_id} not found")

    await rooms_col.update_one({"id": room_id}, {"$set": {"status": norm, "updated_at": get_ist_now()}})
    updated = await rooms_col.find_one({"id": room_id})
    return _serialize_room(updated)


async def delete_room(room_id: str) -> dict:
    """Delete a room by room ID. Raises NotFoundException."""
    rooms_col = get_room_collection()

    existing = await rooms_col.find_one({"id": room_id})
    if not existing:
        raise NotFoundException(f"Room {room_id} not found")

    await rooms_col.delete_one({"id": room_id})
    logger.info(f"Room deleted: {room_id}")
    return {"message": f"Room {room_id} deleted successfully"}


def get_room_status(room: dict, bookings: list, current_dt: Optional[datetime] = None) -> str:
    """
    Derive a room's status based on active booking date/time ranges in IST.
    - If current_dt < checkin_dt → status = "reserved" (upcoming booking exists)
    - If checkin_dt <= current_dt < checkout_dt → status = "occupied" (currently active stay)
    - Otherwise, default to "maint" if set by manager, or "avail".
    """
    if current_dt is None:
        current_dt = get_ist_now()
    else:
        current_dt = to_ist(current_dt)

    room_bookings = [
        b for b in bookings
        if b.get("room_id") == room["id"] and b.get("status") in ("confirmed", "checkedin", "pending")
    ]

    covering_booking = None
    future_booking = None

    for b in room_bookings:
        try:
            ci, co = _extract_booking_datetimes(b)
            if ci <= current_dt < co:
                covering_booking = b
                break
            elif current_dt < ci:
                if not future_booking:
                    future_booking = (b, ci)
                elif ci < future_booking[1]:
                    future_booking = (b, ci)
        except Exception:
            continue

    if covering_booking:
        return "occupied"
    elif future_booking:
        return "reserved"
    elif room.get("status") == "maint":
        return "maint"
    else:
        return "avail"


async def sync_room_statuses_and_bookings(current_dt: Optional[datetime] = None) -> None:
    """
    Auto-checkout expired bookings (checkout_dt <= current_dt in IST)
    and update room statuses in MongoDB based on precise IST time.
    """
    if current_dt is None:
        current_dt = get_ist_now()
    else:
        current_dt = to_ist(current_dt)

    bookings_col = get_booking_collection()
    rooms_col = get_room_collection()

    # 1. Update expired active bookings to "checkout"
    active_cursor = bookings_col.find({"status": {"$in": ["confirmed", "checkedin", "pending"]}})
    async for b in active_cursor:
        try:
            _, co = _extract_booking_datetimes(b)
            if current_dt >= co:
                await bookings_col.update_one(
                    {"_id": b["_id"]},
                    {"$set": {"status": "checkout", "updated_at": get_ist_now()}}
                )
                logger.info(f"Booking {b.get('booking_id')} automatically moved to checkout (time expired in IST).")
        except Exception as e:
            logger.error(f"Failed to auto checkout booking: {e}")
            continue

    # 2. Get all rooms and bookings
    rooms_cursor = rooms_col.find({})
    rooms_list = []
    async for r in rooms_cursor:
        rooms_list.append(r)

    active_bookings_cursor = bookings_col.find({"status": {"$in": ["confirmed", "checkedin", "pending"]}})
    active_bookings = []
    async for b in active_bookings_cursor:
        active_bookings.append(b)

    # 3. Update room status in DB
    for r in rooms_list:
        new_status = get_room_status(r, active_bookings, current_dt)
        if new_status != r.get("status"):
            await rooms_col.update_one({"id": r["id"]}, {"$set": {"status": new_status}})
            logger.info(f"Sync: Room {r['id']} status updated to {new_status}")

