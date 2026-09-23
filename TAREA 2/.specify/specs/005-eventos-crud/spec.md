# Feature Specification: Eventos CRUD Service

**Feature Branch**: `005-eventos-crud`

**Created**: 2026-09-23

**Status**: Draft

**Input**: User description: "Eventos Service: CRUD eventos en MongoDB con health check, modelo: nombre, estado, aforo_total, entradas_disponibles, precios[], ubicacion. Endpoints: POST /api/eventos, GET /api/eventos/{id}, GET /health. MongoDB Motor async."

## User Scenarios & Testing

### User Story 1 - Crear Evento (Priority: P1)
Un organizador crea un nuevo evento con nombre, estado, aforo total, entradas disponibles, precios por categoría y ubicación.

**Why this priority**: Funcionalidad base - sin eventos no hay reservas ni ventas.

**Independent Test**: POST `/api/eventos` con JSON válido → 201 con evento creado + UUID. Verificar en MongoDB que documento existe.

**Acceptance Scenarios**:
1. **Given** JSON válido con nombre, estado, aforo_total, entradas_disponibles, precios[], ubicacion, **When** POST `/api/eventos`, **Then** 201 con evento_id, creado_en
2. **Given** aforo_total < entradas_disponibles, **When** POST `/api/eventos`, **Then** 422 Validation Error
3. **Given** entradas_disponibles > aforo_total, **When** POST `/api/eventos`, **Then** 422 Validation Error
3. **Given** precio negativo en precios[], **When** POST `/api/eventos`, **Then** 422 Validation Error
4. **Given** estado no válido, **When** POST `/api/eventos`, **Then** 422 Validation Error

---

### User Story 2 - Obtener Evento por ID (Priority: P1)
Consultar información completa de un evento por su UUID.

**Why this priority**: Requerido por Reservas Service para validar existencia y aforo en SAGA.

**Independent Test**: GET `/api/eventos/{evento_id}` → 200 con evento completo. Testable sin otros servicios.

**Acceptance Scenarios**:
1. **Given** Evento existe, **When** GET `/api/eventos/{evento_id}`, **Then** 200 con todos los campos + precios[]
2. **Given** Evento no existe, **When** GET `/api/eventos/{evento_id}`, **Then** 404 Not Found
3. **Given** evento_id formato UUID inválido, **When** GET `/api/eventos/{evento_id}`, **Then** 422 Validation Error

---

### User Story 3 - Health Check (Priority: P1)
Verificar disponibilidad del servicio y conectividad a MongoDB.

**Why this priority**: Requerido por orquestadores (Kubernetes, Docker Compose) y otros servicios para validar disponibilidad.

**Independent Test**: GET `/health` → 200 con estado de MongoDB. Testable sin otros servicios.

**Acceptance Scenarios**:
1. **Given** MongoDB disponible, **When** GET `/health`, **Then** 200 con `{"status":"healthy","checks":{"mongodb":"ok"},"timestamp":"..."}`
2. **Given** MongoDB con latencia alta, **When** GET `/health`, **Then** 200 con `{"status":"degraded","checks":{"mongodb":"slow"},"timestamp":"..."}`
3. **Given** MongoDB caído, **When** GET `/health`, **Then** 503 Service Unavailable con `{"status":"unhealthy","checks":{"mongodb":"down"},"timestamp":"..."}`

---

### Edge Cases
- Creación de evento con aforo_total = 0: 422 Validation Error
- Creación de evento con entradas_disponibles = aforo_total: Válido (evento lleno al crear)
- Consulta de evento inexistente: Retorna 404 con error code NOT_FOUND
- Health check con MongoDB lento (>100ms): Retorna estado degraded
- Health check con MongoDB caído: Retorna 503 unhealthy
- Precio 0 en precios[]: Válido (evento gratis)
- Categoría duplicada en precios[]: 422 Validation Error
- Evento con estado "cancelado": No disponible para reservas

## Requirements

### Functional Requirements

