"""
Booking service — business logic for booking CRUD and status transitions.
Rooms with status 'avail' or 'reserved' can be booked.
Status flow: confirmed → checkedin → checkout
"""
from datetime import datetime, timezone
from typing import List, Optional
import uuid
import logging

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.database import get_booking_collection, get_room_collection
from app.core.exceptions import NotFoundException, BadRequestException
from app.services.room_service import sync_room_statuses_and_bookings
from app.utils.timezone import (
    get_ist_now,
    to_ist,
    parse_ist_datetime,
    extract_booking_datetimes,
)

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
    doc.setdefault("bill_seq", None)
    doc.setdefault("checkin_time", "12:00")
    doc.setdefault("checkout_time", "11:00")
    doc.setdefault("checkin_datetime", None)
    doc.setdefault("checkout_datetime", None)
    doc.setdefault("aadhaar_file", None)
    doc.setdefault("photo_file", None)
    return doc


async def get_next_bill_seq(bookings_col) -> int:
    """
    Determine the next sequential bill number directly from the bookings collection.
    Queries the highest numeric bill_seq (or extracts max from bill_number if bill_seq not yet set).
    """
    latest = await bookings_col.find(
        {"bill_seq": {"$type": "number"}},
        {"bill_seq": 1}
    ).sort("bill_seq", -1).limit(1).to_list(1)

    if latest and "bill_seq" in latest[0]:
        try:
            return int(latest[0]["bill_seq"]) + 1
        except (ValueError, TypeError):
            pass

    # Fallback for existing bookings that have a numeric bill_number string (e.g. "005")
    cursor = bookings_col.find(
        {"bill_number": {"$regex": r"^\d+$"}},
        {"bill_number": 1}
    ).sort("bill_number", -1).limit(1)
    async for b in cursor:
        try:
            return int(b["bill_number"]) + 1
        except (ValueError, TypeError):
            pass

    return 1


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
    Create a new booking with checkin/checkout date and time in IST.
    - Rooms with status 'avail' or 'reserved' can be booked.
    - Calculates amount = nights × room price.
    - Sets booking status = 'confirmed', and updates room status dynamically via IST sync.
    """
    rooms_col = get_room_collection()
    bookings_col = get_booking_collection()

    now_ist = get_ist_now()
    await sync_room_statuses_and_bookings(now_ist)

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

    # Validate and parse date + time in IST
    ci_time = (booking_data.get("checkin_time") or "12:00").strip()
    co_time = (booking_data.get("checkout_time") or "11:00").strip()

    try:
        ci_dt = parse_ist_datetime(booking_data["checkin"], ci_time)
        co_dt = parse_ist_datetime(booking_data["checkout"], co_time)
    except Exception as e:
        raise BadRequestException(f"Invalid check-in/check-out date or time: {e}")

    if co_dt <= ci_dt:
        raise BadRequestException("Check-out date/time must be strictly after check-in date/time")

    if co_dt <= now_ist:
        raise BadRequestException("Check-out date/time cannot be in the past")

    # Double-booking guard: ensure no active booking overlaps with this requested period
    overlap_cursor = bookings_col.find({
        "room_id": room["id"],
        "status": {"$in": ["confirmed", "checkedin", "pending"]},
    })
    async for b in overlap_cursor:
        b_ci, b_co = extract_booking_datetimes(b)
        if b_ci < co_dt and b_co > ci_dt:
            ci_str = b.get("checkin", "")
            ci_t = b.get("checkin_time", "12:00")
            co_str = b.get("checkout", "")
            co_t = b.get("checkout_time", "11:00")
            raise BadRequestException(
                f"Room {room['id']} is already booked from {ci_str} {ci_t} to {co_str} {co_t}. "
                "Please choose another room or time range."
            )

    nights = (co_dt.date() - ci_dt.date()).days
    if nights <= 0:
        nights = 1  # Minimum 1 night billing

    custom_amount = booking_data.get("amount")
    if custom_amount is not None and float(custom_amount) >= 0:
        amount = float(custom_amount)
    else:
        amount = nights * room["price"]

    # Generate unique booking ID
    for _ in range(20):
        bk_id = _generate_booking_id()
        if not await bookings_col.find_one({"booking_id": bk_id}):
            break

    # Retry loop to handle concurrent collisions safely using unique index on bill_seq
    max_retries = 5
    for attempt in range(max_retries):
        bill_seq = await get_next_bill_seq(bookings_col)
        bill_no = str(bill_seq).zfill(3)

        booking_dict = {
            "booking_id": bk_id,
            "bill_number": bill_no,
            "bill_seq": bill_seq,
            "guest_name": booking_data["guest_name"],
            "guest_email": booking_data.get("guest_email") or "",
            "guest_phone": booking_data["guest_phone"],
            "room_id": room["id"],
            "room_name": room.get("name") or room.get("floor") or f"Room {room['id']}",
            "checkin": booking_data["checkin"],
            "checkin_time": ci_time,
            "checkout": booking_data["checkout"],
            "checkout_time": co_time,
            "checkin_datetime": ci_dt,
            "checkout_datetime": co_dt,
            "amount": amount,
            "guests_count": booking_data.get("guests_count") or 2,
            "special_requests": booking_data.get("special_requests") or "",
            "aadhaar_file": booking_data.get("aadhaar_file"),
            "photo_file": booking_data.get("photo_file"),
            "status": "confirmed",
            "created_at": now_ist,
        }

        try:
            result = await bookings_col.insert_one(booking_dict)
            booking_dict["id"] = str(result.inserted_id)
            break
        except DuplicateKeyError:
            if attempt == max_retries - 1:
                raise BadRequestException("Could not generate a unique bill sequence. Please try again.")
            logger.warning(f"Bill seq {bill_seq} collision detected. Retrying ({attempt + 1}/{max_retries})...")
            continue

    # Automatically derive and set correct room status in IST
    await sync_room_statuses_and_bookings(now_ist)
    logger.info(f"Booking created: {bk_id} for room {room['id']} (Check-in: {ci_dt}, Check-out: {co_dt})")

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

    now_ist = get_ist_now()
    await bookings_col.update_one(
        {"_id": booking["_id"]},
        {"$set": {"status": new_status, "updated_at": now_ist}},
    )

    # Keep room status in sync
    if new_status == "checkout":
        await rooms_col.update_one(
            {"id": booking["room_id"]}, {"$set": {"status": "avail", "updated_at": now_ist}}
        )
    elif new_status in ["confirmed", "checkedin"]:
        await rooms_col.update_one(
            {"id": booking["room_id"]}, {"$set": {"status": "occupied", "updated_at": now_ist}}
        )

    # Resync all room statuses
    await sync_room_statuses_and_bookings(now_ist)

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

    now_ist = get_ist_now()
    await bookings_col.delete_one({"_id": booking["_id"]})
    await rooms_col.update_one(
        {"id": booking["room_id"]}, {"$set": {"status": "avail", "updated_at": now_ist}}
    )
    # Resync remaining bookings to guarantee room status matches active schedule
    await sync_room_statuses_and_bookings(now_ist)
    logger.info(f"Booking cancelled and deleted: {booking_id}")
    return {"message": f"Booking {booking_id} cancelled and deleted successfully"}

