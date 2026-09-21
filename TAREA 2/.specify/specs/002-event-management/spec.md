# Feature Specification: Event Management (Eventos Service)

**Feature Branch**: `002-event-management`

**Created**: 2026-09-20

**Status**: Complete

**Input**: User description: "Maneja la información de los eventos, como la fecha, el lugar, el aforo total y las entradas disponibles. Lectura extremadamente rápida y escalable, priorizando disponibilidad y tolerancia a particiones, aceptando consistencia eventual."

## User Scenarios & Testing

### User Story 1 - Crear Evento (Priority: P1)
Organizador crea evento con nombre, fecha, ubicación, aforo total y precios por categoría.

**Why this priority**: Sin eventos no hay plataforma. Requerido para que Reservas Service valide aforo.

**Independent Test**: POST `/api/eventos` con JSON completo → 201 con evento_id, entradas_disponibles = aforo_total, estado=borrador. Verificar en MongoDB.

**Acceptance Scenarios**:
1. **Given** JSON válido con nombre, fecha futura, ubicacion, aforo_total>0, precios[], **When** POST `/api/eventos`, **Then** 201 con evento_id, entradas_disponibles=aforo_total, estado=borrador
2. **Given** Fecha en el pasado, **When** POST, **Then** 422 Validation Error
3. **Given** aforo_total <= 0, **When** POST, **Then** 422
4. **Given** Suma precios[].disponibles > aforo_total, **When** POST, **Then** 422
5. **Given** Categoría duplicada en precios, **When** POST, **Then** 422

---

### User Story 2 - Obtener Evento con Aforo Disponible (Priority: P1)
Consultar detalles de evento incluyendo entradas disponibles en tiempo real.

**Why this priority**: Requerido por Reservas Service (validar aforo en SAGA paso 3) y por clientes para compra.

**Independent Test**: GET `/api/eventos/{evento_id}` → 200 con evento completo + entradas_disponibles actualizado. Testable sin Reservas Service.

**Acceptance Scenarios**:
1. **Given** Evento publicado con reservas previas, **When** GET `/api/eventos/{id}`, **Then** 200 con entradas_disponibles = aforo_total - sum(reservas confirmadas)
2. **Given** Evento no existe, **When** GET, **Then** 404
3. **Given** Evento estado=borrador, **When** GET, **Then** 200 (visible para admin)
4. **Given** Cache Redis válido (TTL 30s), **When** GET, **Then** Response < 10ms desde cache

---

### User Story 3 - Sincronización Inventario Redis (Priority: P1 - Internal)
Mantener contador de inventario en Redis sincronizado con MongoDB para validación atómica en SAGA.

**Why this priority**: Crítico para atomicidad de pago + decremento inventario en Reservas Service.

**Independent Test**: Verificar que `inventario:{evento_id}` en Redis = `entradas_disponibles` en MongoDB tras cada reserva exitosa.

**Acceptance Scenarios**:
1. **Given** Evento creado, **When** Inicializar inventario, **Then** Redis SET inventario:evento_id = aforo_total
2. **Given** Reserva exitosa (SAGA paso 4), **When** Lua script DECRBY, **Then** Redis decrementado, MongoDB actualizado async
3. **Given** Cache disponibilidad, **When** Inventario cambia, **Then** Cache invalidado (DEL evento:disp:evento_id)

---

### Edge Cases
- Evento con múltiples categorías de precio: entradas_disponibles = sum(precios[].disponibles)
- Cancelación de reserva: Incrementar inventario (compensación SAGA)
- Evento finalizado: Estado=finalizado, no permite nuevas reservas
- Alta concurrencia consulta aforo: Redis cache absorbe carga

## Requirements

### Functional Requirements

- **EM-FR-001**: System MUST crear evento con validación de fecha futura y aforo positivo
- **EM-FR-002**: System MUST validar suma de precios[].disponibles <= aforo_total
- **EM-FR-003**: System MUST retornar evento con entradas_disponibles calculado en tiempo real
- **EM-FR-004**: System MUST mantener contador Redis `inventario:{evento_id}` sincronizado
- **EM-FR-005**: System MUST invalidar cache disponibilidad al cambiar inventario
- **EM-FR-006**: System MUST soportar búsqueda full-text (nombre, descripción, categorías)
- **EM-FR-007**: System MUST responder health check en `/health` con latencia < 10ms, verificando conectividad MongoDB + Redis (ping), sin dependencias externas

### Key Entities

- **Evento**: Agregado principal con nombre, fecha, ubicación embedded, aforo, precios[] embedded, categorías[]
- **PrecioCategoria**: Subdocumento con categoría, precio, disponibles (embebido para atomicidad por categoría)

## Success Criteria

### Measurable Outcomes

- **EM-SC-001**: Crear evento < 150ms (p95)
- **EM-SC-002**: Obtener evento < 50ms (p95) con secondaryPreferred, < 10ms desde Redis cache
- **EM-SC-003**: Sincronización Redis-MongoDB eventual < 500ms tras reserva
- **EM-SC-004**: Cache hit rate > 90% (ventana 5-min rolling) para consultas de aforo
- **EM-SC-005**: 0 inconsistencias inventario (Redis = MongoDB tras sincronización)
- **EM-SC-006**: Health check `/health` < 10ms (p99), verifica MongoDB ping + Redis ping, retorna `{"status":"healthy","checks":{"mongodb":"ok","redis":"ok"},"timestamp":"..."}` o `degraded` si Redis/MongoDB down

