from redis.asyncio import Redis
from src.config import get_settings
import logging

logger = logging.getLogger(__name__)

_redis: Redis = None
_sha_reservar: str = None
_sha_liberar: str = None


async def register_lua_scripts() -> None:
    """Registrar scripts Lua para operaciones atómicas."""
    global _redis, _sha_reservar, _sha_liberar
    from src.config import get_settings
    settings = get_settings()

    _redis = Redis.from_url(settings.redis_url, decode_responses=True)

    try:
        await _redis.ping()
        logger.info("✅ Redis conectado")
    except Exception as e:
        logger.error(f"❌ Error Redis: {e}")
        raise

    # Script para reserva atómica de inventario
    lua_reservar = """
    local disponible = redis.call('GET', KEYS[1])
    if not disponible then
        return -1  -- clave no existe
    end
    disponible = tonumber(disponible)
    local cantidad = tonumber(ARGV[1])
    if disponible < cantidad then
        return -2  -- inventario insuficiente
    end
    redis.call('DECRBY', KEYS[1], cantidad)
    return disponible - cantidad
    """

    # Script para liberación (compensación)
    lua_liberar = """
    local disponible = redis.call('GET', KEYS[1])
    if not disponible then
        return -1
    end
    local cantidad = tonumber(ARGV[1])
    redis.call('INCRBY', KEYS[1], cantidad)
    return tonumber(disponible) + cantidad
    """

    global _sha_reservar, _sha_liberar
    _sha_reservar = await _redis.script_load(lua_reservar)
    _sha_liberar = await _redis.script_load(lua_liberar)

    logger.info("✅ Scripts Lua registrados")


async def close_redis_connection() -> None:
    global _redis
    if _redis:
        await _redis.close()
        logger.info("🔌 Redis cerrado")


async def get_redis_client() -> Redis:
    from src.config import get_settings
    settings = get_settings()
    return Redis.from_url(settings.redis_url, decode_responses=True)


def get_sha_reservar() -> str:
    global _sha_reservar
    return _sha_reservar


def get_sha_liberar() -> str:
    global _sha_liberar
    return _sha_liberar