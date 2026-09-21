---
name: event-sourcing-cqrs
description: Patrones Event Sourcing y CQRS aplicados en EventFlow
metadata:
  type: pattern
  status: complete
---

# Event Sourcing + CQRS en EventFlow

## Contexto

El **Servicio de Reservas y Pagos** implementa **Event Sourcing** y **CQRS (Command Query Responsibility Segregation)** usando PostgreSQL como event store para auditoría completa y consultas analíticas.

---

## Event Sourcing

### Principio

> **"Almacenar eventos en lugar de estados"**

En lugar de guardar solo el estado final de una reserva, se persiste la **secuencia completa de eventos** que llevaron a ese estado.

### Event Store: Tabla `event_log` (PostgreSQL)

```sql
CREATE TABLE event_log (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,           -- Tipo de evento
    aggregate_id UUID NOT NULL,                -- ID del agregado (reserva_id)
    aggregate_type VARCHAR(50) NOT NULL,       -- 'Reserva'
    payload JSONB NOT NULL,                    -- Datos del evento
    metadata JSONB,                            -- Contexto: correlation_id, service, etc.
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Eventos Generados por SAGA

| Event Type | Aggregate | Payload Clave | Cuándo |
|------------|-----------|---------------|--------|
| `SAGA_STARTED` | Reserva | Request completo | Inicio POST /api/reservar |
| `USUARIO_VALIDADO` | Reserva | usuario_id, nombre | Paso 2 OK |
| `EVENTO_VALIDADO` | Reserva | evento_id, aforo_disponible | Paso 3 OK |
| `PAGO_PROCESADO` | Reserva | reserva_id, monto, metodo_pago | Paso 4 OK |
| `INVENTARIO_DECREMENTADO` | Reserva | evento_id, cantidad, nuevo_disponible | Paso 4 OK |
| `RESERVA_CONFIRMADA` | Reserva | reserva_id, numero_confirmacion, monto_total | Paso 5 OK |
| `SAGA_COMPLETED` | Reserva | pasos_completados: 6 | Paso 6 OK |
| `SAGA_FAILED` | Reserva | error, paso_fallido, compensaciones | Cualquier fallo |
| `COMPENSACION_EJECUTADA` | Reserva | paso_compensado, accion, resultado | Rollback |

### Ventajas en EventFlow

| Beneficio | Aplicación |
|-----------|------------|
| **Auditoría inmutable** | Compliance financiero, no se puede alterar historial |
| **Debugging temporal** | Reconstruir estado en cualquier punto: `SELECT * FROM event_log WHERE aggregate_id = ? ORDER BY timestamp` |
| **Reproducción de bugs** | Replay eventos en entorno de test |
| **Análisis de fallos** | Query: `WHERE event_type = 'SAGA_FAILED' AND timestamp > NOW() - INTERVAL '24h'` |
| **Métricas de negocio** | Tasa éxito, compensaciones por tipo, latencia por paso |

---

## CQRS (Command Query Responsibility Segregation)

### Separación Explícita

```
┌─────────────────────────────────────────────────────────────┐
│                    COMMAND SIDE (Escritura)                 │
├─────────────────────────────────────────────────────────────┤
│  POST /api/reservar                                         │
│       │                                                     │
│       ▼                                                     │
│  SAGA Orchestrator → Chain of Responsibility                │
│       │                                                     │
│       ├── Redis Lua (Pago + Inventario)  ──► Event Log PG  │
│       ├── MongoDB (Reserva)              ──► Event Log PG  │
│       └── PostgreSQL (Audit)             ──► Event Log PG  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    QUERY SIDE (Lectura)                     │
├─────────────────────────────────────────────────────────────┤
│  Operacional (MongoDB)          │  Analítica (PostgreSQL)   │
│  ─────────────────────────      │  ───────────────────────  │
│  GET /api/reservas/{id}         │  Ventas por evento        │
│  Historial por usuario          │  Tasa éxito SAGA          │
│  Ocupación por evento           │  Compensaciones por tipo  │
│  Lookup por confirmación        │  Ingresos por periodo     │
└─────────────────────────────────────────────────────────────┘
```

### Modelos de Lectura

#### 1. Vista Operacional (MongoDB - Colección `reservas`)
```javascript
// Optimizada para: lookup por ID, historial usuario, ocupación evento
{
  _id: UUID,                    // PK = reserva_id
  usuario_id: UUID,             // Índice: usuario_id + creado_en
  evento_id: UUID,              // Índice: evento_id + estado
  numero_confirmacion: String,  // Índice único
  estado: String,               // Índice: estado + creado_en
  saga_log: Array               // Embedded para debugging
}
```

#### 2. Vista Analítica (PostgreSQL - Vistas Materializadas / Queries)

```sql
-- Ventas por evento (últimos 30 días)
CREATE VIEW ventas_por_evento AS
SELECT 
    payload->>'evento_id' as evento_id,
    COUNT(*) as total_reservas,
    SUM((payload->>'cantidad')::int) as total_entradas,
    SUM((payload->>'monto_total')::numeric) as ingreso_total
