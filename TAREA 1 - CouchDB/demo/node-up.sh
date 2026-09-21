#!/usr/bin/env bash
# Vuelve a levantar un nodo. La replicacion continua se retoma sola porque
# esta definida en la base _replicator, que es persistente.
set -euo pipefail
cd "$(dirname "$0")"
case "${1:-}" in
  central-a) SVC=couch-central; PORT=5984 ;;
  central-b) SVC=couch-central-b; PORT=5987 ;;
  tablet-a)  SVC=couch-tablet; PORT=5985 ;;
  *) echo "uso: ./node-up.sh central-a|central-b|tablet-a"; exit 1 ;;
esac
docker compose start "$SVC" >/dev/null
echo -n "esperando a $1"
until curl -sf "http://localhost:$PORT/_up" >/dev/null 2>&1; do echo -n "."; sleep 1; done
echo " arriba."
echo "Mira el monitor: en unos segundos deberia volver a converger solo."
