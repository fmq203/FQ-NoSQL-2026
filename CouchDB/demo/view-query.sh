#!/usr/bin/env bash
# Consulta la vista MapReduce "por_zona" ya replicada en el central,
# agrupando y mostrando estadisticas (_stats) por zona.
set -euo pipefail
CENTRAL="http://admin:admin123@localhost:5984"

curl -s "$CENTRAL/inspecciones/_design/lecturas/_view/por_zona?group=true" | python3 -m json.tool
