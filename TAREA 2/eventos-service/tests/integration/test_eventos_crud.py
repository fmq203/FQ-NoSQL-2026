import pytest
from httpx import AsyncClient
from uuid import uuid4


class TestEventosCRUDIntegration:
    @pytest.mark.asyncio
    async def test_create_and_get_event(self, async_client: AsyncClient):
        # Create event
        create_response = await async_client.post(
            "/api/eventos",
            json={
                "nombre": "Integration Test Event",
                "estado": "publicado",
                "aforo_total": 1000,
                "entradas_disponibles": 1000,
                "precios": [
                    {"categoria": "VIP", "precio": 5000.00, "disponibles": 100},
                    {"categoria": "General", "precio": 1000.00, "disponibles": 900}
                ],
                "ubicacion": {
                    "ciudad": "Córdoba",
                    "pais": "Argentina",
                    "direccion": "Estadio Kempes"
                }
            }
        )
        assert create_response.status_code == 201
        created_event = create_response.json()
        evento_id = created_event["evento_id"]
        
        # Get event
        get_response = await async_client.get(f"/api/eventos/{evento_id}")
        assert get_response.status_code == 200
        retrieved_event = get_response.json()
        
        # Verify all fields match
        assert retrieved_event["evento_id"] == evento_id
        assert retrieved_event["nombre"] == "Integration Test Event"
        assert retrieved_event["estado"] == "publicado"
        assert retrieved_event["aforo_total"] == 1000
        assert retrieved_event["entradas_disponibles"] == 1000
        assert len(retrieved_event["precios"]) == 2
        assert retrieved_event["ubicacion"]["ciudad"] == "Córdoba"
        assert retrieved_event["ubicacion"]["pais"] == "Argentina"
        assert retrieved_event["ubicacion"]["direccion"] == "Estadio Kempes"
    
    @pytest.mark.asyncio
    async def test_create_event_with_correlation_id(self, async_client: AsyncClient):
        correlation_id = "550e8400-e29b-41d4-a716-446655440000"
        response = await async_client.post(
            "/api/eventos",
            json={
                "nombre": "Correlation Test",
                "estado": "publicado",
                "aforo_total": 100,
                "entradas_disponibles": 100,
                "precios": [
                    {"categoria": "General", "precio": 100.00, "disponibles": 100}
                ],
                "ubicacion": {
                    "ciudad": "Buenos Aires",
                    "pais": "Argentina"
                }
            },
            headers={"X-Correlation-ID": correlation_id}
        )
        assert response.status_code == 201
        # Verify correlation ID is returned in headers
        assert response.headers.get("X-Correlation-ID") == correlation_id
        assert response.headers.get("X-Trace-ID") == correlation_id
    
    @pytest.mark.asyncio
    async def test_get_event_returns_correlation_id(self, async_client: AsyncClient):
        # Create event first
        create_response = await async_client.post(
            "/api/eventos",
            json={
                "nombre": "Test Event",
                "estado": "publicado",
                "aforo_total": 100,
                "entradas_disponibles": 100,
                "precios": [
                    {"categoria": "General", "precio": 100.00, "disponibles": 100}
                ],
                "ubicacion": {
                    "ciudad": "Buenos Aires",
                    "pais": "Argentina"
                }
            }
        )
        evento_id = create_response.json()["evento_id"]
        
        # Get event with correlation ID
        correlation_id = "550e8400-e29b-41d4-a716-446655440001"
        get_response = await async_client.get(
            f"/api/eventos/{evento_id}",
            headers={"X-Correlation-ID": correlation_id}
        )
        assert get_response.status_code == 200
        assert get_response.headers.get("X-Correlation-ID") == correlation_id
        assert get_response.headers.get("X-Trace-ID") == correlation_id


class TestHealthIntegration:
    @pytest.mark.asyncio
    async def test_health_check_integration(self, async_client: AsyncClient):
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        # Should be healthy with local MongoDB
        assert data["status"] == "healthy"
        assert data["checks"]["mongodb"] == "ok"