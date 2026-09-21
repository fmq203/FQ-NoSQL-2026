---
name: user-schema
description: Esquema de datos de Usuario para MongoDB
metadata:
  type: specification
  status: complete
---

# Esquema de Usuario — MongoDB

## Colección: `usuarios`

### Documento Completo

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
      "cantidad": 2,
      "precio_total": 160.0,
      "fecha_compra": { "$date": "2026-09-20T10:05:00.000Z" },
      "estado": "confirmada"
    }
  ]
}
```

---

## Definición de Campos

| Campo | Tipo | Requerido | Validaciones | Índice |
|-------|------|-----------|--------------|--------|
| `_id` | UUID | Sí | Auto-generado (v4) | Primary (unique) |
| `tipo_documento` | String | Sí | Enum: `DNI`, `Pasaporte` | — |
| `nro_documento` | String | Sí | Único, 1-20 chars | Unique |
| `nombre` | String | Sí | 1-100 chars | — |
| `apellido` | String | Sí | 1-100 chars | — |
| `email` | String | Sí | Formato email, único | Unique |
| `creado_en` | DateTime | Sí | Auto UTC now | Descending |
| `historial_compras` | Array | No | Ver esquema abajo | — |

---

## Subdocumento: historial_compras[]

**Patrón: EMBEDDED** — Justificación:

| Criterio | Decisión | Razón |
|----------|----------|-------|
| **Cardinalidad** | One-to-Few (usuario tiene < 100 compras típicamente) | Embedded evita joins |
| **Acceso** | Siempre se lee con el usuario | Single query |
| **Tamaño** | Acotado (~2KB por compra, < 200KB total) | Límite 16MB document |
| **Atomicidad** | Actualizar historial + usuario en una operación | Transacción single-doc |
| **Crecimiento** | Limitado (archivar > 50 compras) | `$push` con `$slice` |

```json
{
  "reserva_id": { "$uuid": "..." },
  "evento_id": { "$uuid": "..." },
  "cantidad": { "$numberInt": "2" },
  "precio_total": { "$numberDouble": "160.0" },
  "fecha_compra": { "$date": "2026-09-20T10:05:00.000Z" },
  "estado": "confirmada"
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `reserva_id` | UUID | Referencia a reserva en colección `reservas` |
| `evento_id` | UUID | Referencia a evento (para consultas rápidas sin join) |
| `cantidad` | Int | Entradas compradas |
| `precio_total` | Double | Monto total de la compra |
| `fecha_compra` | DateTime | Timestamp de la transacción |
| `estado` | String | `confirmada`, `cancelada` |

---

## Índices Requeridos

```javascript
// Únicos (constraints de negocio)
db.usuarios.createIndex({ "email": 1 }, { unique: true, name: "idx_email_unique" })
db.usuarios.createIndex({ "nro_documento": 1 }, { unique: true, name: "idx_documento_unique" })

// Consultas frecuentes
db.usuarios.createIndex({ "creado_en": -1 }, { name: "idx_creado_en_desc" })
db.usuarios.createIndex({ "apellido": 1, "nombre": 1 }, { name: "idx_apellido_nombre" })

// Para exportación anonimizada (solo lectura de historial)
db.usuarios.createIndex({ "historial_compras.fecha_compra": -1 }, { name: "idx_historial_fecha" })
```

---

## Patrones de Acceso

| Query | Índice Usado | Consistencia |
|-------|--------------|--------------|
| `findOne({_id})` | Primary | Eventual |
| `findOne({email})` | `idx_email_unique` | Eventual |
| `findOne({nro_documento})` | `idx_documento_unique` | Eventual |
| `find().sort({creado_en: -1}).skip().limit()` | `idx_creado_en_desc` | Eventual |
| `find({}, {historial_compras: 1})` | Collection scan (exportación batch) | Eventual |

---

## Operaciones Críticas

### Crear Usuario (Write Concern: Majority)

```python
async def crear_usuario(db, usuario_doc):
    result = await db.usuarios.with_options(
        write_concern=WriteConcern(w='majority', j=True)
    ).insert_one(usuario_doc)
    return result.inserted_id
```

### Agregar Compra al Historial (Atómico Single-Doc)

```python
async def agregar_compra(db, usuario_id, compra_doc):
    await db.usuarios.update_one(
        {"_id": usuario_id},
        {
            "$push": {
                "historial_compras": {
                    "$each": [compra_doc],
                    "$slice": -50  # Mantener últimas 50
                }
            }
        }
    )
```

### Exportar Anonimizado (Read Only)

```python
async def exportar_anonimizado(db):
    cursor = db.usuarios.find(
        {}, 
        {"historial_compras": 1}  # Solo campos necesarios
    ).batch_size(1000)
    
    async for usuario in cursor:
        yield anonimizar(usuario)
```

---

## Anonimización (GDPR)

### Campos a Eliminar (PII)
- `nombre`, `apellido`, `email`
- `tipo_documento`, `nro_documento`

### Campos a Preservar (Análisis)
- `historial_compras[]` → agregados: `count`, `sum(precio_total)`

### Algoritmo: Hash Irreversible

```python
import hashlib
import os

SALT = os.getenv("ANONYMIZATION_SALT", "eventflow-salt-2026-change-in-prod")

def hash_usuario(usuario_id: UUID) -> str:
    """SHA-256 irreversible con salt"""
    return hashlib.sha256(
        f"{usuario_id}{SALT}".encode()
    ).hexdigest()
```

**Propiedades:**
- Irreversible: No se puede recuperar `usuario_id` del hash
- Determinista: Mismo usuario = mismo hash (para deduplicación en análisis)
- Salt único por despliegue: Evita rainbow tables

---

## Migración de Esquema (Versionado)

```python
# v1 → v2: Agregar campo 'telefono' opcional
async def migrate_v1_to_v2(db):
    await db.usuarios.update_many(
        {"telefono": {"$exists": False}},
        {"$set": {"telefono": None}}
    )
```

---

## Referencias

- [[microservices/usuarios]] — Especificación completa servicio
- [[decisions/db-selection]] — Justificación MongoDB + Embedded
- [[endpoints/usuarios-endpoints]] — API referencia