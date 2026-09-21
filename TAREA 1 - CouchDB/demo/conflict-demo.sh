#!/usr/bin/env bash
# Variante rapida (2 nodos, central vs tablet A) del conflicto de
# replicacion: edita el MISMO documento en central y en tablet sin
# sincronizar entre medio, y despues replica para mostrar que CouchDB no
# pierde ningun cambio: guarda ambas revisiones y expone el conflicto en
# _conflicts. Para el escenario mas realista de dos inspectores (peer to
# peer, sin que el central sea "la autoridad"), ver conflict-demo-peers.sh.
#
# Requisito: haber corrido antes setup.sh y replicate.sh al menos una vez,
# para que el documento ya exista en los dos nodos.
set -euo pipefail
CENTRAL="http://admin:admin123@localhost:5984"
TABLET="http://admin:admin123@localhost:5985"
DOC="lectura:2026-09-13:00234"

rev() { python3 -c "import sys,json; print(json.load(sys.stdin)['_rev'])"; }

echo "1) El central corrige la lectura (recalculo interno)..."
REV_C=$(curl -s "$CENTRAL/inspecciones/$DOC" | rev)
curl -s -X PUT "$CENTRAL/inspecciones/$DOC" \
  -H "Content-Type: application/json" \
  -d "{\"_rev\":\"$REV_C\",\"type\":\"lectura_medidor\",\"medidor_id\":\"OSE-4471\",\"zona\":\"Canelones-Este\",\"inspector\":\"jperez\",\"fecha\":\"2026-09-13T14:32:00-03:00\",\"valor_m3\":18500.0,\"sincronizado\":true,\"geo\":{\"lat\":-34.708,\"lon\":-55.982}}" >/dev/null
echo "   central -> valor_m3 = 18500.0"

echo "2) A la vez, en la tablet (todavia sin ver el cambio del central) el inspector corrige el mismo documento..."
REV_T=$(curl -s "$TABLET/inspecciones/$DOC" | rev)
curl -s -X PUT "$TABLET/inspecciones/$DOC" \
  -H "Content-Type: application/json" \
  -d "{\"_rev\":\"$REV_T\",\"type\":\"lectura_medidor\",\"medidor_id\":\"OSE-4471\",\"zona\":\"Canelones-Este\",\"inspector\":\"jperez\",\"fecha\":\"2026-09-13T14:32:00-03:00\",\"valor_m3\":18470.3,\"sincronizado\":false,\"geo\":{\"lat\":-34.708,\"lon\":-55.982}}" >/dev/null
echo "   tablet  -> valor_m3 = 18470.3"

echo "3) Se restablece la conexion: replicamos tablet -> central..."
curl -s -X POST "$CENTRAL/_replicate" \
  -H "Content-Type: application/json" \
  -d '{"source":"http://admin:admin123@couch-tablet:5984/inspecciones","target":"http://admin:admin123@couch-central:5984/inspecciones","create_target":false}' >/dev/null

echo
echo "4) El documento en el central ahora reporta un conflicto:"
curl -s "$CENTRAL/inspecciones/$DOC?conflicts=true" | python3 -m json.tool

echo
echo "CouchDB conservo las dos revisiones; la app decide cual es la version"
echo "valida y borra la otra (o las combina). Nada se perdio en silencio."
