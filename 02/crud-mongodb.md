# Actividad 2 — Primeros pasos con MongoDB: CRUD y consultas

Todos los comandos ejecutados están en [crud-mongodb.js](crud-mongodb.js). Este
archivo documenta las salidas de terminal (en lugar de capturas de pantalla, ya que
todo se ejecutó por línea de comandos) y las respuestas del Paso 10.

## Contenedor

```
$ docker ps --filter name=mongo-clase
CONTAINER ID   IMAGE     STATUS         PORTS
b1b452e305b2   mongo:7   Up             0.0.0.0:27017->27017/tcp
```

`docker exec -it mongo-clase mongosh` entra sin errores (con credenciales, ya que
este contenedor tiene `--auth` habilitado desde la Actividad 4).

## Al menos 3 consultas (evidencia de terminal)

**1) `$gt` — libros con precio mayor a 400:**

```
> db.libros.find({ precio: { $gt: 400 } }).pretty()
Cien años de soledad - $450
Dune - $520
Fahrenheit 451 - $410
```

**2) Búsqueda dentro de arreglo — categoría "Ciencia ficción":**

```
> db.libros.find({ categorias: "Ciencia ficción" }).pretty()
Dune
1984
Fahrenheit 451
```

**3) `$regex` — títulos que empiezan con "Cien" o "El":**

```
> db.libros.find({ titulo: { $regex: "^(Cien|El)" } }).pretty()
Cien años de soledad
El principito
```

**4) Campo anidado — `editorial.pais`:**

```
> db.libros.find({ "editorial.pais": "EEUU" }).pretty()
Dune
Fahrenheit 451
```

## Verificación de resultados

- [x] `docker exec -it mongo-clase mongosh` entra sin errores.
- [x] Se insertaron 5 libros; "Cien años de soledad" quedó con documento anidado
      `editorial: { nombre, pais }`.
- [x] Se hicieron consultas con `$gt`, `$in`-equivalente (`categorias` sobre arreglo),
      `$regex` y búsqueda en arreglo.
- [x] `countDocuments()` devolvió la cantidad esperada en cada paso (4 disponibles,
      3 al final tras los deletes).

## Paso 10 — Preguntas a la IA

**En MongoDB, ¿cuál es la diferencia entre `updateOne` y `replaceOne`? Mostrame un
ejemplo.**

`updateOne` modifica solo los campos indicados mediante operadores (`$set`, `$push`,
`$inc`, etc.), dejando el resto del documento intacto. `replaceOne` sustituye el
documento entero por uno nuevo (excepto `_id`), así que cualquier campo que no se
incluya en el reemplazo se pierde.

```js
// updateOne: solo cambia precio, el resto del documento de "Dune" queda igual
db.libros.updateOne({ titulo: "Dune" }, { $set: { precio: 599 } });

// replaceOne: reemplaza TODO el documento por este objeto
db.libros.replaceOne(
  { titulo: "Dune" },
  { titulo: "Dune", autor: "Frank Herbert", precio: 599 }
  // perdería anio, categorias, editorial y disponible si no se incluyen
);
```

**¿Cómo puedo buscar libros cuyo `editorial.pais` sea "EEUU" y con más de una
categoría?**

Combinando el filtro por campo anidado con `$expr` y `$size` (o comparando el
tamaño del arreglo):

```js
db.libros.find({
  "editorial.pais": "EEUU",
  $expr: { $gt: [{ $size: "$categorias" }, 1] }
});
```

En los datos de esta actividad, tras el `$push` de "Clásico" a 1984,
si 1984 tuviera `editorial.pais: "EEUU"` calificaría; con los datos actuales
("Fahrenheit 451" tiene 2 categorías y `editorial.pais: "EEUU"`) ese documento
cumple la condición.

**¿Qué es un cursor y por qué `find()` no devuelve directamente los documentos?**

Un cursor es un puntero del lado del servidor hacia el conjunto de resultados de
una consulta: `find()` no trae todos los documentos de inmediato, sino que devuelve
un objeto cursor que va pidiendo los resultados en lotes (batches) a medida que se
iteran (con `forEach`, `.pretty()`, `.toArray()`, etc.). Esto evita cargar en memoria
—de golpe— colecciones enormes: el cliente pagina los resultados según los va
necesitando, en vez de que el servidor arme y transmita todo de una sola vez.

## Reflexión sobre seguridad (adelanto del PDF)

Este contenedor específico ya corre con `--auth` (arrastrado de la Actividad 4). En
un `docker run` "limpio" de la Actividad 2 original, MongoDB queda **sin
contraseña**: cualquiera con acceso al puerto 27017 puede leer, modificar o borrar
todo. Es aceptable solo para prácticas locales, nunca para datos reales.
