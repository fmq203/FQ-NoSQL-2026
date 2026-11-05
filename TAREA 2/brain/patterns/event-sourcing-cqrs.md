---
name: event-sourcing-cqrs
description: Patrones Event Sourcing y CQRS aplicados en EventFlow
metadata:
  type: pattern
  status: complete
---

# Event Sourcing + CQRS en EventFlow

**Última revisión contra el código:** 2026-11-05 (`reservas-service/src/services/postgresql.py`, `chain/validators.py`, `services/saga_orchestrator.py`)

## Qué se implementó (y qué no)

Reservas registra **cada paso de cada SAGA como un evento inmutable** en PostgreSQL (`event_log`) y expone **vistas de lectura** separadas del modelo operativo. Es Event Sourcing **aplicado a la auditoría**:

- ✅ Log append-only de eventos con tipo, payload JSONB, `aggregate_id` y `correlation_id`.
- ✅ Vistas CQRS sobre ese log para análisis.
- ✅ La línea de tiempo de cualquier reserva (incluidas las fallidas) se reconstruye con una consulta (`GET /api/reservar/{id}/audit`).
- ❌ El estado de la reserva **no** se deriva de los eventos: la fuente de verdad operativa es el documento en `eventflow.reservas` (MongoDB). No hay replay, snapshots ni versionado de eventos.

En la defensa conviene decirlo así: "event log como fuente de verdad de la **auditoría**, CQRS para el análisis; el estado operativo vive en MongoDB".

---

## Event Store: `event_log`

```sql
CREATE TABLE IF NOT EXISTS event_log (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    aggregate_id UUID NOT NULL,                 -- reserva_id
    aggregate_type VARCHAR(50) NOT NULL DEFAULT 'Reserva',
    payload JSONB NOT NULL,
    correlation_id UUID,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- índices: aggregate_id, event_type, timestamp DESC, correlation_id, GIN(payload)
```

Detalle y consultas en [[event-log-schema]].

### Eventos emitidos

| Event Type | Payload | Cuándo |
|------------|---------|--------|
| `SAGA_STARTED` | usuario_id, evento_id, cantidad, metodo_pago | Inicio |
| `USUARIO_VALIDADO` | usuario_id | Paso 2 OK |
| `EVENTO_VALIDADO` | evento_id, aforo_disponible | Paso 3 OK |
| `PAGO_PROCESADO` | monto, metodo_pago | Paso 4: cobro OK en Redis (se emite antes de sincronizar con Eventos; si esa sincronización falla, le sigue `COMPENSACION_EJECUTADA`) |
| `INVENTARIO_DECREMENTADO` | evento_id, cantidad | Paso 4 OK: Redis y Eventos Service alineados |
| `RESERVA_CONFIRMADA` | reserva_id, evento_id, numero_confirmacion, cantidad, monto_total | Paso 5 OK |
| `HISTORIAL_ACTUALIZADO` / `HISTORIAL_PENDIENTE` | usuario_id (+ error) | Paso 5, registro en Usuarios |
| `SAGA_COMPLETED` | pasos_completados: 6, reserva_id | Paso 6 |
| `SAGA_FAILED` | error, failed_step | Cualquier fallo |
| `COMPENSACION_EJECUTADA` | paso_compensado, accion, resultado | Rollback en paso 4 o 5 |

Sin datos personales en los payloads (lo verifica un test).

### Para qué sirve en EventFlow

| Beneficio | Aplicación |
|-----------|------------|
| **Auditoría** | Toda compra, exitosa o no, queda con su secuencia de pasos y tiempos |
| **Debugging** | "¿Me cobraron?": `PAGO_PROCESADO` seguido de `COMPENSACION_EJECUTADA` dice que se cobró y se revirtió |
| **Análisis de fallos** | `SAGA_FAILED` agrupado por `failed_step` |
| **Métricas de negocio** | Ventas, tasa de éxito y compensaciones salen de las vistas |

Escribir en el log **no bloquea** la compra: `insert_event_log` atrapa sus errores. Si PostgreSQL cae, la compra sigue y ese evento se pierde (decisión consciente: la auditoría no es precondición del negocio).

---

## CQRS

