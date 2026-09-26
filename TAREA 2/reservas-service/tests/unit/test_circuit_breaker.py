"""Unit tests for the circuit breaker state machine in http_clients.py (E2).

Estados por spec.md ("Circuit Breaker State Machine"):
- Closed: pasa. Open tras 5 fallos consecutivos.
- Open: falla rapido (503). Tras 30s -> Half-Open.
- Half-Open: 1 request de prueba a la vez. Exito -> Closed. Fallo -> Open.
"""
import time
import pytest
from unittest.mock import AsyncMock

from src.services import http_clients


@pytest.fixture(autouse=True)
def _reset_state():
    for name in ("usuarios_service", "eventos_service"):
        http_clients._circuit_breakers[name] = "closed"
        http_clients._failure_counts[name] = 0
        http_clients._circuit_opened_at[name] = 0.0
        http_clients._half_open_probe_in_flight[name] = False
    yield


@pytest.mark.unit
class TestCircuitBreakerStateMachine:
    async def test_closed_permite_requests(self):
        assert await http_clients.check_circuit_breaker("usuarios_service") is True

    async def test_5_fallos_consecutivos_abre_el_breaker(self):
        for _ in range(5):
            http_clients.record_failure("usuarios_service")
        assert http_clients._circuit_breakers["usuarios_service"] == "open"

    async def test_menos_de_5_fallos_no_abre(self):
        for _ in range(4):
            http_clients.record_failure("usuarios_service")
        assert http_clients._circuit_breakers["usuarios_service"] == "closed"
        assert await http_clients.check_circuit_breaker("usuarios_service") is True

    async def test_open_falla_rapido_antes_de_30s(self):
        http_clients._circuit_breakers["usuarios_service"] = "open"
        http_clients._circuit_opened_at["usuarios_service"] = time.monotonic()
        assert await http_clients.check_circuit_breaker("usuarios_service") is False

    async def test_open_transiciona_a_half_open_tras_30s(self):
        http_clients._circuit_breakers["usuarios_service"] = "open"
        http_clients._circuit_opened_at["usuarios_service"] = time.monotonic() - 31
        assert await http_clients.check_circuit_breaker("usuarios_service") is True
        assert http_clients._circuit_breakers["usuarios_service"] == "half-open"

    async def test_half_open_solo_permite_un_probe_a_la_vez(self):
        http_clients._circuit_breakers["usuarios_service"] = "open"
        http_clients._circuit_opened_at["usuarios_service"] = time.monotonic() - 31
        assert await http_clients.check_circuit_breaker("usuarios_service") is True
        # Una segunda request concurrente mientras el probe esta en vuelo: rechazada.
        assert await http_clients.check_circuit_breaker("usuarios_service") is False

    async def test_half_open_exito_cierra_el_breaker(self):
        http_clients._circuit_breakers["usuarios_service"] = "half-open"
        http_clients._half_open_probe_in_flight["usuarios_service"] = True
        http_clients.record_success("usuarios_service")
        assert http_clients._circuit_breakers["usuarios_service"] == "closed"
        assert http_clients._failure_counts["usuarios_service"] == 0

    async def test_half_open_fallo_reabre_inmediatamente(self):
        http_clients._circuit_breakers["usuarios_service"] = "half-open"
        http_clients._half_open_probe_in_flight["usuarios_service"] = True
        http_clients.record_failure("usuarios_service")
        assert http_clients._circuit_breakers["usuarios_service"] == "open"

    async def test_get_circuit_breaker_state_reporta_half_open_tras_30s(self):
        """Reporting es de solo lectura: no muta el estado real ni el probe flag."""
        http_clients._circuit_breakers["eventos_service"] = "open"
        http_clients._circuit_opened_at["eventos_service"] = time.monotonic() - 31
        state = http_clients.get_circuit_breaker_state()
        assert state["eventos_service"] == "half-open"
        assert http_clients._circuit_breakers["eventos_service"] == "open"
        assert http_clients._half_open_probe_in_flight["eventos_service"] is False


@pytest.mark.unit
class TestGetUsuarioFallaRapidoConBreakerAbierto:
    async def test_no_llama_al_servicio_si_breaker_abierto(self, monkeypatch):
        http_clients._circuit_breakers["usuarios_service"] = "open"
        http_clients._circuit_opened_at["usuarios_service"] = time.monotonic()
        fake_client = AsyncMock()
        monkeypatch.setattr(
            http_clients, "get_usuarios_client", AsyncMock(return_value=fake_client)
        )
        with pytest.raises(http_clients.CircuitBreakerOpenError):
            await http_clients.get_usuario("some-id")
        fake_client.get.assert_not_called()
