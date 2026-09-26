"""Unit tests for HTTP retry behavior in http_clients.py (E1)."""
import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services import http_clients


@pytest.fixture(autouse=True)
def _no_real_sleep():
    """Evita esperar los backoffs reales (0.5s/1s/2s) durante los tests."""
    with patch("src.services.http_clients.asyncio.sleep", new=AsyncMock()) as m:
        yield m


@pytest.fixture(autouse=True)
def _reset_circuit_breaker_state():
    http_clients._circuit_breakers["usuarios_service"] = "closed"
    http_clients._circuit_breakers["eventos_service"] = "closed"
    http_clients._failure_counts["usuarios_service"] = 0
    http_clients._failure_counts["eventos_service"] = 0
    http_clients._circuit_opened_at["usuarios_service"] = 0.0
    http_clients._circuit_opened_at["eventos_service"] = 0.0
    http_clients._half_open_probe_in_flight["usuarios_service"] = False
    http_clients._half_open_probe_in_flight["eventos_service"] = False
    yield


def _ok_response(json_body=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = json_body or {}
    resp.raise_for_status = MagicMock()
    return resp


def _server_error_response():
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 503
    resp.request = MagicMock()
    return resp


@pytest.mark.unit
class TestConReintentos:
    async def test_reintenta_ante_timeout_y_luego_exito(self, _no_real_sleep):
        """Falla 2 veces con timeout, la 3ra request tiene exito -> no propaga error."""
        llamada = AsyncMock(
            side_effect=[
                httpx.ConnectTimeout("timeout"),
                httpx.ConnectTimeout("timeout"),
                _ok_response({"ok": True}),
            ]
        )
        resp = await http_clients._con_reintentos(llamada)
        assert resp.status_code == 200
        assert llamada.call_count == 3
        assert _no_real_sleep.call_count == 2

    async def test_reintenta_ante_5xx_y_luego_exito(self, _no_real_sleep):
        llamada = AsyncMock(side_effect=[_server_error_response(), _ok_response()])
        resp = await http_clients._con_reintentos(llamada)
        assert resp.status_code == 200
        assert llamada.call_count == 2

    async def test_agota_reintentos_y_propaga_error(self, _no_real_sleep):
        """4 intentos totales (1 + 3 reintentos), todos fallan -> propaga el ultimo error."""
        llamada = AsyncMock(side_effect=httpx.ConnectTimeout("timeout"))
        with pytest.raises(httpx.ConnectTimeout):
            await http_clients._con_reintentos(llamada)
        assert llamada.call_count == 4
        assert _no_real_sleep.call_count == 3

    async def test_no_reintenta_ante_404(self, _no_real_sleep):
        """Un 404 no es un error transitorio: se retorna tal cual, sin reintentar."""
        resp_404 = MagicMock(spec=httpx.Response)
        resp_404.status_code = 404
        llamada = AsyncMock(return_value=resp_404)
        resp = await http_clients._con_reintentos(llamada)
        assert resp.status_code == 404
        assert llamada.call_count == 1
        assert _no_real_sleep.call_count == 0


@pytest.mark.unit
class TestGetUsuarioConReintentos:
    async def test_get_usuario_reintenta_y_recupera(self, _no_real_sleep):
        fake_client = MagicMock()
        fake_client.get = AsyncMock(
            side_effect=[httpx.ConnectTimeout("timeout"), _ok_response({"usuario_id": "x"})]
        )
        with patch.object(http_clients, "get_usuarios_client", AsyncMock(return_value=fake_client)):
            result = await http_clients.get_usuario("some-id")
        assert result == {"usuario_id": "x"}
        assert fake_client.get.call_count == 2

    async def test_get_usuario_agota_reintentos_marca_fallo(self, _no_real_sleep):
        fake_client = MagicMock()
        fake_client.get = AsyncMock(side_effect=httpx.ConnectTimeout("timeout"))
        with patch.object(http_clients, "get_usuarios_client", AsyncMock(return_value=fake_client)):
            with pytest.raises(httpx.HTTPError):
                await http_clients.get_usuario("some-id")
        assert http_clients._failure_counts["usuarios_service"] == 1
