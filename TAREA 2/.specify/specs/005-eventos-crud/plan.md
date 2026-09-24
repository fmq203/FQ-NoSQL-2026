# Implementation Plan: Eventos CRUD Service

**Branch**: `005-eventos-crud` | **Date**: 2026-09-23 | **Spec**: [.specify/specs/005-eventos-crud/spec.md](.specify/specs/005-eventos-crud/spec.md)

**Input**: Feature specification from `/specs/005-eventos-crud/spec.md`

## Summary

Implement a FastAPI-based microservice for CRUD operations on Eventos (events) stored in MongoDB using Motor async driver. The service provides three endpoints: POST /api/v1/eventos (create event), GET /api/v1/eventos/{id} (get event by UUID), and GET /health (health check with MongoDB connectivity verification). Follows the EventFlow Constitution principles: microservice autonomy, API-first contract, test-first development, observability by default, and distributed tracing.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: FastAPI 0.109+, Uvicorn 0.27+, Motor 3.3+ (async MongoDB driver), Pydantic 2.5+, Pydantic-Settings 2.1+, httpx 0.26+ (for tests), pytest 7.4+, pytest-asyncio 0.23+

**Storage**: MongoDB 7.0 (Motor async driver, replica set with read preference secondaryPreferred for reads, primary for writes)

**Testing**: pytest, pytest-asyncio, httpx for contract/integration tests

**Target Platform**: Linux server (Docker container)

**Project Type**: Web service (microservice)

**Performance Goals**: 
- Create event < 100ms (p95)
- Get event < 50ms (p95)
- Health check < 50ms (p99) verifying MongoDB

**Constraints**: 
- < 200ms p95 latency for CRUD operations
- Health check timeout: 2 seconds for MongoDB ping
- 80% minimum test coverage on business logic
- RFC 7807 error format compliance
- Structured JSON logging with correlation IDs
- Distributed tracing headers (X-Correlation-ID, X-Trace-ID)
- Metrics exposition (Prometheus/OpenTelemetry) for latency, error rate, throughput per endpoint
- Dependency vulnerability scanning in CI

**Scale/Scope**: 
- Single microservice (eventos-service)
- Event collection with indexes on _id, nombre, estado, creado_en
- No authentication/authorization in MVP

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Microservice Autonomy | ✅ Pass | Independent service, owns Eventos collection |
| II. API-First Contract | ⚠️ Partial | OpenAPI 3.1 from FastAPI; versioned routes (/api/v1/) need implementation; OpenAPI validation task needed |
| III. Test-First (NON-NEGOTIABLE) | ✅ Pass | TDD mandatory, contract → integration → unit |
| IV. Observability by Default | ⚠️ Partial | Structured logging, /health, correlation IDs done; **metrics exposition (Prometheus) missing** |
| V. Polyglot Persistence | ⚠️ Partial | MongoDB justified; `brain/decisions/db-selection.md` not verified |
| VI. SAGA Transactions | ✅ Pass | Not applicable (single service CRUD) |
| VII. Security & Privacy | ⚠️ Partial | No PII in logs, input validation, env vars; **dependency vulnerability scanning missing** |
| VIII. Simplicity & YAGNI | ✅ Pass | Minimal MVP implementation |

Violations to address before implementation:
- Principle II: Add API versioning implementation task + OpenAPI contract validation task
- Principle IV: Add metrics middleware task (Prometheus/OpenTelemetry)
- Principle V: Verify `brain/decisions/db-selection.md` exists
- Principle VII: Add dependency scanning task (pip-audit/safety) in CI

## Project Structure

### Documentation (this feature)

```text
specs/005-eventos-crud/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── openapi.yaml     # OpenAPI 3.1 specification
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
eventos-service/
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Settings via pydantic-settings
│   ├── models/
│   │   ├── __init__.py
│   │   ├── evento.py           # Evento, PrecioCategoria, Ubicacion models
│   │   └── health.py           # Health check models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── mongodb.py          # Motor client, connection management
│   │   ├── evento_service.py   # CRUD operations
│   │   └── health_service.py   # Health check logic
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── eventos.py      # POST /api/v1/eventos, GET /api/v1/eventos/{id}
│   │   │   └── health.py       # GET /health
│   │   └── middleware/
│   │       ├── __init__.py
│   │       ├── correlation.py  # Correlation ID middleware
│   │       ├── logging.py      # Structured logging middleware
│   │       └── metrics.py      # Prometheus metrics middleware
│   └── utils/
│       ├── __init__.py
│       ├── errors.py           # RFC 7807 error handling
│       └── validation.py       # Custom validators
├── tests/
│   ├── __init__.py
│   ├── contract/
│   │   ├── __init__.py
│   │   ├── test_eventos_post.py
│   │   ├── test_eventos_get.py
│   │   └── test_health.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_eventos_crud.py
│   │   └── test_health_integration.py
│   └── unit/
│       ├── __init__.py
│       ├── test_evento_model.py
│       ├── test_evento_service.py
│       └── test_health_service.py
├── Dockerfile
├── docker-compose.yml          # Service-specific (extends root compose)
├── requirements.txt
├── pytest.ini
└── .env.example
```

**Structure Decision**: Using existing eventos-service directory structure at repository root `/home/fqueirolo/TECNOLOGO/NoSQL/TAREA 2/eventos-service/`. This follows the single-project microservice pattern consistent with existing services (usuarios-service, reservas-service). Added `metrics.py` middleware for Principle IV compliance.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | All constitution principles satisfied | N/A |