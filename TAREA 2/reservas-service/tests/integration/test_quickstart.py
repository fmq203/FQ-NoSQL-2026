"""Quickstart validation test (T065)."""
import pytest
import asyncio
import subprocess
import time
import requests
import os
from httpx import AsyncClient
from uuid import uuid4
from src.main import app


class TestQuickstartValidation:
    """Quickstart validation test (T065)."""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.integration
    async def test_quickstart_endpoints_work(self):
        """Test that quickstart commands work end-to-end."""
        with patch("src.services.http_clients.get_usuarios_client") as mock_usuarios, \
             patch("src.services.http_clients.get_eventos_client") as mock_eventos, \
             patch("src.services.redis_pago.ejecutar_pagar_y_decrementar") as mock_redis, \
             patch("src.services.mongo.get_reservas_collection") as mock_mongo, \
             patch("src.services.postgresql.insert_event_log") as mock_pg:
            
            # Setup mocks
            mock_usuarios.return_value.get.return_value = AsyncMock(
                status_code=200,
                json=lambda: {"usuario_id": str(uuid4()), "nombre": "Test"}
            )
            
            mock_eventos.return_value.get.return_value = AsyncMock(
                status_code=200,
                json=lambda: {
                    "evento_id": str(uuid4()),
                    "estado": "publicado",
                    "entradas_disponibles": 10,
                    "precios": [{"categoria": "General", "precio": 50.0, "disponibles": 10}],
                }
            )
            
            mock_redis.return_value = {"success": True, "message": "OK"}
            mock_pg.return_value = None
            mock_mongo.return_value.insert_one = AsyncMock()
            mock_mongo.return_value.find_one = AsyncMock(return_value=None)
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                # 1. Health check
                response = await client.get("/health")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] in ["healthy", "degraded"]
                assert "checks" in data
                
                # 2. Create reservation (SAGA happy path)
                response = await client.post("/api/v1/reservar", json={
                    "usuario_id": str(uuid4()),
                    "evento_id": str(uuid4()),
                    "cantidad": 2,
                    "metodo_pago": "tarjeta"
                })
                assert response.status_code == 201
                data = response.json()
                assert data["estado"] == "confirmada"
                assert "numero_confirmacion" in data
                
                reserva_id = data["reserva_id"]
                
                # 3. Get reservation
                response = await client.get(f"/api/v1/reservar/{reserva_id}")
                assert response.status_code == 200
                assert response.json()["reserva_id"] == reserva_id
                
                # 4. List reservations
                response = await client.get("/api/v1/reservar")
                assert response.status_code == 200
                assert isinstance(response.json(), list)
                
                # 5. Metrics endpoint
                response = await client.get("/metrics")
                assert response.status_code == 200
                assert "text/plain" in response.headers.get("content-type", "")
                assert "saga_duration_seconds" in response.text

    @pytest.mark.integration
    @pytest.mark.skipif(
        not os.environ.get("DOCKER_COMPOSE_AVAILABLE"),
        reason="Docker Compose not available"
    )
    def test_docker_compose_up(self):
        """Test docker compose up works (requires docker-compose)."""
        project_root = os.path.join(os.path.dirname(__file__), "..", "..")
        compose_file = os.path.join(project_root, "docker-compose.yml")
        
        if not os.path.exists(compose_file):
            pytest.skip("docker-compose.yml not found")
        
        # Start docker-compose
        import subprocess
        proc = subprocess.Popen(
            ["docker-compose", "up", "-d"],
            cwd=os.path.dirname(compose_file),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        try:
            # Wait for services to be healthy
            time.sleep(30)
            
            # Test health endpoints
            for port, service in [(8001, "usuarios"), (8002, "eventos"), (8003, "reservas")]:
                try:
                    response = requests.get(f"http://localhost:{port}/health", timeout=5)
                    assert response.status_code == 200, f"{service} health check failed"
                    data = response.json()
                    assert data["status"] in ["healthy", "degraded"]
                except Exception as e:
                    pytest.fail(f"{service} health check failed: {e}")
        finally:
            # Cleanup
            subprocess.run(["docker-compose", "down"], 
                         cwd=os.path.dirname(__file__), capture_output=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])