"""Unit tests for the Redis Lua scripts (pagar_y_decrementar / compensar_pago)."""
import pytest
from unittest.mock import AsyncMock, patch


class TestLuaScripts:
    """Unit tests for ejecutar_pagar_y_decrementar / ejecutar_compensar_pago_inventario.

    Contrato real (ver src/services/redis_pago.py):
    - pagar_y_decrementar.lua devuelve {status, valor} vía evalsha:
        status=1  -> pago procesado, valor=disponibles restantes
        status=-2 -> inventario insuficiente, valor=disponibles actuales
    - compensar_pago.lua devuelve un entero simple (no una tabla):
        1 -> compensacion ejecutada, 0 -> nada que compensar (idempotente)
    """

    @pytest.fixture
    def mock_redis_client(self):
        client = AsyncMock()
        client.evalsha = AsyncMock()
        client.script_load = AsyncMock(return_value="deadbeef")
        client.ping = AsyncMock(return_value=True)
        return client

    @pytest.mark.unit
    async def test_pagar_y_decrementar_success(self, mock_redis_client):
        from src.services.redis_pago import ejecutar_pagar_y_decrementar

        mock_redis_client.evalsha.return_value = [1, 8]

        with patch("src.services.redis_pago.get_redis_client", return_value=mock_redis_client):
            with patch("src.services.redis_pago.get_sha_pagar", return_value="deadbeef"):
                result = await ejecutar_pagar_y_decrementar(
                    evento_id="evento-123",
                    reserva_id="reserva-456",
                    usuario_id="usuario-123",
                    cantidad=2,
                    monto=100.0,
                    metodo_pago="tarjeta",
                    categoria="general",
                    seed_disponibles=10,
                )

        assert result["success"] is True
        assert result["disponibles"] == 8
        mock_redis_client.evalsha.assert_called_once()

    @pytest.mark.unit
    async def test_pagar_y_decrementar_insufficient_inventory(self, mock_redis_client):
        from src.services.redis_pago import ejecutar_pagar_y_decrementar

        mock_redis_client.evalsha.return_value = [-2, 1]

        with patch("src.services.redis_pago.get_redis_client", return_value=mock_redis_client):
            with patch("src.services.redis_pago.get_sha_pagar", return_value="deadbeef"):
                result = await ejecutar_pagar_y_decrementar(
                    evento_id="evento-123",
                    reserva_id="reserva-456",
                    usuario_id="usuario-123",
                    cantidad=5,  # mas que lo disponible
                    monto=100.0,
                    metodo_pago="tarjeta",
                    categoria="general",
                    seed_disponibles=1,
                )

        assert result["success"] is False
        assert "INSUFICIENTE" in result["message"]
        assert result["disponibles"] == 1

    @pytest.mark.unit
    async def test_compensar_pago_inventario_success(self, mock_redis_client):
        from src.services.redis_pago import ejecutar_compensar_pago_inventario

        mock_redis_client.evalsha.return_value = 1  # entero simple, no tabla

        with patch("src.services.redis_pago.get_redis_client", return_value=mock_redis_client):
            with patch("src.services.redis_pago.get_sha_compensar", return_value="deadbeef"):
                result = await ejecutar_compensar_pago_inventario(
                    evento_id="evento-123",
                    reserva_id="reserva-456",
                    cantidad=2,
                )

        assert result["success"] is True
        mock_redis_client.evalsha.assert_called_once()

    @pytest.mark.unit
    async def test_compensar_pago_inventario_idempotente_sin_pago_previo(self, mock_redis_client):
        """Compensar una reserva que nunca pago (o ya fue compensada) es un no-op, no un error."""
        from src.services.redis_pago import ejecutar_compensar_pago_inventario

        mock_redis_client.evalsha.return_value = 0

        with patch("src.services.redis_pago.get_redis_client", return_value=mock_redis_client):
            with patch("src.services.redis_pago.get_sha_compensar", return_value="deadbeef"):
                result = await ejecutar_compensar_pago_inventario(
                    evento_id="evento-123",
                    reserva_id="reserva-nunca-pago",
                    cantidad=2,
                )

        assert result["success"] is True
        assert "idempotente" in result["message"].lower()

    @pytest.mark.unit
    async def test_pagar_y_decrementar_calls_evalsha_with_categoria_keys(self, mock_redis_client):
        """La clave de inventario debe incluir la categoria (cada categoria tiene su propio cupo)."""
        from src.services.redis_pago import ejecutar_pagar_y_decrementar

        mock_redis_client.evalsha.return_value = [1, 2]

        with patch("src.services.redis_pago.get_redis_client", return_value=mock_redis_client):
            with patch("src.services.redis_pago.get_sha_pagar", return_value="deadbeef"):
                for i in range(3):
                    await ejecutar_pagar_y_decrementar(
                        evento_id="evento-atomic",
                        reserva_id=f"reserva-{i}",
                        usuario_id="usuario-123",
                        cantidad=1,
                        monto=50.0,
                        metodo_pago="tarjeta",
                        categoria="vip",
                        seed_disponibles=3,
                    )

        assert mock_redis_client.evalsha.call_count == 3
        called_keys = mock_redis_client.evalsha.call_args_list[0].args
        assert "evento:evento-atomic:categoria:vip:disponibles" in called_keys
