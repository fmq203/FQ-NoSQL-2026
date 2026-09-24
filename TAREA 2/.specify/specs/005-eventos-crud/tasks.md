---

description: "Task list for Eventos CRUD Service implementation"
---

# Tasks: Eventos CRUD Service

**Input**: Design documents from `/specs/005-eventos-crud/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Test-first (TDD) mandatory per Constitution Principle III. Contract tests → Integration tests → Unit tests.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `eventos-service/src/`, `eventos-service/tests/` at repository root
- Paths shown below use `eventos-service/` prefix

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure for eventos-service

- [ ] T001 Create project directory structure per implementation plan in `eventos-service/src/`, `eventos-service/tests/`
- [ ] T002 Initialize Python project with FastAPI, Motor, Pydantic dependencies in `eventos-service/requirements.txt`
- [ ] T003 [P] Configure linting (ruff) and formatting (black) in `eventos-service/pyproject.toml`
- [ ] T004 [P] Create `.env.example` with all required environment variables in `eventos-service/.env.example`
- [ ] T005 [P] Create `pytest.ini` with async configuration in `eventos-service/pytest.ini`
- [ ] T006 [P] Create `Dockerfile` for containerization in `eventos-service/Dockerfile`
- [ ] T007 [P] Create `docker-compose.yml` for service integration in `eventos-service/docker-compose.yml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T008 Create configuration management with pydantic-settings in `eventos-service/src/config.py`
- [ ] T009 Implement MongoDB connection manager with Motor async in `eventos-service/src/services/mongodb.py`
- [ ] T010 [P] Create base exception classes and RFC 7807 error handling in `eventos-service/src/utils/errors.py`
- [ ] T011 [P] Implement correlation ID middleware for distributed tracing in `eventos-service/src/api/middleware/correlation.py`
- [ ] T012 [P] Implement structured JSON logging middleware in `eventos-service/src/api/middleware/logging.py`
- [ ] T013 [P] Implement Prometheus metrics middleware in `eventos-service/src/api/middleware/metrics.py`
- [ ] T014 [P] Create base Pydantic models with validation utilities in `eventos-service/src/utils/validation.py`
- [ ] T015 Create FastAPI app factory with middleware registration in `eventos-service/src/main.py`
- [ ] T016 Configure MongoDB indexes on startup in `eventos-service/src/services/mongodb.py`
- [ ] T017 [P] Verify `brain/decisions/db-selection.md` exists and documents MongoDB rationale

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Crear Evento (Priority: P1) 🎯 MVP

**Goal**: Implement POST /api/v1/eventos endpoint to create events with full validation

**Independent Test**: POST `/api/v1/eventos` with valid JSON → 201 with evento_id, creado_en. Verify in MongoDB document exists with all fields.

### Tests for User Story 1 (MANDATORY - TDD)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T018 [P] [US1] Contract test for POST /api/v1/eventos in `eventos-service/tests/contract/test_eventos_post.py`
- [ ] T019 [P] [US1] Integration test for create event flow in `eventos-service/tests/integration/test_eventos_crud.py`
- [ ] T020 [P] [US1] Unit test for Evento model validation in `eventos-service/tests/unit/test_evento_model.py`
- [ ] T021 [P] [US1] Contract test for RFC 7807 error response structure in `eventos-service/tests/contract/test_errors.py`

### Implementation for User Story 1

- [ ] T022 [P] [US1] Create Evento, PrecioCategoria, Ubicacion models in `eventos-service/src/models/evento.py` with validations:
  - nombre: string 1-200 chars, not empty
  - estado: enum borrador|publicado|cancelado|finalizado
  - aforo_total: int >= 0
  - entradas_disponibles: int >= 0, <= aforo_total
  - precios[]: array min 1, categorias unique, precio >= 0 (max 2 decimals), disponibles >= 0
  - sum(precios.disponibles) <= entradas_disponibles
  - ubicacion.ciudad: required, 1-100 chars
  - ubicacion.pais: required, 1-100 chars
  - ubicacion.direccion: optional, max 500 chars
- [ ] T023 [P] [US1] Create health check models in `eventos-service/src/models/health.py`
- [ ] T024 [US1] Implement EventoService with create_event method in `eventos-service/src/services/evento_service.py`:
  - Insert document with UUID _id, creado_en, actualizado_en timestamps
  - Use write concern majority + journal:true
  - Return EventoResponse with generated evento_id
  - Enforce name uniqueness → raise 409 DUPLICATE_EVENT