## Assumptions

- Eventos creados por admins/organizadores (no público general)
- MongoDB replica set para lecturas escalables
- Redis single-node en dev, cluster en prod
- TTL cache 30s balance entre consistencia y performance
- No versionado de eventos (inmutable tras publicar)

## API Versioning Strategy

### Version Location
- **URL Path**: `/api/v1/eventos`, `/api/v1/eventos/{id}`, etc.
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
3. **Egress**: Pass `X-Correlation-ID` to ALL downstream HTTP calls (Reservas service for SAGA)
4. **Logging**: `trace_id` = `correlation_id`; `span_id` = new UUID per operation

## Health Check States

| State | Criteria | Response |
|-------|----------|----------|
| `healthy` | MongoDB ping OK, Redis ping OK | `{"status":"healthy","checks":{"mongodb":"ok","redis":"ok"},"timestamp":"..."}` |
| `degraded` | MongoDB ping OK, Redis ping FAILED OR vice versa | `{"status":"degraded","checks":{"mongodb":"ok","redis":"down"},"timestamp":"..."}` |
| `unhealthy` | MongoDB ping FAILED AND Redis ping FAILED | `{"status":"unhealthy","checks":{"mongodb":"down","redis":"down"},"timestamp":"..."}` HTTP 503 |

## Event State Machine

| State | Description | Transitions |
|-------|-------------|-------------|
| `borrador` | Evento creado, no visible públicamente | → `publicado` |
| `publicado` | Evento visible, acepta reservas | → `finalizado`, `cancelado` |
| `finalizado` | Evento terminado (fecha pasada) | No transitions |
| `cancelado` | Evento cancelado por organizador | No transitions |

**Reglas**:
- Solo `borrador` → `publicado` (manual por admin)
- `publicado` → `finalizado` (automático por fecha)
- `publicado` → `cancelado` (manual por admin)
- Estados `finalizado`/`cancelado` no permiten nuevas reservas

## Full-Text Search Specification

### Implementation
- **Index**: MongoDB text index on `nombre`, `descripcion`, `categorias`
- **Query**: `$text` operator with `$search` string
- **Scoring**: `{ $meta: "textScore" }` for relevance ranking
- **Sort**: By `textScore` descending, then `fecha` ascending
- **Language**: Spanish (`"language": "spanish"`) for stemming/stopwords
- **Weights**: nombre: 10, descripcion: 5, categorias: 3

### API
- **Endpoint**: GET `/api/v1/eventos?search={query}&skip=0&limit=20`
- **Response**: Paginated events with `textScore` field
- **Performance**: < 100ms p95 for search queries

## Error Response Schemas (OpenAPI 3.1)

Formato RFC 7807 con `X-Correlation-ID` header:

| HTTP Status | Error Code | Title | Cuándo |
|-------------|------------|-------|--------|
| 400 | `VALIDATION_ERROR` | Validation Error | JSON inválido, campos faltantes |
| 404 | `NOT_FOUND` | Not Found | Evento no existe (GET por ID) |
| 422 | `VALIDATION_ERROR` | Unprocessable Entity | Fecha pasada, aforo <= 0, suma precios > aforo, categoría duplicada |
| 500 | `INTERNAL_ERROR` | Internal Server Error | Fallo MongoDB/Redis |
| 503 | `SERVICE_UNAVAILABLE` | Service Unavailable | MongoDB/Redis down |

### Implementation Requirements
- All endpoints MUST return errors in RFC 7807 format exactly as specified
- `correlation_id` in error response MUST match `X-Correlation-ID` header
- `instance` field MUST be the request path (e.g., `/api/v1/eventos`)
- `type` URI MUST use `https://eventflow.example.com/errors/{error-code}` pattern

## Cache Hit Rate Measurement

- **Metric**: `cache_hit_rate` = hits / (hits + misses) over 5-minute rolling window
- **Collection**: Increment counters in `obtener_evento` for each cache hit/miss
- **Exposition**: Via `/metrics` endpoint (Prometheus format)
- **Alert**: Alert if rate < 90% for 10 consecutive minutes

```json
{
  "timestamp": "2026-09-20T10:00:00.000Z",
  "level": "INFO|WARN|ERROR|DEBUG",
  "service": "eventos-service",
  "correlation_id": "uuid-v4",
  "trace_id": "uuid-v4",
  "span_id": "uuid-v4",
  "message": "Human readable message",
  "context": {
    "evento_id": "uuid|optional",
    "operation": "create_event|get_event|get_availability|sync_inventory",
    "duration_ms": 12,
    "cache_hit": true,
    "additional_fields": "..."
  }
}
```

**Reglas**: Mismas que usuarios-service. No PII en logs. `cache_hit` booleano obligatorio en operaciones de lectura.