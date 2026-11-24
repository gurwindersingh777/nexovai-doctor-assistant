
from pymongo import AsyncMongoClient
from app.core.config import settings


async def connect_to_mongodb(app):
    """Create MongoDB connection and verify connectivity."""

    client = AsyncMongoClient(
        settings.MONGODB_URI,
        serverSelectionTimeoutMS=5000,
    )

    # Verify that MongoDB is reachable
    await client.admin.command("ping")

    # Select our application database
    database = client[settings.MONGODB_DB_NAME]

    app.state.mongodb_client = client
    app.state.mongodb = database

    print("MongoDB connected successfully!")


async def close_mongodb_connection(app):
    """Close MongoDB connection."""

    client = getattr(app.state, "mongodb_client", None)

    if client:
        await client.close()
        print("MongoDB connection closed.")
