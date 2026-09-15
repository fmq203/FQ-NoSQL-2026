#!/usr/bin/env bash
# Baja un nodo para mostrar que el sistema sigue andando.
#   ./node-down.sh central-a   |   ./node-down.sh central-b   |   ./node-down.sh tablet-a
set -euo pipefail
cd "$(dirname "$0")"
case "${1:-}" in
  central-a) SVC=couch-central ;;
  central-b) SVC=couch-central-b ;;
  tablet-a)  SVC=couch-tablet ;;
  *) echo "uso: ./node-down.sh central-a|central-b|tablet-a"; exit 1 ;;
esac
docker compose stop "$SVC" >/dev/null
echo "$1 detenido. El monitor (http://localhost:8084) deberia marcarlo caido."
echo "Para volver a levantarlo: ./node-up.sh $1"
