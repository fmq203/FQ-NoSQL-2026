"""Tests for double booking prevention."""
import pytest
import asyncio
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from src.main import app


class TestDoubleBooking:
    """Tests to verify zero double bookings (RP-SC-002)."""

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
                    "entradas_disponibles": 10,
                    "precios": [{"categoria": "General", "precio": 50.0, "disponibles": 10}],
                }
            )
            
            # Redis - will track inventory
            inventory = {"count": 10}
            
            async def mock_pagar_y_decrementar(**kwargs):
                evento_id = kwargs["evento_id"]
                cantidad = kwargs["cantidad"]
                if inventory["count"] >= cantidad:
                    inventory["count"] -= cantidad
                    return {"success": True, "message": "OK"}
                return {"success": False, "message": "INVENTARIO_INSUFICIENTE"}
            
            mock_redis.side_effect = mock_pagar_y_decrementar
            yield mock_redis

    @pytest.mark.integration
    async def test_zero_double_bookings_concurrent_requests(
        self,
        client: AsyncClient,
        mock_services
    ):
        """Test zero double bookings with concurrent requests for same inventory."""
        usuario_id = str(uuid4())
        evento_id = str(uuid4())
        
        # 20 concurrent requests for 1 ticket each, only 10 available
        request_data = {
            "usuario_id": str(uuid4()),  # Different users
            "evento_id": evento_id,
            "cantidad": 1,
            "metodo_pago": "tarjeta"
        }
        
        async def make_request(user_id):
            req = request_data.copy()
            req["usuario_id"] = str(user_id)
            response = await client.post("/api/v1/reservar", json=req)
            return response.status_code, response.json() if response.status_code == 201 else None
        
        # 20 concurrent requests for 10 available tickets
        tasks = [make_request(uuid4()) for _ in range(20)]
        results = await asyncio.gather(*tasks)
        
        # Count successful reservations
        successful = [r for r in results if r[0] == 201]
        failed = [r for r in results if r[0] != 201]
        
        print(f"Successful: {len(successful)}, Failed: {len(failed)}")
        
        # Should have exactly 10 successful (inventory limit)
        assert len(successful) == 10, f"Expected 10 successful, got {len(successful)}"
        assert len(failed) == 10, f"Expected 10 failed, got {len(failed)}"
        
        # All failures should be 409 (insufficient inventory) or 503
        for status, _ in failed:
            assert status in [409, 503], f"Unexpected failure status: {status}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])