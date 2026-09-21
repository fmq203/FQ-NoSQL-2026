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
        """Mock all external services."""
        with patch("src.services.http_clients.get_usuarios_client") as mock_usuarios, \
             patch("src.services.http_clients.get_eventos_client") as mock_eventos, \
             patch("src.services.redis_pago.ejecutar_pagar_y_decrementar") as mock_redis:
            
            # Usuarios
            usuarios_client = AsyncMock()
            mock_usuarios.return_value = usuarios_client
            usuarios_client.get.return_value = AsyncMock(
                status_code=200,
                json=lambda: {"usuario_id": str(uuid4()), "nombre": "Test"}
            )
            
            # Eventos
            eventos_client = AsyncMock()
            mock_eventos.return_value = eventos_client
            eventos_client.get.return_value = AsyncMock(
                status_code=200,
                json=lambda: {
                    "evento_id": str(uuid4()),
                    "estado": "publicado",
                    "entradas_disponibles": 1000,
                    "precios": [{"categoria": "General", "precio": 50.0, "disponibles": 1000}],
                }
            )
            
            # Redis
            mock_redis.return_value = {"success": True, "message": "OK"}
            
            yield mock_redis

    @pytest.mark.performance
    async def test_p99_under_1s_100_concurrent(self, client: AsyncClient, mock_all_services):
        """Test P99 < 1s with 100 concurrent requests."""
        request_data = {
            "usuario_id": str(uuid4()),
            "evento_id": str(uuid4()),
            "cantidad": 1,
            "metodo_pago": "tarjeta"
        }
        
        async def make_request():
            start = time.perf_counter()
            response = await client.post("/api/v1/reservar", json=request_data)
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