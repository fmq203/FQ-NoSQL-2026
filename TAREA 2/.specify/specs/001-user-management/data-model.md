# Data Model: User Management (Usuarios Service)

**Date**: 2026-09-20

## MongoDB Collection: `usuarios`

### Document Structure

```json
{
  "_id": { "$uuid": "550e8400-e29b-41d4-a716-446655440000" },
  "tipo_documento": "DNI",
  "nro_documento": "12345678",
  "nombre": "Juan",
  "apellido": "Pérez",
  "email": "juan@example.com",
  "creado_en": { "$date": "2026-09-20T10:00:00.000Z" },
  "historial_compras": [
    {
      "reserva_id": { "$uuid": "550e8400-e29b-41d4-a716-446655440001" },
      "evento_id": { "$uuid": "550e8400-e29b-41d4-a716-446655440002" },
      "cantidad": { "$numberInt": "2" },
      "precio_total": { "$numberDouble": "160.0" },
      "fecha_compra": { "$date": "2026-09-20T10:05:00.000Z" },
      "estado": "confirmada"
    }
  ]
}
```

### Field Definitions

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `_id` | UUID | Yes | PK, unique | Identificador único (v4) |
| `tipo_documento` | String | Yes | Enum: `DNI`, `Pasaporte` | Tipo de documento identidad |
| `nro_documento` | String | Yes | Unique, 1-20 chars | Número de documento |
| `nombre` | String | Yes | 1-100 chars | Nombre(s) |
| `apellido` | String | Yes | 1-100 chars | Apellido(s) |
| `email` | String | Yes | Unique, RFC 5322 | Email único |
| `creado_en` | DateTime | Yes | UTC, auto | Timestamp creación |
| `historial_compras` | Array | No | Max 50 items | Compras embebidas |

### Subdocument: historial_compras[]

```json
{
  "reserva_id": "UUID",
  "evento_id": "UUID",
  "cantidad": "Int32",
  "precio_total": "Double",
  "fecha_compra": "DateTime",
  "estado": "String"  // "confirmada" | "cancelada"
}
```

**Embedded Justification**: Ver `brain/data-models/db-choice-rationale.md`

### Indexes

```javascript
// Unique constraints (business rules)
db.usuarios.createIndex({ "email": 1 }, { unique: true, name: "idx_email_unique" })
db.usuarios.createIndex({ "nro_documento": 1 }, { unique: true, name: "idx_documento_unique" })

// Query performance
db.usuarios.createIndex({ "creado_en": -1 }, { name: "idx_creado_en_desc" })
db.usuarios.createIndex({ "apellido": 1, "nombre": 1 }, { name: "idx_apellido_nombre" })

// Exportación/análisis
db.usuarios.createIndex({ "historial_compras.fecha_compra": -1 }, { name: "idx_historial_fecha" })
```

## Pydantic Models

### UsuarioCreate (Request)
```python
class UsuarioCreate(BaseModel):
    tipo_documento: TipoDocumento  # Enum DNI|Pasaporte
    nro_documento: str = Field(..., min_length=1, max_length=20)
    nombre: str = Field(..., min_length=1, max_length=100)
    apellido: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
```

### Usuario (Response - incluye _id y creado_en)
```python
class Usuario(UsuarioCreate):
    usuario_id: UUID
    creado_en: datetime
    historial_compras: List[CompraHistorial] = Field(default_factory=list)
```

### CompraHistorial (Embedded)
```python
class CompraHistorial(BaseModel):
    reserva_id: UUID
    evento_id: UUID
    cantidad: int = Field(..., gt=0)
    precio_total: float = Field(..., ge=0)
    fecha_compra: datetime
    estado: Literal["confirmada", "cancelada"]
```

### UsuarioAnonimizado (Export GDPR)
```python
class UsuarioAnonimizado(BaseModel):
    usuario_hash: str  # SHA-256 irreversible
    eventos_comprados: int  # count(historial_compras)
    gasto_total: float  # sum(precio_total)
```

### UsuarioExport (Response Export)
```python
class UsuarioExport(BaseModel):
    usuarios_anonimizados: List[UsuarioAnonimizado]
```

## Anonimización Algorithm

```python
def anonimizar_usuario(usuario: Usuario) -> UsuarioAnonimizado:
    """Anonimización irreversible GDPR-compliant"""
    import hashlib
    import os
    
    SALT = os.getenv("ANONYMIZATION_SALT", "eventflow-salt-2026")
    
    usuario_hash = hashlib.sha256(
        f"{usuario.usuario_id}{SALT}".encode()
    ).hexdigest()
    
    return UsuarioAnonimizado(
        usuario_hash=usuario_hash,
        eventos_comprados=len(usuario.historial_compras),
        gasto_total=round(sum(c.precio_total for c in usuario.historial_compras), 2)
    )
```

**Properties**:
- Irreversible: SHA-256 one-way
- Determinista: Mismo input = mismo hash
- Salt rotativo: Configurable via `ANONYMIZATION_SALT`
- Preserva analítica: count + sum mantenidos

## Migration Strategy

### v1 → v2: Agregar campo opcional `telefono`
```python
async def migrate_v1_to_v2(db):
    await db.usuarios.update_many(
        {"telefono": {"$exists": False}},
        {"$set": {"telefono": None}}
    )
```

### v2 → v3: Cambiar historial_compras a referencia (si > 500 items)
```python
# Solo si power users superan límite 16MB
# 1. Crear colección `usuario_compras`
# 2. Migrar historial > 50 items
# 3. Mantener últimas 50 en embedded
# 4. Agregar campo `historial_archivado: bool`
```

## Validation Rules

| Field | Validation | Error Code |
|-------|------------|------------|
| `tipo_documento` | Enum DNI|Pasaporte | 422 |
| `nro_documento` | Required, unique, 1-20 chars | 422 / 409 |
| `nombre` | Required, 1-100 chars | 422 |
| `apellido` | Required, 1-100 chars | 422 |
| `email` | Required, EmailStr, unique | 422 / 409 |

## References

- `brain/data-models/user-schema.md` - Schema detallado
- `brain/data-models/db-choice-rationale.md` - Embedded vs Reference
- `brain/decisions/db-selection.md` - Justificación MongoDB
- MongoDB Schema Design: https://www.mongodb.com/docs/manual/core/schema-design/