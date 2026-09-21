# Research: Event Management (Eventos Service)

**Date**: 2026-09-20

## Technical Decisions

### 1. MongoDB + Redis Cache (Cache-Aside Pattern)
**Decision**: MongoDB como source of truth, Redis cache para disponibilidad (TTL 30s)
**Rationale**: 
- Lecturas masivas de catálogo → Redis absorbe carga
- Consistencia eventual aceptable (PDF: "priorizar disponibilidad")
- Cache invalidation en escritura (decremento inventario)

### 2. Inventario en Redis: String Counter + Lua
**Decision**: `inventario:{evento_id}` como STRING + Lua script para decremento atómico
**Rationale**: 
- SAGA Paso 4 requiere atomicidad pago + decremento
- Redis single-threaded = consistencia fuerte inherente
- Lua script ejecuta sin interleaving

### 3. Embedded: ubicacion + precios[] + categorias[]
**Decision**: EMBEDDED en documento evento
**Rationale**: Ver `brain/data-models/event-schema.md`
- Siempre consultados juntos (catálogo, validación)
- precios[]: categoría+precio+disponibles = tupla atómica
- Tamaño fijo pequeño (< 10KB)

### 4. Text Search: MongoDB $text Index
**Decision**: Índice compuesto `nombre`, `descripcion`, `categorias` con pesos
**Rationale**: 
- Búsqueda full-text nativa, sin Elasticsearch
- Pesos: nombre=10, categorias=5, descripcion=1
- Suficiente para catálogo de eventos

### 5. Cache TTL: 30 segundos
**Decision**: `SETEX evento:disp:{evento_id} 30 disponibles`
**Rationale**: 
- Balance consistencia vs performance
- 30s = max staleness aceptable para aforo
- Invalidación proactiva en decremento

### 6. Índices: fecha + estado+fecha + text
**Decision**: 
- `fecha` (1) para listado cartelera ordenado
- `estado` (1), `fecha` (1) compuesto para dashboard admin
- `$text` para búsqueda

## Alternatives Considered

| Decisión | Alternativa | Por qué NO |
|----------|-------------|------------|
| Redis cache | Solo MongoDB | No escala lecturas masivas, latency alta |
| Lua script | Transacción MongoDB | 10-50ms vs <1ms, no atómico pago+inventario |
| Embedded precios | Colección separada `precios` | Requiere $lookup, rompe atomicidad categoría |
| TTL 30s | TTL 300s | Staleness muy alta para aforo |
| TTL 30s | Sin TTL (invalidación manual) | Riesgo cache stale si invalidación falla |
| MongoDB $text | Elasticsearch | Overkill, dependencia extra, MongoDB nativo suficiente |

## Dependencies

- `motor>=3.3.0` - Async MongoDB
- `redis>=5.0.0` - Async Redis con Lua support
- `pymongo>=4.5.0` - Enums, indexes

## Performance Baselines

| Operación | p50 | p95 | p99 |
|-----------|-----|-----|-----|
| Crear evento | 50ms | 150ms | 300ms |
| Obtener evento (cache hit) | 2ms | 10ms | 20ms |
| Obtener evento (cache miss) | 20ms | 50ms | 100ms |
| Cache hit rate | > 90% | - | - |

## Risks & Mitigations

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Cache stale | Media | Overbooking | TTL 30s + invalidación proactiva |
| Redis down | Baja | SAGA falla | Circuit breaker, fallback MongoDB |
| Inventario desync | Media | Overselling | Lua atómico, verificación periódica |
| Text search lento | Baja | Latencia búsqueda | Índices con pesos, limitar resultados |

## References

- `brain/data-models/event-schema.md`
- `brain/data-models/db-choice-rationale.md`
- `brain/architecture/saga-flow.md` - Uso en SAGA paso 3-4
- MongoDB Text Search: https://www.mongodb.com/docs/manual/text-search/
- Redis Lua Scripting: https://redis.io/docs/manual/patterns/scripting/