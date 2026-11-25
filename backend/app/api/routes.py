from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from app.services.appointment_service import (book_appointment, cancel_appointment, normalize_phone)

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


class BookingRequest(BaseModel):
    patient_name: str = Field(min_length=2, max_length=100)
    phone_number: str = Field(min_length=7, max_length=20)
    doctor_id: str
    slot_id: str


class CancellationRequest(BaseModel):
    phone_number: str = Field(min_length=7, max_length=20)


@router.post("/appointments")
async def create_appointment(payload: BookingRequest, request: Request):
    db = request.app.state.mongodb

    result = await book_appointment(
        db=db,
        patient_name=payload.patient_name,
        phone_number=payload.phone_number,
        doctor_id=payload.doctor_id,
        slot_id=payload.slot_id,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@router.get("/appointments")
async def get_appointments(
    request: Request,
    # A caller (or the voice agent) can still filter by phone.
    phone_number: str | None = Query(default=None, max_length=20),
):
    db = request.app.state.mongodb

    query: dict = {}

    if phone_number:
        normalized = normalize_phone(phone_number)

        if not (10 <= len(normalized) <= 15):
            raise HTTPException(status_code=400, detail="Invalid phone number")

        query["phone_number"] = normalized

    appointments = await db["appointments"].find(query).sort("created_at", -1).to_list(length=100)

    return [
        {
            "id": str(item["_id"]),
            "patient_name": item.get("patient_name", ""),
            "phone_number": item.get("phone_number", ""),
            "doctor_name": item.get("doctor_name", "Unknown doctor"),
            "specialty": item.get("specialty", ""),
            "starts_at": item["starts_at"].isoformat(),
            "status": item.get("status", "booked"),
        }
        for item in appointments
    ]


@router.post("/appointments/{appointment_id}/cancel")
async def cancel_existing_appointment(
    appointment_id: str,
    payload: CancellationRequest,
    request: Request,
):
    db = request.app.state.mongodb

    result = await cancel_appointment(
        db=db,
        phone_number=payload.phone_number,
        appointment_id=appointment_id,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return result