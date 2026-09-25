import httpx
from src.config import get_settings
import logging
import asyncio
from typing import Optional

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


async def record_success(service_name: str):
    """Registrar éxito y resetear contador."""
    _failure_counts[service_name] = 0
    if _circuit_breakers.get(service_name) == "half-open":
        _circuit_breakers[service_name] = "closed"
        logger.info(f"Circuit breaker {service_name} cerrado")


async def record_failure(service_name: str):
    """Registrar fallo y abrir circuit breaker si es necesario."""
    _failure_counts[service_name] = _failure_counts.get(service_name, 0) + 1
    if _failure_counts[service_name] >= 5:
        _circuit_breakers[service_name] = "open"
        logger.warning(f"Circuit breaker {service_name} ABIERTO")


def get_circuit_breaker_state() -> dict:
    return _circuit_breakers.copy()


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