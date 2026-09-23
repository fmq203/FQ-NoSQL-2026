# Feature Specification: Reservation & Payment (Reservas Service)

**Feature Branch**: `003-reservation-payment`

**Created**: 2026-09-20

**Status**: Complete

**Input**: User description: "Procesa las transacciones de compra de entradas y se comunica con otros servicios para completar la compra. Patrón SAGA con Orquestación: Reservas Service actúa como Orquestador Central. Patrón Chain of Responsibility para validaciones secuenciales. Escritura requiere alta consistencia - reserva única, no doble venta."

## User Scenarios & Testing

### User Story 1 - Comprar Entradas (SAGA Completa) (Priority: P1)
Usuario compra entradas: valida usuario, valida evento+aforo, procesa pago atómico, confirma reserva, audita.

**Why this priority**: Core business flow - genera revenue, requiere consistencia fuerte.

**Independent Test**: POST `/api/v1/reservar` con usuario_id válido, evento_id con aforo, cantidad, metodo_pago → 201 con reserva_id, estado=confirmada, numero_confirmacion. Verificar: MongoDB reserva, Redis pago, PostgreSQL audit log, inventario decrementado.

**Acceptance Scenarios**:
1. **Given** Usuario existe, Evento publicado con aforo>=cantidad, **When** POST `/api/v1/reservar`, **Then** 201 Reserva confirmada, inventario decrementado, pago en Redis, audit en PostgreSQL
2. **Given** Usuario no existe, **When** POST `/api/v1/reservar`, **Then** 404 "Usuario no encontrado", SAGA termina sin compensación
3. **Given** Evento no existe, **When** POST `/api/v1/reservar`, **Then** 404 "Evento no encontrado"
4. **Given** Aforo insuficiente (disponibles < cantidad), **When** POST `/api/v1/reservar`, **Then** 409 "Inventario insuficiente"
5. **Given** Fallo MongoDB al guardar reserva, **When** POST `/api/v1/reservar`, **Then** 500, compensación automática: Redis INCRBY inventario + DEL pago
6. **Given** Fallo PostgreSQL auditoría, **When** POST `/api/v1/reservar`, **Then** 201 (reserva OK), warning log, NO rollback

---

### User Story 2 - Chain of Responsibility Validaciones (Priority: P1)
Estructura de validaciones secuenciales: Datos → Usuario → Evento → Pago → Reserva → Auditoría.

**Why this priority**: Arquitectura requerida por especificación, permite testing unitario y extensibilidad.

**Independent Test**: Cada handler testeable independientemente con ReservaContext mock. Cadena completa integra con servicios reales.

**Acceptance Scenarios**:
1. **Given** Request inválido (cantidad<=0), **When** ValidadorDeDatos, **Then** Error 400, cadena se detiene
2. **Given** Usuario inexistente, **When** ValidadorUsuario, **Then** Error 404, cadena se detiene
3. **Given** Evento inexistente, **When** ValidadorEvento, **Then** Error 404
4. **Given** Aforo insuficiente, **When** ValidadorEvento, **Then** Error 409
5. **Given** Pago falla (Redis), **When** ProcesadorPago, **Then** Error 500, compensación automática en Lua
6. **Given** Todo válido, **When** Cadena completa, **Then** 201 con todos los pasos en saga_log

---

### User Story 3 - Compensaciones Automáticas SAGA (Priority: P1)
Rollback automático en fallos tras paso 4 (pago/inventario).

**Why this priority**: Garantía de consistencia - no dinero cobrado sin reserva, no inventario decrementado sin pago.

**Independent Test**: Simular fallo en Paso 5 (MongoDB) → Verificar compensación Redis ejecutada. Simular fallo Paso 4 → Verificar rollback atómico en Lua.

