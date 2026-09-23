# Feature Specification: Usuarios CRUD Service

**Feature Branch**: `004-usuarios-crud`

**Created**: 2026-09-23

**Status**: Draft

**Input**: User description: "Usuarios Service: CRUD usuarios en MongoDB con health check, modelo: nombre, apellido, email, nro_documento, tipo_documento. Endpoints: POST /api/usuarios, GET /api/usuarios/{id}, GET /health. MongoDB Motor async."

## User Scenarios & Testing

### User Story 1 - Crear Usuario (Priority: P1)
Un administrador o sistema crea un nuevo usuario proporcionando su documento, nombre, apellido, email y tipo de documento.

**Why this priority**: Funcionalidad base - sin usuarios no hay reservas ni eventos.

**Independent Test**: POST `/api/usuarios` con JSON válido → 201 con usuario creado + UUID. Verificar en MongoDB que documento existe con índices únicos en email y nro_documento.

**Acceptance Scenarios**:
1. **Given** JSON válido con tipo_documento, nro_documento, nombre, apellido, email único, **When** POST `/api/usuarios`, **Then** 201 con usuario_id, creado_en
2. **Given** Email ya registrado, **When** POST `/api/usuarios`, **Then** 409 Conflict
3. **Given** Documento ya registrado, **When** POST `/api/usuarios`, **Then** 409 Conflict
4. **Given** Email formato inválido, **When** POST `/api/usuarios`, **Then** 422 Validation Error
5. **Given** Tipo documento no soportado, **When** POST `/api/usuarios`, **Then** 422 Validation Error

---

### User Story 2 - Obtener Usuario por ID (Priority: P1)
Consultar perfil completo de un usuario por su UUID.

**Why this priority**: Requerido por otros servicios (Reservas, Eventos) para validar existencia de usuario.

**Independent Test**: GET `/api/usuarios/{usuario_id}` → 200 con usuario completo. Testable sin otros servicios.

**Acceptance Scenarios**:
1. **Given** Usuario existe, **When** GET `/api/usuarios/{usuario_id}`, **Then** 200 con todos los campos
2. **Given** Usuario no existe, **When** GET `/api/usuarios/{usuario_id}`, **Then** 404 Not Found
3. **Given** usuario_id formato UUID inválido, **When** GET `/api/usuarios/{usuario_id}`, **Then** 422 Validation Error

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
- Creación concurrente de usuario con mismo email: Índice único en BD previene duplicados, segundo request recibe 409
- Creación concurrente de usuario con mismo documento: Índice único en BD previene duplicados, segundo request recibe 409
- Consulta de usuario inexistente: Retorna 404 con error code NOT_FOUND
- Health check con MongoDB lento (>100ms): Retorna estado degraded
- Health check con MongoDB caído: Retorna 503 unhealthy
- Documento con formato inválido según tipo_documento: 422 Validation Error

## Requirements

### Functional Requirements

- **UC-FR-001**: System MUST crear usuario con validación de unicidad (email, nro_documento)
- **UC-FR-002**: System MUST validar formato de email (RFC 5322) y tipo_documento (DNI, CE, PAS, etc.)
- **UC-FR-004**: System MUST retornar usuario por UUID con todos los campos
- **UC-FR-005**: System MUST responder health check en `/health` con latencia < 10ms (p99), verificando conectividad MongoDB
- **UC-FR-006**: System MUST usar índices únicos en email y nro_documento para prevención de duplicados a nivel BD

### Key Entities

- **Usuario**: Identidad principal con documento, nombre, apellido, email, tipo_documento
  - Atributos: usuario_id (UUID), tipo_documento (enum: DNI, CE, PAS, OTRO), nro_documento (string), nombre (string), apellido (string), email (string, unique), creado_en (datetime), actualizado_en (datetime)

## Success Criteria

### Measurable Outcomes

- **UC-SC-001**: Crear usuario < 100ms (p95) bajo carga normal
- **UC-SC-002**: Obtener usuario < 50ms (p95) 
- **UC-SC-003**: Health check < 10ms (p99) verificando MongoDB
- **UC-SC-004**: 0 duplicados de email o documento (índices únicos BD)
- **UC-SC-005**: Health check detecta MongoDB caído en < 5s y retorna 503

## Assumptions

- Usuarios tienen conectividad estable para operaciones CRUD
- MongoDB replica set disponible (read preference primary para writes, secondaryPreferred para reads)
- No autenticación/autorización en esta versión (scope MVP)
- Tipos de documento soportados: DNI (Argentina), CE (Extranjero), PAS (Pasaporte), OTRO
- No soft deletes en MVP (eliminación física si se requiere)
- No autenticación/autorización en esta versión (scope MVP)

## API Specification

### Endpoints

#### POST /api/usuarios
Crear nuevo usuario.

**Request Body**:
```json
{
  "tipo_documento": "DNI",
  "nro_documento": "12345678",
  "nombre": "Juan",
  "apellido": "Perez",
  "email": "juan.perez@example.com"
}
```

