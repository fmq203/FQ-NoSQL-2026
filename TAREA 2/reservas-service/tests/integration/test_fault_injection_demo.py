"""Tests for the ?simular_fallo=sync_pago demo fault-injection hook.

Este query param existe solo para poder mostrar, de forma determinista,
la compensacion real de ProcesadorPago (revierte el pago/inventario en
Redis) sin depender de una caida real de eventos-service con timing
imposible de reproducir a mano en una demo en vivo. El codigo de
compensacion que corre es exactamente el mismo que ante un fallo real -
ver ReservaContext.simular_fallo_sync.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from src.main import app


class TestFaultInjectionDemo:
    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    def mocks(self):
        with patch("src.chain.validators.get_usuario", new_callable=AsyncMock) as mock_get_usuario, \
             patch("src.chain.validators.get_evento", new_callable=AsyncMock) as mock_get_evento, \
             patch("src.chain.validators.ejecutar_pagar_y_decrementar", new_callable=AsyncMock) as mock_redis, \
             patch("src.chain.validators.decrementar_inventario_evento", new_callable=AsyncMock) as mock_decrementar_evento, \
             patch("src.chain.validators.ejecutar_compensar_pago_inventario", new_callable=AsyncMock) as mock_compensation, \
             patch("src.chain.validators.insert_event_log", new_callable=AsyncMock) as mock_pg, \
             patch("src.services.saga_orchestrator.insert_event_log", mock_pg), \
             patch("src.api.routes.reservas.check_idempotency", new_callable=AsyncMock) as mock_idempotency:

            mock_get_usuario.return_value = {"usuario_id": str(uuid4()), "nombre": "Test"}
            mock_get_evento.return_value = {
                "evento_id": str(uuid4()),
                "estado": "publicado",
                "entradas_disponibles": 100,
                "precios": [{"categoria": "general", "precio": 50.0, "disponibles": 100}],
            }
            mock_redis.return_value = {"success": True, "message": "OK"}
            mock_compensation.return_value = {"success": True, "message": "COMPENSACION_OK"}
            mock_idempotency.return_value = None

            yield {"decrementar_evento": mock_decrementar_evento, "compensation": mock_compensation, "pg": mock_pg}

    @pytest.mark.asyncio
    async def test_simular_fallo_dispara_compensacion_real(self, client: AsyncClient, mocks):
        response = await client.post(
            "/api/reservar?simular_fallo=sync_pago",
            json={
                "usuario_id": str(uuid4()),
                "evento_id": str(uuid4()),
                "cantidad": 2,
                "categoria": "general",
                "metodo_pago": "tarjeta",
            },
        )

        assert response.status_code == 503
        data = response.json()
        assert data["type"] == "https://eventflow.example.com/errors/SERVICE_UNAVAILABLE"

        # El pago en Redis SI se ejecuto (mock_redis.success=True), pero
        # nunca deberia haber llegado a sincronizar con eventos-service...
        mocks["decrementar_evento"].assert_not_called()
        # ...y la compensacion real (revertir Redis) SI se disparo.
        mocks["compensation"].assert_called_once()

        # El audit trail (event_log) debe reflejar la compensacion, para
        # que la vista CQRS compensaciones_por_tipo la vea.
        event_types = [
            call.kwargs.get("event_type") or call.args[0]
            for call in mocks["pg"].call_args_list
        ]
        assert "COMPENSACION_EJECUTADA" in event_types
        assert "SAGA_FAILED" in event_types

    @pytest.mark.asyncio
    async def test_sin_el_query_param_no_afecta_el_flujo_normal(self, client: AsyncClient, mocks):
        mocks["decrementar_evento"].return_value = {"disponibles": 99}
        response = await client.post(
            "/api/reservar",
            json={
                "usuario_id": str(uuid4()),
                "evento_id": str(uuid4()),
                "cantidad": 2,
                "categoria": "general",
                "metodo_pago": "tarjeta",
            },
        )
        # Sin el query param, decrementar_inventario_evento se llama normal.
        mocks["decrementar_evento"].assert_called_once()
        mocks["compensation"].assert_not_called()
