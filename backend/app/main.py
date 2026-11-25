from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.database.connection import connect_to_mongodb, close_mongodb_connection
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Application startup
    await connect_to_mongodb(app)

    yield

    # Application shutdown
    await close_mongodb_connection(app)


app = FastAPI(
    title=settings.APP_NAME,
    description="Voice AI Doctor Appointment Booking System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {
        "message": "API is running",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "OK",
    }


@app.get("/health/db")
async def database_health(request: Request):
    try:
        await request.app.state.mongodb.command("ping")

        return {
            "status": "connected",
            "database": settings.MONGODB_DB_NAME,
        }

    except Exception:
        return {
            "status": "disconnected",
            "database": settings.MONGODB_DB_NAME,
        }