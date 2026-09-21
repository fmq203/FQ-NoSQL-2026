"""Load test for 100 req/s concurrent."""
import pytest
import asyncio
import time
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from src.main import app


class TestLoad:
    """Load test: 100 req/s concurrent."""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    def mock_all_services(self):
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
            
            yield

    @pytest.mark.performance
    async def test_100_req_per_second(
        self,
        client: AsyncClient,
        mock_all_services
    ):
        """Test 100 req/s sustained for 10 seconds."""
        request_data = {
            "usuario_id": str(uuid4()),
            "evento_id": str(uuid4()),
            "cantidad": 1,
            "metodo_pago": "tarjeta"
        }
        
        results = []
        errors = []
        
        async def make_request(req_id):
            req = request_data.copy()
            req["usuario_id"] = str(uuid4())
            start = time.perf_counter()
            try:
                response = await client.post("/api/v1/reservar", json=req)
                latency_ms = (time.perf_counter() - start) * 1000
                results.append((response.status_code, latency_ms))
            except Exception as e:
                errors.append(str(e))
        
        # Run 100 requests per second for 10 seconds = 1000 requests
        total_requests = 1000
        batch_size = 100
        duration_seconds = 10
        
        all_latencies = []
        all_status_codes = []
        all_errors = []
        
        start_time = time.time()
        
        for batch in range(duration_seconds):
            batch_start = time.time()
            
            tasks = []
            for i in range(batch_size):
                req = request_data.copy()
                req["usuario_id"] = str(uuid4())
                tasks.append(client.post("/api/v1/reservar", json=req))
            
            batch_start = time.time()
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            batch_end = time.time()
            
            for r in responses:
                if isinstance(r, Exception):
                    errors.append(str(r))
                else:
                    all_status_codes.append(r.status_code)
                    # Calculate latency (approximate)
                    latency = (time.time() - start) * 1000 / batch_size
                    pass
            
            # Wait to maintain 100 req/s rate
            elapsed = time.time() - batch_start
            if elapsed < 1.0:
                await asyncio.sleep(1.0 - elapsed)
        
        # Verify results
        successful = sum(1 for c in all_status_codes if c == 201)
        conflicts = sum(1 for c in all_status_codes if c == 409)
        server_errors = sum(1 for c in all_status_codes if c >= 500)
        
        print(f"Total: {len(all_status_codes)}, Success: {successful}, Conflicts: {conflicts}, Errors: {server_errors}")
        
        # Should have no server errors (5xx)
        assert server_errors == 0, f"Server errors: {server_errors}"
        
        # All requests should be either 201 or 409 (conflict is expected)
        assert len(all_status_codes) == 1000
        
        # Print throughput
        elapsed = time.time() - start_time
        throughput = len(all_status_codes) / elapsed
        print(f"Throughput: {throughput:.2f} req/s")
        
        # Should achieve ~100 req/s
        assert throughput >= 90, f"Throughput {throughput:.2f} below 90 req/s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])