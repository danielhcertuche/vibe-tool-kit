#!/usr/bin/env python3
"""Servidor MCP (stdio, solo stdlib) del plugin meeting-to-backlog.

Tools:
  procesar_reunion(fuente, salida?, perfil?, idioma?)  lanza un job en segundo plano
  estado_reunion(job)                                   fase, progreso, rutas y métricas
  fotogramas_candidatos(job, marcas)                    candidatos cercanos a los momentos clave
  conservar_fotogramas(job, elegidos)                   fija los 4 fotogramas entregados
  limpiar_cache()                                       borra caché, temporales y candidatos

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
         "idioma": {"type": "string", "description": "es, en, … o auto"},
         "nube_pct": {"type": "number", "minimum": 0, "maximum": 0.5,
                      "description": "Fracción del audio que se transcribe en la nube (Groq), en paralelo con lo "
                                     "local. 0 = todo local (por defecto). Solo con autorización del usuario PARA "
                                     "ESTA reunión y si su clasificación de datos lo permite."}}}},
    {"name": "estado_reunion",
     "description": "Estado de un job: fase (preparando, descargando, login, transcribiendo, listo, error), "
                    "progreso 0–1, y al terminar la ruta de transcripcion.md y métricas.",
     "inputSchema": {"type": "object", "required": ["job"], "properties": {"job": {"type": "string"}}}},
    {"name": "fotogramas_candidatos",
     "description": "Fotogramas candidatos de un job terminado, los más cercanos a cada momento clave. Pásale "
                    "las marcas [hh:mm:ss] del objetivo, las decisiones y la evidencia de cada HU; mira las "
                    "imágenes devueltas y elige 4 con conservar_fotogramas.",
     "inputSchema": {"type": "object", "required": ["job", "marcas"], "properties": {
         "job": {"type": "string"},
         "marcas": {"type": "array", "items": {"type": "string", "pattern": "^\\d{2}:\\d{2}:\\d{2}$"},
                    "minItems": 1, "maxItems": 12},
         "por_marca": {"type": "integer", "minimum": 1, "maximum": 4}}}},
    {"name": "conservar_fotogramas",
     "description": "Fija los 4 fotogramas que se entregan (reemplaza la selección automática), cada uno con "
                    "por qué es relevante y con qué decisión o HU se relaciona. Borra el resto de candidatos.",
     "inputSchema": {"type": "object", "required": ["job", "elegidos"], "properties": {
         "job": {"type": "string"},
         "elegidos": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
             "type": "object", "required": ["archivo", "motivo"], "properties": {
                 "archivo": {"type": "string", "description": "ruta devuelta por fotogramas_candidatos"},
                 "motivo": {"type": "string"}, "relacion": {"type": "string"}}}}}}},
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
    for k, v in (("VTK_PERFIL", args.get("perfil")), ("VTK_IDIOMA", args.get("idioma")),
                 ("VTK_NUBE_PCT", str(args["nube_pct"]) if args.get("nube_pct") else None)):
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


def _segundos(m):
    h, mi, se = (int(x) for x in m.split(":"))
    return h * 3600 + mi * 60 + se


def _candidatos_de(job):
    st = estado({"job": job})
    if st.get("fase") != "listo" or not st.get("huella"):
        raise ValueError("el job no ha terminado o no tiene huella")
    cdir = os.path.join(DATA, "candidatos", st["huella"])
    idx = os.path.join(cdir, "index.json")
    if not os.path.exists(idx):
        raise ValueError("no quedan candidatos: la reunión no tiene video o ya se eligieron los fotogramas")
    return st, cdir, json.load(open(idx))


def candidatos(args):
    _, cdir, cands = _candidatos_de(args["job"])
    k = int(args.get("por_marca") or 2)
    vistos, out = set(), []
    for m in args["marcas"]:
        t = _segundos(m)
        for c in sorted(cands, key=lambda c: abs(c["t"] - t))[:k]:
            if c["archivo"] not in vistos:
                vistos.add(c["archivo"])
                out.append({"marca_pedida": m, "momento": c["marca"], "archivo": os.path.join(cdir, c["archivo"])})
    return {"candidatos": out, "total_disponibles": len(cands)}


def conservar(args):
    st, cdir, cands = _candidatos_de(args["job"])
    por_nombre = {c["archivo"]: c for c in cands}
    elegidos = []
    for e in args["elegidos"][:4]:
        p = os.path.realpath(e["archivo"])
        name = os.path.basename(p)
        if os.path.dirname(p) != os.path.realpath(cdir) or name not in por_nombre:
            raise ValueError(f"{e['archivo']} no es un candidato de este job")
        elegidos.append(dict(por_nombre[name], motivo=e["motivo"].replace("|", "/"),
                             relacion=(e.get("relacion") or "—").replace("|", "/")))
    elegidos.sort(key=lambda x: x["t"])
    # Misma lógica que frames.publicar, en stdlib: este proceso no tiene el venv.
    fdir = os.path.join(st["salida"], "fotogramas")
    shutil.rmtree(fdir, ignore_errors=True)
    os.makedirs(fdir)
    md = ["# Fotogramas clave (elegidos según la transcripción)", "",
          "| # | Momento | Archivo | Por qué es relevante | Relacionado con |", "|---|---|---|---|---|"]
    for i, x in enumerate(elegidos, 1):
        name = f"f{i}_{x['marca'].replace(':', '')}.jpg"
        shutil.copy2(os.path.join(cdir, x["archivo"]), os.path.join(fdir, name))
        md.append(f"| {i} | `[{x['marca']}]` | `fotogramas/{name}` | {x['motivo']} | {x['relacion']} |")
    open(os.path.join(st["salida"], "fotogramas.md"), "w").write("\n".join(md) + "\n")
    shutil.rmtree(cdir, ignore_errors=True)  # el resto de candidatos no se guarda
    return {"conservados": len(elegidos), "carpeta": fdir, "indice": os.path.join(st["salida"], "fotogramas.md")}


def limpiar(_):
    freed = count = 0
    for sub in ("cache", "tmp", "candidatos"):
        p = os.path.join(DATA, sub)
        for root, _, files in os.walk(p):
            freed += sum(os.path.getsize(os.path.join(root, f)) for f in files)
            count += len(files)
        shutil.rmtree(p, ignore_errors=True)
    return {"archivos_borrados": count, "liberado_kb": round(freed / 1024, 1)}


HANDLERS = {"procesar_reunion": procesar, "estado_reunion": estado, "fotogramas_candidatos": candidatos,
            "conservar_fotogramas": conservar, "limpiar_cache": limpiar}


def _purgar_viejos(dias=2):
    """Candidatos de más de `dias` días sin elegir: se borran al arrancar el servidor."""
    base = os.path.join(DATA, "candidatos")
    if os.path.isdir(base):
        for d in os.listdir(base):
            p = os.path.join(base, d)
            if time.time() - os.path.getmtime(p) > dias * 86400:
                shutil.rmtree(p, ignore_errors=True)


def reply(mid, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": mid}
    msg["error" if error else "result"] = error or result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    _purgar_viejos()
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
