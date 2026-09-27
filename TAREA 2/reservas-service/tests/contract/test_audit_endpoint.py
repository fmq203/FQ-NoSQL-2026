"""Contract tests for GET /api/reservar/{reserva_id}/audit (event_log timeline)."""
import uuid
import pytest
from httpx import AsyncClient

from src.services.postgresql import init_pg_schema, insert_event_log, get_pg_pool


@pytest.mark.contract
class TestAuditEndpoint:
    @pytest.mark.asyncio
    async def test_devuelve_los_eventos_en_orden(self, client: AsyncClient):
        reserva_id = uuid.uuid4()
        await init_pg_schema()
        try:
            await insert_event_log(
                event_type="SAGA_STARTED", aggregate_id=reserva_id,
                payload={"usuario_id": "x", "evento_id": "y"},
            )
            await insert_event_log(
                event_type="SAGA_FAILED", aggregate_id=reserva_id,
                payload={"error": "Inventario insuficiente"},
            )
            await insert_event_log(
                event_type="COMPENSACION_EJECUTADA", aggregate_id=reserva_id,
                payload={"paso_compensado": "PROCESAR_PAGO"},
            )

            response = await client.get(f"/api/reservar/{reserva_id}/audit")

            assert response.status_code == 200
            data = response.json()
            assert data["reserva_id"] == str(reserva_id)
            tipos = [e["event_type"] for e in data["eventos"]]
            assert tipos == ["SAGA_STARTED", "SAGA_FAILED", "COMPENSACION_EJECUTADA"]
        finally:
            pool = await get_pg_pool()
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM event_log WHERE aggregate_id = $1", reserva_id)

    @pytest.mark.asyncio
    async def test_reserva_sin_eventos_devuelve_lista_vacia(self, client: AsyncClient):
        await init_pg_schema()
        response = await client.get(f"/api/reservar/{uuid.uuid4()}/audit")
        assert response.status_code == 200
        assert response.json()["eventos"] == []
