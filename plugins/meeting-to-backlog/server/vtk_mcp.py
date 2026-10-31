#!/usr/bin/env python3
"""Servidor MCP (stdio, solo stdlib) del plugin meeting-to-backlog.

Tools:
  procesar_reunion(fuente, salida?, perfil?, idioma?)  lanza un job en segundo plano
  estado_reunion(job)                                   fase, progreso, rutas y métricas
  limpiar_cache()                                       borra caché de transcripciones y temporales

El primer job crea el entorno de Python en VTK_DATA/venv (faster-whisper) y baja el modelo
(~1,6 GB, una sola vez). Las credenciales de Graph llegan por el entorno que Claude Code arma
desde userConfig; este proceso no las escribe en ningún lado.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.setdefault("VTK_DATA", os.path.expanduser("~/.cache/meeting-to-backlog"))
os.makedirs(DATA, exist_ok=True)

TOOLS = [
    {"name": "procesar_reunion",
     "description": "Transcribe una grabación de reunión (archivo local o enlace de OneDrive/SharePoint) en "
                    "segundo plano. Devuelve un id de job; consulta estado_reunion hasta fase=listo.",
     "inputSchema": {"type": "object", "required": ["fuente"], "properties": {
         "fuente": {"type": "string", "description": "Ruta local absoluta o enlace compartido de la grabación"},
         "salida": {"type": "string", "description": "Carpeta absoluta para los entregables (por defecto, una "
                                                     "carpeta del plugin)"},
         "perfil": {"type": "string", "enum": ["rapido", "preciso"]},
         "idioma": {"type": "string", "description": "es, en, … o auto"}}}},
    {"name": "estado_reunion",
     "description": "Estado de un job: fase (preparando, descargando, login, transcribiendo, listo, error), "
                    "progreso 0–1, y al terminar la ruta de transcripcion.md y métricas.",
     "inputSchema": {"type": "object", "required": ["job"], "properties": {"job": {"type": "string"}}}},
    {"name": "limpiar_cache",
     "description": "Borra las transcripciones cacheadas y los temporales del plugin (no toca los entregables).",
     "inputSchema": {"type": "object", "properties": {}}},
]


def _job_paths(job):
    d = os.path.join(DATA, "jobs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, job + ".json"), os.path.join(d, job + ".log")


def procesar(args):
    fuente = args["fuente"]
    if not fuente.startswith(("http://", "https://")) and not os.path.isabs(fuente):
        raise ValueError("la fuente local debe ser una ruta absoluta")
    job = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    salida = args.get("salida") or os.path.join(DATA, "salidas", job)
    estado, log = _job_paths(job)
    env = dict(os.environ)
    for k, v in (("VTK_PERFIL", args.get("perfil")), ("VTK_IDIOMA", args.get("idioma"))):
        if v:
            env[k] = v
    with open(estado, "w") as f:
        json.dump({"fase": "preparando", "progreso": 0, "salida": salida}, f)
    with open(log, "ab") as lf:
        subprocess.Popen([sys.executable, os.path.join(HERE, "run_job.py"), fuente, salida, estado],
                         stdout=lf, stderr=lf, stdin=subprocess.DEVNULL, env=env, start_new_session=True)
    return {"job": job, "salida": salida, "siguiente": "llama estado_reunion con este job cada 30–60 s"}


def estado(args):
    path, log = _job_paths(os.path.basename(args["job"]))
    if not os.path.exists(path):
        raise ValueError("job desconocido")
    st = json.load(open(path))
    if st.get("fase") == "listo":
        st["transcripcion"] = os.path.join(st["salida"], "transcripcion.md")
    if st.get("fase") == "error":
        st["log"] = log
    return st


def limpiar(_):
    freed = count = 0
    for sub in ("cache", "tmp"):
        p = os.path.join(DATA, sub)
        for root, _, files in os.walk(p):
            freed += sum(os.path.getsize(os.path.join(root, f)) for f in files)
            count += len(files)
        shutil.rmtree(p, ignore_errors=True)
    return {"archivos_borrados": count, "liberado_kb": round(freed / 1024, 1)}


HANDLERS = {"procesar_reunion": procesar, "estado_reunion": estado, "limpiar_cache": limpiar}


def reply(mid, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": mid}
    msg["error" if error else "result"] = error or result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        try:
            req = json.loads(line)
        except ValueError:
            continue
        mid, method = req.get("id"), req.get("method")
        if mid is None:  # notificación
            continue
        if method == "initialize":
            reply(mid, {"protocolVersion": req.get("params", {}).get("protocolVersion", "2025-06-18"),
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "meeting-to-backlog", "version": "0.1.0"}})
        elif method == "tools/list":
            reply(mid, {"tools": TOOLS})
        elif method == "tools/call":
            p = req.get("params", {})
            try:
                out = HANDLERS[p["name"]](p.get("arguments") or {})
                reply(mid, {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}]})
            except Exception as e:
                reply(mid, {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True})
        elif method == "ping":
            reply(mid, {})
        else:
            reply(mid, error={"code": -32601, "message": f"método no soportado: {method}"})


if __name__ == "__main__":
    main()
