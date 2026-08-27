# Actividad 5 — Redis: base clave-valor y patrón de caché

## 1. Contenedor levantado

```
docker run -d --name redis-clase \
  -p 6379:6379 \
  redis:7
```

```
$ docker exec redis-clase redis-cli ping
PONG
```

✅ Contenedor Redis levantado.

## 2. Strings y contadores

```
127.0.0.1:6379> SET mensaje "hola nosql"
OK
127.0.0.1:6379> GET mensaje
"hola nosql"
127.0.0.1:6379> SET visitas 0
OK
127.0.0.1:6379> INCR visitas
(integer) 1
127.0.0.1:6379> INCR visitas
(integer) 2
127.0.0.1:6379> INCRBY visitas 5
(integer) 7
127.0.0.1:6379> GET visitas
"7"
```

✅ El contador del paso 2 llegó a 7.

## 3. Hashes (objetos)

```
127.0.0.1:6379> HSET usuario:1 nombre "Ana" ciudad "Montevideo" edad 30
(integer) 3
127.0.0.1:6379> HGET usuario:1 nombre
"Ana"
127.0.0.1:6379> HGETALL usuario:1
1) "nombre"
2) "Ana"
3) "ciudad"
4) "Montevideo"
5) "edad"
6) "30"
127.0.0.1:6379> HINCRBY usuario:1 edad 1
(integer) 31
```

✅ El hash `usuario:1` muestra todos sus campos con `HGETALL`.

## 4. Listas (colas)

```
127.0.0.1:6379> LPUSH cola:tareas "procesar-venta-1"
(integer) 1
127.0.0.1:6379> LPUSH cola:tareas "procesar-venta-2"
(integer) 2
127.0.0.1:6379> LRANGE cola:tareas 0 -1
1) "procesar-venta-2"
2) "procesar-venta-1"
127.0.0.1:6379> RPOP cola:tareas
"procesar-venta-1"
127.0.0.1:6379> LPUSH cola:tareas "procesar-venta-3"
(integer) 2
127.0.0.1:6379> LLEN cola:tareas
(integer) 2
```

`LPUSH` inserta al frente de la lista, por eso `LRANGE` muestra el último insertado
primero. `RPOP` saca del final (el más viejo, FIFO tipo cola).

## 5. Sets (membresía)

```
127.0.0.1:6379> SADD online "ana"
(integer) 1
127.0.0.1:6379> SADD online "bruno"
(integer) 1
127.0.0.1:6379> SADD online "ana"
(integer) 0
127.0.0.1:6379> SMEMBERS online
1) "ana"
2) "bruno"
127.0.0.1:6379> SISMEMBER online "carla"
(integer) 0
```

✅ `SADD online "ana"` la segunda vez devolvió `0` (no agregó duplicado). `carla` no
es miembro del set.

## 6. Sorted Sets (rankings)

```
127.0.0.1:6379> ZADD ranking 100 "ana"
(integer) 1
127.0.0.1:6379> ZADD ranking 250 "bruno"
(integer) 1
127.0.0.1:6379> ZADD ranking 180 "carla"
(integer) 1
127.0.0.1:6379> ZRANGE ranking 0 -1 WITHSCORES
1) "ana"
2) "100"
3) "carla"
4) "180"
5) "bruno"
6) "250"
127.0.0.1:6379> ZREVRANGE ranking 0 2
1) "bruno"
2) "carla"
3) "ana"
```

✅ `ZREVRANGE` ordena el ranking correctamente: bruno (250) > carla (180) > ana (100).

## 7. Expiración (TTL)

```
127.0.0.1:6379> SET token:sesion "abc123"
OK
127.0.0.1:6379> EXPIRE token:sesion 10
(integer) 1
127.0.0.1:6379> TTL token:sesion
(integer) 10
127.0.0.1:6379> GET token:sesion
"abc123"
127.0.0.1:6379> SET promocion "20% off" EX 15
OK
127.0.0.1:6379> TTL promocion
(integer) 15
```

Después de esperar más de 10 segundos:

```
127.0.0.1:6379> GET token:sesion
(nil)
127.0.0.1:6379> TTL token:sesion
(integer) -2
```

✅ Una clave con `EXPIRE 10` desaparece después de 10 segundos: `GET` devuelve `(nil)`
y `TTL` devuelve `-2` (la clave no existe). Redis la borró sola al vencer.

## 8. Patrón cache-aside

```
127.0.0.1:6379> GET cache:perfil:1
(nil)                              # miss de caché

127.0.0.1:6379> SET cache:perfil:1 "{\"nombre\":\"Ana\",\"ciudad\":\"Montevideo\"}" EX 30
OK

127.0.0.1:6379> GET cache:perfil:1
"{\"nombre\":\"Ana\",\"ciudad\":\"Montevideo\"}"   # hit de caché

127.0.0.1:6379> TTL cache:perfil:1
(integer) 30
```

