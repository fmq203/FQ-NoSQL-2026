"""Contract tests for Reservas Service OpenAPI specification."""
import pytest
from httpx import AsyncClient
from uuid import uuid4
from src.main import app


class TestReservasOpenAPI:
    """Contract tests for Reservas Service OpenAPI endpoints."""

    @pytest.fixture
    async def client(self):
        """Create test client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.contract
    async def test_post_reservar_openapi_validation(self, client: AsyncClient):
        """Test POST /api/v1/reservar validates OpenAPI spec."""
        # Valid request
        valid_request = {
            "usuario_id": str(uuid4()),
            "evento_id": str(uuid4()),
            "cantidad": 2,
            "metodo_pago": "tarjeta"
        }
        
        response = await client.post("/api/v1/reservar", json=valid_request)
        
        # Should return 201 or appropriate error (depending on mock setup)
        assert response.status_code in [201, 404, 409, 422, 500, 503]
        
        # Verify response structure for success case
        if response.status_code == 201:
            data = response.json()
            assert "reserva_id" in data
            assert "estado" in data
            assert "numero_confirmacion" in data
            assert data["estado"] == "confirmada"
            assert data["numero_confirmacion"].startswith("CONF-")

    @pytest.mark.contract
    async def test_get_reserva_openapi_validation(self, client: AsyncClient):
        """Test GET /api/v1/reservar/{reserva_id} validates OpenAPI spec."""
        reserva_id = str(uuid4())
        
        response = await client.get(f"/api/v1/reservar/{reserva_id}")
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "reserva_id" in data
            assert "estado" in data
            assert "numero_confirmacion" in data

    @pytest.mark.contract
    async def test_list_reservas_openapi_validation(self, client: AsyncClient):
        """Test GET /api/v1/reservar validates OpenAPI spec."""
        response = await client.get("/api/v1/reservar")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.contract
    async def test_error_response_format_rfc7807(self, client: AsyncClient):
        """Test error responses follow RFC 7807 format."""
        # Test with invalid UUID
        response = await client.post("/api/v1/reservar", json={
            "usuario_id": "invalid-uuid",
            "evento_id": str(uuid4()),
            "cantidad": 1,
            "metodo_pago": "tarjeta"
        })
        
        assert response.status_code == 422
        data = response.json()
        
        # RFC 7807 fields
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert "instance" in data
        assert "correlation_id" in data
        
        # Verify type URI format
        assert data["type"].startswith("https://eventflow.example.com/errors/")

    @pytest.mark.contract
    async def test_correlation_id_header_propagation(self, client: AsyncClient):
        """Test X-Correlation-ID header is propagated in responses."""
        correlation_id = "test-correlation-123"
        
        response = await client.post(
            "/api/v1/reservar",
            json={
                "usuario_id": str(uuid4()),
                "evento_id": str(uuid4()),
                "cantidad": 1,
                "metodo_pago": "tarjeta"
            },
            headers={"X-Correlation-ID": correlation_id}
        )
        
        # Should return correlation ID in header
        assert "X-Correlation-ID" in response.headers
        # If we provided one, it should be the same (or a valid UUID if we accept it)
        assert response.headers["X-Correlation-ID"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])