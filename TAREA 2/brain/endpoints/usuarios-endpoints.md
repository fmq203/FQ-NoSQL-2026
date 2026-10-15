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

> **Nota**: Los endpoints se definen en código (`src/api/routes.py`) con modelos Pydantic. FastAPI genera la especificación OpenAPI 3.1 automáticamente. Este archivo referencia la especificación generada, no la duplica.

---

## Endpoints

| Método | Ruta | Descripción | Consistencia |
|--------|------|-------------|--------------|
| GET | `/health` | Health check | — |
| POST | `/api/usuarios` | Crear usuario | Fuerte (write concern majority) |
| GET | `/api/usuarios` | Listar usuarios (paginado) | Eventual |
| GET | `/api/usuarios/{usuario_id}` | Obtener usuario + historial | Eventual |
| GET | `/api/usuarios/exportar` | Exportar anonimizado (GDPR) | Eventual |

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

**Response 201** (`Usuario`):
```json
{
  "usuario_id": "550e8400-e29b-41d4-a716-446655440000",
  "tipo_documento": "DNI",
  "nro_documento": "12345678",
  "nombre": "Juan",
  "apellido": "Pérez",
  "email": "juan@example.com",
  "creado_en": "2026-09-20T10:00:00Z",
  "historial_compras": []
}
```

**Errores**:
- 400: Datos inválidos (validación Pydantic)
- 409: Email o documento ya existe

---

### GET /api/usuarios

**Query Parameters**:
- `skip` (int, default: 0) - Registros a saltar
- `limit` (int, default: 10, max: 100) - Máximo registros

**Response 200**: Array de usuarios (sin historial_compras para performance)

---

### GET /api/usuarios/{usuario_id}

**Path Parameter**: `usuario_id` (UUID)

**Response 200** (`Usuario`): Usuario completo con `historial_compras[]`

**Errores**:
- 404: Usuario no encontrado
- 422: UUID inválido

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
- `Usuario` - Response con historial
- `UsuarioAnonimizado` - Item exportación
- `UsuarioExport` - Response exportación
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

- [[microservices/usuarios]] - Spec completa servicio
- [[data-models/user-schema]] - Modelo de datos MongoDB
- [[architecture/data-flow]] - Flujo de datos
- [[decisions/consistency-strategy]] - Consistencia eventual en lecturas