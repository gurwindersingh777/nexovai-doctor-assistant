from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from bson import ObjectId
from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from app.services.appointment_service import (
    check_doctor_availability,
    book_appointment as save_appointment,
    cancel_appointment as remove_appointment,
)

def _format_appointment_time(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    india_time = value.astimezone(ZoneInfo("Asia/Kolkata"))

    return india_time.strftime("%A, %d %B %Y at %I:%M %p IST")


def _get_resources(params):
    resources = params.app_resources or params.pipeline_worker.app_resources
    if not resources:
        raise RuntimeError("Voice session resources are unavailable")
    return resources


def _latest_user_turn(params):
    messages = params.context.messages

    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]

        if isinstance(message, dict):
            role = message.get("role")
            content = message.get("content", "")
        else:
            role = getattr(message, "role", None)
            content = getattr(message, "content", "")

        if role != "user":
            continue

        if isinstance(content, list):
            content = " ".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict)
            )

        return index, str(content).strip().lower()

    return -1, ""


def _is_explicit_yes(text):
    normalized = text.strip().rstrip(".!?").strip()

    return normalized in {
        "yes",
        "yes please",
        "yeah",
        "yep",
        "correct",
        "that's correct",
        "that is correct",
        "i confirm",
        "i agree",
        "confirm",
        "go ahead",
        "please do",
    }


def _normalize_phone(phone):
    return "".join(character for character in str(phone) if character.isdigit())


def _phone_readback(phone):
    return ", ".join(phone)


async def _finish(params, result):
    await params.result_callback(result)


async def check_availability_handler(params):
    try:
        args = params.arguments
        resources = _get_resources(params)

        result = await check_doctor_availability(
            db=resources["db"],
            specialty=args.get("specialty"),
            doctor_name=args.get("doctor_name"),
        )

        for doctor in result:
            for slot in doctor["available_slots"]:
                slot["display_time"] = _format_appointment_time(
                    slot["starts_at"]
                )

        await _finish(params, {
            "success": True,
            "doctors": result,
        })

    except Exception as exc:
        await _finish(params, {
            "success": False,
            "message": str(exc),
        })


async def book_appointment_handler(params):
    try:
        args = params.arguments
        resources = _get_resources(params)
        db = resources["db"]
        state = resources["session_state"]

        action = args.get("action")
        pending = state.get("pending_booking")

        if action == "prepare":
            patient_name = str(args.get("patient_name", "")).strip()
            phone = _normalize_phone(args.get("phone_number", ""))

            doctor_id = str(args.get("doctor_id", ""))
            slot_id = str(args.get("slot_id", ""))

            if not patient_name or not (10 <= len(phone) <= 15):
                await _finish(params, {
                    "success": False,
                    "message": "Please collect a valid patient name and phone number.",
                })
                return

            if not ObjectId.is_valid(doctor_id) or not ObjectId.is_valid(slot_id):
                await _finish(params, {
                    "success": False,
                    "message": "The doctor or slot ID is invalid. Check availability again.",
                })
                return

            doctor = await db["doctors"].find_one({
                "_id": ObjectId(doctor_id),
                "active": True,
            })

            slot = await db["slots"].find_one({
                "_id": ObjectId(slot_id),
                "doctor_id": ObjectId(doctor_id),
                "status": "available",
            })

            if not doctor or not slot:
                await _finish(params, {
                    "success": False,
                    "message": "That doctor or slot is no longer available. Check availability again.",
                })
                return

            prepared_turn, _ = _latest_user_turn(params)
            
            state["pending_booking"] = {
                "patient_name": patient_name,
                "phone_number": phone,
                "doctor_id": doctor_id,
                "slot_id": slot_id,
                "phone_verified": False,
                "phone_confirmed_turn": None,
                "prepared_turn": prepared_turn,
            }

            await _finish(params, {
                "success": True,
                "next_step": "confirm_phone",
                "message": (
                    "Read the patient's phone number digit by digit as "
                    f"{_phone_readback(phone)}. Ask the patient to confirm it. "
                    "Do not book yet."
                ),
            })
            return

        if not pending:
            await _finish(params, {
                "success": False,
                "message": "There is no pending booking. Start the booking process again.",
            })
            return

        if action == "confirm_phone":
            turn_index, user_text = _latest_user_turn(params)

            if (
                turn_index <= pending["prepared_turn"]
                or not _is_explicit_yes(user_text)
            ):
                await _finish(params, {
                    "success": False,
                    "message": "The patient has not explicitly confirmed the phone number in a separate response.",
                })
                return

            pending["phone_verified"] = True
            pending["phone_confirmed_turn"] = turn_index

            doctor = await db["doctors"].find_one({
                "_id": ObjectId(pending["doctor_id"]),
            })

            slot = await db["slots"].find_one({
                "_id": ObjectId(pending["slot_id"]),
                "doctor_id": ObjectId(pending["doctor_id"]),
                "status": "available",
            })

            if not doctor or not slot:
                state["pending_booking"] = None
                await _finish(params, {
                    "success": False,
                    "message": "The selected slot is no longer available. Please check availability again.",
                })
                return

            await _finish(params, {
                "success": True,
                "next_step": "confirm_booking",
                "doctor_name": doctor["name"],
                "specialty": doctor["specialty"],
                "appointment_time": _format_appointment_time(slot["starts_at"]),
                "message": (
                    "The phone number is confirmed. Read the doctor and "
                    "appointment time back to the patient and ask for explicit "
                    "booking confirmation. Do not book yet."
                ),
            })
            return

        if action == "confirm_booking":
            if not pending.get("phone_verified"):
                await _finish(params, {
                    "success": False,
                    "message": "The phone number must be confirmed first.",
                })
                return

            turn_index, user_text = _latest_user_turn(params)

            if (
                turn_index <= pending["phone_confirmed_turn"]
                or not _is_explicit_yes(user_text)
            ):
                await _finish(params, {
                    "success": False,
                    "message": "Wait for a separate, explicit patient confirmation of the appointment.",
                })
                return

            result = await save_appointment(
                db=db,
                patient_name=pending["patient_name"],
                phone_number=pending["phone_number"],
                doctor_id=pending["doctor_id"],
                slot_id=pending["slot_id"],
            )

            if result.get("success"):
                state["pending_booking"] = None

            if result.get("success"):
                result["display_time"] = _format_appointment_time(
                    result["starts_at"]
                )

            await _finish(params, result)
            return

        await _finish(params, {
            "success": False,
            "message": "Unknown booking action.",
        })

    except Exception as exc:
        await _finish(params, {
            "success": False,
            "message": str(exc),
        })


