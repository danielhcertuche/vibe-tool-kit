# Estado del proyecto y cómo seguir (para personas y agentes)

Última actualización: 2026-10-31. Si eres un agente (Claude Code, Codex, Copilot u otro), lee esto antes de cambiar nada.

## Qué es

Marketplace de plugins para Claude Code (y manifests para Codex) con 8 plugins por dominio en `plugins/`. Cada
plugin se publica con un tag `<plugin>--vX.Y.Z`; los consumidores lo fijan por `sha`.

| Plugin | Estado |
|---|---|
| agent-team, quality-gates, security-review, ui-review, ui-review-hooks, mcp-guard, diagrams | v0.1.0 |
| meeting-to-backlog | v0.1.0 — servidor MCP local: reunión → transcripción → acta → 4 fotogramas → borradores de HU |

## Reglas del repo (no negociables)

- **Nada de una organización concreta**: ni nombres, ni hosts, ni correos, ni rutas personales. `scripts/check_denylist.sh`
  y el CI lo verifican en el árbol y en todo el historial.
- **Commits sin marca de IA**: ni `Co-Authored-By` de un modelo ni «asistido por IA». Autor: el dueño (correo noreply).
- `main` está protegida: todo entra por PR con 6 checks obligatorios (`validate`, `denylist`, `security`, `smoke`,
  `e2e-reuniones`, `e2e-usuario-nuevo`), historia lineal, sin force-push.
- Dependencias de meeting-to-backlog: se editan en `requirements.in`; `requirements.txt` es el árbol completo resuelto
  para Python 3.11 (verificar que también resuelve en 3.12 y 3.13). Modelo fijado a un commit de Hugging Face.
- Secretos solo por `userConfig` sensible; nunca en archivos. Ver `SECURITY.md`.

## Cómo probar

```bash
scripts/validate_all.sh                 # claude plugin validate --strict + paridad Claude/Codex
for t in tests/unit/test_*.py; do python3 "$t"; done
tests/hooks/test_hooks.sh
tests/e2e/meeting_to_backlog.py <audio-o-video> [--venv-existente RUTA]   # e2e por MCP
tests/e2e/meeting_hybrid.py <audio ≥ 2 min>                               # híbrido contra Groq falso
tests/e2e/usuario_nuevo.sh              # usuario nuevo aislado (Docker, ~2 GB; mejor en CI)
scripts/check_denylist.sh .
```

## Pendientes

1. Secreto `VIBE_DENYLIST_B64` en el repo (lista privada del mantenedor); sin él, el CI usa solo la lista genérica.
2. Tags firmados (falta una clave de firma registrada en GitHub).
3. Codex: los manifests existen pero no se han probado en Codex.
4. meeting-to-backlog: bundle `.mcpb` para Claude Desktop; vocabulario propio (`hotwords`) para nombres; evals con
   modelo (`.github/workflows/evals.yml`, manual, con `--no-publish` y tope de gasto).
5. Calidad en reuniones reales: verdad de terreno humana y piloto con aceptación de HU.
