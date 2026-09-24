import pytest
from httpx import AsyncClient
from uuid import UUID


class TestEventosPostContract:
    @pytest.mark.asyncio
    async def test_create_event_valid(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/eventos",
            json={
                "nombre": "Concierto Rock 2026",
                "estado": "publicado",
                "aforo_total": 5000,
                "entradas_disponibles": 5000,
                "precios": [
                    {"categoria": "VIP", "precio": 15000.00, "disponibles": 100},
                    {"categoria": "General", "precio": 5000.00, "disponibles": 4900}
                ],
                "ubicacion": {
                    "ciudad": "Buenos Aires",
                    "pais": "Argentina",
                    "direccion": "Estadio Luna Park"
                }
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert "evento_id" in data
        assert UUID(data["evento_id"])
        assert data["nombre"] == "Concierto Rock 2026"
        assert data["estado"] == "publicado"
        assert data["aforo_total"] == 5000
        assert data["entradas_disponibles"] == 5000
        assert len(data["precios"]) == 2
        assert "creado_en" in data
        assert "actualizado_en" in data
    
    @pytest.mark.asyncio
    async def test_create_event_aforo_exceeded(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/eventos",
            json={
                "nombre": "Test Event",
                "estado": "publicado",
                "aforo_total": 100,
                "entradas_disponibles": 200,
                "precios": [
                    {"categoria": "General", "precio": 100.00, "disponibles": 200}
                ],
                "ubicacion": {
                    "ciudad": "Buenos Aires",
                    "pais": "Argentina"
                }
            }
        )
        assert response.status_code == 422
        data = response.json()
        assert data["type"] == "https://eventflow.example.com/errors/validation-error"
        assert data["status"] == 422
    
    @pytest.mark.asyncio
    async def test_create_event_negative_price(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/eventos",
            json={
                "nombre": "Test Event",
                "estado": "publicado",
                "aforo_total": 100,
                "entradas_disponibles": 100,
                "precios": [
                    {"categoria": "VIP", "precio": -100.00, "disponibles": 50}
                ],
                "ubicacion": {
                    "ciudad": "Buenos Aires",
                    "pais": "Argentina"
                }
            }
        )
        assert response.status_code == 422
        data = response.json()
        assert data["type"] == "https://eventflow.example.com/errors/validation-error"
    
    @pytest.mark.asyncio
    async def test_create_event_duplicate_categoria(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/eventos",
            json={
                "nombre": "Test Event",
                "estado": "publicado",
                "aforo_total": 100,
                "entradas_disponibles": 100,
                "precios": [
                    {"categoria": "VIP", "precio": 100.00, "disponibles": 50},
                    {"categoria": "VIP", "precio": 200.00, "disponibles": 50}
                ],
                "ubicacion": {
                    "ciudad": "Buenos Aires",
                    "pais": "Argentina"
                }
            }
        )
        assert response.status_code == 422
        data = response.json()
        assert data["type"] == "https://eventflow.example.com/errors/validation-error"
    
    @pytest.mark.asyncio
    async def test_create_event_invalid_estado(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/eventos",
            json={
                "nombre": "Test Event",
                "estado": "invalido",
                "aforo_total": 100,
                "entradas_disponibles": 100,
                "precios": [
                    {"categoria": "VIP", "precio": 100.00, "disponibles": 100}
                ],
                "ubicacion": {
                    "ciudad": "Buenos Aires",
                    "pais": "Argentina"
                }
            }
        )
        assert response.status_code == 422
        data = response.json()
        assert data["type"] == "https://eventflow.example.com/errors/validation-error"
    
    @pytest.mark.asyncio
    async def test_create_event_precios_disponibles_exceeds_entradas(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/eventos",
            json={
                "nombre": "Test Event",
                "estado": "publicado",
                "aforo_total": 100,
                "entradas_disponibles": 100,
                "precios": [
                    {"categoria": "VIP", "precio": 100.00, "disponibles": 60},
                    {"categoria": "General", "precio": 50.00, "disponibles": 60}
                ],
                "ubicacion": {
                    "ciudad": "Buenos Aires",
                    "pais": "Argentina"
                }
            }
        )
        assert response.status_code == 422
        data = response.json()
        assert data["type"] == "https://eventflow.example.com/errors/validation-error"
    
    @pytest.mark.asyncio
    async def test_create_event_zero_aforo_valid(self, async_client: AsyncClient):
        response = await async_client.post(
            "/api/v1/eventos",
            json={
                "nombre": "Evento Borrador",
                "estado": "borrador",
                "aforo_total": 0,
                "entradas_disponibles": 0,
                "precios": [
                    {"categoria": "Gratis", "precio": 0.00, "disponibles": 0}
                ],
                "ubicacion": {
                    "ciudad": "Montevideo",
                    "pais": "Uruguay"
                }
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["aforo_total"] == 0
        assert data["entradas_disponibles"] == 0
        # Price can be "0.0" or "0.00" depending on JSON serialization
        assert float(data["precios"][0]["precio"]) == 0.0