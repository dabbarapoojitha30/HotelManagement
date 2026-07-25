"""
MongoDB connection management, collection accessors, and index creation.
Migrated from app/database.py with added connection timeout handling.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from app.config.settings import settings
import logging

logger = logging.getLogger("VVResidencyDB")


class Database:
    """Singleton-style container for the Motor client and database handle."""
    client: AsyncIOMotorClient = None
    db = None


db_helper = Database()


def get_database():
    """Return the active database handle."""
    return db_helper.db


async def connect_to_mongo():
    """
    Establish connection to MongoDB with timeout configuration.
    Called during FastAPI lifespan startup.
    """
    try:
        db_helper.client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=5000,   # Fail fast if server unreachable
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
        )
        db_helper.db = db_helper.client[settings.DATABASE_NAME]
        # Verify connectivity by pinging the server
        await db_helper.client.admin.command("ping")
        logger.info(f"Connected to MongoDB: {settings.MONGODB_URL} -> {settings.DATABASE_NAME}")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


async def close_mongo_connection():
    """Close the MongoDB client connection. Called during FastAPI lifespan shutdown."""
    if db_helper.client:
        db_helper.client.close()
        logger.info("Closed MongoDB connection.")


# ── Collection helpers ──────────────────────────────────────────────

def get_user_collection():
    """Return the 'users' collection handle."""
    return db_helper.db["users"]


def get_room_collection():
    """Return the 'rooms' collection handle."""
    return db_helper.db["rooms"]


def get_booking_collection():
    """Return the 'bookings' collection handle."""
    return db_helper.db["bookings"]


def get_counter_collection():
    """Return the 'counters' collection handle (used for sequential bill numbers)."""
    return db_helper.db["counters"]


# ── Index creation ──────────────────────────────────────────────────

async def create_indexes():
    """
    Create MongoDB indexes for performance and uniqueness guarantees.
    Called once at application startup after DB connection is established.
    All calls are idempotent — safe to run on every startup.
    """
    try:
        users_col = get_user_collection()
        rooms_col = get_room_collection()
        bookings_col = get_booking_collection()

        # Users: drop legacy indexes if they exist (migration safety)
        for old_idx in ("idx_users_email_unique", "idx_users_name_unique"):
            try:
                await users_col.drop_index(old_idx)
            except Exception:
                pass

        # Users: compound unique index on (name, role) so the same name can register
        # as both 'manager' and 'owner' but cannot register the same role twice.
        await users_col.create_index(
            [("name", 1), ("role", 1)],
            unique=True,
            name="idx_users_name_role_unique",
        )

        # Rooms: unique index on room id (e.g. "101") for fast lookups
        await rooms_col.create_index("id", unique=True, name="idx_rooms_id_unique")
        # Non-unique index on status for fast filter queries
        await rooms_col.create_index("status", name="idx_rooms_status")
        # Index on type for suite/category searches
        await rooms_col.create_index("type", name="idx_rooms_type")

        # Bookings: unique index on booking_id (BK-XXXX)
        await bookings_col.create_index("booking_id", unique=True, name="idx_bookings_booking_id_unique")
        # Non-unique indexes for common query patterns
        await bookings_col.create_index("room_id", name="idx_bookings_room_id")
        await bookings_col.create_index("status", name="idx_bookings_status")
        await bookings_col.create_index("guest_email", name="idx_bookings_guest_email")
        # Compound index for date range overlap queries used in /search
        await bookings_col.create_index(
            [("checkin", 1), ("checkout", 1)],
            name="idx_bookings_dates",
        )

        # Counters: unique index on counter name
        counters_col = get_counter_collection()
        await counters_col.create_index("name", unique=True, name="idx_counters_name_unique")
        # Seed bill_number counter if not present
        await counters_col.update_one(
            {"name": "bill_number"},
            {"$setOnInsert": {"name": "bill_number", "seq": 0}},
            upsert=True,
        )

        logger.info("MongoDB indexes created successfully.")
    except Exception as e:
        # Indexes may already exist — that's fine, log and continue
        logger.warning(f"Index creation note: {e}")
