"""Redis connection and Lua scripts for Reservas Service."""
import os
from typing import Optional, Dict, Any
import redis.asyncio as redis
from redis.asyncio import Redis

# Global Redis client
_redis_client: Optional[Redis] = None

# Lua scripts
PAGAR_Y_DECREMENTAR_LUA = """
-- KEYS[1] = inventario:evento_id
-- KEYS[2] = pago:reserva_id
-- ARGV[1] = cantidad, ARGV[2] = reserva_id, ARGV[3] = usuario_id
-- ARGV[4] = monto, ARGV[5] = metodo_pago

local disponible = tonumber(redis.call('GET', KEYS[1]) or '0')
if disponible < tonumber(ARGV[1]) then
    return {0, 'INVENTARIO_INSUFICIENTE'}
end
redis.call('DECRBY', KEYS[1], ARGV[1])
redis.call('HSET', KEYS[2],
    'reserva_id', ARGV[2], 'usuario_id', ARGV[3],
    'monto', ARGV[4], 'metodo_pago', ARGV[5],
    'estado', 'confirmado', 'timestamp', os.date('!%Y-%m-%dT%H:%M:%SZ')
)
redis.call('EXPIRE', KEYS[2], 86400)
return {1, 'OK'}
"""

COMPENSAR_PAGO_INVENTARIO_LUA = """
-- KEYS[1] = inventario:evento_id
-- KEYS[2] = pago:reserva_id
-- ARGV[1] = cantidad

redis.call('INCRBY', KEYS[1], ARGV[1])
redis.call('DEL', KEYS[2])
return {1, 'COMPENSACION_OK'}
"""

_redis_client: Optional[redis.Redis] = None
_pagar_y_decrementar_sha: Optional[str] = None
_compensar_pago_inventario_sha: Optional[str] = None


async def get_redis_client() -> redis.Redis:
    """Get or create Redis async client."""
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _redis_client = redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    return _redis_client


async def register_lua_scripts() -> None:
    """Register Lua scripts on startup."""
    global _pagar_y_decrementar_sha, _compensar_pago_inventario_sha
    client = await get_redis_client()
    _pagar_y_decrementar_sha = await client.script_load(PAGAR_Y_DECREMENTAR_LUA)
    _compensar_pago_inventario_sha = await client.script_load(COMPENSAR_PAGO_INVENTARIO_LUA)


async def ejecutar_pagar_y_decrementar(
    evento_id: str,
    reserva_id: str,
    usuario_id: str,
    cantidad: int,
    monto: float,
    metodo_pago: str
) -> Dict[str, Any]:
    """
    Ejecuta pago + decremento inventario atómicamente via Lua script.

    Returns:
        Dict con 'success': bool, 'message': str
    """
    client = await get_redis_client()
    keys = [f"inventario:{evento_id}", f"pago:{reserva_id}"]
    args = [cantidad, reserva_id, usuario_id, str(monto), metodo_pago]

    try:
        result = await client.evalsha(
            _pagar_y_decrementar_sha, 2, *keys, *args
        )
        return {"success": result[0] == 1, "message": result[1]}
    except Exception as e:
        # Script might have been flushed, reload and retry once
        await register_lua_scripts()
        result = await client.evalsha(
            _pagar_y_decrementar_sha, 2, *keys, *args
        )
        return {"success": result[0] == 1, "message": result[1]}


async def ejecutar_compensar_pago_inventario(
    evento_id: str,
    reserva_id: str,
    cantidad: int
) -> Dict[str, Any]:
    """
    Ejecuta compensación: INCRBY inventario + DEL pago.

    Returns:
        Dict con 'success': bool, 'message': str
    """
    client = await get_redis_client()
    keys = [f"inventario:{evento_id}", f"pago:{reserva_id}"]
    args = [cantidad]

    try:
        result = await client.evalsha(
            _compensar_pago_inventario_sha, 2, *keys, *args
        )
        return {"success": result[0] == 1, "message": result[1]}
    except Exception as e:
        await register_lua_scripts()
        result = await client.evalsha(
            _compensar_pago_inventario_sha, 2, *keys, *args
        )
        return {"success": result[0] == 1, "message": result[1]}


async def inicializar_inventario(evento_id: str, aforo_total: int) -> bool:
    """Inicializa inventario en Redis para un evento."""
    client = await get_redis_client()
    try:
        await client.set(
            f"inventario:{evento_id}",
            str(aforo_total),
            ex=86400  # 24h TTL, renovado por Eventos Service
        )
        return True
    except Exception:
        return False


async def obtener_inventario(evento_id: str) -> int:
    """Obtiene inventario actual desde Redis."""
    client = await get_redis_client()
    try:
        value = await client.get(f"inventario:{evento_id}")
        return int(value) if value else 0
    except Exception:
        return 0


async def obtener_pago(reserva_id: str) -> Optional[Dict[str, str]]:
    """Obtiene datos de pago desde Redis."""
    client = await get_redis_client()
    try:
        data = await client.hgetall(f"pago:{reserva_id}")
        return data if data else None
    except Exception:
        return None


async def invalidar_cache_disponibilidad(evento_id: str) -> bool:
    """Invalida cache de disponibilidad para un evento."""
    client = await get_redis_client()
    try:
        await client.delete(f"evento:disp:{evento_id}")
        return True
    except Exception:
        return False


async def close_redis_connection() -> None:
    """Close Redis connection."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None

# Alias for Spanish name
registrar_lua_scripts = register_lua_scripts

# Export both names for compatibility
__all__ = [
    "get_redis_client",
    "register_lua_scripts",
    "registrar_lua_scripts",  # alias for Spanish name
    "ejecutar_pagar_y_decrementar",
    "ejecutar_compensar_pago_inventario",
    "inicializar_inventario",
    "obtener_inventario",
    "obtener_pago",
    "invalidar_cache_disponibilidad",
    "close_redis_connection",
]