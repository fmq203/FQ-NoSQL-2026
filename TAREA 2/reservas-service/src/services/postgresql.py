import asyncpg
from src.config import get_settings
import logging

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

    logger.info("✅ PostgreSQL schema inicializado")


async def close_pg_pool() -> None:
    global _pg_pool
    if _pg_pool:
        await _pg_pool.close()
        logger.info("🔌 PostgreSQL pool cerrado")


async def get_pg_pool():
    if _pg_pool is None:
        raise RuntimeError("PostgreSQL no inicializado")
    return _pg_pool