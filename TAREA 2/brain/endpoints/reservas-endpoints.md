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

---

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/reservar` | Iniciar SAGA + Chain of Responsibility |

---

## POST /api/reservar

**Inicia transacción distribuida SAGA con orquestación y Chain of Responsibility**

### Request Body (`ReservaRequest`)
```json
{
  "usuario_id": "550e8400-e29b-41d4-a716-446655440000",
  "evento_id": "550e8400-e29b-41d4-a716-446655440001",
  "cantidad": 2,
  "metodo_pago": "tarjeta"
}
```

**Validaciones**:
- `usuario_id`, `evento_id`: UUID válidos
- `cantidad`: entero > 0
- `metodo_pago`: enum ["tarjeta", "transferencia", "efectivo", "mercadopago"]

### Response 201 (`ReservaResponse`)
```json
{
  "reserva_id": "550e8400-e29b-41d4-a716-446655440002",
  "estado": "confirmada",
  "numero_confirmacion": "CONF-20260920-A1B2C3D4"
}
```

### Errores Comunes

| Código | Causa | Paso SAGA |
|--------|-------|-----------|
| 400 | Datos inválidos (cantidad<=0, método inválido) | 1 |
| 404 | Usuario no encontrado | 2 |
| 404 | Evento no encontrado | 3 |
| 409 | Inventario insuficiente | 3/4 |
| 500 | Error interno (Redis, MongoDB, PG) | 4/5/6 |
| 503 | Servicios downstream no disponibles | 2/3 |

---

## Flujo SAGA Interno (6 Pasos)

```
POST /api/reservar
    │
    ▼
1. ValidadorDeDatos          ──► Validación local
2. ValidadorInventario       ──► GET /api/usuarios/{id}
3. ValidadorEvento           ──► GET /api/eventos/{id} + aforo
4. ProcesadorPago (Lua)      ──► Redis: Pago + DECRBY inventario (ATÓMICO)
5. ConfirmadorReserva        ──► MongoDB INSERT reserva
6. Auditor                   ──► PostgreSQL INSERT event_log
    │
    ▼
Compensaciones automáticas si falla Paso 4-5
```

### Atomicidad Crítica (Paso 4)

```lua
-- Redis Lua Script: Verificar + Decrementar + Registrar Pago (ATÓMICO)
local disponible = tonumber(redis.call('GET', KEYS[1]) or '0')
if disponible < tonumber(ARGV[1]) then return {0, 'INVENTARIO_INSUFICIENTE'} end
redis.call('DECRBY', KEYS[1], ARGV[1])
redis.call('HSET', KEYS[2], 'reserva_id', ARGV[2], ...)
return {1, 'OK'}
```

### Compensaciones

| Fallo en | Acción |
|----------|--------|
| Paso 1-3 | Ninguna (solo lectura) |
| Paso 4 (Lua) | Rollback interno atómico (0 cambios) |
| Paso 5 (MongoDB) | DELETE reserva + Lua INCRBY inventario + DEL pago |
| Paso 6 (PostgreSQL) | Log WARNING only (reserva ya confirmada) |

---

## Idempotencia

- **Clave**: `reserva_id` (UUID v4) generado al inicio
- **MongoDB**: `_id = reserva_id` (unique)
- **Redis**: `pago:{reserva_id}` evita doble procesamiento
- **PostgreSQL**: `aggregate_id` detecta duplicados

---

## Correlation ID

- Generado al inicio: `X-Correlation-ID` header
- Propagado a: Usuarios Service, Eventos Service, PostgreSQL event_log, Redis keys
- Permite tracing distribuido completo

---

## Modelos Pydantic (Referencia)

Ver `brain/data-models/reservation-schema.md` para definiciones completas.

- `ReservaRequest` - Input
- `ReservaResponse` - Output 201
- `ReservaContext` - Dataclass interno (Chain of Responsibility)
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

- [[microservices/reservas-pagos]] - Spec completa servicio
- [[architecture/saga-flow]] - Flujo completo 6 pasos + compensaciones
- [[architecture/chain-of-responsibility]] - 6 handlers Chain of Responsibility
- [[patterns/saga-pattern]] - SAGA Orchestration
- [[patterns/event-sourcing-cqrs]] - Event Sourcing + CQRS en PostgreSQL
- [[data-models/reservation-schema]] - Esquemas MongoDB/Redis/PostgreSQL
- [[decisions/consistency-strategy]] - Consistencia fuerte en SAGA