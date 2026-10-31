#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hook UserPromptSubmit del plugin ui-review-hooks (vibe-tool-kit).

Dispara cuando el prompt cruza REVISION x INTERFAZ, solo sobre lo que escribio la persona:
  - silencio en mensajes no humanos: <task-notification>, <agent-message>, "Another Claude session
    sent a message", [SYSTEM NOTIFICATION, <cross-session-message>, /loop programado, resumen de
    continuacion de sesion;
  - quita los bloques de contexto automatico del IDE (<ide_opened_file>, <ide_selection>);
  - silencio si el mensaje es texto pegado largo sin pedido tecleado (>1500 chars y <12 tecleados).
Nunca bloquea: ante cualquier error sale 0 sin salida.
"""
import json
import os
import re
import sys

REVISION = re.compile(
    r"\b(revis\w*|review\w*|audit\w*|evalu\w*|eval[uú]\w*|critic\w*|cr[ií]tic\w*|"
    r"feedback|qa|code-review|valid\w*|mejor\w*|pul\w*|analiz\w*)\b",
    re.IGNORECASE,
)
INTERFAZ = re.compile(
    r"\b(front-?end|front|ui|ux|ui/ux|interfa(z|ces)|pantallas?|vistas?|componentes?|"
    r"experiencia de usuario|usabilidad|accesibilidad|a11y|responsive|m[oó]vil|layout|"
    r"landing|dise[nñ]o visual|design system|css|tailwind|tsx|jsx|react)\b",
    re.IGNORECASE,
)


# Palabras del design system propio (DESIGN_SYSTEM_KEYWORDS, csv): también cuentan como interfaz.
_EXTRA = [k.strip() for k in (os.environ.get("CLAUDE_PLUGIN_OPTION_DESIGN_SYSTEM_KEYWORDS")
                              or os.environ.get("VIBE_DESIGN_SYSTEM_KEYWORDS") or "").split(",") if k.strip()]
EXTRA = re.compile(r"\b(" + "|".join(map(re.escape, _EXTRA)) + r")\b", re.IGNORECASE) if _EXTRA else None

NO_HUMANO = re.compile(
    r"^\s*(<task-notification|<agent-message|<cross-session-message|\[SYSTEM NOTIFICATION|"
    r"Another Claude session sent a message|<command-message>loop</command-message>|"
    r"This session is being continued from a previous conversation)",
    re.IGNORECASE,
)
IDE = re.compile(r"<ide_(opened_file|selection)>.*?</ide_(opened_file|selection)>", re.S)
PEGADO = re.compile(r"<pasted_content[^>]*>.*?</pasted_content[^>]*>", re.S)

CONTEXTO = (
    "antislop: el prompt pide una revisión de frontend/UI/UX. Antes de revisar, cargar "
    "la skill `antislop` (núcleo) y aplicar su sección «Integración local» (modo `after` "
    "sin preguntar, sin asistente de instalación, el design system del proyecto manda); "
    "luego `antislop-ui`, `antislop-human` y, si hay pantallas que deben funcionar en "
    "varios anchos, `antislop-layoutmobile` (y `antislop-copywriting` si se revisan "
    "textos)."
)


def texto_humano(prompt):
    """Texto a evaluar, o None si el mensaje no es de la persona."""
    if NO_HUMANO.search(prompt):
        return None
    sin_ide = IDE.sub(" ", prompt)
    tecleado = PEGADO.sub(" ", sin_ide).strip()
    if len(prompt) > 1500 and len(tecleado) < 12:
        return None
    return sin_ide


def encaja(texto):
    return bool(REVISION.search(texto) and (INTERFAZ.search(texto) or (EXTRA and EXTRA.search(texto))))


def main():
    try:
        prompt = json.load(sys.stdin).get("prompt") or ""
        texto = texto_humano(prompt)
        if texto is not None and encaja(texto):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                     "additionalContext": CONTEXTO}}, ensure_ascii=False))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
