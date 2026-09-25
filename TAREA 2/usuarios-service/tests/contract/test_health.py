import pytest
from httpx import AsyncClient


@pytest.mark.contract
class TestHealthCheck:
    """Contract tests para GET /health."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, client: AsyncClient):
        """GET /health -> 200 con estado healthy/degraded."""
        response = await client.get("/health")

        assert response.status_code in [200, 503]
        data = response.json()

        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "checks" in data
        assert "mongodb" in data["checks"]
        assert data["checks"]["mongodb"] in ["ok", "slow", "down"]
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_health_check_headers(self, client: AsyncClient):
        """GET /health incluye headers de tracing."""
        response = await client.get("/health")

        assert "X-Correlation-ID" in response.headers
        assert "X-Trace-ID" in response.headers
        assert response.headers["X-Correlation-ID"] == response.headers["X-Trace-ID"]