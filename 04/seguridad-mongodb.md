# Actividad 4 — Seguridad en MongoDB: autenticación, roles y NoSQL injection

## 1. Contenedor levantado con `--auth`

```
docker rm -f mongo-clase
docker run -d --name mongo-clase \
  -p 27017:27017 \
  -v mongo-clase-data:/data/db \
  mongo:7 --auth
```

Verificación de que sin credenciales no se puede operar:

```
$ mongosh "mongodb://localhost:27017/admin" --eval 'db.getUsers()'
ERROR ESPERADO (sin auth): Command usersInfo requires authentication
```

✅ Con `--auth`, una conexión sin credenciales no puede hacer nada.

## 2. Usuarios creados

### Usuario administrador (`admin`, rol `root` sobre `admin`)

```js
db = db.getSiblingDB("admin");
db.createUser({
 user: "admin",
 pwd: "Admin-Muy-Secreto-2026",
 roles: [ { role: "root", db: "admin" } ]
});
```
Resultado: `{ ok: 1 }`

Verificación de login:

```
$ mongosh "mongodb://admin:Admin-Muy-Secreto-2026@localhost:27017/admin" --eval 'db.getUsers()'
{
  users: [
    {
      _id: 'admin.admin',
      user: 'admin',
      db: 'admin',
      roles: [ { role: 'root', db: 'admin' } ],
      mechanisms: [ 'SCRAM-SHA-1', 'SCRAM-SHA-256' ]
    }
  ],
  ok: 1
}
```

### Usuarios de aplicación (base `app_ventas`, mínimo privilegio)

| Usuario | Rol | DB |
|---|---|---|
| `lector` | `read` | `app_ventas` |
| `app_ventas_user` | `readWrite` | `app_ventas` |

```js
var appdb = db.getSiblingDB("app_ventas");

appdb.createUser({
 user: "lector",
 pwd: "Lector123",
 roles: [ { role: "read", db: "app_ventas" } ]
});
// { ok: 1 }

appdb.createUser({
 user: "app_ventas_user",
 pwd: "AppVentas-Secreto",
 roles: [ { role: "readWrite", db: "app_ventas" } ]
});
// { ok: 1 }
```

`db.getUsers()` sobre `app_ventas`:

```
{
  users: [
    {
      _id: 'app_ventas.app_ventas_user',
      user: 'app_ventas_user',
      db: 'app_ventas',
      roles: [ { role: 'readWrite', db: 'app_ventas' } ]
    },
    {
      _id: 'app_ventas.lector',
      user: 'lector',
      db: 'app_ventas',
      roles: [ { role: 'read', db: 'app_ventas' } ]
    }
  ],
  ok: 1
}
```

## 3. Prueba de RBAC

### `app_ventas_user` (readWrite) — puede leer y escribir

```
$ mongosh "mongodb://app_ventas_user:AppVentas-Secreto@localhost:27017/app_ventas"
> db.productos.insertOne({ nombre: "Laptop", precio: 900 })
> db.productos.find()
[
  { _id: ObjectId('6a9019090a8e10a04cc49c1e'), nombre: 'Laptop', precio: 900 }
]
```
✅ El usuario `app_ventas_user` puede leer y escribir.

### `lector` (read) — NO puede escribir

```
$ mongosh "mongodb://lector:Lector123@localhost:27017/app_ventas"
> db.productos.insertOne({ nombre: "Hack", precio: 1 })

ERROR ESPERADO: not authorized on app_ventas to execute command
{ insert: "productos", documents: [ { nombre: "Hack", precio: 1, ... } ], ... }
```
✅ El usuario `lector` no puede insertar (error `not authorized`).

## 4. Simulación de NoSQL injection

Colección de ejemplo:

```js
db.usuarios.insertMany([
 { usuario: "ana", clave: "s3creto", admin: false },
 { usuario: "bruno", clave: "otra", admin: true }
]);
```

Código vulnerable imaginado (nunca hacer esto):

```js
// const filtro = { usuario: user, clave: pass };
// db.usuarios.findOne(filtro)
```

Si un atacante manda `user = { "$ne": null }` y `pass = { "$ne": null }` como cuerpo del login,
el filtro que arma la app queda:

```js
db.usuarios.findOne({ usuario: { $ne: null }, clave: { $ne: null } })
```

Resultado real obtenido:

```
{
  _id: ObjectId('6a901913de33bd71b78d54ec'),
  usuario: 'ana',
  clave: 's3creto',
  admin: false
}
```

✅ La simulación de inyección devuelve un usuario sin conocer la clave. El atacante obtuvo el
primer documento de la colección (usuario y contraseña incluidos) sin saber ninguna credencial
válida.

Equivalente en SQL clásico:

```sql
-- SELECT * FROM usuarios WHERE usuario = '' OR '1'='1' AND clave = ''
-- El '1'='1' hace que el WHERE sea siempre verdadero
```

