---
name: reservas-pagos
description: Especificación del Servicio de Reservas y Pagos (Orquestador SAGA)
metadata:
  type: specification
  status: complete
---

# Servicio de Reservas y Pagos

## Responsabilidad

Orquesta la transacción distribuida de compra de entradas mediante **SAGA Orchestration** y estructura la lógica de validación con **Chain of Responsibility**. Coordina: Usuarios, Eventos, Redis (pagos), MongoDB (reservas), PostgreSQL (auditoría).

---

## Tecnologías

- **Framework**: FastAPI (Python 3.11)
- **Bases de Datos**: 
  - Redis (pagos atómicos + inventario)
  - MongoDB (persistencia reservas)
  - PostgreSQL (audit log / Event Sourcing)
- **Clientes HTTP**: httpx (async) para Usuarios/Eventos Services
- **Puerto**: 8003
- **Documentación**: http://localhost:8003/docs

---

## Arquitectura Interna

```
POST /api/reservar
    │
    ▼
┌─────────────────────────────────────┐
│ Chain of Responsibility             │
├─────────────────────────────────────┤
│ 1. ValidadorDeDatos                 │ ← Validación esquema
│ 2. ValidadorInventario (Usuario)    │ ← HTTP → Usuarios Service
│ 3. ValidadorEvento                  │ ← HTTP → Eventos Service
│ 4. ProcesadorPago (Redis Lua)       │ ← Atómico: Pago + Inventario
│ 5. ConfirmadorReserva (MongoDB)     │ ← Persistencia reserva
│ 6. Auditor (PostgreSQL)             │ ← Event Sourcing / Audit Log
└─────────────────────────────────────┘
    │
    ▼
Compensaciones automáticas si falla cualquier paso
```

---

## Modelo de Datos

### Redis: Inventario y Pagos

```redis
# Contador de inventario por evento (inicializado al crear evento)
SET inventario:{evento_id} 50000
EXPIRE inventario:{evento_id} 86400  # 24h, renovado por evento service

# Registro de pago (creado en SAGA paso 4)
HSET pago:{reserva_id} 
  reserva_id "uuid"
  usuario_id "uuid" 
  monto 150.0
  metodo_pago "tarjeta"
  estado "confirmado"
  timestamp "2026-09-20T10:00:00Z"
EXPIRE pago:{reserva_id} 86400
```

### MongoDB: Colección `reservas`

```json
{
  "_id": "UUID",
  "usuario_id": "UUID",
  "evento_id": "UUID",
  "cantidad": 2,
  "metodo_pago": "tarjeta",
  "monto_total": 160.0,
  "numero_confirmacion": "CONF-20260920-A1B2C3D4",
  "estado": "confirmada | cancelada | fallida",
  "creado_en": "ISODate",
  "saga_log": [
    { "paso": "USUARIO_VALIDADO", "timestamp": "ISODate", "exitoso": true },
    { "paso": "EVENTO_VALIDADO", "timestamp": "ISODate", "exitoso": true },
    { "paso": "PAGO_PROCESADO", "timestamp": "ISODate", "exitoso": true },
    { "paso": "RESERVA_CONFIRMADA", "timestamp": "ISODate", "exitoso": true },
    { "paso": "AUDITORIA_REGISTRADA", "timestamp": "ISODate", "exitoso": true }
  ]
}
```

### PostgreSQL: Tabla `event_log` (Event Sourcing)

```sql
CREATE TABLE event_log (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,           -- SAGA_STARTED, USUARIO_VALIDADO, etc.
    aggregate_id UUID NOT NULL,                -- reserva_id
    aggregate_type VARCHAR(50) NOT NULL,       -- 'Reserva'
    payload JSONB NOT NULL,                    -- Datos del evento
    metadata JSONB,                            -- Contexto adicional
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    correlation_id UUID                        -- Para trazar SAGA completa
);

CREATE INDEX idx_event_log_aggregate ON event_log(aggregate_id);
CREATE INDEX idx_event_log_type ON event_log(event_type);
CREATE INDEX idx_event_log_timestamp ON event_log(timestamp);
```

---

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/reservar` | Iniciar SAGA + Chain of Responsibility |

### POST /api/reservar

```json
// Request
{
  "usuario_id": "550e8400-e29b-41d4-a716-446655440000",
  "evento_id": "550e8400-e29b-41d4-a716-446655440001",
  "cantidad": 2,
  "metodo_pago": "tarjeta"
}

// Response 201 (Éxito)
{
  "reserva_id": "550e8400-e29b-41d4-a716-446655440002",
  "estado": "confirmada",
  "numero_confirmacion": "CONF-20260920-A1B2C3D4"
}