- **EC-FR-001**: System MUST crear evento con validación de aforo_total >= entradas_disponibles >= 0
- **EC-FR-002**: System MUST validar precios[] con categoria única, precio >= 0, disponibles >= 0
- **EC-FR-003**: System MUST validar estado en enum: borrador, publicado, cancelado, finalizado
- **EC-FR-004**: System MUST validar ubicacion con ciudad y pais obligatorios
- **EC-FR-005**: System MUST retornar evento por UUID con todos los campos + precios[]
- **EC-FR-006**: System MUST responder health check en `/health` con latencia < 10ms (p99), verificando conectividad MongoDB

### Key Entities

- **Evento**: Entidad principal con nombre, estado, aforo, precios por categoría, ubicación
  - Atributos: evento_id (UUID), nombre (string), estado (enum: borrador, publicado, cancelado, finalizado), aforo_total (int >= 0), entradas_disponibles (int >= 0), precios[] (array de objetos), ubicacion (objeto), creado_en (datetime), actualizado_en (datetime)

- **PrecioCategoria**: Subdocumento con categoria, precio, disponibles
  - Atributos: categoria (string, unique dentro del evento), precio (decimal >= 0), disponibles (int >= 0)

- **Ubicacion**: Subdocumento con ciudad, pais, direccion opcional
  - Atributos: ciudad (string), pais (string), direccion (string, opcional)

## Success Criteria

### Measurable Outcomes

- **EC-SC-001**: Crear evento < 100ms (p95) bajo carga normal
- **EC-SC-002**: Obtener evento < 50ms (p95)
- **EC-SC-003**: Health check < 10ms (p99) verificando MongoDB
- **EC-SC-004**: 0 eventos con aforo_total < entradas_disponibles (validación BD)
- **EC-SC-005**: Health check detecta MongoDB caído en < 5s y retorna 503

## Assumptions

- Organizadores tienen conectividad estable para operaciones CRUD
- MongoDB replica set disponible (read preference primary para writes, secondaryPreferred para reads)
- No autenticación/autorización en esta versión (scope MVP)
- Estados de evento: borrador, publicado, cancelado, finalizado
- Precios en moneda local (sin conversión de moneda en MVP)
- Capacidad de evento inmutable tras creación (solo entradas_disponibles cambia)
- No autenticación/autorización en esta versión (scope MVP)

## API Specification

### Endpoints

#### POST /api/eventos
Crear nuevo evento.

**Request Body**:
```json
{
  "nombre": "Concierto Rock 2026",
  "estado": "publicado",
  "aforo_total": 5000,
  "entradas_disponibles": 5000,
  "precios": [
    {"categoria": "VIP", "precio": 15000.00, "disponibles": 100},
    {"categoria": "General", "precio": 5000.00, "disponibles": 4900}
  ],
  "ubicacion": {
    "ciudad": "Buenos Aires",
    "pais": "Argentina",
    "direccion": "Estadio Luna Park"
  }
}
```

**Response 201**:
```json
{
  "evento_id": "uuid-v4",
  "nombre": "Concierto Rock 2026",
  "estado": "publicado",
  "aforo_total": 5000,
  "entradas_disponibles": 5000,
  "precios": [
    {"categoria": "VIP", "precio": 15000.00, "disponibles": 100},
    {"categoria": "General", "precio": 5000.00, "disponibles": 4900}
  ],
  "ubicacion": {
    "ciudad": "Buenos Aires",
    "pais": "Argentina",
    "direccion": "Estadio Luna Park"
  },
  "creado_en": "2026-09-23T10:00:00.000Z",
  "actualizado_en": "2026-09-23T10:00:00.000Z"
}
```

**Error Responses**:
- 422 Validation Error: aforo_total < entradas_disponibles, precio negativo, categoria duplicada, estado inválido, campos faltantes

#### GET /api/eventos/{evento_id}
Obtener evento por ID.

**Response 200**:
```json
{
  "evento_id": "uuid-v4",
  "nombre": "Concierto Rock 2026",
  "estado": "publicado",
  "aforo_total": 5000,
  "entradas_disponibles": 5000,
  "precios": [
    {"categoria": "VIP", "precio": 15000.00, "disponibles": 100},
    {"categoria": "General", "precio": 5000.00, "disponibles": 4900}
  ],
  "ubicacion": {
    "ciudad": "Buenos Aires",
    "pais": "Argentina",
    "direccion": "Estadio Luna Park"
  },
  "creado_en": "2026-09-23T10:00:00.000Z",
  "actualizado_en": "2026-09-23T10:00:00.000Z"
}
```

