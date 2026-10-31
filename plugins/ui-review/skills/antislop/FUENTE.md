# Procedencia — skills `antislop*`

| | |
|---|---|
| Origen | https://github.com/miqdadbadjuber/anti-slop — carpetas `skills/antislop*/` |
| Autor / licencia | miqdadbadjuber · MIT (copia en `LICENSE` de cada carpeta) |
| Versión / commit fijado | 3.2.20 · `388cbe3b6c37d5175b9f460015bb092ef9e34894` (2026-10-05) |
| Hash de carpeta (git tree) | antislop `e756d30` · ui `d2fb2ee` · human `4163260` · layoutmobile `99afc77` · copywriting `3668009` · code `cb31602` |
| Instalada | 2026-10-09, con `git clone --depth 1` y copia de archivos — **sin `npx antislop-ai`, sin plugin, sin MCP** |

Cada `SKILL.md` = frontmatter propio (disparadores en español, `allowed-tools` recortado) + nota
de integración local + marcador `ANTISLOP_UPSTREAM_START` + cuerpo **idéntico al upstream**.
Se instalaron solo `SKILL.md`, `VERSION`, `LICENSE` y `antislop-human/contrast-check.py`.

## Revisión de seguridad (2026-10-09)

- **Sin código malicioso.** `contrast-check.py` y `contrast-mcp.py` solo importan `os/re/sys/json`,
  sin red ni `exec`. El lanzador MCP del plugin (`.claude-plugin/contrast-mcp-launcher.mjs`)
  arranca un proceso Python en cada sesión: no se instaló porque no hace falta.
- **Texto de las skills** leído completo: sin unicode oculto, base64, exfiltración, lectura de
  secretos ni descargas por parte del agente. El core prohíbe explícitamente que el agente baje skills.
- **Riesgos de comportamiento neutralizados por la integración local:**
  - Asistente de primera ejecución que pide aprobación y escribe un bloque en `CLAUDE.md`/`AGENTS.md`
    del repo → se salta.
  - Pregunta de modo en cada sesión ("End the response after asking") → modo por tipo de tarea +
    `~/.config/antislop/settings.json` = `{"mode":"after"}`.
  - Informes `anti-slop/audit-*.md` dentro del repo → en la respuesta; archivo solo en ruta ignorada.
  - `allowed-tools: Bash(python *) Bash(python3 *)` (cualquier Python sin permiso) y `Write/Edit`
    preaprobados → recortado a `Read Glob Grep` + solo `contrast-check.py`.
  - Reglas duras que chocan con el design system del proyecto (R-21 toggle claro/oscuro, R-29 paleta, R-11 pills,
    diales de la Parte 3) → el design system del proyecto manda.
- **No auditado** (no se usa): el paquete npm `antislop-ai` (`cli/`), sus dependencias y los
  manifiestos de otros IDE.

## Activación automática

1. Descripciones de las skills con disparadores de revisión de frontend/UI/UX.
2. Hook `UserPromptSubmit` → `~/.claude/hooks/antislop-ui-review.py` (verbo de revisión +
   término de interfaz ⇒ inyecta la instrucción de cargar las skills; nunca bloquea).
3. `~/.agents/CORE.md` §9.

## Actualizar

```bash
D=$(mktemp -d) && git clone --depth 1 https://github.com/miqdadbadjuber/anti-slop "$D/repo"
for s in antislop antislop-ui antislop-human antislop-layoutmobile antislop-copywriting antislop-code; do
  diff <(sed -n '/ANTISLOP_UPSTREAM_START/,$p' ~/.agents/skills/$s/SKILL.md | tail -n +3) \
       <(awk 'BEGIN{n=0} /^---$/ && n<2 {n++; next} n>=2' "$D/repo/skills/$s/SKILL.md")
done
# revisar el diff (sobre todo instrucciones nuevas de red, escritura o ejecución) antes de aceptar;
# si se acepta: reemplazar solo el cuerpo bajo el marcador, refrescar contrast-check.py y VERSION,
# y anotar el commit aquí, en el frontmatter y en ~/.agents/.skill-lock.json
```

**Ampliación local del 2026-10-11** (solo en la sección «Integración local» del núcleo; el cuerpo
upstream no cambió): puntos 7 (fuentes de componentes prohibidas), 8 (señales de diseño generado,
resumidas de `anthropics/skills/skills/frontend-design/SKILL.md`, Apache-2.0, commit
`dbd4588f9e1033efb41dad4bef2f7947c8993d44`, con la excepción local del rótulo del design system local) y 9
(cargar `web-interface-guidelines`).
