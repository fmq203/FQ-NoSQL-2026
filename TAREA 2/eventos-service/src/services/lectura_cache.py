"""Cache de lecturas (Redis) para los GET de este servicio.

Requisito del enunciado: las lecturas de usuarios y eventos deben ser
extremadamente rapidas y priorizar disponibilidad y tolerancia a
particiones, aceptando consistencia eventual (AP).

Politica "stale-if-error":
- Una entrada tiene dos plazos: *fresca* (CACHE_FRESH_SECONDS, default 30 s)
  y *vencida pero utilizable* (CACHE_STALE_SECONDS, default 1 h).
- Fresca -> se sirve de Redis sin tocar MongoDB (HIT).
- Vencida o ausente -> se lee de MongoDB y se refresca la entrada (MISS).
- MongoDB caido y hay una entrada vencida -> se sirve esa (STALE): se prefiere
  responder con un dato posiblemente desactualizado a no responder.

El camino transaccional NO usa esto: quien necesita un dato estrictamente
actual (la SAGA de Reservas) manda `Cache-Control: no-cache`, que fuerza la
lectura a MongoDB (BYPASS) y no admite STALE.

El cache es una optimizacion, nunca una dependencia: si Redis falla, las
lecturas siguen yendo a MongoDB (y tras un fallo no se reintenta Redis
durante unos segundos para no sumar latencia en cada request).
"""
import json
import logging
import time
from typing import Awaitable, Callable, Optional, Tuple

import redis.asyncio as aioredis
from pymongo.errors import PyMongoError

from src.config import get_settings

logger = logging.getLogger(__name__)

HIT, MISS, STALE, BYPASS = "HIT", "MISS", "STALE", "BYPASS"
_REINTENTO_REDIS_S = 5.0

_redis: Optional[aioredis.Redis] = None
_redis_caido_hasta = 0.0


def _cliente() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            get_settings().cache_redis_url,
            decode_responses=True,
            socket_connect_timeout=0.3,
            socket_timeout=0.3,
        )
    return _redis


def _redis_disponible() -> bool:
    return get_settings().cache_enabled and time.monotonic() >= _redis_caido_hasta


def _marcar_redis_caido(error: Exception) -> None:
    global _redis_caido_hasta
    _redis_caido_hasta = time.monotonic() + _REINTENTO_REDIS_S
    logger.warning(f"Cache Redis no disponible, se lee directo de MongoDB: {error}")


async def _leer(key: str) -> Optional[dict]:
    if not _redis_disponible():
        return None
    try:
        crudo = await _cliente().get(key)
        return json.loads(crudo) if crudo else None
    except Exception as e:
        _marcar_redis_caido(e)
        return None


async def _guardar(key: str, data: dict) -> None:
    if not _redis_disponible():
        return
    try:
        entrada = json.dumps({"cached_at": time.time(), "data": data})
        await _cliente().set(key, entrada, ex=get_settings().cache_stale_seconds)
    except Exception as e:
        _marcar_redis_caido(e)


async def invalidar(key: str) -> None:
    """Borra la entrada tras una escritura, para que la proxima lectura vea el cambio."""
    if not _redis_disponible():
        return
    try:
        await _cliente().delete(key)
    except Exception as e:
        _marcar_redis_caido(e)


async def leer_con_cache(
    key: str,
    cargar: Callable[[], Awaitable[dict]],
    *,
    bypass: bool = False,
) -> Tuple[dict, str]:
    """Devuelve (dato, estado) con estado en HIT / MISS / STALE / BYPASS.

    `cargar` lee de MongoDB y devuelve un dict serializable a JSON. Los errores
    de negocio (ej. 404) se propagan tal cual y no se cachean; solo un fallo de
    infraestructura de MongoDB habilita servir una entrada vencida.
    """
    entrada = None if bypass else await _leer(key)
    if entrada and time.time() - entrada["cached_at"] < get_settings().cache_fresh_seconds:
        return entrada["data"], HIT

    try:
        data = await cargar()
    except PyMongoError:
        if entrada is not None:  # nunca con bypass: entrada es None
            logger.warning(f"MongoDB no responde: se sirve {key} desde cache vencido (STALE)")
            return entrada["data"], STALE
        raise

    await _guardar(key, data)
    return data, BYPASS if bypass else MISS
