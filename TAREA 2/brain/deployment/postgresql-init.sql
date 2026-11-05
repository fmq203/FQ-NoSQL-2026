-- PostgreSQL schema de EventFlow (event_log + vistas CQRS)
--
-- Copia de referencia de lo que ejecuta init_pg_schema() en
-- reservas-service/src/services/postgresql.py al iniciar el servicio.
-- La fuente de verdad es ese código: docker-compose.yml NO monta este
-- archivo, y no hace falta correrlo a mano. Es idempotente
-- (IF NOT EXISTS / OR REPLACE), así que correrlo sobre la base existente
-- no rompe nada.
--
-- Revisado 2026-11-05. La versión anterior de este archivo tenía un
-- esquema de la etapa de diseño (columnas tipo, datos, usuario_id,
-- ip_address, hash_anterior) que nunca se implementó.

-- ============ EVENT LOG (append-only) ============

CREATE TABLE IF NOT EXISTS event_log (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    aggregate_id UUID NOT NULL,                       -- reserva_id
    aggregate_type VARCHAR(50) NOT NULL DEFAULT 'Reserva',
    payload JSONB NOT NULL,
    correlation_id UUID,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_log_aggregate   ON event_log(aggregate_id);
CREATE INDEX IF NOT EXISTS idx_event_log_type        ON event_log(event_type);
CREATE INDEX IF NOT EXISTS idx_event_log_timestamp   ON event_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_correlation ON event_log(correlation_id);
CREATE INDEX IF NOT EXISTS idx_event_log_payload_gin ON event_log USING GIN(payload);

-- ============ VISTAS CQRS (solo lectura) ============

CREATE OR REPLACE VIEW ventas_por_evento AS
SELECT
    payload->>'evento_id' AS evento_id,
    COUNT(*) AS total_reservas,
    SUM((payload->>'cantidad')::int) AS total_entradas,
    SUM((payload->>'monto_total')::numeric) AS ingreso_total
FROM event_log
WHERE event_type = 'RESERVA_CONFIRMADA'
  AND timestamp > NOW() - INTERVAL '30 days'
GROUP BY payload->>'evento_id';

CREATE OR REPLACE VIEW tasa_exito_saga AS
SELECT
    DATE_TRUNC('day', timestamp) AS dia,
    COUNT(*) FILTER (WHERE event_type = 'SAGA_COMPLETED') AS exitosas,
    COUNT(*) FILTER (WHERE event_type = 'SAGA_FAILED') AS fallidas,
    ROUND(
        COUNT(*) FILTER (WHERE event_type = 'SAGA_COMPLETED') * 100.0 /
        NULLIF(COUNT(*) FILTER (WHERE event_type IN ('SAGA_COMPLETED', 'SAGA_FAILED')), 0), 2
    ) AS tasa_exito_pct
FROM event_log
WHERE event_type IN ('SAGA_COMPLETED', 'SAGA_FAILED')
  AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY DATE_TRUNC('day', timestamp)
ORDER BY dia DESC;

CREATE OR REPLACE VIEW compensaciones_por_tipo AS
SELECT
    payload->>'paso_compensado' AS paso,
    COUNT(*) AS total_compensaciones
FROM event_log
WHERE event_type = 'COMPENSACION_EJECUTADA'
  AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY payload->>'paso_compensado';