**Acceptance Scenarios**:
1. **Given** Fallo Paso 4 (Lua script), **When** Error inventario/pago, **Then** Transacción atómica: 0 cambios en Redis (rollback interno)
2. **Given** Fallo Paso 5 (MongoDB insert), **When** Excepción, **Then** Compensación: DELETE reserva (si se creó) + Lua INCRBY inventario + DEL pago
3. **Given** Fallo Paso 6 (PostgreSQL), **When** Excepción, **Then** Log warning, reserva confirmada, NO compensación

---

### User Story 4 - Event Sourcing + CQRS Auditoría (Priority: P2)
Registro inmutable de todos los pasos SAGA en PostgreSQL para compliance y debugging.

**Why this priority**: Requerimiento opcional del PDF, valor para compliance financiero.

**Independent Test**: Consultar event_log por aggregate_id=reserva_id → 6+ eventos ordenados: SAGA_STARTED, USUARIO_VALIDADO, EVENTO_VALIDADO, PAGO_PROCESADO, INVENTARIO_DECREMENTADO, RESERVA_CONFIRMADA, SAGA_COMPLETED.

**Acceptance Scenarios**:
1. **Given** Reserva exitosa, **When** Consultar event_log, **Then** 7 eventos con timestamps crecientes, payloads completos
2. **Given** SAGA fallida, **When** Consultar event_log, **Then** SAGA_FAILED + COMPENSACION_EJECUTADA con detalles
3. **Given** Múltiples reservas, **When** Query analítica ventas por evento, **Then** Vista materializada SQL retorna agregados correctos

---

### Edge Cases
- Idempotencia: Mismo reserva_id reenviado → **200 OK** con datos de reserva existente (idempotente, no doble cobro)
- Timeout HTTP a Usuarios/Eventos: Retry 3x con backoff (0.5s, 1s, 2s), luego 504
- Degraded dependency (health check "degraded"): Retry 1x con timeout extendido (10s), luego 504 si persiste
- Redis unavailable: Circuit breaker, 503 service unavailable
- Pago parcial (monto incorrecto): Validación en Lua script
- Concurrencia extrema: Lua script serializa, Redis single-threaded

## Requirements

### Functional Requirements

- **RP-FR-001**: System MUST orquestar SAGA con 6 pasos via Chain of Responsibility: ValidarDatos → ValidarUsuario → ValidarEvento → ProcesarPago → ConfirmarReserva → Auditar
- **RP-FR-002**: System MUST ejecutar pago + decremento inventario ATÓMICAMENTE via Lua script en Redis
- **RP-FR-003**: System MUST compensar automáticamente: Fallo paso 5 → Rollback Redis + MongoDB; Fallo paso 4 → Rollback atómico Lua
- **RP-FR-004**: System MUST registrar TODOS los pasos SAGA en PostgreSQL event_log (Event Sourcing)
- **RP-FR-005**: System MUST separar lectura/escritura (CQRS): Escritura→PostgreSQL, Lectura operativa→MongoDB, Analítica→SQL views
- **RP-FR-006**: System MUST generar numero_confirmacion formato CONF-YYYYMMDD-XXXXXXXX
- **RP-FR-007**: System MUST validar idempotencia via reserva_id (UUID v4)
- **RP-FR-008**: System MUST responder health check en `/health` con latencia < 10ms, verificando conectividad MongoDB + Redis + PostgreSQL + HTTP clients (Usuarios/Eventos services), reportando degradación por dependencia

### Key Entities

- **Reserva**: Agregado transaccional con usuario_id, evento_id, cantidad, metodo_pago, monto_total, estado, saga_log[]
- **PagoRedis**: Hash efímero en Redis con reserva_id, usuario_id, monto, metodo_pago, estado, timestamp (TTL 24h)
- **InventarioRedis**: String contador `inventario:{evento_id}` (TTL renovado)
- **EventLog**: Tabla PostgreSQL append-only con event_type, aggregate_id, payload JSONB, metadata JSONB

### MongoDB Read Model (Operational CQRS)

