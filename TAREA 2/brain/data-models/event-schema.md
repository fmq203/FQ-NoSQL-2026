---
name: event-schema
description: Schema de Evento en MongoDB
metadata:
  type: specification
  status: draft
---

# Schema — Evento (MongoDB)

## Colección: `eventos`

```javascript
{
  _id: ObjectId,                      // PK
  
  // Información Básica
  nombre: "Concierto de Rock 2026",
  fecha: ISODate,                     // Index
  lugar: "Estadio Nacional",
  descripcion: "...",
  
  // Aforo y Entradas
  aforo_total: 50000,                 // Inmutable
  entradas_vendidas: 12345,           // Actualizado por SAGA
  entradas_disponibles: 37655,        // = aforo_total - vendidas
  precio_entrada: 150.00,
  
  // Categorías (opcional)
  categorias: [
    {
      nombre: "VIP",
      precio: 250.00,
      disponibles: 1000
    },
    {
      nombre: "General",
      precio: 150.00,
      disponibles: 36655
    }
  ],
  
  // Control
  creado_en: ISODate,
  actualizado_en: ISODate,
  estado: "activo" | "cancelado" | "finalizado"
}
```

---

## Decisión: Embedded vs Reference para Categorías

**✅ EMBEDDED para categorías**

Razón: Categorías son atributos del evento, no documentos independientes. Búsquedas siempre juntas.

---

## Índices

```javascript
db.eventos.createIndex({ "fecha": 1 })
db.eventos.createIndex({ "lugar": 1 })
db.eventos.createIndex({ "estado": 1 })
db.eventos.createIndex({ "creado_en": -1 })
```

---

## Consultas Típicas

### Eventos activos por fecha
```javascript
db.eventos.find({ estado: "activo", fecha: { $gte: ISODate(...) } })
  .sort({ fecha: 1 })
```

### Disponibilidad rápida (cached)
```javascript
db.eventos.findOne({ _id: ObjectId(...) }, { entradas_disponibles: 1 })
```

---

## Operación Crítica: Decrement (desde SAGA)

```javascript
db.eventos.updateOne(
  { _id: ObjectId(...), entradas_disponibles: { $gte: 2 } },
  { $inc: { entradas_vendidas: 2, entradas_disponibles: -2 } }
)
```

**Nota:** Condición `$gte: 2` previene sobreventa.

---

## Caché Strategy

- Resultado de GET /eventos/{id} cacheado en Redis (TTL 5 min)
- Invalidación al decrementar inventario
