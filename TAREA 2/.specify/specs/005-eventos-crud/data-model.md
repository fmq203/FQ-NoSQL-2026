# Data Model: Eventos CRUD Service

## Entities

### Evento (Main Entity)

**Collection**: `eventos` (MongoDB)

**Document Structure**:
```javascript
{
  "_id": UUID("..."),                    // PK, MongoDB _id as UUID v4
  "nombre": "string (1-200 chars)",       // Required, non-empty
  "estado": "borrador|publicado|cancelado|finalizado",  // Enum, required
  "aforo_total": 5000,                    // int >= 0, required
  "entradas_disponibles": 5000,           // int >= 0, <= aforo_total, required
  "precios": [                            // Array, non-empty, required
    {
      "categoria": "string",              // Required, unique within evento
      "precio": 15000.00,                 // Decimal >= 0, required
      "disponibles": 100                  // int >= 0, required
    }
  ],
  "ubicacion": {                          // Required object
    "ciudad": "string (1-100 chars)",     // Required, non-empty
    "pais": "string (1-100 chars)",       // Required, non-empty
    "direccion": "string (max 500 chars)" // Optional
  },
  "creado_en": ISODate("2026-09-23T10:00:00.000Z"),  // Auto-set on create
  "actualizado_en": ISODate("2026-09-23T10:00:00.000Z") // Auto-set on create/update
}
```

**Pydantic Model** (`src/models/evento.py`):
```python
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from enum import Enum

class EstadoEvento(str, Enum):
    BORRADOR = "borrador"
    PUBLICADO = "publicado"
    CANCELADO = "cancelado"
    FINALIZADO = "finalizado"

class PrecioCategoria(BaseModel):
    categoria: str = Field(..., min_length=1, max_length=100)
    precio: Decimal = Field(..., ge=0, decimal_places=2)
    disponibles: int = Field(..., ge=0)
    
    @field_validator('precio')
    @classmethod
    def validate_precio_precision(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError('precio must have at most 2 decimal places')
        return v

class Ubicacion(BaseModel):
    ciudad: str = Field(..., min_length=1, max_length=100)
    pais: str = Field(..., min_length=1, max_length=100)
    direccion: Optional[str] = Field(None, max_length=500)

class EventoCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    estado: EstadoEvento
    aforo_total: int = Field(..., ge=0)
    entradas_disponibles: int = Field(..., ge=0)
    precios: List[PrecioCategoria] = Field(..., min_length=1)
    ubicacion: Ubicacion
    
    @model_validator(mode='after')
    def validate_aforo_y_entradas(self) -> 'EventoCreate':
        if self.entradas_disponibles > self.aforo_total:
            raise ValueError('entradas_disponibles cannot exceed aforo_total')
        return self
    
    @model_validator(mode='after')
    def validate_precios_categorias_unicas(self) -> 'EventoCreate':
        categorias = [p.categoria for p in self.precios]
        if len(categorias) != len(set(categorias)):
            raise ValueError('categoria must be unique within precios')
        return self
    
    @model_validator(mode='after')
    def validate_precios_disponibles_sum(self) -> 'EventoCreate':
        total_disponibles = sum(p.disponibles for p in self.precios)
        if total_disponibles > self.entradas_disponibles:
            raise ValueError('sum of precios.disponibles cannot exceed entradas_disponibles')
        return self

class EventoResponse(EventoCreate):
    evento_id: UUID
    creado_en: datetime
    actualizado_en: datetime
    
    class Config:
        from_attributes = True
        populate_by_name = True

class EventoInDB(EventoResponse):
    """Internal model matching MongoDB document"""
    _id: UUID = Field(alias='evento_id')
    
    class Config:
        populate_by_name = True
```

### PrecioCategoria (Subdocument/Value Object)

Embedded in Evento.precios array. Not a separate collection.

