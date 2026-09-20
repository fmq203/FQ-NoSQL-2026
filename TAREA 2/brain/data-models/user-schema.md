---
name: user-schema
description: Schema de Usuario en MongoDB
metadata:
  type: specification
  status: draft
---

# Schema — Usuario (MongoDB)

## Colección: `usuarios`

```javascript
{
  _id: ObjectId,                      // PK
  
  // Identificación
  tipo_documento: "DNI" | "Pasaporte",
  nro_documento: "12345678",          // Unique index
  
  // Datos Personales
  nombre: "Juan",
  apellido: "Pérez",
  email: "juan@example.com",          // Unique index
  
  // Control
  creado_en: ISODate,
  actualizado_en: ISODate,
  
  // Historial de Compras (embedded array)
  historial_compras: [
    {
      reserva_id: ObjectId,
      evento_id: ObjectId,
      cantidad: 2,
      precio_unitario: 150.00,
      precio_total: 300.00,
      fecha_compra: ISODate,
      estado: "confirmada" | "cancelada"
    }
  ]
}
```

---

## Decisión: Embedded vs Reference

**✅ Decisión: EMBEDDED para `historial_compras`**

### Ventajas
- Lectura atómica (usuario + historial en un doc)
- Mejor rendimiento para queries comunes
- Evita JOIN (es NoSQL)

### Desventajas
- Array puede crecer (límite 16MB MongoDB)
- Actualización afecta documento completo

### Mitigación
- Paginación en lectura (GET /usuarios/{id}/historial)
- Archivado de registros antiguos

---

## Índices

```javascript
db.usuarios.createIndex({ "nro_documento": 1 }, { unique: true })
db.usuarios.createIndex({ "email": 1 }, { unique: true })
db.usuarios.createIndex({ "creado_en": -1 })
```

---

## Consultas Típicas

### Obtener usuario + historial
```javascript
db.usuarios.findOne({ _id: ObjectId(...) })
```

### Búsqueda por email (login)
```javascript
db.usuarios.findOne({ email: "juan@example.com" })
```

### Historial paginado
```javascript
db.usuarios.findOne(
  { _id: ObjectId(...) },
  { "historial_compras": { $slice: [0, 10] } }
)
```

---

## Anonimización (Opcional)

Para exportar datos anonimizados:
- nro_documento → hash (irreversible)
- email → hash
- nombre, apellido → remover
- historial_compras → mantener (sin datos personales)
