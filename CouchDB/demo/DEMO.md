# Demo en vivo — "OSE Móvil"

**Dos** servidores centrales y dos tablets de campo, cada una con su
inspector. Corresponde a las secciones "Ejemplo ficticio" y "Replicación"
de `presentacion-couchdb.html`.

Los dos centrales son **masters de verdad**: los dos aceptan escrituras y
se replican entre sí de forma continua. No hay un primario y una réplica de
solo lectura. Eso permite bajar cualquiera de los dos en vivo y mostrar que
no se pierde nada.

Lo interesante es que **las dos tablets no son iguales**:

| | Tablet A · jperez | Tablet B · mgonzalez |
|---|---|---|
| Qué corre | CouchDB completo en Docker | **PouchDB en el navegador** |
| Dónde guarda | volumen del contenedor | IndexedDB del navegador |
| Cómo sincroniza | botón → `POST /_replicate` | `db.sync(..., {live:true})`, sola |
| Qué muestra | todo lo que tenga su nodo | solo las lecturas de mgonzalez |
| Se puede manejar por terminal | sí | no, vive en el navegador |

La tablet B usa **replicación filtrada**: sube todo lo que genera, pero
solo baja lo suyo (`pull: {selector: {inspector: 'mgonzalez'}}`). Un
inspector no necesita la ruta de los demás en su dispositivo — el
consolidado de todos se ve en el panel central.

Para el central las dos son lo mismo: habla el mismo protocolo de
replicación con ambas y no las distingue. Esa es justamente la gracia.

## Direcciones

- **Central A** → http://localhost:5984 (Fauxton: http://localhost:5984/_utils)
- **Central B** → http://localhost:5987 (Fauxton: http://localhost:5987/_utils)
- **Tablet A** → http://localhost:5985 (Fauxton: http://localhost:5985/_utils)
- Usuario/clave de todos los nodos: `admin` / `admin123`

Las cuatro interfaces web (HTML plano, sin build):

- **Monitor** → http://localhost:8084 — estado de todos los nodos, si los
  masters convergieron, el estado de la replicación continua, y **botones
  para encender, apagar y bajar nodos** sin ir a la terminal.
- **UI Central** → http://localhost:8081 — totales, m³ por zona, buscador
  Mango, "editar valor" y "resolver conflicto". Se actualiza sola cada 4 s.
  Arriba se elige **contra qué master operar**: si uno se cae, se sigue
  trabajando con el otro sin tocar nada más.
- **UI Tablet A** → http://localhost:8082 (acento rojo) — switch de conexión
  y botones de sincronización manual.
- **UI Tablet B** → http://localhost:8083 (acento azul) — la app PouchDB.
  No tiene botón de sincronizar: el switch prende una replicación continua.

En las tres, **pasar el mouse sobre los botones** muestra la llamada real que
dispara cada click (`POST /_replicate`, `db.put()`, `DELETE ...?rev=`).

## El conflicto ya viene armado

- **Tablet A** arranca con la ruta de jperez: 6 lecturas, cargadas por
  `setup.sh` directo en su nodo CouchDB.
- **Tablet B** se siembra sola la primera vez que abrís su página: 4 lecturas
  de mgonzalez, de las cuales **2 comparten `_id`** con lecturas de jperez
  (medidores OSE-3390 y OSE-4488) pero con otro valor.

Ninguna de las dos vio a la otra: cada una arrancó su propio historial de
revisiones para esos documentos. Apenas las dos repliquen al central, esos
dos documentos quedan en conflicto, sin que haya que editar nada a mano.

## Guion para presentar

1. **Levantar los nodos**
   ```
   docker compose up -d
   ```

2. **Cargar el escenario** (bases, vistas, índice Mango, CORS y la ruta de
   jperez en la tablet A):
   ```
   ./setup.sh
   ```

3. **Levantar las tres UI**:
   ```
   ./serve-ui.sh
   ```
   Abrir las tres en ventanas visibles a la vez, o el central proyectado y
   las tablets en otros dispositivos.

4. **Mostrar la asimetría** — las dos tablets tienen datos propios, el
   central muestra 0. Cargar una lectura a mano en cualquiera de las dos:
   se guarda igual, sin conexión. En la tablet B eso es un `db.put()`
   contra IndexedDB, sin red de por medio.

5. **Tablet A sincroniza** — switch a "En línea" y botón **Sincronizar con
   central**. El panel central se puebla solo. Todavía no hay conflictos.

