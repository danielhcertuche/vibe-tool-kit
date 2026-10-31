# Guía de instalación paso a paso

Esta guía es para ti si nunca has instalado un plugin de Claude Code. Cada paso explica qué copiar,
dónde pegarlo y qué deberías ver. Si algo no sale igual, salta a [Si algo falla](#si-algo-falla).

Tiempo estimado: 10 minutos.

---

## Antes de empezar

Necesitas **Claude Code** instalado y con tu sesión iniciada.

1. Abre una terminal:
   - **Windows:** menú Inicio → escribe `Terminal` → Enter. Si usas WSL, escribe `wsl` y Enter.
   - **macOS:** `Cmd + Espacio` → escribe `Terminal` → Enter.
   - **Linux:** `Ctrl + Alt + T`.
2. Copia esto, pégalo en la terminal y presiona Enter:

   ```
   claude --version
   ```

   ✅ **Deberías ver** un número como `2.1.301 (Claude Code)`.
   ❌ **Si ves** `command not found` o `no se reconoce`: instala Claude Code primero desde
   <https://code.claude.com/docs/en/setup> y vuelve aquí.

> Necesitas la versión **2.1.301 o más nueva**. Si tienes una más vieja, actualiza con `claude update`.

---

## Paso 1 — Agregar el catálogo de plugins

Un "marketplace" es un catálogo: agregarlo no instala nada todavía, solo te deja ver qué hay.

```
claude plugin marketplace add danielhcertuche/vibe-tool-kit
```

✅ **Deberías ver:** `Successfully added marketplace: vibe-tool-kit`.

---

## Paso 2 — Elegir qué instalar

Cada plugin es independiente. Instala solo lo que te sirva:

| Si quieres… | Instala | ¿Agrega automatismos (hooks)? |
|---|---|---|
| Que Claude revise la calidad de tu código antes de darlo por terminado | `quality-gates` | No |
| Revisiones de seguridad de tus cambios | `security-review` | No |
| Que las pantallas que diseña Claude no se vean "hechas por IA" | `ui-review` | No |
| …y que Claude cargue esa revisión solo cuando hablas de pantallas | `ui-review-hooks` | Sí |
| Diagramas editables (drawio) desde una descripción | `diagrams` | No |
| Coordinar trabajos largos entre varios agentes | `agent-team` | No |
| Que Claude no se cuelgue llamando a un servidor MCP que está apagado | `mcp-guard` | Sí |

> **¿Qué es un hook?** Un pequeño programa que Claude ejecuta solo, en ciertos momentos. Los dos de
> este kit no usan internet y no guardan nada. Si prefieres no tenerlos, no instales esos dos plugins.

**Recomendado para empezar:** `quality-gates` y `ui-review`.

---

## Paso 3 — Instalar

Copia una línea por cada plugin que elegiste (Enter después de cada una):

```
claude plugin install quality-gates@vibe-tool-kit
claude plugin install ui-review@vibe-tool-kit
```

✅ **Deberías ver**, por cada uno: `Successfully installed plugin: …@vibe-tool-kit`.

Si Claude te pregunta si **confías** en el plugin, responde que sí: es el aviso normal de cualquier
plugin que no viene de Anthropic.

---

## Paso 4 — Comprobar que quedó instalado

```
claude plugin list
```

✅ **Deberías ver** cada plugin con `Status: ✔ enabled`.

Ahora pruébalo en una conversación. Abre Claude Code en la carpeta de un proyecto
(`cd` a tu carpeta y luego `claude`) y escribe, por ejemplo:

> Revisa la UI de la pantalla de inicio de sesión y dime qué se ve genérico.

✅ **Deberías ver** que Claude carga la skill `antislop` antes de responder (aparece como
"Skill" en la conversación).

---

## Paso 5 (opcional) — Ajustar a tu equipo

Ningún plugin necesita configuración. Solo si tu equipo tiene un sistema de diseño propio o servidores
MCP locales:

**Opción fácil (con menús):** dentro de Claude Code escribe `/plugin`, elige el plugin con las flechas,
entra a **Configure** y llena los campos.

**Opción por terminal:** primero mira qué campos tiene y cuáles están vacíos:

```
claude plugin configure ui-review@vibe-tool-kit
```

Luego guarda un valor (cambia el texto entre comillas por el tuyo):

```
echo '{"DESIGN_SYSTEM":"Material 3"}' | claude plugin configure ui-review@vibe-tool-kit --values-stdin
```

Los campos disponibles son:

| Plugin | Campo | Qué escribir |
|---|---|---|
| `ui-review` | `DESIGN_SYSTEM` | El nombre de tu sistema de diseño (ej. `Material 3`). Vacío = reglas generales |
| `ui-review-hooks` | `DESIGN_SYSTEM_KEYWORDS` | Palabras separadas por coma que nombran ese sistema (ej. `material,mui`) |
| `mcp-guard` | `MCP_GUARD_PORTS` | Pídeselo a quien administra tus MCP. Formato: `{"mcp__nombre": 3100}` |
| `mcp-guard` | `MCP_GUARD_START_HINT` | El mensaje que verás si ese servidor está apagado |

---

## Actualizar, pausar o quitar

| Quiero… | Comando |
|---|---|
| Traer la última versión | `claude plugin marketplace update vibe-tool-kit` y luego `claude plugin update <plugin>@vibe-tool-kit` |
| Pausar un plugin sin borrarlo | `claude plugin disable <plugin>@vibe-tool-kit` |
| Volver a activarlo | `claude plugin enable <plugin>@vibe-tool-kit` |
| Quitarlo | `claude plugin uninstall <plugin>@vibe-tool-kit` |

---

## Si algo falla

| Lo que ves | Qué hacer |
|---|---|
| `command not found: claude` | Claude Code no está instalado o la terminal no lo encuentra. Cierra y abre la terminal; si sigue, reinstala desde la página del paso "Antes de empezar" |
| `Failed to add marketplace` o error de red | Revisa tu conexión. En una red corporativa puede que GitHub esté bloqueado: pregunta a tu área de TI |
| `plugin not found` | Revisa que escribiste `@vibe-tool-kit` al final y que hiciste el Paso 1 |
| El plugin aparece como `disabled` | `claude plugin enable <plugin>@vibe-tool-kit` |
| Claude no carga la skill en la conversación | Reinicia Claude Code (sal con `/exit` y vuelve a entrar). Los plugins se cargan al iniciar |
| `mcp-guard` bloquea un MCP que sí está encendido | Revisa el número de puerto en `MCP_GUARD_PORTS` (Paso 5). Para apagarlo: `claude plugin disable mcp-guard@vibe-tool-kit` |

¿Nada de esto? Abre un issue en <https://github.com/danielhcertuche/vibe-tool-kit/issues> con lo que
copiaste y lo que viste (sin contraseñas ni tokens).

---

## Para Codex

Los plugins traen también su manifest para Codex (`.codex-plugin/`). La configuración se pasa con
variables de entorno con prefijo `VIBE_` (por ejemplo `VIBE_DESIGN_SYSTEM`). El soporte de Codex
**todavía no está probado**; ver [compatibility.md](compatibility.md).
