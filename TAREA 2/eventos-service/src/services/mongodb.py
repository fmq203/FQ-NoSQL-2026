from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import WriteConcern
from pymongo.read_preferences import ReadPreference
from contextlib import asynccontextmanager
import logging

from src.config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


def _build_connection_uri() -> str:
    settings = get_settings()
    uri = settings.mongodb_uri
    
    # Add connection options to URI if not already present
    if "?" not in uri:
        uri += "?"
    else:
        uri += "&"
    
    uri += "readPreference=secondaryPreferred"
    uri += "&maxPoolSize=10"
    uri += "&minPoolSize=1"
    uri += "&serverSelectionTimeoutMS=5000"
    uri += "&connectTimeoutMS=10000"
    uri += "&socketTimeoutMS=30000"
    uri += "&w=majority"
    uri += "&journal=true"
    uri += "&uuidRepresentation=standard"
    
    return uri


async def connect_to_mongodb() -> None:
    global _client, _database
    uri = _build_connection_uri()
    
    _client = AsyncIOMotorClient(uri)
    _database = _client[get_settings().mongodb_database]
    
    await create_indexes()
    logger.info("MongoDB connection established")


async def close_mongodb_connection() -> None:
    global _client
    if _client:
        _client.close()
        _client = None
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    if _database is None:
        raise RuntimeError("Database not initialized. Call connect_to_mongodb() first.")
    return _database


def get_collection(collection_name: str | None = None):
    settings = get_settings()
    db = get_database()
    return db[collection_name or settings.mongodb_collection]


async def create_indexes() -> None:
    collection = get_collection()
    
    await collection.create_index("nombre")
    await collection.create_index("estado")
    await collection.create_index("creado_en")
    await collection.create_index([("estado", 1), ("creado_en", -1)])
    
    logger.info("MongoDB indexes created/verified")


async def ping_mongodb(timeout_ms: int = 2000) -> tuple[bool, float]:
    """Ping MongoDB and return (success, latency_ms)"""
    import time
    try:
        start = time.perf_counter()
        await get_database().command("ping")
        latency_ms = (time.perf_counter() - start) * 1000
        return True, latency_ms
    except Exception as e:
        logger.warning(f"MongoDB ping failed: {e}")
        return False, float(timeout_ms)


@asynccontextmanager
async def mongodb_lifespan():
    await connect_to_mongodb()
    try:
        yield
    finally:
        await close_mongodb_connection()