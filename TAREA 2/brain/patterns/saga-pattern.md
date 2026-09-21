---
name: saga-pattern
description: Implementación del patrón SAGA con Orquestación en EventFlow
metadata:
  type: pattern
  status: complete
---

# SAGA Pattern con Orquestación - EventFlow

## Visión General

El **Servicio de Reservas y Pagos** actúa como **Orquestador Central** del patrón SAGA. Coordina la transacción distribuida de compra de entradas garantizando atomicidad mediante compensaciones.

---

## Arquitectura SAGA

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RESERVAS SERVICE (Orquestador)                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  POST /api/reservar                                                 │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │           CHAIN OF RESPONSIBILITY (6 Handlers)               │   │
│  ├─────────────────────────────────────────────────────────────┤   │
│  │ 1. ValidadorDeDatos      ──► Validación local               │   │
│  │ 2. ValidadorInventario   ──► HTTP GET Usuarios Service      │   │
│  │ 3. ValidadorEvento       ──► HTTP GET Eventos Service       │   │
│  │ 4. ProcesadorPago        ──► Redis Lua (ATÓMICO)            │   │
│  │ 5. ConfirmadorReserva    ──► MongoDB INSERT                 │   │
│  │ 6. Auditor               ──► PostgreSQL INSERT (Event Log)  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│       │                                                             │
│       ▼                                                             │
│  COMPENSACIONES AUTOMÁTICAS si falla Paso 4-5                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6 Pasos de la Transacción Exitosa

| Paso | Handler | Acción | Servicio/BD | Tipo Consistencia |
|------|---------|--------|-------------|-------------------|
| 1 | **ValidadorDeDatos** | Validar UUIDs, cantidad>0, método pago enum | Local | - |
| 2 | **ValidadorInventario** | GET `/api/usuarios/{id}` | Usuarios Service | Eventual (read) |
| 3 | **ValidadorEvento** | GET `/api/eventos/{id}` + aforo | Eventos Service | Eventual (read) |
| 4 | **ProcesadorPago** | **Lua Redis**: Pago + DECRBY inventario | Redis | **Fuerte (Atómico)** |
| 5 | **ConfirmadorReserva** | INSERT MongoDB reserva + saga_log | MongoDB | **Fuerte (Majority)** |
| 6 | **Auditor** | INSERT PostgreSQL event_log | PostgreSQL | **Fuerte (ACID)** |

---

## Atomicidad Crítica: Paso 4 (Redis Lua Script)

```lua
-- KEYS[1] = inventario:evento_id
-- KEYS[2] = pago:reserva_id
-- ARGV[1] = cantidad, ARGV[2] = reserva_id, ARGV[3] = usuario_id
-- ARGV[4] = monto, ARGV[5] = metodo_pago

local disponible = tonumber(redis.call('GET', KEYS[1]) or '0')
if disponible < tonumber(ARGV[1]) then
    return {0, 'INVENTARIO_INSUFICIENTE'}
end

-- TRANSACCIÓN ATÓMICA: Verificar + Decrementar + Registrar Pago
redis.call('DECRBY', KEYS[1], ARGV[1])
redis.call('HSET', KEYS[2], 
    'reserva_id', ARGV[2], 'usuario_id', ARGV[3],
    'monto', ARGV[4], 'metodo_pago', ARGV[5],
    'estado', 'confirmado', 'timestamp', os.date('!%Y-%m-%dT%H:%M:%SZ')
)
redis.call('EXPIRE', KEYS[2], 86400)

return {1, 'OK'}
```

**Por qué Lua en Redis:**
- ✅ Atomicidad garantizada (single-threaded Redis)
- ✅ < 1ms latencia
- ✅ Verificación + Decremento + Registro en UNA operación
- ✅ Rollback interno si falla verificación (0 cambios)

---

## Compensaciones (Rollback) Automáticas

```mermaid
flowchart TD
    Fail[Fallo en Paso N] --> Check{N <= 3?}
    
    Check -->|Sí: Validaciones| NoComp[Sin compensación\n(Solo lectura HTTP)]
    Check -->|Paso 4: Lua| LuaRollback[Rollback interno Lua\n(Atómico, 0 cambios)]
    Check -->|Paso 5: MongoDB| MongoRollback[1. DELETE reserva\n2. Lua compensación\n   INCRBY + DEL]
    Check -->|Paso 6: PostgreSQL| PgWarn[Log WARNING only\nReserva YA confirmada]
    
    NoComp --> End[Fin]
    LuaRollback --> End
    MongoRollback --> End
    PgWarn --> End
```

