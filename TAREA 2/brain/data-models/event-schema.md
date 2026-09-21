---
name: event-schema
description: Esquema de datos de Evento para MongoDB
metadata:
  type: specification
  status: complete
---

# Esquema de Evento — MongoDB

## Colección: `eventos`

### Documento Completo

```json
{
  "_id": { "$uuid": "550e8400-e29b-41d4-a716-446655440001" },
  "nombre": "Concierto Rock 2026",
  "descripcion": "Gran festival de rock internacional",
  "fecha": { "$date": "2026-12-15T20:00:00.000Z" },
  "ubicacion": {
    "venue": "Estadio Central",
    "direccion": "Av. Principal 123",
    "ciudad": "Madrid",
    "pais": "España",
    "coordenadas": { "lat": 40.4168, "lng": -3.7038 }
  },
  "aforo_total": 50000,
  "entradas_disponibles": 48500,
  "precios": [
    { "categoria": "VIP", "precio": 200.0, "disponibles": 950 },
    { "categoria": "General", "precio": 80.0, "disponibles": 29000 },
    { "categoria": "Popular", "precio": 40.0, "disponibles": 18550 }
  ],
  "categorias": ["musica", "rock", "festival", "2026"],
  "estado": "publicado",
  "creado_en": { "$date": "2026-09-20T10:00:00.000Z" },
  "actualizado_en": { "$date": "2026-09-20T10:00:00.000Z" }
}
```

---

## Definición de Campos

| Campo | Tipo | Requerido | Validaciones |
|-------|------|-----------|--------------|
| `_id` | UUID | Sí | Auto v4 |
| `nombre` | String | Sí | 1-200 chars |
| `descripcion` | String | No | Max 2000 chars |
| `fecha` | DateTime | Sí | Futura, ISO 8601 |
| `ubicacion` | Object | Sí | Ver subdocumento |
| `aforo_total` | Int | Sí | > 0 |
| `entradas_disponibles` | Int | Sí | 0 <= x <= aforo_total |
| `precios` | Array | Sí | Ver subdocumento |
| `categorias` | Array<String> | No | Tags para búsqueda |
| `estado` | String | Sí | Enum: `borrador`, `publicado`, `cancelado`, `finalizado` |
| `creado_en` | DateTime | Sí | Auto UTC now |
| `actualizado_en` | DateTime | Sí | Auto UTC now |

---

## Subdocumento: ubicacion (EMBEDDED)

```json
{
  "venue": "Estadio Central",
  "direccion": "Av. Principal 123",
  "ciudad": "Madrid",
  "pais": "España",
  "coordenadas": { "lat": 40.4168, "lng": -3.7038 }
}
```

**Justificación Embedded**: Siempre se consulta con el evento, no se comparte entre eventos, tamaño fijo pequeño.

---

## Subdocumento: precios[] (EMBEDDED)

```json
[
  { "categoria": "VIP", "precio": 200.0, "disponibles": 950 },
  { "categoria": "General", "precio": 80.0, "disponibles": 29000 },
  { "categoria": "Popular", "precio": 40.0, "disponibles": 18550 }
]
```

| Campo | Tipo | Validaciones |
|-------|------|--------------|
| `categoria` | String | Único dentro del evento, 1-50 chars |
| `precio` | Double | >= 0 |
| `disponibles` | Int | >= 0, suma <= aforo_total |

**Justificación Embedded**: 
- Precios siempre se leen con el evento
- Categoría-precio es tupla atómica por evento
- Actualización atómica de `disponibles` por categoría

---

## Índices Requeridos

```javascript
// Consultas por fecha (listado cartelera)
db.eventos.createIndex({ "fecha": 1 }, { name: "idx_fecha_asc" })

// Filtro por estado + fecha (dashboard)
db.eventos.createIndex({ "estado": 1, "fecha": 1 }, { name: "idx_estado_fecha" })

// Búsqueda full-text
db.eventos.createIndex(
  { "nombre": "text", "descripcion": "text", "categorias": "text" },
  { name: "idx_text_search", weights: { nombre: 10, categorias: 5, descripcion: 1 } }
)

// Para SAGA: validación rápida de aforo
db.eventos.createIndex({ "entradas_disponibles": 1 }, { name: "idx_disponibles" })
```

---

## Patrones de Acceso

| Query | Índice | Consistencia |
|-------|--------|--------------|
| `findOne({_id})` | Primary | Eventual |
| `find({estado: "publicado", fecha: {$gte: now}}).sort({fecha: 1})` | `idx_estado_fecha` | Eventual |
| `find({$text: {$search: "rock"}})` | `idx_text_search` | Eventual |
| `findOne({_id, entradas_disponibles: {$gte: N}})` | Primary + filter | Eventual |

---

## Sincronización Inventario: MongoDB ↔ Redis

### Inicialización (al crear evento)
```python
async def inicializar_inventario_redis(redis, evento_id, aforo_total):
    await redis.set(f"inventario:{evento_id}", aforo_total)
    await redis.expire(f"inventario:{evento_id}", 86400)  # 24h TTL
```

### Decremento Atómico (SAGA paso 4 - Lua Script)
```lua
-- Verificar + Decrementar en una operación
local disponible = tonumber(redis.call('GET', KEYS[1]) or '0')
if disponible < tonumber(ARGV[1]) then
    return {0, 'INVENTARIO_INSUFICIENTE'}
end
redis.call('DECRBY', KEYS[1], ARGV[1])
return {1, 'OK'}
```

### Invalidación Cache Disponibilidad
```python
async def invalidar_cache_disponibilidad(redis, evento_id):
    await redis.delete(f"evento:disponibilidad:{evento_id}")
```

---

## Validaciones de Negocio

| Regla | Implementación |
|-------|----------------|
| `sum(precios[].disponibles) <= aforo_total` | Validación en `POST /api/eventos` y `PATCH` |
| `entradas_disponibles = sum(precios[].disponibles)` | Trigger en actualización de precios |
| `fecha > now()` para estado `publicado` | Validación en modelo Pydantic |
| `estado` transiciones válidas | `borrador → publicado → finalizado` o `cancelado` en cualquier momento |

---

## Referencias

- [[microservices/eventos]] — Especificación completa servicio
- [[architecture/saga-flow]] — Uso en validación de aforo
- [[decisions/consistency-strategy]] — Consistencia eventual en lecturas