---
description: "Task list for User Management feature implementation"
---

# Tasks: User Management (Usuarios Service)

**Input**: Design documents from `.specify/specs/001-user-management/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create `usuarios-service/` directory structure per plan.md
- [ ] T002 Create `requirements.txt` with FastAPI, Pydantic, PyMongo, email-validator, python-dotenv, httpx, pytest
- [ ] T003 [P] Create `Dockerfile` with Python 3.11, install deps, copy src, expose 8001, healthcheck curl
- [ ] T004 [P] Create `.env.example` with MONGODB_URI, MONGODB_DB, SERVICE_PORT, ANONYMIZATION_SALT
- [ ] T005 [P] Create `pytest.ini` with asyncio mode, test paths

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Setup MongoDB connection (`src/services/mongo.py`) with Motor async client, read_preference secondaryPreferred, write_concern majority+journal
- [ ] T007 [P] Create MongoDB indexes on startup: email (unique), nro_documento (unique), creado_en (-1), historial_compras.fecha_compra (-1)
- [ ] T008 [P] Configure structured JSON logging (structlog or stdlib)
- [ ] T009 Create base Pydantic models (`src/models/usuario.py`): TipoDocumento enum, UsuarioCreate, Usuario, UsuarioExport, UsuarioAnonimizado
- [ ] T010 [P] Implement anonymization utility (`src/utils/anonymize.py`): SHA-256 hash with salt from env
- [ ] T010b [P] Document salt rotation procedure in `docs/anonymization-salt-rotation.md`: env var update, re-hash strategy for existing exports
- [ ] T011 Setup FastAPI app (`src/main.py`) with lifespan for MongoDB connection, health check endpoint
- [ ] T011b Implement RFC 7807 error response middleware in `src/api/middleware.py`: format all errors per spec, include correlation_id, type URI
- [ ] T011c Configure API versioning in FastAPI: prefix `/api/v1` for all routes, accept header parsing
- [ ] T012 Configure environment loading (`python-dotenv`) in main.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Crear Usuario (Priority: P1) 🎯 MVP

**Goal**: POST `/api/usuarios` crea usuario con validación unicidad, retorna 201 con UUID y historial vacío

**Independent Test**: POST JSON válido → 201 con usuario_id, creado_en, historial_compras=[]. Verificar en MongoDB.

### Tests for User Story 1 (MANDATORY - Constitution Principle III)

> **NOTE: TDD mandatory - tests written → fail → then implement**

- [ ] T013 [P] [US1] Contract test: POST `/api/usuarios` validates OpenAPI spec in `tests/contract/test_usuarios_openapi.py`
- [ ] T014 [P] [US1] Integration test: Create user success + duplicate email/document → 409 in `tests/integration/test_usuarios_flow.py`
- [ ] T015 [P] [US1] Unit test: Anonymization produces irreversible hash in `tests/unit/test_anonymize.py`
- [ ] T016 [P] [US1] Performance test: Create user < 100ms p95 (SC-001) in `tests/performance/test_create_user.py`

### Implementation for User Story 1

- [ ] T019 [P] [US1] Create route handler `POST /api/usuarios` in `src/api/routes.py`
- [ ] T020 [US1] Implement `crear_usuario` in `src/services/usuario_service.py`: check unique email/document, insert with write_concern majority, return Usuario model
- [ ] T021 [US1] Add validation error handling (422) and conflict errors (409) with proper messages
- [ ] T022 [US1] Add logging for create operations (structured: user_id, action, duration_ms)
- [ ] T023 [US1] Verify RFC 7807 error responses for create user: 409 DUPLICATE_EMAIL, 409 DUPLICATE_DOCUMENT, 422 VALIDATION_ERROR

---

## Phase 4: User Story 2 - Obtener Usuario por ID (Priority: P1)

**Goal**: GET `/api/usuarios/{usuario_id}` retorna usuario completo con historial_compras

**Independent Test**: GET con ID válido → 200 con historial. GET ID inexistente → 404.

### Tests for User Story 2 (MANDATORY)

- [ ] T024 [P] [US2] Contract test: GET `/api/usuarios/{id}` validates OpenAPI spec
- [ ] T025 [P] [US2] Integration test: Get existing user + historial, get non-existent → 404
- [ ] T026 [P] [US2] Performance test: Get user < 50ms p95 secondaryPreferred (SC-002) in `tests/performance/test_get_user.py`

### Implementation for User Story 2

- [ ] T027 [P] [US2] Create route handler `GET /api/usuarios/{usuario_id}` in `src/api/routes.py`
- [ ] T028 [US2] Implement `obtener_usuario` in `src/services/usuario_service.py`: find by _id with read_preference secondaryPreferred
- [ ] T029 [US2] Add UUID validation (422) and not found handling (404)

---

## Phase 5: User Story 3 - Listar Usuarios Paginado (Priority: P2)

**Goal**: GET `/api/usuarios?skip=0&limit=10` retorna array paginado (sin historial para performance)

**Independent Test**: GET con paginación → 200 array usuarios. Parámetros inválidos → 422.

### Tests for User Story 3 (MANDATORY)

- [ ] T030 [P] [US3] Contract test: GET `/api/usuarios` validates OpenAPI spec
- [ ] T031 [P] [US3] Integration test: Pagination skip/limit, boundary conditions
- [ ] T032 [P] [US3] Performance test: List 1000 users < 200ms (SC-003) in `tests/performance/test_list_users.py`

### Implementation for User Story 3

- [ ] T033 [P] [US3] Create route handler `GET /api/usuarios` in `src/api/routes.py` with query params skip, limit
- [ ] T034 [US3] Implement `listar_usuarios` in `src/services/usuario_service.py`: projection sin historial_compras, sort creado_en desc, skip/limit
- [ ] T035 [US3] Add validation: limit max 100, skip >= 0

---

## Phase 6: User Story 4 - Exportar Anonimizado GDPR (Priority: P2)

**Goal**: GET `/api/usuarios/exportar?format=json|csv` streaming response con hash irreversible + métricas analíticas

**Independent Test**: GET → 200 streaming JSON/CSV con usuario_hash, eventos_comprados, gasto_total. Sin PII.

### Tests for User Story 4 (MANDATORY)

- [ ] T036 [P] [US4] Contract test: GET `/api/usuarios/exportar` validates OpenAPI spec
- [ ] T037 [P] [US4] Integration test: Export JSON + CSV, verify no PII fields, hash deterministic
- [ ] T038 [P] [US4] Unit test: Anonymization preserves analytical data (count, sum)
- [ ] T039 [P] [US4] Performance test: Export 10k users < 2s streaming (SC-004) in `tests/performance/test_export_users.py`
- [ ] T040 [P] [US4] Data integrity test: Export includes all users, hash irreversible (SC-005, SC-006) in `tests/integration/test_export_integrity.py`
- [ ] T041 [P] [US4] Streaming export integrity test: Verify all users emitted exactly once, no data loss (SC-005) in `tests/integration/test_export_integrity.py`
- [ ] T042 [P] [US4] Structured logging schema validation test: Verify JSON log format, no PII, required fields present in `tests/contract/test_logging_schema.py`
- [ ] T043 [P] [US4] Correlation ID propagation test: Verify X-Correlation-ID passed to downstream calls in `tests/integration/test_tracing.py`

### Implementation for User Story 4

- [ ] T044 [P] [US4] Create route handler `GET /api/usuarios/exportar` in `src/api/routes.py` con format query param
- [ ] T045 [US4] Implement `exportar_usuarios` en `src/services/usuario_service.py`: cursor batch_size=1000, streaming response, anonymize each
- [ ] T046 [US4] Add CSV formatting with headers, proper escaping
- [ ] T047 [US4] Add memory-efficient streaming (async generator)
- [ ] T048 [US4] Implement salt versioning in anonymization: prefix hash with salt version, support multiple active salts

---

## Phase 7: Polish & Cross-Cutting

- [ ] T049 [P] Update OpenAPI descriptions from docstrings
- [ ] T050 [P] Add request/response examples in OpenAPI
- [ ] T051 Run quickstart.md validation: docker compose up, test all endpoints
- [ ] T052 Code cleanup: remove unused imports, type hints complete
- [ ] T053 [P] Additional unit tests for edge cases (empty historial, large export)
- [ ] T054 Security hardening: input sanitization, rate limiting placeholder
- [ ] T055 Verify all contract tests pass against running service
- [ ] T056 [P] Contract test execution gate: Run all contract tests against running service, fail on any non-compliance
- [ ] T057 Docker build verification: `docker compose build usuarios-service` succeeds, no critical vulnerabilities (`trivy` or `snyk` scan)
- [ ] T058 Dependency vulnerability scan: `pip-audit` or `safety` check on requirements.txt, zero critical/high
- [ ] T059 RFC 7807 compliance test: Verify all error responses match spec format exactly
- [ ] T060 API versioning verification: Test v1 routes work, deprecation headers present on deprecated endpoints

---

## Dependencies & Execution Order

### Phase Dependencies
- Setup (Phase 1): No dependencies
- Foundational (Phase 2): Depends on Setup - BLOCKS all stories
- User Stories (Phases 3-6): All depend on Foundational completion
  - Can proceed in parallel after Phase 2 (different files)
  - Priority order: US1 → US2 → US3 → US4
- Polish (Phase 7): Depends on all stories complete (T049-T060)

### Parallel Opportunities
- All Setup tasks [P] can run in parallel
- All Foundational tasks [P] can run in parallel
- Tests [P] for each story can run in parallel
- Models within a story [P] can run in parallel

---

## Implementation Strategy

### MVP First (US1 + US2 Only)
1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 (Crear)
4. Complete Phase 4: US2 (Obtener)
5. **STOP and VALIDATE**: Test US1+US2 independently
6. Deploy/demo if ready

### Incremental Delivery
1. Add US3 (Listar) → Test independently
2. Add US4 (Exportar GDPR) → Test independently
3. Each story adds value without breaking previous

---

## Notes
- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Verify tests fail before implementing (TDD)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently