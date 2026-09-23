"""SQL Views and partitioning for Event Sourcing CQRS."""
import asyncio
import asyncpg
from src.services.postgresql import get_pg_pool, init_pg_schema
import os


async def create_cqrs_views():
    """Create CQRS analytical views in PostgreSQL."""
    # First initialize the schema (creates event_log table if not exists)
    await init_pg_schema()
    
    pg_uri = os.getenv("POSTGRESQL_URI", "postgresql://eventflow_user:eventflow_password@localhost:5432/eventflow")
    pool = await asyncpg.create_pool(pg_uri, min_size=1, max_size=5)
    
    try:
        async with pool.acquire() as conn:
            # View: ventas_por_evento (Últimos 30 días)
            await conn.execute("""
                CREATE OR REPLACE VIEW ventas_por_evento AS
                SELECT 
                    payload->>'evento_id' as evento_id,
                    COUNT(*) as total_reservas,
                    SUM((payload->>'cantidad')::int) as total_entradas,
                    SUM((payload->>'monto_total')::numeric) as ingreso_total
                FROM event_log
                WHERE event_type = 'RESERVA_CONFIRMADA'
                  AND timestamp > NOW() - INTERVAL '30 days'
                GROUP BY payload->>'evento_id';
            """)
            print("✓ Created view: ventas_por_evento")
            
            # View: tasa_exito_saga (Últimos 7 días - rolling)
            await conn.execute("""
                CREATE OR REPLACE VIEW tasa_exito_saga AS
                SELECT 
                    DATE_TRUNC('day', timestamp) as dia,
                    COUNT(*) FILTER (WHERE event_type = 'SAGA_COMPLETED') as exitosas,
                    COUNT(*) FILTER (WHERE event_type = 'SAGA_FAILED') as fallidas,
                    ROUND(
                        COUNT(*) FILTER (WHERE event_type = 'SAGA_COMPLETED') * 100.0 / 
                        NULLIF(COUNT(*) FILTER (WHERE event_type IN ('SAGA_COMPLETED', 'SAGA_FAILED')), 0), 2
                    ) as tasa_exito_pct
                FROM event_log
                WHERE event_type IN ('SAGA_COMPLETED', 'SAGA_FAILED')
                  AND timestamp > NOW() - INTERVAL '7 days'
                GROUP BY DATE_TRUNC('day', timestamp)
                ORDER BY dia DESC;
            """)
            print("✓ Created view: tasa_exito_saga")
            
            # View: compensaciones_por_tipo (Últimas 24h)
            await conn.execute("""
                CREATE OR REPLACE VIEW compensaciones_por_tipo AS
                SELECT 
                    payload->>'paso_compensado' as paso,
                    COUNT(*) as total_compensaciones
                FROM event_log
                WHERE event_type = 'COMPENSACION_EJECUTADA'
                  AND timestamp > NOW() - INTERVAL '24 hours'
                GROUP BY payload->>'paso_compensado';
            """)
            print("✓ Created view: compensaciones_por_tipo")
            
            # GIN index for analytical queries
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_log_payload_gin 
                ON event_log USING GIN(payload);
            """)
            print("✓ Created GIN index: idx_event_log_payload_gin")
            
    finally:
        await pool.close()


async def setup_monthly_partitioning():
    """Setup monthly partitioning for event_log (optional, for high volume)."""
    pg_uri = os.getenv("POSTGRESQL_URI", "postgresql://eventflow_user:eventflow_password@localhost:5432/eventflow")
    pool = await asyncpg.create_pool(pg_uri, min_size=1, max_size=5)
    
    try:
        async with pool.acquire() as conn:
            # Check if partitioning is needed (event_log > 10M rows/month)
            count = await conn.fetchval("SELECT COUNT(*) FROM event_log WHERE timestamp > NOW() - INTERVAL '30 days'")
            
            if count > 10_000_000:
                print(f"High volume detected ({count} events/month). Setting up partitioning...")
                
                # Create partitioned table structure
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS event_log_partitioned (
                        LIKE event_log INCLUDING ALL
                    ) PARTITION BY RANGE (timestamp);
                """)
                
                # Create monthly partitions for next 12 months
                from datetime import datetime, timedelta
                import calendar
                
                base_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                
                for i in range(12):
                    start = base_date + timedelta(days=30*i)
                    end = base_date + timedelta(days=30*(i+1))
                    
                    partition_name = f"event_log_{start.strftime('%Y_%m')}"
                    
                    await conn.execute(f"""
                        CREATE TABLE IF NOT EXISTS {partition_name} 
                        PARTITION OF event_log_partitioned
                        FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}');
                    """)
                    print(f"✓ Created partition: {partition_name}")
                
                print("✓ Monthly partitioning configured")
            else:
                print(f"Volume OK ({count} events/month). Partitioning not needed.")
    finally:
        await pool.close()


async def main():
    """Main entry point."""
    await create_cqrs_views()
    await setup_monthly_partitioning()


if __name__ == "__main__":
    asyncio.run(main())