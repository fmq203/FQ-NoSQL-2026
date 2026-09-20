-- PostgreSQL Initialization Script for EventFlow
-- Crea las tablas y estructuras iniciales

-- ============ CREAR TABLA EVENT LOG ============

CREATE TABLE IF NOT EXISTS event_log (
  -- Primary Key
  id BIGSERIAL PRIMARY KEY,

  -- Event Identification
  evento_id UUID NOT NULL,
  tipo VARCHAR(100) NOT NULL,

  -- Actor & Context
  usuario_id UUID,
  servicio_origen VARCHAR(50),

  -- Data
  datos JSONB,

  -- Auditoría
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  ip_address INET,
  user_agent TEXT,

  -- Integridad
  hash_anterior UUID
);

-- ============ CREAR INDEXES ============

CREATE INDEX IF NOT EXISTS idx_event_log_usuario_timestamp
  ON event_log (usuario_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_event_log_tipo_timestamp
  ON event_log (tipo, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_event_log_evento_id
  ON event_log (evento_id);

CREATE INDEX IF NOT EXISTS idx_event_log_timestamp_desc
  ON event_log (timestamp DESC);

-- ============ CREAR VISTAS ÚTILES ============

-- Vista: Últimos eventos de un usuario
CREATE OR REPLACE VIEW v_usuario_eventos AS
SELECT
  usuario_id,
  COUNT(*) as total_eventos,
  MAX(timestamp) as ultimo_evento,
  ARRAY_AGG(DISTINCT tipo) as tipos_eventos
FROM event_log
WHERE usuario_id IS NOT NULL
GROUP BY usuario_id;

-- Vista: Eventos fallidos por tipo
CREATE OR REPLACE VIEW v_eventos_fallidos AS
SELECT
  tipo,
  COUNT(*) as total,
  MAX(timestamp) as ultimo,
  MIN(timestamp) as primero
FROM event_log
WHERE tipo LIKE '%FALLIDA%' OR tipo LIKE '%FALLO%' OR tipo LIKE '%RECHAZAD%'
GROUP BY tipo
ORDER BY total DESC;

-- Vista: Timeline de auditoría de un usuario
CREATE OR REPLACE VIEW v_auditoria_usuario AS
SELECT
  usuario_id,
  timestamp,
  tipo,
  datos->>'reserva_id' as reserva_id,
  datos->>'razon' as razon,
  ip_address
FROM event_log
WHERE usuario_id IS NOT NULL
ORDER BY timestamp DESC;

-- ============ CREAR TABLA DE AUDITORÍA GDPR ============

CREATE TABLE IF NOT EXISTS gdpr_access_log (
  id BIGSERIAL PRIMARY KEY,
  usuario_id UUID NOT NULL,
  tipo_acceso VARCHAR(50),  -- 'LECTURA', 'EXPORTACION', 'ELIMINACION', 'MODIFICACION'
  datos_accedidos TEXT,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  usuario_que_accede VARCHAR(100),
  razon VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_gdpr_usuario_timestamp
  ON gdpr_access_log (usuario_id, timestamp DESC);

-- ============ FUNCIONES ÚTILES ============

-- Función: Obtener timeline de evento
CREATE OR REPLACE FUNCTION get_event_timeline(
  p_usuario_id UUID,
  p_evento_id UUID DEFAULT NULL
)
RETURNS TABLE (
  timestamp TIMESTAMP,
  tipo VARCHAR,
  datos JSONB,
  paso_en_saga INT
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    event_log.timestamp,
    event_log.tipo,
    event_log.datos,
    ROW_NUMBER() OVER (ORDER BY event_log.timestamp) as paso_en_saga
  FROM event_log
  WHERE event_log.usuario_id = p_usuario_id
    AND (p_evento_id IS NULL OR event_log.evento_id = p_evento_id)
  ORDER BY event_log.timestamp;
END;
$$ LANGUAGE plpgsql;

-- Función: Contar eventos por tipo
CREATE OR REPLACE FUNCTION count_eventos_por_tipo()
RETURNS TABLE (
  tipo VARCHAR,
  cantidad BIGINT,
  ultimo_evento TIMESTAMP
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    event_log.tipo,
    COUNT(*) as cantidad,
    MAX(event_log.timestamp) as ultimo_evento
  FROM event_log
  GROUP BY event_log.tipo
  ORDER BY cantidad DESC;
END;
$$ LANGUAGE plpgsql;

-- ============ PERMISOS ============

-- El usuario de aplicación solo puede leer y agregar eventos (no modificar/eliminar)
GRANT SELECT, INSERT ON event_log TO eventflow_user;
GRANT SELECT ON v_usuario_eventos TO eventflow_user;
GRANT SELECT ON v_eventos_fallidos TO eventflow_user;
GRANT SELECT ON v_auditoria_usuario TO eventflow_user;
GRANT SELECT, INSERT ON gdpr_access_log TO eventflow_user;
GRANT EXECUTE ON FUNCTION get_event_timeline TO eventflow_user;
GRANT EXECUTE ON FUNCTION count_eventos_por_tipo TO eventflow_user;

-- ============ COMENTARIOS EXPLICATIVOS ============

COMMENT ON TABLE event_log IS
  'Tabla append-only de auditoría. Registra todos los eventos del sistema. NO MODIFICAR O ELIMINAR REGISTROS.';

COMMENT ON COLUMN event_log.id IS
  'ID único incremental del evento';

COMMENT ON COLUMN event_log.tipo IS
  'Tipo de evento: RESERVA_CREADA, PAGO_PROCESADO, PAGO_REVERTIDO, INVENTARIO_DECREMENTADO, DATOS_PERSONALES_MODIFICADOS, etc';

COMMENT ON COLUMN event_log.datos IS
  'JSON con datos específicos del evento (estructura flexible según tipo)';

COMMENT ON COLUMN event_log.hash_anterior IS
  'Referencia al evento anterior del usuario (para integridad de cadena, opcional)';

-- ============ SCRIPT DE PRUEBA ============

-- Para insertar evento de ejemplo:
-- INSERT INTO event_log (evento_id, tipo, usuario_id, datos)
-- VALUES (
--   gen_random_uuid(),
--   'RESERVA_CONFIRMADA',
--   'user-123'::uuid,
--   jsonb_build_object(
--     'reserva_id', 'res-456',
--     'evento_id', 'evt-789',
--     'cantidad', 2,
--     'precio', 300.00
--   )
-- );

-- SELECT * FROM event_log LIMIT 10;
-- SELECT * FROM get_event_timeline('user-123'::uuid);
