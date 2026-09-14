#!/usr/bin/env bash
# Igual que replicate.sh pero para la segunda tablet (mgonzalez).
set -euo pipefail
cd "$(dirname "$0")"

CENTRAL="http://admin:admin123@localhost:5984"

echo "Disparando replicacion tablet-b -> central..."
curl -s -X POST "$CENTRAL/_replicate" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "http://admin:admin123@couch-tablet-b:5984/inspecciones",
    "target": "http://admin:admin123@couch-central:5984/inspecciones",
    "create_target": false
  }' | python3 -m json.tool

echo
echo "Verificando documentos en el central:"
curl -s "$CENTRAL/inspecciones/_all_docs" | python3 -m json.tool
