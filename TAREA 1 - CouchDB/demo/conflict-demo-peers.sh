#!/usr/bin/env bash
# Sincroniza la tablet A contra el central y reporta el estado de los
# conflictos.
#
# OJO: la tablet B corre PouchDB dentro del navegador, asi que no se puede
# manejar desde la terminal. Para que aparezca el conflicto peer-to-peer
# hay que abrir http://localhost:8083 y poner su switch en "EN LINEA":
# ahi PouchDB replica solo, y los dos documentos que comparte con la
# tablet A (OSE-3390 y OSE-4488) quedan en conflicto en el central.
set -euo pipefail
cd "$(dirname "$0")"
CENTRAL="http://admin:admin123@localhost:5984"

echo "1) Tablet A (jperez) sincroniza contra el central..."
curl -s -X POST "$CENTRAL/_replicate" -H "Content-Type: application/json" \
  -d '{"source":"http://admin:admin123@couch-tablet:5984/inspecciones","target":"http://admin:admin123@couch-central:5984/inspecciones","create_target":false}' >/dev/null

echo
echo "2) Estado del central:"
curl -s "$CENTRAL/inspecciones/_changes?include_docs=true&conflicts=true&style=all_docs" | python3 -c "
import sys, json
d = json.load(sys.stdin)
docs = [r['doc'] for r in d['results'] if r.get('doc') and r['doc'].get('type') == 'lectura_medidor']
conf = [x for x in docs if x.get('_conflicts')]
inspectores = sorted({x.get('inspector','?') for x in docs})
print(f'   {len(docs)} lecturas, de: {\", \".join(inspectores)}')
print(f'   {len(conf)} en conflicto')
for x in conf:
    print(f\"     - {x['_id']} ({x['medidor_id']}): vigente {x['valor_m3']} m3 [{x['_rev']}], en conflicto {x['_conflicts'][0]}\")
if not conf:
    print()
    print('   Todavia no hay conflicto: falta que la tablet B replique.')
    print('   Abri http://localhost:8083 y pone el switch en EN LINEA.')
"

echo
echo "Para resolver los conflictos: UI central en http://localhost:8081,"
echo "link 'resolver conflicto' en la lectura correspondiente."
