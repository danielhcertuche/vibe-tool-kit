# Seguridad

Reporta vulnerabilidades por **GitHub Security Advisories** (pestaña *Security → Report a vulnerability*), no en
issues públicos. Respuesta inicial en 5 días hábiles.

Alcance: hooks, servidores MCP y scripts de este repo, manifests de plugins y cualquier instrucción de una skill o
agente que pida saltarse permisos, desactivar confirmaciones o leer credenciales.

## Para quien consume el kit

- Fija cada plugin por `sha` y desactiva el auto-update del marketplace; actualiza con un PR que revise el diff.
- Instala solo los plugins que uses; los hooks viven en plugins aparte para que puedas no instalarlos.

## meeting-to-backlog: datos, secretos y red

| Riesgo | Protección |
|---|---|
| Transcripciones y caché legibles por otros usuarios | `umask 077`: archivos 600, carpetas 700; el servidor fuerza 700 en su carpeta de datos |
| Secretos en archivos del proyecto o en el historial del editor | Los secretos van en `userConfig` sensible (Keychain en macOS; en Linux/WSL `~/.claude/.credentials.json`, que debe ser 600). Nunca edites secretos en archivos de texto: los editores guardan copias en su historial local |
| Tokens incrustados en URLs que terminan en logs | Errores y estado pasan por un filtro que oculta llaves `gsk_`, `Bearer`, JWT, `usuario:token@` y firmas `sig=`, además del valor exacto de cada secreto configurado |
| URL alterada (`file://`, http sin cifrar) | Solo https (http únicamente a 127.0.0.1 para pruebas) |
| El token viaja a otro host en una redirección | Groq no sigue redirecciones; Graph las sigue solo hacia https y sin `Authorization` si cambia el host |
| Cambio silencioso de dependencias o del modelo | Árbol completo de dependencias fijado (`requirements.txt`), modelo fijado a un commit de Hugging Face, Dependabot y osv-scanner |
| App de Graph con permisos de aplicación sobre todo el tenant | Preferir modo `delegado`; si usas `aplicacion`, pide a tu admin `Sites.Selected` y entrega el secreto por un Key Vault, no por chat ni correo |
| Datos dentro de carpetas sincronizadas (OneDrive, Dropbox…) | El tool `diagnostico` lo advierte: las transcripciones saldrían de tu equipo |
| Disco lleno en la primera descarga (~1,8 GB) | Se comprueba el espacio antes de instalar o bajar el modelo |
| Retención indefinida | Transcripciones cacheadas 7 días (`VTK_RETENCION_DIAS`), candidatos de fotogramas 2 días, `limpiar_cache` |
| Modo híbrido (parte del audio a Groq) | Solo si se pide por reunión; como mucho 30 % y dentro de la cuota gratuita; audio sin metadatos ni nombre; activa Zero Data Retention en tu cuenta; registro local sin audio ni texto |

Antes de procesar reuniones con datos personales, confirma que la política de tu organización permite que el texto
de la transcripción pase por el asistente al escribir el acta.
