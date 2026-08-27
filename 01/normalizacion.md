# Normalización de la tabla `biblioteca`

## Tabla original (sin normalizar)

| libro_id | titulo | autor | categoria | socios |
|---|---|---|---|---|
| 1 | Cien años | G. Márquez | Literatura | Ana, Luis |
| 2 | Dune | F. Herbert | Ciencia ficción | Ana |
| 1 | Cien años | G. Márquez | Literatura | Pedro |

**Dependencias funcionales presentes:**
- `libro_id → titulo, autor, categoria`
- La clave natural de una fila es el par `(libro_id, socio)`, porque eso es lo que identifica de forma única "qué socio tiene prestado qué libro".

---

## Paso 1 — Primera Forma Normal (1FN)

**Problema:** la columna `socios` es multivaluada ("Ana, Luis" en una sola celda) → viola atomicidad.

**Acción:** cada valor de `socios` pasa a su propia fila.

| libro_id | titulo | autor | categoria | socio |
|---|---|---|---|---|
| 1 | Cien años | G. Márquez | Literatura | Ana |
| 1 | Cien años | G. Márquez | Literatura | Luis |
| 2 | Dune | F. Herbert | Ciencia ficción | Ana |
| 1 | Cien años | G. Márquez | Literatura | Pedro |

Ahora todas las celdas son atómicas. Clave primaria: `(libro_id, socio)`.

---

## Paso 2 — Segunda Forma Normal (2FN)

**Problema:** la clave es compuesta `(libro_id, socio)`, pero `titulo`, `autor` y `categoria` **dependen solo de `libro_id`**, no de `socio` → **dependencia parcial**.

**Acción:** separar los atributos que dependen de una parte de la clave en su propia tabla.

**LIBROS**

| libro_id (PK) | titulo | autor | categoria |
|---|---|---|---|
| 1 | Cien años | G. Márquez | Literatura |
| 2 | Dune | F. Herbert | Ciencia ficción |

**PRESTAMOS**

| libro_id (FK) | socio |
|---|---|
| 1 | Ana |
| 1 | Luis |
| 1 | Pedro |
| 2 | Ana |

PK compuesta: `(libro_id, socio)`.

---

## Paso 3 — Tercera Forma Normal (3FN)

**Revisión:** en `LIBROS`, ¿hay algún atributo no clave que dependa de *otro* atributo no clave (dependencia transitiva)? Con los datos dados, `titulo`, `autor` y `categoria` dependen directamente de `libro_id`, no unos de otros — estrictamente ya no hay dependencia transitiva demostrable.

Sin embargo, en la práctica esto **igual conviene separarlo más**, porque `autor` y `categoria` son entidades propias que se repiten como texto libre (redundancia), y si mañana querés agregarles atributos (nacionalidad del autor, descripción de la categoría) o corregir un nombre mal escrito, tenés que tocar múltiples filas. Por eso el diseño final habitual extrae catálogos con clave sustituta:

**AUTORES**

| autor_id (PK) | nombre |
|---|---|
| 1 | G. Márquez |
| 2 | F. Herbert |

**CATEGORIAS**

| categoria_id (PK) | nombre |
|---|---|
| 1 | Literatura |
| 2 | Ciencia ficción |

**SOCIOS**

| socio_id (PK) | nombre |
|---|---|
| 1 | Ana |
| 2 | Luis |
| 3 | Pedro |

**LIBROS** (ya en 3FN)

| libro_id (PK) | titulo | autor_id (FK) | categoria_id (FK) |
|---|---|---|---|
| 1 | Cien años | 1 | 1 |
| 2 | Dune | 2 | 2 |

**PRESTAMOS** (tabla asociativa N:M)

| libro_id (FK) | socio_id (FK) |
|---|---|
| 1 | 1 |
| 1 | 2 |
| 1 | 3 |
| 2 | 1 |

PK compuesta: `(libro_id, socio_id)`.

---

## 2) Esquema final

```
AUTORES(autor_id PK, nombre)
CATEGORIAS(categoria_id PK, nombre)
SOCIOS(socio_id PK, nombre)
LIBROS(libro_id PK, titulo, autor_id FK → AUTORES, categoria_id FK → CATEGORIAS)
PRESTAMOS(libro_id FK → LIBROS, socio_id FK → SOCIOS, PK(libro_id, socio_id))
```

---

## 3) Anomalías eliminadas

**Inserción**
En la tabla original no podías registrar un libro nuevo del catálogo sin que ya tuviera un socio asociado (el libro solo "existe" si aparece en una fila de préstamo). Con `LIBROS` separada, se puede dar de alta "Dune" o cualquier libro aunque nadie lo haya pedido todavía.

**Actualización**
Si el título de "Cien años" se corrige o cambia de categoría, en la tabla original había que actualizar **3 filas** (una por cada socio: Ana, Luis, Pedro). Si te olvidás de una, quedan datos inconsistentes (el mismo libro con dos categorías distintas). Con `LIBROS` separada, se actualiza **una sola fila**, y el cambio se refleja automáticamente para todos los préstamos vía la FK.

**Eliminación**
Si Pedro devuelve el libro 1 y esa era la única fila con `libro_id=1` en ese momento, borrar el préstamo hubiera borrado también toda la información del libro (título, autor, categoría) aunque el libro sigue físicamente en la biblioteca. Separando `LIBROS` de `PRESTAMOS`, eliminar un préstamo no afecta el catálogo.

**Redundancia**
El nombre del autor y de la categoría ya no se repite como texto en cada fila de préstamo, lo que reduce espacio y evita inconsistencias de tipeo (ej. "G. Márquez" vs "Gabriel Márquez" en distintas filas).
