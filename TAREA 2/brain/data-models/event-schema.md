---
name: event-schema
description: Esquema de datos de Evento para MongoDB
metadata:
  type: specification
  status: complete
---

# Esquema de Evento — MongoDB

**Última revisión contra el código:** 2026-11-05 (`eventos-service/src/models/evento.py`, `services/evento_service.py`, `services/mongodb.py`)

## Colección: `eventflow.eventos`

### Documento real

```json
{
  "_id": { "$binary": "<UUID v4, subtype 4>" },
  "nombre": "Concierto Demo",
  "estado": "publicado",
  "fecha": { "$date": "2026-12-05T20:00:00Z" },
  "aforo_total": 100,
  "entradas_disponibles": 98,
  "precios": [
    { "categoria": "general", "precio": "5000", "disponibles": 98 }
  ],
  "ubicacion": { "ciudad": "Buenos Aires", "pais": "Argentina", "direccion": null },
  "creado_en": { "$date": "2026-11-05T01:26:04.893Z" },
  "actualizado_en": { "$date": "2026-11-05T01:26:07.420Z" }
}
```

La API expone `_id` como `evento_id`. `precio` es `Decimal` en el modelo y se guarda como string para no perder precisión.

---

## Definición de Campos

| Campo | Tipo | Requerido | Validaciones |
|-------|------|-----------|--------------|
| `_id` | UUID | Sí | Generado (v4) |
| `nombre` | String | Sí | 1-200 caracteres, **único** (409 si se repite) |
| `estado` | String | Sí | `borrador`, `publicado`, `cancelado`, `finalizado` |
| `fecha` | DateTime | Sí | ISO 8601, años 1970-2100; sin zona se toma UTC, con zona se normaliza a UTC |
| `aforo_total` | Int | Sí | ≥ 0 |
| `entradas_disponibles` | Int | Sí | ≥ 0 y ≤ `aforo_total` |
| `precios` | Array | Sí | Al menos 1; ver abajo |
| `ubicacion` | Object | Sí | `ciudad`, `pais` (1-100), `direccion` opcional (≤ 500) |
| `creado_en` / `actualizado_en` | DateTime (UTC) | Sí | Los pone el servicio |

No hay `descripcion`, tags ni coordenadas.

---

## Subdocumento: `precios[]` (EMBEDDED)

| Campo | Tipo | Validaciones |
|-------|------|--------------|
| `categoria` | String | 1-100 caracteres, única dentro del evento |
| `precio` | Decimal | ≥ 0, máximo 2 decimales |
| `disponibles` | Int | ≥ 0; la suma de todas las categorías ≤ `entradas_disponibles` |

**Por qué embebido**: siempre se lee con el evento, no se comparte entre eventos y el inventario de una categoría se ajusta con una sola operación atómica sobre el documento.

`ubicacion` también es embebido por las mismas razones.

---

## Índices (creados al iniciar el servicio)

```javascript
db.eventos.createIndex({ nombre: 1 }, { unique: true })
db.eventos.createIndex({ estado: 1 })
db.eventos.createIndex({ creado_en: 1 })
db.eventos.createIndex({ estado: 1, creado_en: -1 })
```

No hay índice sobre `fecha` ni de texto: no existe un listado o búsqueda de eventos (`GET /api/eventos` no está implementado).

---

## Inventario: Eventos ↔ Redis

Hay **dos contadores** del mismo stock y se mantienen alineados desde la SAGA:

1. **Redis** (`evento:{id}:categoria:{cat}:disponibles`, en Reservas) es el que **decide** la venta: el Lua `pagar_y_decrementar` chequea y descuenta atómicamente. La clave se siembra con `SETNX` desde los `disponibles` que informó Eventos en el paso 3.
2. **MongoDB** (`precios[].disponibles` y `entradas_disponibles`) se actualiza después, con `POST /api/eventos/{id}/decrementar-inventario`:

```python
# evento_service._ajustar_inventario (signo = -1 venta, +1 compensación)
delta = signo * cantidad
query = {"_id": evento_id, "precios.categoria": categoria}
if signo < 0:  # al vender, exigir stock suficiente en esa categoría
    query["precios"] = {"$elemMatch": {"categoria": categoria, "disponibles": {"$gte": cantidad}}}
await collection.find_one_and_update(
    query,
    {"$inc": {"precios.$[elem].disponibles": delta, "entradas_disponibles": delta},
     "$set": {"actualizado_en": ahora}},
    array_filters=[{"elem.categoria": categoria}],
)
# sin match → 404 (no existe), 422 (categoría inexistente) o 409 (sin stock)
```

Si ese decremento falla, la SAGA revierte Redis (compensación del paso 4). El incremento (`/incrementar-inventario`) lo usa la compensación del paso 5. Ambos invalidan `cache:evento:{id}`.

---

## Patrones de Acceso

| Operación | Índice | Consistencia |
|-----------|--------|--------------|
| `GET /api/eventos/{id}` → `findOne({_id})` | Primario (y caché Redis DB 1) | Eventual (AP) |
| Alta → unicidad de `nombre` | Único | Fuerte |
| Decremento/incremento de inventario | Primario + `$elemMatch` | Fuerte (operación atómica sobre el documento) |

---

## Validaciones de Negocio (implementadas)

| Regla | Dónde |
|-------|-------|
| `entradas_disponibles ≤ aforo_total` | `model_validator` de `EventoCreate` → 422 |
| Categorías únicas dentro de `precios` | `model_validator` → 422 |
| `sum(precios[].disponibles) ≤ entradas_disponibles` | `model_validator` → 422 |
| Nombre de evento único | Índice único + chequeo previo → 409 |
| Solo eventos `publicado` se pueden comprar | Paso 3 de la SAGA → 409 `EVENT_NOT_AVAILABLE` |

No implementado: que la fecha sea futura, transiciones de estado (no hay endpoint para cambiar el estado).

---

## Referencias

- [[eventos]] — Especificación del servicio
- [[saga-flow]] — Uso en la validación y el decremento de inventario
- [[consistency-strategy]] — Consistencia eventual en lecturas