// Response 400/404/409/500 (Error)
{
  "detail": "Inventario insuficiente. Disponibles: 1"
}
```

---

## Flujo SAGA Detallado

Ver [[architecture/saga-flow]] para diagrama completo.

### Pasos Exitosos

1. **ValidadorDeDatos** — Validar UUIDs, cantidad > 0, método pago válido
2. **ValidadorInventario** — GET `/api/usuarios/{id}` → Usuario existe
3. **ValidadorEvento** — GET `/api/eventos/{id}` → Evento existe + aforo >= cantidad
4. **ProcesadorPago** — **Lua Script Redis atómico**:
   - Verificar `inventario:evento_id >= cantidad`
   - `DECRBY inventario:evento_id cantidad`
   - `HSET pago:reserva_id {datos_pago}`
5. **ConfirmadorReserva** — INSERT en MongoDB `reservas`
6. **Auditor** — INSERT en PostgreSQL `event_log` (SAGA_COMPLETED)

### Compensaciones (Rollback)

| Fallo en | Acción |
|----------|--------|
| Paso 1-3 (Validaciones) | Ninguna (solo lectura) |
| Paso 4 (Redis) | Automática en Lua (transacción atómica) |
| Paso 5 (MongoDB) | `DELETE reserva` + Lua compensación Redis (`INCRBY` + `DEL`) |
| Paso 6 (PostgreSQL) | Log warning — reserva ya confirmada |

---

## Chain of Responsibility

Ver [[architecture/chain-of-responsibility]] para implementación completa.

### Handlers en Orden

```python
handlers = [
    ValidadorDeDatos(),           # Local
    ValidadorInventario(client),  # HTTP → Usuarios
    ValidadorEvento(client),      # HTTP → Eventos
    ProcesadorPago(redis),        # Redis Lua
    ConfirmadorReserva(mongo),    # MongoDB
    Auditor(pg_pool)              # PostgreSQL
]
```

Cada handler:
- Recibe `ReservaContext` (dataclass con todos los datos)
- Procesa o retorna error
- Pasa al siguiente con `set_next()`

---

## Eventos de Auditoría (Event Sourcing)

| Event Type | Cuándo | Payload Clave |
|------------|--------|---------------|
| `SAGA_STARTED` | Inicio POST /api/reservar | request data |
| `USUARIO_VALIDADO` | Paso 2 OK | usuario_id |
| `EVENTO_VALIDADO` | Paso 3 OK | evento_id, aforo_disponible |
| `PAGO_PROCESADO` | Paso 4 OK | reserva_id, monto, metodo_pago |
| `INVENTARIO_DECREMENTADO` | Paso 4 OK | evento_id, cantidad |
| `RESERVA_CONFIRMADA` | Paso 5 OK | reserva_id, numero_confirmacion |
| `SAGA_COMPLETED` | Paso 6 OK | aggregate completo |
| `SAGA_FAILED` | Cualquier fallo | error, paso_fallido |
| `COMPENSACION_EJECUTADA` | Rollback | pasos_compensados |

---

## CQRS (Command Query Responsibility Segregation)

### Escritura (Commands) → PostgreSQL Event Log
- Cada paso SAGA = evento inmutable
- Fuente de verdad para auditoría

### Lectura (Queries) → Vistas Materializadas / MongoDB
- `reservas` collection para consultas operativas
- Vistas PostgreSQL para reportes analíticos

```sql
-- Vista para reportes de ventas
CREATE VIEW ventas_por_evento AS
SELECT 
    e.nombre as evento,
    COUNT(r.id) as total_reservas,
    SUM(r.cantidad) as total_entradas,
    SUM(r.monto_total) as ingreso_total
FROM event_log r
JOIN eventos e ON e.id = r.payload->>'evento_id'
WHERE r.event_type = 'RESERVA_CONFIRMADA'
GROUP BY e.nombre;
```

---

## Idempotencia

- `reserva_id` (UUID v4) generado al inicio → clave de idempotencia
- Redis: `pago:{reserva_id}` evita doble procesamiento
- MongoDB: `_id = reserva_id` (unique index)
- PostgreSQL: `aggregate_id` permite detectar duplicados

---

## Manejo de Errores

| Error | HTTP | Acción |
|-------|------|--------|
| Usuario no existe | 404 | Fin SAGA, sin compensación |
| Evento no existe | 404 | Fin SAGA, sin compensación |
| Inventario insuficiente | 409 | Fin SAGA, sin compensación |
| Pago falla (Redis) | 500 | Compensación automática Lua |
| MongoDB error | 500 | Compensación Redis + MongoDB |
| PostgreSQL error | 500 | Log warning, reserva confirmada |

---

## Referencias

- [[architecture/saga-flow]] — Diagrama y pasos SAGA
- [[architecture/chain-of-responsibility]] — Implementación CoR
- [[patterns/event-sourcing-cqrs]] — Event Sourcing + CQRS
- [[data-models/reservation-schema]] — Esquemas detallados
- [[endpoints/reservas-endpoints]] — Referencia OpenAPI