**Colección `reservas` - Document Structure:**
```javascript
{
  "_id": UUID("..."),                    // reserva_id (PK, idempotency key)
  "usuario_id": UUID("..."),
  "evento_id": UUID("..."),
  "categoria": "platea",                 // selected category
  "cantidad": 2,
  "metodo_pago": "tarjeta",
  "precio_unitario": 1500.00,
  "monto_total": 3000.00,
  "estado": "confirmada",                // pendiente | confirmada | fallida | compensada
  "numero_confirmacion": "CONF-20260920-A1B2C3D4",
  "creado_en": ISODate("2026-09-20T10:00:00.000Z"),
  "actualizado_en": ISODate("2026-09-20T10:00:05.000Z"),
  "saga_log": [                          // Embedded for debugging (denormalized)
    { "paso": 1, "handler": "ValidadorDeDatos", "estado": "ok", "timestamp": "...", "duracion_ms": 2 },
    { "paso": 2, "handler": "ValidadorUsuario", "estado": "ok", "timestamp": "...", "duracion_ms": 45 },
    { "paso": 3, "handler": "ValidadorEvento", "estado": "ok", "timestamp": "...", "duracion_ms": 38 },
    { "paso": 4, "handler": "ProcesadorPago", "estado": "ok", "timestamp": "...", "duracion_ms": 12 },
    { "paso": 5, "handler": "ConfirmadorReserva", "estado": "ok", "timestamp": "...", "duracion_ms": 8 },
    { "paso": 6, "handler": "Auditor", "estado": "ok", "timestamp": "...", "duracion_ms": 15 }
  ],
  "correlation_id": UUID("..."),
  "metadata": {
    "ip_cliente": "192.168.1.1",
    "user_agent": "..."
  }
}
```

**Optimized Indexes for Read Patterns:**
```javascript
// Query: Reservas por usuario (historial)
db.reservas.createIndex({ "usuario_id": 1, "creado_en": -1 })

// Query: Reservas por evento + estado (operaciones de boletería)
db.reservas.createIndex({ "evento_id": 1, "estado": 1 })

// Query: Lookup por numero_confirmacion (atención al cliente)
db.reservas.createIndex({ "numero_confirmacion": 1 }, { unique: true })

// Query: Reservas por estado + fecha (dashboard admin)
db.reservas.createIndex({ "estado": 1, "creado_en": -1 })

// TTL: Auto-limpieza de reservas pendientes/fallidas > 24h
db.reservas.createIndex(
  { "creado_en": 1 },
  { expireAfterSeconds: 86400, partialFilterExpression: { "estado": { "$in": ["pendiente", "fallida"] } } }
)
```

