# Research: User Management (Usuarios Service)

**Date**: 2026-09-20

## Technical Decisions

### 1. MongoDB Driver: Motor (Async) vs PyMongo (Sync)
**Decision**: Motor (async)
**Rationale**: FastAPI es async nativo. Motor permite concurrencia real sin bloquear event loop. PyMongo con threads añade overhead y complejidad.

### 2. Read Preference: secondaryPreferred
**Decision**: `ReadPreference.SECONDARY_PREFERRED` para lecturas (GET listar, obtener, exportar)
**Rationale**: Requerimiento PDF: "priorizará la disponibilidad y la tolerancia a particiones, aceptando la consistencia eventual". secondaryPreferred lee de secundarios si disponibles, fallback a primary.

### 3. Write Concern: Majority + Journal
**Decision**: `WriteConcern(w='majority', j=True)` para escrituras (POST crear)
**Rationale**: Consistencia fuerte en creación (unicidad email/documento). Majority asegura replicación, journal asegura durabilidad en disco.

### 4. Embedded vs Reference: historial_compras[]
**Decision**: EMBEDDED
**Rationale**: Ver `brain/data-models/user-schema.md` y `brain/data-models/db-choice-rationale.md`.
- Cardinalidad one-to-few (< 50 típicas)
- Acceso conjunto frecuente (perfil + historial)
- Atomicidad: `$push` + `$slice` en single-doc update
- Límite 16MB: 50 compras × ~2KB = 100KB << 16MB

### 5. Anonimización: SHA-256 + Salt
**Decision**: `hashlib.sha256(f"{usuario_id}{SALT}".encode()).hexdigest()`
**Rationale**: 
- Irreversible (one-way)
- Determinista (mismo usuario = mismo hash para deduplicación analítica)
- Salt configurable via env (rotación, anti-rainbow tables)
- No requiere clave secreta (vs HMAC)

### 6. Exportación: Streaming Response
**Decision**: `StreamingResponse` con async generator
**Rationale**: 
- 100k+ usuarios no caben en memoria
- JSON: `json.dumps()` por item + `\n` (NDJSON)
- CSV: `csv.writer` streaming
- Backpressure handled por ASGI server

### 7. Índices Únicos: email + nro_documento
**Decision**: Unique indexes en MongoDB (no aplicación-level)
**Rationale**: 
- Atomicidad garantizada por BD
- Race condition: dos requests simultáneos → uno falla con DuplicateKeyError
- Más simple y confiable que lock distribuido

## Alternatives Considered

| Decisión | Alternativa | Por qué NO |
|----------|-------------|------------|
| Motor | PyMongo + run_in_executor | Thread pool overhead, no native async |
| secondaryPreferred | primary | No escala lecturas, no tolera particiones |
| Embedded historial | Colección separada `compras` | Requiere $lookup/join, rompe atomicidad usuario+historial |
| SHA-256 | UUID v5 (namespace) | UUID v5 reversible si se conoce namespace |
| Streaming | Cargar todo en RAM | OOM en exportaciones grandes |
| Unique index | Check-then-insert app-level | Race condition inevitable |

## Dependencies

- `motor>=3.3.0` - Async MongoDB driver
- `pymongo>=4.5.0` - Para WriteConcern, ReadPreference enums
- `email-validator>=2.1.0` - Requerido por Pydantic EmailStr
- `python-dotenv` - Configuración por entorno

## Performance Baselines (Target)

| Operación | p50 | p95 | p99 |
|-----------|-----|-----|-----|
| Crear usuario | 30ms | 100ms | 200ms |
| Obtener usuario | 15ms | 50ms | 100ms |
| Listar 10 usuarios | 20ms | 100ms | 200ms |
| Exportar 10k (stream) | - | < 2s | < 5s |

## Risks & Mitigations

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Replica lag alto | Media | Lecturas stale | Monitorear `replica_lag_ms`, alertar > 1s |
| Exportación OOM | Baja | Crash servicio | Streaming obligatorio, batch_size=1000 |
| DuplicateKeyError frecuente | Media | 409 errors | Manejo graceful, retry con backoff en cliente |
| Salt hardcodeado | Alta | Seguridad | Variable de entorno obligatoria en prod |

## References

- `brain/decisions/db-selection.md`
- `brain/decisions/consistency-strategy.md`
- `brain/data-models/user-schema.md`
- `brain/data-models/db-choice-rationale.md`
- MongoDB Motor docs: https://motor.readthedocs.io/
- Pydantic EmailStr: https://docs.pydantic.dev/latest/usage/types/#emailstr