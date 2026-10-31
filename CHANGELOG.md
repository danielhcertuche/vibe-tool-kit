# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones semver por plugin.

## [0.1.0] — sin publicar

### Añadido
- Plugins `agent-team`, `quality-gates`, `security-review`, `ui-review`, `ui-review-hooks`,
  `mcp-guard` y `diagrams`, con manifests para Claude Code y Codex.
- `mcp-guard`: puertos y mensaje por `userConfig`; responde con `permissionDecision: deny`;
  chequeo TCP portable con `net` (sin `ss` ni shell); ignora puertos no enteros.
- `diagrams`: rechaza `.drawio` con DOCTYPE/ENTITY antes de parsear.
- `ui-review-hooks`: palabras extra del design system por `userConfig`.
- CI: validate, denylist, gitleaks, semgrep, bandit, shellcheck, osv-scanner, smoke de
  instalación y pruebas de hooks.