async def cancel_appointment_handler(params):
    try:
        args = params.arguments
        resources = _get_resources(params)
        db = resources["db"]
        state = resources["session_state"]

        action = args.get("action")
        pending = state.get("pending_cancel")

        if action == "prepare":
            phone = _normalize_phone(args.get("phone_number", ""))

            if not (10 <= len(phone) <= 15):
                await _finish(params, {
                    "success": False,
                    "message": "Please collect a valid phone number.",
                })
                return

            prepared_turn, _ = _latest_user_turn(params)

            state["pending_cancel"] = {
                "phone_number": phone,
                "phone_verified": False,
                "phone_confirmed_turn": None,
                "appointment_id": None,
                "selected_turn": None,
                "prepared_turn": prepared_turn,
            }

            await _finish(params, {
                "success": True,
                "next_step": "confirm_phone",
                "message": (
                    "Read the phone number digit by digit as "
                    f"{_phone_readback(phone)} and ask the patient to confirm it. "
                    "Do not cancel anything."
                ),
            })
            return

        if not pending:
            await _finish(params, {
                "success": False,
                "message": "There is no pending cancellation. Start again.",
            })
            return

        if action == "confirm_phone":
            turn_index, user_text = _latest_user_turn(params)

            if (
                turn_index <= pending["prepared_turn"]
                or not _is_explicit_yes(user_text)
            ):
                await _finish(params, {
                    "success": False,
                    "message": "The patient must explicitly confirm the phone number.",
                })
                return

            pending["phone_verified"] = True
            pending["phone_confirmed_turn"] = turn_index

            appointments = await db["appointments"].find({
                "phone_number": pending["phone_number"],
                "status": "booked",
            }).sort("starts_at", 1).to_list(length=20)

            if not appointments:
                state["pending_cancel"] = None
                await _finish(params, {
                    "success": False,
                    "message": "No active appointments were found for this phone number.",
                })
                return

            results = [
                {
                    "appointment_id": str(item["_id"]),
                    "doctor_name": item["doctor_name"],
                    "specialty": item.get("specialty"),
                    "starts_at": item["starts_at"].isoformat(),
                }
                for item in appointments
            ]

            await _finish(params, {
                "success": True,
                "next_step": "select_appointment",
                "appointments": results,
                "message": "Ask the patient which appointment they want to cancel. Do not cancel yet.",
            })
            return

        if action == "select":
            if not pending.get("phone_verified"):
                await _finish(params, {
                    "success": False,
                    "message": "Verify the phone number first.",
                })
                return

            turn_index, _ = _latest_user_turn(params)

            if turn_index <= pending["phone_confirmed_turn"]:
                await _finish(params, {
                    "success": False,
                    "message": "Wait for the patient to select an appointment.",
                })
                return

            appointment_id = str(args.get("appointment_id", ""))

            if not ObjectId.is_valid(appointment_id):
                await _finish(params, {
                    "success": False,
                    "message": "Invalid appointment ID.",
                })
                return

            appointment = await db["appointments"].find_one({
                "_id": ObjectId(appointment_id),
                "phone_number": pending["phone_number"],
                "status": "booked",
            })

            if not appointment:
                await _finish(params, {
                    "success": False,
                    "message": "That active appointment was not found for this phone number.",
                })
                return

            pending["appointment_id"] = appointment_id
            pending["selected_turn"] = turn_index

            await _finish(params, {
                "success": True,
                "next_step": "confirm_cancellation",
                "doctor_name": appointment["doctor_name"],
                "appointment_time": _format_appointment_time(appointment["starts_at"]),
                "message": (
                    "Read the selected appointment details back to the patient "
                    "and ask for explicit cancellation confirmation. Do not cancel yet."
                ),
            })
            return

        if action == "confirm_cancellation":
            if not pending.get("phone_verified") or not pending.get("appointment_id"):
                await _finish(params, {
                    "success": False,
                    "message": "Verify the phone number and select an appointment first.",
                })
                return

            turn_index, user_text = _latest_user_turn(params)

            if (
                turn_index <= pending["selected_turn"]
                or not _is_explicit_yes(user_text)
            ):
                await _finish(params, {
                    "success": False,
                    "message": "Wait for a separate, explicit confirmation to cancel this appointment.",
                })
                return

            result = await remove_appointment(
                db=db,
                phone_number=pending["phone_number"],
                appointment_id=pending["appointment_id"],
            )

            if result.get("success"):
                state["pending_cancel"] = None

            await _finish(params, result)
            return

        await _finish(params, {
            "success": False,
            "message": "Unknown cancellation action.",
        })

    except Exception as exc:
        await _finish(params, {
            "success": False,
            "message": str(exc),
        })