6. **Tablet B se conecta** — acá no hay botón que apretar: al poner el
   switch en "EN LÍNEA" arranca `db.sync(remoto, {live:true, retry:true})`
   y replica sola. El panel de estado abajo muestra "sincronizando…" y
   después "al día". En el central, el contador de conflictos pasa a **2**.

7. **Resolver en la UI central** — "resolver conflicto" en cada uno de los
   dos documentos. Se ven los dos valores enfrentados con su revisión, y al
   elegir uno se guarda la decisión y se borra la revisión perdedora
   (`DELETE .../{id}?rev=…`), que es lo que realmente cierra el conflicto.

8. **Consulta Mango** — zona + mínimo de m³ en el panel central.

9. Como la tablet B quedó en sincronización continua, la resolución le baja
   sola: sin tocar nada, su pantalla se actualiza con el valor resuelto.

## Reiniciar entre ensayos

Los dos nodos CouchDB se limpian con `docker compose down -v`, **pero eso no
toca a la tablet B**: sus datos viven en el IndexedDB del navegador. Para
dejarla como al principio usá el link **"reiniciar datos locales"** abajo de
todo en http://localhost:8083 (hace `db.destroy()` y vuelve a sembrar).

Reset completo, en el orden correcto:
```
./reset.sh
```
y después, el paso que el script no puede hacer por vos: abrir
http://localhost:8083 y apretar **"reiniciar datos locales"**.

> **Por qué importa.** Si reseteás los contenedores pero dejás la pestaña de
> la tablet B con datos viejos, PouchDB no sabe que el central se borró:
> vuelve a subir sus revisiones y el central termina con revisiones raíz
> duplicadas, o sea conflictos que no son parte del guion. Pasa de verdad,
> no es teórico.

## MapReduce y Mango: qué mostrar de cada uno

El panel central tiene tres cosas pensadas para esta parte.

**Drill-down con una sola vista.** El panel de consumo tiene tres botones
(*por zona* / *+ año* / *+ mes*). No son tres vistas: es **una sola**, que
emite la clave compuesta `[zona, año, mes]`, y el nivel de agregación lo
elige el parámetro `group_level` de la consulta. Abajo del gráfico se ve la
URL exacta que se está llamando. Esto es lo más idiomático de CouchDB y es
justo lo que Mango **no** puede hacer.

**El plan de la consulta Mango.** Después de buscar, aparece qué índice
eligió el planificador y qué rango del B-tree recorrió, por ejemplo:

```
índice: idx-tipo-zona-valor (json)
rango recorrido: ["lectura_medidor","Florida-Norte","<MAX>"] → ["lectura_medidor","Florida-Norte",0]
```

El botón *"¿y si filtro por un campo sin índice?"* corre un `_explain` de
`{"selector": {"inspector": "jperez"}}` y muestra que cae en `_all_docs`,
o sea que recorre la base entera para filtrar. Ese contraste es la forma de
mostrar el costo real en vez de afirmarlo.

**El límite de Mango.** Mango no tiene agregación: mandarle un `group_by`
devuelve `invalid_key`. Así que "cuántos m³ por zona" no se puede resolver
con Mango, sí o sí es una vista. Esa es la respuesta corta a cuándo usar
cada uno: Mango para buscar documentos, vistas para contar y sumar.

## Validación en el servidor

El design document trae una función `validate_doc_update` que corre en
CouchDB en **cada escritura**, venga de donde venga. Rechaza:

- lecturas sin `medidor_id`
- `valor_m3` que no sea número, o negativo
- una corrección que haga **retroceder** el medidor (físicamente imposible)

Se prueba desde la terminal:
```
curl -X POST http://admin:admin123@localhost:5985/inspecciones   -H "Content-Type: application/json"   -d '{"type":"lectura_medidor","medidor_id":"OSE-4471","zona":"X","valor_m3":-5}'
# {"error":"forbidden","reason":"un medidor no puede marcar negativo: -5"}
```

Un detalle que vale la pena contar: esta validación **no** frena la rama en
conflicto que llega por replicación, aunque tenga un valor menor. Al
replicar una revisión raíz no hay `oldDoc`, así que la regla de "no
retrocede" no se aplica. Son dos mecanismos para dos cosas distintas:
`validate_doc_update` valida escrituras, la resolución de conflictos
arregla divergencias.

## Join sin JOIN