FROM event_log
WHERE event_type = 'RESERVA_CONFIRMADA'
  AND timestamp > NOW() - INTERVAL '30 days'
GROUP BY payload->>'evento_id';

-- Tasa éxito SAGA diaria
CREATE VIEW saga_success_rate AS
SELECT 
    DATE_TRUNC('day', timestamp) as dia,
    COUNT(*) FILTER (WHERE event_type = 'SAGA_COMPLETED') as exitosas,
    COUNT(*) FILTER (WHERE event_type = 'SAGA_FAILED') as fallidas,
    ROUND(
        COUNT(*) FILTER (WHERE event_type = 'SAGA_COMPLETED') * 100.0 / 
        NULLIF(COUNT(*) FILTER (WHERE event_type IN ('SAGA_COMPLETED', 'SAGA_FAILED')), 0), 2
    ) as tasa_exito_pct
FROM event_log
WHERE event_type IN ('SAGA_COMPLETED', 'SAGA_FAILED')
  AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY DATE_TRUNC('day', timestamp);

-- Compensaciones por tipo (últimas 24h)
CREATE VIEW compensaciones_por_tipo AS
SELECT 
    payload->>'paso_compensado' as paso,
    COUNT(*) as total_compensaciones
FROM event_log
WHERE event_type = 'COMPENSACION_EJECUTADA'
  AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY payload->>'paso_compensado';
```

---

## Correlation ID: Trazabilidad Distribuida

### Propagación

```python
# Generado al inicio de SAGA
correlation_id = uuid4()

# Propagado en:
# 1. Logs estructurados (JSON)
logger.info("SAGA_STARTED", correlation_id=correlation_id, reserva_id=reserva_id)

# 2. HTTP Headers a servicios downstream
headers = {"X-Correlation-ID": str(correlation_id)}
await http_client.get(url, headers=headers)

# 3. PostgreSQL event_log
metadata = {"correlation_id": str(correlation_id), "service": "reservas-service"}
await pg.execute(INSERT_EVENT_LOG, ..., metadata=json.dumps(metadata))

# 4. Redis keys (opcional, para debugging)
await redis.hset(f"pago:{reserva_id}", "correlation_id", str(correlation_id))
```

### Query Cross-Service

```sql
-- Buscar todos los eventos de una SAGA completa
SELECT * FROM event_log 
WHERE correlation_id = 'uuid-correlation-id' 
ORDER BY timestamp;

-- Vincular con logs de Usuarios/Eventos (si propagaron correlation_id)
-- Requiere logging centralizado (ELK/Loki) con correlation_id como campo
```

---

## Reconstrucción de Estado (Event Replay)

```python
async def reconstruir_reserva(aggregate_id: UUID) -> ReservaState:
    """Reconstruye estado actual desde event_log"""
    events = await pg.fetch("""
        SELECT event_type, payload, timestamp 
        FROM event_log 
        WHERE aggregate_id = $1 
        ORDER BY timestamp
    """, aggregate_id)
    
    state = ReservaState()
    for event in events:
        state.apply(event)
    return state

class ReservaState:
    def apply(self, event):
        if event.type == 'RESERVA_CONFIRMADA':
            self.estado = 'confirmada'
            self.numero_confirmacion = event.payload['numero_confirmacion']
        elif event.type == 'SAGA_FAILED':
            self.estado = 'fallida'
            self.error = event.payload['error']
        # ... otros eventos
```

---

## Comparación: Con vs Sin Event Sourcing

| Aspecto | Tradicional (Solo Estado) | Event Sourcing (EventFlow) |
|---------|---------------------------|----------------------------|
| **Auditoría** | Difícil (logs dispersos) | Nativa (event_log inmutable) |
| **Debugging** | Estado final فقط | Historia completa reproducible |
| **Compliance** | Manual | Automática (append-only) |
| **Análisis** | Queries complejas sobre estado | Vistas SQL sobre eventos |
| **Bugs temporales** | Imposible reproducir | Replay eventos en test |
| **Esquema** | Migraciones riesgosas | Eventos versionados (upcasters) |

---

## Referencias

- `brain/architecture/saga-flow.md` - Generación de eventos por paso
- `brain/architecture/chain-of-responsibility.md` - Auditor handler
- `brain/data-models/reservation-schema.md` - Tabla event_log DDL
- `brain/data-models/db-choice-rationale.md` - PostgreSQL para Event Sourcing
- Martin Fowler - Event Sourcing: https://martinfowler.com/eaaDev/EventSourcing.html
- Greg Young - CQRS: https://cqrs.nu/Faq