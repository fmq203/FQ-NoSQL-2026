import logging
from typing import Optional
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import NoScriptError

from src.config import get_settings

logger = logging.getLogger(__name__)

# TTL del hash pago:{reserva_id} - suficiente para debugging/idempotencia
# de corto plazo; la fuente de verdad de largo plazo es MongoDB + event_log.
PAGO_TTL_SECONDS = 90 * 24 * 3600  # 90 dias

_redis: Optional[Redis] = None
_sha_reservar: Optional[str] = None
_sha_liberar: Optional[str] = None
_sha_pagar: Optional[str] = None
_sha_compensar: Optional[str] = None

# Script legado (evento sin categoria) - se mantiene por compatibilidad.
_LUA_RESERVAR = """
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

_LUA_LIBERAR = """
local disponible = redis.call('GET', KEYS[1])
if not disponible then
    return -1
end
local cantidad = tonumber(ARGV[1])
redis.call('INCRBY', KEYS[1], cantidad)
return tonumber(disponible) + cantidad
"""

# Paso 4 de la SAGA (ProcesadorPago): siembra la clave de inventario por
# categoria con SETNX (solo la primera llamada la inicializa, con el aforo
# real que ValidadorEvento acaba de leer del Eventos Service) y luego
# decrementa + registra el pago en un unico paso atomico. Esto es lo que
# evita la doble venta: dos reservas concurrentes para el mismo evento
# compiten por la MISMA clave ya sembrada, nunca por dos semillas distintas.
_LUA_PAGAR_Y_DECREMENTAR = """
local inventario_key = KEYS[1]
local pago_key = KEYS[2]
local cantidad = tonumber(ARGV[1])
local seed = tonumber(ARGV[2])
local usuario_id = ARGV[3]
local evento_id = ARGV[4]
local monto = ARGV[5]
local metodo_pago = ARGV[6]
local categoria = ARGV[7]
local ttl = tonumber(ARGV[8])

-- Idempotencia: si esta reserva_id ya pago (reintento del cliente tras un
-- timeout, por ejemplo), no volver a decrementar el inventario.
if redis.call('EXISTS', pago_key) == 1 then
    local ya_pagado = tonumber(redis.call('HGET', pago_key, 'cantidad'))
    return {1, ya_pagado}
end

redis.call('SETNX', inventario_key, seed)
local disponible = tonumber(redis.call('GET', inventario_key))

if disponible < cantidad then
    return {-2, disponible}
end

redis.call('DECRBY', inventario_key, cantidad)
redis.call('HSET', pago_key,
    'usuario_id', usuario_id,
    'evento_id', evento_id,
    'cantidad', ARGV[1],
    'monto', monto,
    'metodo_pago', metodo_pago,
    'categoria', categoria,
    'inventario_key', inventario_key,
    'estado', 'confirmado')
redis.call('EXPIRE', pago_key, ttl)

return {1, disponible - cantidad}
"""

# Compensacion (rollback): revierte el pago identificado por reserva_id.
# Idempotente - si ya fue compensado (o nunca se llego a pagar), no hace nada.
_LUA_COMPENSAR_PAGO = """
local pago_key = KEYS[1]
local inventario_key = redis.call('HGET', pago_key, 'inventario_key')
local cantidad = redis.call('HGET', pago_key, 'cantidad')

if not inventario_key then
    return 0
end

