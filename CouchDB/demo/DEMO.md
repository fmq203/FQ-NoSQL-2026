# Demo en vivo — "OSE Móvil"

Tres nodos CouchDB en Docker simulan el servidor central y dos tablets de
campo, cada una con su propio inspector. Corresponde a las secciones
"Ejemplo ficticio" y "Replicación" de `presentacion-couchdb.html`.

- **Central**  → http://localhost:5984 (Fauxton: http://localhost:5984/_utils)
- **Tablet A**  → http://localhost:5985 (Fauxton: http://localhost:5985/_utils) — inspector jperez
- **Tablet B**  → http://localhost:5986 (Fauxton: http://localhost:5986/_utils) — inspectora mgonzalez
- Usuario/clave de los tres: `admin` / `admin123`

Además de la API cruda hay tres **UI web** hechas a medida (HTML+JS plano,
sin build) para mostrar la historia sin depender de Fauxton ni de la
terminal:

- **UI Tablet A** → http://localhost:8082 (acento rojo) — formulario para
  cargar lecturas, switch "En línea / Sin conexión", botones de
  sincronización (subir y bajar cambios) y "editar valor" en cada lectura.
- **UI Tablet B** → http://localhost:8083 (acento azul) — igual que la
  anterior, para la segunda inspectora.
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

## El escenario ya viene con un conflicto listo para mostrar

`setup.sh` carga las dos tablets **sin que se hayan visto entre sí**:

- **Tablet A (jperez)**: su ruta completa, 6 lecturas.
- **Tablet B (mgonzalez)**: su propia ruta — 2 lecturas nuevas, más **2 que
  coinciden con medidores que jperez ya midió** (OSE-3390 y OSE-4488), con
  valores distintos. Ninguna de las dos tablets sabe de la otra: cada una
  arrancó su propio historial de revisiones para esos documentos.

No hace falta editar nada a mano para generar el conflicto: apenas las dos
tablets sincronizan con el central (en cualquier orden), esos dos
documentos aparecen automáticamente como conflicto, listos para resolver
en la UI central. Es el ejemplo más fiel al "multi-master replication" de
la presentación: el conflicto no lo genera el central, lo generan **dos
pares que nunca se vieron**, y solo se hace visible en el nodo que
finalmente sincroniza con los dos.

## Guion para presentar

1. **Levantar los nodos**
   ```
   docker compose up -d
   ```

2. **Cargar el escenario** (crea las bases, sube el design document con las
   vistas, crea el índice Mango, habilita CORS para las UI, y carga las
   lecturas de las dos tablets como se explica arriba):
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

4. **Mostrar la asimetría** — las dos tablets ya tienen datos propios, el
   central muestra 0. Opcional: cargar una lectura nueva a mano en
   cualquiera de las dos (queda igual, local) para reforzar que escribir
   nunca depende de la conexión.

5. **Tablet A sincroniza primero** — activar su switch a "En línea" y
   apretar **Sincronizar con central**. El panel central se actualiza solo
   con los totales, el gráfico de barras por zona y la lista de documentos.
   Todavía no hay conflictos: el central solo vio una rama.

6. **Tablet B sincroniza después** — mismo switch, mismo botón. Apenas
   termina, en el central el contador "conflictos" pasa a **2** y esos dos
   documentos muestran el badge rojo "⚠ conflicto". Nada se pisó ni se
   perdió: las dos versiones de cada lectura existen.

7. **Resolver en la UI central** — abrir "resolver conflicto" en cada uno
   de los dos documentos. Se abre un panel con los dos valores enfrentados
   (el de jperez y el de mgonzalez) y un botón para cada uno. Elegir
   cualquiera: CouchDB nunca decide por vos, la aplicación es la que
   corrige la inconsistencia (en la vida real, acá OSE mandaría a
   remedir el medidor en disputa). Al confirmar se guarda la elección y
   además se borra explícitamente la revisión perdedora
   (`DELETE .../{id}?rev={rev_perdedora}`) — ese borrado es lo que
   realmente cierra el conflicto; sin él, CouchDB seguiría reportando la
   rama vieja para siempre.

8. **Consulta Mango en vivo** — en la UI central, elegir una zona y un
   mínimo de m³ y apretar Buscar (es la misma consulta de la sección
   "Lenguaje de consulta" de la presentación, ahora con resultados reales).

9. Opcional: en cada tablet, apretar **"↓ Traer cambios del central"** para
   que las tres copias vuelvan a quedar idénticas, sin rastro del
   conflicto ya resuelto.

### Generar un conflicto extra, a mano y en vivo

Si querés mostrar cómo se provoca un conflicto además del que ya viene
armado (por ejemplo para una pregunta del público), cualquier lectura que
ya esté sincronizada en las dos tablets sirve: usá "editar valor" en la
tablet A con un número, después "editar valor" en la tablet B con otro
número *antes* de volver a sincronizar, y sincronizá cualquiera de las
dos. Mismo mecanismo, en vivo.

Alternativa por terminal (dispara las dos sincronizaciones y muestra los
conflictos ya armados por `setup.sh`, sin resolverlos):
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
./replicate.sh        # dispara la replicación tablet A -> central
./replicate-b.sh       # dispara la replicación tablet B -> central
./view-query.sh        # vista MapReduce por_zona
./mango-query.sh       # consulta Mango de la presentación
./conflict-demo.sh     # variante 2 nodos (central vs tablet A) editando a mano
```

## Si algo falla

- `docker compose ps` — confirmar que los tres contenedores están `healthy`/`Up`.
- Si un puerto está ocupado, cambiar `5984`/`5985`/`5986` en `docker-compose.yml`
  (y el puerto correspondiente en `ui/*/index.html`, constante `API`).
- Los scripts usan `python3 -m json.tool` solo para formatear la salida; si
  no está disponible, sacar ese tramo del pipe y listo (el JSON crudo de
  CouchDB también sirve para mostrar en pantalla).
