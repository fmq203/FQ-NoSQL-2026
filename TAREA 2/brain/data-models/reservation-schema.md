---
name: reservation-schema
description: Esquema de datos de Reserva para MongoDB y PostgreSQL
metadata:
  type: specification
  status: complete
---

# Esquema de Reserva — MongoDB + PostgreSQL

## MongoDB: Colección `reservas`

### Documento Completo

```json
{
  "_id": { "$uuid": "550e8400-e29b-41d4-a716-446655440002" },
  "usuario_id": { "$uuid": "550e8400-e29b-41d4-a716-446655440000" },
  "evento_id": { "$uuid": "550e8400-e29b-41d4-a716-446655440001" },
  "cantidad": { "$numberInt": "2" },
  "metodo_pago": "tarjeta",
  "monto_total": { "$numberDouble": "160.0" },
  "numero_confirmacion": "CONF-20260920-A1B2C3D4",
  "estado": "confirmada",
  "creado_en": { "$date": "2026-09-20T10:05:00.000Z" },
  "saga_log": [
    { "paso": "USUARIO_VALIDADO", "timestamp": { "$date": "2026-09-20T10:05:00.001Z" }, "exitoso": true },
    { "paso": "EVENTO_VALIDADO", "timestamp": { "$date": "2026-09-20T10:05:00.002Z" }, "exitoso": true },
    { "paso": "PAGO_PROCESADO", "timestamp": { "$date": "2026-09-20T10:05:00.003Z" }, "exitoso": true },
    { "paso": "RESERVA_CONFIRMADA", "timestamp": { "$date": "2026-09-20T10:05:00.004Z" }, "exitoso": true },
    { "paso": "AUDITORIA_REGISTRADA", "timestamp": { "$date": "2026-09-20T10:05:00.005Z" }, "exitoso": true }
  ]
}
```

### Definición de Campos

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `_id` | UUID | Sí | PK, auto v4 = `reserva_id` |
| `usuario_id` | UUID | Sí | FK → usuarios |
| `evento_id` | UUID | Sí | FK → eventos |
| `cantidad` | Int | Sí | > 0 |
| `metodo_pago` | String | Sí | Enum: tarjeta, transferencia, efectivo, mercadopago |
| `monto_total` | Double | Sí | precio * cantidad |
| `numero_confirmacion` | String | Sí | Formato: `CONF-YYYYMMDD-XXXXXXXX` |
| `estado` | String | Sí | `confirmada`, `cancelada`, `fallida`, `pendiente` |
| `creado_en` | DateTime | Sí | UTC now |
| `saga_log` | Array | No | Historial pasos SAGA para debugging |

### Índices MongoDB

```javascript
// Consultas por usuario (historial)
db.reservas.createIndex({ "usuario_id": 1, "creado_en": -1 }, { name: "idx_usuario_fecha" })

// Consultas por evento (ocupación)
db.reservas.createIndex({ "evento_id": 1, "estado": 1 }, { name: "idx_evento_estado" })

// Búsqueda por confirmación (soporte cliente)
db.reservas.createIndex({ "numero_confirmacion": 1 }, { unique: true, name: "idx_confirmacion_unique" })

// Estados para reportes
db.reservas.createIndex({ "estado": 1, "creado_en": -1 }, { name: "idx_estado_fecha" })

// TTL para reservas fallidas/pendientes (limpieza automática 24h)
db.reservas.createIndex(
  { "creado_en": 1 }, 
  { expireAfterSeconds: 86400, partialFilterExpression: { "estado": { "$in": ["pendiente", "fallida"] } } }
)
```

---

## Redis: Claves Transaccionales (Efímeras)

### Inventario por Evento
```redis
# String contador (inicializado por Eventos Service)
KEY: inventario:{evento_id}
VALUE: "48500"  (entradas disponibles)
TTL: 86400 (renovado periódicamente)
```

### Pago por Reserva (Creado en SAGA paso 4)
```redis
# Hash con datos de pago
KEY: pago:{reserva_id}
FIELDS:
  reserva_id: "uuid"
  usuario_id: "uuid"
  evento_id: "uuid"
  cantidad: "2"
  monto: "160.0"
  metodo_pago: "tarjeta"
  estado: "confirmado"
  timestamp: "2026-09-20T10:05:00.000Z"
TTL: 86400 (24h)
```

