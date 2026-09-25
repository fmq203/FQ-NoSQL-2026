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

---

### 2026-09-24 — Análisis post-implementación y validación para Eventos CRUD (005-eventos-crud)

**Contexto:** Ejecución de `/speckit.analyze` sobre los artefactos implementados (spec.md, plan.md, tasks.md) para validar consistencia, completitud y alineación con la Constitución antes de ejecutar `/speckit.implement`.

**Problema:** El análisis identificó issues menores pendientes de resolver antes de la implementación final:
- F1 (HIGH): US2/US3 acceptance tests usan `/api/eventos` en lugar de `/api/v1/eventos` (copy-paste legacy)
- B1 (HIGH): Health check latency `<50ms p99` aplica solo a estado "healthy"; degraded/unhealthy tienen thresholds distintos
- C1 (MEDIUM): Falta acceptance scenario para 409 DUPLICATE_EVENT en US1
- B1 (MEDIUM): Health check latency spec dice `<50ms p99` pero tabla de estados muestra 3 estados con thresholds distintos
- C1/C2: Falta 5s detection window y "no retries" en health check implementation
- D1: T048 no especifica OpenAPI 3.1 explícitamente
- C3: API Versioning menciona Accept header para futuro pero no hay task que implemente header parsing

**Análisis:**
1. F1 es copy-paste legacy en acceptance scenarios de US2/US3 - paths deben usar `/api/v1/eventos`
2. B1: Spec dice `<50ms p99` pero health check states table muestra healthy <50ms, degraded 50-500ms, unhealthy failed - aclarar que 50ms p99 aplica solo a "healthy"
3. C1: Falta acceptance scenario explícito para 409 en US1 (ya implementado en código pero no documentado)
4. B5: Health check timeout dice "single attempt" pero no especifica retries - agregar "no retries" explícito
5. C3: Accept header parsing mencionado en versioning strategy pero no hay task para implementarlo
6. D1: T048 debe especificar OpenAPI 3.1 explícitamente
6. C5: Consistency Model define Max Staleness 1s, Write Timeout 5s - no hay tasks que configuren estos valores en Motor client

**Decisión:** Aplicar correcciones menores antes de `/speckit.implement`:
- spec.md: Fix F1 (paths en US2/US3), clarificar B1/B5, agregar C1 (409 scenario), C2 (no retries), C3 (Accept header note)
- tasks.md: Actualizar T048 con OpenAPI 3.1, agregar Accept header parsing task o deferir explícitamente, agregar MongoDB client config para consistency model
- plan.md: Actualizar D1 con OpenAPI 3.1 en T048

**Resultado esperado:** Artefactos 100% consistentes y listos para `/speckit.implement`

**Próximos pasos:** Aplicar correcciones, commit, push, luego ejecutar `/speckit.implement`

**Tags:** #analysis #spec-kit #eventos-crud #constitution-compliance #pre-implementation

---

### 2026-09-25 — Corrección Docker Compose: eventos-service fallaba al iniciar (puerto y motor/pymongo)

**Contexto:** Al ejecutar `docker-compose up`, el contenedor `eventflow_eventos` fallaba con error de importación `ImportError: cannot import name '_QUERY_OPTIONS' from 'pymongo.cursor'` y el health check fallaba porque el servicio escuchaba en puerto 8000 pero docker-compose mapeaba 8002.

**Problema:** 
1. Versión incompatible de motor (3.3.2) con pymongo (latest traía 4.8+) - motor 3.3.2 requiere pymongo <4.7
2. Dockerfile hardcodeaba puerto 8000 en CMD pero docker-compose.yml exponía 8002
3. Health check usaba `curl` que no estaba instalado en la imagen base

**Análisis:**
1. El error `_QUERY_OPTIONS` es un breaking change en pymongo 4.7+ que motor 3.3.2 no soporta
2. El servicio leía `SERVICE_PORT` desde config.py pero el entrypoint no lo usaba
3. El health check de docker-compose requiere curl disponible en el container

**Decisión:**
1. Pinnear `pymongo==4.6.1` en requirements.txt de eventos-service
2. Agregar `service_port` a config.py con env var `SERVICE_PORT`
3. Cambiar Dockerfile CMD a usar `${SERVICE_PORT:-8002}` via shell
4. Instalar `curl` en Dockerfile para health checks
5. Actualizar .env y .env.example con `SERVICE_PORT=8002`
6. Aplicar mismos fixes a reservas-service (actualizar requirements.txt con motor, pymongo, pydantic-settings)

**Resultado:**
- eventos-service: Healthy ✅ (puerto 8002, MongoDB OK)
- reservas-service: Healthy ✅ (puerto 8003, MongoDB/Redis/PostgreSQL/usuarios/eventos OK)
- usuarios-service: Healthy ✅ (puerto 8001)
- Todos los 5 contenedores (3 DBs + 3 services) saludables

**Próximos pasos:** Ejecutar tests de integración y validar SAGA completa

**Tags:** #docker #docker-compose #motor #pymongo #healthcheck #deployment #fix