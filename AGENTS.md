# Instrucciones para agentes

Lee primero [docs/HANDOFF.md](docs/HANDOFF.md): estado, reglas del repo, cómo probar y pendientes.

- No agregues nombres, hosts, correos ni rutas de una organización concreta; corre `scripts/check_denylist.sh .`.
- Commits sin marca de IA (ni `Co-Authored-By` de un modelo ni «asistido por IA»).
- Todo cambio entra por PR a `main` con los checks en verde; nunca force-push.
- Antes de declarar algo listo, corre las pruebas de `docs/HANDOFF.md` y reporta el resultado real.
