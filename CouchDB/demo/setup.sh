#!/usr/bin/env bash
# Prepara los dos nodos CouchDB (central y tablet A) y carga la ruta de
# jperez en la tablet A, offline.
#
# La tablet B (mgonzalez) NO se toca desde acá: corre PouchDB dentro del
# navegador y se siembra sola la primera vez que abris http://localhost:8083.
# Dos de sus lecturas comparten _id con lecturas de la tablet A, asi que
# cuando las dos repliquen al central esos documentos quedan en conflicto.
set -euo pipefail
cd "$(dirname "$0")"

CENTRAL="http://admin:admin123@localhost:5984"
TABLET="http://admin:admin123@localhost:5985"

echo "Esperando a que levanten los nodos..."
until curl -sf "$CENTRAL/_up" >/dev/null 2>&1; do sleep 1; done
until curl -sf "$TABLET/_up" >/dev/null 2>&1; do sleep 1; done
echo "Nodos arriba."

echo "Creando bases de sistema (_users, _replicator, _global_changes)..."
for NODE in "$CENTRAL" "$TABLET"; do
  for SYSDB in _users _replicator _global_changes; do
    curl -s -o /dev/null -X PUT "$NODE/$SYSDB"
  done
done

echo "Habilitando CORS (las UI web y PouchDB hablan desde el navegador)..."
for NODE in "$CENTRAL" "$TABLET"; do
  curl -s -o /dev/null -X PUT "$NODE/_node/_local/_config/httpd/enable_cors" -d '"true"'
  curl -s -o /dev/null -X PUT "$NODE/_node/_local/_config/cors/origins" -d '"*"'
  curl -s -o /dev/null -X PUT "$NODE/_node/_local/_config/cors/credentials" -d '"false"'
  curl -s -o /dev/null -X PUT "$NODE/_node/_local/_config/cors/methods" -d '"GET, PUT, POST, HEAD, DELETE"'
  curl -s -o /dev/null -X PUT "$NODE/_node/_local/_config/cors/headers" -d '"accept, authorization, content-type, origin, referer"'
done

echo "Creando base 'inspecciones' en central y tablet A..."
curl -s -X PUT "$CENTRAL/inspecciones" >/dev/null
curl -s -X PUT "$TABLET/inspecciones" >/dev/null

echo "Cargando el design document (vistas por_zona y pendientes_sync)..."
curl -s -X PUT "$TABLET/inspecciones/_design/lecturas" \
  -H "Content-Type: application/json" \
  -d @design-lecturas.json >/dev/null

echo "Creando índice Mango (type, zona, valor_m3)..."
curl -s -X POST "$TABLET/inspecciones/_index" \
  -H "Content-Type: application/json" \
  -d @mango-index.json >/dev/null

echo "El inspector jperez carga 6 lecturas trabajando SIN conexión..."
curl -s -X POST "$TABLET/inspecciones/_bulk_docs" \
  -H "Content-Type: application/json" \
  -d @lecturas.json | python3 -m json.tool

echo
echo "Listo. Estado inicial:"
echo "  Tablet A  -> $TABLET/inspecciones   (Fauxton: http://localhost:5985/_utils)"
echo "  Central   -> $CENTRAL/inspecciones  (Fauxton: http://localhost:5984/_utils)"
echo "  Tablet B  -> PouchDB en el navegador, se siembra al abrir http://localhost:8083"
echo
echo "OJO: la tablet B guarda en el IndexedDB del navegador, asi que"
echo "'docker compose down -v' NO la borra. Para reiniciarla, usa el link"
echo "'reiniciar datos locales' abajo de todo en su pantalla."