**Response 201**:
```json
{
  "usuario_id": "uuid-v4",
  "tipo_documento": "DNI",
  "nro_documento": "12345678",
  "nombre": "Juan",
  "apellido": "Perez",
  "email": "juan.perez@example.com",
  "creado_en": "2026-09-23T10:00:00.000Z",
  "actualizado_en": "2026-09-23T10:00:00.000Z"
}
```

**Error Responses**:
- 409 Conflict: `{"type":".../duplicate-email","title":"Conflict","status":409,"detail":"Email ya registrado","instance":"/api/usuarios"}`
- 409 Conflict: `{"type":".../duplicate-document","title":"Conflict","status":409,"detail":"Documento ya registrado","instance":"/api/usuarios"}`
- 422 Validation Error: Email inválido, tipo_documento no soportado, campos faltantes

#### GET /api/usuarios/{usuario_id}
Obtener usuario por ID.

**Response 200**:
```json
{
  "usuario_id": "uuid-v4",
  "tipo_documento": "DNI",
  "nro_documento": "12345678",
  "nombre": "Juan",
  "apellido": "Perez",
  "email": "juan.perez@example.com",
  "creado_en": "2026-09-23T10:00:00.000Z",
  "actualizado_en": "2026-09-23T10:00:00.000Z"
}
```

**Error Responses**:
- 404 Not Found: `{"type":".../not-found","title":"Not Found","status":404,"detail":"Usuario no encontrado","instance":"/api/usuarios/{id}"}`
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
  "status": 409,
  "detail": "Specific error description",
  "instance": "/api/usuarios",
  "correlation_id": "uuid-v4"
}
```

| HTTP Status | Error Code | Title | Cuándo |
|-------------|------------|-------|--------|
| 400 | `VALIDATION_ERROR` | Validation Error | JSON inválido, campos faltantes, tipos incorrectos |
| 404 | `NOT_FOUND` | Not Found | Usuario no existe (GET por ID) |
| 409 | `DUPLICATE_EMAIL` | Conflict | Email ya registrado (POST /api/usuarios) |
| 409 | `DUPLICATE_DOCUMENT` | Conflict | Documento ya registrado (POST /api/usuarios) |
| 422 | `VALIDATION_ERROR` | Unprocessable Entity | Email inválido, tipo_documento no soportado, formato documento inválido |
| 500 | `INTERNAL_ERROR` | Internal Server Error | Fallo BD, error inesperado |
| 503 | `SERVICE_UNAVAILABLE` | Service Unavailable | MongoDB down |

**Headers de respuesta**: `X-Correlation-ID` (UUID) en todas las respuestas para tracing distribuido.

### Implementation Requirements
- All endpoints MUST return errors in RFC 7807 format exactly as specified
- `correlation_id` in error response MUST match `X-Correlation-ID` header
- `instance` field MUST be the request path (e.g., `/api/usuarios`)
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

### Usuario Collection (MongoDB)

```javascript
{
  "_id": UUID("..."),           // usuario_id (PK)
  "tipo_documento": "DNI",      // enum: DNI, CE, PAS, OTRO
  "nro_documento": "12345678",  // string, unique index
  "nombre": "Juan",
  "apellido": "Perez",
  "email": "juan@example.com",  // unique index
  "creado_en": ISODate("..."),
  "actualizado_en": ISODate("...")
}
```

### Indexes
- `_id` (default)
- `email` (unique)
- `nro_documento` (unique)
- `creado_en` (para queries temporales)

### Validaciones de Dominio

| Campo | Validación |
|-------|------------|
| email | RFC 5322 regex, unique |
| nro_documento | Alfanumérico, 7-12 chars, unique |
| tipo_documento | Enum: DNI, CE, PAS, OTRO |
| nombre | String 1-100 chars, no vacío |
| apellido | String 1-100 chars, no vacío |
| email | Formato válido, longitud ≤ 254 |

### Conflict Resolution (Concurrent Creation)
- **Strategy**: Database-level unique indexes (email, nro_documento)
- **Behavior**: Second writer receives 409 Conflict with error code `DUPLICATE_EMAIL` or `DUPLICATE_DOCUMENT`
- **No application-level retry** — caller handles 409

## Structured Logging Schema (Mandatory per Constitution Principle IV)

Todos los servicios DEBEN emitir logs en formato JSON:

```json
{
  "timestamp": "2026-09-23T10:00:00.000Z",
  "level": "INFO|WARN|ERROR|DEBUG",
  "service": "usuarios-service",
  "correlation_id": "uuid-v4",
  "trace_id": "uuid-v4",
  "span_id": "uuid-v4",
  "message": "Human readable message",
  "context": {
    "user_id": "uuid|optional",
    "operation": "create_user|get_user|health_check",
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
- **URL Path**: `/api/v1/usuarios`, `/api/v1/usuarios/{id}`, etc.
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
- Tipos de documento: DNI, CE, PAS, OTRO
- Salt de anonimización configurable via variable de entorno (para futuras exportaciones)
- No autenticación/autorización en esta versión (scope MVP)
- Conectividad estable entre servicios

## Consistency Model
- **Writes**: `majority` + `journal: true` (strong consistency)
- **Reads**: `secondaryPreferred` (eventual consistency aceptable para reads)
- **Max Staleness**: 1 segundo
- **Write Timeout**: 5 segundos

---

*End of Specification*