from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from loguru import logger
from pymongo import AsyncMongoClient

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import (
    PipelineParams,
    PipelineWorker,
    ProcessorUnusablePolicy,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.elevenlabs.stt import ElevenLabsRealtimeSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.workers.runner import WorkerRunner

from app.core.config import settings
from app.voice.tools import build_voice_tools


load_dotenv(override=True)

GREETING = (
    "Hello, this is NexovAI. "
    "I can check doctor availability, book, or cancel an appointment. "
    "How can I help you today?"
)


SYSTEM_INSTRUCTION = """
You are NexovAI, a friendly voice-based doctor appointment assistant.

Your responsibilities:
- Help patients find doctors and appointment slots.
- Help patients book appointments.
- Help patients cancel existing appointments.
- Speak naturally and keep responses concise.

Greeting rules:
- The assistant has already introduced itself at the beginning of the call.
- Never repeat the introduction or say your name again.
- If the patient says hello, respond only with: "How can I help you today?"
- Continue directly with the patient's request.

Conversation rules:
- Ask only one question at a time.
- Keep every response short, natural, and friendly.
- Never repeat a question if the patient has already answered it.
- Remember all information provided during the current conversation.
- Never ask for information that is already available.
- Understand natural English, including incomplete sentences and different accents.
- If the patient says "I want to", politely ask what they would like to do.
- If the patient changes their request, follow the latest request.
- Do not interrupt the patient.
- Never repeat the initial greeting.
- Do not speak in multiple languages unless the patient requests it.

Booking process:
1. Ask for the patient's name and phone number.
2. Find the requested doctor and available slot using check_doctor_availability. If the patient mentions a day, pass it as the date argument.
3. Call book_appointment with action=prepare and the selected details.
4. Read the phone number back digit by digit.
5. Wait for the patient to explicitly confirm the phone number.
6. Only then call book_appointment with action=confirm_phone.
7. Read the doctor and appointment time back to the patient.
8. Wait for a separate explicit confirmation of the booking.
9. Only then call book_appointment with action=confirm_booking.
10. Report success only if the backend returns success=true.

Cancellation process:
1. Ask for the patient's phone number.
2. Call cancel_appointment with action=prepare.
3. Read the phone number back digit by digit and wait for confirmation.
4. Only then call cancel_appointment with action=confirm_phone.
5. Present the active appointments returned by the tool, using each display_time.
6. Ask which appointment the patient wants to cancel.
7. Call cancel_appointment with action=select and the selected appointment_id.
8. Read the selected doctor and appointment time back.
9. Wait for a separate explicit cancellation confirmation.
10. Only then call cancel_appointment with action=confirm_cancellation.
11. Report success only if the backend returns success=true.

Important rules:
- Never skip a confirmation step.
- Never treat the same "yes" as confirmation of two different actions.
- Always use the exact appointment_time or display_time returned by tools. Never calculate or guess weekdays yourself.
- Never invent doctors, slots, or appointments.
- Copy doctor_id, slot_id and appointment_id exactly as returned by the tools. Never make up an ID.
- Always pass phone_number to tools as digits only.
- Never use asterisks, bullet points or dashes. Speak in plain sentences.
- Never claim a booking or cancellation succeeded unless the backend confirms it.
- If a tool rejects an action, follow its instructions and ask the patient for the missing information.
- Never provide medical diagnoses.
- Speak dates and times clearly, using India Standard Time where appropriate.
- Your responses will be spoken aloud. Avoid markdown and long lists.
"""


def build_system_instruction():
    today = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%A, %d %B %Y")

    return SYSTEM_INSTRUCTION + (
        f"\nToday's date in India is {today}. Use it to understand words like "
        "today, tomorrow or next Monday, and pass dates to "
        "check_doctor_availability as YYYY-MM-DD.\n"
    )


async def run_bot(transport, runner_args: RunnerArguments):
    client = AsyncMongoClient(
        settings.MONGODB_URI,
        tz_aware=True,
        serverSelectionTimeoutMS=5000,
    )

    try:
        await client.admin.command("ping")
        db = client[settings.MONGODB_DB_NAME]
        logger.info("Voice agent connected to MongoDB")

        app_resources = {
            "db": db,
            "session_state": {
                "pending_booking": None,
                "pending_cancel": None,
            },
        }

        stt = ElevenLabsRealtimeSTTService(
            api_key=settings.ELEVENLABS_API_KEY,
        )

        tts = ElevenLabsTTSService(
            api_key=settings.ELEVENLABS_API_KEY,
            settings=ElevenLabsTTSService.Settings(
                voice=settings.ELEVENLABS_VOICE_ID,
                model="eleven_flash_v2_5",
            ),
        )

        llm = GroqLLMService(
            api_key=settings.GROQ_API_KEY,
            settings=GroqLLMService.Settings(
                system_instruction=build_system_instruction(),
                temperature=0.3,
            ),
        )

        context = LLMContext(tools=build_voice_tools())

        user_aggregator, assistant_aggregator = (
            LLMContextAggregatorPair(
                context,
                user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
            )
        )

        pipeline = Pipeline([
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ])

        worker = PipelineWorker(
            pipeline,
            params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
            processor_unusable_policy=ProcessorUnusablePolicy.END,
            app_resources=app_resources,
        )

        runner = WorkerRunner(
            handle_sigint=runner_args.handle_sigint,
        )

        await runner.add_workers(worker)

        greeting_state = {"sent": False} 

        @worker.rtvi.event_handler("on_client_ready")
        async def on_client_ready(rtvi):
            if greeting_state["sent"]:
                return

            greeting_state["sent"] = True
            logger.info("Client ready, speaking greeting")

            await worker.queue_frames([TTSSpeakFrame(GREETING, append_to_context=True)])

        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, webrtc_client):
            logger.info("Patient connected to NexovAI")

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, webrtc_client):
            logger.info("Patient disconnected")
            await runner.cancel()

        await runner.run()

    finally:
        await client.close()
        logger.info("Voice agent MongoDB connection closed")


async def bot(runner_args: RunnerArguments):
    connection: SmallWebRTCConnection = runner_args.webrtc_connection

    transport = SmallWebRTCTransport(
        webrtc_connection=connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    )

    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()