**Error Responses**:
- 404 Not Found: `{"type":".../not-found","title":"Not Found","status":404,"detail":"Evento no encontrado","instance":"/api/eventos/{id}"}`
- 422 Validation Error: UUID inválido

#### GET /health
Health check del servicio.

**Response 200 (healthy)**:
```json
{
  "status": "healthy",
  "checks": {
    "mongodb": "ok"
  },
  "timestamp": "2026-09-23T10:00:00.000Z"
}
```

**Response 200 (degraded)**:
```json
{
  "status": "degraded",
  "checks": {
    "mongodb": "slow"
  },
  "timestamp": "2026-09-23T10:00:00.000Z"
}
```

**Response 503 (unhealthy)**:
```json
{
  "status": "unhealthy",
  "checks": {
    "mongodb": "down"
  },
  "timestamp": "2026-09-23T10:00:00.000Z"
}
```

### Error Response Format (RFC 7807)

Todos los endpoints retornan errores en formato RFC 7807 (Problem Details):

```json
{
  "type": "https://eventflow.example.com/errors/{error-code}",
  "title": "Human-readable title",
  "status": 422,
  "detail": "Specific error description",
  "instance": "/api/eventos",
  "correlation_id": "uuid-v4"
}
```

| HTTP Status | Error Code | Title | Cuándo |
|-------------|------------|-------|--------|
| 400 | `VALIDATION_ERROR` | Validation Error | JSON inválido, campos faltantes, tipos incorrectos |
| 404 | `NOT_FOUND` | Not Found | Evento no existe (GET por ID) |
| 409 | `DUPLICATE_EVENT` | Conflict | Evento duplicado (si se implementa unicidad por nombre) |
| 422 | `VALIDATION_ERROR` | Unprocessable Entity | aforo_total < entradas_disponibles, precio negativo, categoria duplicada, estado inválido, campos faltantes |
| 500 | `INTERNAL_ERROR` | Internal Server Error | Fallo BD, error inesperado |
| 503 | `SERVICE_UNAVAILABLE` | Service Unavailable | MongoDB down |

**Headers de respuesta**: `X-Correlation-ID` (UUID) en todas las respuestas para tracing distribuido.

### Implementation Requirements
- All endpoints MUST return errors in RFC 7807 format exactly as specified
- `correlation_id` in error response MUST match `X-Correlation-ID` header
- `instance` field MUST be the request path (e.g., `/api/eventos`)
- `type` URI MUST use `https://eventflow.example.com/errors/{error-code}` pattern

## Health Check States

| State | Criteria | Response |
|-------|----------|----------|
| `healthy` | MongoDB ping OK, latencia < 50ms | `{"status":"healthy","checks":{"mongodb":"ok"},"timestamp":"..."}` |
| `degraded` | MongoDB ping OK, latencia 50-500ms | `{"status":"degraded","checks":{"mongodb":"slow"},"timestamp":"..."}` |
| `unhealthy` | MongoDB ping failed, timeout, o conexión rechazada | `{"status":"unhealthy","checks":{"mongodb":"down"},"timestamp":"..."}` HTTP 503 |

### Health Check Implementation
- Timeout: 2 segundos para ping MongoDB
- Latencia medida con `ping` command
- Sin dependencias externas (solo MongoDB)

## Data Model

### Evento Collection (MongoDB)

```javascript
{
  "_id": UUID("..."),           // evento_id (PK)
  "nombre": "Concierto Rock 2026",
  "estado": "publicado",        // enum: borrador, publicado, cancelado, finalizado
  "aforo_total": 5000,          // int >= 0
  "entradas_disponibles": 5000, // int >= 0, <= aforo_total
  "precios": [                  // array de objetos
    {"categoria": "VIP", "precio": 15000.00, "disponibles": 100},
    {"categoria": "General", "precio": 5000.00, "disponibles": 4900}
  ],
  "ubicacion": {
    "ciudad": "Buenos Aires",
    "pais": "Argentina",
    "direccion": "Estadio Luna Park"
  },
  "creado_en": ISODate("..."),
  "actualizado_en": ISODate("...")
}
```

