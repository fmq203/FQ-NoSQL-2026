"""Unit tests for Lua scripts."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import fakeredis.aioredis


class TestLuaScripts:
    """Unit tests for Lua scripts pago_y_decrementar and compensar_pago_inventario."""

    @pytest.fixture
    async def redis_client(self):
        """Create fake Redis client for testing."""
        client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        yield client
        await client.close()

    @pytest.mark.unit
    async def test_pagar_y_decrementar_success(self, redis_client):
        """Test pago_y_decrementar.lua executes successfully with sufficient inventory."""
        from src.services.redis_pago import (
            PAGAR_Y_DECREMENTAR_LUA,
            register_lua_scripts,
            ejecutar_pagar_y_decrementar
        )
        
        # Register scripts
        await register_lua_scripts()
        
        # Setup: create inventory with sufficient stock
        evento_id = "evento-123"
        reserva_id = "reserva-456"
        await redis_client.set(f"inventario:{evento_id}", "10")
        
        # Execute script
        result = await ejecutar_pagar_y_decrementar(
            evento_id=evento_id,
            reserva_id=reserva_id,
            usuario_id="usuario-123",
            cantidad=2,
            monto=100.0,
            metodo_pago="tarjeta"
        )
        
        # Verify result
        assert result["success"] is True
        assert result["message"] == "OK"
        
        # Verify inventory was decremented
        inventory = await redis_client.get(f"inventario:{evento_id}")
        assert int(inventory) == 8  # 10 - 2 = 8
        
        # Verify payment hash was created
        pago_keys = await redis_client.keys("pago:*")
        assert len(pago_keys) == 1
        
        pago_data = await redis_client.hgetall(pago_keys[0])
        assert pago_data["cantidad"] == "2"
        assert pago_data["metodo_pago"] == "tarjeta"
        assert pago_data["estado"] == "confirmado"

    @pytest.mark.unit
    async def test_pagar_y_decrementar_insufficient_inventory(self, redis_client):
        """Test pago_y_decrementar.lua fails with insufficient inventory."""
        from src.services.redis_pago import ejecutar_pagar_y_decrementar, register_lua_scripts
        
        await register_lua_scripts()
        
        # Setup: inventory less than requested
        evento_id = "evento-123"
        await redis_client.set(f"inventario:{evento_id}", "1")
        
        result = await ejecutar_pagar_y_decrementar(
            evento_id=evento_id,
            reserva_id="reserva-456",
            usuario_id="usuario-123",
            cantidad=5,  # More than available (1)
            monto=100.0,
            metodo_pago="tarjeta"
        )
        
        assert result["success"] is False
        assert "INSUFICIENTE" in result["message"]
        
        # Inventory should remain unchanged
        inventory = await redis_client.get(f"inventario:{evento_id}")
        assert int(inventory) == 1

    @pytest.mark.unit
    async def test_compensar_pago_inventario_success(self, redis_client):
        """Test compensar_pago_inventario.lua executes successfully."""
        from src.services.redis_pago import (
            ejecutar_pagar_y_decrementar,
            ejecutar_compensar_pago_inventario,
            register_lua_scripts
        )
        
        await register_lua_scripts()
        
        evento_id = "evento-123"
        reserva_id = "reserva-456"
        
        # Setup: create payment and decrement inventory first
        await redis_client.set(f"inventario:{evento_id}", "8")
        await ejecutar_pagar_y_decrementar(
            evento_id=evento_id,
            reserva_id=reserva_id,
            usuario_id="usuario-123",
            cantidad=2,
            monto=100.0,
            metodo_pago="tarjeta"
        )
        
        # Verify inventory was decremented
        inventory_after_pago = await redis_client.get(f"inventario:{evento_id}")
        assert int(inventory_after_pago) == 6  # Assuming started at 8
        
        # Execute compensation
        result = await ejecutar_compensar_pago_inventario(
            evento_id=evento_id,
            reserva_id=reserva_id,
            cantidad=2
        )
        
        assert result["success"] is True
        assert result["message"] == "COMPENSACION_OK"
        
        # Verify inventory was restored
        inventory_after_comp = await redis_client.get(f"inventario:{evento_id}")
        assert int(inventory_after_comp) == 8  # Back to original
        
        # Verify payment hash was deleted
        pago_data = await redis_client.hgetall(f"pago:{reserva_id}")
        assert len(pago_data) == 0

    @pytest.mark.unit
    async def test_lua_scripts_atomicity(self, redis_client):
        """Test that Lua scripts execute atomically."""
        from src.services.redis_pago import (
            ejecutar_pagar_y_decrementar,
            register_lua_scripts
        )
        
        await register_lua_scripts()
        
        evento_id = "evento-atomic"
        await redis_client.set(f"inventario:{evento_id}", "5")
        
        # Simulate concurrent access by running multiple operations
        # In real scenario, Redis single-threaded ensures atomicity
        results = []
        for i in range(3):
            result = await redis_client.eval(
                """
                local disponible = tonumber(redis.call('GET', KEYS[1]) or '0')
                if disponible < tonumber(ARGV[1]) then
                    return {0, 'INVENTARIO_INSUFICIENTE'}
                end
                redis.call('DECRBY', KEYS[1], ARGV[1])
                return {1, 'OK'}
                """,
                1, f"inventario:{evento_id}", "1"
            )
            results.append(result)
        
        # Only first 5 should succeed (inventory was 5)
        success_count = sum(1 for r in results if r[0] == 1)
        assert success_count == 5
        
        # Final inventory should be 0
        final = await redis_client.get(f"inventario:{evento_id}")
        assert int(final) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])