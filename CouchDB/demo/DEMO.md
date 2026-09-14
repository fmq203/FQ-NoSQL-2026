# Demo en vivo — "OSE Móvil"

Tres nodos CouchDB en Docker simulan el servidor central y dos tablets de
campo, cada una con su propio inspector. Corresponde a las secciones
"Ejemplo ficticio" y "Replicación" de `presentacion-couchdb.html`.

- **Central**  → http://localhost:5984 (Fauxton: http://localhost:5984/_utils)
- **Tablet A**  → http://localhost:5985 (Fauxton: http://localhost:5985/_utils) — inspector jperez
- **Tablet B**  → http://localhost:5986 (Fauxton: http://localhost:5986/_utils) — inspector mgonzalez
- Usuario/clave de los tres: `admin` / `admin123`

Además de la API cruda hay tres **UI web** hechas a medida (HTML+JS plano,
sin build) para mostrar la historia sin depender de Fauxton ni de la
terminal:

- **UI Tablet A** → http://localhost:8082 (acento rojo) — formulario para
  cargar lecturas, switch "En línea / Sin conexión", botones de
  sincronización (subir y bajar cambios) y "editar valor" en cada lectura.
- **UI Tablet B** → http://localhost:8083 (acento azul) — igual que la
  anterior pero para el segundo inspector; arranca vacía a propósito.
- **UI Central** → http://localhost:8081 — panel de monitoreo: totales, m³
  por zona, buscador Mango, "editar valor" por lectura y, cuando aparece un
  conflicto, un link "resolver conflicto". Se actualiza sola cada 4
  segundos, así que conviene tenerla abierta en otra ventana/proyector
  mientras se operan las tablets.

En las tres UI, **pasar el mouse sobre cualquier botón de acción** muestra
un tooltip con el método HTTP y el endpoint real de CouchDB que ese click
dispara (por ejemplo `POST /_replicate` o `DELETE /inspecciones/{id}?rev=…`)
— útil para mostrar en clase qué llamada concreta hay detrás de cada
interacción, sin tener que leer el código fuente.

## Guion para presentar

1. **Levantar los nodos**
   ```
   docker compose up -d
   ```

2. **Cargar el escenario** (crea las bases, sube el design document con las
   vistas, crea el índice Mango, habilita CORS para las UI y carga 6
   lecturas *solo en la tablet A*, simulando que jperez trabajó offline
   todo el día. La tablet B queda vacía: es un segundo inspector que se
   suma después):
   ```
   ./setup.sh
   ```

3. **Levantar las tres UI**:
   ```
   ./serve-ui.sh
   ```
   Abrir http://localhost:8082 (tablet A), http://localhost:8083 (tablet B)
   y http://localhost:8081 (central) — idealmente tres ventanas visibles
   a la vez, o el central proyectado y las dos tablets en dos laptops/celus.

4. **Mostrar la asimetría** — la tablet A ya tiene 6 lecturas, la tablet B
   no tiene ninguna todavía y el central muestra 0. Cargar una lectura
   nueva a mano en la tablet A (queda igual, local) para reforzar que
   escribir nunca depende de la conexión.

5. **"Llega señal" en la tablet A** — activar su switch a "En línea" y
   apretar **Sincronizar con central**. El panel central se actualiza solo
   con los totales, el gráfico de barras por zona y la lista de documentos.

6. **Consulta Mango en vivo** — en la UI central, elegir una zona y un
   mínimo de m³ y apretar Buscar (es la misma consulta de la sección
   "Lenguaje de consulta" de la presentación, ahora con resultados reales).

## Escenario principal: conflicto entre dos inspectores (peer-to-peer real)

Esta es la versión más fiel al "multi-master replication" de la
presentación: el conflicto no lo genera el central, lo generan **dos
tablets que nunca se vieron entre sí**.

a. **La tablet B se suma al equipo**: activá su switch a "En línea" y
   apretá **"↓ Traer cambios del central"**. Ahora tablet B tiene la misma
   copia de las 6 lecturas que ya sincronizó la tablet A (incluidas las
   vistas y el índice Mango, que viajan como documentos de diseño).

b. **Las dos tablets se desconectan** (dejá los dos switches en "Sin
   conexión" — no importa si técnicamente el contenedor sigue arriba, lo
   que estamos simulando es que dejan de sincronizar entre sí).

c. **jperez (tablet A)** corrige el valor de una lectura, por ejemplo
   OSE-5102, con "editar valor".

d. **mgonzalez (tablet B)**, sin saber lo anterior, corrige *esa misma
   lectura* con un número distinto — las dos partieron de la misma
   revisión sincronizada en el paso (a), así que divergen limpiamente.

e. Activá "En línea" en la **tablet A** y apretá **Sincronizar con
   central** → esa versión llega primero y queda como la vigente.

f. Activá "En línea" en la **tablet B** y apretá **Sincronizar con
   central** → esta réplica trae la otra rama. Recién ahí, en el central,
   aparece el conflicto: dos inspectores, cada uno seguro de su lectura,
   ninguno pisó al otro.

g. En la UI central, "resolver conflicto" → elegir cuál vale (o cuál
   valor real habría que ir a remedir a campo, que es lo que pasa en la
   vida real con OSE). Al confirmar se guarda la elección y se borra la
   revisión perdedora (`DELETE .../{id}?rev={rev_perdedora}`) — ese
   borrado es lo que realmente cierra el conflicto.

h. Opcional: las dos tablets aprietan **"↓ Traer cambios del central"**
   de nuevo para que las tres copias vuelvan a quedar idénticas.

**Por qué conviene mostrar este escenario y no solo central-vs-tablet:**
acá ninguno de los dos nodos que generan el conflicto es "la autoridad" —
son dos pares (tablet A, tablet B) y el conflicto solo se materializa en
un tercer nodo que los sincroniza a ambos. Es la prueba en vivo de que
CouchDB no tiene jerarquía maestro/esclavo.

### Variante rápida (2 nodos, sin tablet B)

Si hay poco tiempo, se puede provocar el mismo tipo de conflicto editando
la misma lectura en la tablet A y en el central antes de sincronizar
(mismo mecanismo, un actor menos):

1. "editar valor" en la tablet A (queda local).
2. Sin sincronizar, "editar valor" en el central, mismo documento, otro
   número.
3. Sincronizar desde la tablet A → aparece el conflicto en el central.
4. "resolver conflicto" en el central.

Alternativa por terminal (mismo mecanismo, sin clickear, solo genera y
muestra el conflicto — no lo resuelve):
```
./conflict-demo-peers.sh
```

## Apagar todo al terminar

```
./stop-ui.sh
docker compose down -v
```

## Solo terminal (sin las UI web)

Si preferís mostrar todo por línea de comandos en vez de las páginas:
```
./replicate.sh      # dispara la replicación tablet A -> central
./view-query.sh      # vista MapReduce por_zona
./mango-query.sh     # consulta Mango de la presentación
```

## Si algo falla

- `docker compose ps` — confirmar que los tres contenedores están `healthy`/`Up`.
- Si un puerto está ocupado, cambiar `5984`/`5985`/`5986` en `docker-compose.yml`
  (y el puerto correspondiente en `ui/*/index.html`, constante `API`).
- Los scripts usan `python3 -m json.tool` solo para formatear la salida; si
  no está disponible, sacar ese tramo del pipe y listo (el JSON crudo de
  CouchDB también sirve para mostrar en pantalla).
