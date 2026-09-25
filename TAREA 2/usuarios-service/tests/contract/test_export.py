import pytest
from httpx import AsyncClient


@pytest.mark.contract
class TestExportUsuarios:
    """Contract tests para GET /api/usuarios/exportar."""

    @pytest.mark.asyncio
    async def test_exportar_json(self, client: AsyncClient, usuario_valido):
        """GET /api/usuarios/exportar?format=json -> 200 con usuarios anonimizados."""
        await client.post("/api/usuarios", json=usuario_valido)

        response = await client.get("/api/usuarios/exportar?format=json")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) >= 1

        usuario = data[0]
        # Verificar campos anonimizados
        assert "usuario_id_hash" in usuario
        assert "nro_documento_hash" in usuario
        assert "nombre_hash" in usuario
        assert "apellido_hash" in usuario
        assert "email_hash" in usuario
        # NO debe tener datos reales
        assert "nombre" not in usuario
        assert "email" not in usuario
        assert "nro_documento" not in usuario

    @pytest.mark.asyncio
    async def test_exportar_formato_invalido(self, client: AsyncClient):
        """GET /api/usuarios/exportar?format=xml -> 400 Bad Request."""
        response = await client.get("/api/usuarios/exportar?format=xml")

        assert response.status_code == 400
        data = response.json()
        assert data["status"] == 400

    @pytest.mark.asyncio
    async def test_exportar_json_explicit(self, client: AsyncClient, usuario_valido):
        """GET /api/usuarios/exportar?format=json -> 200."""
        await client.post("/api/usuarios", json=usuario_valido)

        response = await client.get("/api/usuarios/exportar?format=json")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)