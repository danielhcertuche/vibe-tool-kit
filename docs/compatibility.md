# Compatibilidad

| vibe-tool-kit | Claude Code probado | Codex probado | Notas |
|---|---|---|---|
| 0.1.0 | 2.1.301 | sin probar (manifests según la doc de Codex 0.118.0) | `plugin validate --strict` limpio; smoke en contenedor con `HOME` vacío |

El CI fija la versión de `claude` (`CLAUDE_CODE_VERSION` en `.github/workflows/ci.yml`).
Subirla es un PR que también actualiza esta tabla.
