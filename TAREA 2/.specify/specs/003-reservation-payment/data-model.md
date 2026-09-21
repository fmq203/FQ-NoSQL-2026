# Data Model: Reservation & Payment (Reservas Service)

**Date**: 2026-09-20

## MongoDB Collection: `reservas`

### Document Structure

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

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | UUID | Yes | PK = reserva_id (v4) |
| `usuario_id` | UUID | Yes | FK → usuarios |
| `evento_id` | UUID | Yes | FK → eventos |
| `cantidad` | Int32 | Yes | > 0 |
| `metodo_pago` | String | Yes | Enum: tarjeta, transferencia, efectivo, mercadopago |
| `monto_total` | Double | Yes | precio * cantidad |
| `numero_confirmacion` | String | Yes | Formato: CONF-YYYYMMDD-XXXXXXXX |
| `estado` | String | Yes | confirmada, cancelada, fallida, pendiente |
| `creado_en` | DateTime | Yes | UTC now |
| `saga_log` | Array | No | Historial pasos SAGA para debugging |

### Indexes

```javascript
// Historial por usuario
db.reservas.createIndex({ "usuario_id": 1, "creado_en": -1 }, { name: "idx_usuario_fecha" })

// Ocupación por evento
db.reservas.createIndex({ "evento_id": 1, "estado": 1 }, { name: "idx_evento_estado" })

// Búsqueda por confirmación (soporte)
db.reservas.createIndex({ "numero_confirmacion": 1 }, { unique: true, name: "idx_confirmacion_unique" })

// Reportes por estado
db.reservas.createIndex({ "estado": 1, "creado_en": -1 }, { name: "idx_estado_fecha" })

// TTL limpieza automática (24h para pendiente/fallida)
db.reservas.createIndex(
  { "creado_en": 1 }, 
  { expireAfterSeconds: 86400, partialFilterExpression: { "estado": { "$in": ["pendiente", "fallida"] } } }
)
```

---

## Redis: Claves Transaccionales

### Inventario por Evento (Gestionado por Eventos Service)
```redis
KEY: inventario:{evento_id}
VALUE: "48500"  # String counter
TTL: 86400 (renovado c/12h por Eventos Service)
```

### Pago por Reserva (Creado en SAGA Paso 4)
```redis
KEY: pago:{reserva_id}
TYPE: Hash
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

### Lua Scripts (Registrados en Startup)

#### `pagar_y_decrementar.lua` (Paso 4 SAGA)
```lua
-- KEYS[1] = inventario:evento_id
-- KEYS[2] = pago:reserva_id
-- ARGV[1] = cantidad, ARGV[2] = reserva_id, ARGV[3] = usuario_id
-- ARGV[4] = monto, ARGV[5] = metodo_pago

local disponible = tonumber(redis.call('GET', KEYS[1]) or '0')
if disponible < tonumber(ARGV[1]) then
    return {0, 'INVENTARIO_INSUFICIENTE'}
end
redis.call('DECRBY', KEYS[1], ARGV[1])
redis.call('HSET', KEYS[2], 
    'reserva_id', ARGV[2], 'usuario_id', ARGV[3],
    'monto', ARGV[4], 'metodo_pago', ARGV[5],
    'estado', 'confirmado', 'timestamp', os.date('!%Y-%m-%dT%H:%M:%SZ')
)
redis.call('EXPIRE', KEYS[2], 86400)
return {1, 'OK'}
```

#### `compensar_pago_inventario.lua` (Rollback Paso 5)
```lua
-- KEYS[1] = inventario:evento_id
-- KEYS[2] = pago:reserva_id
-- ARGV[1] = cantidad

redis.call('INCRBY', KEYS[1], ARGV[1])
redis.call('DEL', KEYS[2])
return {1, 'COMPENSACION_OK'}
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

-- Índices
CREATE INDEX idx_event_log_aggregate ON event_log(aggregate_id);
CREATE INDEX idx_event_log_type ON event_log(event_type);
CREATE INDEX idx_event_log_timestamp ON event_log(timestamp DESC);
CREATE INDEX idx_event_log_correlation ON event_log(correlation_id);
CREATE INDEX idx_event_log_payload_gin ON event_log USING GIN(payload);

