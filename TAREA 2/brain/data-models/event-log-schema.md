---
name: event-log-schema
description: Schema del Event Log en PostgreSQL (append-only), tal como está implementado
metadata:
  type: specification
  status: complete
---

# Schema — Event Log (PostgreSQL)

**Última revisión contra el código:** 2026-11-05 (`reservas-service/src/services/postgresql.py`)

La tabla, sus índices y las vistas CQRS los crea `init_pg_schema()` al iniciar Reservas (`CREATE ... IF NOT EXISTS` / `CREATE OR REPLACE VIEW`, idempotente). No hay scripts de init en `docker-compose.yml`.

## Tabla: `event_log`

```sql
CREATE TABLE IF NOT EXISTS event_log (
    id             BIGSERIAL PRIMARY KEY,
    event_type     VARCHAR(50)  NOT NULL,
    aggregate_id   UUID         NOT NULL,                 -- reserva_id
    aggregate_type VARCHAR(50)  NOT NULL DEFAULT 'Reserva',
    payload        JSONB        NOT NULL,
    correlation_id UUID,                                  -- X-Correlation-ID de la petición
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_log_aggregate   ON event_log(aggregate_id);
CREATE INDEX IF NOT EXISTS idx_event_log_type        ON event_log(event_type);
CREATE INDEX IF NOT EXISTS idx_event_log_timestamp   ON event_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_correlation ON event_log(correlation_id);
CREATE INDEX IF NOT EXISTS idx_event_log_payload_gin ON event_log USING GIN(payload);
```

**Append-only por diseño**: la aplicación solo hace `INSERT` (`insert_event_log`). No hay `UPDATE` ni `DELETE` en el código; no hay un trigger o permiso que lo impida a nivel base de datos.

**No bloqueante**: `insert_event_log` atrapa sus propios errores y deja un warning. Si PostgreSQL no responde, la compra sigue; ese evento se pierde.

---

## Tipos de evento

Todos con `aggregate_type = 'Reserva'` y `aggregate_id = reserva_id`. Payloads en [[reservation-schema]].

| Evento | Emisor |
|--------|--------|
| `SAGA_STARTED`, `SAGA_FAILED` | `SagaOrchestrator` |
| `USUARIO_VALIDADO` | Handler 2 |
| `EVENTO_VALIDADO` | Handler 3 |
| `PAGO_PROCESADO`, `INVENTARIO_DECREMENTADO` | Handler 4 |
| `RESERVA_CONFIRMADA`, `HISTORIAL_ACTUALIZADO` / `HISTORIAL_PENDIENTE` | Handler 5 |
| `SAGA_COMPLETED` | Handler 6 (Auditor) |
| `COMPENSACION_EJECUTADA` | Handlers 4 y 5, y el orquestador (ver [[saga-flow]]) |

Secuencias típicas:

```
Éxito:        SAGA_STARTED → USUARIO_VALIDADO → EVENTO_VALIDADO → PAGO_PROCESADO
              → INVENTARIO_DECREMENTADO → RESERVA_CONFIRMADA → HISTORIAL_ACTUALIZADO → SAGA_COMPLETED
Fallo paso 4: SAGA_STARTED → USUARIO_VALIDADO → EVENTO_VALIDADO → PAGO_PROCESADO
              → COMPENSACION_EJECUTADA → SAGA_FAILED
Fallo paso 3: SAGA_STARTED → USUARIO_VALIDADO → SAGA_FAILED
```

---

## Consultas

### Timeline de una reserva (lo que hace `GET /api/reservar/{id}/audit`)

```sql
SELECT event_type, payload, correlation_id, timestamp
FROM event_log
WHERE aggregate_id = $1
ORDER BY timestamp ASC, id ASC;
```

### Seguir una petición entre servicios

```sql
SELECT event_type, aggregate_id, timestamp
FROM event_log
WHERE correlation_id = '...'
ORDER BY id;
```

### Por qué fallan las compras (usa el índice GIN)

```sql
SELECT payload->>'failed_step' AS paso, COUNT(*)
FROM event_log
WHERE event_type = 'SAGA_FAILED' AND timestamp > NOW() - INTERVAL '1 day'
GROUP BY 1 ORDER BY 2 DESC;

-- Todas las reservas de un evento, por contenido del payload
SELECT aggregate_id, timestamp FROM event_log
WHERE payload @> '{"evento_id": "..."}' AND event_type = 'RESERVA_CONFIRMADA';
```

### Vistas CQRS

```sql
SELECT * FROM ventas_por_evento;        -- RESERVA_CONFIRMADA, últimos 30 días
SELECT * FROM tasa_exito_saga;          -- SAGA_COMPLETED vs SAGA_FAILED por día, últimos 7 días
SELECT * FROM compensaciones_por_tipo;  -- COMPENSACION_EJECUTADA por paso, últimas 24 h
```

---

## Privacidad

El `event_log` no guarda nombre, email ni documento: solo identificadores (`usuario_id`, `evento_id`) y datos de la operación. Un test verifica que ningún dato personal llegue a lo persistido. Así la baja de una persona se resuelve en un único documento de `eventflow.usuarios`.

---

## No implementado (ideas de la etapa de diseño)

Se evaluaron y **no** se implementaron: encadenado por hash entre eventos (integridad tipo blockchain), columnas de `ip_address` / `user_agent`, eventos de GDPR (`DATOS_PERSONALES_MODIFICADOS`, `EXPORTACION_DATOS_SOLICITADA`), políticas de retención por tipo, particionamiento por mes, cifrado de campos y archivado.

---

## Referencias

- [[reservation-schema]] — Payloads de cada evento
- [[event-sourcing-cqrs]] — Patrón
- [[saga-flow]] — Cuándo se emite cada evento
