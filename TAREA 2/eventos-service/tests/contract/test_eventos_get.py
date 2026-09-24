import pytest
from httpx import AsyncClient
from uuid import UUID, uuid4


class TestEventosGetContract:
    @pytest.mark.asyncio
    async def test_get_event_existing(self, async_client: AsyncClient, created_event_id: str):
        response = await async_client.get(f"/api/v1/eventos/{created_event_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["evento_id"] == created_event_id
        assert "nombre" in data
        assert "estado" in data
        assert "aforo_total" in data
        assert "entradas_disponibles" in data
        assert "precios" in data
        assert "ubicacion" in data
        assert "creado_en" in data
        assert "actualizado_en" in data
    
    @pytest.mark.asyncio
    async def test_get_event_not_found(self, async_client: AsyncClient):
        non_existent_id = str(uuid4())
        response = await async_client.get(f"/api/v1/eventos/{non_existent_id}")
        assert response.status_code == 404
        data = response.json()
        assert data["type"] == "https://eventflow.example.com/errors/not-found"
        assert data["status"] == 404
        assert data["detail"] == "Evento no encontrado"
    
    @pytest.mark.asyncio
    async def test_get_event_invalid_uuid(self, async_client: AsyncClient):
        response = await async_client.get("/api/v1/eventos/invalid-uuid")
        assert response.status_code == 422
        data = response.json()
        assert data["type"] == "https://eventflow.example.com/errors/validation-error"
        assert data["status"] == 422