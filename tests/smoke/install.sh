#!/usr/bin/env bash
# Smoke de instalación en una máquina limpia: contenedor desechable con HOME vacío y solo la CLI
# `claude` (versión fijada). Agrega este marketplace desde el árbol local, instala cada plugin,
# sigue los pasos de docs/GUIA-INSTALACION.md y comprueba que nada instalado apunta a una ruta de
# usuario. No necesita credenciales.
#   tests/smoke/install.sh [versión de claude]
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
ver=${1:-2.1.301}
log=$(mktemp)
trap 'rm -f "$log"' EXIT

docker run --rm --network bridge --cpus 2 --memory 2g -v "$root:/kit:ro" -e CLAUDE_VER="$ver" \
  node:22-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da \
  bash -euo pipefail /kit/tests/smoke/inner.sh 2>&1 | tee "$log"

# El resultado lo decide el marcador final, no el código de docker: un script cortado a mitad
# (comillas, señal) no puede pasar por éxito.
grep -qx 'SMOKE_OK' "$log" || { echo "FAIL: el smoke no llegó al final"; exit 1; }
