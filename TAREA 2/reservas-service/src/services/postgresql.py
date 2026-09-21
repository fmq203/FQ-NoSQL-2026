"""PostgreSQL connection and event_log operations for Reservas Service."""
import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
import asyncpg
from asyncpg import Pool, Connection

# Global connection pool
_pg_pool: Optional[Pool] = None


async def get_pg_pool() -> Pool:
    """Get or create PostgreSQL async connection pool."""
    global _pg_pool
    if _pg_pool is None:
        pg_uri = os.getenv("POSTGRESQL_URI", "postgresql://eventflow_user:eventflow_password@localhost:5432/eventflow")
        _pg_pool = await asyncpg.create_pool(
            pg_uri,
            min_size=5,
            max_size=20,
            command_timeout=30,
        )
    return _pg_pool


async def init_pg_schema() -> None:
    """Create event_log table and indexes if not exists."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        # Create table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS event_log (
                id BIGSERIAL PRIMARY KEY,
                event_type VARCHAR(50) NOT NULL,
                aggregate_id UUID NOT NULL,
                aggregate_type VARCHAR(50) NOT NULL DEFAULT 'Reserva',
                payload JSONB NOT NULL,
                metadata JSONB,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                correlation_id UUID
            );
        """)
        
        # Create indexes
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_log_aggregate 
            ON event_log(aggregate_id);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_log_type 
            ON event_log(event_type);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_log_timestamp 
            ON event_log(timestamp DESC);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_log_correlation 
            ON event_log(correlation_id);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_log_payload_gin 
            ON event_log USING GIN(payload);
        """)


async def insert_event_log(
    event_type: str,
    aggregate_id: UUID,
    payload: Dict[str, Any],
    correlation_id: UUID,
    metadata: Optional[Dict[str, Any]] = None,
    aggregate_type: str = "Reserva"
) -> None:
    """Insert event into event_log (Event Sourcing)."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO event_log (event_type, aggregate_id, aggregate_type, payload, metadata, correlation_id)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, event_type, aggregate_id, aggregate_type, 
            json.dumps(payload), json.dumps(metadata) if metadata else None, correlation_id)


async def get_events_by_aggregate(aggregate_id: UUID) -> List[Dict[str, Any]]:
    """Get all events for a specific aggregate_id ordered by timestamp."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT event_type, aggregate_id, payload, metadata, timestamp, correlation_id
            FROM event_log
            WHERE aggregate_id = $1
            ORDER BY timestamp ASC
        """, aggregate_id)
        return [dict(row) for row in rows]


async def get_events_by_type(event_type: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get events by type."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT event_type, aggregate_id, payload, metadata, timestamp, correlation_id
            FROM event_log
            WHERE event_type = $1
            ORDER BY timestamp DESC
            LIMIT $2
        """, event_type, limit)
        return [dict(row) for row in rows]


async def get_saga_success_rate(days: int = 7) -> float:
    """Calculate SAGA success rate over last N days."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT 
                COUNT(*) FILTER (WHERE event_type = 'SAGA_COMPLETED') as exitosas,
                COUNT(*) FILTER (WHERE event_type = 'SAGA_FAILED') as fallidas
            FROM event_log
            WHERE event_type IN ('SAGA_COMPLETED', 'SAGA_FAILED')
              AND timestamp > NOW() - INTERVAL '$1 days'
        """, days)
        if row:
            total = row['exitosas'] + row['fallidas']
            if total > 0:
                return round(row['exitosas'] * 100.0 / total, 2)
    return 0.0


async def get_ventas_por_evento(days: int = 30) -> List[Dict[str, Any]]:
    """Get ventas por evento (CQRS read model)."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                payload->>'evento_id' as evento_id,
                COUNT(*) as total_reservas,
                SUM((payload->>'cantidad')::int) as total_entradas,
                SUM((payload->>'monto_total')::numeric) as ingreso_total
            FROM event_log
            WHERE event_type = 'RESERVA_CONFIRMADA'
              AND timestamp > NOW() - INTERVAL '$1 days'
            GROUP BY payload->>'evento_id'
        """, days)
        return [dict(row) for row in rows]


async def get_compensaciones_por_tipo(hours: int = 24) -> List[Dict[str, Any]]:
    """Get compensaciones por tipo."""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                payload->>'paso_compensado' as paso,
                COUNT(*) as total_compensaciones
            FROM event_log
            WHERE event_type = 'COMPENSACION_EJECUTADA'
              AND timestamp > NOW() - INTERVAL '$1 hours'
            GROUP BY payload->>'paso_compensado'
        """, hours)
        return [dict(row) for row in rows]


async def close_pg_pool() -> None:
    """Close PostgreSQL connection pool."""
    global _pg_pool
    if _pg_pool:
        await _pg_pool.close()
        _pg_pool = None