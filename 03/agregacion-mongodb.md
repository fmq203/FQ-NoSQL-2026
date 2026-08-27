# Actividad 3 — Consultas avanzadas en MongoDB: Aggregation Framework

Todos los pipelines ejecutados y sus resultados están en
[agregacion-mongodb.js](agregacion-mongodb.js). Este archivo cubre el Paso 12
(preguntas a la IA) y una nota sobre una discrepancia encontrada en el enunciado.

## Nota sobre el "resultado esperado" del Paso 7

El PDF de la actividad indica como resultado esperado: **Ana $420, Bruno $250,
Carla $120, Diego $100**. Ejecutando el pipeline exactamente como lo pide la guía,
sobre los datos exactamente como los da la guía, el resultado real es:

```
{ _id: 1, total_gastado: 390 }   (Ana)
{ _id: 2, total_gastado: 250 }   (Bruno)
{ _id: 3, total_gastado: 120 }   (Carla)
{ _id: 4, total_gastado: 100 }   (Diego)
```

Verificación manual para Ana (cliente_id 1), que tiene dos pedidos:
- 2026-01-05: Teclado 1×$40 = $40, Mouse 2×$20 = $40 → subtotal $80
- 2026-02-01: Monitor 1×$250 = $250, Webcam 1×$60 = $60 → subtotal $310
- Total: $80 + $310 = **$390**, no $420.

Bruno, Carla y Diego sí coinciden con lo esperado ($250, $120, $100). Esto sugiere
que el $420 del enunciado es un error de la guía (o de una versión anterior del
dataset), no un error del pipeline: el `$match`/`$unwind`/`$group`/`$sort` es
exactamente el que pide el PDF y produce un resultado matemáticamente consistente
con los datos insertados en el Paso 4.

## Verificación de resultados

- [x] El paso 7 muestra el orden correcto de clientes por total gastado (Ana >
      Bruno > Carla > Diego), aunque el monto de Ana es $390 y no $420 (ver nota
      arriba).
- [x] El paso 8 muestra "Monitor" con 2 unidades y más ingresos ($500, el mayor de
      todos pese a tener pocas unidades).
- [x] El paso 9 agrupa por mes: 2026-01, 2026-02, 2026-03.
- [x] El paso 10 devuelve el nombre del cliente dentro de cada pedido vía `$lookup`.

## Paso 12 — Preguntas a la IA

**Mostrame la diferencia entre usar `$group { _id: "$cliente_id" }` y
`{ _id: null }`.**

`_id` en `$group` define el criterio de agrupación: cada valor distinto de esa
expresión genera un grupo separado. `{ _id: "$cliente_id" }` crea un grupo por cada
cliente distinto (como en el Paso 7, donde se obtiene un total por cliente).
`{ _id: null }` ignora cualquier criterio y mete **todos** los documentos que
llegaron a esa etapa en un único grupo, útil para calcular un agregado global (como
en el Paso 11, donde se calcula la facturación total de todo el negocio en una sola
fila de resultado, en vez de una fila por cliente).

**¿Cómo haría para quedarme solo con los 2 clientes que más gastaron?**

Agregando `$limit: 2` justo después del `$sort` del Paso 7, ya que el pipeline ya
deja los clientes ordenados de mayor a menor gasto:

```js
db.pedidos.aggregate([
  { $unwind: "$items" },
  { $project: {
    cliente_id: 1,
    subtotal: { $multiply: ["$items.cantidad", "$items.precio"] }
  } },
  { $group: { _id: "$cliente_id", total_gastado: { $sum: "$subtotal" } } },
  { $sort: { total_gastado: -1 } },
  { $limit: 2 }   // ← solo los 2 primeros del ranking
]);
// → Ana ($390) y Bruno ($250) con los datos de esta actividad
```

**¿Qué ventaja tiene `$lookup` frente a guardar los datos anidados? ¿Cuándo
conviene cada uno?**

Guardar los datos anidados (desnormalizados, como `editorial` dentro de cada libro
en la Actividad 2) evita una consulta extra: todo lo que se necesita leer junto
está en un solo documento, lo cual es rápido y simple mientras esos datos no
cambien mucho ni se compartan entre muchos documentos. `$lookup` (como en el Paso
10) conviene cuando el dato relacionado es compartido por muchos documentos y puede
cambiar con el tiempo — como los datos de un cliente, que se referencian desde
muchos pedidos: si el nombre de un cliente cambiara, con datos anidados habría que
actualizar todos los pedidos que lo repiten, mientras que con `$lookup` (guardando
solo `cliente_id`) alcanza con actualizar el documento del cliente una sola vez. En
resumen: anidar cuando el dato es propio y estable del documento (patrón "lo que se
lee junto se guarda junto"); referenciar + `$lookup` cuando el dato es compartido,
cambia independientemente, o crecería sin límite si se repitiera en cada documento
(por ejemplo, un cliente con miles de pedidos no debería llevar sus datos
duplicados miles de veces).

## Criterios cubiertos

- Datos cargados correctamente (clientes y pedidos, con arreglo `items` anidado).
- `$match` + `$unwind` correctos (Pasos 5 y 6).
- `$group` con `$sum`/`$avg` correcto (Pasos 7, 8, 9, 11).
- `$lookup` con la unión correcta (Paso 10, equivalente a JOIN).
- Consulta 11 (resumen general) ejecutada, con nota explicativa sobre qué
  representa realmente `total_pedidos` tras el `$unwind`.
