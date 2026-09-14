#!/usr/bin/env bash
# Levanta la base "inspecciones" en las dos tablets, cada una offline y sin
# verse entre si. La tablet A (jperez) carga su ruta completa. La tablet B
# (mgonzalez) carga su propia ruta MAS dos lecturas que "chocan" a
# proposito con dos de la tablet A (mismo _id, valor distinto): apenas las
# dos tablets sincronicen con el central, esos dos documentos van a
# aparecer como conflicto, listos para resolver en la UI central. El
# central se crea vacio a proposito, para poder mostrar la sincronizacion
# durante la demo.
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
echo "La inspectora mgonzalez (tablet-b), sin ver lo anterior, carga su propia"
echo "ruta — dos lecturas nuevas y dos que coinciden con medidores que jperez"
echo "ya midió (OSE-3390 y OSE-4488), con valores distintos..."
curl -s -X POST "$TABLET_B/inspecciones/_bulk_docs" \
  -H "Content-Type: application/json" \
  -d @lecturas-tablet-b.json | python3 -m json.tool

echo
echo "Listo. Estado inicial:"
echo "  Tablet A  -> $TABLET/inspecciones   (Fauxton: http://localhost:5985/_utils)"
echo "  Tablet B  -> $TABLET_B/inspecciones (Fauxton: http://localhost:5986/_utils)"
echo "  Central   -> $CENTRAL/inspecciones  (Fauxton: http://localhost:5984/_utils)"
