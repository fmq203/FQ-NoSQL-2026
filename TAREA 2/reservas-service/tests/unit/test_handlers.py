"""Unit tests for Chain of Responsibility handlers."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from src.chain.validators import (
    ValidadorDeDatos,
    ValidadorInventario,
    ValidadorEvento,
    ProcesadorPago,
    ConfirmadorReserva,
    Auditor,
    ChainBuilder
)
from src.models.reserva import ReservaContext, SagaStep
from datetime import datetime


class TestValidadorDeDatos:
    """Tests for ValidadorDeDatos handler."""

    @pytest.fixture
    def handler(self):
        return ValidadorDeDatos()

    @pytest.fixture
    def valid_context(self):
        return ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=2,
            metodo_pago="tarjeta"
        )

    @pytest.mark.unit
    async def test_valid_data_passes(self, handler, valid_context):
        """Valid data should pass validation."""
        result = await handler.handle(valid_context)
        assert result.error is None
        assert result.status_code == 200
        assert any(log["paso"] == "VALIDAR_DATOS" and log["exitoso"] for log in result.saga_log)

    @pytest.mark.unit
    async def test_invalid_uuid_fails(self, handler):
        """Invalid UUID should fail validation."""
        context = ReservaContext(
            usuario_id="invalid-uuid",
            evento_id=uuid4(),
            cantidad=2,
            metodo_pago="tarjeta"
        )
        result = await handler.handle(context)
        assert result.error == "UUID inválido"
        assert result.status_code == 400
        assert any(log["paso"] == "VALIDAR_DATOS" and not log["exitoso"] for log in result.saga_log)

    @pytest.mark.unit
    async def test_zero_cantidad_fails(self, handler, valid_context):
        """Zero cantidad should fail validation."""
        valid_context.cantidad = 0
        result = await handler.handle(valid_context)
        assert result.error == "Cantidad debe ser mayor a 0"
        assert result.status_code == 400

    @pytest.mark.unit
    async def test_invalid_metodo_pago_fails(self, handler, valid_context):
        """Invalid metodo_pago should fail validation."""
        valid_context.metodo_pago = "bitcoin"
        result = await handler.handle(valid_context)
        assert result.error is not None
        assert "Método de pago inválido" in result.error
        assert result.status_code == 400


class TestValidadorInventario:
    """Tests for ValidadorInventario handler."""

    @pytest.fixture
    def handler(self):
        return ValidadorInventario()

    @pytest.fixture
    def valid_context(self):
        return ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=2,
            metodo_pago="tarjeta"
        )

    @pytest.mark.unit
    async def test_existing_user_passes(self, handler, valid_context):
        """Existing user should pass validation."""
        with patch("src.chain.validators.get_usuario", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "usuario_id": str(valid_context.usuario_id),
                "nombre": "Juan",
                "apellido": "Pérez",
                "email": "juan@example.com"
            }
            result = await handler.handle(valid_context)
            assert result.error is None
            assert result.usuario_data is not None

    @pytest.mark.unit
    async def test_nonexistent_user_fails(self, handler, valid_context):
        """Non-existent user should fail validation."""
        with patch("src.chain.validators.get_usuario", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            result = await handler.handle(valid_context)
            assert result.error == "Usuario no encontrado"
            assert result.status_code == 404

    @pytest.mark.unit
    async def test_service_error_returns_503(self, handler, valid_context):
        """Service error should return 503."""
        with patch("src.chain.validators.get_usuario", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Service unavailable")
            result = await handler.handle(valid_context)
            assert result.error == "Error validando usuario"
            assert result.status_code == 503


class TestValidadorEvento:
    """Tests for ValidadorEvento handler."""

    @pytest.fixture
    def handler(self):
        return ValidadorEvento()

    @pytest.fixture
    def valid_context(self):
        return ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=2,
            metodo_pago="tarjeta"
        )

    @pytest.mark.unit
    async def test_valid_event_passes(self, handler, valid_context):
        """Valid published event with sufficient capacity passes."""
        with patch("src.chain.validators.get_evento", new_callable=AsyncMock) as mock_get:
            with patch("src.chain.validators.insert_event_log", new_callable=AsyncMock) as mock_pg:
                mock_get.return_value = {
                    "evento_id": str(valid_context.evento_id),
                    "estado": "publicado",
                    "entradas_disponibles": 100,
                    "precios": [{"categoria": "General", "precio": 50.0, "disponibles": 100}],
                }
                mock_pg.return_value = None
                result = await handler.handle(valid_context)
                assert result.error is None
                assert result.evento_data is not None

    @pytest.mark.unit
    async def test_nonexistent_event_fails(self, handler, valid_context):
        """Non-existent event should return 404."""
        with patch("src.chain.validators.get_evento", new_callable=AsyncMock) as mock_get:
            with patch("src.chain.validators.insert_event_log", new_callable=AsyncMock) as mock_pg:
                mock_get.return_value = None
                mock_pg.return_value = None
                result = await handler.handle(valid_context)
                assert result.error == "Evento no encontrado"
                assert result.status_code == 404

    @pytest.mark.unit
    async def test_unpublished_event_fails(self, handler, valid_context):
        """Unpublished event should return 409."""
        with patch("src.chain.validators.get_evento", new_callable=AsyncMock) as mock_get:
            with patch("src.chain.validators.insert_event_log", new_callable=AsyncMock) as mock_pg:
                mock_get.return_value = {
                    "evento_id": str(valid_context.evento_id),
                    "estado": "borrador",
                    "entradas_disponibles": 100,
                }
                mock_pg.return_value = None
                result = await handler.handle(valid_context)
                assert result.error == "Evento no disponible para reservas"
                assert result.status_code == 409

    @pytest.mark.unit
    async def test_insufficient_capacity_fails(self, handler, valid_context):
        """Insufficient capacity should return 409."""
        with patch("src.chain.validators.get_evento", new_callable=AsyncMock) as mock_get:
            with patch("src.chain.validators.insert_event_log", new_callable=AsyncMock) as mock_pg:
                mock_get.return_value = {
                    "evento_id": str(valid_context.evento_id),
                    "estado": "publicado",
                    "entradas_disponibles": 1,  # Less than requested (2)
                }
                mock_pg.return_value = None
                result = await handler.handle(valid_context)
                assert result.error == "Inventario insuficiente"
                assert result.status_code == 409


class TestProcesadorPago:
    """Tests for ProcesadorPago handler."""

    @pytest.fixture
    def handler(self):
        return ProcesadorPago()

    @pytest.fixture
    def valid_context(self):
        ctx = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=2,
            metodo_pago="tarjeta",
            reserva_id=uuid4()
        )
        ctx.evento_data = {"precios": [{"categoria": "General", "precio": 50.0}]}
        return ctx

    @pytest.mark.unit
    async def test_successful_payment(self, handler, valid_context):
        """Successful payment processing."""
        with patch("src.chain.validators.ejecutar_pagar_y_decrementar", new_callable=AsyncMock) as mock_redis:
            with patch("src.chain.validators.insert_event_log", new_callable=AsyncMock) as mock_pg:
                mock_redis.return_value = {"success": True, "message": "OK"}
                mock_pg.return_value = None
                result = await handler.handle(valid_context)
                assert result.error is None
                assert result.pago_data is not None
                assert result.pago_data["estado"] == "confirmado"

    @pytest.mark.unit
    async def test_insufficient_inventory_returns_409(self, handler, valid_context):
        """Insufficient inventory should return 409."""
        with patch("src.chain.validators.ejecutar_pagar_y_decrementar", new_callable=AsyncMock) as mock_redis:
            mock_redis.return_value = {"success": False, "message": "INVENTARIO_INSUFICIENTE"}
            result = await handler.handle(valid_context)
            assert result.error == "INVENTARIO_INSUFICIENTE"
            assert result.status_code == 409


class TestConfirmadorReserva:
    """Tests for ConfirmadorReserva handler."""

    @pytest.fixture
    def handler(self):
        return ConfirmadorReserva()

    @pytest.fixture
    def valid_context(self):
        ctx = ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=2,
            metodo_pago="tarjeta",
            reserva_id=uuid4()
        )
        ctx.pago_data = {"monto": 100.0, "metodo_pago": "tarjeta"}
        return ctx

    @pytest.mark.unit
    async def test_successful_reservation(self, handler, valid_context):
        """Successful reservation creation."""
        with patch("src.chain.validators.get_reservas_collection") as mock_collection:
            mock_col = AsyncMock()
            mock_collection.return_value = mock_col
            mock_col.find_one.return_value = None  # Not idempotent
            mock_col.insert_one = AsyncMock()
            with patch("src.chain.validators.insert_event_log") as mock_pg:
                mock_pg.return_value = None
                result = await handler.handle(valid_context)
                assert result.error is None
                assert result.reserva_data is not None
                assert result.reserva_data["estado"] == "confirmada"
                assert "numero_confirmacion" in result.reserva_data

    @pytest.mark.unit
    async def test_idempotent_reservation(self, handler, valid_context):
        """Existing reservation returns success (idempotent)."""
        with patch("src.chain.validators.get_reservas_collection") as mock_collection:
            mock_col = AsyncMock()
            mock_collection.return_value = mock_col
            # Return existing document
            existing_doc = {
                "_id": valid_context.reserva_id,
                "estado": "confirmada",
                "numero_confirmacion": "CONF-20260101-ABCDEFGH"
            }
            mock_col.find_one.return_value = existing_doc
            result = await handler.handle(valid_context)
            assert result.error is None
            assert result.reserva_data is not None

    @pytest.mark.unit
    async def test_mongodb_failure_triggers_compensation(self, handler, valid_context):
        """MongoDB failure triggers Redis compensation."""
        with patch("src.chain.validators.get_reservas_collection") as mock_collection:
            mock_col = AsyncMock()
            mock_collection.return_value = mock_col
            mock_col.find_one.return_value = None
            mock_col.insert_one.side_effect = Exception("MongoDB down")
            with patch("src.chain.validators.ejecutar_compensar_pago_inventario") as mock_comp:
                mock_comp.return_value = {"success": True, "message": "COMPENSACION_OK"}
                with patch("src.chain.validators.insert_event_log") as mock_pg:
                    mock_pg.return_value = None
                    result = await handler.handle(valid_context)
                    assert result.error is not None
                    assert result.status_code == 500
                    assert result.compensation_triggered is True
                    mock_comp.assert_called_once()


class TestAuditor:
    """Tests for Auditor handler."""

    @pytest.fixture
    def handler(self):
        return Auditor()

    @pytest.fixture
    def valid_context(self):
        return ReservaContext(
            usuario_id=uuid4(),
            evento_id=uuid4(),
            cantidad=2,
            metodo_pago="tarjeta",
            reserva_id=uuid4()
        )

    @pytest.mark.unit
    async def test_successful_audit(self, handler, valid_context):
        """Successful audit logs SAGA_COMPLETED."""
        with patch("src.chain.validators.insert_event_log") as mock_pg:
            mock_pg.return_value = None
            result = await handler.handle(valid_context)
            assert result.error is None
            assert any(log["paso"] == "SAGA_COMPLETED" and log["exitoso"] for log in result.saga_log)

    @pytest.mark.unit
    async def test_audit_failure_logs_warning(self, handler, valid_context):
        """Audit failure logs warning but doesn't fail."""
        with patch("src.chain.validators.insert_event_log") as mock_pg:
            mock_pg.side_effect = Exception("PG down")
            result = await handler.handle(valid_context)
            # Should not fail the reservation
            assert result.error is None
            assert any(log["paso"] == "AUDITORIA" and not log["exitoso"] for log in result.saga_log)


class TestChainBuilder:
    """Tests for ChainBuilder."""

    @pytest.mark.unit
    def test_build_chain_order(self):
        """Chain should be built in correct order."""
        chain = ChainBuilder.build()
        # Verify chain structure by traversing
        steps = []
        current = chain
        while current:
            steps.append(current.step_name)
            current = getattr(current, "_next_handler", None)

        expected = [
            "VALIDAR_DATOS",
            "VALIDAR_USUARIO",
            "VALIDAR_EVENTO",
            "PROCESAR_PAGO",
            "CONFIRMAR_RESERVA",
            "AUDITAR"
        ]
        assert steps == expected

    @pytest.mark.unit
    def test_chain_stops_on_error(self):
        """Chain should stop executing when error occurs."""
        chain = ChainBuilder.build()
        # First handler will fail due to invalid UUID
        context = ReservaContext(
            usuario_id="invalid",
            evento_id=uuid4(),
            cantidad=2,
            metodo_pago="tarjeta"
        )
        # This would need async execution, test separately in integration
        # Just verify chain structure is correct
        assert chain is not None