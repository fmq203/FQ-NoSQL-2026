import pytest
from unittest.mock import AsyncMock, patch
from src.services.health_service import HealthService
from src.models.health import HealthStatus, MongoDBHealth


class TestHealthService:
    @pytest.fixture
    def mock_ping(self):
        with patch("src.services.health_service.ping_mongodb") as mock:
            yield mock
    
    @pytest.fixture
    def service(self):
        return HealthService()
    
    @pytest.mark.asyncio
    async def test_check_health_healthy(self, service, mock_ping):
        mock_ping.return_value = (True, 10.0)  # success, latency 10ms
        
        result = await service.check_health()
        
        assert result.status == HealthStatus.HEALTHY
        assert result.checks["mongodb"] == MongoDBHealth.OK
        assert result.timestamp is not None
    
    @pytest.mark.asyncio
    async def test_check_health_degraded(self, service, mock_ping):
        mock_ping.return_value = (True, 100.0)  # success, latency 100ms
        
        result = await service.check_health()
        
        assert result.status == HealthStatus.DEGRADED
        assert result.checks["mongodb"] == MongoDBHealth.SLOW
    
    @pytest.mark.asyncio
    async def test_check_health_unhealthy_ping_failed(self, service, mock_ping):
        mock_ping.return_value = (False, 2000.0)  # failed
        
        result = await service.check_health()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert result.checks["mongodb"] == MongoDBHealth.DOWN
    
    @pytest.mark.asyncio
    async def test_check_health_unhealthy_high_latency(self, service, mock_ping):
        mock_ping.return_value = (True, 600.0)  # success but latency > 500ms
        
        result = await service.check_health()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert result.checks["mongodb"] == MongoDBHealth.DOWN
    
    @pytest.mark.asyncio
    async def test_check_health_boundary_healthy(self, service, mock_ping):
        """Test boundary: exactly 50ms should be degraded"""
        mock_ping.return_value = (True, 50.0)
        
        result = await service.check_health()
        
        assert result.status == HealthStatus.DEGRADED
        assert result.checks["mongodb"] == MongoDBHealth.SLOW
    
    @pytest.mark.asyncio
    async def test_check_health_boundary_degraded(self, service, mock_ping):
        """Test boundary: exactly 500ms should be unhealthy"""
        mock_ping.return_value = (True, 500.0)
        
        result = await service.check_health()
        
        assert result.status == HealthStatus.UNHEALTHY
        assert result.checks["mongodb"] == MongoDBHealth.DOWN