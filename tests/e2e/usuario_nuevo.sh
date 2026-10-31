#!/usr/bin/env bash
# Usuario nuevo, completamente aislado: contenedor Debian mínimo, HOME vacío, Python y Claude Code instalados
# como lo haría una persona, el plugin meeting-to-backlog instalado con `claude plugin install` y probado desde
# la copia instalada (dependencias y modelo desde cero). Solo audio público y video sintético.
# Pesado (~2 GB de descargas): pensado para el CI, no para máquinas con poco disco.
#   tests/e2e/usuario_nuevo.sh [versión de claude]
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
log=$(mktemp); trap 'rm -f "$log"' EXIT
docker run --rm --network bridge --cpus 4 --memory 8g -v "$root:/kit:ro" -e CLAUDE_VER="${1:-2.1.301}" \
  node:22-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da \
  bash -euo pipefail /kit/tests/e2e/usuario_nuevo_dentro.sh 2>&1 | tee "$log"
grep -qx 'USUARIO_NUEVO_OK' "$log" || { echo "FAIL: la prueba de usuario nuevo no llegó al final"; exit 1; }
