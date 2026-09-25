"""Unit tests for 5-second MongoDB down detection logic in health check."""

import pytest
from unittest.mock import AsyncMock, patch
from src.services.health_service import HealthService
from src.models.health import HealthStatus, MongoDBHealth


@pytest.mark.unit
class TestHealthCheck5sDetection:
    """Tests for MongoDB down detection within 5 seconds."""

    @pytest.mark.asyncio
    async def test_mongodb_down_returns_unhealthy_within_5s(self):
        """Test that health check returns unhealthy within 5s when MongoDB is down."""
        service = HealthService()

        # Mock ping_mongodb to simulate MongoDB down (connection refused)
        with patch("src.services.health_service.ping_mongodb", new_callable=AsyncMock) as mock_ping:
            mock_ping.return_value = (False, 2000.0)  # Failed, 2s timeout

            result = await service.check_health()

            assert result.status == HealthStatus.UNHEALTHY
            assert result.checks["mongodb"] == MongoDBHealth.DOWN
            # Verify ping was called with 2s timeout
            mock_ping.assert_called_once_with(2000)

    @pytest.mark.asyncio
    async def test_mongodb_timeout_returns_unhealthy_within_5s(self):
        """Test that health check returns unhealthy within 5s when MongoDB times out."""
        service = HealthService()

        with patch("src.services.health_service.ping_mongodb", new_callable=AsyncMock) as mock_ping:
            mock_ping.return_value = (False, 2000.0)  # Timeout after 2s

            result = await service.check_health()

            assert result.status == HealthStatus.UNHEALTHY
            assert result.checks["mongodb"] == MongoDBHealth.DOWN

    @pytest.mark.asyncio
    async def test_mongodb_slow_returns_degraded(self):
        """Test that health check returns degraded for 50-500ms latency."""
        service = HealthService()

        with patch("src.services.health_service.ping_mongodb", new_callable=AsyncMock) as mock_ping:
            mock_ping.return_value = (True, 100.0)  # Success, 100ms latency

            result = await service.check_health()

            assert result.status == HealthStatus.DEGRADED
            assert result.checks["mongodb"] == MongoDBHealth.SLOW

    @pytest.mark.asyncio
    async def test_mongodb_fast_returns_healthy(self):
        """Test that health check returns healthy for <50ms latency."""
        service = HealthService()

        with patch("src.services.health_service.ping_mongodb", new_callable=AsyncMock) as mock_ping:
            mock_ping.return_value = (True, 25.0)  # Success, 25ms latency

            result = await service.check_health()

            assert result.status == HealthStatus.HEALTHY
            assert result.checks["mongodb"] == MongoDBHealth.OK

    @pytest.mark.asyncio
    async def test_health_check_latency_thresholds(self):
        """Test exact latency threshold boundaries."""
        service = HealthService()

        test_cases = [
            # (latency_ms, expected_status, expected_mongodb_status)
            (49.9, HealthStatus.HEALTHY, MongoDBHealth.OK),  # Just under 50ms
            (50.0, HealthStatus.DEGRADED, MongoDBHealth.SLOW),  # Exactly 50ms
            (250.0, HealthStatus.DEGRADED, MongoDBHealth.SLOW),  # Middle of degraded
            (500.0, HealthStatus.DEGRADED, MongoDBHealth.SLOW),  # Exactly 500ms
            (500.1, HealthStatus.UNHEALTHY, MongoDBHealth.DOWN),  # Just over 500ms
        ]

        for latency_ms, expected_status, expected_mongodb in test_cases:
            with patch("src.services.health_service.ping_mongodb", new_callable=AsyncMock) as mock_ping:
                mock_ping.return_value = (True, latency_ms)

                result = await service.check_health()

                assert result.status == expected_status, f"Failed for latency {latency_ms}ms"
                assert result.checks["mongodb"] == expected_mongodb, f"Failed for latency {latency_ms}ms"