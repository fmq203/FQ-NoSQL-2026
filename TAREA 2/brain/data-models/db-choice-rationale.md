---
name: db-choice-rationale
description: Justificación detallada de elección de bases de datos por microservicio
metadata:
  type: decision
  status: complete
---

# Razonamiento: Elección de Bases de Datos por Entidad

**Última revisión contra el código:** 2026-11-05. Las capacidades que se mencionan como posibles (sharding, búsqueda de texto, particionamiento) son argumentos de la elección, no cosas implementadas; donde importa se aclara.

## Resumen de Asignación

| Entidad | Base Principal | Base Secundaria | Patrón |
|---------|----------------|-----------------|--------|
| Usuario | MongoDB | Redis `redis-cache` (caché de lecturas) | Embedded (historial) |
| Evento | MongoDB | Redis `redis-cache` (caché de lecturas) | Embedded (precios/ubicacion) |
| Reserva | MongoDB | Redis (transacción), PostgreSQL (audit) | Reference |
| Pago | Redis | — | Atomic Lua |
| Auditoría | PostgreSQL | — | Event Sourcing |

---

## Análisis Detallado por Entidad

### 1. Usuario → MongoDB

**Requerimientos:**
- Perfil flexible (campos variables futuros)
- Historial de compras consultado junto al perfil
- Unicidad estricta: email, documento
- Exportación masiva anonimizada (GDPR)

**Por qué MongoDB:**
| Factor | Evaluación |
|--------|------------|
| Esquema flexible | ✅ Campos opcionales futuros (preferencias, teléfono) sin migración |
| Embedded history | ✅ `historial_compras[]` dentro del documento — single query |
| Índices compuestos | ✅ Unique en email + documento, compuestos para listados |
| Export | ✅ Recorrido con cursor (`find({})`); la minimización y el HMAC se hacen en Python |
| Sharding | Posible por `_id` (hash); no usado (un solo nodo) |

**Alternativas descartadas:**
- **PostgreSQL**: Requiere migraciones para campos nuevos, JOIN para historial
- **Redis**: No consultas ad-hoc, no exportación masiva eficiente
- **Cassandra**: Modelo inadecuado para documento anidado variable

---

### 2. Evento → MongoDB + Redis Cache

**Requerimientos:**
- Lecturas masivas de catálogo (alta disponibilidad)
- Aforo dinámico con alta concurrencia
- Precios por categoría atómicos

**Por qué MongoDB:**
| Factor | Evaluación |
|--------|------------|
| Documento único | ✅ Todos los datos del evento en un doc |
| Embedded precios | ✅ Categorías con precio+disponibilidad atómicos |
| Inventario atómico | ✅ `find_one_and_update` con `$elemMatch` + `$inc` sobre la categoría |
| Unicidad | ✅ Índice único en `nombre` |

No hay listado ni búsqueda de eventos implementados (ni índice de texto o de fecha); MongoDB los permitiría sin cambiar el modelo.

**Redis como caché AP de lecturas (`services/lectura_cache.py`):** se cachea el documento completo en `cache:evento:{id}` (instancia `redis-cache`). Fresco 30 s; vencido, se relee de MongoDB; si MongoDB no responde, se sirve la copia vencida (`X-Cache: STALE`, se guarda hasta 1 h). La SAGA la saltea con `Cache-Control: no-cache`. Las escrituras de inventario la invalidan. Usuarios usa el mismo módulo (`cache:usuario:{id}`, 10 min).

**Por qué NO solo Redis:**
- Consultas flexibles a futuro (rangos de fecha, filtros)
- Persistencia duradera de metadatos evento
- Exportación/Reportes requieren query flexible

---

### 3. Reserva → MongoDB + Redis + PostgreSQL

**Requerimientos:**
- **Consistencia fuerte**: No doble venta, unicidad reserva
- **Transacción distribuida**: Usuario + Evento + Pago + Inventario
- **Auditoría completa**: Compliance financiero, debugging
- **Consultas operativas**: Historial usuario, ocupación evento

**Arquitectura Híbrida:**