**Read Queries (Operational):**
- `GET /api/v1/reservar/{reserva_id}` → find by `_id`
- `GET /api/v1/reservar?usuario_id=...` → find by `usuario_id` + sort `creado_en DESC`
- `GET /api/v1/reservar?evento_id=...&estado=confirmada` → find by `evento_id` + `estado`
```

## Success Criteria

### Measurable Outcomes

- **RP-SC-001**: SAGA completa exitosa < 500ms (p95) bajo carga normal (incluye latencia red a Usuarios/Eventos services)
- **RP-SC-002**: 0 doble ventas (unicidad reserva_id + atomicidad Redis)
- **RP-SC-003**: 0 inventario negativo (Lua script valida antes de decrementar)
- **RP-SC-004**: Compensación exitosa 100% en fallos simulados paso 4-5
- **RP-SC-005**: Audit log 100% completo (9 event types: SAGA_STARTED, USUARIO_VALIDADO, EVENTO_VALIDADO, PAGO_PROCESADO, INVENTARIO_DECREMENTADO, RESERVA_CONFIRMADA, SAGA_COMPLETED, SAGA_FAILED, COMPENSACION_EJECUTADA)
- **RP-SC-006**: Tasa éxito SAGA > 99.9% en condiciones normales (ventana 7 días rolling)
- **RP-SC-007**: Latencia P99 < 1s incluso bajo carga (100 req/s)
- **RP-SC-008**: Health check `/health` < 10ms (p99), verifica MongoDB + Redis + PostgreSQL + HTTP clients (Usuarios/Eventos), retorna status por dependencia: `{"status":"healthy|degraded","checks":{"mongodb":"ok","redis":"ok","postgresql":"ok","usuarios_service":"ok","eventos_service":"ok"},"timestamp":"..."}`

## Assumptions

- Usuarios Service y Eventos Service disponibles (health checks passing)
- Redis single-threaded garantiza atomicidad Lua (justificación completa en `brain/decisions/db-selection.md`: MongoDB para documentos anidados Usuarios/Eventos/Reservas; Redis para atomicidad pago+inventario via Lua; PostgreSQL para ACID auditoría/Event Sourcing)
- PostgreSQL ACID para auditoría inmutable
- No autenticación en MVP (usuario_id en request body)
- Métodos de pago: tarjeta, transferencia, efectivo, mercadopago
- Moneda fija (no conversión)
- No reembolsos en MVP (solo cancelación lógica)

## API Versioning Strategy

### Version Location
- **URL Path**: `/api/v1/reservar`, `/api/v1/reservar/{reserva_id}`, etc.
- **Header**: `Accept: application/vnd.eventflow.v1+json` (optional, for future)

### Versioning Rules
1. **Breaking changes** → New major version (`v2`, `v3`) in URL path
2. **Non-breaking additions** → Same version, backward compatible
3. **Deprecation**: 90-day notice via `Deprecation` header + `Sunset` header
4. **Current version**: `v1` (this specification)

### Version Header (Optional)
```
Accept: application/vnd.eventflow.v1+json
```
If absent, defaults to latest stable (`v1`).

## Health Check States (Per Dependency)

| Dependency | Healthy | Degraded | Unhealthy |
|------------|---------|----------|-----------|
| MongoDB | Ping OK | Ping slow (>100ms) | Ping failed / connection refused |
| Redis | Ping OK | Ping slow (>50ms) | Ping failed / connection refused |
| PostgreSQL | Ping OK | Ping slow (>100ms) | Ping failed / connection refused |
| Usuarios Service | HTTP 200 /health | HTTP 200 but degraded | HTTP 5xx / timeout / circuit open |
| Eventos Service | HTTP 200 /health | HTTP 200 but degraded | HTTP 5xx / timeout / circuit open |

**Aggregated Service Status**:
- `healthy`: All dependencies healthy
- `degraded`: One or more dependencies degraded, none unhealthy
- `unhealthy`: One or more dependencies unhealthy

**Response Format**:
```json
{
  "status": "healthy|degraded|unhealthy",
  "checks": {
    "mongodb": "ok|degraded|down",
    "redis": "ok|degraded|down",
    "postgresql": "ok|degraded|down",
    "usuarios_service": "ok|degraded|down",
    "eventos_service": "ok|degraded|down"
  },
  "timestamp": "2026-09-20T10:00:00.000Z"
}
```
HTTP 503 if status = unhealthy.

## Circuit Breaker State Machine

### States
- **Closed** (Normal): Requests pass through. Failure counter resets on success.
- **Open** (Tripped): Requests fail fast (return 503). After 30s timeout → Half-Open.
- **Half-Open** (Testing): Limited requests allowed (1 at a time). Success → Closed. Failure → Open.

### Thresholds
- **Failure threshold**: 5 consecutive failures (or 50% failure rate over 10 requests)
- **Success threshold**: 1 successful request in Half-Open → Closed
- **Timeout**: 30 seconds in Open state before transitioning to Half-Open

### Applied To
- HTTP → Usuarios Service
- HTTP → Eventos Service

## Metrics Exposition (Prometheus)

### Endpoint
- **Path**: `/metrics`
- **Format**: Prometheus text format (text/plain; version=0.0.4)

### Required Metrics
| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `saga_duration_seconds` | Histogram | `step`, `status` | Latency per SAGA step |
| `saga_total` | Counter | `status` | Total SAGA executions (success/failed/compensated) |
| `saga_compensation_total` | Counter | `step` | Compensations triggered per step |
| `http_request_duration_seconds` | Histogram | `method`, `path`, `status` | HTTP latency |
| `db_operation_duration_seconds` | Histogram | `db`, `operation`, `status` | DB operation latency |
| `circuit_breaker_state` | Gauge | `service`, `state` | CB state (0=closed, 1=open, 2=half-open) |
| `idempotency_hit_total` | Counter | | Idempotent request hits |

### Collection
- Increment counters in each handler and orchestrator
- Histogram buckets: 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10

## Idempotency Behavior

- **Idempotency Key**: `reserva_id` (UUID v4) generated by client or server
- **Check**: Before SAGA start, query MongoDB `_id`, Redis `pago:{reserva_id}`, PG `aggregate_id`
- **If exists**: Return **200 OK** with existing reservation data (idempotent success)
- **If not exists**: Proceed with SAGA, store `reserva_id` as primary key in all stores
- **Concurrency**: MongoDB unique index on `_id` prevents race conditions

## Distributed Tracing Headers

### Request Headers (Incoming)
| Header | Required | Description |
|--------|----------|-------------|
| `X-Correlation-ID` | No | UUID v4 — if absent, service generates new |
| `X-Trace-ID` | No | Alias for `X-Correlation-ID` (backward compat) |

### Response Headers (Outgoing)
| Header | Always Present | Description |
|--------|----------------|-------------|
| `X-Correlation-ID` | Yes | UUID v4 — same as request or generated |
| `X-Trace-ID` | Yes | Same as `X-Correlation-ID` |

### Propagation Rules
1. **Ingress**: Extract `X-Correlation-ID` from request headers; if missing, generate UUID v4
2. **Internal**: Use as `correlation_id` in all structured logs (see Logging Schema)
3. **Egress**: Pass `X-Correlation-ID` to ALL downstream HTTP calls (Usuarios, Eventos services)
4. **Logging**: `trace_id` = `correlation_id`; `span_id` = new UUID per operation
5. **Storage**: Include in Redis `pago:{reserva_id}` hash, PG `event_log.metadata.correlation_id`

## Error Response Schemas (OpenAPI 3.1)

Formato RFC 7807 con `X-Correlation-ID` header:

| HTTP Status | Error Code | Title | Cuándo |
|-------------|------------|-------|--------|
| 400 | `VALIDATION_ERROR` | Validation Error | UUIDs inválidos, cantidad <= 0, método pago inválido |
| 404 | `USER_NOT_FOUND` | Not Found | Usuario no existe (Paso 2) |
| 404 | `EVENT_NOT_FOUND` | Not Found | Evento no existe (Paso 3) |
| 409 | `INSUFFICIENT_INVENTORY` | Conflict | Aforo insuficiente (Paso 3) |
| 200 | `IDEMPOTENCY_OK` | OK | reserva_id ya procesado (retorna reserva existente) |
| 500 | `PAYMENT_FAILED` | Internal Server Error | Fallo Lua script Redis (Paso 4) |
| 500 | `RESERVATION_FAILED` | Internal Server Error | Fallo MongoDB insert (Paso 5) |
| 500 | `INTERNAL_ERROR` | Internal Server Error | Error inesperado |
| 503 | `SERVICE_UNAVAILABLE` | Service Unavailable | Usuarios/Eventos service down, Redis/MongoDB/PG down, circuit breaker open |

### Implementation Requirements
- All endpoints MUST return errors in RFC 7807 format exactly as specified
- `correlation_id` in error response MUST match `X-Correlation-ID` header
- `instance` field MUST be the request path (e.g., `/api/v1/reservar`)
- `type` URI MUST use `https://eventflow.example.com/errors/{error-code}` pattern

