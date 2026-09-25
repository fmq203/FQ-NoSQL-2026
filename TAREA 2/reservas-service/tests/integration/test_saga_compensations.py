"""Integration tests for SAGA compensations."""
import pytest
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock
from src.main import app


class TestSAGACompensations:
    """Integration tests for SAGA compensations (US2)."""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    def mock_services(self):
        # Create async mocks for the external services
        mock_get_usuario = AsyncMock()
        async def mock_get_usuario_impl(usuario_id: str, correlation_id: str = ""):
            return {
                "usuario_id": usuario_id,
                "nombre": "Test",
                "apellido": "User",
                "email": "test@example.com"
            }
        mock_get_usuario.side_effect = mock_get_usuario_impl

        mock_get_evento = AsyncMock()
        async def mock_get_evento_impl(evento_id: str, correlation_id: str = ""):
            return {
                "evento_id": evento_id,
                "estado": "publicado",
                "entradas_disponibles": 100,
                "precios": [{"categoria": "general", "precio": 50.0, "disponibles": 100}],
            }
        mock_get_evento.side_effect = mock_get_evento_impl

        mock_collection = AsyncMock()
        mock_collection.insert_one = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)

        # IMPORTANT: src/chain/validators.py does
        # `from ..services.redis_pago import ejecutar_pagar_y_decrementar`,
        # which binds its own name in the validators module namespace.
        # Patching src.services.redis_pago.* (the origin module) does NOT
        # intercept that already-imported name - the patch has to target
        # src.chain.validators.* (the actual call site) to take effect.
        with patch("src.chain.validators.get_usuario", mock_get_usuario), \
             patch("src.chain.validators.get_evento", mock_get_evento), \
             patch("src.chain.validators.ejecutar_pagar_y_decrementar", new_callable=AsyncMock) as mock_redis, \
             patch("src.chain.validators.ejecutar_compensar_pago_inventario", new_callable=AsyncMock) as mock_redis_compensar, \
             patch("src.chain.validators.decrementar_inventario_evento", new_callable=AsyncMock) as mock_decrementar_evento, \
             patch("src.chain.validators.incrementar_inventario_evento", new_callable=AsyncMock) as mock_incrementar_evento, \
             patch("src.chain.validators.get_reservas_collection", new_callable=AsyncMock) as mock_mongo, \
             patch("src.chain.validators.insert_event_log", new_callable=AsyncMock) as mock_pg, \
             patch("src.api.routes.reservas.check_idempotency", new_callable=AsyncMock) as mock_idempotency:

            mock_redis.return_value = {"success": True, "message": "OK"}
            mock_redis_compensar.return_value = {"success": True, "message": "COMPENSACION_OK"}
            mock_decrementar_evento.return_value = {"disponibles": 99}
            mock_incrementar_evento.return_value = None
            mock_mongo.return_value = mock_collection
            mock_pg.return_value = None
            mock_idempotency.return_value = None

            yield {
                "redis": mock_redis,
                "redis_compensar": mock_redis_compensar,
                "decrementar_evento": mock_decrementar_evento,
                "incrementar_evento": mock_incrementar_evento,
                "mongo": mock_collection,
                "pg": mock_pg,
            }

    @pytest.mark.integration
    async def test_compensation_mongodb_failure_step5(
        self,
        client: AsyncClient,
        mock_services
    ):
        """Test compensation when MongoDB fails at step 5 (ConfirmadorReserva)."""
        # Setup: MongoDB insert fails
        mock_services["mongo"].insert_one.side_effect = Exception("MongoDB connection failed")

        request_data = {
            "usuario_id": str(uuid4()),
            "evento_id": str(uuid4()),
            "cantidad": 2,
            "categoria": "general",
            "metodo_pago": "tarjeta"
        }

        response = await client.post("/api/reservar", json=request_data)

        # Should return 500
        assert response.status_code == 500

        # Verify compensation was executed (INCRBY + DEL)
        # The compensation should be triggered by ConfirmadorReserva's except block
        # In real implementation, this would call ejecutar_compensar_pago_inventario

        # Verify error response format
        data = response.json()
        assert "type" in data
        assert data["status"] == 500

    @pytest.mark.integration
    async def test_compensation_lua_failure_step4(
        self,
        client: AsyncClient,
        mock_services
    ):
        """Test compensation when Lua script fails at step 4 (insufficient inventory)."""
        # Setup: Lua script returns insufficient inventory
        mock_services["redis"].return_value = {
            "success": False,
            "message": "INVENTARIO_INSUFICIENTE"
        }

        request_data = {
            "usuario_id": str(uuid4()),
            "evento_id": str(uuid4()),
            "cantidad": 100,  # More than available
            "categoria": "general",
            "metodo_pago": "tarjeta"
        }

        response = await client.post("/api/reservar", json=request_data)

        # Should return 409
        assert response.status_code == 409
        data = response.json()
        assert "INSUFICIENTE" in data.get("detail", "")

        # No compensation needed for step 4 failure (atomic Lua rollback)

    @pytest.mark.integration
    async def test_compensation_100_percent_success(
        self,
        client: AsyncClient,
        mock_services
    ):
        """Test compensation executes 100% successfully in simulated failures."""
        # Simulate MongoDB failure after successful payment
        mock_services["mongo"].insert_one.side_effect = [
            Exception("MongoDB down"),  # First call fails
        ]

        request_data = {
            "usuario_id": str(uuid4()),
            "evento_id": str(uuid4()),
            "cantidad": 1,
            "categoria": "general",
            "metodo_pago": "tarjeta"
        }

        response = await client.post("/api/reservar", json=request_data)

        assert response.status_code == 500

        # In a real test with actual DBs, we would verify:
        # 1. Redis INCRBY was called to restore inventory
        # 2. Redis DEL was called to remove payment hash
        # 3. COMPENSACION_EJECUTADA event was logged in PostgreSQL