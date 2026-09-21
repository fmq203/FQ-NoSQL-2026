"""Unit tests for Chain of Responsibility handlers."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime
from src.chain.validators import (
    ValidadorDeDatos,
    ValidadorInventario,
    ValidadorEvento,
    ProcesadorPago,
    ConfirmadorReserva,
    Auditor,
    ChainBuilder
)
from src.models.reserva import ReservaContext, SagaStep, EventType
from uuid import UUID


class TestValidadorDeDatos:
    """Tests for ValidadorDeDatos handler."""

    @pytest.fixture
    def handler(self):
        return ValidadorDeDatos()

    @pytest.mark.unit
    async def test_valid_data_passes(self):
        """Valid data should pass validation."""
        handler = ValidadorDeDatos()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=2,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        result = await handler.handle(context)
        
        assert result.error is None
        assert result.status_code == 200
        assert len(context.saga_log) == 1
        assert context.saga_log[0]["paso"] == "VALIDAR_DATOS"
        assert context.saga_log[0]["exitoso"] is True

    @pytest.mark.unit
    async def test_invalid_uuid_fails(self):
        """Invalid UUID should fail with 400."""
        handler = ValidadorDeDatos()
        context = ReservaContext(
            usuario_id="not-a-uuid",
            evento_id=uuid4(),
            cantidad=1,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        result = await handler.handle(context)
        
        assert result.error == "UUID inválido"
        assert result.status_code == 400
        assert result.saga_log[0]["exitoso"] is False

    @pytest.mark.unit
    async def test_zero_cantidad_fails(self):
        """Zero or negative cantidad should fail."""
        handler = ValidadorDeDatos()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=0,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        result = await handler.handle(context)
        
        assert result.error == "Cantidad debe ser mayor a 0"
        assert result.status_code == 400

    @pytest.mark.unit
    async def test_invalid_metodo_pago_fails(self):
        """Invalid payment method should fail."""
        handler = ValidadorDeDatos()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=1,
            metodo_pago="bitcoin",  # Not in valid list
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        result = await handler.handle(context)
        
        assert "Método de pago inválido" in context.error
        assert context.status_code == 400


class TestValidadorInventario:
    """Tests for ValidadorInventario handler."""

    @pytest.mark.unit
    async def test_existing_user_passes(self):
        """Existing user should pass validation."""
        handler = ValidadorInventario()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=1,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        with patch("src.chain.validators.get_usuario") as mock_get_usuario:
            mock_get_usuario.return_value = {"usuario_id": str(uuid4()), "nombre": "Juan"}
            
            result = await handler.handle(context)
            
            assert result.error is None
            assert context.usuario_data is not None
            assert context.saga_log[0]["exitoso"] is True

    @pytest.mark.unit
    async def test_nonexistent_user_fails(self):
        """Non-existent user should return 404."""
        handler = ValidadorInventario()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=1,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        with patch("src.chain.validators.get_usuario") as mock_get_usuario:
            mock_get_usuario.return_value = None
            
            result = await handler.handle(context)
            
            assert result.error == "Usuario no encontrado"
            assert result.status_code == 404

    @pytest.mark.unit
    async def test_service_error_returns_503(self):
        """Service error should return 503."""
        handler = ValidadorInventario()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=1,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        with patch("src.chain.validators.get_usuario") as mock_get_usuario:
            mock_get_usuario.side_effect = Exception("Service down")
            
            result = await handler.handle(context)
            
            assert result.error == "Error validando usuario"
            assert result.status_code == 503


class TestValidadorEvento:
    """Tests for ValidadorEvento handler."""

    @pytest.mark.unit
    async def test_valid_event_passes(self):
        """Valid published event with sufficient capacity passes."""
        handler = ValidadorEvento()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=2,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        with patch("src.chain.validators.get_evento") as mock_get_evento:
            mock_get_evento.return_value = {
                "evento_id": str(uuid4()),
                "estado": "publicado",
                "entradas_disponibles": 10,
                "precios": [{"categoria": "General", "precio": 50.0, "disponibles": 10}]
            }
            
            result = await handler.handle(context)
            
            assert result.error is None
            assert context.evento_data is not None
            assert context.saga_log[0]["exitoso"] is True

    @pytest.mark.unit
    async def test_nonexistent_event_fails(self):
        """Non-existent event returns 404."""
        handler = ValidadorEvento()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=1,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        with patch("src.chain.validators.get_evento") as mock_get_evento:
            mock_get_evento.return_value = None
            
            result = await handler.handle(context)
            
            assert result.error == "Evento no encontrado"
            assert result.status_code == 404

    @pytest.mark.unit
    async def test_unpublished_event_fails(self):
        """Unpublished event returns 409."""
        handler = ValidadorEvento()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=1,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        with patch("src.chain.validators.get_evento") as mock_get_evento:
            mock_get_evento.return_value = {"estado": "borrador", "entradas_disponibles": 10}
            
            result = await handler.handle(context)
            
            assert result.error == "Evento no disponible para reservas"
            assert result.status_code == 409

    @pytest.mark.unit
    async def test_insufficient_capacity_fails(self):
        """Insufficient capacity returns 409."""
        handler = ValidadorEvento()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=10,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        with patch("src.chain.validators.get_evento") as mock_get_evento:
            mock_get_evento.return_value = {
                "estado": "publicado",
                "entradas_disponibles": 5,
                "precios": [{"categoria": "General", "disponibles": 5}]
            }
            
            result = await handler.handle(context)
            
            assert "Inventario insuficiente" in context.error
            assert result.status_code == 409


class TestProcesadorPago:
    """Tests for ProcesadorPago handler."""

    @pytest.mark.unit
    async def test_successful_payment(self):
        """Successful payment processing."""
        handler = ProcesadorPago()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=2,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        with patch("src.chain.validators.ejecutar_pagar_y_decrementar") as mock_pago:
            mock_pago.return_value = {"success": True, "message": "OK"}
            
            with patch("src.chain.validators.insert_event_log") as mock_insert:
                result = await handler.handle(context)
                
                assert result.error is None
                assert context.pago_data is not None
                assert context.pago_data["estado"] == "confirmado"

    @pytest.mark.unit
    async def test_insufficient_inventory_returns_409(self):
        """Insufficient inventory returns 409."""
        handler = ProcesadorPago()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=1,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        with patch("src.chain.validators.ejecutar_pagar_y_decrementar") as mock_pago:
            mock_pago.return_value = {"success": False, "message": "INVENTARIO_INSUFICIENTE"}
            
            result = await handler.handle(context)
            
            assert "INSUFICIENTE" in context.error
            assert result.status_code == 409


class TestConfirmadorReserva:
    """Tests for ConfirmadorReserva handler."""

    @pytest.mark.unit
    async def test_successful_reservation(self):
        """Successful reservation creation."""
        handler = ConfirmadorReserva()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=2,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4(),
            pago_data={"monto": 100.0, "metodo_pago": "tarjeta"}
        )
        
        with patch("src.chain.validators.get_reservas_collection") as mock_collection:
            mock_coll = AsyncMock()
            mock_coll.find_one.return_value = None  # Not idempotent
            mock_collection.return_value = mock_coll
            mock_coll.insert_one = AsyncMock()
            
            with patch("src.chain.validators.generate_confirmation_number") as mock_gen:
                mock_gen.return_value = "CONF-20260101-ABCDEF12"
                
                result = await handler.handle(context)
                
                assert result.error is None
                assert context.reserva_data is not None
                assert context.reserva_data["estado"] == "confirmada"
                assert "CONF-" in context.reserva_data["numero_confirmacion"]

    @pytest.mark.unit
    async def test_idempotent_reservation(self):
        """Existing reservation returns success (idempotent)."""
        handler = ConfirmadorReserva()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=1,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        with patch("src.chain.validators.get_reservas_collection") as mock_collection:
            mock_coll = AsyncMock()
            mock_coll.find_one.return_value = {"_id": context.reserva_id, "estado": "confirmada"}
            mock_collection.return_value = mock_coll
            
            result = await handler.handle(context)
            
            assert result.error is None
            assert context.reserva_data is not None
            assert "idempotent" in context.saga_log[-1]["detalles"].lower()

    @pytest.mark.unit
    async def test_mongodb_failure_triggers_compensation(self):
        """MongoDB failure triggers Redis compensation."""
        handler = ConfirmadorReserva()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=1,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4(),
            pago_data={"monto": 50.0}
        )
        
        with patch("src.chain.validators.get_reservas_collection") as mock_collection:
            mock_coll = AsyncMock()
            mock_coll.find_one.return_value = None
            mock_coll.insert_one.side_effect = Exception("MongoDB down")
            mock_collection.return_value = mock_coll
            
            with patch("src.chain.validators.ejecutar_compensar_pago_inventario") as mock_comp:
                mock_comp.return_value = {"success": True, "message": "COMPENSACION_OK"}
                
                with patch("src.chain.validators.insert_event_log") as mock_insert:
                    result = await handler.handle(context)
                    
                    assert result.error is not None
                    assert result.status_code == 500
                    assert context.compensation_triggered is True
                    mock_comp.assert_called_once()


class TestAuditor:
    """Tests for Auditor handler."""

    @pytest.mark.unit
    async def test_successful_audit(self):
        """Successful audit logs SAGA_COMPLETED."""
        handler = Auditor()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=1,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        with patch("src.services.postgresql.insert_event_log") as mock_insert:
            result = await handler.handle(context)
            
            assert result.error is None
            mock_insert.assert_called_once()
            call_args = mock_insert.call_args
            assert call_args.kwargs["event_type"] == "SAGA_COMPLETED"

    @pytest.mark.unit
    async def test_audit_failure_logs_warning(self):
        """Audit failure logs warning but doesn't fail."""
        handler = Auditor()
        context = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=1,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        with patch("src.chain.validators.insert_event_log") as mock_insert:
            mock_insert.side_effect = Exception("PG down")
            
            result = await handler.handle(context)
            
            # Should not fail the SAGA
            assert result.error is None
            assert context.status_code == 200


