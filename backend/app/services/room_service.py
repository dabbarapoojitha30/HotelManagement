"""
Room service — business logic for room CRUD operations and availability search.
Supports frontend status values: avail | occupied | reserved | maint
Backend also accepts 'booked' as an alias for 'occupied'.
"""
from datetime import datetime, timezone
from typing import List, Optional
from app.database import get_room_collection, get_booking_collection
from app.core.exceptions import NotFoundException, BadRequestException
import logging

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
) -> List[dict]:
    """
    Search available rooms by date range and type.
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
        from datetime import datetime as dt
        try:
            ci = dt.strptime(checkin, "%Y-%m-%d")
            co = dt.strptime(checkout, "%Y-%m-%d")
            if ci >= co:
                raise BadRequestException("Check-out must be after check-in")
        except ValueError:
            raise BadRequestException("Dates must be in YYYY-MM-DD format")

        booked_room_ids = set()
        booking_cursor = bookings_col.find({
            "status": {"$in": ["confirmed", "checkedin", "pending"]},
            "$or": [
                {"checkin": {"$lt": checkout}, "checkout": {"$gt": checkin}},
            ],
        })
        async for b in booking_cursor:
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

    room_data["created_at"] = datetime.now(timezone.utc)
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
    filtered["updated_at"] = datetime.now(timezone.utc)

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

    await rooms_col.update_one({"id": room_id}, {"$set": {"status": norm}})
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


def get_room_status(room: dict, bookings: list, current_date) -> str:
    """
    Derive a room's status based on active booking dates and current date.
    - If current_date < checkin_date → status = "reserved"
    - If current_date >= checkin_date AND current_date < checkout_date → status = "occupied"
    - Otherwise, default to "maint" if set by manager, or "avail".
    """
    room_bookings = [
        b for b in bookings 
        if b.get("room_id") == room["id"] and b.get("status") in ("confirmed", "checkedin", "pending")
    ]
    
    covering_booking = None
    future_booking = None
    
    for b in room_bookings:
        try:
            ci_val = b["checkin"]
            co_val = b["checkout"]
            if isinstance(ci_val, str):
                ci = datetime.strptime(ci_val, "%Y-%m-%d").date()
            else:
                ci = ci_val
            if isinstance(co_val, str):
                co = datetime.strptime(co_val, "%Y-%m-%d").date()
            else:
                co = co_val
                
            if ci <= current_date < co:
                covering_booking = b
                break
            elif current_date < ci:
                if not future_booking:
                    future_booking = b
                else:
                    f_ci = future_booking["checkin"]
                    if isinstance(f_ci, str):
                        f_ci = datetime.strptime(f_ci, "%Y-%m-%d").date()
                    if ci < f_ci:
                        future_booking = b
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


async def sync_room_statuses_and_bookings(current_date) -> None:
    """
    Auto-checkout expired bookings (checkout <= current_date)
    and update room statuses in MongoDB.
    """
    bookings_col = get_booking_collection()
    rooms_col = get_room_collection()
    
    # 1. Update old active bookings to "checkout"
    active_cursor = bookings_col.find({"status": {"$in": ["confirmed", "checkedin", "pending"]}})
    async for b in active_cursor:
        try:
            checkout_val = b["checkout"]
            if isinstance(checkout_val, str):
                co = datetime.strptime(checkout_val, "%Y-%m-%d").date()
            else:
                co = checkout_val
            if current_date >= co:
                await bookings_col.update_one(
                    {"_id": b["_id"]},
                    {"$set": {"status": "checkout", "updated_at": datetime.now(timezone.utc)}}
                )
                logger.info(f"Booking {b.get('booking_id')} automatically moved to checkout.")
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
        new_status = get_room_status(r, active_bookings, current_date)
        if new_status != r.get("status"):
            await rooms_col.update_one({"id": r["id"]}, {"$set": {"status": new_status}})
            logger.info(f"Sync: Room {r['id']} status updated to {new_status}")
