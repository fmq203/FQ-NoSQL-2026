"""Cliente HTTP registrar_compra_usuario (historial en usuarios-service)."""
import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services import http_clients


@pytest.fixture(autouse=True)
def _estado_limpio():
    for name in ("usuarios_service", "eventos_service"):
        http_clients._circuit_breakers[name] = "closed"
        http_clients._failure_counts[name] = 0
        http_clients._circuit_opened_at[name] = 0.0
        http_clients._half_open_probe_in_flight[name] = False
    yield


def _resp(status=201, body=None):
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.json.return_value = body or {"registrada": True}
    r.raise_for_status = MagicMock()
    return r


KW = dict(usuario_id="u1", reserva_id="r1", evento_id="e1", evento_nombre="Rock", entradas=2, total_pagado=100.0)


@pytest.mark.unit
class TestRegistrarCompraUsuario:
    async def test_postea_el_payload_esperado(self):
        client = MagicMock()
        client.post = AsyncMock(return_value=_resp())
        with patch.object(http_clients, "get_usuarios_client", AsyncMock(return_value=client)):
            out = await http_clients.registrar_compra_usuario(**KW, correlation_id="c1")

        assert out == {"registrada": True}
        args, kwargs = client.post.call_args
        assert args[0] == "/api/usuarios/u1/historial"
        assert kwargs["json"] == {
            "reserva_id": "r1", "evento_id": "e1", "evento_nombre": "Rock",
            "entradas": 2, "total_pagado": 100.0, "estado": "confirmada",
        }
        assert kwargs["headers"] == {"X-Correlation-ID": "c1"}

    async def test_circuit_breaker_abierto_falla_rapido(self):
        import time
        http_clients._circuit_breakers["usuarios_service"] = "open"
        http_clients._circuit_opened_at["usuarios_service"] = time.monotonic()
        client = MagicMock()
        client.post = AsyncMock()
        with patch.object(http_clients, "get_usuarios_client", AsyncMock(return_value=client)):
            with pytest.raises(http_clients.CircuitBreakerOpenError):
                await http_clients.registrar_compra_usuario(**KW)
        client.post.assert_not_called()

    async def test_reintenta_y_luego_propaga_si_sigue_fallando(self):
        client = MagicMock()
        client.post = AsyncMock(side_effect=httpx.ConnectError("caido"))
        with patch.object(http_clients, "get_usuarios_client", AsyncMock(return_value=client)), \
             patch("src.services.http_clients.asyncio.sleep", new=AsyncMock()):
            with pytest.raises(httpx.HTTPError):
                await http_clients.registrar_compra_usuario(**KW)
        assert client.post.call_count == 4  # 1 intento + 3 reintentos
        assert http_clients._failure_counts["usuarios_service"] == 1
