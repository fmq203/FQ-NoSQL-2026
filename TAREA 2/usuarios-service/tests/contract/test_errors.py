import pytest
from httpx import AsyncClient
from uuid import uuid4


@pytest.mark.contract
class TestRFC7807ErrorFormat:
    """Tests para validar formato RFC 7807 en todos los endpoints."""

    @pytest.mark.asyncio
    async def test_error_formato_rfc7807(self, client: AsyncClient):
        """Todos los errores deben seguir formato RFC 7807."""
        # Test POST /api/usuarios con email inválido
        response = await client.post("/api/usuarios", json={
            "tipo_documento": "DNI",
            "nro_documento": "12345678",
            "nombre": "Test",
            "apellido": "User",
            "email": "invalid-email"
        })

        assert response.status_code == 422
        data = response.json()

        # RFC 7807 required fields
        assert "type" in data
        assert "title" in data
        assert "status" in data
        assert "detail" in data
        assert "instance" in data
        assert "correlation_id" in data

        # Verificar formato type URI
        assert data["type"].startswith("https://eventflow.example.com/errors/")
        assert data["instance"] == "/api/usuarios"
        assert data["status"] == 422

    @pytest.mark.asyncio
    async def test_correlation_id_en_header_y_body(self, client: AsyncClient):
        """X-Correlation-ID en header debe coincidir con correlation_id en body."""
        response = await client.post("/api/usuarios", json={
            "tipo_documento": "DNI",
            "nro_documento": "12345678",
            "nombre": "Test",
            "apellido": "User",
            "email": "invalid-email"
        })

        assert response.status_code == 422
        assert "X-Correlation-ID" in response.headers
        assert "X-Trace-ID" in response.headers
        assert response.headers["X-Correlation-ID"] == response.headers["X-Trace-ID"]

        data = response.json()
        assert data["correlation_id"] == response.headers["X-Correlation-ID"]

    @pytest.mark.asyncio
    async def test_error_404_formato(self, client: AsyncClient):
        """GET /api/usuarios/{uuid_inexistente} -> 404 con formato RFC 7807."""
        from uuid import uuid4
        response = await client.get(f"/api/usuarios/{uuid4()}")

        assert response.status_code == 404
        data = response.json()

        assert data["type"] == "https://eventflow.example.com/errors/not-found"
        assert data["title"] == "Not Found"
        assert data["status"] == 404
        assert "correlation_id" in data
        assert data["instance"] == f"/api/usuarios/{str(uuid4())}" or "/api/usuarios/" in data["instance"]

    @pytest.mark.asyncio
    async def test_error_422_uuid_invalido(self, client: AsyncClient):
        """GET /api/usuarios/uuid-invalido -> 422 RFC 7807."""
        response = await client.get("/api/usuarios/uuid-invalido")

        assert response.status_code == 422
        data = response.json()

        assert data["type"] == "https://eventflow.example.com/errors/validation-error"
        assert data["status"] == 422
        assert "correlation_id" in data