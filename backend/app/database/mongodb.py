"""
MongoDB connection management, collection accessors, and index creation.
Migrated from app/database.py with added connection timeout handling.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from app.config.settings import settings
import logging

logger = logging.getLogger("VVResidencyDB")


class Database:
    """
    True Singleton container for the AsyncIOMotorClient and database handle.
    Guarantees only one instance and connection pool exist across the entire runtime.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client: AsyncIOMotorClient = None
            cls._instance.db = None
        return cls._instance

    @property
    def is_connected(self) -> bool:
        return self.client is not None and self.db is not None


db_helper = Database()


def get_database():
    """
    Return the active singleton database handle.
    Raises RuntimeError if accessed before connection is established.
    """
    if not db_helper.is_connected:
        raise RuntimeError("Database is not connected. Call connect_to_mongo() first.")
    return db_helper.db


async def connect_to_mongo():
    """
    Establish or retrieve the singleton connection to MongoDB with timeout configuration.
    Idempotent: If already connected, returns existing handle without recreating clients.
    Called during FastAPI lifespan startup.
    """
    if db_helper.is_connected:
        logger.debug("MongoDB client already connected (reusing singleton).")
        return db_helper.db

    try:
        db_helper.client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=20000,
            socketTimeoutMS=30000,
            maxPoolSize=50,
            minPoolSize=0,
            maxIdleTimeMS=45000,
        )
        db_helper.db = db_helper.client[settings.DATABASE_NAME]
        # Verify connectivity by pinging the server
        await db_helper.client.admin.command("ping")
        logger.info(f"Connected to MongoDB (singleton): {settings.MONGODB_URL} -> {settings.DATABASE_NAME}")
        return db_helper.db
    except Exception as e:
        db_helper.client = None
        db_helper.db = None
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


async def close_mongo_connection():
    """Close the MongoDB singleton connection and reset handles."""
    if db_helper.client:
        db_helper.client.close()
        db_helper.client = None
        db_helper.db = None
        logger.info("Closed MongoDB singleton connection.")


# ── Collection helpers ──────────────────────────────────────────────

def get_user_collection():
    """Return the singleton 'users' collection handle."""
    return get_database()["users"]


def get_room_collection():
    """Return the singleton 'rooms' collection handle."""
    return get_database()["rooms"]


def get_booking_collection():
    """Return the singleton 'bookings' collection handle."""
    return get_database()["bookings"]


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
        # Unique sparse index on bill_seq for auto-incrementing bill numbers
        await bookings_col.create_index("bill_seq", unique=True, sparse=True, name="idx_bookings_bill_seq_unique")
        # Non-unique indexes for common query patterns
        await bookings_col.create_index("room_id", name="idx_bookings_room_id")
        await bookings_col.create_index("status", name="idx_bookings_status")
        await bookings_col.create_index("guest_email", name="idx_bookings_guest_email")
        # Compound index for date range overlap queries used in /search
        await bookings_col.create_index(
            [("checkin", 1), ("checkout", 1)],
            name="idx_bookings_dates",
        )

        # Clean up legacy 'counters' collection if it exists
        try:
            await db_helper.db.drop_collection("counters")
        except Exception:
            pass

        logger.info("MongoDB indexes created successfully.")
    except Exception as e:
        # Indexes may already exist — that's fine, log and continue
        logger.warning(f"Index creation note: {e}")
