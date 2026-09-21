"""Tests for zero negative inventory prevention."""
import pytest
import asyncio
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from src.main import app


class TestNegativeInventory:
    """Tests to verify zero negative inventory (RP-SC-003)."""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    def mock_services(self):
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
                    "entradas_disponibles": 5,
                    "precios": [{"categoria": "General", "precio": 50.0, "disponibles": 5}],
                }
            )
            
            # Redis - track inventory to ensure no negative
            inventory = {"count": 5}
            
            async def mock_pagar_y_decrementar(**kwargs):
                cantidad = kwargs["cantidad"]
                if inventory["count"] >= cantidad:
                    inventory["count"] -= cantidad
                    return {"success": True, "message": "OK"}
                return {"success": False, "message": "INVENTARIO_INSUFICIENTE"}
            
            mock_redis.side_effect = mock_pagar_y_decrementar
            yield mock_redis

    @pytest.mark.integration
    async def test_zero_negative_inventory_sequential(
        self,
        client: AsyncClient,
        mock_services
    ):
        """Test inventory never goes negative with sequential requests."""
        request_data = {
            "usuario_id": str(uuid4()),
            "evento_id": str(uuid4()),
            "cantidad": 1,
            "metodo_pago": "tarjeta"
        }
        
        # Make 10 requests for 5 available tickets
        results = []
        for i in range(10):
            req = request_data.copy()
            req["usuario_id"] = str(uuid4())
            response = await client.post("/api/v1/reservar", json=req)
            results.append((response.status_code, response.json() if response.status_code == 201 else None))
        
        # Verify no negative inventory - only 5 should succeed
        successful = [r for r in results if r[0] == 201]
        failed = [r for r in results if r[0] != 201]
        
        assert len(successful) == 5, f"Expected 5 successful, got {len(successful)}"
        assert len(failed) == 5, f"Expected 5 failed, got {len(failed)}"
        
        # All failures should be 409 (insufficient inventory)
        for status, _ in failed:
            assert status == 409, f"Expected 409, got {status}"

    @pytest.mark.integration
    async def test_zero_negative_inventory_concurrent(
        self,
        client: AsyncClient,
        mock_services
    ):
        """Test inventory never goes negative under concurrent load."""
        # 50 concurrent requests for 5 tickets
        request_data = {
            "usuario_id": str(uuid4()),
            "evento_id": str(uuid4()),
            "cantidad": 1,
            "metodo_pago": "tarjeta"
        }
        
        async def make_request():
            req = request_data.copy()
            req["usuario_id"] = str(uuid4())
            response = await client.post("/api/v1/reservar", json=req)
            return response.status_code
        
        # 50 concurrent requests, only 5 tickets available
        tasks = [make_request() for _ in range(50)]
        status_codes = await asyncio.gather(*tasks)
        
        # Count successes
        successes = sum(1 for code in status_codes if code == 201)
        failures = sum(1 for code in status_codes if code != 201)
        
        assert successes == 5, f"Expected 5 successful, got {successes}"
        assert failures == 45, f"Expected 45 failed, got {failures}"
        
        # All failures should be 409 (insufficient inventory)
        for code in status_codes:
            if code != 201:
                assert code == 409, f"Expected 409 for failure, got {code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])