---
name: usuarios-endpoints
description: Referencia a endpoints de Usuarios Service (OpenAPI auto-generado)
metadata:
  type: specification
  status: complete
---

# Endpoints: Usuarios Service

## Fuente de Verdad

**OpenAPI Spec auto-generado por FastAPI**: http://localhost:8001/openapi.json  
**Swagger UI**: http://localhost:8001/docs  
**ReDoc**: http://localhost:8001/redoc

> **Nota** (revisado contra el código 2026-11-05): Los endpoints se definen en código (`src/api/routes/usuarios.py`, `health.py`, `metrics.py`) con modelos Pydantic. FastAPI genera la especificación OpenAPI 3.1 automáticamente. Este archivo referencia la especificación generada, no la duplica.

---

## Endpoints

| Método | Ruta | Descripción | Consistencia |
|--------|------|-------------|--------------|
| GET | `/health` | Health check (MongoDB) | — |
| GET | `/metrics` | Métricas Prometheus | — |
| POST | `/api/usuarios` | Crear usuario | Fuerte (write concern majority) |
| GET | `/api/usuarios` | Listar usuarios (paginado) | Eventual |
| GET | `/api/usuarios/{usuario_id}` | Obtener usuario + historial (caché AP) | Eventual |
| POST | `/api/usuarios/{usuario_id}/historial` | Registrar una compra (lo llama Reservas) | Fuerte, idempotente por `reserva_id` |
| GET | `/api/usuarios/exportar` | Exportar anonimizado | Eventual |

Si MongoDB no responde (y no hay caché que servir) cualquier endpoint devuelve **503** `service-unavailable` con `Retry-After: 5`.

---

## Referencia Rápida (desde OpenAPI)

### POST /api/usuarios

**Request Body** (`UsuarioCreate`):
```json
{
  "tipo_documento": "DNI",
  "nro_documento": "12345678",
  "nombre": "Juan",
  "apellido": "Pérez",
  "email": "juan@example.com"
}
```

**Response 201** (`UsuarioResponse`):
```json
{
  "usuario_id": "550e8400-e29b-41d4-a716-446655440000",
  "tipo_documento": "DNI",
  "nro_documento": "12345678",
  "nombre": "Juan",
  "apellido": "Pérez",
  "email": "juan@example.com",
  "creado_en": "2026-09-20T10:00:00Z",
  "actualizado_en": "2026-09-20T10:00:00Z",
  "historial_compras": []
}
```

El email se guarda en minúsculas.

**Errores**:
- 422: Datos inválidos (validación Pydantic), RFC 7807
- 409: Email o documento ya existe

---

### GET /api/usuarios

**Query Parameters**:
- `skip` (int, default: 0) - Registros a saltar
- `limit` (int, default: 10, max: 100) - Máximo registros

**Response 200**: Array de `UsuarioResponse` (incluye `historial_compras`)

---

### GET /api/usuarios/{usuario_id}

**Path Parameter**: `usuario_id` (UUID)

**Response 200** (`UsuarioResponse`): Usuario completo con `historial_compras[]`

**Caché AP**: header `X-Cache` = `HIT` (Redis, < 30 s), `MISS` (leído de MongoDB), `STALE` (MongoDB caído, copia vencida de hasta 10 min) o `BYPASS` (el cliente mandó `Cache-Control: no-cache`, como hace la SAGA). Los 404 no se cachean.

**Errores**:
- 404: Usuario no encontrado
- 422: UUID inválido
- 503: MongoDB no disponible y sin copia en caché (o lectura `no-cache`)

---

### POST /api/usuarios/{usuario_id}/historial

Lo llama Reservas al confirmar una compra (best-effort: si falla, la reserva queda igual y se registra `HISTORIAL_PENDIENTE`).

**Request Body** (`CompraRegistrar`):
```json
{
  "reserva_id": "uuid",
  "evento_id": "uuid",
  "evento_nombre": "Concierto Rock 2026",
  "entradas": 2,
  "total_pagado": 10000.0,
  "estado": "confirmada"
}
```

**Response** (`CompraRegistrada`: `{usuario_id, reserva_id, registrada}`):
- **201** `registrada: true` — compra agregada
- **200** `registrada: false` — esa `reserva_id` ya estaba (reintento idempotente)
- 404 usuario inexistente; 422 datos inválidos

Invalida `cache:usuario:{id}`.

---

### GET /api/usuarios/exportar

**Query Parameter**: `format` (string, enum: `json`, `csv`, default: `json`)

**Response 200** (JSON, lista de `UsuarioAnonimizado`; con `?format=csv` devuelve `text/csv`, una fila por compra):
```json
[
  {
    "pseudonimo": "9f2c41d0a7b3e85561c0d4aa7e3b9f12",
    "tipo_documento": "DNI",
    "mes_alta": "2026-09",
    "historial_compras": [
      {
        "evento_id": "7b8b32a1-7b35-4b82-8362-a97b1c19bd71",
        "evento_nombre": "Concierto Rock 2026",
        "fecha_compra": "2026-10-15",
        "entradas": 3,
        "total_pagado": 7500.0,
        "estado": "confirmada"
      }
    ]
  }
]
```

**Anonimización**: se **eliminan** `nombre`, `apellido`, `email` y `nro_documento` (no se hashean: son datos de baja entropía y un hash se revierte por diccionario). `pseudonimo` = HMAC-SHA256(clave del servidor, `usuario_id`); `mes_alta` y `fecha_compra` están generalizados. El historial se preserva sin `reserva_id`. Estrategia completa y justificación en el [README](../../README.md#-privacidad-de-datos-y-exportación-anonimizada).

---

## Modelos Pydantic (Referencia)

Ver `brain/data-models/user-schema.md` para definiciones completas.

- `UsuarioCreate` - Request POST
- `UsuarioResponse` - Response con historial
- `CompraRegistrar` / `CompraRegistrada` - Registro de compra en el historial
- `UsuarioAnonimizado` / `CompraAnonimizada` - Items de la exportación
- `TipoDocumento` - Enum: DNI, Pasaporte

---

## Especificación Completa

```bash
# Obtener spec completo
curl http://localhost:8001/openapi.json | jq '.paths'

# Ver solo schemas
curl http://localhost:8001/openapi.json | jq '.components.schemas'
```

---

## Referencias Relacionadas

- [[usuarios]] - Spec completa servicio
- [[user-schema]] - Modelo de datos MongoDB
- [[data-flow]] - Flujo de datos
- [[consistency-strategy]] - Consistencia eventual en lecturas