## 5. Validador de esquema (prevención)

```js
db.runCommand({
 collMod: "usuarios",
 validator: {
   $jsonSchema: {
     bsonType: "object",
     required: ["usuario", "clave"],
     properties: {
       usuario: { bsonType: "string" },
       clave: { bsonType: "string" }
     }
   }
 }
});
// { ok: 1 }
```

Prueba de que ahora rechaza el mismo payload de inyección (objeto en vez de string):

```
$ mongosh "mongodb://app_ventas_user:AppVentas-Secreto@localhost:27017/app_ventas"
> db.usuarios.insertOne({ usuario: { $ne: null }, clave: "x" })

RECHAZADO COMO SE ESPERABA: Document failed validation
```

✅ El validador de esquema rechaza documentos con operadores en lugar de strings.

## 6. Checklist de verificación

- [x] Con `--auth`, una conexión sin credenciales no puede hacer nada.
- [x] El usuario `lector` no puede insertar (error `not authorized`).
- [x] El usuario `app_ventas_user` puede leer y escribir.
- [x] La simulación de inyección devuelve un usuario sin conocer la clave.
- [x] El validador de esquema rechaza documentos con operadores.

## 7. Preguntas a la IA (Paso 10)

**¿Qué es el principio de mínimo privilegio y cómo se aplica con los roles de MongoDB?**

Consiste en darle a cada identidad (usuario humano o aplicación) únicamente los permisos
estrictamente necesarios para su función, ni uno más. En MongoDB se aplica eligiendo el rol más
acotado posible por base de datos: un usuario de solo consultas usa `read`, la aplicación que
necesita leer y escribir usa `readWrite` (nunca `root`), y los roles administrativos
(`userAdminAnyDatabase`, `root`) quedan reservados para tareas puntuales de administración, no
para el día a día de una app. Así, si se filtran las credenciales de la aplicación, el daño queda
acotado a lo que ese rol permite (por ejemplo, no podría crear usuarios ni tocar otras bases).

**¿Cuál es la diferencia entre cifrado en tránsito y cifrado en reposo?**

El cifrado en tránsito (TLS/SSL) protege los datos mientras viajan por la red entre el cliente y
el servidor, evitando que alguien que intercepte el tráfico (por ejemplo, en la misma red) pueda
leer usuarios, contraseñas o documentos. El cifrado en reposo protege los datos cuando están
guardados en el disco, evitando que alguien con acceso físico a los archivos (un backup robado, un
disco mal desechado, un servidor comprometido) pueda leerlos directamente sin pasar por el motor de
la base. Son complementarios: uno cubre el dato "en el camino" y el otro "parado".

**Mostrame un ejemplo de cómo una API debería validar un login sin exponerse a NoSQL injection.**

```js
// Node.js / Express — validación explícita de tipos antes de armar el filtro
app.post("/login", async (req, res) => {
  const { usuario, clave } = req.body;

  // 1) Rechazar cualquier cosa que no sea string (objetos como { $ne: null } quedan afuera)
  if (typeof usuario !== "string" || typeof clave !== "string") {
    return res.status(400).json({ error: "Credenciales inválidas" });
  }

  // 2) Comparar por igualdad exacta, nunca insertar el valor crudo del usuario como operador
  const user = await db.collection("usuarios").findOne({ usuario, clave });

  if (!user) {
    return res.status(401).json({ error: "Usuario o contraseña incorrectos" });
  }

  return res.json({ ok: true });
});
```

Esto se refuerza con el validador `$jsonSchema` de la sección 5, que actúa como segunda capa por
si la validación de la aplicación falla o se olvida en algún endpoint.

## 8. Reflexión

Una API nunca debe armar filtros de consulta concatenando o insertando directamente el texto
que envía el usuario, porque en MongoDB (igual que en SQL) esa entrada deja de ser un simple
dato y pasa a poder actuar como parte del propio lenguaje de consulta. Si el backend arma
`{ usuario: req.body.user, clave: req.body.pass }` sin validar tipos, un atacante puede mandar
objetos con operadores (`$ne`, `$gt`, `$where`) en vez de strings, y el motor los interpreta como
condiciones lógicas legítimas en lugar de como valores a comparar. El resultado, como se vio en
esta actividad, es que un `findOne` pensado para "buscar exactamente este usuario con esta
contraseña" termina devolviendo el primer documento de la colección sin que el atacante conozca
ninguna credencial real. La defensa correcta es doble: validar explícitamente el tipo de cada
campo de entrada (rechazar cualquier cosa que no sea el string esperado) y reforzarlo con
validadores de esquema (`$jsonSchema`) a nivel de base de datos, para que incluso si una capa de
validación falla en la aplicación, la base rechace igualmente documentos u operaciones con formas
inesperadas.
