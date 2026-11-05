---
name: overview
description: Vista general de la arquitectura EventFlow
metadata:
  type: architecture
  status: complete
---

# EventFlow — Arquitectura General

**Última revisión contra el código:** 2026-11-05

## Contexto

**EventFlow** es una plataforma de gestión de eventos y venta de entradas construida con arquitectura de microservicios, bases de datos políglotas y patrones de consistencia distribuida (SAGA orquestada + Chain of Responsibility).

---

## Microservicios

| Servicio | Puerto | Responsabilidad Principal | Datos |
|----------|--------|---------------------------|-------|
| **Usuarios** | 8001 | Perfiles, historial de compras embebido, exportación anonimizada | MongoDB `eventflow.usuarios` + caché de lecturas en Redis (`redis-cache`) |
| **Eventos** | 8002 | Eventos, fecha, precios por categoría, inventario | MongoDB `eventflow.eventos` + caché de lecturas en Redis (`redis-cache`) |
| **Reservas y Pagos** | 8003 | Orquestador SAGA, Chain of Responsibility, cobro e inventario atómicos, auditoría | Redis `redis` (pagos + inventario, Lua), MongoDB `eventflow.reservas`, PostgreSQL `event_log` |

Un **único contenedor MongoDB** con una colección por servicio: separación lógica (cada servicio solo accede a la suya y llega a los datos de otro por su API), no *database-per-service* física.

---

## Bases de Datos (Políglota)

| DB | Tipo | Uso | Justificación |
|----|------|-----|---------------|
| **MongoDB 7.0** | Documental | Usuarios (con historial embebido), Eventos (precios embebidos), Reservas (con `saga_log`) | Esquema flexible, documentos embebidos, índices únicos |
| **Redis 7.0** | Clave-valor en memoria | Dos instancias: `redis` guarda `pago:{reserva_id}` y `evento:{id}:categoria:{cat}:disponibles` (scripts Lua); `redis-cache` guarda la caché AP de lecturas (`cache:usuario:*`, `cache:evento:*`) | Atomicidad de los scripts Lua (un script a la vez), velocidad, TTL |
| **PostgreSQL 15** | Relacional | `event_log` append-only (JSONB) + vistas CQRS | ACID, consultas analíticas, índice GIN sobre el payload |

---

## Patrones Implementados

| Patrón | Ubicación | Propósito |
|--------|-----------|-----------|
| **SAGA (orquestación)** | Reservas Service | Compra distribuida con compensaciones inline en los pasos 4 y 5 |
| **Chain of Responsibility** | Reservas Service | 6 handlers: validar datos → usuario → evento → procesar pago → confirmar reserva → auditar |
| **Event Sourcing (auditoría) + CQRS** | Reservas Service (PostgreSQL) | Cada paso queda como evento inmutable; vistas `ventas_por_evento`, `tasa_exito_saga`, `compensaciones_por_tipo` |
| **Caché stale-if-error** | Usuarios y Eventos | Lecturas disponibles con MongoDB caído (`X-Cache: HIT/MISS/STALE/BYPASS`) |
| **Minimización + seudónimo HMAC** | Usuarios Service | Export sin datos personales; anonimizado (clave efímera) o seudonimizado (clave fija) |

---

## Estrategia de Consistencia

| Operación | Consistencia | Cómo se logra |
|-----------|--------------|---------------|
| Lectura usuarios/eventos | **Eventual (AP)** | Caché Redis stale-if-error. `secondaryPreferred` está configurado pero MongoDB corre en un solo nodo (sin replica set), así que no se ejercita |
| Compra (reserva + pago) | **Fuerte** | Script Lua atómico (sin doble venta), idempotencia por `reserva_id`, SAGA con compensación, `w=majority` + journal |

Ver [[consistency-strategy]].

---

## Comunicación

- **Síncrona HTTP/REST** entre servicios: Reservas → Usuarios (validar usuario, registrar historial best-effort) y Reservas → Eventos (validar evento, decrementar/incrementar inventario). Reintentos 3× con backoff (0,5 / 1 / 2 s) y circuit breaker (abre con 5 fallos, half-open a los 30 s).
- **Atómica**: scripts Lua en Redis para pago + decremento de inventario y para su compensación.
- **Auditoría**: cada paso escribe en `event_log` en el momento (no hay mensajería asíncrona); un fallo de PostgreSQL no aborta la compra.

---

## Despliegue

- **Docker Compose**: 3 bases + 3 servicios, `make up` (build + up).
- **Health checks** en todos los contenedores; `/health` de cada servicio revisa sus dependencias.
- **Red compartida** `eventflow_network`; **volúmenes persistentes** `mongodb_data`, `redis_data` (AOF, solo `redis`; `redis-cache` no persiste), `postgresql_data`.

---

## Endpoints

```
Usuarios (8001):
  POST   /api/usuarios                       → Crear usuario
  GET    /api/usuarios                       → Listar (paginado)
  GET    /api/usuarios/{id}                  → Obtener con historial (caché AP)
  POST   /api/usuarios/{id}/historial        → Registrar compra (lo llama Reservas; idempotente)
  GET    /api/usuarios/exportar?format=json|csv → Export anonimizado

Eventos (8002):
  POST   /api/eventos                        → Crear evento
  GET    /api/eventos/{id}                   → Obtener (caché AP)
  POST   /api/eventos/{id}/decrementar-inventario → Lo llama Reservas (paso 4)
  POST   /api/eventos/{id}/incrementar-inventario → Compensación

Reservas (8003):
  POST   /api/reservar                       → SAGA + Chain of Responsibility (201 nueva, 200 reintento)
  GET    /api/reservar                       → Listar reservas
  GET    /api/reservar/{id}                  → Obtener reserva
  GET    /api/reservar/{id}/audit            → Eventos de la SAGA en PostgreSQL

Todos: GET /health, GET /metrics (Prometheus)
```

No existen `GET /api/eventos` (listado), ni `PUT`/`DELETE` de usuarios o eventos.

---

## Diagramas Relacionados

- [[microservices-diagram]] — Topología de servicios
- [[data-flow]] — Flujo de datos entre servicios
- [[saga-flow]] — Flujo transacción SAGA
- [[chain-of-responsibility]] — Cadena de validaciones
