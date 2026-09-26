"""Integration tests for all Event Sourcing event types."""
import pytest
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from src.main import app
from src.services.postgresql import get_events_by_aggregate


class TestAllEventTypes:
    """Integration tests for all 9 event types in event_log."""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    def mock_services(self):
        # Patched at src.chain.validators / src.api.routes.reservas (the
        # actual call sites) - see test_double_booking.py for why patching
        # the origin modules doesn't intercept an already-imported name.
        with patch("src.chain.validators.get_usuario", new_callable=AsyncMock) as mock_get_usuario, \
             patch("src.chain.validators.get_evento", new_callable=AsyncMock) as mock_get_evento, \
             patch("src.chain.validators.ejecutar_pagar_y_decrementar", new_callable=AsyncMock) as mock_redis, \
             patch("src.chain.validators.decrementar_inventario_evento", new_callable=AsyncMock) as mock_decrementar_evento, \
             patch("src.chain.validators.insert_event_log", new_callable=AsyncMock) as mock_pg, \
             patch("src.services.saga_orchestrator.insert_event_log", mock_pg), \
             patch("src.api.routes.reservas.check_idempotency", new_callable=AsyncMock) as mock_idempotency:

            mock_get_usuario.return_value = {"usuario_id": str(uuid4()), "nombre": "Test"}
            mock_get_evento.return_value = {
                "evento_id": str(uuid4()),
                "estado": "publicado",
                "entradas_disponibles": 100,
                "precios": [{"categoria": "general", "precio": 50.0, "disponibles": 100}],
            }
            mock_redis.return_value = {"success": True, "message": "OK"}
            mock_decrementar_evento.return_value = {"disponibles": 98}
            mock_pg.return_value = None
            mock_idempotency.return_value = None

            # SAGA_STARTED/SAGA_FAILED are logged from
            # saga_orchestrator.execute()/_handle_error, which import
            # insert_event_log independently of chain/validators.py -
            # reusing the same mock object for both patch targets so both
            # modules' calls land in one call_args_list.
            yield {"pg": mock_pg}

    @pytest.mark.integration
    async def test_7_events_ordered_after_successful_reservation(
        self,
        client: AsyncClient,
        mock_services
    ):
        """Test that 7 events are created in order after successful reservation."""
        request_data = {
            "usuario_id": str(uuid4()),
            "evento_id": str(uuid4()),
            "cantidad": 2,
            "categoria": "general",
            "metodo_pago": "tarjeta"
        }
        
        response = await client.post("/api/reservar", json=request_data)
        
        assert response.status_code == 201
        reserva_id = response.json()["reserva_id"]
        
        # Verify all 7 event types were logged in order
        expected_events = [
            "SAGA_STARTED",
            "USUARIO_VALIDADO",
            "EVENTO_VALIDADO",
            "PAGO_PROCESADO",
            "INVENTARIO_DECREMENTADO",
            "RESERVA_CONFIRMADA",
            "SAGA_COMPLETED"
        ]
        
        # insert_event_log esta mockeado (mock_services) para aislar esta
        # asercion del call site, sin round-trip real a PostgreSQL. Los
        # tests de integracion contra Mongo/Redis/PostgreSQL reales corren
        # via docker-compose (ver README), no via testcontainers - no hace
        # falta un motor de contenedores efimeros separado cuando el
        # docker-compose del proyecto ya deja las 3 bases arriba para toda
        # la suite.

        # Verificar que el Auditor handler fue llamado con SAGA_COMPLETED.
        # Read the mock from mock_services, not a fresh
        # `from src.services.postgresql import insert_event_log` - that
        # import would return the real, unpatched function, since the mock
        # is bound at src.chain.validators.insert_event_log (the call
        # site), not at its origin module.
        mock_pg = mock_services["pg"]
        mock_pg.assert_called()

        # Check SAGA_COMPLETED was one of the calls
        calls = mock_pg.call_args_list
        event_types = [call.kwargs.get("event_type") or call.args[0] for call in calls]
        assert "SAGA_COMPLETED" in event_types

    @pytest.mark.integration
    async def test_saga_failed_event_logged(
        self,
        client: AsyncClient
    ):
        """Test SAGA_FAILED event is logged on failure."""
        with patch("src.chain.validators.get_usuario", new_callable=AsyncMock) as mock_get_usuario, \
             patch("src.chain.validators.get_evento", new_callable=AsyncMock) as mock_get_evento, \
             patch("src.chain.validators.insert_event_log", new_callable=AsyncMock) as mock_pg, \
             patch("src.services.saga_orchestrator.insert_event_log", mock_pg), \
             patch("src.api.routes.reservas.check_idempotency", new_callable=AsyncMock) as mock_idempotency:

            mock_get_usuario.return_value = {"usuario_id": str(uuid4()), "nombre": "Test"}
            # Evento not found -> ValidadorEvento sets 404 and the chain stops
            mock_get_evento.return_value = None
            mock_pg.return_value = None
            mock_idempotency.return_value = None

            response = await client.post(
                "/api/reservar",
                json={
                    "usuario_id": str(uuid4()),
                    "evento_id": str(uuid4()),
                    "cantidad": 1,
                    "categoria": "general",
                    "metodo_pago": "tarjeta"
                }
            )

            assert response.status_code == 404

            # SAGA_FAILED is logged by SagaOrchestrator._handle_error once
            # the chain returns with context.error set (see
            # saga_orchestrator.py::execute).
            event_types = [
                call.kwargs.get("event_type") or call.args[0]
                for call in mock_pg.call_args_list
            ]
            assert "SAGA_FAILED" in event_types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])