- [ ] T025 [US1] Implement POST /api/v1/eventos endpoint in `eventos-service/src/api/routes/eventos.py`:
  - Accept EventoCreate request body
  - Return 201 with EventoResponse
  - Handle validation errors → 422 RFC 7807
  - Handle MongoDB duplicate key → 409 RFC 7807
  - Handle MongoDB errors → 500/503 RFC 7807
  - Add X-Correlation-ID header to response
- [ ] T026 [US1] Add structured logging for create_event operation in `eventos-service/src/services/evento_service.py` and route
- [ ] T027 [US1] Register eventos router with /api/v1 prefix in main.py
- [ ] T028 [US1] Performance test for create event: verify < 100ms p95 in `eventos-service/tests/performance/test_create_event.py`

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently. Run contract tests to validate.

---

## Phase 4: User Story 2 - Obtener Evento por ID (Priority: P1)

**Goal**: Implement GET /api/v1/eventos/{evento_id} endpoint to retrieve events by UUID

**Independent Test**: GET `/api/v1/eventos/{evento_id}` → 200 with complete event + precios[]. Testable without other services.

### Tests for User Story 2 (MANDATORY - TDD)

- [ ] T029 [P] [US2] Contract test for GET /api/v1/eventos/{id} in `eventos-service/tests/contract/test_eventos_get.py`
- [ ] T030 [P] [US2] Integration test for get event by ID in `eventos-service/tests/integration/test_eventos_crud.py`
- [ ] T031 [P] [US2] Unit test for get_event service method in `eventos-service/tests/unit/test_evento_service.py`

### Implementation for User Story 2

- [ ] T032 [US2] Add get_event method to EventoService in `eventos-service/src/services/evento_service.py`:
  - Query by UUID _id with read preference secondaryPreferred
  - Return EventoResponse or raise NotFound exception
  - Handle invalid UUID format → 422 RFC 7807
- [ ] T033 [US2] Implement GET /api/v1/eventos/{evento_id} endpoint in `eventos-service/src/api/routes/eventos.py`:
  - Path parameter validation (UUID format)
  - Return 200 with EventoResponse
  - Return 404 Not Found with RFC 7807 format
  - Return 422 for invalid UUID
  - Add X-Correlation-ID header to response
- [ ] T034 [US2] Add structured logging for get_event operation
- [ ] T035 [US2] Add correlation ID propagation in service layer
- [ ] T036 [US2] Performance test for get event: verify < 50ms p95 in `eventos-service/tests/performance/test_get_event.py`

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently.

---

## Phase 5: User Story 3 - Health Check (Priority: P1)

**Goal**: Implement GET /health endpoint with MongoDB connectivity verification

**Independent Test**: GET `/health` → 200 with MongoDB status. Testable without other services.

### Tests for User Story 3 (MANDATORY - TDD)

- [ ] T037 [P] [US3] Contract test for GET /health in `eventos-service/tests/contract/test_health.py`
- [ ] T038 [P] [US3] Integration test for health check with real MongoDB in `eventos-service/tests/integration/test_health_integration.py`
- [ ] T039 [P] [US3] Unit test for health status determination logic in `eventos-service/tests/unit/test_health_service.py`

### Implementation for User Story 3

- [ ] T040 [US3] Implement HealthService with check_mongodb method in `eventos-service/src/services/health_service.py`:
  - Ping MongoDB with 2-second timeout
  - Measure latency: <50ms = healthy/ok, 50-500ms = degraded/slow, failed = unhealthy/down
  - Return HealthCheckResponse with status, checks, timestamp
- [ ] T041 [US3] Implement GET /health endpoint in `eventos-service/src/api/routes/health.py`:
  - Call HealthService.check_mongodb()
  - Return 200 for healthy/degraded with HealthCheckResponse
  - Return 503 for unhealthy with HealthCheckResponse
  - Add X-Correlation-ID header to response
- [ ] T042 [US3] Add structured logging for health_check operation
- [ ] T043 [US3] Configure health check thresholds via environment variables
- [ ] T044 [US3] Performance test for health check: verify < 50ms p99 in `eventos-service/tests/performance/test_health.py`

**Checkpoint**: All user stories should now be independently functional.

---

## Phase 6: Cross-Cutting Concerns (Constitution Compliance)

**Purpose**: Constitution Principles II, IV, V, VII compliance tasks

