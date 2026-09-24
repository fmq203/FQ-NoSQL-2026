import pytest
from httpx import AsyncClient


class TestHealthIntegration:
    @pytest.mark.asyncio
    async def test_health_check_with_mongodb(self, async_client: AsyncClient):
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["checks"]["mongodb"] == "ok"
        assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_health_check_correlation_id(self, async_client: AsyncClient):
        correlation_id = "550e8400-e29b-41d4-a716-446655440002"
        response = await async_client.get(
            "/health",
            headers={"X-Correlation-ID": correlation_id}
        )
        assert response.status_code == 200
        assert response.headers.get("X-Correlation-ID") == correlation_id
        assert response.headers.get("X-Trace-ID") == correlation_id