"""Unit tests for Lua scripts."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestLuaScripts:
    """Unit tests for Lua scripts pago_y_decrementar and compensar_pago_inventario."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create mock Redis client for testing."""
        client = AsyncMock()
        client.evalsha = AsyncMock()
        client.set = AsyncMock()
        client.get = AsyncMock()
        client.keys = AsyncMock()
        client.hgetall = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.mark.unit
    async def test_pagar_y_decrementar_success(self, mock_redis_client):
        """Test pago_y_decrementar.lua executes successfully with sufficient inventory."""
        from src.services.redis_pago import ejecutar_pagar_y_decrementar

        # Setup mock
        mock_redis_client.evalsha.return_value = [1, "OK"]
        mock_redis_client.get.return_value = "10"
        mock_redis_client.keys.return_value = ["pago:reserva-456"]
        mock_redis_client.hgetall.return_value = {
            "reserva_id": "reserva-456",
            "cantidad": "2",
            "metodo_pago": "tarjeta",
            "estado": "confirmado"
        }

        # Patch the redis client getter
        with patch("src.services.redis_pago.get_redis_client", return_value=mock_redis_client):
            with patch("src.services.redis_pago.register_lua_scripts"):
                # Execute script
                result = await ejecutar_pagar_y_decrementar(
                    evento_id="evento-123",
                    reserva_id="reserva-456",
                    usuario_id="usuario-123",
                    cantidad=2,
                    monto=100.0,
                    metodo_pago="tarjeta"
                )

        # Verify result
        assert result["success"] is True
        assert result["message"] == "OK"
        mock_redis_client.evalsha.assert_called_once()

    @pytest.mark.unit
    async def test_pagar_y_decrementar_insufficient_inventory(self, mock_redis_client):
        """Test pago_y_decrementar.lua fails with insufficient inventory."""
        from src.services.redis_pago import ejecutar_pagar_y_decrementar

        # Setup mock
        mock_redis_client.evalsha.return_value = [0, "INVENTARIO_INSUFICIENTE"]

        with patch("src.services.redis_pago.get_redis_client", return_value=mock_redis_client):
            with patch("src.services.redis_pago.register_lua_scripts"):
                result = await ejecutar_pagar_y_decrementar(
                    evento_id="evento-123",
                    reserva_id="reserva-456",
                    usuario_id="usuario-123",
                    cantidad=5,  # More than available
                    monto=100.0,
                    metodo_pago="tarjeta"
                )

        assert result["success"] is False
        assert "INSUFICIENTE" in result["message"]
        mock_redis_client.evalsha.assert_called_once()

    @pytest.mark.unit
    async def test_compensar_pago_inventario_success(self, mock_redis_client):
        """Test compensar_pago_inventario.lua executes successfully."""
        from src.services.redis_pago import ejecutar_compensar_pago_inventario

        # Setup mock
        mock_redis_client.evalsha.return_value = [1, "COMPENSACION_OK"]
        mock_redis_client.get.return_value = "8"
        mock_redis_client.hgetall.return_value = {}

        with patch("src.services.redis_pago.get_redis_client", return_value=mock_redis_client):
            with patch("src.services.redis_pago.register_lua_scripts"):
                result = await ejecutar_compensar_pago_inventario(
                    evento_id="evento-123",
                    reserva_id="reserva-456",
                    cantidad=2
                )

        assert result["success"] is True
        assert result["message"] == "COMPENSACION_OK"
        mock_redis_client.evalsha.assert_called_once()

    @pytest.mark.unit
    async def test_lua_scripts_atomicity(self, mock_redis_client):
        """Test that Lua scripts execute atomically - mock version."""
        # Since we're mocking, we can't test real atomicity, but we can verify
        # the script is called with correct parameters
        from src.services.redis_pago import ejecutar_pagar_y_decrementar

        mock_redis_client.evalsha.return_value = [1, "OK"]

        with patch("src.services.redis_pago.get_redis_client", return_value=mock_redis_client):
            with patch("src.services.redis_pago.register_lua_scripts"):
                # Simulate multiple concurrent requests
                results = []
                for i in range(3):
                    result = await ejecutar_pagar_y_decrementar(
                        evento_id="evento-atomic",
                        reserva_id=f"reserva-{i}",
                        usuario_id="usuario-123",
                        cantidad=1,
                        monto=50.0,
                        metodo_pago="tarjeta"
                    )
                    results.append(result)

        # All should succeed in mock
        assert len(results) == 3
        assert all(r["success"] for r in results)
        assert mock_redis_client.evalsha.call_count == 3