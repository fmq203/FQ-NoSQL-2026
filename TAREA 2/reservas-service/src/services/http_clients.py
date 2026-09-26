import asyncio
import logging
import time
from typing import Awaitable, Callable, Optional

import httpx

from src.config import get_settings
from src.services.metrics import set_circuit_breaker_state

logger = logging.getLogger(__name__)

_usuarios_client: Optional[httpx.AsyncClient] = None
_eventos_client: Optional[httpx.AsyncClient] = None
_circuit_breakers = {"usuarios_service": "closed", "eventos_service": "closed"}
_failure_counts = {"usuarios_service": 0, "eventos_service": 0}
# Momento (time.monotonic()) en que cada breaker paso a "open"; usado para
# calcular cuando corresponde probar half-open.
_circuit_opened_at = {"usuarios_service": 0.0, "eventos_service": 0.0}
# Evita que mas de una request de prueba concurrente entre en half-open a
# la vez ("Half-Open: Limited requests allowed (1 at a time)" en spec.md).
_half_open_probe_in_flight = {"usuarios_service": False, "eventos_service": False}

# Backoff exponencial para reintentos HTTP a Usuarios/Eventos, por spec.md
# ("Timeouts y Reintentos": 3 reintentos, 0.5s/1s/2s).
_RETRY_BACKOFFS_S = (0.5, 1.0, 2.0)

# "Open (Tripped)... After 30s timeout -> Half-Open" (spec.md, Circuit
# Breaker State Machine).
_HALF_OPEN_TIMEOUT_S = 30.0


class CircuitBreakerOpenError(httpx.HTTPError):
    """El circuit breaker esta abierto: se falla rapido sin llamar al servicio."""


async def _con_reintentos(
    hacer_request: Callable[[], Awaitable[httpx.Response]]
) -> httpx.Response:
    """Ejecuta una request HTTP con hasta 3 reintentos y backoff exponencial.

    Reintenta ante error de red/timeout (httpx.HTTPError) o respuesta 5xx.
    No reintenta 4xx: son errores del cliente (ej. 404, 400), un reintento
    no cambia el resultado.
    """
    ultimo_exc: Optional[Exception] = None
    for intento, delay in enumerate((0.0,) + _RETRY_BACKOFFS_S):
        if delay:
            logger.warning(f"Reintentando request (intento {intento + 1}) tras {delay}s")
            await asyncio.sleep(delay)
        try:
            resp = await hacer_request()
        except httpx.HTTPError as e:
            ultimo_exc = e
            continue
        if resp.status_code < 500:
            return resp
        ultimo_exc = httpx.HTTPStatusError(
            f"{resp.status_code} Server Error", request=resp.request, response=resp
        )
    raise ultimo_exc


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
    """True si la request puede intentarse; False si debe fallar rápido.

    Closed: siempre True. Open: True solo si ya pasaron 30s (transiciona a
    half-open y reserva el único "probe" permitido); si no, False. Half-open:
    True solo si no hay ya un probe en curso (1 a la vez), si no False.
    """
    state = _circuit_breakers.get(service_name, "closed")
    if state == "closed":
        return True
    if state == "half-open":
        if _half_open_probe_in_flight.get(service_name):
            return False
        _half_open_probe_in_flight[service_name] = True
        return True
    # state == "open"
    if time.monotonic() - _circuit_opened_at.get(service_name, 0.0) >= _HALF_OPEN_TIMEOUT_S:
        _circuit_breakers[service_name] = "half-open"
        _half_open_probe_in_flight[service_name] = True
        set_circuit_breaker_state(service_name, "half-open")
        logger.warning(f"Circuit breaker {service_name}: open -> half-open (probe)")
        return True
    return False


def record_success(service_name: str) -> None:
    """Registrar éxito: resetea contador y cierra el breaker si estaba probando."""
    _failure_counts[service_name] = 0
    _half_open_probe_in_flight[service_name] = False
    if _circuit_breakers.get(service_name) in ("half-open", "open"):
        _circuit_breakers[service_name] = "closed"
        set_circuit_breaker_state(service_name, "closed")
        logger.info(f"Circuit breaker {service_name} cerrado")


def record_failure(service_name: str) -> None:
    """Registrar fallo y abrir circuit breaker si es necesario.

    Un fallo durante el probe de half-open reabre inmediatamente (no espera
    a 5 fallos de nuevo), por spec.md ("Half-Open... Failure -> Open").
    """
    _failure_counts[service_name] = _failure_counts.get(service_name, 0) + 1
    _half_open_probe_in_flight[service_name] = False
    if _circuit_breakers.get(service_name) == "half-open":
        _circuit_breakers[service_name] = "open"
        _circuit_opened_at[service_name] = time.monotonic()
        set_circuit_breaker_state(service_name, "open")
        logger.warning(f"Circuit breaker {service_name}: probe de half-open fallo -> ABIERTO de nuevo")
    elif _failure_counts[service_name] >= 5:
        _circuit_breakers[service_name] = "open"
        _circuit_opened_at[service_name] = time.monotonic()
        set_circuit_breaker_state(service_name, "open")
        logger.warning(f"Circuit breaker {service_name} ABIERTO")


def get_circuit_breaker_state() -> dict:
    """Estado de los breakers para reporting (ej. health check).

    Un breaker "open" cuyo timeout de 30s ya paso se reporta como
    "half-open" aunque la transición real (que reserva el probe) recién
    ocurre en la próxima llamada real vía check_circuit_breaker().
    """
    now = time.monotonic()
    result = {}
    for name, state in _circuit_breakers.items():
        if state == "open" and now - _circuit_opened_at.get(name, 0.0) >= _HALF_OPEN_TIMEOUT_S:
            result[name] = "half-open"
        else:
            result[name] = state
    return result


async def get_usuario(usuario_id: str, correlation_id: str = "") -> Optional[dict]:
    """GET /api/usuarios/{id} en Usuarios Service. None si no existe (404).

    Reintenta 3x con backoff exponencial ante timeout/error de red o 5xx.
    Falla rápido (sin llamar al servicio) si el circuit breaker está abierto.
    """
    if not await check_circuit_breaker("usuarios_service"):
        raise CircuitBreakerOpenError("Circuit breaker abierto para usuarios_service")
    client = await get_usuarios_client()
    headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}
    try:
        resp = await _con_reintentos(
            lambda: client.get(f"/api/usuarios/{usuario_id}", headers=headers)
        )
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
    """GET /api/eventos/{id} en Eventos Service. None si no existe (404).

    Reintenta 3x con backoff exponencial ante timeout/error de red o 5xx.
    Falla rápido (sin llamar al servicio) si el circuit breaker está abierto.
    """
    if not await check_circuit_breaker("eventos_service"):
        raise CircuitBreakerOpenError("Circuit breaker abierto para eventos_service")
    client = await get_eventos_client()
    headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}
    try:
        resp = await _con_reintentos(
            lambda: client.get(f"/api/eventos/{evento_id}", headers=headers)
        )
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

    Reintenta 3x con backoff exponencial ante timeout/error de red o 5xx.
    Falla rápido (sin llamar al servicio) si el circuit breaker está abierto.
    """
    if not await check_circuit_breaker("eventos_service"):
        raise CircuitBreakerOpenError("Circuit breaker abierto para eventos_service")
    client = await get_eventos_client()
    headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}
    try:
        resp = await _con_reintentos(
            lambda: client.post(
                f"/api/eventos/{evento_id}/decrementar-inventario",
                json={"categoria": categoria, "cantidad": cantidad},
                headers=headers,
            )
        )
    except httpx.HTTPError:
        record_failure("eventos_service")
        raise
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
