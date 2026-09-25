import pytest
from httpx import AsyncClient


@pytest.mark.contract
class TestPOSTUsuarios:
    """Contract tests para POST /api/usuarios."""

    @pytest.mark.asyncio
    async def test_crear_usuario_exitoso(self, client: AsyncClient, usuario_valido):
        """POST /api/usuarios con JSON válido -> 201 con usuario_id."""
        response = await client.post("/api/usuarios", json=usuario_valido)

        assert response.status_code == 201
        data = response.json()

        # Verificar campos requeridos en response
        assert "usuario_id" in data
        assert data["nombre"] == usuario_valido["nombre"]
        assert data["apellido"] == usuario_valido["apellido"]
        assert data["email"] == usuario_valido["email"]
        assert data["tipo_documento"] == usuario_valido["tipo_documento"]
        assert data["nro_documento"] == usuario_valido["nro_documento"]
        assert "creado_en" in data
        assert "actualizado_en" in data
        assert "historial_compras" in data
        assert isinstance(data["historial_compras"], list)

    @pytest.mark.asyncio
    async def test_crear_usuario_email_duplicado(self, client: AsyncClient, usuario_valido):
        """POST /api/usuarios con email existente -> 409 Conflict."""
        # Crear primer usuario
        await client.post("/api/usuarios", json=usuario_valido)

        # Intentar crear con mismo email
        response = await client.post("/api/usuarios", json=usuario_valido)

        assert response.status_code == 409
        data = response.json()
        assert data["type"] == "https://eventflow.example.com/errors/duplicate-resource"
        assert data["title"] == "Conflict"
        assert data["status"] == 409
        assert "correlation_id" in data

    @pytest.mark.asyncio
    async def test_crear_usuario_documento_duplicado(self, client: AsyncClient, usuario_valido):
        """POST /api/usuarios con nro_documento existente -> 409 Conflict."""
        await client.post("/api/usuarios", json=usuario_valido)

        # Mismo documento, diferente email
        usuario_dup = usuario_valido.copy()
        usuario_dup["email"] = "otro@example.com"
        response = await client.post("/api/usuarios", json=usuario_dup)

        assert response.status_code == 409
        data = response.json()
        assert data["type"] == "https://eventflow.example.com/errors/duplicate-resource"

    @pytest.mark.asyncio
    async def test_crear_usuario_email_invalido(self, client: AsyncClient, usuario_valido):
        """POST /api/usuarios con email inválido -> 422 Validation Error."""
        usuario_invalido = usuario_valido.copy()
        usuario_invalido["email"] = "email-invalido"

        response = await client.post("/api/usuarios", json=usuario_invalido)

        assert response.status_code == 422
        data = response.json()
        assert data["type"] == "https://eventflow.example.com/errors/validation-error"
        assert data["status"] == 422

    @pytest.mark.asyncio
    async def test_crear_usuario_tipo_documento_invalido(self, client: AsyncClient, usuario_valido):
        """POST /api/usuarios con tipo_documento inválido -> 422."""
        usuario_invalido = usuario_valido.copy()
        usuario_invalido["tipo_documento"] = "CEDULA"

        response = await client.post("/api/usuarios", json=usuario_invalido)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_crear_usuario_campos_faltantes(self, client: AsyncClient):
        """POST /api/usuarios sin campos obligatorios -> 422."""
        response = await client.post("/api/usuarios", json={"nombre": "Juan"})

        assert response.status_code == 422