**Validation Rules**:
- `categoria`: String, unique within the event's precios array
- `precio`: Decimal >= 0, max 2 decimal places
- `disponibles`: Integer >= 0
- Sum of all `disponibles` across categories <= `entradas_disponibles`

### Ubicacion (Subdocument/Value Object)

Embedded in Evento.ubicacion. Not a separate collection.

**Validation Rules**:
- `ciudad`: Required, 1-100 chars
- `pais`: Required, 1-100 chars
- `direccion`: Optional, max 500 chars

## Health Check Models

### HealthStatus (Enum)
```python
class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
```

### MongoDBHealth (Enum)
```python
class MongoDBHealth(str, Enum):
    OK = "ok"
    SLOW = "slow"
    DOWN = "down"
```

### HealthCheckResponse
```python
class HealthCheckResponse(BaseModel):
    status: HealthStatus
    checks: dict = Field(default_factory=dict)  # {"mongodb": MongoDBHealth}
    timestamp: datetime
    
    class Config:
        json_schema_extra = {
            "examples": [
                {"status": "healthy", "checks": {"mongodb": "ok"}, "timestamp": "2026-09-23T10:00:00.000Z"},
                {"status": "degraded", "checks": {"mongodb": "slow"}, "timestamp": "2026-09-23T10:00:00.000Z"},
                {"status": "unhealthy", "checks": {"mongodb": "down"}, "timestamp": "2026-09-23T10:00:00.000Z"}
            ]
        }
```

## Indexes

```javascript
// Automatic: _id (unique)
// Unique index for name (enables 409 DUPLICATE_EVENT)
db.eventos.createIndex({ "nombre": 1 }, { unique: true })
// Query performance indexes
db.eventos.createIndex({ "estado": 1 })
db.eventos.createIndex({ "creado_en": -1 })
db.eventos.createIndex({ "estado": 1, "creado_en": -1 })
```

## Consistency Model

| Operation | Write Concern | Read Preference | Timeout |
|-----------|---------------|-----------------|---------|
| Create (POST) | `majority` + `journal:true` | N/A | 5s |
| Read (GET) | N/A | `secondaryPreferred` | 5s |
| Health Check | N/A | `primary` (ping) | 2s |

**Rationale**:
- Writes: Strong consistency required for event creation (financial implications)
- Reads: Eventual consistency acceptable for reads (max staleness 1s)
- Health check: Primary ping for accurate connectivity status

## Migration/Versioning

No migrations needed for MVP. Schema changes would require:
1. New API version (v2) per Constitution Principle II
2. Migration script for existing documents
3. Backward compatibility period (90 days)

## Sample Documents

### Valid Event (Publicado)
```json
{
  "_id": "550e8400-e29b-41d4-a716-446655440000",
  "nombre": "Concierto Rock 2026",
  "estado": "publicado",
  "aforo_total": 5000,
  "entradas_disponibles": 5000,
  "precios": [
    {"categoria": "VIP", "precio": 15000.00, "disponibles": 100},
    {"categoria": "General", "precio": 5000.00, "disponibles": 4900}
  ],
  "ubicacion": {
    "ciudad": "Buenos Aires",
    "pais": "Argentina",
    "direccion": "Estadio Luna Park"
  },
  "creado_en": "2026-09-23T10:00:00.000Z",
  "actualizado_en": "2026-09-23T10:00:00.000Z"
}
```

### Valid Event (Borrador) - Zero Capacity
```json
{
  "_id": "550e8400-e29b-41d4-a716-446655440001",
  "nombre": "Evento Borrador",
  "estado": "borrador",
  "aforo_total": 0,
  "entradas_disponibles": 0,
  "precios": [
    {"categoria": "Gratis", "precio": 0.00, "disponibles": 0}
  ],
  "ubicacion": {
    "ciudad": "Montevideo",
    "pais": "Uruguay"
  },
  "creado_en": "2026-09-23T10:00:00.000Z",
  "actualizado_en": "2026-09-23T10:00:00.000Z"
}
```