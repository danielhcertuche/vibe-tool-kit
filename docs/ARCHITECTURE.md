# Arquitectura

## Forma

- Un **marketplace** (`.claude-plugin/marketplace.json`, espejo para Codex en
  `.agents/plugins/marketplace.json`) con un **plugin por dominio** en `plugins/<dominio>/`.
- Cada plugin trae `.claude-plugin/plugin.json` y `.codex-plugin/plugin.json` idénticos;
  `scripts/validate_all.sh` falla si divergen.
- Los hooks viven en plugins propios (`ui-review-hooks`, `mcp-guard`): Claude Code activa o
  apaga los hooks junto con su plugin, no uno por uno.
- Rutas siempre relativas a `${CLAUDE_PLUGIN_ROOT}`; estado persistente, si alguna vez hace
  falta, en `${CLAUDE_PLUGIN_DATA}`.

## Configuración

Todo lo que cambia entre organizaciones entra por `userConfig` (Claude Code) o `VIBE_<KEY>`
(Codex). El repo no contiene valores de ninguna organización; `scripts/check_denylist.sh` lo
verifica en el árbol y en todo el historial.

## Cómo consumirlo desde un repo privado (overlay)

Un repo privado puede publicar su propio marketplace que combine plugins internos con
plugins de este repo, fijados por commit:

```json
{
  "name": "acme-plugins",
  "owner": { "name": "Acme" },
  "plugins": [
    { "name": "quality-gates",
      "source": { "source": "git-subdir", "url": "https://github.com/danielhcertuche/vibe-tool-kit.git",
                  "path": "plugins/quality-gates", "ref": "quality-gates--v0.1.0",
                  "sha": "<40 hex del commit del tag>" } },
    { "name": "acme-rules", "source": "./plugins/acme-rules" }
  ]
}
```

- `sha` manda sobre `ref`: el pin es el commit, el tag es solo legible. Claude Code no
  comprueba que el tag apunte a ese commit; hazlo en tu CI.
- Desactiva el auto-update de ese marketplace y actualiza con un PR que cambie el `sha`.
- Los valores propios (design system, puertos de MCP) se pasan con
  `claude plugin install <p>@<mkt> --config KEY=valor` o `claude plugin configure`.

## Versionado

Semver por plugin, con tags `<plugin>--vX.Y.Z` (convención de `claude plugin tag`) y un tag
de repo `vX.Y.Z` por release agregado con SBOM (syft) adjunto. Ver `CHANGELOG.md` y
`docs/compatibility.md`.