### Indexes
- `_id` (default)
- `nombre` (para búsquedas)
- `estado` (para filtros)
- `creado_en` (para queries temporales)

### Validaciones de Dominio

| Campo | Validación |
|-------|------------|
| nombre | String 1-200 chars, no vacío |
| estado | Enum: borrador, publicado, cancelado, finalizado |
| aforo_total | Int >= 0 |
| entradas_disponibles | Int >= 0, <= aforo_total |
| precios[] | Array no vacío, categorias únicas |
| precio | Decimal >= 0 |
| disponibles | Int >= 0 |
| ubicacion.ciudad | String 1-100 chars, requerido |
| ubicacion.pais | String 1-100 chars, requerido |
| ubicacion.direccion | String opcional, max 500 chars |

### Validaciones de Precios
- Array `precios` no puede estar vacío
- Cada categoria debe ser única dentro del evento
- `precio` >= 0 (0 = evento gratis)
- `disponibles` >= 0
- Suma de `disponibles` en todas las categorías <= `entradas_disponibles`

## Structured Logging Schema (Mandatory per Constitution Principle IV)

```json
{
  "timestamp": "2026-09-23T10:00:00.000Z",
  "level": "INFO|WARN|ERROR|DEBUG",
  "service": "eventos-service",
  "correlation_id": "uuid-v4",
  "trace_id": "uuid-v4",
  "span_id": "uuid-v4",
  "message": "Human readable message",
  "context": {
    "evento_id": "uuid|optional",
    "operation": "create_event|get_event|health_check",
    "duration_ms": 45,
    "additional_fields": "..."
  }
}
```

**Reglas**:
- `correlation_id`: Propagado desde request entrante (header `X-Correlation-ID`) o generado al inicio
- `trace_id`: Igual a `correlation_id` para tracing distribuido
- `span_id`: Único por operación hija
- `context.duration_ms`: Latencia de la operación (obligatorio para requests HTTP)
- No PII en logs (email, documento, nombre, apellido) — usar IDs o hashes
- Log level: INFO para requests, WARN para errores recuperables, ERROR para fallos

## API Versioning Strategy

### Version Location
- **URL Path**: `/api/v1/eventos`, `/api/v1/eventos/{id}`, etc.
- **Header**: `Accept: application/vnd.eventflow.v1+json` (optional, for future)

### Versioning Rules
1. **Breaking changes** → New major version (`v2`, `v3`) in URL path
2. **Non-breaking additions** → Same version, backward compatible
3. **Deprecation**: 90-day notice via `Deprecation` header + `Sunset` header
4. **Current version**: `v1` (this specification)

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
2. **Internal**: Use as `correlation_id` in all structured logs
3. **Egress**: Pass `X-Correlation-ID` to ALL downstream HTTP calls
4. **Logging**: `trace_id` = `correlation_id`; `span_id` = new UUID per operation

## Technology Stack (per Constitution)
- **Language**: Python 3.11 (FastAPI, Uvicorn)
- **Database**: MongoDB 7.0 (Motor async driver)
- **Containerization**: Docker + Docker Compose (dev), K8s-ready (prod)
- **Testing**: pytest, pytest-asyncio, httpx for contract tests

## Assumptions
- MongoDB replica set disponible (writes a primary, reads con secondaryPreferred)
- No autenticación/autorización en MVP (scope mínimo)
- Estados de evento: borrador, publicado, cancelado, finalizado
- Precios en moneda local (sin conversión de moneda en MVP)
- Aforo total inmutable tras creación (solo entradas_disponibles cambia via reservas)
- No autenticación/autorización en esta versión (scope MVP)

## Consistency Model
- **Writes**: `majority` + `journal: true` (strong consistency)
- **Reads**: `secondaryPreferred` (eventual consistency aceptable para reads)
- **Max Staleness**: 1 segundo
- **Write Timeout**: 5 segundos

---

*End of Specification*