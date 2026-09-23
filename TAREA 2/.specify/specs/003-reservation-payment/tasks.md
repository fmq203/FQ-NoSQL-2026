---
description: "Task list for Reservation & Payment feature implementation"
---

# Tasks: Reservation & Payment (Reservas Service)

**Input**: Design documents from `.specify/specs/003-reservation-payment/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create `reservas-service/` directory structure per plan.md
- [ ] T002 Create `requirements.txt`: FastAPI, Pydantic, PyMongo, redis, psycopg[binary], sqlalchemy, httpx, python-dotenv, pytest, fakeredis, pytest-asyncio
- [ ] T003 [P] Create `Dockerfile`: Python 3.11, install deps, copy src, expose 8003, healthcheck
- [ ] T004 [P] Create `.env.example`: MONGODB_URI, MONGODB_DB, REDIS_URL, POSTGRESQL_URI, USUARIOS_SERVICE_URL, EVENTOS_SERVICE_URL, SERVICE_PORT
- [ ] T005 [P] Create `pytest.ini`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work until complete

- [ ] T006 Setup MongoDB connection (`src/services/mongo.py`): Motor async, write_concern majority+journal for reservas
- [ ] T007 [P] Create MongoDB indexes on startup: usuario_id+creado_en, evento_id+estado, numero_confirmacion unique, estado+creado_en, TTL 24h para pendiente/fallida
- [ ] T008 [P] Setup Redis connection (`src/services/redis_pago.py`): async redis-py, register Lua scripts (pago + compensación)
- [ ] T009 [P] Setup PostgreSQL connection (`src/services/postgresql.py`): asyncpg pool, prepared statements for event_log inserts
- [ ] T010 [P] Setup HTTP clients (`src/services/http_clients.py`): httpx.AsyncClient para Usuarios (8001) y Eventos (8002) con timeouts, retries 3x
- [ ] T011 [P] Configure structured JSON logging with correlation_id
- [ ] T012 [P] Create Pydantic models (`src/models/reserva.py`): EstadoReserva, MetodoPago enums, ReservaRequest, ReservaResponse, ReservaContext (dataclass para cadena)
- [ ] T013 [P] Create Chain of Responsibility base (`src/chain/handler.py`): Handler abstracto, set_next, ReservaContext dataclass
- [ ] T014 Setup FastAPI app (`src/main.py`): lifespan para todas las conexiones, health check
- [ ] T014b Implement RFC 7807 error response middleware in `src/api/middleware.py`: format all errors per spec, include correlation_id, type URI
- [ ] T014c Configure API versioning in FastAPI: prefix `/api/v1` for all routes, accept header parsing
- [ ] T014d Implement distributed tracing middleware: X-Correlation-ID extraction, propagation, logging
- [ ] T014e Implement circuit breaker for HTTP clients: closed/open/half-open states, threshold 5 failures, 30s half-open
- [ ] T014f Implement Prometheus metrics endpoint `/metrics` in `src/api/metrics.py`:
    - `saga_duration_seconds` histogram (step, status)
    - `saga_total` counter (status)
    - `saga_compensation_total` counter (step)
    - `http_request_duration_seconds` histogram (method, path, status)
    - `db_operation_duration_seconds` histogram (db, operation, status)
    - `circuit_breaker_state` gauge (service, state)
    - `idempotency_hit_total` counter
    - Histogram buckets: 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10
- [ ] T014g Implement Accept header versioning middleware: parse `Accept: application/vnd.eventflow.v1+json`, default to v1
- [ ] T015 Create idempotency helper (`src/utils/idempotency.py`): check reserva_id exists in MongoDB/Redis/PostgreSQL

**Checkpoint**: Foundation ready - SAGA orchestration can begin

---

## Phase 3: User Story 1 - TESTS ONLY (TDD Red Phase)

**Goal**: Write ALL tests for US1, run them, verify they FAIL before any implementation

- [ ] T016 [P] [US1] Contract test: POST `/api/reservar` OpenAPI validation en `tests/contract/test_reservas_openapi.py`
- [ ] T017 [P] [US1] Integration test: SAGA happy path completo en `tests/integration/test_saga_happy_path.py`
  - Setup: usuario existe, evento con aforo
  - Execute: POST /api/reservar
  - Assert: 201, reserva en MongoDB, pago en Redis, 7 eventos en PG, inventario decrementado
- [ ] T018 [P] [US1] Unit test: Lua script pago+decremento atómico en `tests/unit/test_lua_scripts.py`
- [ ] T019 [P] [US1] Performance test: SAGA completa < 500ms p95 (RP-SC-001) in `tests/performance/test_saga_performance.py`
- [ ] T020 [P] [US1] Performance test: P99 < 1s under load (RP-SC-007) in `tests/performance/test_saga_p99.py`
- [ ] T021 [P] [US1] Test: Zero double bookings (RP-SC-002) in `tests/integration/test_double_booking.py`
- [ ] T022 [P] [US1] Test: Zero negative inventory (RP-SC-003) in `tests/integration/test_negative_inventory.py`
- [ ] **CHECKPOINT**: Run `pytest tests/` - ALL US1 tests must FAIL before proceeding to Phase 4

---

## Phase 4: User Story 1 - IMPLEMENTATION (TDD Green Phase)

**Goal**: Make all Phase 3 tests pass

**Chain Handlers (implement in order, each depends on previous - NO parallel):**

- [ ] T023 [US1] Handler 1: `ValidadorDeDatos` en `src/chain/validators.py` - valida UUIDs, cantidad>0, metodo_pago en enum
- [ ] T024 [US1] Handler 2: `ValidadorUsuario` - GET Usuarios Service, verifica usuario existe
- [ ] T025 [US1] Handler 3: `ValidadorEvento` - GET Eventos Service, verifica existe + aforo>=cantidad
- [ ] T026 [US1] Handler 4: `ProcesadorPago` - Ejecuta Lua script `pagar_y_decrementar.lua` en Redis
- [ ] T027 [US1] Handler 5: `ConfirmadorReserva` - INSERT MongoDB reserva con saga_log parcial
- [ ] T028 [US1] Handler 6: `Auditor` - INSERT PostgreSQL event_log (SAGA_COMPLETED + pasos previos)

**Chain Builder & Orchestration:**

- [ ] T031 [US1] `ChainBuilder` en `src/chain/builder.py`: encadena 6 handlers en orden
- [ ] T032 [US1] `SagaOrchestrator` en `src/services/saga_orchestrator.py`: ejecuta cadena, maneja errores, dispara compensaciones
- [ ] T033 [US1] Route handler `POST /api/v1/reservar` en `src/api/routes.py`: genera reserva_id (uuid4), crea ReservaContext, ejecuta orchestrator
- [ ] T034 [US1] Generar `numero_confirmacion`: `CONF-{YYYYMMDD}-{reserva_id[:8].upper()}`
- [ ] T035 [US1] Idempotencia: check reserva_id existe antes de iniciar SAGA
- [ ] T036 [US1] Correlation ID: propagar en logs, HTTP headers, PG event_log
- [ ] **CHECKPOINT**: Run `pytest tests/` - ALL US1 tests must PASS

---

## Phase 5: User Story 2 - TESTS ONLY (TDD Red Phase)

**Goal**: Write ALL tests for US2, run them, verify they FAIL

- [ ] T040 [P] [US2] Integration test: Fallo Paso 5 (MongoDB down) → compensación Redis en `tests/integration/test_saga_compensations.py`
- [ ] T041 [P] [US2] Integration test: Fallo Paso 4 (inventario insuficiente Lua) → 0 cambios
- [ ] T042 [P] [US2] Unit test: Lua compensación `compensar_pago_inventario.lua` en `tests/unit/test_lua_scripts.py`
- [ ] T043 [P] [US2] Test: Compensación 100% success en fallos simulados paso 4-5 (RP-SC-004) in `tests/integration/test_compensation_success.py`
- [ ] **CHECKPOINT**: Run `pytest tests/` - ALL US2 tests must FAIL before proceeding to Phase 6

---

## Phase 6: User Story 2 - IMPLEMENTATION (TDD Green Phase)

**Goal**: Make all Phase 5 tests pass

- [ ] T044 [US2] En `ProcesadorPago`: Lua script maneja rollback interno si DECRBY falla (transacción atómica)
- [ ] T045 [US2] En `ConfirmadorReserva`: try/except en INSERT MongoDB → si falla, ejecutar Lua compensación `compensar_pago_inventario.lua` (INCRBY inventario + DEL pago)
- [ ] T046 [US2] En `SagaOrchestrator`: catch exceptions por paso, ejecutar compensaciones en orden inverso (5→4)
- [ ] T047 [US2] Registrar eventos compensación en PG: `COMPENSACION_EJECUTADA` con paso y acción
- [ ] T048 [US2] Fallo Paso 6 (PostgreSQL): Log warning ONLY, NO compensación (reserva ya confirmada)
- [ ] **CHECKPOINT**: Run `pytest tests/` - ALL US2 tests must PASS

---

## Phase 7: User Story 3 - TESTS ONLY (TDD Red Phase)

**Goal**: Write ALL handler unit tests, run them, verify they FAIL

- [ ] T049 [P] [US3] Unit tests each handler en `tests/unit/test_handlers.py`:
  - ValidadorDeDatos: cantidad=0 → error, cantidad>0 → pass
  - ValidadorUsuario: usuario existe → pass, no existe → 404
  - ValidadorEvento: aforo ok → pass, insuficiente → 409
  - ProcesadorPago: mock Redis, verificar Lua llamado
  - ConfirmadorReserva: mock MongoDB, verificar insert
  - Auditor: mock PG, verificar insert event_log
- [ ] **CHECKPOINT**: Run `pytest tests/unit/test_handlers.py` - ALL tests must FAIL before proceeding to Phase 8

---

## Phase 8: User Story 3 - IMPLEMENTATION (TDD Green Phase)

**Goal**: Make all Phase 7 tests pass

- [ ] T050 [US3] Asegurar handlers sin side effects en `__init__` (solo config)
- [ ] T051 [US3] Dependency injection: handlers reciben clientes (http, redis, mongo, pg) por constructor
- [ ] T052 [US3] ReservaContext inmutable entre handlers (dataclass frozen o copy)
- [ ] **CHECKPOINT**: Run `pytest tests/unit/test_handlers.py` - ALL tests must PASS

## Phase 9: User Story 4 - TESTS ONLY (TDD Red Phase)

**Goal**: Write ALL tests for US4, run them, verify they FAIL

- [ ] T053 [P] [US4] Integration test: Verificar 7 eventos ordenados en PG tras reserva exitosa
- [ ] T054 [P] [US4] Integration test: Verificar SAGA_FAILED + COMPENSACION en PG tras fallo
- [ ] T055 [P] [US4] Unit test: Query analítica `ventas_por_evento` retorna agregados correctos
- [ ] T056 [P] [US4] Integration test: Verificar TODOS los event types (SAGA_STARTED, USUARIO_VALIDADO, EVENTO_VALIDADO, PAGO_PROCESADO, INVENTARIO_DECREMENTADO, RESERVA_CONFIRMADA, SAGA_COMPLETED, SAGA_FAILED, COMPENSACION_EJECUTADA) en `tests/integration/test_all_event_types.py`
- [ ] T057 [P] [US4] Test: Audit log 100% completo (RP-SC-005) in `tests/integration/test_audit_completeness.py`
- [ ] T058 [P] [US4] Test: SAGA success rate > 99.9% measurement (RP-SC-006) in `tests/performance/test_saga_success_rate.py`
- [ ] **CHECKPOINT**: Run `pytest tests/` - ALL US4 tests must FAIL before proceeding to Phase 10

---

## Phase 10: User Story 4 - IMPLEMENTATION (TDD Green Phase)

**Goal**: Make all Phase 9 tests pass

- [ ] T059 [US4] En `Auditor`: insert event_log por cada paso SAGA (no solo al final)
  - SAGA_STARTED, USUARIO_VALIDADO, EVENTO_VALIDADO, PAGO_PROCESADO, INVENTARIO_DECREMENTADO, RESERVA_CONFIRMADA, SAGA_COMPLETED
- [ ] T060 [US4] Payloads JSONB completos con todos los datos relevantes
- [ ] T061 [US4] Metadata: correlation_id, service name, timestamp
- [ ] T062 [US4] Vista materializada / query analítica: `ventas_por_evento`, `tasa_exito_saga`, `compensaciones_por_tipo` (ver plan.md SQL)
- [ ] T063 [US4] Particionamiento mensual event_log (opcional, activar si >10M eventos/mes o latencia analítica >500ms)
- [ ] **CHECKPOINT**: Run `pytest tests/` - ALL US4 tests must PASS

## Phase 11: Polish & Cross-Cutting

- [ ] T064 [P] OpenAPI descriptions + examples + error responses
- [ ] T065 [P] Quickstart validation: docker compose up full stack, test SAGA end-to-end
- [ ] T066 Code cleanup: type hints, remove unused, docstrings
- [ ] T067 [P] Load test: 100 req/s concurrentes, verificar 0 doble ventas, 0 inventario negativo
- [ ] T068 Circuit breaker verification: test closed/open/half-open transitions
- [ ] T069 Security: validación estricta inputs, no PII en logs, correlation_id tracking
- [ ] T071 [P] Health check three-state per dependency: healthy/degraded/unhealthy
- [ ] T072 [P] Docker build verification: `docker compose build reservas-service` succeeds, no critical vulnerabilities
- [ ] T073 [P] Dependency vulnerability scan: `pip-audit` or `safety` check, zero critical/high
- [ ] T074 [P] Idempotency behavior verification: same reserva_id returns 200 with existing reservation
- [ ] T075 Verify all contract/integration/unit tests pass

---

## Dependencies & Execution Order

### Phase Dependencies
- Setup (1) → Foundational (2) → US1 Tests (3) → US1 Impl (4) → US2 Tests (5) → US2 Impl (6) → US3 Tests (7) → US3 Impl (8) → US4 Tests (9) → US4 Impl (10) → Polish (11)
- Polish (Phase 11): Depends on all stories complete (T064-T075)

### Within Each User Story
- Tests FIRST (must fail) → Implementation
- Handlers sequential: 1→2→3→4→5→6
- Chain builder after all handlers
- Orchestrator after chain builder

### Parallel Opportunities
- All Setup [P] parallel
- All Foundational [P] parallel (different files: mongo, redis, pg, http, models, chain base)
- All Tests [P] for each story parallel
- Handler unit tests [P] parallel

---

## Implementation Strategy

### MVP First (US1 + US2 Only)
1. Setup + Foundational
2. US1: Implement 6 handlers + chain + orchestrator + route
3. US2: Add compensations in handlers 4-5 + orchestrator error handling
4. **STOP and VALIDATE**: Test SAGA happy path + compensation MongoDB failure
5. Deploy/demo MVP

### Incremental Delivery
1. Add US3: Unit tests per handler (refactor confidence)
2. Add US4: Full event sourcing per step + analytics queries
3. Each layer adds observability/compliance without breaking SAGA

---

## Critical Technical Notes

1. **Lua Scripts**: Register on startup, not per-request. Atomicity guaranteed by Redis single-threaded.
2. **Compensación Orden**: Fallo paso N → compensar N-1, N-2, ..., 4 (solo pasos mutantes)
3. **Idempotencia**: `reserva_id` = clave. Check MongoDB `_id`, Redis `pago:{id}`, PG `aggregate_id` antes de iniciar.
4. **Correlation ID**: Generar al inicio (uuid4), propagar en: logs, HTTP headers X-Correlation-ID, PG event_log.correlation_id
5. **Timeouts**: HTTP clients 5s timeout, retry 3x con backoff 0.5s, 1s, 2s. Redis 1s. PG 3s.
6. **Event Log**: Insert por paso (no batch) para debugging granular. SAGA_COMPLETED al final.

---

## Phase 12: Convergence & Gap Closure

**Purpose**: Close gaps between specification, plan, tasks, and implementation identified during convergence analysis.

### Critical - Missing Core Components

- [ ] T076 [US1] Implement `SagaOrchestrator` in `src/services/saga_orchestrator.py`: execute chain, handle errors, trigger compensations per `plan.md:T032`
- [ ] T077 [US1] Implement contract test: POST `/api/v1/reservar` OpenAPI validation in `tests/contract/test_reservas_openapi.py`
- [ ] T078 [US1] Implement integration test: SAGA happy path completo in `tests/integration/test_saga_happy_path.py`
- [ ] T079 [US1] Implement unit test: Lua script pago+decremento atómico in `tests/unit/test_lua_scripts.py`
- [ ] T080 [US1] Implement performance test: SAGA < 500ms p95 (RP-SC-001) in `tests/performance/test_saga_performance.py`
- [ ] T081 [US1] Implement performance test: P99 < 1s under load (RP-SC-007) in `tests/performance/test_saga_p99.py`
- [ ] T082 [US1] Implement test: Zero double bookings (RP-SC-002) in `tests/integration/test_double_booking.py`
- [ ] T083 [US1] Implement test: Zero negative inventory (RP-SC-003) in `tests/integration/test_negative_inventory.py`

### Critical - US2 Compensations Tests

- [ ] T084 [US2] Integration test: Fallo Paso 5 (MongoDB down) → compensación Redis in `tests/integration/test_saga_compensations.py`
- [ ] T085 [US2] Integration test: Fallo Paso 4 (Lua) → 0 cambios
- [ ] T086 [US2] Unit test: Lua compensación `compensar_pago_inventario.lua` in `tests/unit/test_lua_scripts.py`
- [ ] T087 [US2] Test: Compensación 100% success (RP-SC-004) in `tests/integration/test_compensation_success.py`

### Critical - US3 Chain Testing

- [ ] T088 [US3] Unit tests each handler in `tests/unit/test_handlers.py`

### Critical - US4 Event Sourcing Tests

- [ ] T089 [US4] Integration test: 7 eventos ordenados en PG tras reserva exitosa
- [ ] T090 [US4] Integration test: SAGA_FAILED + COMPENSACION en PG tras fallo
- [ ] T091 [US4] Unit test: Query analítica `ventas_por_evento` retorna agregados correctos
- [ ] T092 [US4] Integration test: TODOS los event types in `tests/integration/test_all_event_types.py`
- [ ] T093 [US4] Test: Audit log 100% completo (RP-SC-005) in `tests/integration/test_audit_completeness.py`
- [ ] T094 [US4] Test: SAGA success rate > 99.9% (RP-SC-006) in `tests/performance/test_saga_success_rate.py`

### High - Missing SQL Views & Partitioning

- [ ] T095 [US4] Create SQL view `ventas_por_evento` in PostgreSQL `init_pg_schema()`
- [ ] T096 [US4] Create SQL view `tasa_exito_saga` in PostgreSQL `init_pg_schema()`
- [ ] T097 [US4] Create SQL view `compensaciones_por_tipo` in PostgreSQL `init_pg_schema()`
- [ ] T098 [US4] Create GIN index `idx_event_log_payload_gin` on `event_log.payload`
- [ ] T099 [US4] Implement monthly partitioning activation logic for `event_log`

### High - Health Check & Circuit Breaker

- [ ] T100 [US1] Add circuit breaker state transition tests (closed→open→half-open→closed)
- [ ] T101 [US1] Add HTTP client timeout to health check timeouts table
- [ ] T102 [US1] Add `degraded` state for HTTP clients in health check
- [ ] T103 [US1] Add `half-open` state to circuit breaker health check

### High - OpenAPI & Documentation

- [ ] T104 [US1] Fix OpenAPI contract: add all error responses to POST `/api/v1/reservar`
- [ ] T105 [US1] Add OpenAPI examples for request/response bodies
- [ ] T106 [US1] Add GET `/api/v1/reservar/{reserva_id}` 404 response to OpenAPI
- [ ] T107 [US1] Add GET `/api/v1/reservar` 200 response with array schema
- [ ] T108 [US1] Document RFC 7807 error response format in OpenAPI

### High - Test Infrastructure Fixes

- [ ] T109 [US1] Fix idempotency test: resolve "Event loop is closed" error
- [ ] T110 [US1] Fix Lua script test: resolve "Event loop is closed" with fakeredis
- [ ] T111 [US2] Fix compensation test: resolve "Event loop is closed"
- [ ] T112 [US4] Fix integration test: resolve "Event loop is closed" in saga tests

### High - Missing Core Functionality

- [ ] T113 [US1] Implement double booking prevention under concurrency
- [ ] T114 [US1] Fix Lua script atomicity under concurrency
- [ ] T115 [US4] Implement comprehensive event type verification test
- [ ] T116 [US1] Fix SAGA happy path integration test: complete MongoDB/Redis/PG verification

### Medium - Code Quality & Observability

- [ ] T117 [US1] Fix unused imports in `tests/quality/test_code_quality.py`
- [ ] T118 [US1] Add correlation_id propagation to ALL downstream HTTP calls
- [ ] T119 [US1] Verify all contract/integration/unit tests pass
- [ ] T120 [US1] Security hardening: sanitize PII from logs
- [ ] T121 [US1] Quickstart validation: docker compose up full stack, test SAGA end-to-end
- [ ] T122 [US1] Load test: 100 req/s concurrent, verify 0 double ventas, 0 inventario negativo
- [ ] T123 [US1] Docker build verification test
- [ ] T124 [US1] Dependency vulnerability scan test (`pip-audit`/`safety`)
- [ ] T125 [US2] Implement compensation handler for step 4 in `SagaOrchestrator`
- [ ] T126 [US2] Verify step 5 compensation: INCRBY inventory + DEL payment executed correctly
- [ ] T127 [US4] Add PostgreSQL event_log correlation_id index verification
- [ ] T128 [US4] Implement SAGA_STARTED event emission at SAGA start
- [ ] T129 [US4] Implement SAGA_FAILED event emission on SAGA failure
- [ ] T130 [US4] Verify SQL views created and queryable
- [ ] T131 [US4] Verify GIN index created on event_log.payload

---

## Phase 13: Convergence

**Purpose**: Close remaining gaps between specification, plan, tasks, and implementation identified during convergence analysis.

### Critical - Prometheus Metrics Instrumentation (RP-FR-009, RP-SC-001, RP-SC-007, Constitution IV)

- [ ] T132 [US1] Instrument Prometheus metrics in saga steps: add `record_saga_step_duration`, `record_saga_total`, `record_saga_compensation` calls in `src/chain/validators.py` handlers per `metrics.py` functions
- [ ] T133 [US1] Instrument Prometheus metrics in HTTP layer: add `record_http_request_duration` calls in `src/api/routes.py` and `src/services/http_clients.py` per `metrics.py` functions
- [ ] T134 [US1] Instrument Prometheus metrics in DB operations: add `record_db_operation_duration` calls in `src/services/mongo.py`, `src/services/redis_pago.py`, `src/services/postgresql.py` per `metrics.py` functions
- [ ] T135 [US1] Instrument circuit breaker metrics: add `set_circuit_breaker_state` calls in `src/api/circuit_breaker.py` state transitions per `metrics.py` functions
- [ ] T136 [US1] Instrument idempotency metrics: add `record_idempotency_hit` call in `src/utils/idempotency.py` per `metrics.py` functions

### High - OpenAPI Documentation Compliance (RP-FR-001, Constitution II)

- [ ] T137 [US1] Add OpenAPI request/response examples to POST `/api/v1/reservar` in `src/api/routes.py`
- [ ] T138 [US1] Add OpenAPI 404 response schema for GET `/api/v1/reservar/{reserva_id}` in `src/api/routes.py`
- [ ] T139 [US1] Add OpenAPI 200 response with array schema for GET `/api/v1/reservar` in `src/api/routes.py`
- [ ] T140 [US1] Document RFC 7807 error response format in OpenAPI schema (all error codes) in `src/main.py` or `src/api/middleware.py`

### High - PostgreSQL Partitioning Activation (RP-FR-004, RP-FR-005, plan.md:192)

- [ ] T141 [US4] Implement monthly partitioning activation logic for `event_log`: monitor event count and analytical query latency, auto-create partitions when >10M events/month or latency >500ms in `src/services/postgresql.py`

### High - PII Sanitization (Constitution VII, T120)

- [ ] T142 [US1] Add PII sanitization logging filter: remove user data (emails, names, documents) from structured logs, retain only correlation_id and operational fields in `src/services/logging_config.py`

### Medium - Test Infrastructure (T117)

- [ ] T143 [US1] Add `testcontainers` to `requirements.txt` for real integration tests with MongoDB/Redis/PostgreSQL
- [ ] T144 [US1] Add code quality checks (ruff/flake8) and dependency vulnerability scan (pip-audit/safety) to CI pipeline

### Medium - Correlation ID Index Verification (T127)

- [ ] T145 [US4] Add test verifying `idx_event_log_correlation` index exists and is used for correlation_id queries in `tests/integration/test_audit_completeness.py`