# Feature Specification: User Management (Usuarios Service)

**Feature Branch**: `001-user-management`

**Created**: 2026-09-20

**Status**: Complete

**Input**: User description: "Gestiona los perfiles de los usuarios y su historial de compras. Debe ser extremadamente rápida y escalable. Se priorizará la disponibilidad y la tolerancia a particiones, aceptando la consistencia eventual."

## User Scenarios & Testing

### User Story 1 - Crear Usuario (Priority: P1)
Un usuario se registra en la plataforma proporcionando su documento, nombre, apellido y email.

**Why this priority**: Funcionalidad base - sin usuarios no hay reservas ni eventos.

**Independent Test**: POST `/api/usuarios` con JSON válido → 201 con usuario creado + UUID + historial vacío. Verificar en MongoDB que documento existe con índices únicos.

**Acceptance Scenarios**:
1. **Given** JSON válido con tipo_documento, nro_documento, nombre, apellido, email único, **When** POST `/api/usuarios`, **Then** 201 con usuario_id, creado_en, historial_compras=[]
2. **Given** Email ya registrado, **When** POST `/api/usuarios`, **Then** 409 Conflict
3. **Given** Documento ya registrado, **When** POST `/api/usuarios`, **Then** 409 Conflict
4. **Given** Email formato inválido, **When** POST `/api/usuarios`, **Then** 422 Validation Error

---

### User Story 2 - Obtener Usuario por ID (Priority: P1)
Consultar perfil completo incluyendo historial de compras.

**Why this priority**: Requerido por Reservas Service para validar usuario en SAGA.

**Independent Test**: GET `/api/usuarios/{usuario_id}` → 200 con usuario + historial_compras[]. Testable sin otros servicios.

**Acceptance Scenarios**:
1. **Given** Usuario existe, **When** GET `/api/usuarios/{usuario_id}`, **Then** 200 con todos los campos + historial_compras
2. **Given** Usuario no existe, **When** GET `/api/usuarios/{usuario_id}`, **Then** 404 Not Found
3. **Given** usuario_id formato UUID inválido, **When** GET `/api/usuarios/{usuario_id}`, **Then** 422 Validation Error

---

### User Story 3 - Listar Usuarios Paginado (Priority: P2)
Listado paginado para administración y debugging.

**Why this priority**: Operación de lectura masiva, debe ser escalable.

**Independent Test**: GET `/api/usuarios?skip=0&limit=10` → 200 con array de usuarios (proyección sin historial_compras para performance).

**Acceptance Scenarios**:
1. **Given** 15 usuarios en BD, **When** GET `/api/usuarios?limit=10`, **Then** 200 con 10 usuarios
2. **Given** skip=10&limit=10, **When** GET, **Then** 200 con siguientes 5 usuarios
3. **Given** Parámetros inválidos (skip negativo), **When** GET, **Then** 422

---

### User Story 4 - Exportar Usuarios Anonimizados GDPR (Priority: P2)
Exportación masiva para análisis con datos personales irreversiblemente anonimizados.

**Why this priority**: Requerimiento legal GDPR, opcional en PDF pero implementado.

**Independent Test**: GET `/api/usuarios/exportar?format=json` → 200 con array de objetos anonimizados (usuario_hash, eventos_comprados, gasto_total). Sin nombre, email, documento.

**Acceptance Scenarios**:
1. **Given** Usuarios con historial, **When** GET `/api/usuarios/exportar`, **Then** 200 con usuario_hash (SHA-256 irreversible), eventos_comprados (count), gasto_total (sum)
2. **Given** Usuario sin compras, **When** Exportar, **Then** eventos_comprados=0, gasto_total=0
3. **Given** format=csv, **When** Exportar, **Then** 200 con CSV válido

---

### Edge Cases
- Usuario con historial muy grande (>50 compras): Solo últimas 50 en embedded, resto archivado
- Concurrent creation mismo email: Último escritor gana con 409 en segundo (DB unique index enforcement)
- Exportación con millones de usuarios: Stream response, no cargar todo en memoria

## Requirements

### Functional Requirements

- **UM-FR-001**: System MUST crear usuario con validación de unicidad (email, documento)
- **UM-FR-002**: System MUST retornar usuario por UUID con historial_compras embedded
- **UM-FR-003**: System MUST listar usuarios con paginación (skip, limit)
- **UM-FR-004**: System MUST exportar usuarios anonimizados (SHA-256 hash + salt)
- **UM-FR-005**: System MUST preservar datos analíticos (eventos_comprados, gasto_total) en exportación
- **UM-FR-006**: System MUST eliminar PII (nombre, apellido, email, documento) en exportación
- **UM-FR-007**: System MUST responder health check en `/health` con latencia < 10ms (p99), ejecutando: (1) MongoDB `ping` command (timeout 2s), (2) Replica set status via `replSetGetStatus` — verify primary exists, calculate max lag across secondaries, (3) Retornar JSON según estado (ver tabla "Health Check States"), (4) Sin dependencias externas (solo MongoDB)

