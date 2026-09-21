"""Performance tests for SAGA execution."""
import pytest
import asyncio
import time
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from src.main import app


class TestSAGAPerformance:
    """Performance tests for SAGA execution."""

    @pytest.fixture
    async def client(self):
        """Create test client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    def mock_services(self):
        """Mock all external services for performance testing."""
        with patch("src.services.http_clients.get_usuarios_client") as mock_usuarios, \
             patch("src.services.http_clients.get_eventos_client") as mock_eventos, \
             patch("src.services.redis_pago.ejecutar_pagar_y_decrementar") as mock_redis:
            
            # Setup usuarios client
            usuarios_client = AsyncMock()
            mock_usuarios.return_value = usuarios_client
            usuarios_client.get.return_value = AsyncMock(
                status_code=200,
                json=lambda: {"usuario_id": str(uuid4()), "nombre": "Test"}
            )
            
            # Setup eventos client
            eventos_client = AsyncMock()
            mock_eventos.return_value = eventos_client
            eventos_client.get.return_value = AsyncMock(
                status_code=200,
                json=lambda: {
                    "evento_id": str(uuid4()),
                    "estado": "publicado",
                    "entradas_disponibles": 100,
                    "precios": [{"categoria": "General", "precio": 50.0, "disponibles": 100}],
                    "ubicacion": {"ciudad": "Madrid", "pais": "España"}
                }
            )
            
            # Setup Redis
            mock_redis.return_value = {"success": True, "message": "OK"}
            
            yield mock_redis

    @pytest.mark.performance
    async def test_saga_performance_p95_under_500ms(
        self,
        client: AsyncClient,
        mock_services
    ):
        """Test SAGA completes in under 500ms (p95)."""
        request_data = {
            "usuario_id": str(uuid4()),
            "evento_id": str(uuid4()),
            "cantidad": 1,
            "metodo_pago": "tarjeta"
        }
        
        latencies = []
        
        # Run 100 requests to calculate p95
        for _ in range(100):
            start = time.perf_counter()
            response = await client.post("/api/v1/reservar", json=request_data)
            end = time.perf_counter()
            
            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)
            
            assert response.status_code in [201, 409, 500]  # Valid responses
        
        # Calculate p95
        latencies.sort()
        p95_index = int(0.95 * len(latencies))
        p95_latency = latencies[p95_index]
        
        print(f"SAGA Performance - p50: {latencies[len(latencies)//2]:.2f}ms, "
              f"p95: {p95_latency:.2f}ms, p99: {latencies[int(0.99*len(latencies))]:.2f}ms")
        
        assert p95_latency < 500, f"p95 latency {p95_latency:.2f}ms exceeds 500ms threshold"

    @pytest.mark.performance
    async def test_saga_p99_under_1s_under_load(
        self,
        client: AsyncClient,
        mock_services
    ):
        """Test SAGA P99 < 1s under concurrent load (100 req/s)."""
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
        
        # Simulate 100 concurrent requests
        tasks = [make_request() for _ in range(100)]
        results = await asyncio.gather(*tasks)
        
        latencies = [r[0] for r in results]
        status_codes = [r[1] for r in results]
        
        # All should succeed or fail gracefully
        assert all(code in [201, 409, 500] for code in status_codes)
        
        latencies.sort()
        p99_index = int(0.99 * len(latencies))
        p99_latency = latencies[p99_index]
        
        print(f"Load Test - p99 latency: {p99_latency:.2f}ms")
        assert p99_latency < 1000, f"p99 latency {p99_latency:.2f}ms exceeds 1s threshold"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])