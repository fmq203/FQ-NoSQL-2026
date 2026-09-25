"""Performance test for P99 latency under load."""
import pytest
import asyncio
import time
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from src.main import app


class TestSAGAP99:
    """P99 latency tests under load."""

    @pytest.fixture
    async def client(self):
        """Create test client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    def mock_all_services(self):
        """Mock all external services.

        Patched at src.chain.validators / src.api.routes.reservas (the
        actual call sites) - see test_double_booking.py for why patching
        the origin modules doesn't intercept an already-imported name.
        """
        with patch("src.chain.validators.get_usuario", new_callable=AsyncMock) as mock_get_usuario, \
             patch("src.chain.validators.get_evento", new_callable=AsyncMock) as mock_get_evento, \
             patch("src.chain.validators.ejecutar_pagar_y_decrementar", new_callable=AsyncMock) as mock_redis, \
             patch("src.chain.validators.decrementar_inventario_evento", new_callable=AsyncMock) as mock_decrementar_evento, \
             patch("src.api.routes.reservas.check_idempotency", new_callable=AsyncMock) as mock_idempotency:

            mock_get_usuario.return_value = {"usuario_id": str(uuid4()), "nombre": "Test"}
            mock_get_evento.return_value = {
                "evento_id": str(uuid4()),
                "estado": "publicado",
                "entradas_disponibles": 1000,
                "precios": [{"categoria": "general", "precio": 50.0, "disponibles": 1000}],
            }
            mock_redis.return_value = {"success": True, "message": "OK"}
            mock_decrementar_evento.return_value = {"disponibles": 999}
            mock_idempotency.return_value = None

            yield mock_redis

    @pytest.mark.performance
    async def test_p99_under_1s_100_concurrent(self, client: AsyncClient, mock_all_services):
        """Test P99 < 1s with 100 concurrent requests."""
        request_data = {
            "usuario_id": str(uuid4()),
            "evento_id": str(uuid4()),
            "cantidad": 1,
            "categoria": "general",
            "metodo_pago": "tarjeta"
        }
        
        async def make_request():
            start = time.perf_counter()
            response = await client.post("/api/reservar", json=request_data)
            end = time.perf_counter()
            return (end - start) * 1000, response.status_code
        
        # 100 concurrent requests
        tasks = [make_request() for _ in range(100)]
        results = await asyncio.gather(*tasks)
        
        latencies = [r[0] for r in results]
        status_codes = [r[1] for r in results]
        
        # All should be valid responses
        assert all(code in [201, 409, 500, 503] for code in status_codes)
        
        latencies.sort()
        p99_index = int(0.99 * len(latencies))
        p99_latency = latencies[p99_index]
        
        print(f"P99 Latency: {p99_latency:.2f}ms")
        assert p99_latency < 1000, f"P99 latency {p99_latency:.2f}ms exceeds 1000ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])