✅ El patrón cache-aside muestra primero `(nil)` y después el valor guardado (hit),
con TTL vigente para forzar el refresco en 30 segundos.

## 9. Estado de la base

```
127.0.0.1:6379> DBSIZE
(integer) 8
127.0.0.1:6379> KEYS *
1) "promocion"
2) "cola:tareas"
3) "visitas"
4) "mensaje"
5) "ranking"
6) "online"
7) "cache:perfil:1"
8) "usuario:1"
```

(`token:sesion` ya no aparece porque venció; no se ejecutó `FLUSHALL` para conservar
el estado y poder seguir explorando desde `redis-cli`.)

## 10. Preguntas a la IA

**¿Cuál es la diferencia entre Redis y Memcached? ¿Cuándo conviene cada uno?**

Memcached es un caché puro en memoria: solo maneja pares clave-valor de tipo string
(o blobs), es multihilo y no ofrece persistencia ni estructuras de datos adicionales.
Redis, en cambio, además de ser un almacén clave-valor en memoria, soporta tipos de
datos ricos (hashes, listas, sets, sorted sets, streams), persistencia opcional a
disco (RDB/AOF), replicación, pub/sub y scripting. Memcached conviene cuando lo único
que se necesita es un caché simple y masivamente paralelo de objetos pequeños (por
ejemplo, fragmentos de HTML o resultados de consultas) y no importa perder los datos
al reiniciar. Redis conviene cuando además del caché se necesitan estructuras más
expresivas (colas, rankings, contadores, sets de membresía), algo de persistencia, o
funcionalidades como pub/sub — que es exactamente el caso de esta actividad (cola de
tareas, ranking, patrón cache-aside).

**¿Qué pasa con la consistencia si la app escribe primero en MongoDB y después en
Redis, o al revés?**

Ninguno de los dos órdenes es perfecto porque no hay una transacción atómica entre
las dos bases; siempre queda una ventana de inconsistencia posible:

- *Escribir primero en MongoDB y después en Redis* (lo más común, "write-through"):
  si el proceso falla justo después de escribir en Mongo pero antes de actualizar
  Redis, la caché queda con el valor viejo hasta que expire el TTL. Es el enfoque
  más seguro porque la fuente de verdad (MongoDB) siempre queda actualizada primero;
  el peor caso es servir un dato desactualizado por un rato corto.
- *Escribir primero en Redis y después en MongoDB*: si falla la escritura a Mongo
  después de haber actualizado Redis, la caché muestra un dato que la base principal
  nunca llegó a tener — un problema más grave, porque la "fuente de verdad" aparente
  para los lectores queda divergida del dato real persistido.

Por eso la práctica más segura suele ser: escribir/confirmar en la base principal
primero y, en vez de actualizar Redis proactivamente, simplemente invalidar
(`DEL`) la clave de caché para que el próximo `GET` sea un miss y dispare una
relectura fresca desde MongoDB (patrón cache-aside puro). El TTL actúa como red de
seguridad adicional para que ninguna inconsistencia dure para siempre.

**Ejemplo real de cómo Node.js usaría Redis como caché con TTL**

```js
// Node.js con ioredis + MongoDB (driver oficial), patrón cache-aside
const Redis = require("ioredis");
const redis = new Redis(); // localhost:6379

async function obtenerPerfil(id) {
  const clave = `cache:perfil:${id}`;

  // 1) Preguntar primero a Redis
  const enCache = await redis.get(clave);
  if (enCache) {
    return JSON.parse(enCache); // hit
  }

  // 2) Miss: leer de MongoDB
  const perfil = await db.collection("perfiles").findOne({ _id: id });
  if (!perfil) return null;

  // 3) Guardar en Redis con TTL (30s) antes de devolver
  await redis.set(clave, JSON.stringify(perfil), "EX", 30);

  return perfil;
}
```

Esto es exactamente el patrón implementado en la sección 8, ahora llevado a código:
Redis primero, MongoDB solo en el miss, y TTL para que la caché se refresque sola.

## Verificación de resultados

- [x] El contador del paso 2 llegó a 7.
- [x] El hash `usuario:1` muestra todos sus campos con `HGETALL`.
- [x] Una clave con `EXPIRE 10` desaparece después de 10 segundos.
- [x] El patrón cache-aside muestra primero `(nil)` y después el valor guardado.
- [x] `ZREVRANGE` ordena el ranking correctamente.

## Nota de seguridad

Este Redis se levantó **sin contraseña** y con el puerto 6379 publicado en el host:
cualquiera con acceso a ese puerto podría ejecutar `FLUSHALL` y borrar todo, o leer
cualquier clave. Queda pendiente para la Actividad 6 protegerlo con `requirepass`,
ACLs y renombramiento de comandos peligrosos.
