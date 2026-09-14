#!/usr/bin/env bash
# Levanta la base "inspecciones" en el nodo tablet (offline) con las vistas
# y las lecturas de ejemplo. El central y la tablet-b se crean vacíos a
# propósito, para poder mostrar la sincronización durante la demo.
set -euo pipefail
cd "$(dirname "$0")"

CENTRAL="http://admin:admin123@localhost:5984"
TABLET="http://admin:admin123@localhost:5985"
TABLET_B="http://admin:admin123@localhost:5986"

echo "Esperando a que levanten los nodos..."
until curl -sf "$CENTRAL/_up" >/dev/null 2>&1; do sleep 1; done
until curl -sf "$TABLET/_up" >/dev/null 2>&1; do sleep 1; done
until curl -sf "$TABLET_B/_up" >/dev/null 2>&1; do sleep 1; done
echo "Nodos arriba."

echo "Creando bases de sistema (_users, _replicator, _global_changes) en los tres nodos..."
for NODE in "$CENTRAL" "$TABLET" "$TABLET_B"; do
  for SYSDB in _users _replicator _global_changes; do
    curl -s -o /dev/null -X PUT "$NODE/$SYSDB"
  done
done

echo "Habilitando CORS en los tres nodos (para las UI web)..."
for NODE in "$CENTRAL" "$TABLET" "$TABLET_B"; do
  curl -s -o /dev/null -X PUT "$NODE/_node/_local/_config/httpd/enable_cors" -d '"true"'
  curl -s -o /dev/null -X PUT "$NODE/_node/_local/_config/cors/origins" -d '"*"'
  curl -s -o /dev/null -X PUT "$NODE/_node/_local/_config/cors/credentials" -d '"false"'
  curl -s -o /dev/null -X PUT "$NODE/_node/_local/_config/cors/methods" -d '"GET, PUT, POST, HEAD, DELETE"'
  curl -s -o /dev/null -X PUT "$NODE/_node/_local/_config/cors/headers" -d '"accept, authorization, content-type, origin, referer"'
done

echo "Creando base 'inspecciones' en los tres nodos..."
curl -s -X PUT "$CENTRAL/inspecciones" >/dev/null
curl -s -X PUT "$TABLET/inspecciones" >/dev/null
curl -s -X PUT "$TABLET_B/inspecciones" >/dev/null

echo "Cargando el design document (vistas por_zona y pendientes_sync) en la tablet..."
curl -s -X PUT "$TABLET/inspecciones/_design/lecturas" \
  -H "Content-Type: application/json" \
  -d @design-lecturas.json >/dev/null

echo "Creando índice Mango (type, zona, valor_m3) en la tablet..."
curl -s -X POST "$TABLET/inspecciones/_index" \
  -H "Content-Type: application/json" \
  -d @mango-index.json >/dev/null

echo "El inspector jperez carga 6 lecturas trabajando SIN conexión (directo en la tablet)..."
curl -s -X POST "$TABLET/inspecciones/_bulk_docs" \
  -H "Content-Type: application/json" \
  -d @lecturas.json | python3 -m json.tool

echo
echo "La tablet-b arranca vacía a propósito: es un segundo inspector que se"
echo "suma después y primero tiene que 'Traer cambios del central' para"
echo "empezar a trabajar con la misma base (ver DEMO.md, escenario de"
echo "conflicto entre dos inspectores)."
echo
echo "Listo. Estado inicial:"
echo "  Tablet A  -> $TABLET/inspecciones   (Fauxton: http://localhost:5985/_utils)"
echo "  Tablet B  -> $TABLET_B/inspecciones (Fauxton: http://localhost:5986/_utils)"
echo "  Central   -> $CENTRAL/inspecciones  (Fauxton: http://localhost:5984/_utils)"
