import logging
from typing import Optional

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

_usuarios_client: Optional[httpx.AsyncClient] = None
_eventos_client: Optional[httpx.AsyncClient] = None
_circuit_breakers = {"usuarios_service": "closed", "eventos_service": "closed"}
_failure_counts = {"usuarios_service": 0, "eventos_service": 0}


async def get_usuarios_client() -> httpx.AsyncClient:
    global _usuarios_client
    settings = get_settings()
    if _usuarios_client is None:
        _usuarios_client = httpx.AsyncClient(
            base_url=settings.usuarios_service_url,
            timeout=httpx.Timeout(5.0, connect=2.0),
        )
    return _usuarios_client


async def get_eventos_client() -> httpx.AsyncClient:
    global _eventos_client
    settings = get_settings()
    if _eventos_client is None:
        _eventos_client = httpx.AsyncClient(
            base_url=settings.eventos_service_url,
            timeout=httpx.Timeout(5.0, connect=2.0),
        )
    return _eventos_client


async def close_http_clients() -> None:
    global _usuarios_client, _eventos_client
    if _usuarios_client:
        await _usuarios_client.aclose()
        _usuarios_client = None
    if _eventos_client:
        await _eventos_client.aclose()
        _eventos_client = None
    logger.info("🔌 HTTP clients cerrados")


async def check_circuit_breaker(service_name: str) -> bool:
    """Verificar si circuit breaker está abierto."""
    return _circuit_breakers.get(service_name) != "open"


def record_success(service_name: str) -> None:
    """Registrar éxito y resetear contador."""
    _failure_counts[service_name] = 0
    if _circuit_breakers.get(service_name) == "half-open":
        _circuit_breakers[service_name] = "closed"
        logger.info(f"Circuit breaker {service_name} cerrado")


def record_failure(service_name: str) -> None:
    """Registrar fallo y abrir circuit breaker si es necesario."""
    _failure_counts[service_name] = _failure_counts.get(service_name, 0) + 1
    if _failure_counts[service_name] >= 5:
        _circuit_breakers[service_name] = "open"
        logger.warning(f"Circuit breaker {service_name} ABIERTO")


def get_circuit_breaker_state() -> dict:
    return _circuit_breakers.copy()


async def get_usuario(usuario_id: str, correlation_id: str = "") -> Optional[dict]:
    """GET /api/usuarios/{id} en Usuarios Service. None si no existe (404)."""
    client = await get_usuarios_client()
    headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}
    try:
        resp = await client.get(f"/api/usuarios/{usuario_id}", headers=headers)
    except httpx.HTTPError:
        record_failure("usuarios_service")
        raise
    if resp.status_code == 404:
        record_success("usuarios_service")
        return None
    resp.raise_for_status()
    record_success("usuarios_service")
    return resp.json()


async def get_evento(evento_id: str, correlation_id: str = "") -> Optional[dict]:
    """GET /api/eventos/{id} en Eventos Service. None si no existe (404)."""
    client = await get_eventos_client()
    headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}
    try:
        resp = await client.get(f"/api/eventos/{evento_id}", headers=headers)
    except httpx.HTTPError:
        record_failure("eventos_service")
        raise
    if resp.status_code == 404:
        record_success("eventos_service")
        return None
    resp.raise_for_status()
    record_success("eventos_service")
    return resp.json()


async def decrementar_inventario_evento(
    evento_id: str, categoria: str, cantidad: int, correlation_id: str = ""
) -> dict:
    """POST /api/eventos/{id}/decrementar-inventario.

    Sincroniza en eventos-service la venta que Redis ya confirmo de forma
    atomica. Redis es quien evita la doble venta; esta llamada solo
    mantiene entradas_disponibles/precios[].disponibles alineados con lo
    que efectivamente se vendio, para que GET /api/eventos/{id} no siga
    mostrando el aforo original despues de vender entradas. Propaga la
    excepcion en caso de error - el llamador decide como compensar.
    """
    client = await get_eventos_client()
    headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}
    resp = await client.post(
        f"/api/eventos/{evento_id}/decrementar-inventario",
        json={"categoria": categoria, "cantidad": cantidad},
        headers=headers,
    )
    resp.raise_for_status()
    record_success("eventos_service")
    return resp.json()


async def incrementar_inventario_evento(
    evento_id: str, categoria: str, cantidad: int, correlation_id: str = ""
) -> None:
    """POST /api/eventos/{id}/incrementar-inventario - compensacion.

    Best-effort: si esta llamada falla no hay nada mas que hacer para
    revertir (ya estamos en un camino de compensacion), asi que solo se
    loguea. La fuente de verdad de "cuanto queda disponible" para evitar
    dobles ventas sigue siendo Redis, que ya se revirtio antes de llegar
    aca - esto es solo mantener eventos-service alineado.
    """
    client = await get_eventos_client()
    headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}
    try:
        resp = await client.post(
            f"/api/eventos/{evento_id}/incrementar-inventario",
            json={"categoria": categoria, "cantidad": cantidad},
            headers=headers,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.error(
            f"No se pudo revertir inventario en eventos-service "
            f"(evento={evento_id}, categoria={categoria}, cantidad={cantidad}): {e}"
        )
