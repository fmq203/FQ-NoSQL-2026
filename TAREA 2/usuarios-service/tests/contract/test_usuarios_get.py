import pytest
from httpx import AsyncClient


@pytest.mark.contract
class TestGETUsuarios:
    """Contract tests para GET /api/usuarios/{id} y GET /api/usuarios."""

    @pytest.mark.asyncio
    async def test_obtener_usuario_existente(self, client: AsyncClient, usuario_valido):
        """GET /api/usuarios/{id} -> 200 con usuario completo."""
        # Crear usuario
        create_response = await client.post("/api/usuarios", json=usuario_valido)
        usuario_id = create_response.json()["usuario_id"]

        # Obtener usuario
        response = await client.get(f"/api/usuarios/{usuario_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["usuario_id"] == str(usuario_id)
        assert data["nombre"] == "Juan"
        assert data["apellido"] == "Pérez"
        assert data["email"] == "juan.perez@example.com"
        assert data["tipo_documento"] == "DNI"
        assert data["nro_documento"] == "12345678"
        assert "historial_compras" in data

    @pytest.mark.asyncio
    async def test_obtener_usuario_inexistente(self, client: AsyncClient):
        """GET /api/usuarios/{id_inexistente} -> 404 Not Found."""
        from uuid import uuid4
        response = await client.get(f"/api/usuarios/{uuid4()}")

        assert response.status_code == 404
        data = response.json()
        assert data["type"] == "https://eventflow.example.com/errors/not-found"
        assert data["title"] == "Not Found"
        assert data["status"] == 404

    @pytest.mark.asyncio
    async def test_obtener_usuario_uuid_invalido(self, client: AsyncClient):
        """GET /api/usuarios/uuid_invalido -> 422 Validation Error."""
        response = await client.get("/api/usuarios/uuid-invalido")

        assert response.status_code == 422
        data = response.json()
        assert data["type"] == "https://eventflow.example.com/errors/validation-error"
        assert data["status"] == 422

    @pytest.mark.asyncio
    async def test_listar_usuarios_paginado(self, client: AsyncClient, usuario_valido, usuario_valido_2):
        """GET /api/usuarios?skip=0&limit=10 -> 200 lista paginada."""
        # Crear dos usuarios
        await client.post("/api/usuarios", json=usuario_valido)
        await client.post("/api/usuarios", json=usuario_valido_2)

        # Listar
        response = await client.get("/api/usuarios?skip=0&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2