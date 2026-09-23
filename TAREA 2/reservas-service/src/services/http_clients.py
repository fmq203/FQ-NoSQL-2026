"""HTTP clients for external services (Usuarios, Eventos)."""
import os
import time
from typing import Optional, Dict, Any
import httpx
from httpx import AsyncClient
import logging

from ..services.metrics import record_http_request_duration

logger = logging.getLogger(__name__)

# Global clients
_usuarios_client: Optional[AsyncClient] = None
_eventos_client: Optional[AsyncClient] = None

# Circuit breaker state
_cb_state = {
    "usuarios": {"failures": 0, "state": "closed", "last_failure": None},
    "eventos": {"failures": 0, "state": "closed", "last_failure": None},
}

CB_FAILURE_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))
CB_HALF_OPEN_TIMEOUT = int(os.getenv("CB_HALF_OPEN_TIMEOUT", "30"))


async def get_usuarios_client() -> AsyncClient:
    """Get or create Usuarios Service HTTP client."""
    global _usuarios_client
    if _usuarios_client is None:
        base_url = os.getenv("USUARIOS_SERVICE_URL", "http://localhost:8001")
        _usuarios_client = AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(5.0, connect=2.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _usuarios_client


async def get_eventos_client() -> AsyncClient:
    """Get or create Eventos Service HTTP client."""
    global _eventos_client
    if _eventos_client is None:
        base_url = os.getenv("EVENTOS_SERVICE_URL", "http://localhost:8002")
        _eventos_client = AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(5.0, connect=2.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _eventos_client


def _check_circuit_breaker(service: str) -> bool:
    """Check if circuit breaker allows request."""
    state = _cb_state[service]["state"]
    if state == "closed":
        return True
    if state == "open":
        # Check if half-open timeout has passed
        import time
        if _cb_state[service]["last_failure"]:
            if time.time() - _cb_state[service]["last_failure"] > CB_HALF_OPEN_TIMEOUT:
                _cb_state[service]["state"] = "half-open"
                return True
        return False
    # half-open allows one request
    return True


def _record_success(service: str) -> None:
    """Record successful request."""
    _cb_state[service]["failures"] = 0
    _cb_state[service]["state"] = "closed"


def _record_failure(service: str) -> None:
    """Record failed request and update circuit breaker state."""
    import time
    _cb_state[service]["failures"] += 1
    _cb_state[service]["last_failure"] = time.time()
    if _cb_state[service]["failures"] >= CB_FAILURE_THRESHOLD:
        _cb_state[service]["state"] = "open"
        logger.warning(f"Circuit breaker OPEN for {service}")


async def get_usuario(usuario_id: str, correlation_id: str = "") -> Optional[Dict]:
    """Get usuario by ID from Usuarios Service."""
    client = await get_usuarios_client()
    headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}

    if not _check_circuit_breaker("usuarios"):
        raise Exception("Usuarios Service circuit breaker open")

    start_time = time.perf_counter()
    try:
        response = await client.get(f"/api/usuarios/{usuario_id}", headers=headers)
        duration = time.perf_counter() - start_time
        record_http_request_duration("GET", "/api/usuarios/{usuario_id}", response.status_code, duration)
        if response.status_code == 200:
            _record_success("usuarios")
            return response.json()
        elif response.status_code == 404:
            _record_success("usuarios")
            return None
        else:
            _record_failure("usuarios")
            return None
    except Exception as e:
        duration = time.perf_counter() - start_time
        record_http_request_duration("GET", "/api/usuarios/{usuario_id}", 500, duration)
        _record_failure("usuarios")
        logger.error(f"Error calling Usuarios Service: {e}")
        raise


async def get_evento(evento_id: str, correlation_id: str = "") -> Optional[Dict]:
    """Get evento by ID from Eventos Service."""
    client = await get_eventos_client()
    headers = {"X-Correlation-ID": correlation_id} if correlation_id else {}

    if not _check_circuit_breaker("eventos"):
        raise Exception("Eventos Service circuit breaker open")

    start_time = time.perf_counter()
    try:
        response = await client.get(f"/api/eventos/{evento_id}", headers=headers)
        duration = time.perf_counter() - start_time
        record_http_request_duration("GET", "/api/eventos/{evento_id}", response.status_code, duration)
        if response.status_code == 200:
            _record_success("eventos")
            return response.json()
        elif response.status_code == 404:
            _record_success("eventos")
            return None
        else:
            _record_failure("eventos")
            return None
    except Exception as e:
        duration = time.perf_counter() - start_time
        record_http_request_duration("GET", "/api/eventos/{evento_id}", 500, duration)
        _record_failure("eventos")
        logger.error(f"Error calling Eventos Service: {e}")
        raise


async def close_http_clients() -> None:
    """Close HTTP clients."""
    global _usuarios_client, _eventos_client
    if _usuarios_client:
        await _usuarios_client.aclose()
        _usuarios_client = None
    if _eventos_client:
        await _eventos_client.aclose()
        _eventos_client = None


def get_circuit_breaker_state() -> Dict:
    """Get circuit breaker states for health check."""
    return {
        "usuarios_service": _cb_state["usuarios"]["state"],
        "eventos_service": _cb_state["eventos"]["state"],
    }