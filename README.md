# vibe-tool-kit

Skills, agentes y hooks genéricos para **Claude Code** y **Codex**, distribuidos como un
marketplace de plugins. Cada plugin cubre un dominio y se instala por separado.

| Plugin | Qué trae | Hooks |
|---|---|---|
| `agent-team` | Protocolo multi-agente (task packets, handoffs) y scaffolding de artefactos con linaje | no |
| `quality-gates` | Gate de calidad por lenguaje (lint, tipos, tests) y validación de SQL antes de ejecutarlo | no |
| `security-review` | Threat modeling, supply chain, gating de releases y un agente de AppSec | no |
| `ui-review` | Filtro contra UI genérica de IA: visual, accesibilidad, móvil, textos y comentarios | no |
| `ui-review-hooks` | Recuerda cargar `ui-review` cuando el prompt pide revisar o construir UI | `UserPromptSubmit` |
| `mcp-guard` | Niega llamadas a servidores MCP HTTP caídos antes de que cuelguen la sesión | `PreToolUse` |
| `diagrams` | Diagramas editables (`.drawio` + `.svg`) desde un spec YAML, con validador | no |

## Instalación

Claude Code:

```bash
claude plugin marketplace add danielhcertuche/vibe-tool-kit
claude plugin install quality-gates@vibe-tool-kit      # repetir por plugin
```

Para fijar una versión exacta (recomendado en equipos), agrega el marketplace en un ref y
usa `sha` en tu propio `marketplace.json`; ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

Codex: los plugins traen `.codex-plugin/plugin.json` y el marketplace está también en
`.agents/plugins/marketplace.json`. Los parámetros se pasan con variables `VIBE_<KEY>`.

## Parámetros

Ningún plugin necesita configuración para funcionar. Los que la aceptan la declaran en
`userConfig` (Claude Code los pregunta al instalar, o `claude plugin install --config`):

| Plugin | KEY | Default | Efecto |
|---|---|---|---|
| `ui-review` | `DESIGN_SYSTEM` | vacío | Design system que manda sobre las reglas genéricas |
| `ui-review-hooks` | `DESIGN_SYSTEM_KEYWORDS` | vacío | Palabras (csv) que también cuentan como "interfaz" |
| `mcp-guard` | `MCP_GUARD_PORTS` | `{}` | JSON `{"mcp__<server>": puerto}`; vacío = no niega nada |
| `mcp-guard` | `MCP_GUARD_START_HINT` | texto genérico | Mensaje cuando el servidor está caído |

## Permisos y red

- Ningún hook sale a internet. `mcp-guard` abre una conexión TCP a `127.0.0.1:<puerto>` (1,5 s
  de timeout) para ver si el servidor escucha; no ejecuta comandos de shell.
- `ui-review-hooks` solo lee el prompt y agrega contexto; nunca bloquea.
- Los hooks viven en plugins aparte para que puedas no instalarlos: Claude Code no permite
  apagar un hook suelto dentro de un plugin.
- Ninguna skill pide credenciales ni lee archivos fuera del proyecto.

## Desarrollo

```bash
scripts/validate_all.sh          # claude plugin validate --strict + paridad Claude/Codex
tests/hooks/test_hooks.sh        # comportamiento de los hooks
tests/smoke/install.sh           # instalación en contenedor con HOME vacío
scripts/check_denylist.sh .      # rutas personales, correos, endpoints y tokens
claude plugin eval plugins/<p> --eval-dir tests/evals/<p> --no-publish --max-cost-usd 5
```

`scripts/kit_ephemeral.sh` corre las herramientas de seguridad (gitleaks, semgrep, bandit,
shellcheck, osv-scanner, syft) en contenedores desechables con límites de CPU y RAM: nada se
instala en la máquina y todo se libera al terminar.

## Licencia

Apache-2.0. Incluye material de terceros bajo MIT; ver [NOTICE](NOTICE).
