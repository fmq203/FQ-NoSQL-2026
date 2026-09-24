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