---
name: three-database-strategy
description: Estrategia de 3 bases de datos - MongoDB, Redis, PostgreSQL
metadata:
  type: decision
  status: complete
  last-updated: 2026-11-05
---

# Estrategia de 3 Bases de Datos

**Última revisión contra el código:** 2026-11-05

## Arquitectura

```
                   EVENTFLOW 3-DATABASE ARCHITECTURE

┌──────────────────────┐  ┌───────────────────────┐  ┌──────────────────────┐
│ MONGODB              │  │ REDIS (2 instancias)  │  │ POSTGRESQL           │
│ (datos de negocio)   │  │                       │  │ (auditoría)          │
├──────────────────────┤  ├───────────────────────┤  ├──────────────────────┤
│ eventflow.usuarios   │  │ redis (transacción):  │  │ event_log            │
│   + historial        │  │  pago:{reserva_id}    │  │   (append-only)      │
│ eventflow.eventos    │  │  evento:..:disponibles│  │ vistas CQRS:         │
│   + precios          │  │ redis-cache (lecturas)│  │  ventas_por_evento   │
│ eventflow.reservas   │  │  cache:usuario:{id}   │  │  tasa_exito_saga     │
│   + saga_log         │  │  cache:evento:{id}    │  │  compensaciones_...  │
└──────────────────────┘  └───────────────────────┘  └──────────────────────┘
  lecturas AP (vía caché)    compra CP (Lua atómico)    registro ACID, no bloquea
```

---

## Responsabilidades por BD

### MongoDB — datos de negocio

- **Usuarios** (perfil + `historial_compras[]` embebido), **Eventos** (`precios[]` y `ubicacion` embebidos, inventario por categoría) y **Reservas** confirmadas (con `saga_log[]`).
- Un contenedor, una base (`eventflow`), una colección por servicio.
- Escrituras con `w=majority` + journal; índices únicos para email, documento, nombre de evento y número de confirmación.

### Redis — transacción crítica y caché (dos instancias)

- **`redis`** (Reservas): `evento:{id}:categoria:{cat}:disponibles` (contador) y `pago:{reserva_id}` (hash, TTL 90 días). El script Lua `pagar_y_decrementar` chequea stock, descuenta y registra el pago en una sola operación: Redis ejecuta un script a la vez, así que **no hay doble venta**. `compensar_pago` lo revierte.
- **`redis-cache`** (Usuarios y Eventos): caché de lecturas stale-if-error (fresco 30 s; copia vencida hasta 10 min / 1 h si MongoDB cae). Sin persistencia (es una copia descartable) y con tope de 128 MB (`allkeys-lru`).
- **Por qué dos instancias:** si la caché compartiera servidor con los pagos, un corte de Redis tumbaría las lecturas y las compras a la vez. Separadas, cada caída afecta solo a lo suyo (verificado: con `redis-cache` caído las compras siguen dando 201; con `redis` caído las lecturas siguen dando 200 `HIT` y solo falla comprar con 500 `PAYMENT_FAILED`).
- `redis` con persistencia AOF; ninguna de las dos tiene réplica.

### PostgreSQL — auditoría

- `event_log` append-only: un evento por paso de cada SAGA (incluidas las fallidas y las compensaciones), con `correlation_id` para seguir la petición.
- Vistas CQRS para análisis; índice GIN para consultar dentro del payload JSONB.
- No es fuente de verdad del negocio: si no responde, la compra sigue (se pierde ese registro).

---

## Flujo de una compra exitosa

```
POST /api/reservar
 ├─ Validar usuario y evento        → HTTP a Usuarios / Eventos (leen MongoDB, sin caché)
 ├─ Cobrar + descontar (atómico)    → Redis (`redis`), Lua
 ├─ Sincronizar inventario          → HTTP a Eventos → MongoDB ($elemMatch + $inc)
 ├─ Confirmar reserva               → MongoDB eventflow.reservas
 ├─ Registrar historial             → HTTP a Usuarios → MongoDB ($push idempotente)
 └─ Un evento por paso              → PostgreSQL event_log
Resultado: 201 Created
```

## Flujo de compensación

```
Falla la sincronización con Eventos (paso 4)
 ├─ Redis: Lua compensar_pago (INCRBY inventario + DEL pago)
 └─ PostgreSQL: PAGO_PROCESADO ya registrado → COMPENSACION_EJECUTADA → SAGA_FAILED
Resultado: 503 SERVICE_UNAVAILABLE (el cliente puede reintentar con el mismo reserva_id)

Falla el insert en MongoDB (paso 5)
 ├─ Redis: Lua compensar_pago
 ├─ Eventos: POST /incrementar-inventario
 └─ PostgreSQL: COMPENSACION_EJECUTADA → SAGA_FAILED
Resultado: 500 RESERVATION_FAILED
```

---

## Casos de uso de la auditoría

**"Me cobraron pero la compra falló"**: la línea de tiempo de la reserva muestra si el cobro se revirtió.

```sql
SELECT event_type, payload, timestamp FROM event_log
WHERE aggregate_id = '<reserva_id>' ORDER BY timestamp, id;
-- ... PAGO_PROCESADO → COMPENSACION_EJECUTADA → SAGA_FAILED
```

(Es lo que muestra `GET /api/reservar/{id}/audit` y la tarjeta "Auditoría" de la demo.)

**¿Dónde fallan las compras?**

```sql
SELECT payload->>'failed_step' AS paso, COUNT(*) FROM event_log
WHERE event_type = 'SAGA_FAILED' GROUP BY 1;
```

**Ventas por evento**: `SELECT * FROM ventas_por_evento;`

---

## Ventajas

| Ventaja | Detalle |
|---------|---------|
| **Especialización** | Documentos para el negocio, atomicidad en memoria para la venta, SQL para el análisis |
| **Consistencia por operación** | Lecturas AP (caché), compra fuerte (Lua + idempotencia + SAGA) |
| **Trazabilidad** | Cada compra, fallida o no, queda reconstruible desde PostgreSQL |
| **Privacidad** | Los datos personales viven solo en `eventflow.usuarios`; auditoría y reservas guardan identificadores |

## Desafíos

| Desafío | Cómo se manejó |
|---------|----------------|
| Dos contadores de stock (Redis y MongoDB) | Redis decide la venta; MongoDB se sincroniza en el mismo paso y, si falla, se revierte Redis |
| Complejidad operacional | Docker Compose, `make up` / `make test`, health checks por dependencia |
| Un solo nodo por base | Documentado; la disponibilidad de lecturas se resuelve con la caché, no con réplicas |
| Backups | No implementados |

---

## Alternativas rechazadas

- **Solo MongoDB**: la venta necesitaría transacciones multi-documento o un lock; el Lua de Redis lo resuelve en una operación sub-milisegundo.
- **MongoDB + Redis**: sin un log SQL append-only, analizar y auditar compras fallidas sería más difícil.
- **MongoDB + Redis + PostgreSQL**: seleccionada.

## Pendiente / no implementado

- Política de retención del `event_log`, cifrado de datos sensibles, backups, réplicas.
