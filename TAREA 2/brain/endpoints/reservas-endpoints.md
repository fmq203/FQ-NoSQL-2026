---
name: reservas-endpoints
description: Referencia a endpoints de Reservas Service (OpenAPI auto-generado)
metadata:
  type: specification
  status: complete
---

# Endpoints: Reservas & Pagos Service

## Fuente de Verdad

**OpenAPI Spec auto-generado por FastAPI**: http://localhost:8003/openapi.json
**Swagger UI**: http://localhost:8003/docs
**ReDoc**: http://localhost:8003/redoc

Revisado contra el código: 2026-11-05 (`reservas-service/src/api/routes/reservas.py`).

---

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Health check (MongoDB, Redis, PostgreSQL, Usuarios, Eventos) |
| GET | `/metrics` | Métricas Prometheus (`saga_total`, `saga_compensation_total`, `circuit_breaker_state`, ...) |
| POST | `/api/reservar` | Iniciar SAGA + Chain of Responsibility |
| GET | `/api/reservar` | Listar reservas (`skip`, `limit` ≤ 100, filtros `usuario_id`, `evento_id`, `estado`) |
| GET | `/api/reservar/{reserva_id}` | Obtener una reserva |
| GET | `/api/reservar/{reserva_id}/audit` | Eventos de esa SAGA en PostgreSQL |

---

## POST /api/reservar

### Request Body (`ReservaCreateRequest`)
```json
{
  "usuario_id": "550e8400-e29b-41d4-a716-446655440000",
  "evento_id": "550e8400-e29b-41d4-a716-446655440001",
  "cantidad": 2,
  "categoria": "general",
  "metodo_pago": "tarjeta",
  "reserva_id": "opcional: UUID v4 de idempotencia"
}
```

- `cantidad` > 0; `categoria` debe existir en `precios[]` del evento.
- `metodo_pago` ∈ `tarjeta`, `transferencia`, `efectivo`, `mercadopago`.
- `reserva_id` opcional: si no viene se genera. Mandarlo permite reintentar sin riesgo.
- Query param de demo: `?simular_fallo=sync_pago` fuerza el fallo de la sincronización con Eventos para mostrar la compensación del paso 4.

### Respuestas
```json
{
  "reserva_id": "550e8400-e29b-41d4-a716-446655440002",
  "estado": "confirmada",
  "numero_confirmacion": "CONF-20260920-A1B2C3D4"
}
```

- **201**: reserva nueva confirmada.
- **200**: ese `reserva_id` ya estaba confirmado (reintento idempotente; no se vuelve a cobrar).

### Errores (RFC 7807, `type` termina en el código)

| Código | `type` | Paso SAGA |
|--------|--------|-----------|
| 422 | `VALIDATION_ERROR` (datos inválidos, categoría inexistente) | 1 / 3 |
| 404 | `USER_NOT_FOUND` | 2 |
| 404 | `EVENT_NOT_FOUND` | 3 |
| 409 | `EVENT_NOT_AVAILABLE` (evento no publicado) | 3 |
| 409 | `INSUFFICIENT_INVENTORY` | 3 / 4 |
| 503 | `SERVICE_UNAVAILABLE` (Usuarios/Eventos caído, circuit breaker abierto, o falla la sincronización con Eventos → compensado) | 2 / 3 / 4 |
| 500 | `PAYMENT_FAILED` (error en Redis) | 4 |
| 500 | `RESERVATION_FAILED` (falla el insert en MongoDB → compensado) | 5 |

---

## Flujo SAGA Interno (6 pasos)

```
POST /api/reservar
    │  (si el reserva_id ya existe en MongoDB → 200 sin ejecutar la cadena)
    ▼
1. ValidadorDeDatos      ──► Validación local
2. ValidadorInventario   ──► GET /api/usuarios/{id}          (no-cache, reintentos, circuit breaker)
3. ValidadorEvento       ──► GET /api/eventos/{id}           (estado, categoría, stock)
4. ProcesadorPago        ──► Redis Lua pagar_y_decrementar   (atómico, idempotente)
                         ──► POST /api/eventos/{id}/decrementar-inventario
5. ConfirmadorReserva    ──► MongoDB insert + POST /api/usuarios/{id}/historial (best-effort)
6. Auditor               ──► SAGA_COMPLETED en event_log
```

Compensaciones (inline en los pasos 4 y 5) y Lua completos en [[saga-flow]].

| Fallo en | Acción |
|----------|--------|
| Pasos 1-3 | Ninguna (nada se modificó) |
| Paso 4: sincronización con Eventos | Lua `compensar_pago` (devuelve inventario en Redis y borra el pago) |
| Paso 5: insert MongoDB | Lua `compensar_pago` + `incrementar-inventario` en Eventos |
| event_log / historial | Ninguna: no bloquean (warning / `HISTORIAL_PENDIENTE`) |

---

## GET /api/reservar · GET /api/reservar/{reserva_id}

Devuelven `{reserva_id, estado, numero_confirmacion}` (el listado, un array). 404 `RESERVA_NOT_FOUND` si no existe.

## GET /api/reservar/{reserva_id}/audit

```json
{
  "reserva_id": "uuid",
  "eventos": [
    {"event_type": "SAGA_STARTED", "payload": {...}, "correlation_id": "uuid", "timestamp": "..."},
    {"event_type": "USUARIO_VALIDADO", "payload": {...}, "correlation_id": "uuid", "timestamp": "..."}
  ]
}
```

Ordenados por `timestamp, id`. Un `reserva_id` sin eventos devuelve 200 con `eventos: []`. Es lo que muestra la tarjeta "Auditoría" de la demo.

---

## Idempotencia

- **Clave**: `reserva_id` (UUID v4), del cliente o generado.
- **Antes de la cadena**: reserva ya confirmada en MongoDB → 200 (métrica `idempotency_hit_total`).
- **Redis**: `pago:{reserva_id}` existente → el Lua no vuelve a decrementar.
- **MongoDB**: `_id = reserva_id`.
- **Historial**: `$ne` sobre `historial_compras.reserva_id`.

---

## Correlation ID

- Header `X-Correlation-ID` (se genera si no viene); se devuelve en la respuesta y en los errores.
- Se propaga en las llamadas a Usuarios y Eventos y se guarda en la columna `correlation_id` de cada fila del `event_log`.

---

## Modelos Pydantic (Referencia)

Ver [[reservation-schema]].

- `ReservaCreateRequest` - Input
- `ReservaResponse` - Output (`reserva_id`, `estado`, `numero_confirmacion`)
- `ReservaContext` - Dataclass interno que recorre la cadena
- `MetodoPago` - Enum: tarjeta, transferencia, efectivo, mercadopago
- `EstadoReserva` - Enum: pendiente, confirmada, cancelada, fallida

---

## Especificación Completa

```bash
curl http://localhost:8003/openapi.json | jq '.paths'
curl http://localhost:8003/openapi.json | jq '.components.schemas'
```

---

## Referencias Relacionadas

- [[reservas-pagos]] - Spec completa servicio
- [[saga-flow]] - Flujo completo + compensaciones + Lua
- [[chain-of-responsibility]] - 6 handlers
- [[saga-pattern]] - SAGA Orchestration
- [[event-sourcing-cqrs]] - Event Sourcing + CQRS en PostgreSQL
- [[reservation-schema]] - Esquemas MongoDB/Redis/PostgreSQL
- [[consistency-strategy]] - Consistencia fuerte en SAGA
