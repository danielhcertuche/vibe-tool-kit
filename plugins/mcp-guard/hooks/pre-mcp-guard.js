#!/usr/bin/env node
// PreToolUse hook — guard MCP calls before they hang on dead servers

const net = require('net');

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

  // Chequeo TCP portable (Linux, macOS, Windows) y sin shell: si el puerto acepta
  // conexión el servidor está arriba; si la rechaza o no responde en 1,5 s, se niega.
  const deny = () => {
    const serverName = prefix.replace('mcp__', '');
    process.stdout.write(JSON.stringify({ hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'deny',
      permissionDecisionReason: `MCP server "${serverName}" not running (port ${port} closed). ` + HINT,
    } }));
    process.exit(0);
  };
  const sock = net.connect({ host: '127.0.0.1', port, timeout: 1500 });
  sock.once('connect', () => { sock.destroy(); process.exit(0); });
  sock.once('timeout', () => { sock.destroy(); deny(); });
  sock.once('error', deny);
});
