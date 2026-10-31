"""Protecciones comunes del plugin y diagnóstico para el usuario. Solo stdlib.

Salen de incidentes reales en una instalación de producción: secretos en archivos legibles por otros (644),
tokens incrustados en URLs que terminaron en logs, discos llenos por cachés que nadie limpiaba, datos dentro de
carpetas sincronizadas y una app con permisos de lectura sobre todo el tenant.
"""
import os
import re
import shutil
import sys
import time

DISCO_MIN_GB = 2.5          # venv (~215 MB) + modelo (~1,6 GB) + margen
RETENCION_DIAS = float(os.environ.get("VTK_RETENCION_DIAS", "7"))
SECRETOS_ENV = ("GRAPH_CLIENT_SECRET", "GROQ_API_KEY")
PATRONES = [  # (patrón, reemplazo)
    (re.compile(r"gsk_[A-Za-z0-9]{16,}"), "<oculto>"),                                   # llaves de Groq
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{16,}"), "Bearer <oculto>"),            # Authorization
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "<oculto>"),  # JWT de Entra
    (re.compile(r"(https?://)[^/\s:@]+:[^/\s@]+@"), r"\1<oculto>@"),                    # usuario:token@ en URLs
    (re.compile(r"(?i)\b(sig|client_secret|access_token|refresh_token)=[^&\s\"']+"), r"\1=<oculto>"),
]


def privado():
    """Todo lo que cree el proceso queda solo para su dueño (archivos 600, carpetas 700)."""
    os.umask(0o077)


def limpiar_secretos(texto):
    texto = str(texto)
    for k in SECRETOS_ENV:
        v = os.environ.get(k, "").strip()
        if len(v) >= 8:
            texto = texto.replace(v, f"<{k} oculto>")
    for p, rep in PATRONES:
        texto = p.sub(rep, texto)
    return texto


def espacio_libre_gb(ruta):
    while not os.path.exists(ruta):
        ruta = os.path.dirname(ruta)
    return shutil.disk_usage(ruta).free / 1e9


def purgar(base, dias):
    """Borra lo que tenga más de `dias` días en base/* (caché de transcripciones, candidatos)."""
    n = 0
    if not os.path.isdir(base):
        return 0
    for d in os.listdir(base):
        p = os.path.join(base, d)
        if time.time() - os.path.getmtime(p) > dias * 86400:
            shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
            n += 1
    return n


def _sincronizada(ruta):
    r = os.path.realpath(ruta).lower()
    return any(s in r for s in ("onedrive", "dropbox", "google drive", "icloud"))


def diagnostico(data, salida_tipica=None):
    """Lista de chequeos {chequeo, estado: ok|aviso|error, detalle}. Nunca incluye valores secretos."""
    out = []

    def add(c, e, d):
        out.append({"chequeo": c, "estado": e, "detalle": d})

    v = sys.version_info
    add("python", "ok" if v >= (3, 11) else "error", f"{v.major}.{v.minor} (se necesita 3.11 o más)")
    gb = espacio_libre_gb(data)
    add("espacio en disco", "ok" if gb >= DISCO_MIN_GB else "error",
        f"{gb:.1f} GB libres donde vive el plugin (primer uso necesita {DISCO_MIN_GB} GB)")
    modo = oct(os.stat(data).st_mode & 0o777) if os.path.exists(data) else "no existe aún"
    add("permisos de los datos", "ok" if modo in ("0o700", "no existe aún") else "aviso",
        f"{data}: {modo} (debe ser 0o700: transcripciones solo para ti)")
    for r, nombre in ((data, "datos del plugin"), (salida_tipica, "carpeta de salida")):
        if r and _sincronizada(r):
            add(f"{nombre} en carpeta sincronizada", "aviso",
                f"{r} está dentro de una carpeta que se sube a la nube; las transcripciones saldrían de tu equipo")
    cred = os.path.expanduser("~/.claude/.credentials.json")
    if sys.platform.startswith("linux") and os.path.exists(cred):
        m = os.stat(cred).st_mode & 0o777
        add("almacén de secretos (Linux/WSL)", "ok" if m == 0o600 else "aviso",
            f"~/.claude/.credentials.json con {oct(m)}; corre: chmod 600 ~/.claude/.credentials.json")
    auth = os.environ.get("GRAPH_AUTH", "ninguno") or "ninguno"
    if auth == "aplicacion":
        add("acceso a Graph", "aviso", "modo aplicación: la app lee lo que tenga permitido en todo el tenant; pide a "
            "tu admin limitarla con Sites.Selected a los sitios de grabaciones")
    else:
        add("acceso a Graph", "ok", f"modo {auth}")
    if os.environ.get("GROQ_API_KEY", "").strip():
        add("modo híbrido", "aviso", "llave de Groq configurada: confirma que Zero Data Retention está activo en tu "
            "cuenta (Settings > Data Controls); solo se usa si lo pides por reunión")
    else:
        add("modo híbrido", "ok", "sin llave de Groq: todo se procesa en tu equipo")
    add("retención", "ok", f"caché de transcripciones {RETENCION_DIAS:g} días, candidatos de fotogramas 2 días")
    return out