### Key Entities

- **Usuario**: Identidad principal con documento, nombre, email, historial de compras embebido
- **CompraHistorial**: Subdocumento embebido con reserva_id, evento_id, cantidad, precio_total, fecha_compra, estado

## Success Criteria

### Measurable Outcomes

- **UM-SC-001**: Crear usuario < 100ms (p95) bajo carga normal
- **UM-SC-002**: Obtener usuario < 50ms (p95) con read preference secondaryPreferred
- **UM-SC-003**: Listar 1000 usuarios paginado < 200ms
- **UM-SC-004**: Exportar 10k usuarios anonimizados < 2s streaming
- **UM-SC-005**: 0 pérdida de datos en exportación (todos los usuarios representados)
- **UM-SC-006**: Hash irreversible verificado - imposible recuperar email original
- **UM-SC-007**: Health check `/health` < 10ms (p99), verifica MongoDB ping + replica status, retorna estados `healthy`/`degraded`/`unhealthy` según criterios definidos en tabla "Health Check States"

## Assumptions

- Usuarios tienen conectividad estable para registro
- MongoDB replica set disponible para read preference secondaryPreferred
- Salt de anonimización configurable via variable de entorno
- Historial de compras acotado a últimas 50 (política de retención)
- No autenticación/autorización en esta versión (scope MVP)

## Consistency Model Specification

### Read Preference Configuration
- **Default**: `secondaryPreferred` for all GET operations
- **Fallback**: `primary` when no secondary available within 500ms
- **Max Staleness**: 1 second (operations older than 1s routed to primary)
- **Tag Sets**: None (use default replica set topology)

### Write Concern
- **All writes**: `majority` + `journal: true` (strong consistency)
- **Timeout**: 5 seconds

### Health Check States
| State | Criteria | Response |
|-------|----------|----------|
| `healthy` | Primary reachable, replica lag ≤ 1s, all secondaries syncing | `{"status":"healthy","checks":{"mongodb":"ok"},"timestamp":"..."}` |
| `degraded` | Primary reachable, replica lag > 1s OR secondary unavailable | `{"status":"degraded","checks":{"mongodb":"lag"},"timestamp":"..."}` |
| `unhealthy` | Primary unreachable OR write concern failed | `{"status":"unhealthy","checks":{"mongodb":"down"},"timestamp":"..."}` HTTP 503 |

### Conflict Resolution (Concurrent Creation)
- **Strategy**: Database-level unique indexes (email, nro_documento)
- **Behavior**: Second writer receives 409 Conflict with error code `DUPLICATE_EMAIL` or `DUPLICATE_DOCUMENT`
- **No application-level retry** — caller handles 409

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
3. **Egress**: Pass `X-Correlation-ID` to ALL downstream HTTP calls (Eventos, Reservas services)
4. **Logging**: `trace_id` = `correlation_id`; `span_id` = new UUID per operation

## API Versioning Strategy

### Version Location
- **URL Path**: `/api/v1/usuarios`, `/api/v1/usuarios/{id}`, etc.
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

## Error Response Schemas (OpenAPI 3.1)

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
| 422 | `VALIDATION_ERROR` | Unprocessable Entity | Email formato inválido, documento inválido |
| 500 | `INTERNAL_ERROR` | Internal Server Error | Fallo BD, error inesperado |
| 503 | `SERVICE_UNAVAILABLE` | Service Unavailable | MongoDB down, replica set unavailable |

**Headers de respuesta**: `X-Correlation-ID` (UUID) en todas las respuestas para tracing distribuido.

### Implementation Requirements
- All endpoints MUST return errors in RFC 7807 format exactly as specified
- `correlation_id` in error response MUST match `X-Correlation-ID` header
- `instance` field MUST be the request path (e.g., `/api/usuarios`)
- `type` URI MUST use `https://eventflow.example.com/errors/{error-code}` pattern

## Structured Logging Schema (Mandatory per Constitution Principle IV)

Todos los servicios DEBEN emitir logs en formato JSON con los siguientes campos obligatorios:

```json
{
  "timestamp": "2026-09-20T10:00:00.000Z",
  "level": "INFO|WARN|ERROR|DEBUG",
  "service": "usuarios-service",
  "correlation_id": "uuid-v4",
  "trace_id": "uuid-v4",
  "span_id": "uuid-v4",
  "message": "Human readable message",
  "context": {
    "user_id": "uuid|optional",
    "operation": "create_user|get_user|list_users|export_users",
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
- No PII en logs (email, documento, nombre, apellido) — usar hashes o IDs
- Log level: INFO para requests, WARN para errores recuperables, ERROR para fallos