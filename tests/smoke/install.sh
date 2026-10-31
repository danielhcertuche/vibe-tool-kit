#!/usr/bin/env bash
# Smoke de instalación en una máquina limpia: contenedor desechable con HOME vacío y solo la CLI
# `claude` (versión fijada). Agrega este marketplace desde el árbol local, instala cada plugin y
# comprueba que ningún archivo instalado apunta a una ruta de usuario. No necesita credenciales.
#   tests/smoke/install.sh [versión de claude]
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
ver=${1:-2.1.301}
docker run --rm --network bridge --cpus 2 --memory 2g -v "$root:/kit:ro" -e HOME=/home/tester \
  node:22-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da bash -euo pipefail -c '
    useradd -m tester >/dev/null 2>&1 || true
    npm install -g --silent "@anthropic-ai/claude-code@'"$ver"'" >/dev/null 2>&1
    node "$(npm root -g)/@anthropic-ai/claude-code/install.cjs" >/dev/null   # binario nativo
    cp -r /kit /tmp/kit && chown -R tester /tmp/kit
    su tester -s /bin/bash -c "
      set -euo pipefail
      claude --version
      claude plugin marketplace add /tmp/kit
      for p in \$(ls /tmp/kit/plugins); do claude plugin install \$p@vibe-tool-kit; done
      claude plugin list
      if grep -rIhoE \"/home/[a-z0-9_-]+/\" ~/.claude/plugins 2>/dev/null | grep -v \"^/home/tester/\"; then
        echo \"FAIL: ruta de usuario en lo instalado\"; exit 1; fi
      echo SMOKE_OK
    "'
