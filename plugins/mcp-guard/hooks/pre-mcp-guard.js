#!/usr/bin/env node
// PreToolUse hook — guard MCP calls before they hang on dead servers

const { execSync } = require('child_process');

let input = '';
process.stdin.on('data', c => { input += c; });
process.stdin.on('end', () => {
  let data;
  try { data = JSON.parse(input); } catch { process.exit(0); }

  const tool = data.tool_name || '';

  // Mapa prefijo de tool MCP -> puerto, solo para servidores que escuchan en TCP
  // (los stdio no abren puerto y el chequeo los bloquearía siempre). Sale de la
  // configuración del plugin (MCP_GUARD_PORTS); vacío = no bloquea nada.
  let MCP_PORTS = {};
  try {
    MCP_PORTS = JSON.parse(process.env.CLAUDE_PLUGIN_OPTION_MCP_GUARD_PORTS ||
                           process.env.VIBE_MCP_GUARD_PORTS || '{}');
  } catch { process.exit(0); }
  const HINT = process.env.CLAUDE_PLUGIN_OPTION_MCP_GUARD_START_HINT ||
               process.env.VIBE_MCP_GUARD_START_HINT || 'Arranca el servidor MCP y reintenta.';

  const prefix = Object.keys(MCP_PORTS).find(p => tool.startsWith(p));
  if (!prefix) process.exit(0); // tool sin puerto configurado: se deja pasar

  const port = MCP_PORTS[prefix];
  if (!Number.isInteger(port) || port < 1 || port > 65535) process.exit(0);

  // Fast TCP check: ss -tnlp | grep :<port>
  try {
    execSync(`ss -tnlp 2>/dev/null | grep -q ':${port} '`, { timeout: 2000 });
    // Port is open → server running → allow
    process.exit(0);
  } catch {
    // Port not open — server likely down
    const serverName = prefix.replace('mcp__', '');
    const msg = JSON.stringify({ hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'deny',
      permissionDecisionReason: `MCP server "${serverName}" not running (port ${port} closed). ` +
              HINT
    } });
    process.stdout.write(msg);
    process.exit(0);
  }
});
