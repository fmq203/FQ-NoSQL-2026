import pytest
import asyncio
import time
from httpx import AsyncClient
from statistics import mean, quantiles


@pytest.mark.performance
class TestPerformance:
    """Performance tests básicos."""

    @pytest.mark.asyncio
    async def test_create_usuario_latency(self, client: AsyncClient, usuario_valido):
        """Test latencia de creación de usuario < 100ms p95."""
        latencies = []

        for i in range(20):
            # Usar email único para cada iteración
            usuario = usuario_valido.copy()
            usuario["email"] = f"perf_test_{i}@example.com"
            usuario["nro_documento"] = f"{10000000 + i}"

            start = time.perf_counter()
            response = await client.post("/api/usuarios", json=usuario)
            latency_ms = (time.perf_counter() - start) * 1000

            assert response.status_code == 201
            latencies.append(latency_ms)

        p95 = quantiles(latencies, n=100)[94] if len(latencies) >= 20 else max(latencies)
        avg = mean(latencies)

        print(f"Create Usuario - Avg: {avg:.2f}ms, P95: {p95:.2f}ms")
        assert p95 < 100, f"P95 latency {p95:.2f}ms exceeds 100ms threshold"

    @pytest.mark.asyncio
    async def test_get_usuario_latency(self, client: AsyncClient, usuario_valido):
        """Test latencia de obtención de usuario < 50ms p95."""
        # Crear usuario primero
        create_response = await client.post("/api/usuarios", json=usuario_valido)
        usuario_id = create_response.json()["usuario_id"]

        latencies = []

        for _ in range(20):
            start = time.perf_counter()
            response = await client.get(f"/api/usuarios/{usuario_id}")
            latency_ms = (time.perf_counter() - start) * 1000

            assert response.status_code == 200
            latencies.append(latency_ms)

        p95 = quantiles(latencies, n=100)[94] if len(latencies) >= 20 else max(latencies)
        avg = mean(latencies)

        print(f"Get Usuario - Avg: {avg:.2f}ms, P95: {p95:.2f}ms")
        assert p95 < 50, f"P95 latency {p95:.2f}ms exceeds 50ms threshold"

    @pytest.mark.asyncio
    async def test_health_check_latency(self, client: AsyncClient):
        """Test latencia health check < 50ms p99."""
        latencies = []

        for _ in range(50):
            start = time.perf_counter()
            response = await client.get("/health")
            latency_ms = (time.perf_counter() - start) * 1000

            assert response.status_code in [200, 503]
            latencies.append(latency_ms)

        p99 = quantiles(latencies, n=100)[98] if len(latencies) >= 50 else max(latencies)
        avg = mean(latencies)

        print(f"Health Check - Avg: {avg:.2f}ms, P99: {p99:.2f}ms")
        assert p99 < 50, f"P99 latency {p99:.2f}ms exceeds 50ms threshold"