
import asyncio
from datetime import datetime, timedelta, timezone, time
from zoneinfo import ZoneInfo

from pymongo import AsyncMongoClient

from app.core.config import settings


DOCTORS = [
    {
        "slug": "ananya-sharma",
        "name": "Dr. Ananya Sharma",
        "specialty": "Cardiology",
        "experience_years": 12,
        "bio": "Specialist in heart health and cardiovascular care.",
        "active": True,
    },
    {
        "slug": "rahul-mehta",
        "name": "Dr. Rahul Mehta",
        "specialty": "Dermatology",
        "experience_years": 8,
        "bio": "Specialist in skin, hair, and general dermatology.",
        "active": True,
    },
    {
        "slug": "priya-kapoor",
        "name": "Dr. Priya Kapoor",
        "specialty": "Pediatrics",
        "experience_years": 10,
        "bio": "Specialist in child health and pediatric care.",
        "active": True,
    },
]


async def seed_database():
    client = AsyncMongoClient(settings.MONGODB_URI)

    try:
        await client.admin.command("ping")
        db = client[settings.MONGODB_DB_NAME]

        doctors_collection = db["doctors"]
        slots_collection = db["slots"]

        await doctors_collection.create_index("slug", unique=True)
        await slots_collection.create_index(
            [("doctor_id", 1), ("starts_at", 1)],
            unique=True,
        )

        doctor_count = 0
        slot_count = 0

        for doctor_data in DOCTORS:
            await doctors_collection.update_one(
                {"slug": doctor_data["slug"]},
                {"$setOnInsert": doctor_data},
                upsert=True,
            )

            doctor = await doctors_collection.find_one(
                {"slug": doctor_data["slug"]}
            )

            doctor_count += 1

            # Generate slots for the next three days in Indian Standard Time.
            india_tz = ZoneInfo("Asia/Kolkata")

            for day_offset in range(1, 4):
                slot_date = (
                    datetime.now(india_tz).date()
                    + timedelta(days=day_offset)
                )

                for hour in (10, 12, 15):
                    local_start = datetime.combine(
                        slot_date,
                        time(hour=hour, minute=0),
                        tzinfo=india_tz,
                    )

                    slot_data = {
                        "doctor_id": doctor["_id"],
                        "starts_at": local_start.astimezone(timezone.utc),
                        "status": "available",
                    }

                    result = await slots_collection.update_one(
                        {
                            "doctor_id": doctor["_id"],
                            "starts_at": slot_data["starts_at"],
                        },
                        {"$setOnInsert": slot_data},
                        upsert=True,
                    )

                    if result.upserted_id:
                        slot_count += 1

        print(f"Seed completed. Doctors checked: {doctor_count}")
        print(f"New slots created: {slot_count}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(seed_database())
