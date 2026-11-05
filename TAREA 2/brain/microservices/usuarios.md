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

Revisado contra el código: 2026-11-05.

---

## Tecnologías

- **Framework**: FastAPI (Python 3.11)
- **Base de Datos**: MongoDB (`eventflow.usuarios`) + Redis DB 1 (caché de lecturas, `cache:usuario:{id}`)
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
  "email": "string (único, en minúsculas)",
  "creado_en": "ISODate",
  "actualizado_en": "ISODate",
  "historial_compras": [
    {
      "evento_id": "UUID",
      "evento_nombre": "string",
      "fecha_compra": "ISODate",
      "entradas": "int",
      "total_pagado": "float",
      "estado": "confirmada",
      "reserva_id": "UUID (clave de idempotencia)"
    }
  ]
}
```

Detalle en [[user-schema]].

### Índices

```javascript
db.usuarios.createIndex({ email: 1 }, { unique: true })
db.usuarios.createIndex({ nro_documento: 1 }, { unique: true })
db.usuarios.createIndex({ creado_en: 1 })
db.usuarios.createIndex({ tipo_documento: 1 })
db.usuarios.createIndex({ nombre: 1 })
```

---

## Endpoints

| Método | Ruta | Descripción | Consistencia |
|--------|------|-------------|--------------|
| GET | `/health` | Health check | — |
| GET | `/metrics` | Prometheus | — |
| POST | `/api/usuarios` | Crear usuario | Fuerte (write concern majority) |
| GET | `/api/usuarios` | Listar usuarios (paginado) | Eventual |
| GET | `/api/usuarios/{usuario_id}` | Obtener usuario + historial (caché AP, `X-Cache`) | Eventual |
| POST | `/api/usuarios/{usuario_id}/historial` | Registrar compra (lo llama Reservas) | Fuerte, idempotente |
| GET | `/api/usuarios/exportar` | Exportar anonimizado (GDPR) | Eventual |

Detalle de cada endpoint en [[usuarios-endpoints]].

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
  "actualizado_en": "2026-09-20T10:00:00Z",
  "historial_compras": []
}
```

#### GET /api/usuarios?skip=0&limit=10
Array de usuarios completos (mismo formato que el GET por id, con historial).

#### GET /api/usuarios/{usuario_id}
```json
// Response 200 (header X-Cache: HIT | MISS | STALE | BYPASS)
{
  "usuario_id": "...",
  "nombre": "Juan",
  "email": "juan@example.com",
  "historial_compras": [
    { "evento_id": "...", "evento_nombre": "Concierto", "fecha_compra": "...", "entradas": 2, "total_pagado": 10000.0, "estado": "confirmada", "reserva_id": "..." }
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
| `nro_documento` | Requerido, único, 1-50 chars |
| `nombre` | Requerido, string, 1-100 chars |
| `apellido` | Requerido, string, 1-100 chars |
| `email` | Requerido, formato email válido, único, se normaliza a minúsculas |

---

## Errores Comunes

| Código | Causa |
|--------|-------|
| 422 | Datos inválidos (validación Pydantic), RFC 7807 |
| 409 | Email o documento ya existe |
| 404 | Usuario no encontrado |
| 503 | MongoDB no disponible (con `Retry-After: 5`); el GET por id responde igual desde la caché si hay copia |
| 500 | Error interno no previsto |

---

## Integración con Otros Servicios

### Reservas Service → Usuarios Service
- **GET** `/api/usuarios/{usuario_id}` — Validar existencia en SAGA paso 2, con `Cache-Control: no-cache` (nunca recibe datos de la caché).
- **POST** `/api/usuarios/{usuario_id}/historial` — Registrar la compra en el paso 5 (best-effort).
- **Timeout**: 5 s (2 s de conexión), 3 reintentos con backoff 0,5 / 1 / 2 s y circuit breaker.

---

## Testing

```bash
make test           # las suites de los 3 servicios dentro de sus contenedores (usuarios: 56 tests)
make jmeter          # carga: incluye GET /api/usuarios/{id}
```

---

## Referencias

- [[user-schema]] — Esquema detallado
- [[usuarios-endpoints]] — Referencia OpenAPI
- [[data-flow]] — Flujo de datos
- [[db-selection]] — Justificación MongoDB