#!/usr/bin/env bash
# Corre dentro del contenedor de tests/smoke/install.sh. No ejecutar en tu máquina: crea un usuario.
set -euo pipefail
useradd -m tester >/dev/null 2>&1 || true
# El binario nativo llega como dependencia opcional y su descarga a veces falla: se reintenta
# y se verifica con `claude --version` antes de seguir.
for i in 1 2 3; do
  npm install -g --no-fund --no-audit "@anthropic-ai/claude-code@${CLAUDE_VER}" >/tmp/npm.log 2>&1 || true
  node "$(npm root -g)/@anthropic-ai/claude-code/install.cjs" >/dev/null 2>&1 || true
  if claude --version >/dev/null 2>&1; then break; fi
  echo "instalación de claude, intento $i fallido; reintento"; tail -3 /tmp/npm.log; sleep 3
done
claude --version >/dev/null
cp -r /kit /tmp/kit && chown -R tester /tmp/kit

su tester -s /bin/bash <<'AS_TESTER'
set -euo pipefail
cd ~
claude --version
claude plugin marketplace add /tmp/kit
for p in /tmp/kit/plugins/*/; do claude plugin install "$(basename "$p")@vibe-tool-kit"; done
claude plugin list

# Pasos de docs/GUIA-INSTALACION.md
echo '{"DESIGN_SYSTEM":"Material 3"}' | claude plugin configure ui-review@vibe-tool-kit --values-stdin
claude plugin configure ui-review@vibe-tool-kit --json | grep -q 'Material 3'
echo "guía: configurar OK"
claude plugin disable mcp-guard@vibe-tool-kit
claude plugin list | grep -A4 'mcp-guard@vibe-tool-kit' | grep -qi 'disabled'
claude plugin enable mcp-guard@vibe-tool-kit
claude plugin list | grep -A4 'mcp-guard@vibe-tool-kit' | grep -q 'enabled'
echo "guía: pausar y reactivar OK"
claude plugin uninstall diagrams@vibe-tool-kit
if claude plugin list | grep -q 'diagrams@vibe-tool-kit'; then echo "FAIL: diagrams sigue instalado"; exit 1; fi
echo "guía: quitar OK"

if grep -rIhoE '/home/[a-z0-9_-]+/' ~/.claude/plugins 2>/dev/null | grep -v '^/home/tester/'; then
  echo "FAIL: ruta de usuario en lo instalado"; exit 1
fi
echo SMOKE_OK
AS_TESTER
