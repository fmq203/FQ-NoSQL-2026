---
name: reservas-pagos
description: Especificación del Servicio de Reservas y Pagos (Orquestador SAGA)
metadata:
  type: specification
  status: complete
---

# Servicio de Reservas y Pagos

## Responsabilidad

Orquesta la compra de entradas como una **SAGA orquestada**, ejecutada como **Chain of Responsibility** de 6 handlers. Coordina Usuarios y Eventos (HTTP), Redis (cobro + inventario atómicos), MongoDB (reserva confirmada) y PostgreSQL (auditoría).

Revisado contra el código: 2026-11-05 (`reservas-service/src/`).

---

## Tecnologías

- **Framework**: FastAPI (Python 3.11)
- **Datos**:
  - Redis `redis` — `pago:{reserva_id}` y `evento:{id}:categoria:{cat}:disponibles` (scripts Lua)
  - MongoDB — `eventflow.reservas`
  - PostgreSQL — `event_log` + vistas CQRS (los crea `init_pg_schema()` al iniciar)
- **Clientes HTTP**: httpx async hacia Usuarios y Eventos (timeout 5 s, 3 reintentos con backoff, circuit breaker)
- **Puerto**: 8003 — docs en http://localhost:8003/docs

---

## Arquitectura Interna

```
POST /api/reservar
    │  ¿reserva_id ya confirmado en MongoDB? → 200 (idempotencia)
    ▼
SagaOrchestrator.execute()  → SAGA_STARTED
    │
    ▼
┌────────────────────────────────────────────┐
│ ChainBuilder.build()                       │
│ 1. ValidadorDeDatos                        │ validación local
│ 2. ValidadorInventario                     │ GET usuario (no-cache)
│ 3. ValidadorEvento                         │ GET evento: estado, categoría, stock
│ 4. ProcesadorPago                          │ Lua pagar_y_decrementar + decrementar en Eventos
│ 5. ConfirmadorReserva                      │ insert MongoDB + historial en Usuarios (best-effort)
│ 6. Auditor                                 │ SAGA_COMPLETED
└────────────────────────────────────────────┘
    │ si context.error → SAGA_FAILED
    ▼
201 / 200 / error RFC 7807
```

Las compensaciones reales están **dentro de los handlers 4 y 5** (ver [[saga-flow]]). El orquestador tiene además un mapa `compensation_handlers` para los pasos 4 y 5; en la práctica solo agrega un `COMPENSACION_EJECUTADA` nominal del paso 4 cuando falla el 5 (su handler solo escribe un log). Ver la nota al final.

---

## Modelo de Datos

Detalle completo en [[reservation-schema]] y [[event-log-schema]]. Resumen:

- **MongoDB** `eventflow.reservas`: `_id = reserva_id`, `usuario_id`, `evento_id`, `cantidad`, `categoria`, `metodo_pago`, `monto_total`, `numero_confirmacion` (único), `estado` (`confirmada`), `creado_en`, `saga_log[]`. Solo se guardan reservas confirmadas.
- **Redis**: `pago:{reserva_id}` (hash, TTL 90 días) e inventario por categoría (sembrado con `SETNX` desde lo que informó Eventos).
- **PostgreSQL** `event_log(id, event_type, aggregate_id, aggregate_type, payload JSONB, correlation_id, timestamp)` + índice GIN.

---

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Health check de MongoDB, Redis, PostgreSQL, Usuarios y Eventos |
| GET | `/metrics` | Prometheus |
| POST | `/api/reservar` | SAGA (201 nueva, 200 reintento) |
| GET | `/api/reservar` | Listar reservas |
| GET | `/api/reservar/{reserva_id}` | Obtener reserva |
| GET | `/api/reservar/{reserva_id}/audit` | Línea de tiempo en PostgreSQL |

Request, respuestas y códigos de error en [[reservas-endpoints]]. Los errores son RFC 7807 con códigos específicos (`USER_NOT_FOUND`, `EVENT_NOT_FOUND`, `EVENT_NOT_AVAILABLE`, `INSUFFICIENT_INVENTORY`, `PAYMENT_FAILED`, `RESERVATION_FAILED`, `SERVICE_UNAVAILABLE`, `VALIDATION_ERROR`, `RESERVA_NOT_FOUND`).

---

