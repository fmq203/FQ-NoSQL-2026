#!/usr/bin/env bash
# Levanta la base "inspecciones" en el nodo tablet (offline) con las vistas
# y las lecturas de ejemplo. El nodo central se crea vacío a propósito,
# para poder mostrar la sincronización con replicate.sh durante la demo.
set -euo pipefail
cd "$(dirname "$0")"

CENTRAL="http://admin:admin123@localhost:5984"
TABLET="http://admin:admin123@localhost:5985"

echo "Esperando a que levanten los nodos..."
until curl -sf "$CENTRAL/_up" >/dev/null 2>&1; do sleep 1; done
until curl -sf "$TABLET/_up" >/dev/null 2>&1; do sleep 1; done
echo "Nodos arriba."

echo "Creando bases de sistema (_users, _replicator, _global_changes) en ambos nodos..."
for NODE in "$CENTRAL" "$TABLET"; do
  for SYSDB in _users _replicator _global_changes; do
    curl -s -o /dev/null -X PUT "$NODE/$SYSDB"
  done
done

echo "Creando base 'inspecciones' en central y en tablet..."
curl -s -X PUT "$CENTRAL/inspecciones" >/dev/null
curl -s -X PUT "$TABLET/inspecciones" >/dev/null

echo "Cargando el design document (vistas por_zona y pendientes_sync) en la tablet..."
curl -s -X PUT "$TABLET/inspecciones/_design/lecturas" \
  -H "Content-Type: application/json" \
  -d @design-lecturas.json >/dev/null

echo "Creando índice Mango (type, zona, valor_m3) en la tablet..."
curl -s -X POST "$TABLET/inspecciones/_index" \
  -H "Content-Type: application/json" \
  -d @mango-index.json >/dev/null

echo "El inspector carga 6 lecturas trabajando SIN conexión (directo en la tablet)..."
curl -s -X POST "$TABLET/inspecciones/_bulk_docs" \
  -H "Content-Type: application/json" \
  -d @lecturas.json | python3 -m json.tool

echo
echo "Listo. La tablet tiene datos que el central todavía no vio:"
echo "  Tablet  -> $TABLET/inspecciones (Fauxton: http://localhost:5985/_utils)"
echo "  Central -> $CENTRAL/inspecciones (Fauxton: http://localhost:5984/_utils)"