### Detalle por Paso

| Fallo en | Compensación | Implementación |
|----------|--------------|----------------|
| **Paso 1-3** (Validaciones) | Ninguna | Solo lectura HTTP, sin side effects |
| **Paso 4** (Lua Pago) | Automática en Lua | Si `disponible < cantidad`: retorna error, 0 cambios |
| **Paso 5** (MongoDB) | **SÍ - Crítica** | 1. `DELETE reserva` (si insertó)<br>2. `EVAL compensar_pago_inventario.lua` (INCRBY inventario + DEL pago) |
| **Paso 6** (PostgreSQL) | **NO** | Log `WARNING`, reserva ya confirmada, cliente notificado 201 |

### Lua Compensación (Paso 5 Fallo)

```lua
-- KEYS[1] = inventario:evento_id
-- KEYS[2] = pago:reserva_id
-- ARGV[1] = cantidad

redis.call('INCRBY', KEYS[1], ARGV[1])  -- Restaurar inventario
redis.call('DEL', KEYS[2])               -- Eliminar registro pago
return {1, 'COMPENSACION_OK'}
```

---

## Estados de la SAGA

| Estado | Descripción | Transición |
|--------|-------------|------------|
| `STARTED` | SAGA iniciada | → `USUARIO_VALIDADO` |
| `USUARIO_VALIDADO` | Usuario existe | → `EVENTO_VALIDADO` |
| `EVENTO_VALIDADO` | Evento existe + aforo | → `PAGO_PROCESADO` |
| `PAGO_PROCESADO` | Pago + inventario OK | → `RESERVA_CONFIRMADA` |
| `RESERVA_CONFIRMADA` | Reserva en MongoDB | → `SAGA_COMPLETED` |
| `SAGA_COMPLETED` | Todo OK + Audit log | **FINAL** |
| `SAGA_FAILED` | Fallo + compensaciones | **FINAL** |
| `COMPENSATING` | Ejecutando rollback | → `SAGA_FAILED` |

---

## Manejo de Errores por Tipo

| Error | HTTP Status | Paso | Compensación | Reintento |
|-------|-------------|------|--------------|-----------|
| Usuario no encontrado | 404 | 2 | Ninguna | No |
| Evento no encontrado | 404 | 3 | Ninguna | No |
| Inventario insuficiente | 409 | 3/4 | Lua interna / 409 | No (manual) |
| Pago falla (Redis) | 500 | 4 | Automática Lua | Sí (idempotente) |
| MongoDB error | 500 | 5 | Lua compensación + DELETE | Sí |
| PostgreSQL error | 500 | 6 | Log warning only | Sí (async retry) |

---

## Idempotencia

- **Clave**: `reserva_id` (UUID v4) generado al inicio
- **Redis**: `pago:{reserva_id}` evita doble procesamiento
- **MongoDB**: `_id = reserva_id` (unique index)
- **PostgreSQL**: `aggregate_id` permite detectar duplicados

```python
# Verificación idempotencia al inicio
async def verificar_idempotencia(reserva_id: UUID) -> bool:
    # Check MongoDB
    if await mongo.reservas.find_one({"_id": reserva_id}):
        return True
    # Check Redis
    if await redis.exists(f"pago:{reserva_id}"):
        return True
    # Check PostgreSQL
    if await pg.fetchval("SELECT 1 FROM event_log WHERE aggregate_id = $1", reserva_id):
        return True
    return False
```

---

## Correlation ID para Tracing

```python
# Generado al inicio
correlation_id = uuid4()

# Propagado en:
# 1. Logs: logger.info(..., correlation_id=correlation_id)
# 2. HTTP Headers: X-Correlation-ID
# 3. PG event_log: metadata.correlation_id
# 4. Redis: HSET pago:{id} correlation_id
```

---

## Referencias

- `brain/architecture/saga-flow.md` - Diagrama completo + Lua scripts
- `brain/architecture/chain-of-responsibility.md` - Handlers implementados
- `brain/data-models/reservation-schema.md` - Esquemas MongoDB/Redis/PG
- `brain/patterns/event-sourcing-cqrs.md` - Event Sourcing + CQRS
- `brain/decisions/consistency-strategy.md` - Consistencia fuerte en SAGA