CouchDB no tiene joins. El panel central tiene una tabla *"Lecturas
cruzadas con el padrón"* que muestra el truco equivalente: la vista
`con_padron` emite como valor un `{_id: 'medidor:…'}`, y al consultarla con
`include_docs=true` el servidor adjunta ese otro documento en la misma
consulta. Una sola vuelta al servidor, dos tipos de documento.

## Encender y apagar desde el monitor

El monitor no es una página estática: la sirve `control-server.py`, que
además ejecuta las acciones de Docker que disparan los botones.

- **Encender todo** — `docker compose up -d` + `setup.sh`. Es lo primero que
  conviene apretar si venís de otro día: los contenedores no arrancan solos
  cuando se reinicia la máquina o WSL se suspende.
- **Apagar todo** — los detiene sin borrar nada.
- **Reset total** — borra los volúmenes y recarga el escenario. Pide
  confirmación. No toca la tablet B (IndexedDB del navegador).
- **bajar este nodo / levantar** — en cada tarjeta, para el escenario de
  caída sin salir de la pantalla.

Abajo del panel queda la salida de los comandos, así se ve qué corrió.

Sobre la seguridad: el servidor escucha solo en `127.0.0.1` y únicamente
ejecuta comandos de una lista fija. El navegador manda una clave como
`down:central-a`, nunca un comando; no se arma ningún string con texto de
afuera ni se usa `shell=True`.

Si preferís la terminal, los scripts siguen estando: `./node-down.sh`,
`./node-up.sh`, `./reset.sh`.

## Bajar un master en vivo

Este es el escenario que muestra que tener dos masters sirve para algo.
Conviene tener abierto el monitor (http://localhost:8084) proyectado.

1. **Estado de partida**: el monitor dice *"Los dos masters tienen
   exactamente lo mismo"*. La huella que compara no es el conteo: es el
   `_id` + revisión de cada documento, ordenado.

2. **Bajar uno**:
   ```
   ./node-down.sh central-a
   ```
   El monitor lo marca caído y pasa a *"Operando con un solo master"*.

3. **Seguir trabajando igual**. En la UI central, cambiar el selector de
   arriba a **Central B** y editar el valor de una lectura, o resolver un
   conflicto. El sistema sigue aceptando escrituras con un master menos.

4. **Levantarlo**:
   ```
   ./node-up.sh central-a
   ```
   El monitor pasa unos segundos por *"Replicando… todavía no convergen"*
   (se ve la diferencia de lecturas entre uno y otro) y después vuelve a
   *"exactamente lo mismo"*. Lo que se escribió mientras A no estaba,
   aparece solo en A.

Lo importante para contar: **nadie volvió a disparar la replicación a
mano**. Está definida en la base `_replicator`, que es persistente, así que
CouchDB la retoma sola cuando el nodo vuelve. En la prueba tardó unos 10
segundos en converger.

## Solo terminal

La tablet B no se puede manejar por terminal (corre en el navegador). Para
el resto:
```
./replicate.sh             # replicación tablet A -> central
./view-query.sh            # vista MapReduce por_zona
./mango-query.sh           # consulta Mango
./conflict-demo-peers.sh   # sincroniza A y reporta el estado de conflictos
./conflict-demo.sh         # conflicto central vs tablet A, editando a mano
./node-down.sh central-a   # baja un master
./node-up.sh central-a     # lo vuelve a levantar
```

Lo mismo se puede hacer con los botones del monitor (http://localhost:8084).

## Si algo falla

- `docker compose ps` — los tres contenedores en `Up`.
- **La tablet B no carga**: tiene que existir `ui/tablet-b/pouchdb.min.js`
  (va versionado en el repo, no se baja de internet). Si falta, la página
  lo avisa en rojo.
- **La tablet B no sincroniza**: revisá que el central tenga CORS activo
  (lo hace `setup.sh`) y que la consola del navegador no muestre errores de
  origen. PouchDB habla directo desde el navegador al puerto 5984.
- **Datos viejos en la tablet B** tras un `down -v`: es esperable, borralos
  con "reiniciar datos locales".
- Si un puerto está ocupado, cambiá `5984`/`5985`/`5987` en `docker-compose.yml`
  y las constantes `API` / `MASTERS` / `REMOTA_URL` en `ui/*/index.html`.
- **Los masters no convergen**: mirá el panel de replicación del monitor. Si
  una réplica figura `crashing`, casi siempre es CORS o credenciales.
