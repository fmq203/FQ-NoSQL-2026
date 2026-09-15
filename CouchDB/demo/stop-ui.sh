#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

for name in central tablet tablet-b monitor presentacion; do
  pidfile=".pids/$name.pid"
  if [ -f "$pidfile" ]; then
    kill "$(cat "$pidfile")" 2>/dev/null || true
    rm -f "$pidfile"
    echo "UI $name detenida."
  fi
done
