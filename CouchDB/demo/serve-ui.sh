#!/usr/bin/env bash
# Sirve las UI estaticas y la presentacion (no necesitan build, son HTML+JS planos que
# hablan directo con la API HTTP de cada nodo CouchDB via fetch).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p .pids

nohup python3 -m http.server 8081 --directory ui/central >/tmp/ose-ui-central.log 2>&1 &
echo $! > .pids/central.pid

nohup python3 -m http.server 8082 --directory ui/tablet >/tmp/ose-ui-tablet.log 2>&1 &
echo $! > .pids/tablet.pid

nohup python3 -m http.server 8083 --directory ui/tablet-b >/tmp/ose-ui-tablet-b.log 2>&1 &
echo $! > .pids/tablet-b.pid

nohup python3 -m http.server 8084 --directory ui/monitor >/tmp/ose-ui-monitor.log 2>&1 &
echo $! > .pids/monitor.pid

# La presentacion vive un nivel mas arriba; el archivo ya declara
# <meta charset="utf-8">, asi que no hace falta nada especial.
nohup python3 -m http.server 8080 --directory .. >/tmp/ose-presentacion.log 2>&1 &
echo $! > .pids/presentacion.pid

sleep 1
echo "UI Central   -> http://localhost:8081"
echo "UI Tablet A  -> http://localhost:8082"
echo "UI Tablet B  -> http://localhost:8083"
echo "Monitor      -> http://localhost:8084"
echo "Presentación -> http://localhost:8080/presentacion-couchdb.html"
echo "(para bajarlas: ./stop-ui.sh)"
