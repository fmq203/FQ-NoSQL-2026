"""Integration test for compensation success rate."""
import pytest
from httpx import AsyncClient
from unittest.mock import ANY, AsyncMock, patch
from uuid import uuid4
from src.main import app


class TestCompensationSuccess:
    """Test compensation 100% success rate (RP-SC-004)."""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    def mock_failure_services(self):
        # Patched at src.chain.validators / src.api.routes.reservas (the
        # actual call sites), not the origin modules where these names are
        # defined - see test_double_booking.py for why patching the origin
        # module doesn't intercept an already-imported name.
        with patch("src.chain.validators.get_usuario", new_callable=AsyncMock) as mock_get_usuario, \
             patch("src.chain.validators.get_evento", new_callable=AsyncMock) as mock_get_evento, \
             patch("src.chain.validators.ejecutar_pagar_y_decrementar", new_callable=AsyncMock) as mock_redis, \
             patch("src.chain.validators.decrementar_inventario_evento", new_callable=AsyncMock) as mock_decrementar_evento, \
             patch("src.chain.validators.incrementar_inventario_evento", new_callable=AsyncMock) as mock_incrementar_evento, \
             patch("src.chain.validators.ejecutar_compensar_pago_inventario", new_callable=AsyncMock) as mock_compensation, \
             patch("src.chain.validators.get_reservas_collection", new_callable=AsyncMock) as mock_mongo, \
             patch("src.chain.validators.insert_event_log", new_callable=AsyncMock) as mock_pg, \
             patch("src.api.routes.reservas.check_idempotency", new_callable=AsyncMock) as mock_idempotency:

            mock_get_usuario.return_value = {"usuario_id": str(uuid4()), "nombre": "Test"}
            mock_get_evento.return_value = {
                "evento_id": str(uuid4()),
                "estado": "publicado",
                "entradas_disponibles": 100,
                "precios": [{"categoria": "general", "precio": 50.0, "disponibles": 100}],
            }
            mock_redis.return_value = {"success": True, "message": "OK"}
            mock_decrementar_evento.return_value = {"disponibles": 99}
            mock_incrementar_evento.return_value = None
            mock_compensation.return_value = {"success": True, "message": "COMPENSACION_OK"}
            mock_pg.return_value = None
            mock_idempotency.return_value = None

            mock_collection = AsyncMock()
            # ConfirmadorReserva checks find_one() first for idempotency; a
            # bare AsyncMock() auto-generates a truthy Mock return value,
            # which would make it think the reservation already exists and
            # short-circuit before ever calling insert_one() - explicitly
            # None so the tests below actually reach insert_one().
            mock_collection.find_one.return_value = None
            mock_mongo.return_value = mock_collection

            yield {
                "mongo": mock_collection,
                "compensation": mock_compensation,
                "incrementar_evento": mock_incrementar_evento,
                "pg": mock_pg,
            }

    @pytest.mark.integration
    async def test_compensation_100_percent_success_mongodb_failure(
        self,
        client: AsyncClient,
        mock_failure_services
    ):
        """Test 100% compensation success when MongoDB fails."""
        # Simulate MongoDB failure after successful payment
        mock_failure_services["mongo"].insert_one.side_effect = Exception("MongoDB down")

        request_data = {
            "usuario_id": str(uuid4()),
            "evento_id": str(uuid4()),
            "cantidad": 1,
            "categoria": "general",
            "metodo_pago": "tarjeta"
        }

        response = await client.post("/api/reservar", json=request_data)

        assert response.status_code == 500

        # Verify both compensations ran: Redis rollback (step 4) and the
        # eventos-service inventory sync revert (also part of step 4's
        # work, from the previous session's inventory-sync commit).
        mock_failure_services["compensation"].assert_called_once_with(
            evento_id=ANY, reserva_id=ANY, cantidad=1
        )
        mock_failure_services["incrementar_evento"].assert_called_once()

        # Verify compensation event was logged
        pg_calls = mock_failure_services["pg"].call_args_list
        event_types = [c.kwargs.get("event_type") or c.args[0] for c in pg_calls]
        assert "COMPENSACION_EJECUTADA" in event_types

    @pytest.mark.integration
    async def test_compensation_atomic_lua_rollback(self, client: AsyncClient):
        """Test Lua atomic rollback on step 4 failure (insufficient inventory)."""
        with patch("src.chain.validators.get_usuario", new_callable=AsyncMock) as mock_get_usuario, \
             patch("src.chain.validators.get_evento", new_callable=AsyncMock) as mock_get_evento, \
             patch("src.chain.validators.ejecutar_pagar_y_decrementar", new_callable=AsyncMock) as mock_redis, \
             patch("src.chain.validators.insert_event_log", new_callable=AsyncMock) as mock_pg, \
             patch("src.services.saga_orchestrator.insert_event_log", new_callable=AsyncMock), \
             patch("src.api.routes.reservas.check_idempotency", new_callable=AsyncMock) as mock_idempotency:

            mock_get_usuario.return_value = {"usuario_id": str(uuid4()), "nombre": "Test"}
            # ValidadorEvento's own check (evento.precios[].disponibles vs
            # cantidad) must pass so the SAGA actually reaches step 4 -
            # otherwise this ends up testing step 3's rejection instead of
            # what it claims to (Redis's atomic rejection at step 4, e.g. a
            # concurrent request winning the race between ValidadorEvento's
            # read and this request's own payment attempt).
            mock_get_evento.return_value = {
                "evento_id": str(uuid4()),
                "estado": "publicado",
                "entradas_disponibles": 10,
                "precios": [{"categoria": "general", "precio": 50.0, "disponibles": 10}],
            }
            # Redis rejects anyway - the Lua script itself never
            # decremented anything, so no compensation is needed
            # (ejecutar_pagar_y_decrementar's own atomicity is the rollback).
            mock_redis.return_value = {"success": False, "message": "INSUFICIENTE: solo hay 1 entradas disponibles"}
            mock_pg.return_value = None
            mock_idempotency.return_value = None

            request_data = {
                "usuario_id": str(uuid4()),
                "evento_id": str(uuid4()),
                "cantidad": 5,
                "categoria": "general",
                "metodo_pago": "tarjeta"
            }

            response = await client.post("/api/reservar", json=request_data)

            assert response.status_code == 409
            data = response.json()
            assert "INSUFICIENTE" in data.get("detail", "")

    @pytest.mark.integration
    async def test_compensation_not_executed_for_pg_failure(
        self,
        client: AsyncClient,
        mock_failure_services
    ):
        """Test compensation NOT executed for PG failure (audit step) - reservation already confirmed."""
        mock_failure_services["mongo"].insert_one.side_effect = None
        mock_failure_services["mongo"].insert_one.return_value = None
        mock_failure_services["mongo"].find_one.return_value = None

        # The real insert_event_log never raises to its caller - it catches
        # its own PG errors internally and just logs a warning (see
        # postgresql.py::insert_event_log). Replicate that contract here,
        # but fail specifically on the SAGA_COMPLETED call (the Auditor
        # step, which runs after the reservation is already confirmed in
        # MongoDB) to prove that failure doesn't roll anything back -
        # Auditor's own except block swallows it exactly like the real
        # function would, so the response should still be 201.
        async def mock_insert_event_log(*args, **kwargs):
            event_type = kwargs.get("event_type") or (args[0] if args else None)
            if event_type == "SAGA_COMPLETED":
                raise Exception("PG down")
            return None

        mock_failure_services["pg"].side_effect = mock_insert_event_log

        request_data = {
            "usuario_id": str(uuid4()),
            "evento_id": str(uuid4()),
            "cantidad": 1,
            "categoria": "general",
            "metodo_pago": "tarjeta"
        }

        response = await client.post("/api/reservar", json=request_data)

        # Should still succeed (201) since the reservation itself was
        # confirmed - audit failure is warning-only.
        assert response.status_code == 201
        mock_failure_services["compensation"].assert_not_called()
        mock_failure_services["incrementar_evento"].assert_not_called()
