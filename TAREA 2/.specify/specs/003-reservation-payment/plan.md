# Implementation Plan: Reservation & Payment (Reservas Service)

**Branch**: `003-reservation-payment` | **Date**: 2026-09-20 | **Spec**: .specify/specs/003-reservation-payment/spec.md

## Summary

Implementar **Reservas & Pagos Service** como **Orquestador SAGA** con **Chain of Responsibility**. Coordina 3 servicios externos + 3 bases de datos. Transacción distribuida con compensaciones automáticas y Event Sourcing en PostgreSQL.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: 
- FastAPI 0.104.0, Uvicorn 0.24.0
- Pydantic 2.x, PyMongo 4.5.0
- Redis 5.0.0 (Lua scripts), asyncpg/psycopg 3.x (PostgreSQL)
- httpx 0.25.0 (async HTTP client para Usuarios/Eventos)
- python-dotenv, SQLAlchemy 2.0 (async)

**Storage**: 
- MongoDB 7.0 (colección `reservas` + saga_log embedded)
- Redis 7.0 (pagos atómicos Lua + inventario contadores)
- PostgreSQL 15 (tabla `event_log` Event Sourcing)

**Testing**: pytest, pytest-asyncio, httpx.AsyncClient, fakeredis, testcontainers para PG

**Target Platform**: Linux container (Docker), puerto 8003

**Performance Goals**: 
- SAGA completa: < 500ms p95, < 1s p99
- 100 req/s concurrentes
- 0 doble ventas, 0 inventario negativo

**Constraints**: 
- Consistencia FUERTE en toda la transacción
- Atomicidad pago+inventario: Redis Lua script (single-threaded)
- Compensaciones automáticas paso 4-5
- Event Sourcing: append-only PostgreSQL
- Idempotencia via reserva_id (UUID v4)

## Constitution Check

- ✅ Microservice Autonomy: Orquestador, owns MongoDB reservas, coordinates others
- ✅ API-First: OpenAPI auto-generated, versioning strategy defined
- ✅ Test-First: Contract + SAGA integration tests
- ✅ Observability: /health, correlation IDs, full audit log, metrics, tracing
- ✅ Polyglot Persistence: 3 DBs justificadas (Redis atomic, Mongo flexible, PG ACID)
- ✅ SAGA Orchestration: Implementado explícitamente with compensations
- ✅ Security/Privacy: No PII en logs, correlation IDs, RFC 7807 errors
- ✅ Simplicity: Chain of Responsibility, no over-engineering

## Requirements Traceability

| Spec Requirement | Plan Section | Tasks |
|------------------|--------------|-------|
| RP-FR-001 | Phase 3-4 (US1) | T023-T028, T031-T033, T036, T076, T078 |
| RP-FR-002 | Phase 3-4, 5-6 (US1, US2) | T018, T026, T044, T079, T110 |
| RP-FR-003 | Phase 5-6 (US2) | T044-T048, T084-T087, T125, T126 |
| RP-FR-004 | Phase 9-10 (US4) | T059-T063, T089-T094, T128, T129 |
| RP-FR-005 | Phase 9-10 (US4) | T059-T063, T095-T099, T130, T131 |
| RP-FR-006 | Phase 4 (US1) | T034 |
| RP-FR-007 | Phase 2, 4 (US1) | T015, T035, T074, T109 |
| RP-FR-008 | Phase 2, 11 (US1) | T014, T071, T100-T103 |
| RP-SC-001 | Performance Goals | T019, T080 |
| RP-SC-002 | Phase 3-4, 12 | T021, T082, T113 |
| RP-SC-003 | Phase 3-4, 12 | T022, T083, T114 |
| RP-SC-004 | Phase 5-6, 12 | T043, T087 |
| RP-SC-005 | Phase 9-10, 12 | T056, T057, T092, T093, T115 |
| RP-SC-006 | Phase 9-10, 12 | T058, T094 |
| RP-SC-007 | Performance Goals | T020, T081 |
| RP-SC-008 | Phase 2, 11 | T014, T071, T101 |

## Project Structure

```
reservas-service/
├── docker-compose.yml          # Local dev stack: MongoDB, Redis, PostgreSQL, Usuarios, Eventos
├── Dockerfile
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── reserva.py           # Pydantic: ReservaRequest, ReservaResponse, ReservaContext
│   │   └── enums.py             # EstadoReserva, MetodoPago
│   ├── chain/
│   │   ├── __init__.py
│   │   ├── handler.py           # Base Handler abstracto + ReservaContext
│   │   ├── validators.py        # 6 handlers: ValidadorDatos, ValidadorUsuario, ValidadorEvento, ProcesadorPago, ConfirmadorReserva, Auditor
│   │   └── builder.py           # Construir cadena encadenada
│   ├── services/
│   │   ├── __init__.py
│   │   ├── mongo.py             # MongoDB connection + indexes
│   │   ├── redis_pago.py        # Redis Lua scripts (pago + compensación)
│   │   ├── postgresql.py        # AsyncPG pool + event_log inserts
│   │   ├── http_clients.py      # httpx.AsyncClient para Usuarios/Eventos
│   │   └── saga_orchestrator.py # Orquestador SAGA: ejecuta cadena, maneja errores, dispara compensaciones
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py            # POST /api/v1/reservar, GET /api/v1/reservar/{id}
│   │   └── middleware.py        # RFC 7807, versioning, tracing, circuit breaker
│   └── utils/
│       ├── __init__.py
│       └── idempotency.py       # Clave idempotencia reserva_id
├── tests/
│   ├── __init__.py
│   ├── contract/
│   │   ├── __init__.py
│   │   └── test_reservas_openapi.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_saga_happy_path.py
│   │   ├── test_saga_compensations.py
│   │   ├── test_chain_of_responsibility.py
│   │   ├── test_double_booking.py
│   │   ├── test_negative_inventory.py
│   │   ├── test_compensation_success.py
│   │   ├── test_all_event_types.py
│   │   └── test_audit_completeness.py
│   ├── performance/
│   │   ├── __init__.py
│   │   ├── test_saga_performance.py
│   │   ├── test_saga_p99.py
│   │   └── test_saga_success_rate.py
│   └── unit/
│       ├── __init__.py
│       ├── test_lua_scripts.py
│       ├── test_handlers.py
│       └── test_idempotency.py
└── pytest.ini
```

