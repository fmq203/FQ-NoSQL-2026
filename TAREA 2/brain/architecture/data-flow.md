---
name: data-flow
description: Flujo de datos entre microservicios EventFlow
metadata:
  type: architecture
  status: complete
---

# Flujo de Datos — EventFlow

**Última revisión contra el código:** 2026-11-05

## Flujo Principal: Compra de Entrada (SAGA)

```mermaid
sequenceDiagram
    participant Client
    participant RS as Reservas Service<br/>(Orquestador)
    participant US as Usuarios Service
    participant ES as Eventos Service
    participant Redis
    participant MongoDB
    participant PG as PostgreSQL

    Client->>RS: POST /api/reservar<br/>{usuario_id, evento_id, cantidad, categoria, metodo_pago, reserva_id?}

    Note over RS: Chain of Responsibility (en serie):<br/>1. ValidadorDeDatos 2. ValidadorInventario (usuario)<br/>3. ValidadorEvento 4. ProcesadorPago<br/>5. ConfirmadorReserva 6. Auditor

    RS->>PG: SAGA_STARTED
    RS->>US: GET /api/usuarios/{usuario_id} (no-cache)
    US-->>RS: 200 / 404 USER_NOT_FOUND
    RS->>PG: USUARIO_VALIDADO

    RS->>ES: GET /api/eventos/{evento_id} (no-cache)
    ES-->>RS: 200 (estado, precios[], disponibles) / 404
    RS->>PG: EVENTO_VALIDADO

    Note over RS,Redis: Paso 4: Lua pagar_y_decrementar (atómico)
    RS->>Redis: EVALSHA (inventario_key, pago:{reserva_id})
    Redis-->>RS: OK / INVENTARIO_INSUFICIENTE
    RS->>PG: PAGO_PROCESADO
    RS->>ES: POST /api/eventos/{id}/decrementar-inventario

    alt Eventos no responde
        RS->>Redis: Lua compensar (INCRBY + DEL pago)
        RS->>PG: COMPENSACION_EJECUTADA, SAGA_FAILED
        RS-->>Client: 503 SERVICE_UNAVAILABLE
    else Eventos OK
        RS->>PG: INVENTARIO_DECREMENTADO
        RS->>MongoDB: insert reserva (_id = reserva_id)
        alt Insert falla
            RS->>Redis: Lua compensar
            RS->>ES: POST /incrementar-inventario
            RS->>PG: COMPENSACION_EJECUTADA, SAGA_FAILED
            RS-->>Client: 500 RESERVATION_FAILED
        else Insert OK
            RS->>PG: RESERVA_CONFIRMADA
            RS->>US: POST /api/usuarios/{id}/historial (best-effort)
            RS->>PG: HISTORIAL_ACTUALIZADO o HISTORIAL_PENDIENTE
            RS->>PG: SAGA_COMPLETED
            RS-->>Client: 201 {reserva_id, estado: "confirmada", numero_confirmacion}
        end
    end
```

Si fallan los pasos 1 a 3 no se modificó nada: 404 / 409 / 422 / 503 y `SAGA_FAILED`, sin compensación. Un reintento con el mismo `reserva_id` de una reserva ya confirmada devuelve **200** sin volver a cobrar.

---

## Flujo: Lectura de Usuario o Evento (caché AP)

```mermaid
sequenceDiagram
    participant Client
    participant S as Usuarios / Eventos Service
    participant Cache as Redis DB 1
    participant MongoDB

    Client->>S: GET /api/usuarios/{id} (o /api/eventos/{id})
    S->>Cache: GET cache:usuario:{id}
    alt Fresca (< 30 s)
        Cache-->>S: documento
        S-->>Client: 200 (X-Cache: HIT)
    else Vencida o ausente
        S->>MongoDB: findOne({_id: id})
        alt MongoDB responde
            MongoDB-->>S: documento
            S->>Cache: SET (TTL stale: 600 s usuarios / 3600 s eventos)
            S-->>Client: 200 (X-Cache: MISS)
        else MongoDB caído y hay entrada vencida
            S-->>Client: 200 (X-Cache: STALE)
        else MongoDB caído sin entrada
            S-->>Client: 503 + Retry-After: 5
        end
    end
```

