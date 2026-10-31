#!/usr/bin/env bash
# Pruebas de comportamiento de los hooks publicados. Sin red ni dependencias aparte de node y python3.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
G=plugins/mcp-guard/hooks/pre-mcp-guard.js
H=plugins/ui-review-hooks/hooks/antislop-ui-review.py
IN='{"tool_name":"mcp__demo__x"}'
pass=0 fail=0

# check "nombre" <comando...>: pasa si el comando sale 0.
check() {
  local name=$1; shift
  if "$@"; then pass=$((pass+1)); echo "ok   $name"; else fail=$((fail+1)); echo "FAIL $name"; fi
}
empty() { [ -z "$1" ]; }
has() { grep -q -- "$2" <<<"$1"; }
silent_ok() { [ "$1" -eq 0 ] && [ -z "$2" ]; }

out=$(echo "$IN" | node $G)
check "guard sin configuración no bloquea" empty "$out"

out=$(echo "$IN" | CLAUDE_PLUGIN_OPTION_MCP_GUARD_PORTS='{"mcp__demo":65001}' node $G)
check "guard niega con puerto cerrado" has "$out" '"permissionDecision":"deny"'

python3 -m http.server 65002 --bind 127.0.0.1 >/dev/null 2>&1 & srv=$!
for _ in 1 2 3 4 5 6 7 8 9 10; do (exec 3<>/dev/tcp/127.0.0.1/65002) 2>/dev/null && break; sleep 0.2; done
out=$(echo "$IN" | CLAUDE_PLUGIN_OPTION_MCP_GUARD_PORTS='{"mcp__demo":65002}' node $G)
kill "$srv" 2>/dev/null
check "guard deja pasar con el puerto abierto" empty "$out"

out=$(echo "$IN" | VIBE_MCP_GUARD_PORTS='{"mcp__demo":65001}' VIBE_MCP_GUARD_START_HINT='usa make up' node $G)
check "guard lee VIBE_* (Codex) y la sugerencia" has "$out" 'usa make up'

marker=$(mktemp -u)
out=$(echo "$IN" | CLAUDE_PLUGIN_OPTION_MCP_GUARD_PORTS="{\"mcp__demo\":\"1; touch $marker\"}" node $G)
check "guard ignora puertos no enteros" empty "$out"
check "guard no ejecuta lo inyectado en el puerto" test ! -e "$marker"

out=$(echo "$IN" | CLAUDE_PLUGIN_OPTION_MCP_GUARD_PORTS='{roto' node $G); rc=$?
check "guard con JSON inválido sale 0 sin salida" silent_ok "$rc" "$out"

out=$(echo '{"prompt":"revisa la pantalla de login"}' | python3 $H)
check "ui-review dispara en revisión de UI" has "$out" additionalContext

out=$(echo '{"prompt":"revisa acmekit"}' | python3 $H)
check "ui-review no dispara sin palabra de interfaz" empty "$out"

out=$(echo '{"prompt":"revisa acmekit"}' | CLAUDE_PLUGIN_OPTION_DESIGN_SYSTEM_KEYWORDS=acmekit python3 $H)
check "ui-review usa DESIGN_SYSTEM_KEYWORDS" has "$out" additionalContext

out=$(echo '{"prompt":"[SYSTEM NOTIFICATION revisa la ui"}' | python3 $H)
check "ui-review calla en mensajes no humanos" empty "$out"

out=$(echo 'no es json' | python3 $H); rc=$?
check "ui-review nunca falla" silent_ok "$rc" "$out"

echo "pasan $pass, fallan $fail"
[ "$fail" -eq 0 ]
