---
name: reservation-schema
description: Esquema de datos de Reserva en MongoDB, Redis y PostgreSQL
metadata:
  type: specification
  status: complete
---

# Esquema de Reserva — MongoDB + Redis + PostgreSQL

**Última revisión contra el código:** 2026-11-05 (`reservas-service/src/models/reserva.py`, `chain/validators.py`, `services/redis_pago.py`, `services/mongo.py`, `services/postgresql.py`)

## MongoDB: Colección `eventflow.reservas`

### Documento real

```json
{
  "_id": { "$binary": "<UUID = reserva_id>" },
  "usuario_id": { "$binary": "<UUID>" },
  "evento_id": { "$binary": "<UUID>" },
  "cantidad": 2,
  "categoria": "general",
  "metodo_pago": "tarjeta",
  "monto_total": 10000,
  "numero_confirmacion": "CONF-20261105-52066ECC",
  "estado": "confirmada",
  "creado_en": { "$date": "2026-11-05T01:26:07.442Z" },
  "saga_log": [
    { "paso": "VALIDAR_DATOS", "timestamp": "2026-11-05T01:26:07.386565Z", "exitoso": true, "detalles": "Datos válidos" },
    { "paso": "VALIDAR_USUARIO", "timestamp": "...", "exitoso": true, "detalles": "Usuario validado" },
    { "paso": "VALIDAR_EVENTO", "timestamp": "...", "exitoso": true, "detalles": "Evento validado, aforo disponible (general): 100" },
    { "paso": "PROCESAR_PAGO", "timestamp": "...", "exitoso": true, "detalles": "Pago procesado: 10000.0" },
    { "paso": "RESERVA_CONFIRMADA", "timestamp": "...", "exitoso": true }
  ]
}
```

Solo se guardan reservas **confirmadas**: si la SAGA falla antes del paso 5 no hay documento (el rastro queda en `event_log`). El `saga_log` no guarda datos personales (antes guardaba el nombre del usuario; se quitó).

### Campos

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `_id` | UUID | `reserva_id`: clave de idempotencia (la manda el cliente o se genera) |
| `usuario_id` | UUID | Referencia a `eventflow.usuarios` |
| `evento_id` | UUID | Referencia a `eventflow.eventos` |
| `cantidad` | Int | > 0 |
| `categoria` | String | Categoría de precio del evento |
| `metodo_pago` | String | `tarjeta`, `transferencia`, `efectivo`, `mercadopago` |
| `monto_total` | Float | `precio de la categoría × cantidad` |
| `numero_confirmacion` | String | `CONF-YYYYMMDD-XXXXXXXX` (derivado del `reserva_id`) |
| `estado` | String | Enum `pendiente`, `confirmada`, `cancelada`, `fallida`; en la práctica se escribe `confirmada` |
| `creado_en` | DateTime (UTC) | Al confirmar |
| `saga_log` | Array | Pasos de la SAGA (`paso`, `timestamp`, `exitoso`, `detalles`) |

### Índices (creados al iniciar el servicio)

```javascript
db.reservas.createIndex({ usuario_id: 1 })
db.reservas.createIndex({ evento_id: 1 })
db.reservas.createIndex({ estado: 1 })
db.reservas.createIndex({ creado_en: 1 })
db.reservas.createIndex({ usuario_id: 1, creado_en: -1 })
db.reservas.createIndex({ evento_id: 1, estado: 1 })
db.reservas.createIndex({ numero_confirmacion: 1 }, { unique: true })
db.reservas.createIndex({ estado: 1, creado_en: -1 })
// TTL: borra a las 24 h las reservas pendiente/fallida
db.reservas.createIndex({ creado_en: 1 }, {
  name: "idx_ttl_pendiente_fallida", expireAfterSeconds: 86400,
  partialFilterExpression: { estado: { $in: ["pendiente", "fallida"] } }
})
```

Escritura con `w=majority` + `journal`.

---

## Redis (`redis`): claves transaccionales

### Inventario por evento y categoría

```
KEY:   evento:{evento_id}:categoria:{categoria}:disponibles
TIPO:  String (contador)
VALOR: entradas disponibles de esa categoría
TTL:   sin TTL
```

No la crea Eventos: la siembra el propio Lua con `SETNX` (desde los `disponibles` que informó Eventos en el paso 3) la primera vez que se compra ese evento y categoría.

### Pago por reserva (paso 4)

```
KEY:   pago:{reserva_id}
TIPO:  Hash
CAMPOS: usuario_id, evento_id, cantidad, monto, metodo_pago, categoria,
        inventario_key, estado = "confirmado"
TTL:   90 días
```