## Chain of Responsibility

```python
# chain/validators.py — ChainBuilder.build()
validador_datos = ValidadorDeDatos()
validador_inventario = ValidadorInventario()
...
validador_datos.set_next(validador_inventario)   # 1→2→3→4→5→6
```

Los handlers no reciben dependencias por constructor: usan los clientes globales (`http_clients`, `redis_pago`, `mongo`, `postgresql`). Cada uno recibe el `ReservaContext`, hace su paso, escribe su entrada en `saga_log` y su evento en `event_log`; si falla, deja `context.error` y la cadena se corta. Ver [[chain-of-responsibility]].

---

## Compensaciones

| Fallo en | Acción | Respuesta |
|----------|--------|-----------|
| Pasos 1-3 | Ninguna (nada se modificó) | 404 / 409 / 422 / 503 |
| Paso 4: Lua sin stock | Ninguna (el Lua no descontó) | 409 |
| Paso 4: sincronización con Eventos | Lua `compensar_pago` | 503 |
| Paso 5: insert MongoDB | Lua `compensar_pago` + `incrementar-inventario` | 500 |
| Historial / event_log | Ninguna (no bloquean) | 201 igual |

---

## Resiliencia

- **Reintentos**: 3 (0,5 / 1 / 2 s) ante timeout, error de red o 5xx de Usuarios/Eventos; un 404 no se reintenta.
- **Circuit breaker** por servicio: abre con 5 fallos seguidos, rechaza al instante 30 s, después deja pasar una prueba (half-open). Estado en `/health` y en la métrica `circuit_breaker_state`.
- **Fault injection de demo**: `?simular_fallo=sync_pago` fuerza la falla de la sincronización del paso 4.

---

## CQRS

- **Escritura**: cada paso de la SAGA agrega un evento inmutable a `event_log`.
- **Lectura**: vistas `ventas_por_evento` (desde `RESERVA_CONFIRMADA`), `tasa_exito_saga`, `compensaciones_por_tipo`; y `eventflow.reservas` para la consulta operativa.

```sql
-- ventas_por_evento: todo sale del payload (los eventos no están en PostgreSQL)
SELECT payload->>'evento_id' AS evento_id, COUNT(*) AS total_reservas,
       SUM((payload->>'cantidad')::int) AS total_entradas,
       SUM((payload->>'monto_total')::numeric) AS ingreso_total
FROM event_log
WHERE event_type = 'RESERVA_CONFIRMADA' AND timestamp > NOW() - INTERVAL '30 days'
GROUP BY payload->>'evento_id';
```

---

## Idempotencia

`reserva_id` (UUID v4, del cliente o generado): chequeo previo en MongoDB (→ 200), `pago:{reserva_id}` en el Lua, `_id` en MongoDB y `$ne` en el historial del usuario.

---

## Testing

```bash
make test     # reservas: 112 passed, 4 skipped (unit, integración, contrato, carga con dependencias mockeadas)
make jmeter   # de punta a punta: doble venta (50/250 con stock 50) y SAGA sostenida (satura en ≈50 req/s)
```

---

## Nota: segunda capa de compensación en el orquestador

`SagaOrchestrator._handle_error()` calcula los pasos a compensar con `range(failed_step - 1, 3, -1)` y ejecuta `compensation_handlers` (configurados en `routes/reservas.py` para los pasos 4 y 5):

- Falla en paso ≤ 4 → no corre nada.
- Falla en paso 5 → corre `compensate_step_4_payment`, que **solo escribe un log**, y registra un `COMPENSACION_EJECUTADA` con `accion: "COMPENSATION"`. Ese evento se suma al real que ya registró el handler 5, así que la auditoría de un fallo en MongoDB muestra dos compensaciones.
- `compensate_step_5_reservation` (que sí revierte) solo correría si fallara el paso 6, que no falla (el Auditor atrapa sus errores).

Es redundante con las compensaciones inline; queda como deuda técnica documentada.

---

## Referencias

- [[saga-flow]] — Diagrama, Lua y compensaciones
- [[chain-of-responsibility]] — Implementación CoR
- [[event-sourcing-cqrs]] — Event Sourcing + CQRS
- [[reservation-schema]] — Esquemas detallados
- [[reservas-endpoints]] — Referencia OpenAPI
