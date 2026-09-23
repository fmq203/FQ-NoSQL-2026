"""Test SAGA success rate measurement (RP-SC-006)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.postgresql import get_saga_success_rate


class TestSAGASuccessRate:
    """Tests for SAGA success rate measurement (RP-SC-006)."""

    @pytest.fixture
    def mock_pool(self):
        """Create a properly mocked asyncpg pool."""
        pool = AsyncMock()
        # acquire() returns an async context manager
        acquire_cm = AsyncMock()
        conn = AsyncMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=None)
        pool.acquire = MagicMock(return_value=acquire_cm)
        return pool, conn

    @pytest.mark.integration
    async def test_success_rate_calculation(self, mock_pool):
        """Test success rate calculation from event_log."""
        pool, conn = mock_pool
        conn.fetchrow = AsyncMock(return_value={"exitosas": 950, "fallidas": 10})
        
        with patch("src.services.postgresql.get_pg_pool", return_value=pool):
            rate = await get_saga_success_rate(days=7)
            
            # 950 / (950 + 10) * 100 = 98.99%
            assert abs(rate - 98.96) < 0.01

    @pytest.mark.integration
    async def test_success_rate_above_threshold(self, mock_pool):
        """Test success rate is above 99.9% threshold."""
        pool, conn = mock_pool
        conn.fetchrow = AsyncMock(return_value={"exitosas": 999, "fallidas": 1})
        
        with patch("src.services.postgresql.get_pg_pool", return_value=pool):
            rate = await get_saga_success_rate(days=7)
            
            assert rate >= 99.9, f"Success rate {rate}% is below 99.9% threshold"

    @pytest.mark.integration
    async def test_success_rate_zero_division_handling(self, mock_pool):
        """Test success rate handles zero divisions gracefully."""
        pool, conn = mock_pool
        conn.fetchrow = AsyncMock(return_value={"exitosas": 0, "fallidas": 0})
        
        with patch("src.services.postgresql.get_pg_pool", return_value=pool):
            rate = await get_saga_success_rate(days=7)
            
            assert rate == 0.0  # No data should return 0%

    @pytest.mark.integration
    async def test_success_rate_mixed_data(self, mock_pool):
        """Test success rate with mixed success/failure data."""
        pool, conn = mock_pool
        conn.fetchrow = AsyncMock(return_value={"exitosas": 9990, "fallidas": 10})
        
        with patch("src.services.postgresql.get_pg_pool", return_value=pool):
            rate = await get_saga_success_rate(days=7)
            
            # 9990 / 10000 = 99.9%
            assert rate == 99.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])