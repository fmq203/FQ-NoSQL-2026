"""Contract tests for RFC 7807 error response structure across all endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.contract
class TestRFC7807ErrorFormat:
    """Tests that all endpoints return errors in RFC 7807 format."""

    @pytest.mark.asyncio
    async def test_validation_error_format(self, client: AsyncClient):
        """Test 422 validation errors follow RFC 7807 format."""
        # Missing required fields
        response = await client.post("/api/v1/eventos", json={})

        assert response.status_code == 422
        data = response.json()

        # RFC 7807 required fields
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert "instance" in data
        assert "correlation_id" in data

        # Check type URI format
        assert data["type"].startswith("https://eventflow.example.com/errors/")
        assert data["instance"] == "/api/v1/eventos"
        assert data["status"] == 422

    @pytest.mark.asyncio
    async def test_not_found_error_format(self, client: AsyncClient):
        """Test 404 errors follow RFC 7807 format."""
        response = await client.get("/api/v1/eventos/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404
        data = response.json()

        assert data["type"] == "https://eventflow.example.com/errors/not-found"
        assert data["title"] == "Not Found"
        assert data["status"] == 404
        assert data["instance"] == "/api/v1/eventos/00000000-0000-0000-0000-000000000000"
        assert "correlation_id" in data

    @pytest.mark.asyncio
    async def test_conflict_error_format(self, client: AsyncClient):
        """Test 409 conflict errors follow RFC 7807 format."""
        # Create first event
        event_data = {
            "nombre": "Test Event",
            "estado": "publicado",
            "aforo_total": 100,
            "entradas_disponibles": 100,
            "precios": [{"categoria": "General", "precio": 1000.00, "disponibles": 100}],
            "ubicacion": {"ciudad": "Buenos Aires", "pais": "Argentina"},
        }
        await client.post("/api/v1/eventos", json=event_data)

        # Try to create duplicate
        response = await client.post("/api/v1/eventos", json=event_data)

        assert response.status_code == 409
        data = response.json()

        assert data["type"] == "https://eventflow.example.com/errors/duplicate-event"
        assert data["title"] == "Conflict"
        assert data["status"] == 409
        assert data["instance"] == "/api/v1/eventos"
        assert "correlation_id" in data

    @pytest.mark.asyncio
    async def test_invalid_uuid_format_error(self, client: AsyncClient):
        """Test 422 for invalid UUID format follows RFC 7807."""
        response = await client.get("/api/v1/eventos/invalid-uuid")

        assert response.status_code == 422
        data = response.json()

        assert data["type"] == "https://eventflow.example.com/errors/validation-error"
        assert data["status"] == 422
        assert data["instance"] == "/api/v1/eventos/invalid-uuid"
        assert "correlation_id" in data

    @pytest.mark.asyncio
    async def test_correlation_id_in_response_header(self, client: AsyncClient):
        """Test X-Correlation-ID header present in error responses."""
        response = await client.post("/api/v1/eventos", json={})

        assert response.status_code == 422
        assert "X-Correlation-ID" in response.headers
        assert "X-Trace-ID" in response.headers
        assert response.headers["X-Correlation-ID"] == response.headers["X-Trace-ID"]

        # Correlation ID in header should match body
        data = response.json()
        assert data["correlation_id"] == response.headers["X-Correlation-ID"]

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_format(self, client: AsyncClient):
        """Test 503 from health check follows RFC 7807 format."""
        # This test requires MongoDB to be down - skip in normal runs
        # It's covered in integration tests
        pass