// Actividad 3 — Consultas avanzadas en MongoDB: Aggregation Framework
// Ejecutado contra el contenedor mongo-clase (mongo:7), base "comercio"
// Conexión usada: mongodb://admin:***@localhost:27017/comercio?authSource=admin

// ─────────────────────────────────────────────────────────────
// Paso 2 — Base de datos
// ─────────────────────────────────────────────────────────────
use comercio

// ─────────────────────────────────────────────────────────────
// Paso 3 — Insertar clientes
// ─────────────────────────────────────────────────────────────
db.clientes.insertMany([
  { _id: 1, nombre: "Ana", ciudad: "Montevideo" },
  { _id: 2, nombre: "Bruno", ciudad: "Salto" },
  { _id: 3, nombre: "Carla", ciudad: "Montevideo" },
  { _id: 4, nombre: "Diego", ciudad: "Paysandú" }
])
// → { acknowledged: true, insertedIds: { '0': 1, '1': 2, '2': 3, '3': 4 } }

// ─────────────────────────────────────────────────────────────
// Paso 4 — Insertar pedidos con detalle en arreglo
// ─────────────────────────────────────────────────────────────
db.pedidos.insertMany([
  { cliente_id: 1, fecha: "2026-01-05", items: [
    { producto: "Teclado", cantidad: 1, precio: 40 },
    { producto: "Mouse", cantidad: 2, precio: 20 } ] },
  { cliente_id: 2, fecha: "2026-01-08", items: [
    { producto: "Monitor", cantidad: 1, precio: 250 } ] },
  { cliente_id: 1, fecha: "2026-02-01", items: [
    { producto: "Monitor", cantidad: 1, precio: 250 },
    { producto: "Webcam", cantidad: 1, precio: 60 } ] },
  { cliente_id: 3, fecha: "2026-02-10", items: [
    { producto: "Teclado", cantidad: 3, precio: 40 } ] },
  { cliente_id: 4, fecha: "2026-03-15", items: [
    { producto: "Mouse", cantidad: 5, precio: 20 } ] }
])
// → 5 pedidos insertados

// ─────────────────────────────────────────────────────────────
// Paso 5 — Filtrar con $match
// ─────────────────────────────────────────────────────────────
db.pedidos.aggregate([
  { $match: { fecha: { $gte: "2026-02-01" } } }
])
// → 3 pedidos: cliente 1 (2026-02-01), cliente 3 (2026-02-10), cliente 4 (2026-03-15)

// ─────────────────────────────────────────────────────────────
// Paso 6 — Desarmar el arreglo con $unwind
// ─────────────────────────────────────────────────────────────
db.pedidos.aggregate([
  { $unwind: "$items" }
])
/* → 7 documentos (uno por cada item):
   1 | 2026-01-05 | Teclado x1
   1 | 2026-01-05 | Mouse x2
   2 | 2026-01-08 | Monitor x1
   1 | 2026-02-01 | Monitor x1
   1 | 2026-02-01 | Webcam x1
   3 | 2026-02-10 | Teclado x3
   4 | 2026-03-15 | Mouse x5
*/

// ─────────────────────────────────────────────────────────────
// Paso 7 — Calcular el total por pedido/cliente
// ─────────────────────────────────────────────────────────────
db.pedidos.aggregate([
  { $unwind: "$items" },
  { $project: {
    cliente_id: 1,
    fecha: 1,
    subtotal: { $multiply: ["$items.cantidad", "$items.precio"] }
  } },
  { $group: {
    _id: "$cliente_id",
    total_gastado: { $sum: "$subtotal" }
  } },
  { $sort: { total_gastado: -1 } }
])
/* → RESULTADO REAL obtenido con estos datos:
   { _id: 1, total_gastado: 390 }   (Ana)
   { _id: 2, total_gastado: 250 }   (Bruno)
   { _id: 3, total_gastado: 120 }   (Carla)
   { _id: 4, total_gastado: 100 }   (Diego)

   NOTA: el PDF de la actividad indica como "resultado esperado" Ana $420, pero
   sumando manualmente los items de la actividad para cliente_id 1
   (Teclado 1x40=40 + Mouse 2x20=40 + Monitor 1x250=250 + Webcam 1x60=60 = 390),
   el total correcto según los datos dados es $390, no $420. Es una discrepancia
   en el enunciado, no un error del pipeline (el pipeline es correcto).
*/

