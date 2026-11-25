import re
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
from bson import ObjectId
from pymongo import ReturnDocument

INDIA_TZ = ZoneInfo("Asia/Kolkata")

def normalize_phone(phone) -> str:
    """Keep digits only and drop the Indian country code / leading zero."""
    digits = "".join(c for c in str(phone) if c.isdigit())

    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    return digits


async def check_doctor_availability(
    db,
    specialty: str | None = None,
    doctor_name: str | None = None,
    slot_date: date | None = None,
):
    doctor_query = {"active": True}

    if specialty:
        doctor_query["specialty"] = {
            "$regex": re.escape(specialty.strip()),
            "$options": "i",
        }

    if doctor_name:
        cleaned_name = re.sub(r"^\s*dr\.?\s*", "", doctor_name, flags=re.IGNORECASE)
        doctor_query["name"] = {
            "$regex": re.escape(cleaned_name.strip()),
            "$options": "i",
        }

    doctors = await db["doctors"].find(doctor_query).to_list(length=100)

    starts_filter = {"$gt": datetime.now(timezone.utc)}

    # Convert the requested Indian calendar date into UTC boundaries.
    if slot_date:
        start_local = datetime.combine(slot_date, time.min, tzinfo=INDIA_TZ)
        end_local = datetime.combine(slot_date, time.max, tzinfo=INDIA_TZ)
        starts_filter["$gte"] = start_local.astimezone(timezone.utc)
        starts_filter["$lte"] = end_local.astimezone(timezone.utc)

    results = []

    for doctor in doctors:
        slots = await db["slots"].find({
            "doctor_id": doctor["_id"],
            "status": "available",
            "starts_at": starts_filter,
        }).sort("starts_at", 1).to_list(length=20)

        results.append({
            "doctor_id": str(doctor["_id"]),
            "doctor_name": doctor["name"],
            "specialty": doctor["specialty"],
            "available_slots": [
                {
                    "slot_id": str(slot["_id"]),
                    "starts_at": slot["starts_at"].isoformat(),
                }
                for slot in slots
            ],
        })

    return results


async def book_appointment(
    db,
    patient_name: str,
    phone_number: str,
    doctor_id: str,
    slot_id: str,
):
    phone_number = normalize_phone(phone_number)

    if not (10 <= len(phone_number) <= 15):
        return {"success": False, "message": "Invalid phone number"}

    if not ObjectId.is_valid(doctor_id):
        return {"success": False, "message": "Invalid doctor ID"}

    if not ObjectId.is_valid(slot_id):
        return {"success": False, "message": "Invalid slot ID"}

    doctor = await db["doctors"].find_one({"_id": ObjectId(doctor_id), "active": True})

    if not doctor:
        return {"success": False, "message": "Doctor not found"}

    # Atomically claim the slot only if it is still available.
    slot = await db["slots"].find_one_and_update(
        {
            "_id": ObjectId(slot_id),
            "doctor_id": doctor["_id"],
            "status": "available",
            "starts_at": {"$gt": datetime.now(timezone.utc)},
        },
        {
            "$set": {
                "status": "booked",
                "updated_at": datetime.now(timezone.utc),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    if not slot:
        return {
            "success": False,
            "message": "This slot is no longer available. Please choose another slot.",
        }

    appointment = {
        "patient_name": patient_name,
        "phone_number": phone_number,
        "doctor_id": doctor["_id"],
        "doctor_name": doctor["name"],
        "specialty": doctor["specialty"],
        "slot_id": slot["_id"],
        "starts_at": slot["starts_at"],
        "status": "booked",
        "created_at": datetime.now(timezone.utc),
    }

    try:
        result = await db["appointments"].insert_one(appointment)
    except Exception:
        # Release the slot if appointment creation fails.
        await db["slots"].update_one(
            {
                "_id": slot["_id"],
                "status": "booked",
            },
            {
                "$set": {"status": "available"},
                "$unset": {"updated_at": ""},
            },
        )
        raise

    return {
        "success": True,
        "message": "Appointment booked successfully",
        "appointment_id": str(result.inserted_id),
        "patient_name": patient_name,
        "doctor_name": doctor["name"],
        "specialty": doctor["specialty"],
        "starts_at": slot["starts_at"].isoformat(),
        "phone_number": phone_number,
    }


async def cancel_appointment(
    db,
    phone_number: str,
    appointment_id: str,
):
    phone_number = normalize_phone(phone_number)

    if not ObjectId.is_valid(appointment_id):
        return {"success": False, "message": "Invalid appointment ID"}

    appointment = await db["appointments"].find_one_and_update(
        {
            "_id": ObjectId(appointment_id),
            "phone_number": phone_number,
            "status": "booked",
        },
        {
            "$set": {
                "status": "cancelled",
                "cancelled_at": datetime.now(timezone.utc),
            }
        },
        return_document=ReturnDocument.AFTER,
    )

    if not appointment:
        return {
            "success": False,
            "message": "No active appointment found for this phone number and appointment ID.",
        }

    await db["slots"].update_one(
        {
            "_id": appointment["slot_id"],
            "status": "booked",
        },
        {
            "$set": {"status": "available"},
            "$unset": {"updated_at": ""},
        },
    )

    return {
        "success": True,
        "message": "Appointment cancelled successfully",
        "appointment_id": str(appointment["_id"]),
        "doctor_name": appointment["doctor_name"],
        "starts_at": appointment["starts_at"].isoformat(),
    }