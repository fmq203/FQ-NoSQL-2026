---
name: reservation-schema
description: Schema de Reserva en Redis (Transacciones de Pagos)
metadata:
  type: specification
  status: draft
---

# Schema — Reserva (Redis)

## Estructura de Datos en Redis

### 1. Transacción Temporal (durante procesamiento)

```
Key: txn:{uuid}
Type: Hash

Content:
{
  "usuario_id": "65a1b2c3d4e5f6g7h8i9j0k1",
  "evento_id": "65a1b2c3d4e5f6g7h8i9j0k2",
  "cantidad": 2,
  "precio_total": 300.00,
  "metodo_pago": "tarjeta_credito",
  "estado": "en_proceso" | "completada" | "fallida",
  "timestamp_inicio": 1695206730,
  "timestamp_expiracion": 1695206735  // 5 segundos TTL
}
```

**TTL:** 5 segundos (failsafe — si no termina, se limpia)

---

### 2. Reserva Confirmada

```
Key: res:{reserva_id}
Type: Hash

Content:
{
  "usuario_id": "65a1b2c3d4e5f6g7h8i9j0k1",
  "evento_id": "65a1b2c3d4e5f6g7h8i9j0k2",
  "cantidad": 2,
  "precio_total": 300.00,
  "numero_confirmacion": "CONF-2026092010053012345",
  "estado": "confirmada",
  "timestamp_confirmacion": 1695206790,
  "timestamp_expiracion": 1735000000  // ~3 meses
}
```

**TTL:** 90 días (caché caliente)

---

### 3. Índice de Transacciones por Usuario

```
Key: user:{usuario_id}:reservas
Type: Sorted Set

Members: reserva_id (score = timestamp)
```

**Uso:** Obtener historial rápido de reservas del usuario

---

## Operación Crítica: Transacción Atómica (Lua Script)

```lua
-- Lua Script ejecutado ATOMICALLY en Redis
-- Garantiza: Pago procesado Y inventario decrementado, o ambos fallan

-- INPUT
local usuario_id = ARGV[1]
local evento_id = ARGV[2]
local cantidad = tonumber(ARGV[3])
local precio_total = tonumber(ARGV[4])

-- STEP 1: Validar inventario en TEMP cache
local inventario_key = "evento:" .. evento_id .. ":disponibles"
local disponibles = tonumber(redis.call('GET', inventario_key))

if not disponibles or disponibles < cantidad then
  return { err = "Inventario insuficiente" }
end

-- STEP 2: Procesar pago (simular validación)
-- En producción: llamar API de pagos externa con timeout
local pago_id = "pag_" .. redis.call('INCR', 'pago:counter')

-- STEP 3: Decrementar inventario (ATÓMICO)
redis.call('DECRBY', inventario_key, cantidad)

-- STEP 4: Registrar transacción completada
local reserva_id = "res_" .. redis.call('INCR', 'reserva:counter')
redis.call('HSET', 'res:' .. reserva_id,
  'usuario_id', usuario_id,
  'evento_id', evento_id,
  'cantidad', cantidad,
  'precio_total', precio_total,
  'estado', 'confirmada'
)

-- STEP 5: Registrar en índice de usuario
redis.call('ZADD', 'user:' .. usuario_id .. ':reservas',
  redis.call('TIME')[1], reserva_id
)

-- STEP 6: Establecer TTL
redis.call('EXPIRE', 'res:' .. reserva_id, 7776000)  -- 90 días

return { ok = reserva_id }
```

**Garantía:** Todo o nada (transacción atómica en Redis)

---

## Compensaciones (En caso de fallo)

Si la transacción falla en MongoDB (Step 5):

```lua
-- Rollback en Redis
redis.call('DEL', 'res:' .. reserva_id)
redis.call('INCR', inventario_key)  -- Liberar inventario
redis.call('ZREM', 'user:' .. usuario_id .. ':reservas', reserva_id)
```

---

## Consultas

### Obtener reserva
```
GET res:{reserva_id}
```

### Historial del usuario (últimas 10)
```
ZREVRANGE user:{usuario_id}:reservas 0 9
```

---

## Performance

- **Latencia:** < 10ms (in-memory)
- **Throughput:** Cientos de miles de TPS
- **Atomicidad:** Garantizada por Lua scripts
