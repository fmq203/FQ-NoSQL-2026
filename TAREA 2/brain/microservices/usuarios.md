---
name: usuarios
description: Especificación del Servicio de Usuarios
metadata:
  type: specification
  status: complete
---

# Servicio de Usuarios

## Responsabilidad

Gestiona perfiles de usuarios, historial de compras y exportación anonimizada para análisis (GDPR).

---

## Tecnologías

- **Framework**: FastAPI (Python 3.11)
- **Base de Datos**: MongoDB (colección `usuarios`)
- **Puerto**: 8001
- **Documentación**: http://localhost:8001/docs (Swagger), http://localhost:8001/redoc (ReDoc)

---

## Modelo de Datos

### Colección: `usuarios`

```json
{
  "_id": "UUID",
  "tipo_documento": "DNI | Pasaporte",
  "nro_documento": "string (único)",
  "nombre": "string",
  "apellido": "string",
  "email": "string (único, formato email)",
  "creado_en": "ISODate",
  "historial_compras": [
    {
      "reserva_id": "UUID",
      "evento_id": "UUID",
      "cantidad": "int",
      "precio_total": "float",
      "fecha_compra": "ISODate",
      "estado": "confirmada | cancelada"
    }
  ]
}
```

### Índices

```javascript
db.usuarios.createIndex({ "email": 1 }, { unique: true })
db.usuarios.createIndex({ "nro_documento": 1 }, { unique: true })
db.usuarios.createIndex({ "creado_en": -1 })
```

---

## Endpoints

| Método | Ruta | Descripción | Consistencia |
|--------|------|-------------|--------------|
| GET | `/health` | Health check | — |
| POST | `/api/usuarios` | Crear usuario | Fuerte (write concern majority) |
| GET | `/api/usuarios` | Listar usuarios (paginado) | Eventual |
| GET | `/api/usuarios/{usuario_id}` | Obtener usuario + historial | Eventual |
| GET | `/api/usuarios/exportar` | Exportar anonimizado (GDPR) | Eventual |

### Detalle de Endpoints

#### POST /api/usuarios
```json
// Request
{
  "tipo_documento": "DNI",
  "nro_documento": "12345678",
  "nombre": "Juan",
  "apellido": "Pérez",
  "email": "juan@example.com"
}

// Response 201
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

#### GET /api/usuarios?skip=0&limit=10
```json
// Response 200
[
  { "usuario_id": "...", "nombre": "...", "email": "...", "creado_en": "..." }
]
```

#### GET /api/usuarios/{usuario_id}
```json
// Response 200
{
  "usuario_id": "...",
  "nombre": "Juan",
  "email": "juan@example.com",
  "historial_compras": [
    { "reserva_id": "...", "evento_id": "...", "cantidad": 2, "precio_total": 150.0, "fecha_compra": "...", "estado": "confirmada" }
  ]
}
```

#### GET /api/usuarios/exportar?format=json|csv
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

---

## Anonimización (GDPR)

### Estrategia: minimización + pseudónimo con HMAC + generalización

Implementación: `UsuarioService._to_anonimizado()` y `_pseudonimo()` (`usuarios-service/src/services/usuario_service.py`).

- **Eliminados** (no hasheados): `nombre`, `apellido`, `email`, `nro_documento`. Un hash sin clave de un DNI de 8 dígitos o de un nombre se revierte por diccionario en segundos, así que no era una anonimización irreversible (la versión inicial usaba SHA-256 truncado: se descartó).
- **`pseudonimo`** = HMAC-SHA256(`EXPORT_PSEUDONYM_KEY`, `usuario_id`)[:32]. El `usuario_id` es un UUID v4 aleatorio (no enumerable). Sin clave configurada se genera una al azar por proceso (anonimización); con clave fija los pseudónimos son estables (seudonimización, para seguimiento de cohortes; la clave se custodia aparte).
- **Generalizados**: alta → `YYYY-MM`; compra → `YYYY-MM-DD`; se omite `reserva_id`.
- **Preservados** (valor analítico): `tipo_documento`, historial (`evento_id`, `evento_nombre`, `entradas`, `total_pagado`, `estado`).
- CSV: una fila por compra; neutraliza *formula injection* (celdas que empiezan con `= + - @`).

---

## Validaciones

| Campo | Reglas |
|-------|--------|
| `tipo_documento` | Enum: `DNI`, `Pasaporte` |
| `nro_documento` | Requerido, único, string |
| `nombre` | Requerido, string, 1-100 chars |
| `apellido` | Requerido, string, 1-100 chars |
| `email` | Requerido, formato email válido, único |

---

## Errores Comunes

| Código | Causa |
|--------|-------|
| 400 | Datos inválidos (validación Pydantic) |
| 409 | Email o documento ya existe |
| 404 | Usuario no encontrado (GET by ID) |
| 500 | Error interno BD |

---

## Integración con Otros Servicios

### Reservas Service → Usuarios Service
- **GET** `/api/usuarios/{usuario_id}` — Validar existencia en SAGA paso 2
- **Consistencia**: Eventual (read preference secondaryPreferred)
- **Timeout**: 5s con reintentos

---

## Testing

```bash
# Unit tests
pytest usuarios-service/tests/ -v

# Integration tests (requiere MongoDB)
docker compose exec usuarios-service pytest -v

# Load test (JMeter opcional)
# Ver brain/deployment/deployment-checklist.md
```

---

## Referencias

- [[data-models/user-schema]] — Esquema detallado
- [[endpoints/usuarios-endpoints]] — Referencia OpenAPI
- [[architecture/data-flow]] — Flujo de datos
- [[decisions/db-selection]] — Justificación MongoDB