- [ ] T045 [P] Implement API versioning: add /v1 prefix to all routes, Accept header parsing in `eventos-service/src/api/routes/`
- [ ] T046 [P] Implement egress correlation ID propagation for downstream HTTP calls in `eventos-service/src/api/middleware/correlation.py` (no downstream calls in MVP - document)
- [ ] T047 [P] Add dependency vulnerability scanning (pip-audit) to CI in `.github/workflows/ci.yml`
- [ ] T048 [P] Run contract test suite against OpenAPI spec for compliance in `eventos-service/tests/contract/test_openapi_compliance.py`
- [ ] T049 [P] Add Prometheus metrics exposition endpoint `/metrics` in `eventos-service/src/api/routes/metrics.py`

---

## Phase 7: Polish & Validation

**Purpose**: Improvements that affect multiple user stories, validation, and production readiness

- [ ] T050 [P] Run quickstart.md validation - verify all endpoints work per examples
- [ ] T051 Run full test suite with coverage ≥ 80% on business logic
- [ ] T052 [P] Add unit tests for edge cases in `eventos-service/tests/unit/`:
  - aforo_total = 0 validation (with entradas_disponibles = 0 valid)
  - aforo_total = 0, entradas_disponibles > 0 → 422
  - entradas_disponibles = aforo_total > 0 valid case
  - precio = 0 valid (free event)
  - categoria duplicada validation
  - estado cancelado handling
  - name uniqueness → 409 Conflict
- [ ] T053 [P] Verify Docker build succeeds: `docker build -t eventos-service .`
- [ ] T054 [P] Verify docker-compose integration from repository root
- [ ] T055 [P] Security review: no secrets in code, input validation at boundaries, no PII in logs
- [ ] T056 [P] Update OpenAPI spec if any deviations from contracts/openapi.yaml

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - **BLOCKS all user stories**
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1, US2, US3 can proceed in parallel after Foundational (all P1 priority)
  - Or sequentially: US1 → US2 → US3
- **Cross-Cutting (Phase 6)**: Can start after Foundational; runs parallel to user stories
- **Polish (Phase 7)**: Depends on all user stories (US1, US2, US3) AND cross-cutting being complete

### User Story Dependencies

- **User Story 1 (Crear Evento)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (Obtener Evento)**: Can start after Foundational - May use Evento model from US1 but independently testable
- **User Story 3 (Health Check)**: Can start after Foundational - Completely independent, no dependencies

### Within Each User Story

- Tests (MANDATORY) MUST be written and FAIL before implementation (TDD)
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next (if sequential)

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T003-T007)
- All Foundational tasks marked [P] can run in parallel (T010-T014, T017)
- All US1 tests marked [P] can run in parallel (T018-T021)
- All US2 tests marked [P] can run in parallel (T029-T031)
- All US3 tests marked [P] can run in parallel (T037-T039)
- US1, US2, US3 implementation can run in parallel after Foundational (different files)
- All Cross-Cutting tasks marked [P] can run in parallel (T045-T049)
- All Polish tasks marked [P] can run in parallel (T050, T052-T056)

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Contract test for POST /api/v1/eventos in events-service/tests/contract/test_eventos_post.py"
Task: "Integration test for create event flow in events-service/tests/integration/test_eventos_crud.py"
Task: "Unit test for Evento model validation in events-service/tests/unit/test_evento_model.py"
Task: "Contract test for RFC 7807 error response structure in events-service/tests/contract/test_errors.py"

# Launch all models for User Story 1 together:
Task: "Create Evento, PrecioCategoria, Ubicacion models in events-service/src/models/evento.py"
Task: "Create health check models in events-service/src/models/health.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (**CRITICAL - blocks all stories**)
3. Complete Phase 3: User Story 1 (Crear Evento)
4. **STOP and VALIDATE**: Test User Story 1 independently with contract tests
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 (Crear Evento) → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 (Obtener Evento) → Test independently → Deploy/Demo
4. Add User Story 3 (Health Check) → Test independently → Deploy/Demo
5. Add Cross-Cutting Concerns → Full Constitution compliance
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Crear Evento)
   - Developer B: User Story 2 (Obtener Evento)
   - Developer C: User Story 3 (Health Check)
   - Developer D: Cross-Cutting Concerns (Versioning, Metrics, Security)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- **TDD MANDATORY**: Verify tests fail before implementing (Constitution Principle III)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- Constitution Principle IV: All logging must use structured JSON with correlation_id; metrics exposition required
- Constitution Principle II: OpenAPI spec is source of truth - validate against contracts/openapi.yaml; versioned routes required
- Constitution Principle VII: Dependency vulnerability scanning required in CI