## Structured Logging Schema (Mandatory per Constitution Principle IV)

| Componente | Timeout | Retries | Backoff | Circuit Breaker |
|------------|---------|---------|---------|-----------------|
| HTTP → Usuarios Service | 5s | 3 | 0.5s, 1s, 2s (exponencial) | Abrir tras 5 fallos consecutivos, half-open 30s |
| HTTP → Eventos Service | 5s | 3 | 0.5s, 1s, 2s (exponencial) | Abrir tras 5 fallos consecutivos, half-open 30s |
| Redis (Lua scripts) | 1s | 0 (atómico) | N/A | N/A |
| MongoDB (write_concern majority) | 3s | 1 | 1s | N/A |
| PostgreSQL (event_log) | 3s | 2 | 0.5s, 1s | N/A |
| Health Check HTTP Clients | 2s | 1 | 0.5s | N/A |

**Idempotencia**: `reserva_id` (UUID v4) generado al inicio = clave en MongoDB `_id`, Redis `pago:{reserva_id}`, PG `aggregate_id`. Check-exists antes de iniciar SAGA. **Si existe: retorna 200 OK con datos de reserva existente**.

**Correlation ID**: UUID v4 generado al inicio, propagado en: logs estructurados (campo `correlation_id`), HTTP header `X-Correlation-ID`, PG `event_log.metadata.correlation_id`, Redis `pago:{reserva_id}.correlation_id`.

