# Seguridad

Reporta vulnerabilidades por **GitHub Security Advisories** (pestaña *Security → Report a
vulnerability*), no en issues públicos. Respuesta inicial en 5 días hábiles.

Alcance: hooks y scripts de este repo, manifests de plugins y cualquier instrucción de una
skill o agente que pida saltarse permisos, desactivar confirmaciones o leer credenciales.

Recomendación para quien consume el kit: fija cada plugin por `sha` y desactiva el
auto-update del marketplace; actualiza con un PR que revise el diff entre SHAs.