Su existencia hace idempotente al Lua y le dice a la compensación qué clave y cuánto devolver. No hay locks distribuidos: la atomicidad la da el script Lua.

La caché de lecturas de Usuarios y Eventos usa **otra instancia, `redis-cache`** (`cache:usuario:{id}`, `cache:evento:{id}`), separada de estas claves y del servidor que las guarda.

---

## PostgreSQL: Tabla `event_log`

### DDL (lo crea `init_pg_schema()` al iniciar Reservas)

```sql
CREATE TABLE IF NOT EXISTS event_log (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    aggregate_id UUID NOT NULL,                       -- reserva_id
    aggregate_type VARCHAR(50) NOT NULL DEFAULT 'Reserva',
    payload JSONB NOT NULL,
    correlation_id UUID,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_event_log_aggregate   ON event_log(aggregate_id);
CREATE INDEX IF NOT EXISTS idx_event_log_type        ON event_log(event_type);
CREATE INDEX IF NOT EXISTS idx_event_log_timestamp   ON event_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_correlation ON event_log(correlation_id);
CREATE INDEX IF NOT EXISTS idx_event_log_payload_gin ON event_log USING GIN(payload);
```

No hay columna `metadata` ni particionamiento.

### Eventos y payloads reales

| `event_type` | Payload |
|--------------|---------|
| `SAGA_STARTED` | `{usuario_id, evento_id, cantidad, metodo_pago}` |
| `USUARIO_VALIDADO` | `{usuario_id}` |
| `EVENTO_VALIDADO` | `{evento_id, aforo_disponible}` |
| `PAGO_PROCESADO` | `{monto, metodo_pago}` |
| `INVENTARIO_DECREMENTADO` | `{evento_id, cantidad}` |
| `RESERVA_CONFIRMADA` | `{reserva_id, evento_id, numero_confirmacion, cantidad, monto_total}` |
| `HISTORIAL_ACTUALIZADO` | `{usuario_id}` |
| `HISTORIAL_PENDIENTE` | `{usuario_id, error}` |
| `SAGA_COMPLETED` | `{pasos_completados: 6, reserva_id}` |
| `SAGA_FAILED` | `{error, failed_step}` |
| `COMPENSACION_EJECUTADA` | `{paso_compensado, accion, resultado}` — paso 4: `PROCESAR_PAGO` / `REVERTIR_REDIS`; paso 5: `PAGO_PROCESADO` / `INCRBY+DEL` |

No existe `RESERVA_CANCELADA` (no hay cancelación). Los payloads no llevan nombre ni email: un test verifica que ningún dato personal llegue a lo persistido.

### Vistas CQRS (creadas con `CREATE OR REPLACE VIEW`)

```sql
-- ventas_por_evento: ventas confirmadas de los últimos 30 días
SELECT payload->>'evento_id' AS evento_id, COUNT(*) AS total_reservas,
       SUM((payload->>'cantidad')::int) AS total_entradas,
       SUM((payload->>'monto_total')::numeric) AS ingreso_total
FROM event_log
WHERE event_type = 'RESERVA_CONFIRMADA' AND timestamp > NOW() - INTERVAL '30 days'
GROUP BY payload->>'evento_id';

-- tasa_exito_saga: exitosas vs fallidas por día (últimos 7 días)
-- compensaciones_por_tipo: COMPENSACION_EJECUTADA agrupadas por paso (últimas 24 h)
```

Las ventas se cuentan por `RESERVA_CONFIRMADA`, así que un cobro compensado (`PAGO_PROCESADO` seguido de `COMPENSACION_EJECUTADA`) no las infla.

---

## Embebido vs Referencia

| Relación | Patrón | Justificación |
|----------|--------|---------------|
| Reserva → Usuario | **Referencia** (`usuario_id`) | Viven en servicios distintos; muchos-a-uno |
| Reserva → Evento | **Referencia** (`evento_id`) | Ídem |
| Usuario → Historial | **Embebido** (`historial_compras[]`) | Se lee siempre con el usuario |
| Evento → Precios | **Embebido** (`precios[]`) | Se lee con el evento; el inventario se ajusta atómicamente en el documento |

---

## Referencias

- [[reservas-pagos]] — Especificación del servicio
- [[saga-flow]] — Flujo transaccional
- [[event-sourcing-cqrs]] — Event Sourcing + CQRS
- [[db-choice-rationale]] — Justificación multi-DB
