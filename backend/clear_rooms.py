import asyncio
from app.database import connect_to_mongo, close_mongo_connection, get_room_collection, get_booking_collection

async def clear_rooms():
    await connect_to_mongo()
    db_rooms = get_room_collection()
    db_bookings = get_booking_collection()
    await db_rooms.delete_many({})
    await db_bookings.delete_many({})
    print("Rooms and bookings cleared!")
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(clear_rooms())
