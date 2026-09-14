# Demo en vivo — "OSE Móvil"

Dos nodos CouchDB en Docker simulan el servidor central y la tablet de un
inspector. Corresponde a la sección "Ejemplo ficticio" y "Replicación" de
`presentacion-couchdb.html`.

- **Central** → http://localhost:5984 (Fauxton: http://localhost:5984/_utils)
- **Tablet**  → http://localhost:5985 (Fauxton: http://localhost:5985/_utils)
- Usuario/clave de ambos: `admin` / `admin123`

Además de la API cruda hay dos **UI web** hechas a medida (HTML+JS plano,
sin build) para mostrar la historia sin depender de Fauxton ni de la
terminal:

- **UI Tablet** → http://localhost:8082 — formulario para cargar lecturas,
  un switch "En línea / Sin conexión", botones de sincronización (subir y
  bajar cambios) y un link "editar valor" en cada lectura.
- **UI Central** → http://localhost:8081 — panel de monitoreo: totales, m³
  por zona, buscador Mango, "editar valor" por lectura y, cuando aparece un
  conflicto, un link "resolver conflicto". Se actualiza sola cada 4
  segundos, así que conviene tenerla abierta en otra ventana/proyector
  mientras se opera la tablet.

## Guion para presentar

1. **Levantar los nodos**
   ```
   docker compose up -d
   ```

2. **Cargar el escenario** (crea las bases, sube el design document con las
   vistas, crea el índice Mango, habilita CORS para las UI y carga 6
   lecturas *solo en la tablet*, simulando que el inspector trabajó offline
   todo el día):
   ```
   ./setup.sh
   ```

3. **Levantar las dos UI**:
   ```
   ./serve-ui.sh
   ```
   Abrir http://localhost:8082 (tablet) y http://localhost:8081 (central)
   en dos ventanas lado a lado.

4. **Mostrar la asimetría** — la tablet ya tiene 6 lecturas cargadas, el
   panel central todavía muestra 0. Cargar una lectura nueva a mano en la
   UI de la tablet (queda igual, local) para reforzar que escribir nunca
   depende de la conexión.

5. **"Llega señal"** — activar el switch "Sin conexión → En línea" en la
   tablet y apretar **Sincronizar con central**. El panel central se
   actualiza solo (sin recargar la página) con los totales, el gráfico de
   barras por zona y la lista de documentos.

6. **Consulta Mango en vivo** — en la UI central, elegir una zona y un
   mínimo de m³ y apretar Buscar (es la misma consulta de la sección
   "Lenguaje de consulta" de la presentación, ahora con resultados reales).

7. **Provocar un conflicto en vivo, a un clic** — esta es la parte que
   contesta "¿y si dos personas corrigen lo mismo al mismo tiempo?":

   a. En la UI de la **tablet**, abrí "editar valor" en cualquier lectura ya
      cargada (por ejemplo OSE-5102) y guardá un número distinto — esto
      queda solo local, sin tocar el central.

   b. Sin sincronizar todavía, en la UI del **central** abrí "editar valor"
      en **esa misma lectura** y guardá un número *distinto al anterior*.
      Ahora las dos copias divergieron desde la misma revisión, cada una
      sin saber de la otra — el escenario real de dos usuarios editando
      offline.

   c. Volvé a la tablet y apretá **Sincronizar con central**. La UI central
      se actualiza sola: el contador "conflictos" pasa a 1 y la lectura
      muestra el badge rojo "⚠ conflicto". Nada se pisó ni se perdió — las
      dos revisiones existen.

   d. En la UI central, abrí **"resolver conflicto"** en esa lectura. Se
      abre un panel con los dos valores enfrentados ("actual (central)" vs.
      "en conflicto (llegó de la tablet)") y un botón para cada uno.
      Elegir cualquiera de los dos: CouchDB nunca decide por vos, la
      aplicación es la que corrige la inconsistencia. Al confirmar, se
      guarda el valor elegido *y además se borra explícitamente la
      revisión perdedora* (`DELETE .../{id}?rev={rev_perdedora}`) — ese
      borrado es el que realmente cierra el conflicto; sin él, CouchDB
      sigue reportando la rama vieja para siempre.

   e. El badge "⚠ conflicto" desaparece solo en el siguiente refresco.
      Opcional: volvé a la tablet y apretá **"↓ Traer cambios del
      central"** para bajar la resolución y que las dos copias queden
      idénticas otra vez.

   Alternativa por terminal (mismo mecanismo, sin clickear):
   ```
   ./conflict-demo.sh
   ```
   (este script solo genera y muestra el conflicto, no lo resuelve — para
   la resolución conviene la UI, o repetir a mano los pasos GET rev → PUT →
   DELETE rev que se explican arriba).

8. **Apagar todo al terminar**:
   ```
   ./stop-ui.sh
   docker compose down -v
   ```

## Solo terminal (sin las UI web)

Si preferís mostrar todo por línea de comandos en vez de las páginas:
```
./replicate.sh      # dispara la replicación tablet -> central
./view-query.sh      # vista MapReduce por_zona
./mango-query.sh     # consulta Mango de la presentación
```

## Si algo falla

- `docker compose ps` — confirmar que los dos contenedores están `healthy`/`Up`.
- Si un puerto está ocupado, cambiar `5984`/`5985` en `docker-compose.yml`.
- Los scripts usan `python3 -m json.tool` solo para formatear la salida; si
  no está disponible, sacar ese tramo del pipe y listo (el JSON crudo de
  CouchDB también sirve para mostrar en pantalla).
