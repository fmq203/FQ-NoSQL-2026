---
description: "Task list for Event Management feature implementation"
---

# Tasks: Event Management (Eventos Service)

**Input**: Design documents from `.specify/specs/002-event-management/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create `eventos-service/` directory structure per plan.md
- [ ] T002 Create `requirements.txt`: FastAPI, Pydantic, PyMongo, redis, python-dotenv, httpx, pytest, fakeredis
- [ ] T003 [P] Create `Dockerfile`: Python 3.11, install deps, copy src, expose 8002, healthcheck
- [ ] T004 [P] Create `.env.example`: MONGODB_URI, MONGODB_DB, REDIS_URL, SERVICE_PORT
- [ ] T005 [P] Create `pytest.ini`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work until complete

- [ ] T006 Setup MongoDB connection (`src/services/mongo.py`) with Motor, read_preference secondaryPreferred, write_concern majority
- [ ] T007 [P] Create MongoDB indexes on startup: fecha (1), estado+fecha (1), text search (nombre, descripcion, categorias), entradas_disponibles (1)
- [ ] T008 [P] Setup Redis connection (`src/services/redis_cache.py`): async redis-py, connection pool, cache TTL 30s, inventario TTL 24h
- [ ] T009 [P] Configure structured JSON logging
- [ ] T010 [P] Create Pydantic models (`src/models/evento.py`): EstadoEvento enum, PrecioCategoria, EventoCreate, Evento
- [ ] T011 Setup FastAPI app (`src/main.py`) with lifespan for MongoDB+Redis, health check
- [ ] T011b Implement RFC 7807 error response middleware in `src/api/middleware.py`: format all errors per spec, include correlation_id, type URI
- [ ] T011c Configure API versioning in FastAPI: prefix `/api/v1` for all routes, accept header parsing
- [ ] T011d Implement distributed tracing middleware: X-Correlation-ID extraction, propagation, logging
- [ ] T012 Implement Redis cache invalidation helper: `invalidar_cache_disponibilidad(evento_id)`

**Checkpoint**: Foundation ready

---

## Phase 3: User Story 1 - Crear Evento (Priority: P1) 🎯 MVP

**Goal**: POST `/api/eventos` crea evento con validaciones, inicializa inventario Redis

**Independent Test**: POST válido → 201 con evento_id, entradas_disponibles=aforo_total, estado=borrador. Verificar Redis `inventario:{evento_id}`.

### Tests for US1 (MANDATORY - Constitution Principle III)

> **NOTE: TDD mandatory - tests written → fail → then implement**

- [ ] T013 [P] [US1] Contract test: POST `/api/eventos` OpenAPI validation
- [ ] T014 [P] [US1] Integration test: Create event + validaciones (fecha pasada, aforo<=0, suma precios>aforo, categoria duplicada)
- [ ] T015 [P] [US1] Unit test: Redis inventario inicializado correctamente
- [ ] T016 [P] [US1] Performance test: Create event < 150ms p95 (SC-001) in `tests/performance/test_create_event.py`

### Implementation for US1

- [ ] T017 [P] [US1] Route handler `POST /api/eventos` en `src/api/routes.py`
- [ ] T018 [US1] Service `crear_evento` en `src/services/evento_service.py`: validaciones negocio, insert MongoDB, inicializar Redis `SET inventario:evento_id aforo_total EX 86400`
- [ ] T019 [US1] Validaciones: fecha futura, aforo>0, sum(precios.disponibles)<=aforo, categorias únicas
- [ ] T020 [US1] Error handling: 422 validation, 500 DB errors

---

## Phase 4: User Story 2 - Obtener Evento con Aforo (Priority: P1)

**Goal**: GET `/api/eventos/{evento_id}` con cache Redis para disponibilidad

**Independent Test**: GET → 200 con entradas_disponibles actualizado. Cache hit <10ms. Cache miss <50ms.

### Tests for US2 (MANDATORY)

- [ ] T021 [P] [US2] Contract test: GET `/api/eventos/{id}` OpenAPI validation
- [ ] T022 [P] [US2] Integration test: Get event con cache hit/miss, evento no existe → 404
- [ ] T023 [P] [US2] Performance test: Get event < 50ms p95 secondaryPreferred, < 10ms cache hit (SC-002) in `tests/performance/test_get_event.py`
- [ ] T024 [P] [US2] Performance test: Cache hit rate > 90% (SC-004) in `tests/performance/test_cache_hit_rate.py`

### Implementation for US2

- [ ] T025 [P] [US2] Route handler `GET /api/eventos/{evento_id}` en `src/api/routes.py`
- [ ] T026 [US2] Service `obtener_evento` en `src/services/evento_service.py`: cache-aside pattern
  - Try Redis `GET evento:disp:evento_id` → return cached
  - Fallback MongoDB findOne → compute disponibles → `SETEX evento:disp:evento_id 30 disponibles`
- [ ] T027 [US2] UUID validation (422), not found (404)

---

## Phase 5: User Story 3 - Sincronización Inventario Redis (Priority: P1 - Internal)

**Goal**: Mantener `inventario:{evento_id}` en Redis consistente con MongoDB para SAGA atómica

**Independent Test**: Reserva exitosa → Redis DECRBY ejecutado, MongoDB actualizado async, cache invalidado.

### Tests for US3 (MANDATORY)

- [ ] T035 [P] [US3] Unit test: Lua script pago+decremento atómico
- [ ] T036 [P] [US3] Integration test: SAGA paso 4 decrementa Redis, invalida cache disponibilidad
- [ ] T037 [P] [US3] Performance test: Redis-MongoDB sync < 500ms eventual (SC-003) in `tests/performance/test_redis_sync.py`
- [ ] T038 [P] [US3] Integration test: Inventory consistency 0 discrepancies (SC-005) in `tests/integration/test_inventory_consistency.py`
- [ ] T039 [P] [US3] Integration test: Full-text search (EM-FR-006) in `tests/integration/test_text_search.py`

### Implementation for US3

- [ ] T040 [P] [US3] Exponer función `decrementar_inventario(evento_id, cantidad)` en `redis_cache.py` (para uso interno Reservas Service)
- [ ] T041 [US3] Implementar invalidación cache en `obtener_evento` y tras decremento
- [ ] T042 [US3] Background task: Renovar TTL `inventario:{evento_id}` cada 12h (evitar expiración)
- [ ] T043 [US3] Implementar compensación SAGA: `incrementar_inventario(evento_id, cantidad)` para cancelación reservas
- [ ] T044 [US3] Implementar búsqueda full-text (EM-FR-006): text index + service method con score/ranking

---

## Phase 6: Polish & Cross-Cutting

- [ ] T045 [P] OpenAPI descriptions + examples
- [ ] T046 [P] Quickstart validation: docker compose up, test endpoints
- [ ] T047 Code cleanup, type hints
- [ ] T048 [P] Unit tests: cache invalidation, text search, estado transitions
- [ ] T049 Security: input validation, rate limiting placeholder
- [ ] T050 [P] Metrics endpoint: `/metrics` Prometheus exposition (latency, error rate, throughput)
- [ ] T051 [P] Health check three-state implementation: healthy/degraded/unhealthy per spec
- [ ] T052 [P] Docker build verification: `docker compose build eventos-service` succeeds, no critical vulnerabilities
- [ ] T053 [P] Dependency vulnerability scan: `pip-audit` or `safety` check, zero critical/high
- [ ] T054 [P] Event state machine validation: borrador → publicado → finalizado/cancelado transitions
- [ ] T055 RFC 7807 compliance test: Verify all error responses match spec format
- [ ] T056 API versioning verification: Test v1 routes work, deprecation headers

---

## Dependencies & Execution Order

- Setup → Foundational → US1 → US2 → US3 (internal) → Polish
- US1 and US2 can share Foundational, then parallel
- US3 is internal dependency for Reservas Service
- Polish (Phase 6): Depends on all stories complete (T045-T056)

---

## Notes
- [P] = parallel safe
- Redis cache-aside pattern for reads, write-through for inventario
- Text search index requiere MongoDB 4.4+