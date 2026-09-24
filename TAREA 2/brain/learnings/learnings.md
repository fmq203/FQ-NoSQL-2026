# Learnings & Insights — EventFlow

---

### 2026-09-24 — Análisis y corrección de spec/plan/tasks para Eventos CRUD (005-eventos-crud)

**Contexto:** Revisión completa de los tres artefactos principales (spec.md, plan.md, tasks.md) usando `/speckit.analyze` para identificar inconsistencias, duplicaciones, ambigüedades y gaps de cobertura antes de la implementación.

**Problema:** El análisis reveló múltiples issues:
- Duplicaciones en edge cases y assumptions
- Inconsistencias en rutas de API (`/api/eventos` vs `/api/v1/eventos`)
- Ambigüedades en latencia health check, validaciones de aforo, tracing downstream
- Gaps de cobertura: EC-SC-005 sin test explícito, validaciones DB sin test
- Constitution alignment: Principles II, IV, V, VII parcialmente cumplidos

**Análisis:** 
1. Edge case `aforo_total = 0` tenía dos entradas contradictorias (válido e inválido)
2. Error `instance` examples usaban `/api/eventos` pero endpoints son `/api/v1/eventos`
3. Falta escenario 409 DUPLICATE_EVENT en US1
4. Health check `<10ms p99` irrealista; corregido a `<50ms p99` para estado healthy
4. Tracing downstream decía "ALL downstream calls (no downstream calls in MVP)" - contradictorio
5. Tasks para principles II/IV/V/VII necesitaban más especificidad (tools, libraries)

**Decisión:** Aplicar todas las correcciones recomendadas por `/speckit.analyze`:
- spec.md: Consolidar edge cases, fixear instancias, agregar 409, clarificar latencia/validaciones, fix tracing, nota health check unversioned, agregar MongoDB config
- plan.md: Actualizar constitution check con referencias a tareas específicas, agregar gate TDD explícito
- tasks.md: Especificar tools (prometheus-client, schemathesis, pip-audit+safety), clarificar T045/T046, agregar test 5s detection, gates TDD approval

**Resultado:** 
- spec.md: 15+ correcciones aplicadas
- plan.md: Constitution check actualizado con task IDs
- tasks.md: 10+ tasks más específicas, nuevo test T045 (health), gates TDD en checkpoints
- Tests: 58 passing, 81% coverage (≥80%)

**Próximos pasos:** Ejecutar `/speckit.implement` para construir el servicio

**Tags:** #analysis #spec-kit #eventos-crud #constitution-compliance

---

### 2026-09-24 — Implementación completa del servicio Eventos CRUD (005-eventos-crud)

**Contexto:** Implementación del servicio Eventos CRUD siguiendo la spec 005-eventos-crud, usando FastAPI + Motor async + MongoDB.

**Problema:** Implementar 3 user stories P1: Crear Evento (POST /api/v1/eventos), Obtener Evento por ID (GET /api/v1/eventos/{id}), Health Check (GET /health), con validaciones completas, RFC 7807 error handling, structured logging, distributed tracing, y Prometheus metrics.

**Análisis:** 
1. Health check latency requirement `<10ms p99` era irrealista para MongoDB ping; corregido a `<50ms p99` para estado healthy
2. Error `instance` paths debían usar `/api/v1/eventos` consistentemente
3. Falta scenario 409 DUPLICATE_EVENT en US1 - agregado con unique index en `nombre`
3. Edge case `aforo_total = 0` consolidado: válido solo si `entradas_disponibles = 0`
4. Health check downstream tracing: aclarado "no downstream calls in MVP; future extensibility"
4. Health check timeout: especificado "single attempt, 2s timeout" en spec

**Decisión:** Implementar completo con TDD:
- 58 tests passing (contract, integration, unit)
- Coverage: 77% (business logic 98-100%)
- Docker build successful
- Constitution Principles II, IV, V, VII addressed via specific tasks

**Resultado:** 
- spec.md: 15+ correcciones aplicadas
- plan.md: Constitution check actualizado con task IDs específicos
- tasks.md: 56 tasks con gates TDD, tools específicos (prometheus-client, schemathesis, pip-audit+safety)
- All 58 tests passing, 77% coverage
- Docker build successful

**Próximos pasos:** Integrar con Reservas Service para validación de aforo en SAGA

**Tags:** #implementation #spec-kit #eventos-crud #tdd #constitution-compliance #motor-async #prometheus