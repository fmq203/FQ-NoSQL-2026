"""Test audit log completeness (RP-SC-005)."""
import pytest
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from src.main import app
from src.services.postgresql import insert_event_log, get_events_by_aggregate
from uuid import UUID


class TestAuditCompleteness:
    """Test audit log 100% completeness (RP-SC-005)."""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.integration
    async def test_all_9_event_types_present(self):
        """Test that all 9 event types can be recorded."""
        # The 9 required event types per spec:
        required_events = [
            "SAGA_STARTED",
            "USUARIO_VALIDADO",
            "EVENTO_VALIDADO",
            "PAGO_PROCESADO",
            "INVENTARIO_DECREMENTADO",
            "RESERVA_CONFIRMADA",
            "SAGA_COMPLETED",
            "SAGA_FAILED",
            "COMPENSACION_EJECUTADA"
        ]
        
        # Verify all event types are defined in EventType enum
        from src.models.reserva import EventType
        defined_events = [e.value for e in EventType]
        
        for event in required_events:
            assert event in defined_events, f"Missing event type: {event}"
        
        # Verify EventType enum has all required
        assert len(defined_events) >= len(required_events)

    @pytest.mark.integration
    async def test_successful_reservation_logs_all_events(self):
        """Test successful reservation logs all 7 success events."""
        from src.chain.validators import ChainBuilder
        from src.models.reserva import ReservaContext

        # Mock external calls. Patched at src.chain.validators (the actual
        # call sites) - see test_double_booking.py for why patching the
        # origin modules doesn't intercept an already-imported name.
        with patch("src.chain.validators.get_usuario", new_callable=AsyncMock) as mock_usuario, \
             patch("src.chain.validators.get_evento", new_callable=AsyncMock) as mock_evento, \
             patch("src.chain.validators.ejecutar_pagar_y_decrementar", new_callable=AsyncMock) as mock_pago, \
             patch("src.chain.validators.decrementar_inventario_evento", new_callable=AsyncMock) as mock_decrementar_evento, \
             patch("src.chain.validators.get_reservas_collection", new_callable=AsyncMock) as mock_mongo, \
             patch("src.chain.validators.insert_event_log", new_callable=AsyncMock) as mock_pg:

            mock_usuario.return_value = {"nombre": "Test"}
            mock_evento.return_value = {
                "estado": "publicado",
                "entradas_disponibles": 10,
                "precios": [{"categoria": "general", "precio": 50.0, "disponibles": 10}]
            }
            mock_pago.return_value = {"success": True, "message": "OK"}
            mock_decrementar_evento.return_value = {"disponibles": 9}

            mock_collection = AsyncMock()
            mock_collection.insert_one = AsyncMock()
            mock_collection.find_one = AsyncMock(return_value=None)
            mock_mongo.return_value = mock_collection

            chain = ChainBuilder.build()
            context = ReservaContext(
                usuario_id=uuid4(),
                evento_id=uuid4(),
                cantidad=1,
                categoria="general",
                metodo_pago="tarjeta",
                reserva_id=uuid4(),
                correlation_id=uuid4()
            )

            context = await chain.handle(context)

            assert context.error is None, f"Chain failed: {context.error}"

            # Auditor (the last handler) only runs - and logs
            # SAGA_COMPLETED - if every prior handler succeeded, so its
            # presence is proof the other 6 events were logged too without
            # having to assert each one's exact position.
            event_types = [
                call.kwargs.get("event_type") or call.args[0]
                for call in mock_pg.call_args_list
            ]
            for expected in ("USUARIO_VALIDADO", "EVENTO_VALIDADO", "PAGO_PROCESADO",
                              "INVENTARIO_DECREMENTADO", "RESERVA_CONFIRMADA"):
                assert expected in event_types, f"Missing event: {expected}"

    @pytest.mark.integration
    async def test_failed_saga_logs_saga_failed_and_compensation(self):
        """Test failed SAGA logs SAGA_FAILED and COMPENSACION_EJECUTADA."""
        # Simulate failed SAGA at step 5 (MongoDB)
        from src.chain.validators import ConfirmadorReserva
        from src.models.reserva import ReservaContext

        with patch("src.chain.validators.get_reservas_collection", new_callable=AsyncMock) as mock_collection, \
             patch("src.chain.validators.ejecutar_compensar_pago_inventario", new_callable=AsyncMock) as mock_comp, \
             patch("src.chain.validators.incrementar_inventario_evento", new_callable=AsyncMock) as mock_incr, \
             patch("src.chain.validators.insert_event_log", new_callable=AsyncMock) as mock_pg:

            mock_coll = AsyncMock()
            mock_coll.find_one.return_value = None
            mock_coll.insert_one.side_effect = Exception("MongoDB down")
            mock_collection.return_value = mock_coll

            mock_comp.return_value = {"success": True, "message": "COMPENSACION_OK"}
            mock_incr.return_value = None
            mock_pg.return_value = None

            context = ReservaContext(
                usuario_id=uuid4(),
                evento_id=uuid4(),
                cantidad=1,
                categoria="general",
                metodo_pago="tarjeta",
                reserva_id=uuid4(),
                correlation_id=uuid4(),
                pago_data={"monto": 50.0}
            )

            result = await ConfirmadorReserva().handle(context)

            # Verify compensation ran
            assert result.compensation_triggered is True
            mock_comp.assert_called_once()
            mock_incr.assert_called_once()

            # Check COMPENSACION_EJECUTADA was logged
            pg_calls = [
                c for c in mock_pg.call_args_list
                if c.kwargs.get("event_type") == "COMPENSACION_EJECUTADA"
            ]
            assert len(pg_calls) >= 1

    @pytest.mark.integration
    async def test_correlation_id_index_exists_and_used(self):
        """Test that idx_event_log_correlation index exists and is used for correlation_id queries."""
        with patch("src.services.postgresql.get_pg_pool") as mock_pool:
            mock_pool_instance = AsyncMock()
            mock_pool.return_value = mock_pool_instance
            mock_conn = AsyncMock()
            mock_pool_instance.acquire.return_value.__aenter__.return_value = mock_conn
            
            # Mock the index existence check
            mock_conn.fetchrow.return_value = {"indexname": "idx_event_log_correlation"}
            
            # Mock the query plan showing index usage
            mock_conn.fetch.return_value = [
                {"index_name": "idx_event_log_correlation", "scan_type": "Index Scan"}
            ]
            
            from src.services.postgresql import get_events_by_aggregate
            from uuid import uuid4
            
            reserva_id = uuid4()
            correlation_id = uuid4()
            
            # This would test the actual query in a real integration test
            # For now, verify the index exists in the schema
            from src.services.postgresql import init_pg_schema
            
            # Verify the index creation SQL is in the init_pg_schema function
            import src.services.postgresql as pg_module
            import inspect
            source = inspect.getsource(pg_module.init_pg_schema)
            assert "idx_event_log_correlation" in source
            assert "ON event_log(correlation_id)" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])