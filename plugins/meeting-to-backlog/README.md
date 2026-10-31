# meeting-to-backlog

Grabación de reunión → transcripción **en tu máquina** → acta con decisiones y pendientes → 4 fotogramas clave →
borradores de HU
→ Azure Boards **solo con tu aprobación**. No necesita licencias de Teams Premium ni de Copilot.

Uso: `/acta /ruta/absoluta/reunion.mp4` o pídele a Claude "saca el acta y las HU de esta reunión".

## Qué instala y qué consume

| Recurso | Cuándo | Tamaño |
|---|---|---|
| Entorno de Python (faster-whisper, Pillow) en `${CLAUDE_PLUGIN_DATA}/venv` | primer uso | ~215 MB |
| Modelo `large-v3-turbo` (CTranslate2, int8) | primer uso | ~1,6 GB |
| CPU y RAM | solo mientras transcribe | ver `docs/` del repo |

Requisitos: `python3` ≥ 3.11 en el PATH (si hay `uv`, la instalación es más rápida). No usa GPU ni ffmpeg.

## Datos y red

- La grabación descargada y todo intermedio viven en una carpeta temporal que se borra al terminar, también si
  falla. El audio se decodifica en memoria. Queda solo lo que sirve: `transcripcion.md`, `acta.md`, `hu.json` y **4 fotogramas clave** con
  `fotogramas.md`, elegidos según la transcripción, las decisiones y las HU (siempre que haya video).
- La transcripción se cachea por huella (SHA-256) del archivo para no repetir trabajo. Los fotogramas candidatos
  (decenas de JPEG pequeños, ~4 MB por hora) viven hasta que se eligen los 4 o 2 días; `limpiar_cache` borra todo.
- Red: Hugging Face (modelo, primer uso), PyPI (dependencias, primer uso), Microsoft Graph (solo si usas
  enlaces) y Groq (solo en modo híbrido). Al escribir el acta, el texto de la transcripción pasa por el asistente: úsalo solo si la política de
  datos de tu organización lo permite.

## Modo híbrido (opcional)

`procesar_reunion` con `nube_pct` (0 a 0,3) manda el **tramo final** de la reunión a Groq mientras el resto se
transcribe en local, al mismo tiempo. Pocos cortes y en silencios, porque cada corte pierde palabras.
Estimado para 1 h: ~22 min solo local → ~15 min con 30 % en la nube (la RAM local no baja: el modelo se carga
igual). Controles:
- Solo si se pide para esa reunión y hay `GROQ_API_KEY`. Activa **Zero Data Retention** en tu cuenta de Groq.
- Sale FLAC con nombre fijo, sin metadatos ni prompt.
- **Nunca más del 30 % ni de lo que deja la cuota gratuita de Groq** (7.200 s de audio por hora, 28.800 por día,
  2.000 peticiones por día; se usa solo el 80 % y se cobra el mínimo de 10 s por petición). Si no alcanza, manda
  menos; si no queda cupo, todo local. `NUBE_MES_MIN` agrega un presupuesto mensual. El estado del job dice cuánto
  se permitió y por qué. Groq no informa la cuota de audio, así que se cuenta en local: usa una llave por persona.
- 429/5xx: reintenta respetando `retry-after`; si sigue fallando, ese tramo vuelve a local.
- `registro_nube.jsonl` en `${CLAUDE_PLUGIN_DATA}` dice qué salió (huella, desplazamiento, código HTTP), nunca
  audio ni texto.

## Configuración (`/plugin` → meeting-to-backlog → Configure)

| Campo | Para qué |
|---|---|
| `PERFIL` | `rapido` (por defecto) o `preciso` |
| `IDIOMA` | `es` por defecto; `auto` detecta |
| `GRAPH_AUTH` | `ninguno` (solo archivos locales), `delegado` (cada persona inicia sesión con su cuenta) o `aplicacion` |
| `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID` | Datos de la app de tu organización (no son secretos) |
| `GRAPH_CLIENT_SECRET` | Solo modo `aplicacion`. Se guarda en el almacén seguro del sistema (Keychain en macOS; en Linux/WSL, `~/.claude/.credentials.json`, que debe tener permisos 600). Nunca lo pongas en un archivo del proyecto |
| `AZDO_ORG`, `AZDO_PROJECT`, `AZDO_AREA`, `AZDO_TIPO` | Dónde crear las HU aprobadas; vacío = exportar CSV |
| `GROQ_API_KEY` | Opcional, modo híbrido. Almacén seguro del sistema |
| `NUBE_MES_MIN` | Opcional: minutos de audio al mes que pueden ir a la nube |

**Modo `aplicacion`:** la credencial lee lo que su app tenga permitido en todo el tenant. Pide a tu administrador
que la limite con `Sites.Selected` a los sitios donde se guardan las grabaciones, y entrégala por un canal seguro
(un Key Vault con acceso por rol, no un chat ni un correo).
