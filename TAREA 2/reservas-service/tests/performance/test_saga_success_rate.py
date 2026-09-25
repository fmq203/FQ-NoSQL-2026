"""Test SAGA success rate measurement (RP-SC-006)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.postgresql import get_saga_success_rate


class TestSAGASuccessRate:
    """Tests for SAGA success rate measurement (RP-SC-006).

    get_saga_success_rate(hours: int = 24) -> dict with keys
    exitosas/fallidas/total/tasa_exito_pct - see postgresql.py. These
    tests were originally written against a different assumed contract
    (a `days` parameter, a bare float return) that the actual
    implementation never had; updated to match the real one instead of
    changing working, more informative production code (the dict form
    carries the raw counts, not just the percentage) to fit tests that
    predated it.
    """

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
            result = await get_saga_success_rate(hours=24 * 7)

            assert result["exitosas"] == 950
            assert result["fallidas"] == 10
            assert result["total"] == 960
            # 950 / 960 * 100 = 98.96%
            assert abs(result["tasa_exito_pct"] - 98.96) < 0.01

    @pytest.mark.integration
    async def test_success_rate_above_threshold(self, mock_pool):
        """Test success rate is above 99.9% threshold."""
        pool, conn = mock_pool
        conn.fetchrow = AsyncMock(return_value={"exitosas": 999, "fallidas": 1})

        with patch("src.services.postgresql.get_pg_pool", return_value=pool):
            result = await get_saga_success_rate(hours=24 * 7)

            assert result["tasa_exito_pct"] >= 99.9, \
                f"Success rate {result['tasa_exito_pct']}% is below 99.9% threshold"

    @pytest.mark.integration
    async def test_success_rate_zero_division_handling(self, mock_pool):
        """Test success rate handles the no-data case gracefully (no SAGAs ran)."""
        pool, conn = mock_pool
        conn.fetchrow = AsyncMock(return_value={"exitosas": 0, "fallidas": 0})

        with patch("src.services.postgresql.get_pg_pool", return_value=pool):
            result = await get_saga_success_rate(hours=24 * 7)

            assert result["total"] == 0
            # None (no data), not 0.0 - a 0% rate would imply SAGAs ran and
            # all failed, which isn't what "nothing ran" means.
            assert result["tasa_exito_pct"] is None

    @pytest.mark.integration
    async def test_success_rate_mixed_data(self, mock_pool):
        """Test success rate with mixed success/failure data."""
        pool, conn = mock_pool
        conn.fetchrow = AsyncMock(return_value={"exitosas": 9990, "fallidas": 10})

        with patch("src.services.postgresql.get_pg_pool", return_value=pool):
            result = await get_saga_success_rate(hours=24 * 7)

            # 9990 / 10000 = 99.9%
            assert result["tasa_exito_pct"] == 99.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
