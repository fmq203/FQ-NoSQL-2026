from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import WriteConcern
from pymongo.read_preferences import _ServerMode
from redis.asyncio import Redis
from src.config import get_settings
import logging
import asyncpg

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient = None
_database: AsyncIOMotorDatabase = None
_redis: Redis = None
_pg_pool = None


async def connect_to_mongodb() -> None:
    global _client, _database
    settings = get_settings()

    # Configurar read preference con max_staleness_seconds=1
    read_pref = _ServerMode(2, [{}], 1)

    _client = AsyncIOMotorClient(
        settings.mongodb_uri,
        read_preference=read_pref,
        serverSelectionTimeoutMS=5000,
        w="majority",
        journal=True,
    )
    _database = _client[settings.mongodb_database]

    try:
        await _client.admin.command("ping")
        logger.info("✅ MongoDB conectado")
    except Exception as e:
        logger.error(f"❌ Error MongoDB: {e}")
        raise

    await create_indexes()


async def close_mongodb_connection() -> None:
    global _client
    if _client:
        _client.close()
        logger.info("🔌 MongoDB cerrado")


def get_mongo_client():
    return _client


def get_database() -> AsyncIOMotorDatabase:
    if _database is None:
        raise RuntimeError("MongoDB no inicializado")
    return _database


def get_collection(collection_name: str):
    db = get_database()
    return db[collection_name]


async def create_indexes() -> None:
    settings = get_settings()
    db = get_database()

    # Índices para reservas
    reservas = db[settings.mongodb_collection_reservas]
    await reservas.create_index("usuario_id")
    await reservas.create_index("evento_id")
    await reservas.create_index("estado")
    await reservas.create_index("creado_en")
    await reservas.create_index("idempotency_key", unique=True)

    logger.info("✅ Índices MongoDB creados")


async def ping_mongodb(timeout_ms: int = 2000) -> tuple[bool, float]:
    import time
    import asyncio
    db = get_database()
    start = time.perf_counter()
    try:
        await asyncio.wait_for(db.command("ping"), timeout=timeout_ms / 1000.0)
        return True, (time.perf_counter() - start) * 1000
    except asyncio.TimeoutError:
        logger.warning(f"MongoDB ping timeout después de {timeout_ms}ms")
        return False, (time.perf_counter() - start) * 1000
    except Exception as e:
        logger.warning(f"MongoDB ping falló: {e}")
        return False, (time.perf_counter() - start) * 1000