def build_voice_tools():
    return [
        FunctionSchema(
            name="check_doctor_availability",
            description=(
                "Find active doctors and their future available appointment slots. "
                "Use this before preparing a booking."
            ),
            properties={
                "specialty": {
                    "type": "string",
                    "description": "Optional medical specialty, such as Cardiology.",
                },
                "doctor_name": {
                    "type": "string",
                    "description": "Optional doctor name.",
                },
            },
            required=[],
            handler=check_availability_handler,
        ),
        FunctionSchema(
            name="book_appointment",
            description=(
                "Manage a staged appointment booking. First call action=prepare "
                "with patient_name, phone_number, doctor_id and slot_id. Then call "
                "action=confirm_phone only after the patient confirms the read-back. "
                "Finally call action=confirm_booking only after the patient separately "
                "confirms the doctor and appointment time."
            ),
            properties={
                "action": {
                    "type": "string",
                    "enum": ["prepare", "confirm_phone", "confirm_booking"],
                },
                "patient_name": {"type": "string"},
                "phone_number": {"type": "string"},
                "doctor_id": {"type": "string"},
                "slot_id": {"type": "string"},
            },
            required=["action"],
            handler=book_appointment_handler,
        ),
        FunctionSchema(
            name="cancel_appointment",
            description=(
                "Manage a staged cancellation. First call action=prepare with the "
                "patient phone number. After the patient confirms the phone read-back, "
                "call action=confirm_phone. Show the returned appointments. After "
                "the patient selects one, call action=select with its appointment_id. "
                "Only call action=confirm_cancellation after the patient separately "
                "confirms the selected cancellation."
            ),
            properties={
                "action": {
                    "type": "string",
                    "enum": [
                        "prepare",
                        "confirm_phone",
                        "select",
                        "confirm_cancellation",
                    ],
                },
                "phone_number": {"type": "string"},
                "appointment_id": {"type": "string"},
            },
            required=["action"],
            handler=cancel_appointment_handler,
        ),
    ]
