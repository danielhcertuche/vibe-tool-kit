---
name: team-security-review-positivo
plugins: [security-review]
max_turns: 4
allowed_tools: [Read, Glob, Grep, Skill]
---

Revisa la seguridad de este cambio antes del merge: el endpoint /export ahora acepta un parámetro path del usuario.
