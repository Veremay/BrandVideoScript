from collections.abc import AsyncIterator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings


class Mongo:
    client: AsyncIOMotorClient | None = None


async def connect_mongo() -> None:
    settings = get_settings()
    Mongo.client = AsyncIOMotorClient(settings.mongodb_url)


async def close_mongo() -> None:
    if Mongo.client is not None:
        Mongo.client.close()
        Mongo.client = None


def get_database() -> AsyncIOMotorDatabase:
    if Mongo.client is None:
        raise RuntimeError("MongoDB client is not initialized")
    return Mongo.client[get_settings().mongodb_db]


async def database_dependency() -> AsyncIterator[AsyncIOMotorDatabase]:
    yield get_database()

