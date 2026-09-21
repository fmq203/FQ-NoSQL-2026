# Research: Reservation & Payment (Reservas Service)

**Date**: 2026-09-20

## Technical Decisions

### 1. SAGA Orchestration (Centralized)
**Decision**: Reservas Service como Orquestador Central, no coreografía
**Rationale**: 
- PDF requiere: "Servicio de Reservas y Pagos debe actuar como un Orquestador Central"
- Visibilidad completa del flujo, debugging fácil
- Compensaciones ordenadas y determinísticas
- Single point of failure aceptable (stateless, escalable horizontal)

### 2. Chain of Responsibility para Validaciones
**Decision**: 6 handlers encadenados: Datos → Usuario → Evento → Pago → Reserva → Auditoría
**Rationale**: 
- PDF requiere: "utilizar el patrón Chain of Responsibility para estructurar esta lógica"
- Separación de responsabilidades, testabilidad unitaria
- Extensible: agregar validaciones = nuevo handler
- Orden garantizado, compensaciones en reversa natural

### 3. Redis Lua Scripts para Atomicidad Pago+Inventario
**Decision**: Single Lua script ejecuta verificación + DECRBY + HSET atómicamente
**Rationale**: 
- Requerimiento: "procesar pago (Redis - atomic)", "no doble venta"
- Redis single-threaded = consistencia fuerte inherente
- < 1ms latencia vs 10-50ms transacciones MongoDB
- Rollback atómico interno si falla verificación

### 4. Tres Bases de Datos Políglotas
| Operación | Base | Justificación |
|-----------|------|---------------|
| Pago + Inventario | Redis (Lua) | Atomicidad sub-ms, contadores |
| Reserva persistente | MongoDB | Documento flexible, saga_log embedded, consultas por usuario/evento |
| Audit Log inmutable | PostgreSQL | ACID, Event Sourcing, SQL analytics, compliance |

**Rationale**: Ver `brain/decisions/db-selection.md` y `brain/data-models/db-choice-rationale.md`

### 5. Compensaciones Automáticas (Rollback)
**Decision**: 
- Fallo Paso 4 (Lua): Rollback interno atómico (0 cambios)
- Fallo Paso 5 (MongoDB): Lua compensación `INCRBY inventario + DEL pago`
- Fallo Paso 6 (PostgreSQL): Log warning ONLY, NO rollback

**Rationale**: 
- Reserva ya confirmada en MongoDB → cliente ya recibió 201
- Auditoría es observabilidad, no requisito de negocio
- Evita complejidad rollback distribuido por fallo de logging

### 6. Event Sourcing + CQRS en PostgreSQL
**Decision**: Tabla `event_log` append-only con todos los pasos SAGA
**Rationale**: 
- PDF opcional: "Event Sourcing y CQRS... planteen un escenario beneficioso"
- Compliance financiero: auditoría inmutable
- CQRS natural: Escritura→event_log, Lectura operativa→MongoDB, Analítica→SQL views
- Correlation ID para tracing distribuido

### 7. Idempotencia via reserva_id (UUID v4)
**Decision**: `reserva_id` generado al inicio = clave idempotencia en todas las BDs
**Rationale**: 
- Reintentos seguros (red timeout, cliente reenvía)
- MongoDB: `_id = reserva_id` unique
- Redis: `pago:{reserva_id}` evita doble procesamiento
- PostgreSQL: `aggregate_id` permite detectar duplicados

### 8. Correlation ID para Tracing
**Decision**: UUID generado al inicio, propagado en logs, HTTP headers, PG event_log
**Rationale**: Debugging distribuido, vincular SAGA completa across services

## Alternatives Considered

| Decisión | Alternativa | Por qué NO |
|----------|-------------|------------|
| SAGA Orchestration | Coreografía (eventos) | PDF requiere orquestador central, visibilidad, debugging |
| Chain of Responsibility | If/else secuencial | PDF requiere patrón explícito, testabilidad, extensibilidad |
| Redis Lua | MongoDB Transacciones | 10-50ms vs <1ms, no atómico pago+inventario simple |
| 3 DBs políglotas | Solo MongoDB | No garantiza atomicidad pago+inventario sin complejidad |
| PostgreSQL Event Sourcing | Solo MongoDB saga_log | ACID compliance, SQL analytics, particionamiento nativo |
| Compensación PG = warning | Rollback completo | Reserva ya confirmada, cliente ya notificado |
| UUID v4 reserva_id | Secuencia DB | Distribuido, sin coordinación, idempotencia natural |

## Dependencies

- `motor>=3.3.0` - MongoDB async
- `redis>=5.0.0` - Redis async + Lua scripts
- `psycopg[binary]>=3.2.6` / `asyncpg` - PostgreSQL async
- `httpx>=0.25.0` - HTTP clients async con timeouts/retries
- `sqlalchemy>=2.0.0` - ORM opcional para PG

## Performance Baselines

| Operación | p50 | p95 | p99 |
|-----------|-----|-----|-----|
| SAGA completa (éxito) | 200ms | 500ms | 800ms |
| Lua script Redis | 0.5ms | 1ms | 2ms |
| HTTP Usuarios/Eventos | 10ms | 50ms | 100ms |
| MongoDB insert | 5ms | 20ms | 50ms |
| PostgreSQL insert | 3ms | 10ms | 20ms |

## Risks & Mitigations

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Double booking | Baja | Crítico | Lua atómico + unique index reserva_id |
| Inventario negativo | Baja | Crítico | Lua valida antes de DECRBY |
| SAGA timeout | Media | Partial failure | Timeouts por paso, compensaciones |
| Redis unavailable | Baja | Service down | Circuit breaker, 503 graceful |
| PG audit falla | Media | Log loss | Warning only, no bloquear reserva |
| Race condition idempotencia | Baja | Duplicados | Check-then-act con unique constraints |

## References

- `brain/architecture/saga-flow.md` - Flujo completo 6 pasos + compensaciones
- `brain/architecture/chain-of-responsibility.md` - 6 handlers implementados
- `brain/decisions/db-selection.md` - 3 DBs justificadas
- `brain/data-models/reservation-schema.md` - Esquemas MongoDB/Redis/PG
- `brain/data-models/db-choice-rationale.md` - Rationale multi-DB
- `brain/patterns/event-sourcing-cqrs.md` - Event Sourcing + CQRS (pendiente)