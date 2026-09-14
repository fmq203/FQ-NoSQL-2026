#!/usr/bin/env bash
# Corre la consulta Mango de la presentacion (zona Canelones-Este,
# valor_m3 > 15000, ordenado descendente) contra el central.
set -euo pipefail
cd "$(dirname "$0")"
CENTRAL="http://admin:admin123@localhost:5984"

curl -s -X POST "$CENTRAL/inspecciones/_find" \
  -H "Content-Type: application/json" \
  -d @mango-query.json | python3 -m json.tool
