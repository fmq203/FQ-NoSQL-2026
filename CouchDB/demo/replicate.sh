#!/usr/bin/env bash
# Simula que la tablet recupera conectividad: el nodo central le pide
# al de la tablet que le replique la base "inspecciones".
# Usa el nombre de servicio de docker-compose (couch-tablet) porque la
# replicacion corre DENTRO del contenedor central, no desde el host.
set -euo pipefail
cd "$(dirname "$0")"

CENTRAL="http://admin:admin123@localhost:5984"

echo "Disparando replicacion tablet -> central..."
curl -s -X POST "$CENTRAL/_replicate" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "http://admin:admin123@couch-tablet:5984/inspecciones",
    "target": "http://admin:admin123@couch-central:5984/inspecciones",
    "create_target": false
  }' | python3 -m json.tool

echo
echo "Verificando documentos en el central:"
curl -s "$CENTRAL/inspecciones/_all_docs" | python3 -m json.tool
