---
name: user-schema
description: Esquema de datos de Usuario para MongoDB
metadata:
  type: specification
  status: complete
---

# Esquema de Usuario — MongoDB

**Última revisión contra el código:** 2026-11-05 (`usuarios-service/src/models/usuario.py`, `services/usuario_service.py`, `services/mongodb.py`)

## Colección: `eventflow.usuarios`

### Documento real

```json
{
  "_id": { "$binary": "<UUID v4, subtype 4>" },
  "tipo_documento": "DNI",
  "nro_documento": "377174497",
  "nombre": "Ada",
  "apellido": "Lovelace",
  "email": "ada@example.com",
  "creado_en": { "$date": "2026-11-05T01:26:03.677Z" },
  "actualizado_en": { "$date": "2026-11-05T01:26:07.464Z" },
  "historial_compras": [
    {
      "evento_id": { "$binary": "<UUID>" },
      "evento_nombre": "Concierto Demo",
      "fecha_compra": { "$date": "2026-11-05T01:26:07.464Z" },
      "entradas": 2,
      "total_pagado": 10000,
      "estado": "confirmada",
      "reserva_id": { "$binary": "<UUID>" }
    }
  ]
}
```

La API expone `_id` como `usuario_id`.

---

## Definición de Campos

| Campo | Tipo | Requerido | Validaciones | Índice |
|-------|------|-----------|--------------|--------|
| `_id` | UUID | Sí | Generado (v4) | Primario |
| `tipo_documento` | String | Sí | Enum: `DNI`, `Pasaporte` | Simple |
| `nro_documento` | String | Sí | 1-50 caracteres | Único |
| `nombre` | String | Sí | 1-100 caracteres | Simple |
| `apellido` | String | Sí | 1-100 caracteres | — |
| `email` | String | Sí | `EmailStr`, normalizado | Único |
| `creado_en` | DateTime (UTC) | Sí | Al crear | Simple |
| `actualizado_en` | DateTime (UTC) | Sí | Al crear y al agregar compras | — |
| `historial_compras` | Array | Sí (puede estar vacío) | Ver abajo | — |

Un email o documento repetido devuelve 409.

---

## Subdocumento: `historial_compras[]`

**Patrón: EMBEDDED.**

| Criterio | Decisión | Razón |
|----------|----------|-------|
| **Acceso** | Siempre se lee con el usuario | Una sola consulta (`GET /api/usuarios/{id}`) |
| **Atomicidad** | El `$push` de una compra es una operación sobre un único documento | Atómica sin transacciones |
| **Cardinalidad** | Pocas compras por usuario | Lejos del límite de 16 MB |
| **Crecimiento** | **Sin tope implementado** | Si un usuario acumulara miles de compras habría que paginar o mover el historial a su propia colección |

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `evento_id` | UUID | Evento comprado |
| `evento_nombre` | String | Copia del nombre (desnormalizado para no consultar Eventos al mostrar el historial) |
| `fecha_compra` | DateTime (UTC) | Momento del registro |
| `entradas` | Int | Cantidad de entradas |
| `total_pagado` | Float | Monto total |
| `estado` | String | `confirmada` |
| `reserva_id` | UUID (opcional) | Clave de idempotencia; referencia a `eventflow.reservas` |

### Cómo se agrega una compra

Lo hace Reservas al confirmar (paso 5 de la SAGA), con `POST /api/usuarios/{id}/historial`. Es **idempotente por `reserva_id`**:

```python
filtro = {"_id": usuario_id, "historial_compras.reserva_id": {"$ne": reserva_id}}
await collection.update_one(filtro, {
    "$push": {"historial_compras": compra},
    "$set": {"actualizado_en": ahora},
})
# modified_count 1 → 201 (agregada); 0 y el usuario existe → 200 (ya estaba); no existe → 404
```

Después invalida la entrada `cache:usuario:{id}` de la caché de lecturas.

---

## Índices (creados al iniciar el servicio)

```javascript
db.usuarios.createIndex({ email: 1 }, { unique: true })
db.usuarios.createIndex({ nro_documento: 1 }, { unique: true })
db.usuarios.createIndex({ creado_en: 1 })
db.usuarios.createIndex({ tipo_documento: 1 })
db.usuarios.createIndex({ nombre: 1 })
```

---

## Patrones de Acceso

| Operación | Índice | Consistencia |
|-----------|--------|--------------|
| `GET /api/usuarios/{id}` → `findOne({_id})` | Primario (y caché `redis-cache`) | Eventual (AP) |
| `GET /api/usuarios?skip&limit` | Colección | Eventual |
| Alta → unicidad de email y documento | Únicos | Fuerte (`w=majority`, journal) |
| Export → `find({})` | Recorrido completo | Eventual |

---

## Exportación anonimizada

Implementada en `GET /api/usuarios/exportar?format=json|csv`. Ver la sección de privacidad del README y [[data-flow]].

- **Se eliminan** (no se hashean): `nombre`, `apellido`, `email`, `nro_documento`, `usuario_id`, `reserva_id`.
- **Se conserva** `tipo_documento` (no identifica a nadie por sí solo).
- **Se generaliza**: `creado_en` → `mes_alta` (`YYYY-MM`); `fecha_compra` → solo el día.
- **Seudónimo**: `pseudonimo = HMAC-SHA256(clave, usuario_id)[:32]`.
  - `EXPORT_PSEUDONYM_KEY` vacía → clave aleatoria por proceso: los seudónimos cambian al reiniciar (**anonimización**).
  - Con valor → seudónimos estables entre exports (**seudonimización**: quien tiene la clave puede re-identificar).
- **CSV**: una fila por compra (usuarios sin compras incluidos) y celdas que empiezan con `= + - @` neutralizadas.

Sin k-anonimato: un historial muy particular cruzado con datos externos podría re-identificar.

---

## Referencias

- [[usuarios]] — Especificación del servicio
- [[db-selection]] — Justificación MongoDB + embebido
- [[usuarios-endpoints]] — API