| Operación | Base | Por Qué |
|-----------|------|---------|
| Validar usuario | HTTP → Usuarios (MongoDB) | Servicio propietario |
| Validar evento + aforo | HTTP → Eventos (MongoDB) | Servicio propietario |
| **Pago + Decremento inventario** | **Redis (Lua)** | **Atomicidad garantizada, sub-ms** |
| Persistir reserva | **MongoDB** | Documento flexible, consulta por usuario/evento |
| **Audit log inmutable** | **PostgreSQL** | **ACID, Event Sourcing, reportes SQL** |

**Por qué MongoDB para Reserva (no PostgreSQL):**
- Documento `saga_log[]` embebido para debugging rápido
- `_id = reserva_id` da la idempotencia sin tabla aparte
- Consultas por `usuario_id` / `evento_id` / `estado` con índices (listado `GET /api/reservar`)
- Sharding por `usuario_id` posible (no usado)

**Por qué Redis para Pago (no MongoDB transacciones):**
| MongoDB Transacciones | Redis Lua |
|----------------------|-----------|
| Multi-document, 2PC-like | Single-threaded, inherentemente atómico |
| ~10-50ms latencia | **< 1ms latencia** |
| Complejidad: sesiones, commit/abort | Simple: script atómico |
| No ideal para alta concurrencia simple | **Diseñado para contadores/locks** |

**Por qué PostgreSQL para Auditoría:**
- ACID estricto para compliance financiero
- Event Sourcing: tabla append-only inmutable
- Consultas analíticas complejas (SQL, JOINs, window functions)
- Particionamiento nativo por tiempo (no usado: una sola tabla)
- Índice GIN para consultar dentro del payload JSONB
- Tooling maduro: pgAdmin, BI tools, replication

---

### 4. Matriz de Decisión Consolidada

| Criterio | MongoDB | Redis | PostgreSQL |
|----------|---------|-------|------------|
| **Modelo de datos** | Documento flexible | Clave-Valor + Estructuras | Relacional estricto |
| **Consistencia** | Eventual (configurable) | Fuerte (single-thread) | ACID completa |
| **Atomicidad multi-op** | Transacciones (4.0+) | **Lua scripts (nativo)** | Transacciones SQL |
| **Consultas ad-hoc** | ✅ Ricas (aggregation) | ❌ Solo key/pattern | ✅ SQL completo |
| **Escalabilidad escritura** | Sharding | Cluster (limitado) | Read replicas / Citus |
| **Latencia típica** | 5-20ms | **< 1ms** | 2-10ms |
| **Persistencia** | WAL + snapshots | AOF + RDB | WAL (crash-safe) |
| **Caso de uso EventFlow** | Usuarios, Eventos, Reservas | Pagos e inventario (`redis`), caché de lecturas (`redis-cache`) | Audit Log, vistas CQRS |

---

## Patrones de Datos Aplicados

### Embedded (Denormalización Controlada)

| Documento | Campo Embedded | Razón |
|-----------|----------------|-------|
| `usuarios` | `historial_compras[]` | Acceso conjunto, cardinalidad baja, atomicidad |
| `eventos` | `ubicacion`, `precios[]` | Siempre juntos, tamaño fijo, actualización atómica |
| `reservas` | `saga_log[]` | Debugging local, inmutable tras confirmación |

### Reference (Normalización)

| Referencia | Desde → Hacia | Razón |
|------------|---------------|-------|
| `reservas.usuario_id` | Reserva → Usuario | Muchos-a-uno, usuario tiene vida independiente |
| `reservas.evento_id` | Reserva → Evento | Muchos-a-uno, evento consultado solo |
| `usuarios.historial_compras[].evento_id` | Embebido → Evento | Junto con `evento_nombre` copiado, para mostrar el historial sin consultar Eventos |

---

## Referencias

- [[db-selection]] — Decisión macro
- [[consistency-strategy]] — Consistencia por operación
- [[saga-flow]] — Uso de Redis en SAGA
- [[event-sourcing-cqrs]] — PostgreSQL para Event Sourcing