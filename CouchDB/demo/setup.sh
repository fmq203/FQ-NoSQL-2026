#!/usr/bin/env bash
# Prepara los nodos CouchDB de la demo:
#   - central A (:5984) y central B (:5987), los dos masters, replicandose
#     entre si de forma continua y bidireccional
#   - tablet A (:5985) con la ruta de jperez, offline
#
# La tablet B (mgonzalez) NO se toca desde aca: corre PouchDB dentro del
# navegador y se siembra sola la primera vez que abris http://localhost:8083.
# Dos de sus lecturas comparten _id con lecturas de la tablet A, asi que
# cuando las dos repliquen al central esos documentos quedan en conflicto.
set -euo pipefail
cd "$(dirname "$0")"

CENTRAL_A="http://admin:admin123@localhost:5984"
CENTRAL_B="http://admin:admin123@localhost:5987"
TABLET="http://admin:admin123@localhost:5985"

echo "Esperando a que levanten los nodos..."
for NODE in "$CENTRAL_A" "$CENTRAL_B" "$TABLET"; do
  until curl -sf "$NODE/_up" >/dev/null 2>&1; do sleep 1; done
done
echo "Nodos arriba."

echo "Creando bases de sistema (_users, _replicator, _global_changes)..."
for NODE in "$CENTRAL_A" "$CENTRAL_B" "$TABLET"; do
  for SYSDB in _users _replicator _global_changes; do
    curl -s -o /dev/null -X PUT "$NODE/$SYSDB"
  done
done

echo "Habilitando CORS (las UI web y PouchDB hablan desde el navegador)..."
for NODE in "$CENTRAL_A" "$CENTRAL_B" "$TABLET"; do
  curl -s -o /dev/null -X PUT "$NODE/_node/_local/_config/httpd/enable_cors" -d '"true"'
  curl -s -o /dev/null -X PUT "$NODE/_node/_local/_config/cors/origins" -d '"*"'
  # PouchDB manda las peticiones con credenciales: sin esto en "true" el
  # navegador descarta la respuesta y la replicacion falla en silencio.
  curl -s -o /dev/null -X PUT "$NODE/_node/_local/_config/cors/credentials" -d '"true"'
  curl -s -o /dev/null -X PUT "$NODE/_node/_local/_config/cors/methods" -d '"GET, PUT, POST, HEAD, DELETE"'
  curl -s -o /dev/null -X PUT "$NODE/_node/_local/_config/cors/headers" -d '"accept, authorization, content-type, origin, referer"'
done

echo "Creando base 'inspecciones' en los tres nodos..."
for NODE in "$CENTRAL_A" "$CENTRAL_B" "$TABLET"; do
  curl -s -o /dev/null -X PUT "$NODE/inspecciones"
done

echo "Cargando el design document (vistas por_zona y pendientes_sync)..."
for NODE in "$CENTRAL_A" "$CENTRAL_B" "$TABLET"; do
  curl -s -o /dev/null -X PUT "$NODE/inspecciones/_design/lecturas" \
    -H "Content-Type: application/json" -d @design-lecturas.json
done

echo "Creando índice Mango (type, zona, valor_m3)..."
for NODE in "$CENTRAL_A" "$CENTRAL_B" "$TABLET"; do
  curl -s -o /dev/null -X POST "$NODE/inspecciones/_index" \
    -H "Content-Type: application/json" -d @mango-index.json
done

# Replicacion continua entre los dos masters. Va en la base _replicator (no
# con POST /_replicate) para que sea persistente: si un nodo se reinicia,
# CouchDB retoma la replicacion solo. Cada central tira del otro.
echo "Enlazando central A <-> central B (replicación continua)..."
curl -s -o /dev/null -X PUT "$CENTRAL_A/_replicator/desde-central-b" \
  -H "Content-Type: application/json" -d '{
    "source": { "url": "http://couch-central-b:5984/inspecciones",
                "auth": { "basic": { "username": "admin", "password": "admin123" } } },
    "target": { "url": "http://couch-central:5984/inspecciones",
                "auth": { "basic": { "username": "admin", "password": "admin123" } } },
    "continuous": true
  }'
curl -s -o /dev/null -X PUT "$CENTRAL_B/_replicator/desde-central-a" \
  -H "Content-Type: application/json" -d '{
    "source": { "url": "http://couch-central:5984/inspecciones",
                "auth": { "basic": { "username": "admin", "password": "admin123" } } },
    "target": { "url": "http://couch-central-b:5984/inspecciones",
                "auth": { "basic": { "username": "admin", "password": "admin123" } } },
    "continuous": true
  }'

echo "El inspector jperez carga 6 lecturas trabajando SIN conexión..."
curl -s -X POST "$TABLET/inspecciones/_bulk_docs" \
  -H "Content-Type: application/json" \
  -d @lecturas.json | python3 -m json.tool

echo
echo "Listo. Estado inicial:"
echo "  Central A -> $CENTRAL_A/inspecciones  (Fauxton: http://localhost:5984/_utils)"
echo "  Central B -> $CENTRAL_B/inspecciones  (Fauxton: http://localhost:5987/_utils)"
echo "  Tablet A  -> $TABLET/inspecciones     (Fauxton: http://localhost:5985/_utils)"
echo "  Tablet B  -> PouchDB en el navegador, se siembra al abrir http://localhost:8083"
echo
echo "OJO: la tablet B guarda en el IndexedDB del navegador, asi que"
echo "'docker compose down -v' NO la borra. Usa ./reset.sh, que te recuerda"
echo "el paso del navegador."
