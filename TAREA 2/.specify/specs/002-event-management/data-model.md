# Data Model: Event Management (Eventos Service)

**Date**: 2026-09-20

## MongoDB Collection: `eventos`

### Document Structure

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

### Field Definitions

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `_id` | UUID | Yes | PK, unique | Identificador único (v4) |
| `nombre` | String | Yes | 1-200 chars | Nombre del evento |
| `descripcion` | String | No | Max 2000 chars | Descripción |
| `fecha` | DateTime | Yes | Futura, ISO 8601 | Fecha/hora evento |
| `ubicacion` | Object | Yes | Ver abajo | Ubicación embebida |
| `aforo_total` | Int32 | Yes | > 0 | Capacidad total |
| `entradas_disponibles` | Int32 | Yes | 0 <= x <= aforo_total | Entradas libres |
| `precios` | Array | Yes | Ver abajo | Precios por categoría |
| `categorias` | Array<String> | No | Tags | Tags para búsqueda |
| `estado` | String | Yes | Enum: borrador, publicado, cancelado, finalizado | Estado |
| `creado_en` | DateTime | Yes | UTC, auto | Timestamp creación |
| `actualizado_en` | DateTime | Yes | UTC, auto | Timestamp actualización |

### Subdocument: ubicacion (EMBEDDED)

```json
{
  "venue": "Estadio Central",
  "direccion": "Av. Principal 123",
  "ciudad": "Madrid",
  "pais": "España",
  "coordenadas": { "lat": 40.4168, "lng": -3.7038 }
}
```

### Subdocument: precios[] (EMBEDDED)

```json
[
  { "categoria": "VIP", "precio": 200.0, "disponibles": 950 },
  { "categoria": "General", "precio": 80.0, "disponibles": 29000 },
  { "categoria": "Popular", "precio": 40.0, "disponibles": 18550 }
]
```

| Field | Type | Constraints |
|-------|------|-------------|
| `categoria` | String | Único por evento, 1-50 chars |
| `precio` | Double | >= 0 |
| `disponibles` | Int32 | >= 0, suma <= aforo_total |

**Embedded Justification**: Tupla atómica categoría-precio-disponibles, siempre consultada junta.

### Indexes

```javascript
// Consultas por fecha (cartelera)
db.eventos.createIndex({ "fecha": 1 }, { name: "idx_fecha_asc" })

// Filtro estado + fecha (dashboard admin)
db.eventos.createIndex({ "estado": 1, "fecha": 1 }, { name: "idx_estado_fecha" })

// Búsqueda full-text
db.eventos.createIndex(
  { "nombre": "text", "descripcion": "text", "categorias": "text" },
  { name: "idx_text_search", weights: { nombre: 10, categorias: 5, descripcion: 1 } }
)

// Validación rápida aforo (SAGA)
db.eventos.createIndex({ "entradas_disponibles": 1 }, { name: "idx_disponibles" })
```

## Redis Keys

| Key | Type | TTL | Description |
|-----|------|-----|-------------|
| `inventario:{evento_id}` | String | 86400 (renovado) | Contador entradas disponibles |
| `evento:disp:{evento_id}` | String | 30 | Cache disponibilidad lecturas |

### Inventario Operations

```python
# Inicializar (al crear evento)
await redis.set(f"inventario:{evento_id}", aforo_total)
await redis.expire(f"inventario:{evento_id}", 86400)

# Decremento atómico (Lua script - SAGA paso 4)
# Ver research.md para script completo

# Cache disponibilidad (cache-aside)
async def get_disponibilidad(evento_id):
    cached = await redis.get(f"evento:disp:{evento_id}")
    if cached: return int(cached)
    evento = await mongo.eventos.find_one({"_id": evento_id})
    disp = evento["entradas_disponibles"]
    await redis.setex(f"evento:disp:{evento_id}", 30, disp)
    return disp

# Invalidación (tras decremento)
await redis.delete(f"evento:disp:{evento_id}")
```

## Pydantic Models

### PrecioCategoria
```python
class PrecioCategoria(BaseModel):
    categoria: str = Field(..., min_length=1, max_length=50)
    precio: float = Field(..., ge=0)
    disponibles: int = Field(..., ge=0)
```

### EventoCreate (Request)
```python
class EventoCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    descripcion: str = Field(default="", max_length=2000)
    fecha: datetime  # Validado > now()
    ubicacion: Ubicacion
    aforo_total: int = Field(..., gt=0)
    precios: List[PrecioCategoria] = Field(..., min_items=1)
    categorias: List[str] = Field(default_factory=list)
    
    @field_validator('precios')
    @classmethod
    def validar_precios(cls, v, info):
        aforo = info.data.get('aforo_total', 0)
        total_disp = sum(p.disponibles for p in v)
        if total_disp > aforo:
            raise ValueError("Suma de disponibles excede aforo_total")
        categorias = [p.categoria for p in v]
        if len(categorias) != len(set(categorias)):
            raise ValueError("Categorías duplicadas")
        return v
```

### Evento (Response)
```python
class Evento(EventoCreate):
    evento_id: UUID
    entradas_disponibles: int
    estado: EstadoEvento = EstadoEvento.BORRADOR
    creado_en: datetime
    actualizado_en: datetime
```

### EstadoEvento Enum
```python
class EstadoEvento(str, Enum):
    BORRADOR = "borrador"
    PUBLICADO = "publicado"
    CANCELADO = "cancelado"
    FINALIZADO = "finalizado"
```

## Validation Rules (Single Source of Truth)

> **Referenced by**: spec.md (EM-FR-001, EM-FR-002), plan.md (Phase 3 validations)

| Field | Validation | Error Code | HTTP Status |
|-------|------------|------------|-------------|
| `nombre` | Required, 1-200 chars | `VALIDATION_ERROR` | 422 |
| `fecha` | Future datetime (ISO 8601) | `VALIDATION_ERROR` | 422 |
| `aforo_total` | Integer > 0 | `VALIDATION_ERROR` | 422 |
| `precios[].categoria` | Unique per event | `VALIDATION_ERROR` | 422 |
| `precios[].precio` | >= 0 | `VALIDATION_ERROR` | 422 |
| `precios[].disponibles` | >= 0 | `VALIDATION_ERROR` | 422 |
| `precios[]` | sum(disponibles) <= aforo_total | `VALIDATION_ERROR` | 422 |
| `estado` | Enum: borrador, publicado, cancelado, finalizado | `VALIDATION_ERROR` | 422 |
| Transiciones estado | borrador→publicado→finalizado, cancelado desde cualquier | `VALIDATION_ERROR` | 422 |

**Note**: All validation errors return RFC 7807 Problem Details format (see spec.md Error Response Schemas).

## Estado Transitions

```
BORRADOR → PUBLICADO → FINALIZADO
    ↓           ↓
  CANCELADO  CANCELADO
```

## Migration Strategy

### v1 → v2: Agregar coordenadas a ubicacion
```python
async def migrate_v1_to_v2(db):
    await db.eventos.update_many(
        {"ubicacion.coordenadas": {"$exists": False}},
        {"$set": {"ubicacion.coordenadas": {"lat": 0.0, "lng": 0.0}}}
    )
```

## References

- `brain/data-models/event-schema.md` - Schema completo
- `brain/data-models/db-choice-rationale.md` - Embedded vs Reference
- `brain/architecture/saga-flow.md` - Sincronización inventario
- MongoDB Text Search: https://www.mongodb.com/docs/manual/text-search/