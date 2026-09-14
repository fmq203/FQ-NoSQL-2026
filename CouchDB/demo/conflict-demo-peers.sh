#!/usr/bin/env bash
# El conflicto "peer to peer" ya viene armado por setup.sh: la tablet A
# (jperez) y la tablet B (mgonzalez) midieron los mismos dos medidores
# (OSE-3390 y OSE-4488) sin verse entre si, cada una con su propio
# historial de revisiones. Este script solo dispara las dos
# sincronizaciones, en orden, y muestra como recien con la segunda el
# central detecta el conflicto — no lo resuelve (para eso, usar la UI
# central en http://localhost:8081, "resolver conflicto").
#
# Requisito: haber corrido setup.sh antes.
set -euo pipefail
cd "$(dirname "$0")"
CENTRAL="http://admin:admin123@localhost:5984"

echo "1) Tablet A (jperez) sincroniza..."
curl -s -X POST "$CENTRAL/_replicate" -H "Content-Type: application/json" \
  -d '{"source":"http://admin:admin123@couch-tablet:5984/inspecciones","target":"http://admin:admin123@couch-central:5984/inspecciones","create_target":false}' >/dev/null

echo "   -> el central todavia no tiene conflictos (solo vio una rama)."
echo
echo "2) Tablet B (mgonzalez) sincroniza..."
curl -s -X POST "$CENTRAL/_replicate" -H "Content-Type: application/json" \
  -d '{"source":"http://admin:admin123@couch-tablet-b:5984/inspecciones","target":"http://admin:admin123@couch-central:5984/inspecciones","create_target":false}' >/dev/null

echo
echo "3) Recien ahora el central ve los conflictos entre las dos inspectoras:"
curl -s "$CENTRAL/inspecciones/_changes?include_docs=true&conflicts=true&style=all_docs" | python3 -c "
import sys, json
d = json.load(sys.stdin)
docs = [r['doc'] for r in d['results'] if r.get('doc') and r['doc'].get('type') == 'lectura_medidor']
conf = [x for x in docs if x.get('_conflicts')]
print(f'{len(docs)} lecturas totales, {len(conf)} en conflicto:')
for x in conf:
    print(f\"  - {x['_id']} ({x['medidor_id']}): central tiene {x['valor_m3']} m3, en conflicto rev {x['_conflicts'][0]}\")
"

echo
echo "Ningun nodo actuo como 'autoridad': el conflicto solo existe donde"
echo "confluyen las dos replicas. Para resolverlo, usar la UI central"
echo "(http://localhost:8081) -> 'resolver conflicto'."
