import pytest
from httpx import AsyncClient
from uuid import uuid4


@pytest.mark.integration
class TestUsuariosCRUD:
    """Integration tests para flujo completo CRUD usuarios."""

    @pytest.mark.asyncio
    async def test_flujo_completo_crear_obtener_listar(self, client: AsyncClient, usuario_valido):
        """Test flujo: crear -> obtener -> listar."""
        # 1. Crear usuario
        create_response = await client.post("/api/usuarios", json=usuario_valido)
        assert create_response.status_code == 201
        created = create_response.json()
        usuario_id = created["usuario_id"]

        # 2. Obtener usuario
        get_response = await client.get(f"/api/usuarios/{usuario_id}")
        assert get_response.status_code == 200
        retrieved = get_response.json()
        assert retrieved["usuario_id"] == str(usuario_id)
        assert retrieved["email"] == usuario_valido["email"]

        # 3. Listar usuarios
        list_response = await client.get("/api/usuarios?skip=0&limit=10")
        assert list_response.status_code == 200
        users = list_response.json()
        assert isinstance(users, list)
        assert any(u["usuario_id"] == str(usuario_id) for u in users)

    @pytest.mark.asyncio
    async def test_crear_usuario_con_historial_vacio(self, client: AsyncClient, usuario_valido):
        """Usuario nuevo debe tener historial_compras vacío."""
        response = await client.post("/api/usuarios", json=usuario_valido)
        assert response.status_code == 201
        data = response.json()
        assert data["historial_compras"] == []

    @pytest.mark.asyncio
    async def test_unicidad_email_y_documento(self, client: AsyncClient, usuario_valido):
        """Email y nro_documento deben ser únicos."""
        # Crear primer usuario
        await client.post("/api/usuarios", json=usuario_valido)

        # Intentar mismo email
        response_email = await client.post("/api/usuarios", json=usuario_valido)
        assert response_email.status_code == 409

        # Intentar mismo documento, distinto email
        usuario_dup = usuario_valido.copy()
        usuario_dup["email"] = "otro@example.com"
        response_doc = await client.post("/api/usuarios", json=usuario_dup)
        assert response_doc.status_code == 409


@pytest.mark.integration
class TestHealthCheck:
    """Integration tests para health check."""

    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, client: AsyncClient):
        """Health check debe responder con estructura correcta."""
        response = await client.get("/health")
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert "mongodb" in data["checks"]