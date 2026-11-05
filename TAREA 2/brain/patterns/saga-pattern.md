---
name: saga-pattern
description: Implementación del patrón SAGA con Orquestación en EventFlow
metadata:
  type: pattern
  status: complete
---

# SAGA Pattern con Orquestación - EventFlow

**Última revisión contra el código:** 2026-11-05. El detalle paso a paso (diagrama, Lua real, códigos de error) está en [[saga-flow]]; acá va el patrón y por qué se aplicó así.

## Problema

Una compra toca tres sistemas que no comparten transacción: el inventario y el cobro (Redis), el inventario visible del evento (Eventos/MongoDB) y la reserva (MongoDB), más la auditoría (PostgreSQL). Un 2PC entre ellos no es viable; la alternativa es una **SAGA**: pasos locales en orden y, si uno falla después de haber modificado algo, **compensaciones** que deshacen lo hecho.

## Por qué orquestación (y no coreografía)

- Un solo componente (`SagaOrchestrator` en Reservas) conoce el orden y el estado de la compra: compensar y auditar es directo.
- Con coreografía, cada servicio reaccionaría a eventos de los otros y la lógica de compensación quedaría repartida.
- El costo: Reservas es el punto central (si cae, no hay compras). Se mitiga con health checks, reintentos y circuit breaker hacia los servicios que llama.

---

## Implementación

```
POST /api/reservar
  │ reserva_id ya confirmado en MongoDB → 200 (no se ejecuta nada)
  ▼
SagaOrchestrator.execute(context)            → SAGA_STARTED
  │
  ├─ Chain of Responsibility (6 handlers, en serie)
  │   1. ValidadorDeDatos      local
  │   2. ValidadorInventario   HTTP GET Usuarios
  │   3. ValidadorEvento       HTTP GET Eventos
  │   4. ProcesadorPago        Redis Lua (atómico) + HTTP decrementar en Eventos   ← compensa inline
  │   5. ConfirmadorReserva    MongoDB insert + historial best-effort              ← compensa inline
  │   6. Auditor               SAGA_COMPLETED
  │
  └─ si context.error → SAGA_FAILED (+ compensation_handlers del orquestador, ver nota)
```

| Paso | Consistencia | Si falla |
|------|--------------|----------|
| 1-3 | Lecturas sin caché (`Cache-Control: no-cache`) | Nada que compensar |
| 4 | **Fuerte**: Lua atómico en Redis | Falla la sincronización con Eventos → Lua `compensar_pago` (503) |
| 5 | **Fuerte**: `w=majority` + journal | Lua `compensar_pago` + `incrementar-inventario` (500) |
| 6 / event_log / historial | No bloqueante | Warning / `HISTORIAL_PENDIENTE`; la reserva queda confirmada |

Las compensaciones son **inline y sincrónicas**: el handler que modificó estado lo revierte antes de devolver el error. No hay un estado intermedio "COMPENSATING".

### Atomicidad del paso 4

El script `pagar_y_decrementar` chequea el stock, lo descuenta y registra el pago en una sola ejecución. Redis corre un script por vez, así que dos compradores no pueden ver el mismo stock: es lo que evita la doble venta (verificado con JMeter: 300 intentos contra 50 entradas → exactamente 50 ventas). Si no hay stock, devuelve error sin modificar nada. El script completo está en [[saga-flow]].

---

## Idempotencia

`check_idempotency(reserva_id)` (`utils/idempotency.py`) consulta:

1. **MongoDB** (fuente de verdad): si la reserva existe, la ruta responde **200** con ella y no ejecuta la SAGA.
2. **Redis** (`pago:{reserva_id}`) y **PostgreSQL** (eventos con ese `aggregate_id`), best-effort: si hay coincidencia se cuenta en `idempotency_hit_total`, pero la SAGA **sí** se ejecuta (es el caso de un reintento después de un fallo, que debe poder completarse).

Además, dentro de la SAGA: el Lua no vuelve a cobrar si `pago:{reserva_id}` existe, `_id = reserva_id` en MongoDB, y el historial usa `$ne` sobre `reserva_id`.

Resultado medido: reintentar con el mismo `reserva_id` → 200 si ya estaba confirmada; 201 si el intento anterior había fallado (nada quedó a medias).

---

## Correlation ID

`X-Correlation-ID` (se genera si no viene) → logs estructurados, headers hacia Usuarios y Eventos, columna `correlation_id` de cada fila del `event_log` y header de la respuesta (también en los errores RFC 7807).

---

## Nota: compensaciones del orquestador

`SagaOrchestrator` también recibe `compensation_handlers` (pasos 4 y 5) y los ejecuta en `_handle_error()` para los pasos **anteriores** al que falló, a partir del 4. Como las compensaciones reales ya ocurrieron inline, esto es redundante: cuando falla el paso 5 agrega un `COMPENSACION_EJECUTADA` nominal del paso 4 (`accion: "COMPENSATION"`) cuyo handler solo escribe un log. Ver [[reservas-pagos]].

---

## Referencias

- [[saga-flow]] - Diagrama, Lua y tabla de errores
- [[chain-of-responsibility]] - Handlers
- [[reservation-schema]] - Esquemas MongoDB/Redis/PG
- [[event-sourcing-cqrs]] - Event Sourcing + CQRS
- [[consistency-strategy]] - Consistencia fuerte en SAGA
