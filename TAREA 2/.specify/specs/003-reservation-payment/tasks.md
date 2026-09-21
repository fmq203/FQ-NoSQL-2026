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
- [ ] T015 Create idempotency helper (`src/utils/idempotency.py`): check reserva_id exists in MongoDB/Redis/PostgreSQL

**Checkpoint**: Foundation ready - SAGA orchestration can begin

---

## Phase 3: User Story 1 - SAGA Completa Happy Path (Priority: P1) 🎯 MVP

**Goal**: POST `/api/reservar` ejecuta 6 pasos SAGA exitosamente: ValidaDatos → Usuario → Evento → PagoRedis → ReservaMongo → AuditPG

**Independent Test**: Request válido → 201 con reserva_id, estado=confirmada, numero_confirmacion. Verificar: MongoDB reserva, Redis pago, PG event_log (7 eventos), inventario decrementado.

### Tests for US1 (Write FIRST, must FAIL)

> **NOTE: TDD mandatory - tests written → fail → then implement**

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

### Implementation for US1

**Chain Handlers (implement in order, each depends on previous):**

- [ ] T023 [P] [US1] Handler 1: `ValidadorDeDatos` en `src/chain/validators.py` - valida UUIDs, cantidad>0, metodo_pago en enum
- [ ] T024 [P] [US1] Handler 2: `ValidadorInventario` - GET Usuarios Service, verifica usuario existe
- [ ] T025 [P] [US1] Handler 3: `ValidadorEvento` - GET Eventos Service, verifica existe + aforo>=cantidad
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

---

## Phase 4: User Story 2 - Compensaciones Automáticas (Priority: P1)

**Goal**: Rollback automático en fallos paso 4 (Lua interno) y paso 5 (MongoDB → compensar Redis)

**Independent Test**: Simular fallo MongoDB → compensación Redis ejecutada (INCRBY + DEL). Fallo Lua → 0 cambios.

### Tests for US2 (MANDATORY)

- [ ] T040 [P] [US2] Integration test: Fallo Paso 5 (MongoDB down) → compensación Redis en `tests/integration/test_saga_compensations.py`
- [ ] T041 [P] [US2] Integration test: Fallo Paso 4 (inventario insuficiente Lua) → 0 cambios
- [ ] T042 [P] [US2] Unit test: Lua compensación `compensar_pago_inventario.lua` en `tests/unit/test_lua_scripts.py`
- [ ] T043 [P] [US2] Test: Compensación 100% success en fallos simulados paso 4-5 (RP-SC-004) in `tests/integration/test_compensation_success.py`

### Implementation for US2

- [ ] T044 [US2] En `ProcesadorPago`: Lua script maneja rollback interno si DECRBY falla (transacción atómica)
- [ ] T045 [US2] En `ConfirmadorReserva`: try/except en INSERT MongoDB → si falla, ejecutar Lua compensación `compensar_pago_inventario.lua` (INCRBY inventario + DEL pago)
- [ ] T046 [US2] En `SagaOrchestrator`: catch exceptions por paso, ejecutar compensaciones en orden inverso (5→4)
- [ ] T047 [US2] Registrar eventos compensación en PG: `COMPENSACION_EJECUTADA` con paso y acción
- [ ] T048 [US2] Fallo Paso 6 (PostgreSQL): Log warning ONLY, NO compensación (reserva ya confirmada)

---

## Phase 5: User Story 3 - Chain of Responsibility Testing (Priority: P1)

**Goal**: Cada handler testeable independientemente, cadena completa integrable

**Independent Test**: Unit test cada handler con ReservaContext mock. Integration test cadena completa.

### Tests for US3 (MANDATORY)

- [ ] T049 [P] [US3] Unit tests each handler en `tests/unit/test_handlers.py`:
  - ValidadorDeDatos: cantidad=0 → error, cantidad>0 → pass
  - ValidadorInventario: usuario existe → pass, no existe → 404
  - ValidadorEvento: aforo ok → pass, insuficiente → 409
  - ProcesadorPago: mock Redis, verificar Lua llamado
  - ConfirmadorReserva: mock MongoDB, verificar insert
  - Auditor: mock PG, verificar insert event_log

### Implementation for US3

- [ ] T050 [US3] Asegurar handlers sin side effects en `__init__` (solo config)
- [ ] T051 [US3] Dependency injection: handlers reciben clientes (http, redis, mongo, pg) por constructor
- [ ] T052 [US3] ReservaContext inmutable entre handlers (dataclass frozen o copy)

---

## Phase 6: User Story 4 - Event Sourcing + CQRS Auditoría (Priority: P2)

**Goal**: Event log completo en PostgreSQL para compliance y analytics

**Independent Test**: Reserva exitosa → 7 eventos en PG ordenados. Fallo → SAGA_FAILED + COMPENSACION. Query analítica ventas funciona.

### Tests for US4 (MANDATORY)

