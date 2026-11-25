
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api", tags=["Appointments"])


@router.get("/doctors")
async def get_doctors(request: Request):
    db = request.app.state.mongodb

    doctors = await db["doctors"].find({"active": True}).to_list(length=100)

    return [
        {
            "id": str(doctor["_id"]),
            "name": doctor["name"],
            "specialty": doctor["specialty"],
            "experience_years": doctor["experience_years"],
            "bio": doctor["bio"],
        }
        for doctor in doctors
    ]


@router.get("/slots")
async def get_slots(
    request: Request,
    doctor_id: str | None = None,
    slot_date: date | None = Query(default=None, alias="date"),
):
    db = request.app.state.mongodb

    query = {"status": "available"}

    if doctor_id:
        if not ObjectId.is_valid(doctor_id):
            raise HTTPException(status_code=400, detail="Invalid doctor ID")
        query["doctor_id"] = ObjectId(doctor_id)

    # Convert the requested Indian calendar date into UTC boundaries.
    if slot_date:
        india_tz = ZoneInfo("Asia/Kolkata")

        start_local = datetime.combine(slot_date, time.min, tzinfo=india_tz)
        end_local = datetime.combine(slot_date, time.max, tzinfo=india_tz)

        query["starts_at"] = {
            "$gte": start_local.astimezone(timezone.utc),
            "$lte": end_local.astimezone(timezone.utc),
        }

    slots = await db["slots"].find(query).sort("starts_at", 1).to_list(length=200)

    # Get doctor names for the slots.
    doctor_ids = list({slot["doctor_id"] for slot in slots})

    doctors = await db["doctors"].find(
        {"_id": {"$in": doctor_ids}}
    ).to_list(length=100)

    doctor_names = {
        doctor["_id"]: doctor["name"]
        for doctor in doctors
    }

    return [
        {
            "id": str(slot["_id"]),
            "doctor_id": str(slot["doctor_id"]),
            "doctor_name": doctor_names.get(slot["doctor_id"], "Unknown doctor"),
            "starts_at": slot["starts_at"].isoformat(),
            "status": slot["status"],
        }
        for slot in slots
    ]
