"""Test SAGA success rate measurement (RP-SC-006)."""
import pytest
from unittest.mock import AsyncMock, patch
from src.services.postgresql import get_saga_success_rate


class TestSAGASuccessRate:
    """Tests for SAGA success rate measurement (RP-SC-006)."""

    @pytest.mark.integration
    async def test_success_rate_calculation(self):
        """Test success rate calculation from event_log."""
        with patch("src.services.postgresql.get_pg_pool") as mock_pool:
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value.fetchrow = AsyncMock(
                return_value={"exitosas": 95, "fallidas": 5}
            )
            mock_pool.__aenter__.return_value = mock_pool
            mock_pool.__aexit__ = AsyncMock()
            mock_pool.return_value = mock_pool
            
            # Need to mock the pool properly
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(
                return_value=AsyncMock(
                    fetchrow=AsyncMock(return_value={"exitosas": 950, "fallidas": 10})
                )
            )
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.services.postgresql.get_pg_pool", return_value=mock_pool):
                rate = await get_saga_success_rate(days=7)
                
                # 950 / (950 + 10) * 100 = 98.99%
                assert rate == 98.99

    @pytest.mark.integration
    async def test_success_rate_above_threshold(self):
        """Test success rate is above 99.9% threshold."""
        with patch("src.services.postgresql.get_pg_pool") as mock_pool:
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(
                return_value=AsyncMock(
                    fetchrow=AsyncMock(return_value={"exitosas": 999, "fallidas": 1})
                )
            )
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.services.postgresql.get_pg_pool", return_value=mock_pool):
                rate = await get_saga_success_rate(days=7)
                
                assert rate > 99.9, f"Success rate {rate}% is below 99.9% threshold"

    @pytest.mark.integration
    async def test_success_rate_zero_division_handling(self):
        """Test success rate handles zero divisions gracefully."""
        with patch("src.services.postgresql.get_pg_pool") as mock_pool:
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(
                return_value=AsyncMock(
                    fetchrow=AsyncMock(return_value={"exitosas": 0, "fallidas": 0})
                )
            )
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.services.postgresql.get_pg_pool", return_value=mock_pool):
                rate = await get_saga_success_rate(days=7)
                
                assert rate == 0.0  # No data should return 0%

    @pytest.mark.integration
    async def test_success_rate_mixed_data(self):
        """Test success rate with mixed success/failure data."""
        with patch("src.services.postgresql.get_pg_pool") as mock_pool:
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(
                return_value=AsyncMock(
                    fetchrow=AsyncMock(return_value={"exitosas": 9990, "fallidas": 10})
                )
            )
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.services.postgresql.get_pg_pool", return_value=mock_pool):
                rate = await get_saga_success_rate(days=7)
                
                # 9990 / 10000 = 99.9%
                assert rate == 99.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])