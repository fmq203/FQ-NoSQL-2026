import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
from src.services.health_service import HealthService
from src.models.health import HealthStatus, MongoDBHealth


@pytest.mark.unit
class TestHealthService:
    """Unit tests para HealthService."""

    @pytest.mark.asyncio
    async def test_mongodb_fast_returns_healthy(self):
        """MongoDB < 50ms -> healthy."""
        service = HealthService()

        with patch("src.services.health_service.ping_mongodb", new_callable=AsyncMock) as mock_ping:
            mock_ping.return_value = (True, 25.0)

            result = await service.check_health()

            assert result.status == HealthStatus.HEALTHY
            assert result.checks["mongodb"] == MongoDBHealth.OK.value

    @pytest.mark.asyncio
    async def test_mongodb_medium_returns_degraded(self):
        """MongoDB 50-500ms -> degraded."""
        service = HealthService()

        with patch("src.services.health_service.ping_mongodb", new_callable=AsyncMock) as mock_ping:
            mock_ping.return_value = (True, 150.0)

            result = await service.check_health()

            assert result.status == HealthStatus.DEGRADED
            assert result.checks["mongodb"] == MongoDBHealth.SLOW.value

    @pytest.mark.asyncio
    async def test_mongodb_slow_returns_unhealthy(self):
        """MongoDB > 500ms -> unhealthy."""
        service = HealthService()

        with patch("src.services.health_service.ping_mongodb", new_callable=AsyncMock) as mock_ping:
            mock_ping.return_value = (True, 600.0)

            result = await service.check_health()

            assert result.status == HealthStatus.UNHEALTHY
            assert result.checks["mongodb"] == MongoDBHealth.DOWN.value

    @pytest.mark.asyncio
    async def test_mongodb_failed_returns_unhealthy(self):
        """MongoDB falla -> unhealthy."""
        service = HealthService()

        with patch("src.services.health_service.ping_mongodb", new_callable=AsyncMock) as mock_ping:
            mock_ping.return_value = (False, 2000.0)

            result = await service.check_health()

            assert result.status == HealthStatus.UNHEALTHY
            assert result.checks["mongodb"] == MongoDBHealth.DOWN.value

    @pytest.mark.asyncio
    async def test_threshold_boundaries(self):
        """Probar límites exactos de umbrales."""
        service = HealthService()

        test_cases = [
            (49.9, HealthStatus.HEALTHY, MongoDBHealth.OK),
            (50.0, HealthStatus.DEGRADED, MongoDBHealth.SLOW),
            (250.0, HealthStatus.DEGRADED, MongoDBHealth.SLOW),
            (500.0, HealthStatus.DEGRADED, MongoDBHealth.SLOW),
            (500.1, HealthStatus.UNHEALTHY, MongoDBHealth.DOWN),
        ]

        for latency_ms, expected_status, expected_mongodb in test_cases:
            with patch("src.services.health_service.ping_mongodb", new_callable=AsyncMock) as mock_ping:
                mock_ping.return_value = (True, latency_ms)

                result = await service.check_health()

                assert result.status == expected_status, f"Failed for latency {latency_ms}ms"
                assert result.checks["mongodb"] == expected_mongodb.value, f"Failed for latency {latency_ms}ms"