-- Particionamiento mensual (opcional, para volumen alto)
-- CREATE TABLE event_log_2026_09 PARTITION OF event_log
-- FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
```

### Event Types & Payloads

| Event Type | Cuándo | Payload Clave |
|------------|--------|---------------|
| `SAGA_STARTED` | Inicio POST /api/reservar | {usuario_id, evento_id, cantidad, metodo_pago} |
| `USUARIO_VALIDADO` | Paso 2 OK | {usuario_id, usuario_nombre} |
| `EVENTO_VALIDADO` | Paso 3 OK | {evento_id, evento_nombre, aforo_disponible} |
| `PAGO_PROCESADO` | Paso 4 OK | {reserva_id, monto, metodo_pago} |
| `INVENTARIO_DECREMENTADO` | Paso 4 OK | {evento_id, cantidad, nuevo_disponible} |
| `RESERVA_CONFIRMADA` | Paso 5 OK | {reserva_id, numero_confirmacion, monto_total} |
| `SAGA_COMPLETED` | Paso 6 OK | {reserva_id, pasos_completados: 6} |
| `SAGA_FAILED` | Cualquier fallo | {reserva_id, error, paso_fallido, compensaciones} |
| `COMPENSACION_EJECUTADA` | Rollback | {paso_compensado, accion, resultado} |

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

-- Tasa éxito SAGA (últimos 7 días)
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

-- Compensaciones por tipo (últimas 24h)
SELECT 
    payload->>'paso_compensado' as paso,
    COUNT(*) as total_compensaciones
FROM event_log
WHERE event_type = 'COMPENSACION_EJECUTADA'
  AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY payload->>'paso_compensado';
```

---

## Chain of Responsibility: ReservaContext

### Dataclass que viaja por la cadena

```python
@dataclass
class ReservaContext:
    usuario_id: UUID
    evento_id: UUID
    cantidad: int
    metodo_pago: str
    reserva_id: UUID          # Generado al inicio (idempotencia)
    correlation_id: UUID      # Para tracing distribuido
    evento_data: dict = None  # Llenado por ValidadorEvento
    usuario_data: dict = None # Llenado por ValidadorInventario
    pago_data: dict = None    # Llenado por ProcesadorPago
    reserva_data: dict = None # Llenado por ConfirmadorReserva
    error: str = None
    status_code: int = 200
```

### Handlers en Orden

| Orden | Handler | Acción | Dependencia | Compensación si falla |
|-------|---------|--------|-------------|----------------------|
| 1 | ValidadorDeDatos | Validar UUIDs, cantidad>0, metodo_pago enum | Local | Ninguna |
| 2 | ValidadorInventario | GET /api/usuarios/{id} | Usuarios Service (HTTP) | Ninguna |
| 3 | ValidadorEvento | GET /api/eventos/{id} + aforo | Eventos Service (HTTP) | Ninguna |
| 4 | ProcesadorPago | Lua Redis: pago + DECRBY inventario | Redis (Lua atómico) | Rollback interno Lua |
| 5 | ConfirmadorReserva | INSERT MongoDB reserva + saga_log | MongoDB | Lua compensación + DELETE reserva |
| 6 | Auditor | INSERT PostgreSQL event_log | PostgreSQL | Log warning only |

---

## Pydantic Models

### ReservaRequest (Input)
```python
class ReservaRequest(BaseModel):
    usuario_id: UUID
    evento_id: UUID
    cantidad: int = Field(..., gt=0)
    metodo_pago: Literal["tarjeta", "transferencia", "efectivo", "mercadopago"]
```

### ReservaResponse (Output)
```python
class ReservaResponse(BaseModel):
    reserva_id: str
    estado: str
    numero_confirmacion: str
```

### MetodoPago Enum
```python
class MetodoPago(str, Enum):
    TARJETA = "tarjeta"
    TRANSFERENCIA = "transferencia"
    EFECTIVO = "efectivo"
    MERCADOPAGO = "mercadopago"
```

### EstadoReserva Enum
```python
class EstadoReserva(str, Enum):
    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    FALLIDA = "fallida"
```

---

## Embedded vs Reference

| Relación | Patrón | Justificación |
|----------|--------|---------------|
| Reserva → Usuario | **Reference** (`usuario_id`) | Muchos-a-uno, vida independiente |
| Reserva → Evento | **Reference** (`evento_id`) | Muchos-a-uno, consulta independiente |
| Reserva → saga_log | **Embedded** | Debugging local, inmutable tras confirmar, 6 items fijos |

---

## Referencias

- `brain/data-models/reservation-schema.md` - Schema completo
- `brain/data-models/db-choice-rationale.md` - Justificación multi-DB
- `brain/architecture/saga-flow.md` - Flujo transaccional + Lua scripts
- `brain/architecture/chain-of-responsibility.md` - Handlers + ReservaContext
- `brain/patterns/event-sourcing-cqrs.md` - Event Sourcing + CQRS