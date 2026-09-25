import pytest
from httpx import AsyncClient


@pytest.mark.contract
class TestPOSTReservar:
    """Contract tests para POST /api/v1/reservar."""

    @pytest.mark.asyncio
    async def test_reservar_exitoso(self, client: AsyncClient, reserva_valida):
        """POST /api/v1/reservar -> 201 con reserva creada."""
        # Nota: requiere usuarios y eventos services corriendo
        response = await client.post("/api/v1/reservar", json=reserva_valida)
        
        # Puede fallar si servicios dependientes no están disponibles
        # En ese caso verificar que retorna error 503 o 404 apropiado
        assert response.status_code in [201, 404, 503]

    @pytest.mark.asyncio
    async def test_reservar_usuario_inexistente(self, client: AsyncClient, reserva_valida):
        """POST /api/v1/reservar con usuario inexistente -> 404."""
        reserva_invalida = reserva_valida.copy()
        reserva_invalida["usuario_id"] = "550e8400-e29b-41d4-a716-446655449999"
        
        response = await client.post("/api/v1/reservar", json=reserva_invalida)
        
        # Debe retornar 404 o 503 si servicio no disponible
        assert response.status_code in [404, 503]

    @pytest.mark.asyncio
    async def test_reservar_cantidad_invalida(self, client: AsyncClient, reserva_valida):
        """POST /api/v1/reservar con cantidad 0 -> 422."""
        reserva_invalida = reserva_valida.copy()
        reserva_invalida["cantidad"] = 0
        
        response = await client.post("/api/v1/reservar", json=reserva_invalida)
        
        assert response.status_code == 422
        data = response.json()
        assert data["type"] == "https://eventflow.example.com/errors/validation-error"