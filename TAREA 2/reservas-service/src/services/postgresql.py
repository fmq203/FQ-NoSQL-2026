import json
import logging
from typing import Any, Optional
from uuid import UUID

import asyncpg

from src.config import get_settings

logger = logging.getLogger(__name__)

_pg_pool = None


async def init_pg_schema() -> None:
    global _pg_pool
    settings = get_settings()

    _pg_pool = await asyncpg.create_pool(
        settings.postgresql_uri,
        min_size=2,
        max_size=10,
    )

    async with _pg_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pagos (
                pago_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                reserva_id UUID NOT NULL,
                usuario_id UUID NOT NULL,
                evento_id UUID NOT NULL,
                monto DECIMAL(10,2) NOT NULL,
                estado VARCHAR(50) NOT NULL DEFAULT 'pendiente',
                proveedor_pago VARCHAR(100),
                referencia_externa VARCHAR(200),
                creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pagos_reserva_id ON pagos(reserva_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pagos_usuario_id ON pagos(usuario_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pagos_estado ON pagos(estado)
        """)

        # Event Log: registro append-only de cada paso de la SAGA
        # (Event Sourcing). Ver brain/patterns/event-log-pattern.md.
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS event_log (
                id BIGSERIAL PRIMARY KEY,
                event_type VARCHAR(50) NOT NULL,
                aggregate_id UUID NOT NULL,
                aggregate_type VARCHAR(50) NOT NULL DEFAULT 'Reserva',
                payload JSONB NOT NULL,
                correlation_id UUID,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_log_aggregate ON event_log(aggregate_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_log_type ON event_log(event_type)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_log_timestamp ON event_log(timestamp DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_log_correlation ON event_log(correlation_id)
        """)

    logger.info("✅ PostgreSQL schema inicializado (pagos + event_log)")


async def close_pg_pool() -> None:
    global _pg_pool
    if _pg_pool:
        await _pg_pool.close()
        logger.info("🔌 PostgreSQL pool cerrado")


async def get_pg_pool():
    if _pg_pool is None:
        raise RuntimeError("PostgreSQL no inicializado")
    return _pg_pool


def _event_type_value(event_type: Any) -> str:
    """Acepta tanto un EventType (Enum) como un str plano."""
    return event_type.value if hasattr(event_type, "value") else str(event_type)


async def insert_event_log(
    event_type: Any,
    aggregate_id: UUID,
    payload: dict,
    correlation_id: Optional[UUID] = None,
    aggregate_type: str = "Reserva",
) -> None:
    """Registrar un evento inmutable en el event log (SAGA_STARTED,
    USUARIO_VALIDADO, PAGO_PROCESADO, SAGA_FAILED, COMPENSACION_EJECUTADA, ...).

    Un fallo al escribir en el event log NUNCA debe abortar la SAGA: la
    auditoría es un side-effect, no una precondición del negocio. Por eso
    esta función atrapa sus propios errores y solo deja un warning.
    """
    try:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO event_log
                    (event_type, aggregate_id, aggregate_type, payload, correlation_id)
                VALUES ($1, $2, $3, $4::jsonb, $5)
                """,
                _event_type_value(event_type),
                aggregate_id,
                aggregate_type,
                json.dumps(payload, default=str),
                correlation_id,
            )
    except Exception as e:
        logger.warning(f"No se pudo registrar evento {event_type} en event_log: {e}")


async def get_events_by_aggregate(aggregate_id: UUID) -> list[dict]:
    """Recuperar la timeline completa de eventos de una reserva (debugging/auditoría)."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT event_type, payload, correlation_id, timestamp
            FROM event_log
            WHERE aggregate_id = $1
            ORDER BY timestamp ASC, id ASC
            """,
            aggregate_id,
        )
    return [
        {
            "event_type": row["event_type"],
            "payload": json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"],
            "correlation_id": str(row["correlation_id"]) if row["correlation_id"] else None,
            "timestamp": row["timestamp"].isoformat(),
        }
        for row in rows
    ]


async def get_saga_success_rate(hours: int = 24) -> dict:
    """Tasa de éxito de la SAGA en las últimas N horas, para /metrics y debugging."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE event_type = 'SAGA_COMPLETED') AS exitosas,
                COUNT(*) FILTER (WHERE event_type = 'SAGA_FAILED') AS fallidas
            FROM event_log
            WHERE event_type IN ('SAGA_COMPLETED', 'SAGA_FAILED')
              AND timestamp > NOW() - ($1 || ' hours')::interval
            """,
            str(hours),
        )
    exitosas = row["exitosas"] or 0
    fallidas = row["fallidas"] or 0
    total = exitosas + fallidas
    return {
        "exitosas": exitosas,
        "fallidas": fallidas,
        "total": total,
        "tasa_exito_pct": round(exitosas * 100.0 / total, 2) if total else None,
    }