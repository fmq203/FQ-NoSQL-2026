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
- Escrituras (reservas, pagos): Priorizar **consistencia fuerte** → ACID, no doble venta

---

## Decisión: Consistencia Híbrida por Operación

| Operación | Nivel de Consistencia | Implementación | Justificación |
|-----------|----------------------|----------------|---------------|
| **GET /api/usuarios/{id}** | Eventual | MongoDB read preference `secondaryPreferred` | Alta disponibilidad, tolerancia a particiones, latencia < 50ms |
| **GET /api/eventos/{id}** | Eventual | MongoDB read preference `secondaryPreferred` | Lecturas masivas, cache Redis opcional |
| **GET /api/usuarios (listado)** | Eventual | MongoDB paginado + índices | Escalabilidad horizontal |
| **POST /api/reservar** | **Fuerte (Linealizable)** | SAGA Orchestration + Redis Lua atómico + MongoDB + PostgreSQL | Unicidad reserva, integridad financiera, no doble venta |

---

## Modelo de Consistencia por Base de Datos

### MongoDB (Usuarios, Eventos, Reservas)

```python
# Configuración de cliente para lecturas eventuales
client = MongoClient(
    MONGODB_URI,
    read_preference=ReadPreference.SECONDARY_PREFERRED,  # Eventual para lecturas
    write_concern=WriteConcern(w='majority', j=True)     # Fuerte para escrituras
)

# Para reservas (escritura fuerte):
db.reservas.with_options(write_concern=WriteConcern(w='majority', j=True))
```

| Colección | Read Preference | Write Concern | Índices Críticos |
|-----------|-----------------|---------------|------------------|
| `usuarios` | `secondaryPreferred` | `majority` | `email` (unique), `nro_documento` (unique) |
| `eventos` | `secondaryPreferred` | `majority` | `fecha`, `estado` |
| `reservas` | `primary` (consistencia fuerte) | `majority` + `journal` | `usuario_id`, `evento_id`, `estado` |

### Redis (Pagos, Inventario)

```python
# Redis: Consistencia fuerte inherentemente (single-threaded)
# Lua scripts = atomicidad garantizada
# No hay réplicas de lectura en configuración actual
```

- **Consistencia**: Fuerte (single-threaded event loop)
- **Persistencia**: AOF (Append Only File) + RDB snapshots
- **Replicación**: Master-replica async (no usado para lecturas en este diseño)

### PostgreSQL (Audit Log)

```python
# ACID completo por defecto
# Isolation level: READ COMMITTED (default)
# Para auditoría: SERIALIZABLE si requiere consistencia estricta en reportes
```

---

## Patrones de Consistencia Aplicados

### 1. Read Your Writes (MongoDB)

```python
# Tras crear usuario, leerlo inmediatamente requiere primary
async def crear_usuario(usuario: UsuarioCreate):
    result = await db.usuarios.insert_one(usuario_doc)
    # Leer con primary para garantizar visibilidad inmediata
    created = await db.usuarios.with_options(read_preference=ReadPreference.PRIMARY).find_one({'_id': result.inserted_id})
    return created
```

### 2. Saga con Compensación (Reservas)

```python
# Consistencia eventual entre servicios, fuerte dentro de cada paso
# Paso 4 (Redis): Fuerte atómico via Lua
# Paso 5 (MongoDB): Fuerte con write_concern majority
# Paso 6 (PostgreSQL): Fuerte ACID
# Si falla paso 5 → Compensación paso 4 (eventual pero garantizada)
```

### 3. Eventual Consistency para Exportación

```python
# Exportación anonimizada: tolera datos ligeramente stale
# No afecta transacciones, solo análisis
async def exportar_usuarios():
    # read_preference=SECONDARY_PREFERRED por defecto
    cursor = db.usuarios.find({}, {'historial_compras': 1})
    # Anonimización en aplicación
```

---

## Trade-offs Aceptados

| Trade-off | Decisión | Impacto |
|-----------|----------|---------|
| **Lectura stale en usuarios/eventos** | Aceptado | Usuario ve evento creado hace 100ms — aceptable para catálogo |
| **Latencia escritura reservas** | Priorizada consistencia | ~200-500ms por SAGA completa — aceptable para compra |
| **Complejidad compensaciones** | Necesaria | Rollback automático en Redis/MongoDB, manual en PostgreSQL |
| **No distributed transactions** | Evitado (2PC) | SAGA pattern más escalable y resiliente |

---

## Monitoreo de Consistencia

```python
# Métricas a observar
- replica_lag_ms (MongoDB): < 100ms objetivo
- redis_replication_lag: N/A (single master)
- saga_duration_ms: P99 < 500ms
- compensacion_rate: < 1% de transacciones
- audit_log_gap: 0 eventos perdidos
```

---

## Referencias

- [[architecture/saga-flow]] — Implementación SAGA con consistencia
- [[architecture/data-flow]] — Flujos por nivel de consistencia
- [[decisions/db-selection]] — Bases de datos elegidas