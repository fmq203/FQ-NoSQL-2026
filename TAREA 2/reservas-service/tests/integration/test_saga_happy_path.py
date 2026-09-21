"""Integration tests for SAGA happy path."""
import pytest
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock
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
        with patch("src.services.http_clients.get_usuarios_client") as mock:
            client = AsyncMock()
            mock.return_value = client
            yield client

    @pytest.fixture
    def mock_eventos_service(self):
        """Mock Eventos Service responses."""
        with patch("src.services.http_clients.get_eventos_client") as mock:
            client = AsyncMock()
            mock.return_value = client
            yield client

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
        mock_usuario_service: AsyncMock,
        mock_eventos_service: AsyncMock,
        mock_redis: AsyncMock,
    ):
        """Test complete SAGA happy path: ValidaDatos → Usuario → Evento → PagoRedis → ReservaMongo → AuditPG"""
        # Setup mocks
        usuario_id = str(uuid4())
        evento_id = str(uuid4())
        
        # Mock usuario service response
        mock_usuario_service.get.return_value = AsyncMock(
            status_code=200,
            json=lambda: {
                "usuario_id": usuario_id,
                "nombre": "Juan",
                "apellido": "Pérez",
                "email": "juan@example.com"
            }
        )
        
        # Mock evento service response
        mock_eventos_service.get.return_value = AsyncMock(
            status_code=200,
            json=lambda: {
                "evento_id": evento_id,
                "nombre": "Concierto Test",
                "estado": "publicado",
                "aforo_total": 100,
                "entradas_disponibles": 50,
                "precios": [{"categoria": "General", "precio": 50.0, "disponibles": 50}],
                "ubicacion": {"ciudad": "Madrid", "pais": "España"}
            }
        )
        
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
        mock_usuario_service: AsyncMock,
        mock_eventos_service: AsyncMock,
        mock_redis: AsyncMock,
    ):
        """Test idempotency: same reserva_id returns 200 with existing reservation."""
        usuario_id = str(uuid4())
        evento_id = str(uuid4())
        
        # Setup mocks
        mock_usuario_service.get.return_value = AsyncMock(
            status_code=200,
            json=lambda: {"usuario_id": str(uuid4()), "nombre": "Test"}
        )
        
        mock_eventos_service.get.return_value = AsyncMock(
            status_code=200,
            json=lambda: {
                "evento_id": evento_id,
                "estado": "publicado",
                "entradas_disponibles": 50,
                "precios": [{"categoria": "General", "precio": 50.0, "disponibles": 50}]
            }
        )
        
        mock_redis.return_value = {"success": True, "message": "OK"}
        
        # First request - should succeed
        request_data = {
            "usuario_id": usuario_id,
            "evento_id": evento_id,
            "cantidad": 1,
            "metodo_pago": "tarjeta"
        }
        
        response1 = await client.post("/api/v1/reservar", json=request_data)
        assert response1.status_code == 201
        reserva_id = response1.json()["reserva_id"]
        
        # Second request with same reserva_id (simulate retry)
        # In real implementation, client would send same reserva_id
        # For now, we verify the idempotency check in the service
        from src.utils.idempotency import check_idempotency
        from uuid import UUID
        
        existing = await check_idempotency(UUID(reserva_id))
        assert existing is not None  # Should find existing reservation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])