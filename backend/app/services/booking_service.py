"""
Booking service — business logic for booking CRUD and status transitions.
Rooms with status 'avail' or 'reserved' can be booked.
Status flow: confirmed → checkedin → checkout
"""
from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
from app.database import get_booking_collection, get_room_collection, get_counter_collection
from app.core.exceptions import NotFoundException, BadRequestException
import uuid
import logging

logger = logging.getLogger("VVResidencyAPI")

# Statuses that mean the room is currently in-use/committed
ACTIVE_STATUSES = {"confirmed", "checkedin", "pending"}


def _serialize_booking(doc: dict) -> dict:
    """Convert MongoDB doc to a JSON-safe dict for BookingResponse."""
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    else:
        doc.setdefault("id", "")
    doc.setdefault("guests_count", 2)
    doc.setdefault("special_requests", "")
    doc.setdefault("created_at", None)
    doc.setdefault("room_name", "")
    doc.setdefault("bill_number", None)
    return doc


async def get_next_bill_number() -> str:
    """Atomically increment the bill counter and return a zero-padded bill number string."""
    counters_col = get_counter_collection()
    result = await counters_col.find_one_and_update(
        {"name": "bill_number"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    seq = result["seq"]
    return str(seq).zfill(3)  # 001, 002, ...


async def _find_booking(bookings_col, booking_id: str) -> Optional[dict]:
    """Try to find a booking by booking_id (BK-XXXX) or MongoDB _id."""
    booking = await bookings_col.find_one({"booking_id": booking_id})
    if not booking:
        try:
            booking = await bookings_col.find_one({"_id": ObjectId(booking_id)})
        except Exception:
            pass
    return booking


def _generate_booking_id() -> str:
    """
    Generate a unique booking ID using UUID to avoid race conditions.
    Format: BK-XXXX (4 hex characters from UUID, uppercased).
    """
    short = uuid.uuid4().hex[:4].upper()
    return f"BK-{short}"


async def get_all_bookings(
    status_filter: Optional[str] = None,
    room_id: Optional[str] = None,
) -> List[dict]:
    """Get all bookings with optional filters. Returns newest first."""
    bookings_col = get_booking_collection()

    query: dict = {}
    if status_filter:
        query["status"] = status_filter.lower()
    if room_id:
        query["room_id"] = room_id

    cursor = bookings_col.find(query).sort("created_at", -1)
    bookings = []
    async for doc in cursor:
        bookings.append(_serialize_booking(doc))
    return bookings


async def get_booking_by_id(booking_id: str) -> dict:
    """Get a single booking by BK-XXXX id or MongoDB _id. Raises NotFoundException."""
    bookings_col = get_booking_collection()
    booking = await _find_booking(bookings_col, booking_id)
    if not booking:
        raise NotFoundException(f"Booking {booking_id} not found")
    return _serialize_booking(booking)


async def create_booking(booking_data: dict) -> dict:
    """
    Create a new booking.
    - Rooms with status 'avail' or 'reserved' can be booked.
    - Calculates amount = nights × room price.
    - Sets booking status = 'confirmed', room status = 'occupied'.
    """
    rooms_col = get_room_collection()
    bookings_col = get_booking_collection()

    from app.services.room_service import sync_room_statuses_and_bookings
    await sync_room_statuses_and_bookings(datetime.now().date())

    # Find the exact room
    room = await rooms_col.find_one({"id": booking_data["room_id"]})

    # Fallback: treat room_id as a room-type category name
    if not room and booking_data["room_id"] in ["Standard", "Deluxe", "Suite"]:
        async for r in rooms_col.find({
            "type": {"$regex": booking_data["room_id"], "$options": "i"},
            "status": {"$in": ["avail", "reserved"]},
        }):
            room = r
            break

    if not room:
        raise NotFoundException(
            f"Room '{booking_data['room_id']}' not found or no available rooms of this type"
        )

    # Allow both 'avail' and 'reserved' rooms to be booked
    if room["status"] not in ("avail", "reserved"):
        raise BadRequestException(
            f"Room {room['id']} is currently not available for booking (status: {room['status']})"
        )

    # Validate and parse dates
    try:
        ci_date = datetime.strptime(booking_data["checkin"], "%Y-%m-%d").date()
        co_date = datetime.strptime(booking_data["checkout"], "%Y-%m-%d").date()
    except ValueError:
        raise BadRequestException("Dates must be in YYYY-MM-DD format")

    today = datetime.now().date()
    if ci_date < today:
        raise BadRequestException("Check-in date cannot be in the past")

    nights = (co_date - ci_date).days
    if nights <= 0:
        raise BadRequestException("Check-out date must be after check-in date")

    amount = nights * room["price"]

    # Generate unique booking ID
    for _ in range(20):
        bk_id = _generate_booking_id()
        if not await bookings_col.find_one({"booking_id": bk_id}):
            break

    now = datetime.now(timezone.utc)
    bill_no = await get_next_bill_number()
    booking_dict = {
        "booking_id": bk_id,
        "bill_number": bill_no,
        "guest_name": booking_data["guest_name"],
        "guest_email": booking_data["guest_email"],
        "guest_phone": booking_data["guest_phone"],
        "room_id": room["id"],
        "room_name": room.get("name") or room.get("floor") or f"Room {room['id']}",
        "checkin": booking_data["checkin"],
        "checkout": booking_data["checkout"],
        "amount": amount,
        "guests_count": booking_data.get("guests_count") or 2,
        "special_requests": booking_data.get("special_requests") or "",
        "aadhaar_file": booking_data.get("aadhaar_file"),
        "status": "confirmed",
        "created_at": now,
    }

    result = await bookings_col.insert_one(booking_dict)
    booking_dict["id"] = str(result.inserted_id)

    # Automatically derive and set correct room status (reserved / occupied)
    await sync_room_statuses_and_bookings(datetime.now().date())
    logger.info(f"Booking created: {bk_id} for room {room['id']}")

    return booking_dict


async def update_booking_status(booking_id: str, new_status: str) -> dict:
    """
    Update booking status. Valid: pending, confirmed, checkedin, checkout.
    On checkout → room becomes 'avail'.
    On confirmed/checkedin → room stays 'occupied'.
    """
    bookings_col = get_booking_collection()
    rooms_col = get_room_collection()

    booking = await _find_booking(bookings_col, booking_id)
    if not booking:
        raise NotFoundException(f"Booking {booking_id} not found")

    new_status = new_status.lower()
    if new_status not in ["pending", "confirmed", "checkedin", "checkout"]:
        raise BadRequestException(
            "Status must be one of: pending, confirmed, checkedin, checkout"
        )

    await bookings_col.update_one(
        {"_id": booking["_id"]},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}},
    )

    # Keep room status in sync
    if new_status == "checkout":
        await rooms_col.update_one(
            {"id": booking["room_id"]}, {"$set": {"status": "avail"}}
        )
    elif new_status in ["confirmed", "checkedin"]:
        await rooms_col.update_one(
            {"id": booking["room_id"]}, {"$set": {"status": "occupied"}}
        )

    updated = await bookings_col.find_one({"_id": booking["_id"]})
    logger.info(f"Booking {booking_id} status → {new_status}")
    return _serialize_booking(updated)


async def cancel_booking(booking_id: str) -> dict:
    """Cancel and delete a booking. Frees the room back to 'avail'."""
    bookings_col = get_booking_collection()
    rooms_col = get_room_collection()

    booking = await _find_booking(bookings_col, booking_id)
    if not booking:
        raise NotFoundException(f"Booking {booking_id} not found")

    await bookings_col.delete_one({"_id": booking["_id"]})
    await rooms_col.update_one(
        {"id": booking["room_id"]}, {"$set": {"status": "avail"}}
    )
    logger.info(f"Booking cancelled and deleted: {booking_id}")
    return {"message": f"Booking {booking_id} cancelled and deleted successfully"}
