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

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T007 Create configuration management with pydantic-settings in `eventos-service/src/config.py`
- [ ] T008 Implement MongoDB connection manager with Motor async in `eventos-service/src/services/mongodb.py`
- [ ] T009 [P] Create base exception classes and RFC 7807 error handling in `eventos-service/src/utils/errors.py`
- [ ] T010 [P] Implement correlation ID middleware for distributed tracing in `eventos-service/src/api/middleware/correlation.py`
- [ ] T011 [P] Implement structured JSON logging middleware in `eventos-service/src/api/middleware/logging.py`
- [ ] T012 [P] Create base Pydantic models with validation utilities in `eventos-service/src/utils/validation.py`
- [ ] T013 Create FastAPI app factory with middleware registration in `eventos-service/src/main.py`
- [ ] T014 Configure MongoDB indexes on startup in `eventos-service/src/services/mongodb.py`
- [ ] T015 Add health check endpoint structure in `eventos-service/src/api/routes/health.py` (placeholder)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Crear Evento (Priority: P1) 🎯 MVP

**Goal**: Implement POST /api/eventos endpoint to create events with full validation

**Independent Test**: POST `/api/eventos` with valid JSON → 201 with evento_id, creado_en. Verify in MongoDB document exists with all fields.

### Tests for User Story 1 (MANDATORY - TDD)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T016 [P] [US1] Contract test for POST /api/eventos in `eventos-service/tests/contract/test_eventos_post.py`
- [ ] T017 [P] [US1] Integration test for create event flow in `eventos-service/tests/integration/test_eventos_crud.py`
- [ ] T018 [P] [US1] Unit test for Evento model validation in `eventos-service/tests/unit/test_evento_model.py`

### Implementation for User Story 1

- [ ] T019 [P] [US1] Create Evento, PrecioCategoria, Ubicacion models in `eventos-service/src/models/evento.py` with validations:
  - nombre: string 1-200 chars, not empty
  - estado: enum borrador|publicado|cancelado|finalizado
  - aforo_total: int >= 0
  - entradas_disponibles: int >= 0, <= aforo_total
  - precios[]: array min 1, categorias unique, precio >= 0 (2 decimals), disponibles >= 0
  - sum(precios.disponibles) <= entradas_disponibles
  - ubicacion.ciudad: required, 1-100 chars
  - ubicacion.pais: required, 1-100 chars
  - ubicacion.direccion: optional, max 500 chars
- [ ] T020 [P] [US1] Create health check models in `eventos-service/src/models/health.py`
- [ ] T021 [US1] Implement EventoService with create_event method in `eventos-service/src/services/evento_service.py`:
  - Insert document with UUID _id, creado_en, actualizado_en timestamps
  - Use write concern majority + journal:true
  - Return EventoResponse with generated evento_id
- [ ] T022 [US1] Implement POST /api/eventos endpoint in `eventos-service/src/api/routes/eventos.py`:
  - Accept EventoCreate request body
  - Return 201 with EventoResponse
  - Handle validation errors → 422 RFC 7807
  - Handle MongoDB errors → 500/503 RFC 7807
  - Add X-Correlation-ID header to response
- [ ] T023 [US1] Add structured logging for create_event operation in `eventos-service/src/services/evento_service.py` and route
- [ ] T024 [US1] Register eventos router in main.py

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently. Run contract tests to validate.

---

## Phase 4: User Story 2 - Obtener Evento por ID (Priority: P1)

**Goal**: Implement GET /api/eventos/{evento_id} endpoint to retrieve events by UUID

**Independent Test**: GET `/api/eventos/{evento_id}` → 200 with complete event + precios[]. Testable without other services.

### Tests for User Story 2 (MANDATORY - TDD)

- [ ] T025 [P] [US2] Contract test for GET /api/eventos/{id} in `eventos-service/tests/contract/test_eventos_get.py`
- [ ] T026 [P] [US2] Integration test for get event by ID in `eventos-service/tests/integration/test_eventos_crud.py`
- [ ] T027 [P] [US2] Unit test for get_event service method in `eventos-service/tests/unit/test_evento_service.py`

### Implementation for User Story 2

- [ ] T028 [US2] Add get_event method to EventoService in `eventos-service/src/services/evento_service.py`:
  - Query by UUID _id with read preference secondaryPreferred
  - Return EventoResponse or raise NotFound exception
  - Handle invalid UUID format → 422 RFC 7807
