"""
Database package — re-exports from mongodb.py for backward compatibility.
All existing imports like `from app.database import get_room_collection` continue to work.
"""
from app.database.mongodb import (
    get_database,
    connect_to_mongo,
    close_mongo_connection,
    get_user_collection,
    get_room_collection,
    get_booking_collection,
    create_indexes,
)

__all__ = [
    "get_database",
    "connect_to_mongo",
    "close_mongo_connection",
    "get_user_collection",
    "get_room_collection",
    "get_booking_collection",
    "create_indexes",
]
