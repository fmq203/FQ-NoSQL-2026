---
name: event-log-pattern
description: Patrón Append-Only Event Log con PostgreSQL
metadata:
  type: pattern
  status: complete
---

# Patrón Event Log (Append-Only)

**Última revisión contra el código:** 2026-11-05 (`reservas-service/src/services/postgresql.py`)

## Concepto

El **event log** es una cinta de auditoría que solo crece: cada paso de cada compra agrega una fila y nunca se modifica ni se borra. Registra también los **fallos y las compensaciones**, que es justamente lo que el modelo operativo (MongoDB, donde solo quedan las reservas confirmadas) no muestra.

Relación con [[event-sourcing-cqrs]]: este doc es el *cómo* (la tabla y la escritura); aquel, el *para qué* (auditoría + CQRS).

---

## Implementación real

Una sola función, llamada desde el orquestador y desde cada handler:

```python
async def insert_event_log(event_type, aggregate_id, payload,
                           correlation_id=None, aggregate_type="Reserva") -> None:
    """Un fallo al escribir en el event log NUNCA debe abortar la SAGA."""
    try:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO event_log
                       (event_type, aggregate_id, aggregate_type, payload, correlation_id)
                   VALUES ($1, $2, $3, $4::jsonb, $5)""",
                _event_type_value(event_type), aggregate_id, aggregate_type,
                json.dumps(payload, default=str), correlation_id,
            )
    except Exception as e:
        logger.warning(f"No se pudo registrar evento {event_type} en event_log: {e}")
```

- `id` (BIGSERIAL) y `timestamp` (`NOW()`) los pone PostgreSQL.
- Pool `asyncpg`; cada `INSERT` es su propia transacción.
- **No bloqueante**: si PostgreSQL no responde, warning y la compra sigue.
- Lectura: `get_events_by_aggregate(reserva_id)` → `GET /api/reservar/{id}/audit`.

---

## Flujo: SAGA + Event Log

```
POST /api/reservar
 ├─ SAGA_STARTED
 ├─ Paso 2 OK → USUARIO_VALIDADO
 ├─ Paso 3 OK → EVENTO_VALIDADO
 ├─ Paso 4: Lua cobra → PAGO_PROCESADO
 │    ├─ Eventos sincronizado → INVENTARIO_DECREMENTADO
 │    └─ falla la sync → COMPENSACION_EJECUTADA → SAGA_FAILED
 ├─ Paso 5 OK → RESERVA_CONFIRMADA → HISTORIAL_ACTUALIZADO | HISTORIAL_PENDIENTE
 │    └─ falla el insert → COMPENSACION_EJECUTADA → SAGA_FAILED
 └─ Paso 6 → SAGA_COMPLETED

Cualquier fallo en los pasos 1-3 → SAGA_FAILED (sin compensación)
```

### Timelines reales (de la demo)

```
Éxito (≈ 105 ms):
  SAGA_STARTED → USUARIO_VALIDADO (+21) → EVENTO_VALIDADO (+42) → PAGO_PROCESADO (+47)
  → INVENTARIO_DECREMENTADO (+68) → RESERVA_CONFIRMADA (+80) → HISTORIAL_ACTUALIZADO (+101)
  → SAGA_COMPLETED (+105)

Compensación del paso 4 (≈ 51 ms):
  SAGA_STARTED → USUARIO_VALIDADO (+18) → EVENTO_VALIDADO (+36) → PAGO_PROCESADO (+42)
  → COMPENSACION_EJECUTADA (+47) → SAGA_FAILED (+51)
```

---

## Consultas de debugging

```sql
-- ¿Qué pasó con esta compra?
SELECT event_type, payload, timestamp FROM event_log
WHERE aggregate_id = '<reserva_id>' ORDER BY timestamp, id;

-- ¿Dónde fallan las compras hoy?
SELECT payload->>'failed_step' AS paso, COUNT(*) FROM event_log
WHERE event_type = 'SAGA_FAILED' AND timestamp > NOW() - INTERVAL '1 day'
GROUP BY 1;

-- Compras que se cobraron y se revirtieron
SELECT aggregate_id FROM event_log WHERE event_type = 'COMPENSACION_EJECUTADA';
```

Más consultas y las vistas CQRS en [[event-log-schema]].

---

## Características de PostgreSQL aprovechadas

| Característica | Uso |
|---------------|-----|
| **JSONB + índice GIN** | Payload flexible por tipo de evento, consultable (`payload @> '{...}'`) |
| **BIGSERIAL + TIMESTAMPTZ** | Orden total de los eventos (se ordena por `timestamp, id`) |
| **Índices** | Por `aggregate_id`, `event_type`, `timestamp`, `correlation_id` |
| **Vistas** | `ventas_por_evento`, `tasa_exito_saga`, `compensaciones_por_tipo` |
| **ACID / WAL** | Cada evento se escribe completo o no se escribe |

---

## Limitaciones

| Limitación | Estado |
|-----------|--------|
| Append-only solo por convención (la app no hace UPDATE/DELETE; la base no lo impide) | Se podría reforzar con permisos o un trigger |
| Si PostgreSQL cae, los eventos de ese lapso se pierden | Aceptado: la auditoría no bloquea la compra |
| La tabla crece sin límite | Sin retención ni particionamiento implementados |
| Sin integridad encadenada (hash entre eventos) | Evaluado en el diseño, no implementado |

---

## Referencias

- [[event-log-schema]] - Tabla, índices, consultas
- [[event-sourcing-cqrs]] - Auditoría + CQRS
- [[saga-flow]] - Qué paso emite cada evento
