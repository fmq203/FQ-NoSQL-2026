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
  un switch "En línea / Sin conexión" y el botón que dispara la sincronización.
- **UI Central** → http://localhost:8081 — panel de solo lectura: totales,
  m³ por zona, buscador Mango y alerta de conflictos. Se actualiza sola
  cada 4 segundos, así que conviene tenerla abierta en otra ventana/proyector
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

7. **(Opcional, avanzado) Conflicto multi-maestro por terminal** — edita el
   mismo documento en los dos nodos "desconectados" y vuelve a sincronizar
   para mostrar que CouchDB no pisa datos, guarda ambas revisiones (esto
   se ve también como un badge "⚠ conflicto" en la UI central):
   ```
   ./conflict-demo.sh
   ```

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
