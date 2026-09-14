# Demo en vivo — "OSE Móvil"

Dos nodos CouchDB en Docker simulan el servidor central y la tablet de un
inspector. Corresponde a la sección "Ejemplo ficticio" y "Replicación" de
`presentacion-couchdb.html`.

- **Central** → http://localhost:5984 (Fauxton: http://localhost:5984/_utils)
- **Tablet**  → http://localhost:5985 (Fauxton: http://localhost:5985/_utils)
- Usuario/clave de ambos: `admin` / `admin123`

## Guion para presentar

1. **Levantar los nodos**
   ```
   docker compose up -d
   ```

2. **Cargar el escenario** (crea las bases, sube el design document con las
   vistas, crea el índice Mango y carga 6 lecturas *solo en la tablet*,
   simulando que el inspector trabajó offline todo el día):
   ```
   ./setup.sh
   ```

3. **Mostrar la asimetría** — el central todavía no vio nada:
   ```
   curl http://admin:admin123@localhost:5984/inspecciones/_all_docs
   curl http://admin:admin123@localhost:5985/inspecciones/_all_docs
   ```
   (o abrir Fauxton de los dos nodos lado a lado en el navegador)

4. **"Llega señal" → sincronizar** (dispara la replicación tablet → central):
   ```
   ./replicate.sh
   ```
   Ahora el central tiene los 6 documentos y el design document.

5. **Vista MapReduce** — total y estadísticas de m³ por zona:
   ```
   ./view-query.sh
   ```

6. **Consulta Mango** — lecturas de Canelones-Este mayores a 15.000 m³:
   ```
   ./mango-query.sh
   ```

7. **(Opcional, avanzado) Conflicto multi-maestro** — edita el mismo
   documento en los dos nodos "desconectados" y vuelve a sincronizar para
   mostrar que CouchDB no pisa datos, guarda ambas revisiones:
   ```
   ./conflict-demo.sh
   ```

8. **Apagar todo al terminar**:
   ```
   docker compose down -v
   ```

## Si algo falla

- `docker compose ps` — confirmar que los dos contenedores están `healthy`/`Up`.
- Si un puerto está ocupado, cambiar `5984`/`5985` en `docker-compose.yml`.
- Los scripts usan `python3 -m json.tool` solo para formatear la salida; si
  no está disponible, sacar ese tramo del pipe y listo (el JSON crudo de
  CouchDB también sirve para mostrar en pantalla).
