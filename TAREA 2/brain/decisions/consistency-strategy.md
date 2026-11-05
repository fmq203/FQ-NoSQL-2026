---
name: consistency-strategy
description: Estrategia de consistencia para EventFlow
metadata:
  type: decision
  status: complete
---

# Decisión: Estrategia de Consistencia

## Problema

EventFlow tiene requerimientos de consistencia **diferenciados** por operación:
- Lecturas (usuarios, eventos): Priorizar **disponibilidad y escalabilidad** → Consistencia eventual
- Escrituras (reservas, pagos): Priorizar **consistencia fuerte** → no doble venta, no doble cobro

---

## Decisión: Consistencia Híbrida por Operación

| Operación | Nivel de Consistencia | Implementación | Justificación |
|-----------|----------------------|----------------|---------------|
| **GET /api/usuarios/{id}** | Eventual (AP) | Caché Redis stale-if-error + MongoDB | Disponibilidad ante caída de MongoDB; caché fresco 30 s, copia vencida hasta 10 min |
| **GET /api/eventos/{id}** | Eventual (AP) | Caché Redis stale-if-error + MongoDB | Lecturas masivas; fresco 30 s, `STALE` hasta 1 h si MongoDB cae; la SAGA lo saltea con `Cache-Control: no-cache` |
| **GET /api/usuarios (listado)** | Eventual | MongoDB paginado + índices | Escalabilidad horizontal |
| **POST /api/reservar** | **Fuerte** | Redis Lua atómico (chequeo + decremento + pago en un paso) + idempotencia por `reserva_id` + SAGA con compensación + `w=majority`/journal | Unicidad de reserva, no doble venta, no doble cobro |

> **Estado real de la implementación (revisado 2026-11-05):** el `docker-compose.yml` levanta **un solo nodo** de MongoDB, sin replica set. Las read preferences de la tabla de abajo y `w=majority` + `journal` están configurados en los clientes, pero en un nodo standalone la read preference se ignora y `majority` = ese nodo: la lectura eventual **no se ejercita** y el `replica_lag_ms` de abajo no aplica. La disponibilidad de lecturas (AP) se demuestra con el caché Redis (`lectura_cache.py`, `X-Cache: STALE` con MongoDB caído). Si MongoDB cae y no hay entrada en caché (o la lectura es estricta, `Cache-Control: no-cache`), Usuarios y Eventos responden `503 SERVICE_UNAVAILABLE` con `Retry-After: 5`. Redis tampoco tiene réplica.

---

## Modelo de Consistencia por Base de Datos

### MongoDB (Usuarios, Eventos, Reservas)

Configuración real de los clientes (`*/src/services/mongodb.py`, `reservas-service/src/services/mongo.py`):

| Colección | Read Preference | Write Concern | Índices clave |
|-----------|-----------------|---------------|---------------|
| `usuarios` | `_ServerMode(2, ..., 1)` = **`SECONDARY`** con `maxStalenessSeconds=1` | `majority` + `journal` | `email` (único), `nro_documento` (único) |
| `eventos` | `secondaryPreferred` + `maxStalenessSeconds=1` (en la URI) | `majority` + `journal` | `nombre` (único), `estado` |
| `reservas` | `primary` (cliente Motor por defecto) | `majority` + `journal` (`with_options` en la colección) | `numero_confirmacion` (único), `usuario_id`, `evento_id` |

> **Ojo si se pasa a replica set:** con un nodo standalone estas preferencias no tienen efecto, pero en un replica set fallarían: MongoDB rechaza `maxStalenessSeconds` menor a 90 (afecta a Usuarios y a Eventos), y además `SECONDARY` (Usuarios) no cae al primario si no hay secundarios disponibles. Antes de agregar réplicas habría que pasar ambos a `secondaryPreferred` con `maxStalenessSeconds >= 90`.

### Redis (DB 0: pagos e inventario; DB 1: caché de lecturas)

```python
# Redis: Consistencia fuerte inherentemente (single-threaded)
# Lua scripts = atomicidad garantizada
# No hay réplicas de lectura en configuración actual
```

- **Consistencia**: Fuerte (single-threaded event loop)
- **Persistencia**: AOF (`redis-server --appendonly yes`)
- **Replicación**: ninguna (un solo nodo)

### PostgreSQL (Audit Log)

```python
# ACID; cada INSERT del event_log es su propia transacción (autocommit, READ COMMITTED)
# La escritura es no bloqueante para la SAGA: si falla, warning y la compra sigue
```

---

## Patrones de Consistencia Aplicados

### 1. Read Your Writes

No hay lecturas explícitas desde el primario después de escribir: con un solo nodo no hace falta. Lo que sí se hace es **invalidar la caché** (`cache:evento:{id}`, `cache:usuario:{id}`) tras cada escritura que cambia el dato, y la SAGA lee siempre sin caché (`Cache-Control: no-cache`). Con un replica set habría que leer del primario en el camino transaccional.

### 2. Saga con Compensación (Reservas)

```python
# Consistencia eventual entre servicios, fuerte dentro de cada paso
# Paso 4 (Redis): atómico vía Lua; luego sincroniza Eventos por HTTP
#   si esa sincronización falla → Lua revierte Redis
# Paso 5 (MongoDB): w=majority + journal
#   si falla → Lua revierte Redis + incrementar-inventario en Eventos
# event_log (PostgreSQL): no bloqueante
```

### 3. Eventual Consistency para Exportación

```python
# Exportación anonimizada: tolera datos ligeramente stale
# No afecta transacciones, solo análisis
async def exportar_anonimizado():
    cursor = collection.find({})          # recorrido completo
    # minimización + seudónimo HMAC en la aplicación
```

---

## Trade-offs Aceptados

| Trade-off | Decisión | Impacto |
|-----------|----------|---------|
| **Lectura stale en usuarios/eventos** | Aceptado | Hasta 30 s normalmente; hasta 10 min (usuarios) o 1 h (eventos) si MongoDB está caído — aceptable para catálogo, nunca para comprar |
| **Latencia escritura reservas** | Priorizada consistencia | ≈ 100 ms una SAGA aislada; satura en ≈ 50 req/s (no se cumple 100 req/s con p99 < 1 s) |
| **Complejidad compensaciones** | Necesaria | Inline en los pasos 4 y 5 (Redis + inventario de Eventos). El event_log no se revierte: registra la compensación |
| **No distributed transactions** | Evitado (2PC) | SAGA pattern más escalable y resiliente |

---

## Monitoreo de Consistencia

Métricas Prometheus reales de Reservas (`GET /metrics`): `saga_total`, `saga_duration_seconds`, `saga_compensation_total`, `idempotency_hit_total`, `circuit_breaker_state`, `db_operation_duration_seconds`, `http_request_duration_seconds`. En PostgreSQL: vistas `tasa_exito_saga` y `compensaciones_por_tipo`.

No hay métrica de lag de réplica (no hay réplicas).

---

## Referencias

- [[saga-flow]] — Implementación SAGA con consistencia
- [[data-flow]] — Flujos por nivel de consistencia
- [[decisions/db-selection]] — Bases de datos elegidas