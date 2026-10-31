---
name: reunion-a-hu
description: Convierte una grabación de reunión (video o audio local, o enlace de OneDrive/SharePoint) en transcripción, acta con decisiones y pendientes, y borradores de historias de usuario (HU) para Azure Boards. Usar cuando pidan resumir una reunión, sacar el acta, los compromisos o los action items, o pasar lo acordado a HU o al backlog. Nunca crea work items sin aprobación explícita.
---

# Reunión → acta → HU

La transcripción corre en la máquina del usuario (servidor MCP `meeting-to-backlog`). El acta y las HU las
escribes tú leyendo la transcripción. Nada se crea en Azure Boards sin que el usuario apruebe cada HU.

## 1. Antes de procesar

- Confirma la fuente: ruta **absoluta** de un archivo local o enlace compartido de OneDrive/SharePoint.
  Si es un enlace y el acceso a Graph está en `ninguno` (${user_config.GRAPH_AUTH}), pide que descargue el archivo
  o que configure el plugin (`/plugin` → meeting-to-backlog → Configure).
- Pregunta una sola vez si la reunión trata datos personales o confidenciales. Si sí, recuerda que la
  transcripción se procesa en local, pero que al resumirla su texto pasa por este asistente: debe estar permitido
  por la política de datos de su organización.
- Carpeta de salida: dentro del proyecto actual, `docs/reuniones/AAAAMMDD_tema-corto/` (ruta absoluta).

## 2. Transcribir

1. Llama `procesar_reunion` con `fuente`, `salida` y, si el usuario lo pide, `perfil` (`rapido` por defecto,
   `preciso` para audio difícil) e `idioma`.
2. Llama `estado_reunion` cada 30–60 s. Informa la fase en una línea; no repitas el JSON.
   - `instalando`: primera vez, baja dependencias y modelo (unos minutos, una sola vez).
   - `login`: muestra al usuario el `mensaje` (enlace y código para iniciar sesión) tal cual.
   - `error`: muestra el error y el `log`; no reintentes a ciegas.
3. Con `fase=listo`, lee `transcripcion.md` (por tramos si es larga). Cada línea trae `[hh:mm:ss]`.

## 3. Acta

Escribe `acta.md` en la carpeta de salida con `templates/acta.md`. Reglas:
- Cada decisión, pendiente y riesgo lleva su marca `[hh:mm:ss]` de la transcripción. Sin evidencia, no va.
- Responsable y fecha solo si se dijeron; si no, `por definir`. No inventes nombres ni fechas.
- Separa **decisiones** (ya acordado) de **pendientes** (alguien debe hacer algo) y de **preguntas abiertas**.

## 4. Borradores de HU

Por cada pendiente que sea trabajo de producto o de sistema (no tareas administrativas), propone una HU en
`hu.json` (esquema: `templates/hu.schema.json`) y muéstrala al usuario como tabla:

| # | Título | Como / quiero / para | Criterios de aceptación | Evidencia | Confianza |

- La confianza es `alta` solo si en la reunión se describió el qué y el para qué; si falta, `media` o `baja`,
  y escribe qué falta.
- No juntes dos pendientes en una HU ni partas uno en varias sin decirlo.

## 5. Crear en Azure Boards (solo con aprobación)

Pide al usuario que apruebe, edite o descarte **cada** HU. Con las aprobadas:
- Si hay organización configurada (${user_config.AZDO_ORG}, proyecto ${user_config.AZDO_PROJECT}), crea cada una
  con `az boards work-item create --org <org> --project <proyecto> --type "${user_config.AZDO_TIPO}" --title …
  --description …` (y `--area` si hay área), una por una, y anota el id devuelto en `hu.json`.
- Si no hay organización configurada o `az` no tiene sesión, escribe `hu.csv` (Title, Description,
  Acceptance Criteria) para importarlo en Boards y dile cómo.

## 6. Cierre

- Resume: duración, perfil, tiempo de transcripción, HU creadas y sus ids.
- Si el usuario no necesita la transcripción completa, ofrece borrarla y llamar `limpiar_cache`.
