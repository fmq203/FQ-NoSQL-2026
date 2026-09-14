#!/usr/bin/env bash
# Sirve las dos UI estaticas (no necesitan build, son HTML+JS planos que
# hablan directo con la API HTTP de cada nodo CouchDB via fetch).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p .pids

nohup python3 -m http.server 8081 --directory ui/central >/tmp/ose-ui-central.log 2>&1 &
echo $! > .pids/central.pid

nohup python3 -m http.server 8082 --directory ui/tablet >/tmp/ose-ui-tablet.log 2>&1 &
echo $! > .pids/tablet.pid

sleep 1
echo "UI Central -> http://localhost:8081"
echo "UI Tablet  -> http://localhost:8082"
echo "(para bajarlas: ./stop-ui.sh)"
