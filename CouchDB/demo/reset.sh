#!/usr/bin/env bash
# Reset completo de la demo, en el orden correcto.
#
# OJO con la tablet B: sus datos viven en el IndexedDB del navegador, no en
# Docker. Si reseteas los contenedores pero dejas la pestaña abierta con
# datos viejos, PouchDB los vuelve a subir al central y aparecen conflictos
# de mas (revisiones raiz duplicadas). Por eso este script te frena hasta
# que hagas el paso del navegador.
set -euo pipefail
cd "$(dirname "$0")"

echo "1/4 · bajando UI y contenedores..."
./stop-ui.sh >/dev/null 2>&1 || true
docker compose down -v >/dev/null 2>&1

echo "2/4 · levantando nodos limpios..."
docker compose up -d >/dev/null 2>&1

echo "3/4 · cargando el escenario..."
./setup.sh >/dev/null 2>&1

echo "4/4 · sirviendo las UI..."
./serve-ui.sh >/dev/null 2>&1
sleep 1

cat <<'TXT'

Contenedores listos. Falta el paso manual de la tablet B:

  1. Abri http://localhost:8083
  2. Boton "reiniciar datos locales" (abajo de todo)

Sin eso, la tablet B todavia tiene en IndexedDB las lecturas de la corrida
anterior y al sincronizar las reenvia, generando conflictos que no son
parte del guion.

  UI Central  -> http://localhost:8081
  UI Tablet A -> http://localhost:8082
  UI Tablet B -> http://localhost:8083
TXT