## Lua Script Specifications

### `pagar_y_decrementar.lua` (Paso 4 SAGA)
Ejecuta atómicamente: verifica inventario, decrementa contador, crea hash de pago.

**Claves Redis:**
- `KEYS[1]` = `inventario:{evento_id}` (contador string)
- `KEYS[2]` = `pago:{reserva_id}` (hash)

**Argumentos:**
- `ARGV[1]` = cantidad (int)
- `ARGV[2]` = reserva_id (UUID string)
- `ARGV[3]` = usuario_id (UUID string)
- `ARGV[4]` = monto (decimal string)
- `ARGV[5]` = metodo_pago (string)

**Lógica:**
```lua
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

**Comportamiento atómico:** Redis single-threaded garantiza que verificación + decremento + creación de pago sean una sola operación atómica. Si falla cualquier paso, no hay cambios parciales.

### `compensar_pago_inventario.lua` (Rollback Paso 5)
Ejecuta compensación atómica: incrementa inventario + elimina pago.

**Claves Redis:**
- `KEYS[1]` = `inventario:{evento_id}`
- `KEYS[2]` = `pago:{reserva_id}`

**Argumentos:**
- `ARGV[1]` = cantidad (int)

**Lógica:**
```lua
redis.call('INCRBY', KEYS[1], ARGV[1])
redis.call('DEL', KEYS[2])
return {1, 'COMPENSACION_OK'}
```

**Registro:** Ambos scripts se registran en startup via `SCRIPT LOAD` y se ejecutan via `EVALSHA` para performance.

## Saga Orchestrator Specification

### Responsabilidades
El `SagaOrchestrator` coordina la ejecución de la Chain of Responsibility y maneja errores/compensaciones.

### Interfaz
```python
class SagaOrchestrator:
    def __init__(self, chain: Handler, compensation_handlers: Dict[int, Callable]):
        self.chain = chain
        self.compensation_handlers = compensation_handlers
    
    async def execute(self, context: ReservaContext) -> ReservaContext:
        """Ejecuta la cadena completa con manejo de errores."""