- [ ] T053 [P] [US4] Integration test: Verificar 7 eventos ordenados en PG tras reserva exitosa
- [ ] T054 [P] [US4] Integration test: Verificar SAGA_FAILED + COMPENSACION en PG tras fallo
- [ ] T055 [P] [US4] Unit test: Query analítica `ventas_por_evento` retorna agregados correctos
- [ ] T056 [P] [US4] Integration test: Verificar TODOS los event types (SAGA_STARTED, USUARIO_VALIDADO, EVENTO_VALIDADO, PAGO_PROCESADO, INVENTARIO_DECREMENTADO, RESERVA_CONFIRMADA, SAGA_COMPLETED, SAGA_FAILED, COMPENSACION_EJECUTADA) en `tests/integration/test_all_event_types.py`
- [ ] T057 [P] [US4] Test: Audit log 100% completo (RP-SC-005) in `tests/integration/test_audit_completeness.py`
- [ ] T058 [P] [US4] Test: SAGA success rate > 99.9% measurement (RP-SC-006) in `tests/performance/test_saga_success_rate.py`

### Implementation for US4

- [ ] T059 [US4] En `Auditor`: insert event_log por cada paso SAGA (no solo al final)
  - SAGA_STARTED, USUARIO_VALIDADO, EVENTO_VALIDADO, PAGO_PROCESADO, INVENTARIO_DECREMENTADO, RESERVA_CONFIRMADA, SAGA_COMPLETED
- [ ] T060 [US4] Payloads JSONB completos con todos los datos relevantes
- [ ] T061 [US4] Metadata: correlation_id, service name, timestamp
- [ ] T062 [US4] Vista materializada / query analítica: `ventas_por_evento`, `tasa_exito_saga`, `compensaciones_por_tipo` (ver plan.md SQL)
- [ ] T063 [US4] Particionamiento mensual event_log (opcional, activar si >10M eventos/mes o latencia analítica >500ms)

---

## Phase 7: Polish & Cross-Cutting

- [ ] T064 [P] OpenAPI descriptions + examples + error responses
- [ ] T065 [P] Quickstart validation: docker compose up full stack, test SAGA end-to-end
- [ ] T066 Code cleanup: type hints, remove unused, docstrings
- [ ] T067 [P] Load test: 100 req/s concurrentes, verificar 0 doble ventas, 0 inventario negativo
- [ ] T068 Circuit breaker verification: test closed/open/half-open transitions
- [ ] T069 Security: validación estricta inputs, no PII en logs, correlation_id tracking
- [ ] T070 [P] Metrics endpoint: `/metrics` Prometheus exposition (latency, error rate, throughput)
- [ ] T071 [P] Health check three-state per dependency: healthy/degraded/unhealthy
- [ ] T072 [P] Docker build verification: `docker compose build reservas-service` succeeds, no critical vulnerabilities
- [ ] T073 [P] Dependency vulnerability scan: `pip-audit` or `safety` check, zero critical/high
- [ ] T074 [P] Idempotency behavior verification: same reserva_id returns 200 with existing reservation
- [ ] T075 Verify all contract/integration/unit tests pass

---

## Dependencies & Execution Order

### Phase Dependencies
- Setup (1) → Foundational (2) → US1 SAGA Happy (3) → US2 Compensaciones (4) → US3 Chain Test (5) → US4 Event Sourcing (6) → Polish (7)
- Polish (Phase 7): Depends on all stories complete (T064-T075)

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

## Phase 8: Convergence

**Purpose**: Close gaps between specification, plan, tasks, and implementation identified during convergence analysis.

### Critical - Missing Core Components

- [ ] T076 [US1] Implement `SagaOrchestrator` in `src/services/saga_orchestrator.py`: execute chain, handle errors, trigger compensations per `plan.md:T032` (missing)
- [ ] T077 [US1] Implement contract test: POST `/api/v1/reservar` OpenAPI validation in `tests/contract/test_reservas_openapi.py` per `tasks.md:T016` (missing)
- [ ] T078 [US1] Implement integration test: SAGA happy path completo in `tests/integration/test_saga_happy_path.py` per `tasks.md:T017` (missing)
- [ ] T079 [US1] Implement unit test: Lua script pago+decremento atómico in `tests/unit/test_lua_scripts.py` per `tasks.md:T018` (missing)
- [ ] T080 [US1] Implement performance test: SAGA completa < 500ms p95 (RP-SC-001) in `tests/performance/test_saga_performance.py` per `tasks.md:T019` (missing)
- [ ] T081 [US1] Implement performance test: P99 < 1s under load (RP-SC-007) in `tests/performance/test_saga_p99.py` per `tasks.md:T020` (missing)
- [ ] T082 [US1] Implement test: Zero double bookings (RP-SC-002) in `tests/integration/test_double_booking.py` per `tasks.md:T021` (missing)
- [ ] T083 [US1] Implement test: Zero negative inventory (RP-SC-003) in `tests/integration/test_negative_inventory.py` per `tasks.md:T022` (missing)

### Critical - US2 Compensations Tests