## Phase 1: Design

### Data Models

Data models defined inline below. External reference removed.

**MongoDB - Colección `reservas`**:
```javascript
db.reservas.createIndex({ "usuario_id": 1, "creado_en": -1 })
db.reservas.createIndex({ "evento_id": 1, "estado": 1 })
db.reservas.createIndex({ "numero_confirmacion": 1 }, { unique: true })
db.reservas.createIndex({ "estado": 1, "creado_en": -1 })
// TTL 24h para pendiente/fallida
db.reservas.createIndex({ "creado_en": 1 }, { expireAfterSeconds: 86400, partialFilterExpression: { "estado": { "$in": ["pendiente", "fallida"] } } })
```

**Redis - Lua Scripts**:

`pagar_y_decrementar.lua` (Paso 4 SAGA):
```lua
-- KEYS[1]=inventario:evento_id, KEYS[2]=pago:reserva_id
-- ARGV[1]=cantidad, ARGV[2]=reserva_id, ARGV[3]=usuario_id, ARGV[4]=monto, ARGV[5]=metodo_pago
local disponible = tonumber(redis.call('GET', KEYS[1]) or '0')
if disponible < tonumber(ARGV[1]) then return {0, 'INVENTARIO_INSUFICIENTE'} end
redis.call('DECRBY', KEYS[1], ARGV[1])
redis.call('HSET', KEYS[2], 'reserva_id', ARGV[2], 'usuario_id', ARGV[3], 'monto', ARGV[4], 'metodo_pago', ARGV[5], 'estado', 'confirmado', 'timestamp', os.date('!%Y-%m-%dT%H:%M:%SZ'))
redis.call('EXPIRE', KEYS[2], 86400)
return {1, 'OK'}
```

`compensar_pago_inventario.lua` (Rollback paso 5):
```lua
-- KEYS[1]=inventario:evento_id, KEYS[2]=pago:reserva_id, ARGV[1]=cantidad
redis.call('INCRBY', KEYS[1], ARGV[1])
redis.call('DEL', KEYS[2])
return {1, 'COMPENSACION_OK'}
```

**PostgreSQL - Tabla `event_log`**:
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
CREATE INDEX idx_event_log_aggregate ON event_log(aggregate_id);
CREATE INDEX idx_event_log_type ON event_log(event_type);
CREATE INDEX idx_event_log_timestamp ON event_log(timestamp DESC);
CREATE INDEX idx_event_log_correlation ON event_log(correlation_id);
CREATE INDEX idx_event_log_payload_gin ON event_log USING GIN(payload);
```

**Particionamiento mensual (opcional, activar si >10M eventos/mes o latencia analítica >500ms):**
```sql
-- CREATE TABLE event_log_2026_09 PARTITION OF event_log
-- FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
```

**Criterio de activación de particionamiento**: Activar cuando `event_log` supere 10M eventos/mes o latencia de consultas analíticas > 500ms.

### CQRS Read Models / SQL Views (Analítica)

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
```

### Chain of Responsibility Handlers

| Orden | Handler | Responsabilidad | Dependencia Externa |
|-------|---------|-----------------|---------------------|
| 1 | ValidadorDeDatos | Validar UUIDs, cantidad>0, metodo_pago válido | Local |
| 2 | ValidadorUsuario | GET /api/usuarios/{id} | Usuarios Service (HTTP) |
| 3 | ValidadorEvento | GET /api/eventos/{id} + aforo | Eventos Service (HTTP) |
| 4 | ProcesadorPago | Lua Redis: pago + DECRBY inventario | Redis (Lua atómico) |
| 5 | ConfirmadorReserva | INSERT MongoDB reserva + saga_log | MongoDB |
| 6 | Auditor | INSERT PostgreSQL event_log | PostgreSQL |

### Contracts (OpenAPI)

Auto-generado en `/openapi.json`. Endpoint principal:
- POST `/api/v1/reservar` - Inicia SAGA completa

### Quickstart

```bash
cd reservas-service
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Requiere: Usuarios (8001), Eventos (8002), MongoDB, Redis, PostgreSQL
uvicorn src.main:app --reload --port 8003

# Tests (requieren stack completo)
docker compose up -d
pytest -v

# Test SAGA happy path
curl -X POST http://localhost:8003/api/v1/reservar \
  -H "Content-Type: application/json" \
  -d '{"usuario_id":"...", "evento_id":"...", "cantidad":2, "metodo_pago":"tarjeta"}'

# Ver audit log
docker compose exec postgresql psql -U eventflow_user -d eventflow -c "SELECT * FROM event_log ORDER BY timestamp DESC LIMIT 10;"

# Health check (3 estados por dependencia)
curl http://localhost:8003/health
# {"status":"healthy|degraded|unhealthy","checks":{"mongodb":"ok|degraded|down","redis":"ok|degraded|down","postgresql":"ok|degraded|down","usuarios_service":"ok|degraded|down","eventos_service":"ok|degraded|down"},"timestamp":"..."}

# Metrics (Prometheus)
curl http://localhost:8003/metrics
```