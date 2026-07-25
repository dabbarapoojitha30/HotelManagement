"""
Cleanup script — removes legacy user documents (role='user', old email-based accounts)
and drops stale indexes so the new (name, role) unique index can be created cleanly.

Run ONCE from the backend directory:
    python cleanup_legacy_users.py
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = "mongodb://localhost:27017"
DB_NAME   = "vvresidency"

async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    users = db["users"]

    # Show current users
    print("=== Users BEFORE cleanup ===")
    async for u in users.find():
        print(f"  name={u.get('name')!r:20} role={u.get('role')!r:10} email={u.get('email')!r}")

    # Delete any user whose role is not 'manager' or 'owner'
    result = await users.delete_many({"role": {"$nin": ["manager", "owner"]}})
    print(f"\nDeleted {result.deleted_count} legacy user(s) with unsupported roles.")

    # Drop the old single-field indexes if still present
    for idx in ("idx_users_email_unique", "idx_users_name_unique"):
        try:
            await users.drop_index(idx)
            print(f"Dropped index: {idx}")
        except Exception as e:
            print(f"Index {idx!r} not found (skipped): {e}")

    # Create the correct compound unique index
    try:
        await users.create_index(
            [("name", 1), ("role", 1)],
            unique=True,
            name="idx_users_name_role_unique",
        )
        print("Created index: idx_users_name_role_unique")
    except Exception as e:
        print(f"Index already exists or error: {e}")

    # Show remaining users
    print("\n=== Users AFTER cleanup ===")
    count = 0
    async for u in users.find():
        count += 1
        print(f"  name={u.get('name')!r:20} role={u.get('role')!r}")
    if count == 0:
        print("  (no users — database is clean, ready for fresh signups)")

    client.close()
    print("\nDone.")

asyncio.run(main())
