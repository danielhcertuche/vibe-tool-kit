#!/usr/bin/env bash
# Corre dentro del contenedor de usuario_nuevo.sh. No ejecutar en tu máquina: instala paquetes y crea un usuario.
set -euo pipefail
apt-get update -qq >/dev/null && apt-get install -y -qq --no-install-recommends python3 python3-venv ffmpeg ca-certificates >/dev/null
python3 -c 'import sys; assert sys.version_info >= (3, 11), sys.version; print("python", sys.version.split()[0])'
for _ in 1 2 3; do
  npm install -g --no-fund --no-audit "@anthropic-ai/claude-code@${CLAUDE_VER}" >/tmp/npm.log 2>&1 || true
  node "$(npm root -g)/@anthropic-ai/claude-code/install.cjs" >/dev/null 2>&1 || true
  claude --version >/dev/null 2>&1 && break; sleep 3
done
claude --version
useradd -m nuevo >/dev/null 2>&1
cp -r /kit /tmp/kit && chown -R nuevo /tmp/kit

su nuevo -s /bin/bash -c 'bash /tmp/kit/tests/e2e/usuario_nuevo_pasos.sh' </dev/null