redis.call('INCRBY', inventario_key, tonumber(cantidad))
redis.call('DEL', pago_key)
return 1
"""


async def register_lua_scripts() -> None:
    """Conectar a Redis y registrar todos los scripts Lua."""
    global _redis, _sha_reservar, _sha_liberar, _sha_pagar, _sha_compensar
    settings = get_settings()

    _redis = Redis.from_url(settings.redis_url, decode_responses=True)

    try:
        await _redis.ping()
        logger.info("✅ Redis conectado")
    except Exception as e:
        logger.error(f"❌ Error Redis: {e}")
        raise

    _sha_reservar = await _redis.script_load(_LUA_RESERVAR)
    _sha_liberar = await _redis.script_load(_LUA_LIBERAR)
    _sha_pagar = await _redis.script_load(_LUA_PAGAR_Y_DECREMENTAR)
    _sha_compensar = await _redis.script_load(_LUA_COMPENSAR_PAGO)

    logger.info("✅ Scripts Lua registrados (reservar, liberar, pagar, compensar)")


async def close_redis_connection() -> None:
    global _redis
    if _redis:
        await _redis.close()
        _redis = None
        logger.info("🔌 Redis cerrado")


async def get_redis_client() -> Redis:
    """Devuelve el cliente Redis compartido, creandolo si aun no se llamo
    a register_lua_scripts() (por ejemplo en tests unitarios)."""
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def get_sha_reservar() -> Optional[str]:
    return _sha_reservar


def get_sha_liberar() -> Optional[str]:
    return _sha_liberar


def get_sha_pagar() -> Optional[str]:
    return _sha_pagar


def get_sha_compensar() -> Optional[str]:
    return _sha_compensar


async def _evalsha_with_reload(sha_getter, script_src: str, keys: list, args: list):
    """Ejecuta evalsha; si Redis perdio el script cacheado (reinicio, FLUSHALL,
    etc.) lo vuelve a registrar una vez y reintenta, en vez de romper la SAGA."""
    redis = await get_redis_client()
    sha = sha_getter()
    if not sha:
        await register_lua_scripts()
        sha = sha_getter()
    try:
        return await redis.evalsha(sha, len(keys), *keys, *args)
    except NoScriptError:
        await register_lua_scripts()
        sha = sha_getter()
        return await redis.evalsha(sha, len(keys), *keys, *args)


async def ejecutar_pagar_y_decrementar(
    evento_id: str,
    reserva_id: str,
    usuario_id: str,
    cantidad: int,
    monto: float,
    metodo_pago: str,
    categoria: str,
    seed_disponibles: int,
) -> dict:
    """Paso 4 de la SAGA: reserva atomica de inventario + registro de pago.

    seed_disponibles es el aforo real leido de Eventos Service en el paso
    anterior (ValidadorEvento). Solo se usa para inicializar la clave la
    PRIMERA vez (SETNX); reservas concurrentes subsiguientes decrementan
    la misma clave ya sembrada, por lo que nunca puede venderse mas de lo
    que la clave realmente tiene disponible.
    """
    inventario_key = f"evento:{evento_id}:categoria:{categoria}:disponibles"
    pago_key = f"pago:{reserva_id}"

    result = await _evalsha_with_reload(
        get_sha_pagar,
        _LUA_PAGAR_Y_DECREMENTAR,
        [inventario_key, pago_key],
        [
            str(cantidad),
            str(seed_disponibles),
            str(usuario_id),
            str(evento_id),
            str(monto),
            metodo_pago,
            categoria,
            str(PAGO_TTL_SECONDS),
        ],
    )

    status, value = int(result[0]), int(result[1])
    if status == -2:
        return {
            "success": False,
            "message": f"INSUFICIENTE: solo hay {value} entradas disponibles",
            "disponibles": value,
        }
    return {"success": True, "message": "Pago procesado", "disponibles": value}


async def ejecutar_compensar_pago_inventario(
    evento_id: str,
    reserva_id: str,
    cantidad: int,
) -> dict:
    """Compensacion: libera el inventario reservado y borra el pago.

    Idempotente por diseno (si ya se compenso o nunca hubo pago, es un no-op).
    evento_id/cantidad se reciben por compatibilidad de firma con el resto
    de la SAGA, pero la fuente de verdad de que revertir vive en el propio
    hash pago:{reserva_id} (evita reconstruir mal la clave si difiere).
    """
    pago_key = f"pago:{reserva_id}"
    result = await _evalsha_with_reload(
        get_sha_compensar,
        _LUA_COMPENSAR_PAGO,
        [pago_key],
        [],
    )
    if int(result) == 0:
        return {"success": True, "message": "Nada que compensar (idempotente)"}
    return {"success": True, "message": "Inventario liberado y pago revertido"}


async def obtener_pago(reserva_id: str) -> Optional[dict]:
    """Leer el hash pago:{reserva_id} - usado para chequeos de idempotencia."""
    redis = await get_redis_client()
    data = await redis.hgetall(f"pago:{reserva_id}")
    return data or None
