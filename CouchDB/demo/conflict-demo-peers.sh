#!/usr/bin/env bash
# Version "peer-to-peer" del conflicto: NO lo genera el central, lo genera
# que dos inspectores (tablet A y tablet B) corrigen la misma lectura sin
# haberse visto entre si. El conflicto recien se ve cuando alguien las
# sincroniza a las dos. Es el escenario recomendado en DEMO.md.
#
# Requisito: haber corrido setup.sh, y que la tablet A ya haya sincronizado
# al menos una vez (./replicate.sh) para que central y tablet B tengan
# el mismo punto de partida.
set -euo pipefail
CENTRAL="http://admin:admin123@localhost:5984"
TABLET_A="http://admin:admin123@localhost:5985"
TABLET_B="http://admin:admin123@localhost:5986"
DOC="lectura:2026-09-13:00238"

rev() { python3 -c "import sys,json; print(json.load(sys.stdin)['_rev'])"; }

echo "0) Tablet B (recien incorporada) trae la base del central..."
curl -s -X POST "$TABLET_B/_replicate" -H "Content-Type: application/json" \
  -d '{"source":"http://admin:admin123@couch-central:5984/inspecciones","target":"http://admin:admin123@localhost:5984/inspecciones","create_target":false}' >/dev/null

echo "1) jperez (tablet A) corrige la lectura a 5100.0..."
REV_A=$(curl -s "$TABLET_A/inspecciones/$DOC" | rev)
curl -s -o /dev/null -X PUT "$TABLET_A/inspecciones/$DOC" \
  -H "Content-Type: application/json" \
  -d "{\"_rev\":\"$REV_A\",\"type\":\"lectura_medidor\",\"medidor_id\":\"OSE-3390\",\"zona\":\"Florida-Norte\",\"inspector\":\"jperez\",\"fecha\":\"2026-09-13T15:44:00-03:00\",\"valor_m3\":5100.0,\"sincronizado\":false,\"geo\":{\"lat\":-34.1,\"lon\":-56.22}}"

echo "2) mgonzalez (tablet B), sin saberlo, corrige la misma lectura a 5087.4..."
REV_B=$(curl -s "$TABLET_B/inspecciones/$DOC" | rev)
curl -s -o /dev/null -X PUT "$TABLET_B/inspecciones/$DOC" \
  -H "Content-Type: application/json" \
  -d "{\"_rev\":\"$REV_B\",\"type\":\"lectura_medidor\",\"medidor_id\":\"OSE-3390\",\"zona\":\"Florida-Norte\",\"inspector\":\"mgonzalez\",\"fecha\":\"2026-09-13T15:44:00-03:00\",\"valor_m3\":5087.4,\"sincronizado\":false,\"geo\":{\"lat\":-34.1,\"lon\":-56.22}}"

echo "3) Tablet A sincroniza primero..."
curl -s -o /dev/null -X POST "$TABLET_A/_replicate" -H "Content-Type: application/json" \
  -d '{"source":"http://admin:admin123@localhost:5984/inspecciones","target":"http://admin:admin123@couch-central:5984/inspecciones","create_target":false}'

echo "   -> el central todavia no tiene conflicto (solo vio una rama):"
curl -s "$CENTRAL/inspecciones/$DOC?conflicts=true" | python3 -c "import sys,json;d=json.load(sys.stdin);print('   valor:',d['valor_m3'],'conflicts:',d.get('_conflicts','ninguno'))"

echo "4) Tablet B sincroniza despues (trae la otra rama)..."
curl -s -o /dev/null -X POST "$TABLET_B/_replicate" -H "Content-Type: application/json" \
  -d '{"source":"http://admin:admin123@localhost:5984/inspecciones","target":"http://admin:admin123@couch-central:5984/inspecciones","create_target":false}'

echo
echo "5) Recien ahora el central ve el conflicto entre los dos inspectores:"
curl -s "$CENTRAL/inspecciones/$DOC?conflicts=true" | python3 -m json.tool

echo
echo "Ningun nodo actuo como 'autoridad': el conflicto solo existe donde"
echo "confluyen las dos replicas. Para resolverlo, usar la UI central"
echo "(http://localhost:8081) -> 'resolver conflicto'."
