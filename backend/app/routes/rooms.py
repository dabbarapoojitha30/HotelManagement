"""
Room routes — CRUD operations and availability search.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from app.schemas.room import RoomCreate, RoomUpdate, RoomStatusUpdate, RoomResponse
from app.auth.dependencies import require_roles
from app.services import room_service
from app.utils.timezone import get_ist_now

router = APIRouter(prefix="/rooms", tags=["Rooms"])


@router.get("/search", response_model=List[RoomResponse])
async def search_rooms(
    checkin: Optional[str] = Query(None, description="Check-in date YYYY-MM-DD"),
    checkout: Optional[str] = Query(None, description="Check-out date YYYY-MM-DD"),
    checkin_time: Optional[str] = Query("12:00", description="Check-in time HH:MM"),
    checkout_time: Optional[str] = Query("11:00", description="Check-out time HH:MM"),
    room_type: Optional[str] = Query(None, description="Room type: Standard, Deluxe, Suite"),
    guests: Optional[int] = Query(None, description="Number of guests"),
):
    """
    Search available rooms by date/time range and type in IST.
    Called by the frontend 'Search Rooms' button.
    Returns only rooms with status='avail' that are not booked in the given range.
    """
    await room_service.sync_room_statuses_and_bookings(get_ist_now())
    return await room_service.search_available_rooms(
        checkin=checkin,
        checkout=checkout,
        room_type=room_type,
        checkin_time=checkin_time,
        checkout_time=checkout_time,
    )


@router.get("", response_model=List[RoomResponse])
async def get_rooms(
    status_filter: Optional[str] = Query(None, alias="status_filter"),
):
    """
    Get all rooms with optional status/type filter.
    status_filter: 'all' | 'avail' | 'booked' | 'maint' | 'suite'
    """
    await room_service.sync_room_statuses_and_bookings(get_ist_now())
    return await room_service.get_all_rooms(status_filter=status_filter)


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(room_id: str):
    """Get a single room by its room number/ID (e.g. '101')."""
    await room_service.sync_room_statuses_and_bookings(get_ist_now())
    return await room_service.get_room_by_id(room_id)


@router.post("", response_model=RoomResponse, status_code=201)
async def create_room(
    room_data: RoomCreate,
    current_user=Depends(require_roles(["owner", "manager"])),
):
    """Create a new room. Requires admin or staff role."""
    return await room_service.create_room(room_data.model_dump())


@router.put("/{room_id}", response_model=RoomResponse)
async def update_room(
    room_id: str,
    room_data: RoomUpdate,
    current_user=Depends(require_roles(["owner", "manager"])),
):
    """Update a room's properties. Requires admin or staff role."""
    return await room_service.update_room(room_id, room_data.model_dump())


@router.patch("/{room_id}/status", response_model=RoomResponse)
async def update_room_status(
    room_id: str,
    status_data: RoomStatusUpdate,
    current_user=Depends(require_roles(["owner", "manager"])),
):
    """Quickly update only a room's status. Requires admin or staff role."""
    return await room_service.update_room_status(room_id, status_data.status.lower())


@router.delete("/{room_id}")
async def delete_room(
    room_id: str,
    current_user=Depends(require_roles(["owner", "manager"])),
):
    """Delete a room by room ID. Requires admin or staff role."""
    return await room_service.delete_room(room_id)