```
┌────────────────────────────────────────────────────────────┐
│ COMMAND (escritura)                                        │
│ POST /api/reservar → SagaOrchestrator → 6 handlers         │
│   Redis (cobro/inventario), Eventos, MongoDB (reserva)     │
│   └── cada paso → INSERT event_log                         │
└────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴──────────────────────────────┐
│ QUERY (lectura)                                            │
│ Operacional (MongoDB)            │ Analítica (PostgreSQL)  │
│ GET /api/reservar/{id}           │ ventas_por_evento       │
│ GET /api/reservar?usuario_id=... │ tasa_exito_saga         │
│ GET /api/reservar/{id}/audit (PG)│ compensaciones_por_tipo │
└────────────────────────────────────────────────────────────┘
```

### Vistas (las crea `init_pg_schema()` con `CREATE OR REPLACE VIEW`; son vistas comunes, no materializadas)

```sql
CREATE OR REPLACE VIEW ventas_por_evento AS          -- últimos 30 días
SELECT payload->>'evento_id' AS evento_id, COUNT(*) AS total_reservas,
       SUM((payload->>'cantidad')::int) AS total_entradas,
       SUM((payload->>'monto_total')::numeric) AS ingreso_total
FROM event_log
WHERE event_type = 'RESERVA_CONFIRMADA' AND timestamp > NOW() - INTERVAL '30 days'
GROUP BY payload->>'evento_id';

CREATE OR REPLACE VIEW tasa_exito_saga AS            -- por día, últimos 7 días
SELECT DATE_TRUNC('day', timestamp) AS dia,
       COUNT(*) FILTER (WHERE event_type = 'SAGA_COMPLETED') AS exitosas,
       COUNT(*) FILTER (WHERE event_type = 'SAGA_FAILED') AS fallidas,
       ROUND(COUNT(*) FILTER (WHERE event_type = 'SAGA_COMPLETED') * 100.0 /
             NULLIF(COUNT(*) FILTER (WHERE event_type IN ('SAGA_COMPLETED','SAGA_FAILED')), 0), 2) AS tasa_exito_pct
FROM event_log
WHERE event_type IN ('SAGA_COMPLETED', 'SAGA_FAILED') AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY DATE_TRUNC('day', timestamp) ORDER BY dia DESC;

CREATE OR REPLACE VIEW compensaciones_por_tipo AS    -- últimas 24 h
SELECT payload->>'paso_compensado' AS paso, COUNT(*) AS total_compensaciones
FROM event_log
WHERE event_type = 'COMPENSACION_EJECUTADA' AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY payload->>'paso_compensado';
```

Como las ventas se cuentan por `RESERVA_CONFIRMADA`, un cobro compensado no infla `ventas_por_evento`. En `compensaciones_por_tipo` el paso aparece como `PROCESAR_PAGO` (compensación del paso 4) o `PAGO_PROCESADO` (compensación del paso 5): los dos handlers usan nombres distintos.

---

## Correlation ID

- Lo pone el middleware `CorrelationIDMiddleware` (`X-Correlation-ID`, se genera si no viene) y vuelve en la respuesta.
- Va en los logs JSON, en el header de las llamadas a Usuarios y Eventos y en la **columna** `correlation_id` del `event_log`.
- No se guarda en Redis.

```sql
SELECT event_type, aggregate_id, timestamp FROM event_log
WHERE correlation_id = '<uuid>' ORDER BY id;
```

---

## Si se quisiera Event Sourcing completo

Faltaría: derivar el estado de la reserva aplicando los eventos (en lugar de leer el documento de MongoDB), versionar los payloads, snapshots para agregados largos y una proyección asincrónica hacia las vistas. Para esta tarea se eligió el log de auditoría porque cubre el requerimiento (trazabilidad completa y análisis) sin duplicar la fuente de verdad.

---

## Referencias

- [[saga-flow]] - En qué paso se emite cada evento
- [[chain-of-responsibility]] - Handlers que los emiten
- [[event-log-schema]] - Tabla, índices y consultas
- [[reservation-schema]] - Payloads
- Martin Fowler - Event Sourcing: https://martinfowler.com/eaaDev/EventSourcing.html
