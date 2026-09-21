---
name: db-choice-rationale
description: Justificación detallada de elección de bases de datos por microservicio
metadata:
  type: decision
  status: complete
---

# Razonamiento: Elección de Bases de Datos por Entidad

## Resumen de Asignación

| Entidad | Base Principal | Base Secundaria | Patrón |
|---------|----------------|-----------------|--------|
| Usuario | MongoDB | — | Embedded (historial) |
| Evento | MongoDB | Redis (cache) | Embedded (precios/ubicacion) |
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
| Aggregation pipeline | ✅ Exportación anonimizada con `$project`, `$group` |
| Sharding | ✅ Por `_id` (hash) para escalar usuarios |

**Alternativas descartadas:**
- **PostgreSQL**: Requiere migraciones para campos nuevos, JOIN para historial
- **Redis**: No consultas ad-hoc, no exportación masiva eficiente
- **Cassandra**: Modelo inadecuado para documento anidado variable

---

### 2. Evento → MongoDB + Redis Cache

**Requerimientos:**
- Lecturas masivas de catálogo (alta disponibilidad)
- Aforo dinámico con alta concurrencia
- Búsqueda por texto (nombre, descripción, categorías)
- Precios por categoría atómicos

**Por qué MongoDB:**
| Factor | Evaluación |
|--------|------------|
| Documento único | ✅ Todos los datos del evento en un doc |
| Embedded precios | ✅ Categorías con precio+disponibilidad atómicos |
| Text search | ✅ Índice `$text` nativo |
| Consulta por fecha | ✅ Índice rango eficiente |
| TTL/Archivo | ✅ Eventos finalizados movibles a colección archive |

**Redis Cache (Capa Adicional):**
```python
# Cache de disponibilidad (TTL 30s)
async def get_disponibilidad(evento_id):
    cached = await redis.get(f"evento:disp:{evento_id}")
    if cached: return int(cached)
    
    evento = await mongo.eventos.find_one({"_id": evento_id})
    disp = evento["entradas_disponibles"]
    await redis.setex(f"evento:disp:{evento_id}", 30, disp)
    return disp
```

**Por qué NO solo Redis:**
- Consultas complejas (búsqueda texto, rangos fecha, filtros categoría)
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
- Esquema variable (diferentes métodos pago → campos extra)
- Consultas por `usuario_id` + `evento_id` naturales en doc
- Sharding por `usuario_id` para escalar historial

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
- Particionamiento nativo por tiempo
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
| **Caso de uso EventFlow** | Usuarios, Eventos, Reservas | Pagos, Inventario, Cache | Audit Log, Reportes |

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
| `usuarios.historial_compras[].evento_id` | Embebido → Evento | Denormalización para evitar join en exportación |

---

## Referencias

- [[decisions/db-selection]] — Decisión macro
- [[decisions/consistency-strategy]] — Consistencia por operación
- [[architecture/saga-flow]] — Uso de Redis en SAGA
- [[patterns/event-sourcing-cqrs]] — PostgreSQL para Event Sourcing