# Demo en vivo — "OSE Móvil"

Un servidor central y dos tablets de campo, cada una con su inspector.
Corresponde a las secciones "Ejemplo ficticio" y "Replicación" de
`presentacion-couchdb.html`.

Lo interesante es que **las dos tablets no son iguales**:

| | Tablet A · jperez | Tablet B · mgonzalez |
|---|---|---|
| Qué corre | CouchDB completo en Docker | **PouchDB en el navegador** |
| Dónde guarda | volumen del contenedor | IndexedDB del navegador |
| Cómo sincroniza | botón → `POST /_replicate` | `db.sync(..., {live:true})`, sola |
| Se puede manejar por terminal | sí | no, vive en el navegador |

Para el central las dos son lo mismo: habla el mismo protocolo de
replicación con ambas y no las distingue. Esa es justamente la gracia.

## Direcciones

- **Central** → http://localhost:5984 (Fauxton: http://localhost:5984/_utils)
- **Tablet A** → http://localhost:5985 (Fauxton: http://localhost:5985/_utils)
- Usuario/clave de los dos nodos: `admin` / `admin123`

Las tres interfaces web (HTML plano, sin build):

- **UI Central** → http://localhost:8081 — totales, m³ por zona, buscador
  Mango, "editar valor" y "resolver conflicto". Se actualiza sola cada 4 s.
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

Reset completo:
```
./stop-ui.sh
docker compose down -v
docker compose up -d && ./setup.sh && ./serve-ui.sh
# y en http://localhost:8083 → "reiniciar datos locales"
```

## Solo terminal

La tablet B no se puede manejar por terminal (corre en el navegador). Para
el resto:
```
./replicate.sh             # replicación tablet A -> central
./view-query.sh            # vista MapReduce por_zona
./mango-query.sh           # consulta Mango
./conflict-demo-peers.sh   # sincroniza A y reporta el estado de conflictos
./conflict-demo.sh         # conflicto central vs tablet A, editando a mano
```

## Si algo falla

- `docker compose ps` — los dos contenedores en `Up`.
- **La tablet B no carga**: tiene que existir `ui/tablet-b/pouchdb.min.js`
  (va versionado en el repo, no se baja de internet). Si falta, la página
  lo avisa en rojo.
- **La tablet B no sincroniza**: revisá que el central tenga CORS activo
  (lo hace `setup.sh`) y que la consola del navegador no muestre errores de
  origen. PouchDB habla directo desde el navegador al puerto 5984.
- **Datos viejos en la tablet B** tras un `down -v`: es esperable, borralos
  con "reiniciar datos locales".
- Si un puerto está ocupado, cambiá `5984`/`5985` en `docker-compose.yml` y
  la constante `API` / `REMOTA` en `ui/*/index.html`.
