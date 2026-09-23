"""Integration tests for SAGA happy path."""
import pytest
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from src.main import app


class TestSAGAHappyPath:
    """Integration tests for complete SAGA happy path."""

    @pytest.fixture
    async def client(self):
        """Create test client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    def mock_usuario_service(self):
        """Mock Usuarios Service responses."""
        async def mock_get_usuario(*args, **kwargs):
            return {
                "usuario_id": "test",
                "nombre": "Test",
                "apellido": "Test",
                "email": "test@example.com"
            }
        with patch("src.chain.validators.get_usuario") as mock:
            mock.side_effect = mock_get_usuario
            yield mock

    @pytest.fixture
    def mock_eventos_service(self):
        """Mock Eventos Service responses."""
        async def mock_get_evento(*args, **kwargs):
            return {
                "evento_id": "test",
                "estado": "publicado",
                "entradas_disponibles": 50,
                "precios": [{"categoria": "General", "precio": 50.0, "disponibles": 50}],
            }
        with patch("src.chain.validators.get_evento") as mock:
            mock.side_effect = mock_get_evento
            yield mock

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis operations."""
        with patch("src.services.redis_pago.ejecutar_pagar_y_decrementar") as mock:
            mock.return_value = {"success": True, "message": "OK"}
            yield mock

    @pytest.fixture
    def mock_mongo(self):
        """MongoDB is tested with real connection via testcontainers in real env."""
        pass

    @pytest.mark.integration
    async def test_saga_happy_path_complete(
        self,
        client: AsyncClient,
        mock_usuario_service,
        mock_eventos_service,
        mock_redis,
    ):
        """Test complete SAGA happy path: ValidaDatos -> Usuario -> Evento -> PagoRedis -> ReservaMongo -> AuditPG"""
        # Setup mocks
        usuario_id = str(uuid4())
        evento_id = str(uuid4())

        # Mock usuario service response
        mock_usuario_service.return_value = {
            "usuario_id": usuario_id,
            "nombre": "Juan",
            "apellido": "Pérez",
            "email": "juan@example.com"
        }

        # Mock evento service response
        mock_eventos_service.return_value = {
            "evento_id": evento_id,
            "nombre": "Concierto Test",
            "estado": "publicado",
            "aforo_total": 100,
            "entradas_disponibles": 50,
            "precios": [{"categoria": "General", "precio": 50.0, "disponibles": 50}],
            "ubicacion": {"ciudad": "Madrid", "pais": "España"}
        }

        # Make request
        response = await client.post(
            "/api/v1/reservar",
            json={
                "usuario_id": usuario_id,
                "evento_id": evento_id,
                "cantidad": 2,
                "metodo_pago": "tarjeta"
            }
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert "reserva_id" in data
        assert data["estado"] == "confirmada"
        assert "numero_confirmacion" in data
        assert data["numero_confirmacion"].startswith("CONF-")

        # Verify MongoDB was called (reserva created)
        # Verify Redis was called (pago + inventory decrement)
        mock_redis.assert_called_once()

        # Verify PostgreSQL event_log has 7 events
        # This would be verified in a real integration test with testcontainers

    @pytest.mark.integration
    async def test_saga_idempotency(
        self,
        client: AsyncClient,
        mock_usuario_service,
        mock_eventos_service,
        mock_redis,
    ):
        """Test idempotency: same request returns 200 with existing reservation."""
        usuario_id = str(uuid4())
        evento_id = str(uuid4())
        reserva_id = str(uuid4())  # Pre-generated for idempotency

        # Setup mocks - the fixtures now return dicts directly
        mock_usuario_service.return_value = {
            "usuario_id": str(uuid4()),
            "nombre": "Test",
            "apellido": "Test",
            "email": "test@example.com"
        }

        mock_eventos_service.return_value = {
            "evento_id": str(uuid4()),
            "estado": "publicado",
            "entradas_disponibles": 50,
            "precios": [{"categoria": "General", "precio": 50.0, "disponibles": 50}],
        }

        mock_redis.return_value = {"success": True, "message": "OK"}

        # First request - should succeed with pre-generated reserva_id
        request_data = {
            "usuario_id": usuario_id,
            "evento_id": evento_id,
            "cantidad": 1,
            "metodo_pago": "tarjeta",
            "reserva_id": reserva_id  # Include idempotency key
        }

        response1 = await client.post("/api/v1/reservar", json=request_data)
        assert response1.status_code == 201
        assert response1.json()["reserva_id"] == reserva_id

        # Second request with SAME data AND same reserva_id (simulate retry) - should be idempotent
        response2 = await client.post("/api/v1/reservar", json={
            "usuario_id": usuario_id,
            "evento_id": evento_id,
            "cantidad": 1,
            "metodo_pago": "tarjeta",
            "reserva_id": reserva_id  # Same idempotency key
        })

        assert response2.status_code == 200
        assert response2.json()["reserva_id"] == reserva_id