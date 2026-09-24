import pytest
from httpx import AsyncClient


class TestHealthContract:
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, async_client: AsyncClient):
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "checks" in data
        assert "mongodb" in data["checks"]
        assert data["checks"]["mongodb"] in ["ok", "slow", "down"]
        assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_health_check_response_structure(self, async_client: AsyncClient):
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields
        assert "status" in data
        assert "checks" in data
        assert "timestamp" in data
        
        # Verify status is one of expected values
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        
        # Verify checks structure
        assert isinstance(data["checks"], dict)
        assert "mongodb" in data["checks"]
        assert data["checks"]["mongodb"] in ["ok", "slow", "down"]
        
        # Verify timestamp is ISO format
        import datetime
        timestamp = data["timestamp"]
        assert "T" in timestamp
        assert timestamp.endswith("Z") or "+" in timestamp