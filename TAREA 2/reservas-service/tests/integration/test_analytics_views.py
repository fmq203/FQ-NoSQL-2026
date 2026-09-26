"""Integration tests for the CQRS analytical SQL views (E3).

A diferencia del resto de la suite (ver conftest.py._reset_db_singletons
y tests/integration/test_saga_happy_path.py), estos tests llaman
init_pg_schema() directamente en vez de depender del lifespan de FastAPI
(que AsyncClient(app=app, ...) nunca dispara) - las vistas viven en
PostgreSQL, no en la app, asi que probarlas no necesita levantar la app.
"""
import uuid
import pytest

from src.services.postgresql import init_pg_schema, close_pg_pool, get_pg_pool


@pytest.fixture
async def pg_conn():
    await init_pg_schema()
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        yield conn
    await close_pg_pool()


@pytest.mark.integration
class TestVentasPorEvento:
    async def test_agrega_reservas_confirmadas_por_evento(self, pg_conn):
        evento_id = str(uuid.uuid4())
        aggregate_id = str(uuid.uuid4())
        await pg_conn.execute(
            """INSERT INTO event_log (event_type, aggregate_id, payload)
               VALUES ('RESERVA_CONFIRMADA', $1, $2::jsonb)""",
            aggregate_id,
            f'{{"evento_id": "{evento_id}", "cantidad": 3, "monto_total": 150.0}}',
        )
        try:
            rows = await pg_conn.fetch(
                "SELECT * FROM ventas_por_evento WHERE evento_id = $1", evento_id
            )
            assert len(rows) == 1
            assert rows[0]["total_reservas"] == 1
            assert rows[0]["total_entradas"] == 3
            assert float(rows[0]["ingreso_total"]) == 150.0
        finally:
            await pg_conn.execute(
                "DELETE FROM event_log WHERE aggregate_id = $1", aggregate_id
            )

    async def test_no_incluye_eventos_de_otro_tipo(self, pg_conn):
        evento_id = str(uuid.uuid4())
        aggregate_id = str(uuid.uuid4())
        await pg_conn.execute(
            """INSERT INTO event_log (event_type, aggregate_id, payload)
               VALUES ('SAGA_STARTED', $1, $2::jsonb)""",
            aggregate_id,
            f'{{"evento_id": "{evento_id}"}}',
        )
        try:
            rows = await pg_conn.fetch(
                "SELECT * FROM ventas_por_evento WHERE evento_id = $1", evento_id
            )
            assert len(rows) == 0
        finally:
            await pg_conn.execute(
                "DELETE FROM event_log WHERE aggregate_id = $1", aggregate_id
            )


@pytest.mark.integration
class TestTasaExitoSaga:
    async def test_calcula_porcentaje_de_exito(self, pg_conn):
        marker = str(uuid.uuid4())
        completadas_id = str(uuid.uuid4())
        falladas_id = str(uuid.uuid4())
        await pg_conn.execute(
            """INSERT INTO event_log (event_type, aggregate_id, payload)
               VALUES ('SAGA_COMPLETED', $1, $2::jsonb)""",
            completadas_id,
            f'{{"marker": "{marker}"}}',
        )
        await pg_conn.execute(
            """INSERT INTO event_log (event_type, aggregate_id, payload)
               VALUES ('SAGA_FAILED', $1, $2::jsonb)""",
            falladas_id,
            f'{{"marker": "{marker}"}}',
        )
        try:
            rows = await pg_conn.fetch("SELECT * FROM tasa_exito_saga")
            total_exitosas = sum(r["exitosas"] for r in rows)
            total_fallidas = sum(r["fallidas"] for r in rows)
            assert total_exitosas >= 1
            assert total_fallidas >= 1
        finally:
            await pg_conn.execute(
                "DELETE FROM event_log WHERE aggregate_id IN ($1, $2)",
                completadas_id,
                falladas_id,
            )


@pytest.mark.integration
class TestCompensacionesPorTipo:
    async def test_agrupa_por_paso_compensado(self, pg_conn):
        aggregate_id = str(uuid.uuid4())
        await pg_conn.execute(
            """INSERT INTO event_log (event_type, aggregate_id, payload)
               VALUES ('COMPENSACION_EJECUTADA', $1, $2::jsonb)""",
            aggregate_id,
            '{"paso_compensado": "PAGO_PROCESADO", "accion": "INCRBY+DEL"}',
        )
        try:
            rows = await pg_conn.fetch(
                "SELECT * FROM compensaciones_por_tipo WHERE paso = 'PAGO_PROCESADO'"
            )
            assert len(rows) == 1
            assert rows[0]["total_compensaciones"] >= 1
        finally:
            await pg_conn.execute(
                "DELETE FROM event_log WHERE aggregate_id = $1", aggregate_id
            )


@pytest.mark.integration
class TestIndiceGIN:
    async def test_gin_index_existe_en_event_log_payload(self, pg_conn):
        rows = await pg_conn.fetch(
            "SELECT indexdef FROM pg_indexes WHERE tablename = 'event_log' "
            "AND indexname = 'idx_event_log_payload_gin'"
        )
        assert len(rows) == 1
        assert "gin" in rows[0]["indexdef"].lower()
