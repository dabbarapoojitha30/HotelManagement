"""
Seed VV Residency rooms: 101,102,103,201,202,203,301
Run: python seed_rooms.py
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

ROOMS = [
    {"id": "101", "name": "Standard Room", "floor": "1st Floor", "type": "Standard", "price": 1200, "status": "avail", "cls": "r1", "feats": [], "fcls": []},
    {"id": "102", "name": "Standard Room", "floor": "1st Floor", "type": "Standard", "price": 1200, "status": "avail", "cls": "r1", "feats": [], "fcls": []},
    {"id": "103", "name": "Standard Room", "floor": "1st Floor", "type": "Standard", "price": 1200, "status": "avail", "cls": "r1", "feats": [], "fcls": []},
    {"id": "201", "name": "Deluxe Room",   "floor": "2nd Floor", "type": "Deluxe",   "price": 1800, "status": "avail", "cls": "r2", "feats": [], "fcls": []},
    {"id": "202", "name": "Deluxe Room",   "floor": "2nd Floor", "type": "Deluxe",   "price": 1800, "status": "avail", "cls": "r2", "feats": [], "fcls": []},
    {"id": "203", "name": "Deluxe Room",   "floor": "2nd Floor", "type": "Deluxe",   "price": 1800, "status": "avail", "cls": "r2", "feats": [], "fcls": []},
    {"id": "301", "name": "Suite",          "floor": "3rd Floor", "type": "Suite",    "price": 3000, "status": "avail", "cls": "r3", "feats": [], "fcls": []},
]

async def seed():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["vvresidency"]
    rooms_col = db["rooms"]

    # Remove all existing rooms
    deleted = await rooms_col.delete_many({})
    print(f"Deleted {deleted.deleted_count} existing rooms.")

    # Insert new rooms
    result = await rooms_col.insert_many(ROOMS)
    print(f"Inserted {len(result.inserted_ids)} rooms: {[r['id'] for r in ROOMS]}")

    client.close()

asyncio.run(seed())