- [ ] T029 [US2] Implement GET /api/eventos/{evento_id} endpoint in `eventos-service/src/api/routes/eventos.py`:
  - Path parameter validation (UUID format)
  - Return 200 with EventoResponse
  - Return 404 Not Found with RFC 7807 format
  - Return 422 for invalid UUID
  - Add X-Correlation-ID header to response
- [ ] T030 [US2] Add structured logging for get_event operation
- [ ] T031 [US2] Add correlation ID propagation in service layer

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently.

---

## Phase 5: User Story 3 - Health Check (Priority: P1)

**Goal**: Implement GET /health endpoint with MongoDB connectivity verification

**Independent Test**: GET `/health` → 200 with MongoDB status. Testable without other services.

### Tests for User Story 3 (MANDATORY - TDD)

- [ ] T032 [P] [US3] Contract test for GET /health in `eventos-service/tests/contract/test_health.py`
- [ ] T033 [P] [US3] Integration test for health check with real MongoDB in `eventos-service/tests/integration/test_health_integration.py`
- [ ] T034 [P] [US3] Unit test for health status determination logic in `eventos-service/tests/unit/test_health_service.py`

### Implementation for User Story 3

- [ ] T035 [US3] Implement HealthService with check_mongodb method in `eventos-service/src/services/health_service.py`:
  - Ping MongoDB with 2-second timeout
  - Measure latency: <50ms = healthy/ok, 50-500ms = degraded/slow, failed = unhealthy/down
  - Return HealthCheckResponse with status, checks, timestamp
- [ ] T036 [US3] Implement GET /health endpoint in `eventos-service/src/api/routes/health.py`:
  - Call HealthService.check_mongodb()
  - Return 200 for healthy/degraded with HealthCheckResponse
  - Return 503 for unhealthy with HealthCheckResponse
  - Add X-Correlation-ID header to response
- [ ] T037 [US3] Add structured logging for health_check operation
- [ ] T038 [US3] Configure health check thresholds via environment variables

**Checkpoint**: All user stories should now be independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories, validation, and production readiness

- [ ] T039 [P] Run quickstart.md validation - verify all endpoints work per examples
- [ ] T040 Run full test suite with coverage ≥ 80% on business logic
- [ ] T041 [P] Add unit tests for edge cases in `eventos-service/tests/unit/`:
  - aforo_total = 0 validation
  - entradas_disponibles = aforo_total valid case
  - precio = 0 valid (free event)
  - categoria duplicada validation
  - estado cancelado handling
- [ ] T042 Performance test: verify create event < 100ms p95, get event < 50ms p95, health check < 10ms p99
- [ ] T043 [P] Verify Docker build succeeds: `docker build -t eventos-service .`
- [ ] T044 [P] Verify docker-compose integration from repository root
- [ ] T045 [P] Security review: no secrets in code, input validation at boundaries, no PII in logs
- [ ] T046 [P] Update OpenAPI spec if any deviations from contracts/openapi.yaml
- [ ] T047 Run contract test suite against OpenAPI spec for compliance

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - **BLOCKS all user stories**
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1, US2, US3 can proceed in parallel after Foundational (all P1 priority)
  - Or sequentially: US1 → US2 → US3
- **Polish (Phase 6)**: Depends on all user stories (US1, US2, US3) being complete

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

- All Setup tasks marked [P] can run in parallel (T003-T006)
- All Foundational tasks marked [P] can run in parallel (T009-T012)
- All US1 tests marked [P] can run in parallel (T016-T018)
- All US2 tests marked [P] can run in parallel (T025-T027)
- All US3 tests marked [P] can run in parallel (T032-T034)
- US1, US2, US3 implementation can run in parallel after Foundational (different files)
- All Polish tasks marked [P] can run in parallel (T039, T041, T043-T047)

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Contract test for POST /api/eventos in events-service/tests/contract/test_eventos_post.py"
Task: "Integration test for create event flow in events-service/tests/integration/test_eventos_crud.py"
Task: "Unit test for Evento model validation in events-service/tests/unit/test_evento_model.py"

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
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Crear Evento)
   - Developer B: User Story 2 (Obtener Evento)
   - Developer C: User Story 3 (Health Check)
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
- Constitution Principle IV: All logging must use structured JSON with correlation_id
- Constitution Principle II: OpenAPI spec is source of truth - validate against contracts/openapi.yaml