```

### Flujo de Ejecución
1. **Iniciar**: Generar `reserva_id`, `correlation_id`, crear `ReservaContext`
2. **Idempotencia**: Verificar si `reserva_id` ya existe en MongoDB/Redis/PG
3. **Ejecutar cadena**: `await chain.handle(context)` - ejecuta 6 handlers secuencialmente
4. **Manejo de errores**: Si handler falla (context.error):
   - Identificar paso fallido (1-6)
   - Ejecutar compensaciones en orden inverso (paso N-1 → 4)
   - Solo pasos mutantes (4, 5) tienen compensación
   - Registrar `COMPENSACION_EJECUTADA` en PostgreSQL
5. **Resultado**: Retornar `ReservaContext` con error/status_code

### Compensaciones por Paso
| Paso Fallido | Acción de Compensación |
|--------------|------------------------|
| 1-3 (Validación) | Ninguna (solo lectura) |
| 4 (Pago/Inventario) | Rollback atómico interno en Lua (0 cambios) |
| 5 (MongoDB) | Lua `compensar_pago_inventario.lua` (INCRBY + DEL) |
| 6 (PostgreSQL) | Log warning ONLY, NO compensación (reserva ya confirmada) |

### Timeouts y Reintentos
- **Timeout por paso**: Configurable por handler (ver tabla Timeouts)
- **Reintentos HTTP**: 3x con backoff exponencial (0.5s, 1s, 2s)
- **Circuit Breaker**: 5 fallos consecutivos → Open, 30s → Half-Open

## CQRS Read Models / SQL Views

### Modelo de Lectura Operativa (MongoDB)
- Colección `reservas` con índices optimizados para consultas por usuario, evento, estado
- `saga_log` embebido para debugging granular

### Modelo Analítico (PostgreSQL - Event Sourcing)

#### Vista: `ventas_por_evento` (Últimos 30 días)
```sql
CREATE VIEW ventas_por_evento AS
SELECT 
    payload->>'evento_id' as evento_id,
    COUNT(*) as total_reservas,
    SUM((payload->>'cantidad')::int) as total_entradas,
    SUM((payload->>'monto_total')::numeric) as ingreso_total
FROM event_log
WHERE event_type = 'RESERVA_CONFIRMADA'
  AND timestamp > NOW() - INTERVAL '30 days'
GROUP BY payload->>'evento_id';
```

#### Vista: `tasa_exito_saga` (Últimos 7 días - rolling)
```sql
CREATE VIEW tasa_exito_saga AS
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
```

#### Vista: `compensaciones_por_tipo` (Últimas 24h)
```sql
CREATE VIEW compensaciones_por_tipo AS
SELECT 
    payload->>'paso_compensado' as paso,
    COUNT(*) as total_compensaciones
FROM event_log
WHERE event_type = 'COMPENSACION_EJECUTADA'
  AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY payload->>'paso_compensado';
```

#### Índices de Soporte Analítico
```sql
CREATE INDEX idx_event_log_payload_gin ON event_log USING GIN(payload);
-- Particionamiento mensual (opcional, para volumen > 10M eventos/mes)
-- CREATE TABLE event_log_2026_09 PARTITION OF event_log
-- FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
```

**Criterio de activación de particionamiento**: Activar cuando `event_log` supere 10M eventos/mes o latencia de consultas analíticas > 500ms.

## Price Source para `monto_total`

El campo `monto_total` en la reserva se calcula como: `precio_unitario * cantidad`.

**Fuente del precio**: El `Eventos Service` provee el precio por categoría en el endpoint `GET /api/v1/eventos/{evento_id}`:
- Response incluye `precios[]` con `categoria`, `precio`, `disponibles`
- El `ValidadorEvento` obtiene y almacena `evento_data.precios` en `ReservaContext`
- El `ProcesadorPago` calcula: `monto_total = precio_categoria_seleccionada * cantidad`
- **MVP (v1)**: Se usa la primera categoría disponible; campo `categoria` en request es opcional
- **Post-MVP (v2+)**: Cliente especifica `categoria` en request para selección explícita
  - **Acceptance Criteria v2**: POST `/api/v1/reservar` acepta campo opcional `categoria`; si se provee, validar que existe en `precios[]` del evento; si no, usar primera categoría; rechazar con 400 si categoría no existe
  - **Requerimiento**: Endpoint Eventos Service actualizado para incluir `categoria` en response (ya incluido)

**Validación**: El `ProcesadorPago` verifica que `monto_total` coincida con `precio * cantidad` antes de ejecutar Lua script.