### Lock Distribuido (Opcional, para alta concurrencia)
```redis
# Lock por evento durante SAGA
KEY: lock:evento:{evento_id}
VALUE: "reserva_id"
TTL: 10 (expiración corta)
# SET NX para adquirir, Lua para liberar seguro
```

---

## PostgreSQL: Tabla `event_log` (Event Sourcing)

### DDL

```sql
CREATE TABLE event_log (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    aggregate_id UUID NOT NULL,
    aggregate_type VARCHAR(50) NOT NULL DEFAULT 'Reserva',
    payload JSONB NOT NULL,
    metadata JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    correlation_id UUID
);

-- Índices para consultas frecuentes
CREATE INDEX idx_event_log_aggregate ON event_log(aggregate_id);
CREATE INDEX idx_event_log_type ON event_log(event_type);
CREATE INDEX idx_event_log_timestamp ON event_log(timestamp DESC);
CREATE INDEX idx_event_log_correlation ON event_log(correlation_id);
CREATE INDEX idx_event_log_payload_gin ON event_log USING GIN(payload);

-- Particionamiento por mes (opcional, para volumen alto)
-- CREATE TABLE event_log_2026_09 PARTITION OF event_log
-- FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
```

### Event Types y Payloads

| Event Type | aggregate_type | Payload Ejemplo |
|------------|----------------|-----------------|
| `SAGA_STARTED` | Reserva | `{usuario_id, evento_id, cantidad, metodo_pago}` |
| `USUARIO_VALIDADO` | Reserva | `{usuario_id, usuario_nombre}` |
| `EVENTO_VALIDADO` | Reserva | `{evento_id, evento_nombre, aforo_disponible}` |
| `PAGO_PROCESADO` | Reserva | `{reserva_id, monto, metodo_pago, transaccion_id}` |
| `INVENTARIO_DECREMENTADO` | Reserva | `{evento_id, cantidad, nuevo_disponible}` |
| `RESERVA_CONFIRMADA` | Reserva | `{reserva_id, numero_confirmacion, monto_total}` |
| `SAGA_COMPLETED` | Reserva | `{reserva_id, pasos_completados: 6}` |
| `SAGA_FAILED` | Reserva | `{reserva_id, error, paso_fallido, compensaciones}` |
| `COMPENSACION_EJECUTADA` | Reserva | `{paso_compensado, accion, resultado}` |
| `RESERVA_CANCELADA` | Reserva | `{reserva_id, motivo, monto_reembolso}` |

### Consultas Analíticas (CQRS Read Model)

```sql
-- Ventas por evento (últimos 30 días)
SELECT 
    payload->>'evento_id' as evento_id,
    COUNT(*) as total_reservas,
    SUM((payload->>'cantidad')::int) as total_entradas,
    SUM((payload->>'monto_total')::numeric) as ingreso_total
FROM event_log
WHERE event_type = 'RESERVA_CONFIRMADA'
  AND timestamp > NOW() - INTERVAL '30 days'
GROUP BY payload->>'evento_id';

-- Tasa de éxito SAGA
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

-- Compensaciones por tipo
SELECT 
    payload->>'paso_compensado' as paso,
    COUNT(*) as total_compensaciones
FROM event_log
WHERE event_type = 'COMPENSACION_EJECUTADA'
  AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY payload->>'paso_compensado';
```

---

## Relación Embedded vs Reference

| Relación | Patrón | Justificación |
|----------|--------|---------------|
| Reserva → Usuario | **Reference** (`usuario_id`) | Usuario consultado independientemente, muchos-a-uno |
| Reserva → Evento | **Reference** (`evento_id`) | Evento consultado independientemente, muchos-a-uno |
| Usuario → Historial | **Embedded** (`historial_compras[]`) | Acceso frecuente junto a usuario, cardinalidad baja |
| Evento → Precios | **Embedded** (`precios[]`) | Siempre se leen juntos, atómicos por categoría |

---

## Referencias

- [[microservices/reservas-pagos]] — Especificación completa servicio
- [[architecture/saga-flow]] — Flujo transaccional
- [[patterns/event-sourcing-cqrs]] — Event Sourcing + CQRS
- [[data-models/db-choice-rationale]] — Justificación multi-DB