// Actividad 2 — Primeros pasos con MongoDB: CRUD y consultas
// Ejecutado contra el contenedor mongo-clase (mongo:7), base "biblioteca"
// Conexión usada: mongodb://admin:***@localhost:27017/biblioteca?authSource=admin
// (el contenedor de este entorno ya tenía --auth habilitado desde la Actividad 4;
//  todos los comandos son exactamente los mismos que sin autenticación, solo
//  cambia la cadena de conexión)

// ─────────────────────────────────────────────────────────────
// Paso 3 — Crear base de datos y colección
// ─────────────────────────────────────────────────────────────
use biblioteca
db.createCollection("libros")
// → { ok: 1 }

show collections
// → libros

// ─────────────────────────────────────────────────────────────
// Paso 4 — Insertar documentos
// ─────────────────────────────────────────────────────────────
db.libros.insertOne({
  titulo: "Cien años de soledad",
  autor: "Gabriel García Márquez",
  anio: 1967,
  precio: 450,
  categorias: ["Literatura", "Realismo mágico"],
  editorial: { nombre: "Sudamericana", pais: "Argentina" },
  disponible: true
})
// → { acknowledged: true, insertedId: ObjectId('6a901af242a67ca2e3b4cc3d') }

db.libros.insertMany([
  { titulo: "Dune", autor: "Frank Herbert", anio: 1965, precio: 520, categorias: ["Ciencia ficción"], editorial: { nombre: "Ace Books", pais: "EEUU" }, disponible: true },
  { titulo: "1984", autor: "George Orwell", anio: 1949, precio: 380, categorias: ["Distopía", "Ciencia ficción"], editorial: { nombre: "Secker", pais: "Inglaterra" }, disponible: false },
  { titulo: "Fahrenheit 451", autor: "Ray Bradbury", anio: 1953, precio: 410, categorias: ["Distopía", "Ciencia ficción"], editorial: { nombre: "Ballantine", pais: "EEUU" }, disponible: true },
  { titulo: "El principito", autor: "Antoine de Saint-Exupéry", anio: 1943, precio: 250, categorias: ["Infantil", "Fábula"], editorial: { nombre: "Reynal", pais: "Francia" }, disponible: true }
])
// → { acknowledged: true, insertedIds: { '0': ObjectId(...), '1': ObjectId(...), '2': ObjectId(...), '3': ObjectId(...) } }
// Total insertados: 5 libros (1 + 4). "Cien años de soledad" quedó con el documento
// anidado editorial: { nombre, pais }.

// ─────────────────────────────────────────────────────────────
// Paso 5 — Consultar documentos (Read)
// ─────────────────────────────────────────────────────────────
db.libros.find().pretty()
/* → 5 documentos: Cien años de soledad, Dune, 1984, Fahrenheit 451, El principito */

db.libros.find({ disponible: true }).pretty()
// → Cien años de soledad, Dune, Fahrenheit 451, El principito (4 libros)

db.libros.find({ precio: { $gt: 400 } }).pretty()
// → Cien años de soledad ($450), Dune ($520), Fahrenheit 451 ($410)

db.libros.find({ disponible: true, precio: { $gte: 400 } }).pretty()
// → Cien años de soledad, Dune, Fahrenheit 451

db.libros.find({ categorias: "Ciencia ficción" }).pretty()
// → Dune, 1984, Fahrenheit 451

db.libros.find({ "editorial.pais": "EEUU" }).pretty()
// → Dune, Fahrenheit 451

db.libros.find({ titulo: { $regex: "^(Cien|El)" } }).pretty()
// → Cien años de soledad, El principito

// ─────────────────────────────────────────────────────────────
// Paso 6 — Proyecciones
// ─────────────────────────────────────────────────────────────
db.libros.find({}, { titulo: 1, precio: 1, _id: 0 }).pretty()
/* →
{ titulo: 'Cien años de soledad', precio: 450 }
{ titulo: 'Dune', precio: 520 }
{ titulo: '1984', precio: 380 }
{ titulo: 'Fahrenheit 451', precio: 410 }
{ titulo: 'El principito', precio: 250 }
*/

// ─────────────────────────────────────────────────────────────
// Paso 7 — Contar y ordenar
// ─────────────────────────────────────────────────────────────
db.libros.countDocuments({ disponible: true })
// → 4

db.libros.find().sort({ precio: -1 }).pretty()
// → Dune $520, Cien años de soledad $450, Fahrenheit 451 $410, 1984 $380, El principito $250

db.libros.find().sort({ precio: -1 }).limit(3).pretty()
// → Dune $520, Cien años de soledad $450, Fahrenheit 451 $410

// ─────────────────────────────────────────────────────────────
// Paso 8 — Actualizar (Update)
// ─────────────────────────────────────────────────────────────
db.libros.updateOne(
  { titulo: "Dune" },
  { $set: { precio: 599 } }
)
// → { acknowledged: true, matchedCount: 1, modifiedCount: 1 }

db.libros.updateOne(
  { titulo: "1984" },
  { $push: { categorias: "Clásico" } }
)
// → { acknowledged: true, matchedCount: 1, modifiedCount: 1 }
// db.libros.findOne({ titulo: "1984" }).categorias → [ 'Distopía', 'Ciencia ficción', 'Clásico' ]

db.libros.updateMany(
  { disponible: false },
  { $set: { disponible: true } }
)
// → { acknowledged: true, matchedCount: 1, modifiedCount: 1 }
// countDocuments({ disponible: true }) pasó de 4 a 5

// ─────────────────────────────────────────────────────────────
// Paso 9 — Eliminar (Delete)
// ─────────────────────────────────────────────────────────────
db.libros.deleteOne({ titulo: "El principito" })
// → { acknowledged: true, deletedCount: 1 }

db.libros.deleteMany({ anio: { $lt: 1950 } })
// → { acknowledged: true, deletedCount: 1 }   (borró "1984", anio 1949)

db.libros.countDocuments()
// → 3
// Quedaron: Cien años de soledad (1967), Dune (1965), Fahrenheit 451 (1953)

// ─────────────────────────────────────────────────────────────
// Paso 10 — Preguntas a la IA (respondidas más abajo en el .md)
// ─────────────────────────────────────────────────────────────