Con `Cache-Control: no-cache` (lo usa la SAGA) se lee siempre de MongoDB (`X-Cache: BYPASS`). Las escrituras que cambian el dato (inventario, historial) invalidan la entrada; los 404 no se cachean.

---

## Flujo: Exportación Anonimizada

```mermaid
sequenceDiagram
    participant Client
    participant US as Usuarios Service
    participant MongoDB

    Client->>US: GET /api/usuarios/exportar?format=json|csv
    US->>MongoDB: find({})
    MongoDB-->>US: Cursor usuarios

    Note over US: Minimización:<br/>- Se eliminan nombre, apellido, email, nro_documento, usuario_id, reserva_id<br/>- pseudonimo = HMAC-SHA256(clave, usuario_id)[:32]<br/>- Se generalizan mes de alta y fecha de compra<br/>- CSV: celdas neutralizadas contra inyección de fórmulas

    US-->>Client: 200 [{pseudonimo, tipo_documento, mes_alta, historial_compras}] (o text/csv)
```

---

## Flujo: Escritura del Event Log

`insert_event_log(event_type, aggregate_id, payload, correlation_id)` → `INSERT INTO event_log (event_type, aggregate_id, aggregate_type, payload, correlation_id)`; `id` y `timestamp` los pone PostgreSQL. La función atrapa sus errores: si PostgreSQL falla, la compra sigue.

Eventos: `SAGA_STARTED`, `USUARIO_VALIDADO`, `EVENTO_VALIDADO`, `PAGO_PROCESADO`, `INVENTARIO_DECREMENTADO`, `RESERVA_CONFIRMADA`, `HISTORIAL_ACTUALIZADO` / `HISTORIAL_PENDIENTE`, `SAGA_COMPLETED`, `SAGA_FAILED`, `COMPENSACION_EJECUTADA`.

---

## Resumen de Flujos por Consistencia

| Flujo | Consistencia | Medido | Patrón |
|-------|--------------|--------|--------|
| Lectura usuario / evento | Eventual (AP) | p50 ≈ 8-10 ms local | Caché stale-if-error + MongoDB |
| Listar usuarios / reservas | Eventual | — | Paginado (`skip`, `limit` ≤ 100) |
| Compra de entrada | **Fuerte** | ≈ 100 ms aislada; satura en ≈ 50 req/s | SAGA + Redis Lua |
| Export anonimizado | Eventual | — | Minimización + HMAC |

---

## Datos que Fluyen Entre Servicios

| Origen → Destino | Datos | Frecuencia |
|------------------|-------|------------|
| Reservas → Usuarios | `GET` usuario (validación); `POST historial` (compra) | Por reserva |
| Reservas → Eventos | `GET` evento; `decrementar-inventario` (y `incrementar` al compensar) | Por reserva |
| Reservas → Redis | `pago:{reserva_id}`, `evento:{id}:categoria:{cat}:disponibles` | Por reserva (atómico) |
| Reservas → MongoDB | Documento de reserva con `saga_log` | Por reserva exitosa |
| Reservas → PostgreSQL | Un evento por paso | Por paso de la SAGA |

---

## Consideraciones de Rendimiento

1. **Validaciones en serie**: la cadena valida usuario y después evento (no en paralelo).
2. **Redis Lua**: pago + inventario en una sola operación atómica (un round-trip).
3. **Índices MongoDB** (reales):
   - `usuarios`: `email` (único), `nro_documento` (único), `creado_en`, `tipo_documento`, `nombre`
   - `eventos`: `nombre` (único), `estado`, `creado_en`, `{estado, creado_en}`
   - `reservas`: `usuario_id`, `evento_id`, `estado`, `creado_en`, `{usuario_id, creado_en}`, `{evento_id, estado}`, `numero_confirmacion` (único), `{estado, creado_en}` y TTL de 24 h para `pendiente`/`fallida`
4. **Clientes HTTP**: `httpx.AsyncClient` reutilizado, 3 reintentos con backoff y circuit breaker.