- [ ] T084 [US2] Integration test: Fallo Paso 5 (MongoDB down) → compensación Redis in `tests/integration/test_saga_compensations.py` per `tasks.md:T040` (missing)
- [ ] T085 [US2] Integration test: Fallo Paso 4 (inventario insuficiente Lua) → 0 cambios in `tests/integration/test_saga_compensations.py` per `tasks.md:T041` (missing)
- [ ] T086 [US2] Unit test: Lua compensación `compensar_pago_inventario.lua` in `tests/unit/test_lua_scripts.py` per `tasks.md:T042` (missing)
- [ ] T087 [US2] Test: Compensación 100% success en fallos simulados paso 4-5 (RP-SC-004) in `tests/integration/test_compensation_success.py` per `tasks.md:T043` (missing)

### Critical - US3 Chain Testing

- [ ] T088 [US3] Unit tests each handler in `tests/unit/test_handlers.py` per `tasks.md:T049` (missing)

### Critical - US4 Event Sourcing Tests

- [ ] T089 [US4] Integration test: Verificar 7 eventos ordenados en PG tras reserva exitosa per `tasks.md:T053` (missing)
- [ ] T089 [US4] Integration test: Verificar SAGA_FAILED + COMPENSACION en PG tras fallo per `tasks.md:T054` (missing)
- [ ] T091 [US4] Unit test: Query analítica `ventas_por_evento` retorna agregados correctos per `tasks.md:T055` (missing)
- [ ] T092 [US4] Integration test: Verificar TODOS los event types en `tests/integration/test_all_event_types.py` per `tasks.md:T056` (missing)
- [ ] T093 [US4] Test: Audit log 100% completo (RP-SC-005) in `tests/integration/test_audit_completeness.py` per `tasks.md:T057` (missing)
- [ ] T094 [US4] Test: SAGA success rate > 99.9% measurement (RP-SC-006) in `tests/performance/test_saga_success_rate.py` per `tasks.md:T058` (missing)

### High - Missing SQL Views & Partitioning

- [ ] T095 [US4] Create SQL view `ventas_por_evento` (Últimos 30 días) in PostgreSQL per `spec.md` CQRS section (missing)
- [ ] T096 [US4] Create SQL view `tasa_exito_saga` (Últimos 7 días rolling) in PostgreSQL per `spec.md` CQRS section (missing)
- [ ] T097 [US4] Create SQL view `compensaciones_por_tipo` (Últimas 24h) in PostgreSQL per `spec.md` CQRS section (missing)
- [ ] T097 [US4] Create GIN index `idx_event_log_payload_gin` on `event_log.payload` per `plan.md` (missing)
- [ ] T098 [US4] Implement monthly partitioning for `event_log` (activar si >10M eventos/mes o latencia analítica >500ms) per `plan.md` (partial)

### High - Health Check & Circuit Breaker Improvements

- [ ] T099 [US1] Add `degraded` state for HTTP clients in health check per `spec.md` Health Check States (partial)
- [ ] T100 [US1] Add `half-open` state to circuit breaker health check per `spec.md` Circuit Breaker (partial)
- [ ] T101 [US1] Add HTTP client timeout to health check timeouts table per `spec.md` (partial)
- [ ] T102 [US1] Add circuit breaker state transition tests per `tasks.md:T068` (missing)

### High - Missing Tests & Documentation

- [ ] T103 [US4] Create OpenAPI descriptions + examples + error responses per `tasks.md:T064` (missing)
- [ ] T104 [US1] Quickstart validation test: docker compose up full stack, test SAGA end-to-end per `tasks.md:T065` (missing)
- [ ] T105 [US1] Code cleanup: type hints, remove unused, docstrings per `tasks.md:T066` (missing)
- [ ] T106 [US1] Load test: 100 req/s concurrentes, verificar 0 doble ventas, 0 inventario negativo per `tasks.md:T067` (missing)
- [ ] T107 [US1] Docker build verification test per `tasks.md:T072` (missing)
- [ ] T108 [US1] Dependency vulnerability scan test per `tasks.md:T073` (missing)
- [ ] T109 [US1] Idempotency behavior verification test per `tasks.md:T074` (missing)
- [ ] T110 [US1] Verify all contract/integration/unit tests pass per `tasks.md:T075` (missing)
- [ ] T111 [US1] Security hardening: input validation/sanitization per `tasks.md:T069` (partial)
- [ ] T112 [US1] Docker build verification: `docker compose build reservas-service` succeeds, no critical vulnerabilities per `tasks.md:T072` (missing)
- [ ] T112 [US1] Dependency vulnerability scan: `pip-audit` or `safety` check per `tasks.md:T073` (missing)

### Medium - SagaOrchestrator Compensation Handlers

- [ ] T113 [US2] Implement compensation handlers in `SagaOrchestrator` for steps 4-5 per `tasks.md:T046` (missing)

### Medium - Health Check HTTP Clients Timeout

- [ ] T114 [US1] Add HTTP client timeout to health check timeouts table per `spec.md` (partial)