class TestChainBuilder:
    """Tests for ChainBuilder."""

    @pytest.mark.unit
    def test_build_chain_order(self):
        """Chain should be built in correct order."""
        chain = ChainBuilder.build()
        
        # Verify chain order: 1→2→3→4→5→6
        current = chain
        expected_steps = [
            "VALIDAR_DATOS",
            "VALIDAR_USUARIO",
            "VALIDAR_EVENTO",
            "PROCESAR_PAGO",
            "CONFIRMAR_RESERVA",
            "AUDITAR"
        ]
        
        for expected_step in expected_steps:
            assert current is not None
            assert current._step_name == expected_step
            current = current._next_handler
        
        assert current is None  # End of chain

    @pytest.mark.unit
    async def test_chain_stops_on_error(self):
        """Chain should stop executing when error occurs."""
        from src.chain.validators import ValidadorDeDatos, Handler
        
        # Create a chain where first handler fails
        handler1 = ValidadorDeDatos()
        handler2 = AsyncMock()
        # Configure the mock to return a proper context
        handler2.handle.return_value = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=1,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        handler1.set_next(handler2)
        
        context = ReservaContext(
            usuario_id="invalid",  # Invalid UUID
            evento_id=uuid4(),
            cantidad=1,
            metodo_pago="tarjeta",
            reserva_id=uuid4(),
            correlation_id=uuid4()
        )
        
        result = await handler1.handle(context)
        
        assert result.error is not None
        assert result.status_code == 400
        # Second handler should not be called
        handler2.handle.assert_not_awaited()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])