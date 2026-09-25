from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import WriteConcern
from pymongo.read_preferences import _ServerMode
from src.config import get_settings
import logging

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient = None
_database: AsyncIOMotorDatabase = None


async def connect_to_mongodb() -> None:
    """Conectar a MongoDB con configuración de consistencia."""
    global _client, _database
    settings = get_settings()

    # Configurar read preference con max_staleness_seconds=1
    # mode=2 (SECONDARY_PREFERRED), tag_sets=[{}], max_staleness_seconds=1
    read_pref = _ServerMode(2, [{}], 1)

    _client = AsyncIOMotorClient(
        settings.mongodb_uri,
        read_preference=read_pref,
        serverSelectionTimeoutMS=5000,
        w="majority",
        journal=True,
    )
    _database = _client[settings.mongodb_database]

    # Verificar conexión
    try:
        await _client.admin.command("ping")
        logger.info("✅ Conexión a MongoDB establecida")
    except Exception as e:
        logger.error(f"❌ Error conectando a MongoDB: {e}")
        raise

    # Crear índices
    await create_indexes()


async def close_mongodb_connection() -> None:
    """Cerrar conexión a MongoDB."""
    global _client
    if _client:
        _client.close()
        logger.info("🔌 Conexión a MongoDB cerrada")


def get_database() -> AsyncIOMotorDatabase:
    """Obtener instancia de base de datos."""
    if _database is None:
        raise RuntimeError("MongoDB no inicializado. Llamar connect_to_mongodb() primero.")
    return _database


def get_collection(collection_name: str):
    """Obtener colección específica."""
    db = get_database()
    return db[collection_name]


async def create_indexes() -> None:
    """Crear índices en MongoDB."""
    db = get_database()
    settings = get_settings()

    # Índices para usuarios
    usuarios_collection = db[settings.mongodb_collection]
    await usuarios_collection.create_index("email", unique=True)
    await usuarios_collection.create_index("nro_documento", unique=True)
    await usuarios_collection.create_index("creado_en")
    await usuarios_collection.create_index("tipo_documento")
    await usuarios_collection.create_index("nombre")

    logger.info("✅ Índices de MongoDB creados/verificados")


async def ping_mongodb(timeout_ms: int = 2000) -> tuple[bool, float]:
    """Hacer ping a MongoDB y medir latencia."""
    import time
    import asyncio
    db = get_database()
    start = time.perf_counter()
    try:
        await asyncio.wait_for(db.command("ping"), timeout=timeout_ms / 1000.0)
        latency_ms = (time.perf_counter() - start) * 1000
        return True, latency_ms
    except asyncio.TimeoutError:
        logger.warning(f"MongoDB ping timeout después de {timeout_ms}ms")
        latency_ms = (time.perf_counter() - start) * 1000
        return False, latency_ms
    except Exception as e:
        logger.warning(f"MongoDB ping falló: {e}")
        latency_ms = (time.perf_counter() - start) * 1000
        return False, latency_ms