// ─────────────────────────────────────────────────────────────
// Paso 8 — Productos más vendidos (por cantidad)
// ─────────────────────────────────────────────────────────────
db.pedidos.aggregate([
  { $unwind: "$items" },
  { $group: {
    _id: "$items.producto",
    unidades: { $sum: "$items.cantidad" },
    ingresos: { $sum: { $multiply: ["$items.cantidad", "$items.precio"] } }
  } },
  { $sort: { unidades: -1 } }
])
/* →
   { _id: 'Mouse',    unidades: 7, ingresos: 140 }
   { _id: 'Teclado',  unidades: 4, ingresos: 160 }
   { _id: 'Monitor',  unidades: 2, ingresos: 500 }
   { _id: 'Webcam',   unidades: 1, ingresos: 60  }

   Mouse tiene más unidades vendidas (7), pero Monitor genera más ingresos ($500)
   con solo 2 unidades, porque su precio unitario es mucho más alto.
*/

// ─────────────────────────────────────────────────────────────
// Paso 9 — Estadísticas por mes
// ─────────────────────────────────────────────────────────────
db.pedidos.aggregate([
  { $unwind: "$items" },
  { $group: {
    _id: { $substr: ["$fecha", 0, 7] },
    ventas: { $sum: { $multiply: ["$items.cantidad", "$items.precio"] } },
    promedio_item: { $avg: "$items.precio" }
  } },
  { $sort: { _id: 1 } }
])
/* →
   { _id: '2026-01', ventas: 330, promedio_item: 103.33 }
   { _id: '2026-02', ventas: 430, promedio_item: 116.67 }
   { _id: '2026-03', ventas: 100, promedio_item: 20 }
*/

// ─────────────────────────────────────────────────────────────
// Paso 10 — Unir colecciones con $lookup
// ─────────────────────────────────────────────────────────────
db.pedidos.aggregate([
  { $lookup: {
    from: "clientes",
    localField: "cliente_id",
    foreignField: "_id",
    as: "cliente"
  } },
  { $unwind: "$cliente" },
  { $project: {
    _id: 0,
    cliente_nombre: "$cliente.nombre",
    ciudad: "$cliente.ciudad",
    total_items: { $size: "$items" }
  } }
])
/* →
   { cliente_nombre: 'Ana',   ciudad: 'Montevideo', total_items: 2 }
   { cliente_nombre: 'Bruno', ciudad: 'Salto',       total_items: 1 }
   { cliente_nombre: 'Ana',   ciudad: 'Montevideo', total_items: 2 }
   { cliente_nombre: 'Carla', ciudad: 'Montevideo', total_items: 1 }
   { cliente_nombre: 'Diego', ciudad: 'Paysandú',   total_items: 1 }
*/

// ─────────────────────────────────────────────────────────────
// Paso 11 — Resumen general (todos juntos)
// ─────────────────────────────────────────────────────────────
db.pedidos.aggregate([
  { $match: { fecha: { $gte: "2026-01-01" } } },
  { $unwind: "$items" },
  { $group: { _id: null,
    total_pedidos: { $sum: 1 },
    facturacion_total: { $sum: { $multiply: ["$items.cantidad", "$items.precio"] } },
    ticket_promedio: { $avg: { $multiply: ["$items.cantidad", "$items.precio"] } }
  } }
])
/* →
   { _id: null, total_pedidos: 7, facturacion_total: 860, ticket_promedio: 122.86 }

   NOTA: "total_pedidos: 7" en realidad cuenta líneas de ítem (tras el $unwind),
   no pedidos distintos — hay 5 pedidos reales pero 7 ítems en total. El nombre
   del campo es algo engañoso; para contar pedidos distintos habría que agrupar
   por _id del pedido antes de sumar 1, o usar $addToSet / distinct sobre _id.
*/
