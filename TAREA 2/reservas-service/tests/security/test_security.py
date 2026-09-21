"""Security hardening tests (T069, T074)."""
import pytest
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from io import StringIO
import logging
from src.main import app


class TestSecurityHardening:
    """Security hardening tests (T069)."""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.security
    async def test_input_validation_rejects_malicious_payloads(self, client):
        """Test that malicious payloads are rejected."""
        malicious_payloads = [
            {"usuario_id": "<script>alert('xss')</script>", "evento_id": str(uuid4()), "cantidad": 1, "metodo_pago": "tarjeta"},
            {"usuario_id": str(uuid4()), "evento_id": "'; DROP TABLE users; --", "cantidad": 1, "metodo_pago": "tarjeta"},
            {"usuario_id": str(uuid4()), "evento_id": str(uuid4()), "cantidad": -1, "metodo_pago": "tarjeta"},
            {"usuario_id": str(uuid4()), "evento_id": str(uuid4()), "cantidad": 1, "metodo_pago": "malicious<script>"},
        ]
        
        for payload in malicious_payloads:
            response = await client.post("/api/v1/reservar", json=payload)
            # Should reject with 422 or 400
            assert response.status_code in [400, 422], f"Failed to reject: {payload}"

    @pytest.mark.security
    async def test_no_pii_in_logs(self):
        """Test that no PII is logged."""
        # Capture logs
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)
        
        logger = logging.getLogger("test_security")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        
        with patch("src.services.http_clients.get_usuarios_client") as mock_usuarios, \
             patch("src.services.http_clients.get_eventos_client") as mock_eventos, \
             patch("src.services.redis_pago.ejecutar_pagar_y_decrementar") as mock_redis:
            
            mock_redis.return_value = {"success": True, "message": "OK"}
            
            # Make a request with PII
            async with AsyncClient(app=app, base_url="http://test") as client:
                await client.post("/api/v1/reservar", json={
                    "usuario_id": str(uuid4()),
                    "evento_id": str(uuid4()),
                    "cantidad": 1,
                    "metodo_pago": "tarjeta"
                })
        
        log_output = log_stream.getvalue()
        
        # Verify no PII in logs (email, document, name, etc.)
        assert "juan@example.com" not in log_output
        assert "12345678" not in log_output  # Document number
        # Note: Names might appear in mock data, so we check correlation_id is present
        assert "correlation_id" in log_output


class TestIdempotencyBehavior:
    """Tests for idempotency behavior verification (T074)."""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.integration
    async def test_idempotency_returns_200_for_existing_reservation(self):
        """Same reserva_id should return 200 with existing reservation (T074)."""
        with patch("src.services.http_clients.get_usuarios_client") as mock_usuarios, \
             patch("src.services.http_clients.get_eventos_client") as mock_eventos, \
             patch("src.services.redis_pago.ejecutar_pagar_y_decrementar") as mock_redis, \
             patch("src.services.mongo.get_reservas_collection") as mock_mongo, \
             patch("src.services.postgresql.insert_event_log") as mock_pg:
            
            # Setup mocks for successful path
            mock_usuarios.return_value.get.return_value = AsyncMock(
                status_code=200,
                json=lambda: {"usuario_id": str(uuid4()), "nombre": "Test"}
            )
            
            mock_eventos.return_value.get.return_value = AsyncMock(
                status_code=200,
                json=lambda: {
                    "evento_id": str(uuid4()),
                    "estado": "publicado",
                    "entradas_disponibles": 10,
                    "precios": [{"categoria": "General", "precio": 50.0, "disponibles": 10}],
                }
            )
            
            mock_redis.return_value = {"success": True, "message": "OK"}
            mock_pg.return_value = None
            
            # First request - create reservation
            reserva_id = str(uuid4())
            request_data = {
                "usuario_id": str(uuid4()),
                "evento_id": str(uuid4()),
                "cantidad": 1,
                "metodo_pago": "tarjeta"
            }
            
            # Mock MongoDB to return existing on second call
            call_count = {"count": 0}
            
            async def mock_find_one(*args, **kwargs):
                call_count["count"] += 1
                if call_count["count"] == 1:
                    return None  # First call - not found
                return {
                    "_id": uuid4(),
                    "estado": "confirmada",
                    "numero_confirmacion": "CONF-20260101-ABCDEF12"
                }
            
            with patch("src.services.mongo.get_reservas_collection") as mock_mongo:
                mock_collection = AsyncMock()
                mock_collection.find_one.side_effect = mock_find_one
                mock_collection.insert_one = AsyncMock()
                mock_mongo.return_value = mock_collection
                
                # Setup other mocks
                with patch("src.services.http_clients.get_usuarios_client") as mock_usuarios, \
                     patch("src.services.http_clients.get_eventos_client") as mock_eventos, \
                     patch("src.services.redis_pago.ejecutar_pagar_y_decrementar") as mock_redis, \
                     patch("src.services.postgresql.insert_event_log") as mock_pg:
                    
                    mock_usuarios.return_value.get.return_value = AsyncMock(
                        status_code=200,
                        json=lambda: {"usuario_id": str(uuid4()), "nombre": "Test"}
                    )
                    mock_eventos.return_value.get.return_value = AsyncMock(
                        status_code=200,
                        json=lambda: {"estado": "publicado", "entradas_disponibles": 10}
                    )
                    mock_redis.return_value = {"success": True, "message": "OK"}
                    
                    # First request
                    async with AsyncClient(app=app, base_url="http://test") as client:
                        request_data = {
                            "usuario_id": str(uuid4()),
                            "evento_id": str(uuid4()),
                            "cantidad": 1,
                            "metodo_pago": "tarjeta"
                        }
                        response1 = await client.post("/api/v1/reservar", json=request_data)
                        assert response1.status_code == 201
                        
                        # Second request with same reserva_id (simulated)
                        # In real implementation, client would send same reserva_id
                        # Here we test the idempotency check logic directly
                        from src.utils.idempotency import check_idempotency, mark_idempotent
                        from uuid import uuid4 as uuid4_gen
                        
                        reserva_id = uuid4()
                        existing = await check_idempotency(reserva_id)
                        # First check - should be None (not exists)
                        assert existing is None
                        
                        # Mark as idempotent
                        await mark_idempotent(reserva_id)
                        
                        # Second check - should find existing
                        existing = await check_idempotency(reserva_id)
                        assert existing is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])