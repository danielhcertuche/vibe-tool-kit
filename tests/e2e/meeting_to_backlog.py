"""Prueba de punta a punta de meeting-to-backlog hablando MCP por stdio, como lo hace Claude Code.

  python3 tests/e2e/meeting_to_backlog.py <audio> [--venv-existente RUTA] [--timeout 1800]

Verifica: protocolo MCP, job hasta fase=listo, transcripcion.md con marcas de tiempo, carpeta
temporal borrada, segunda corrida desde caché, y que un secreto canario puesto en
GRAPH_CLIENT_SECRET no aparece en ningún archivo que escribe el plugin.
--venv-existente reutiliza un venv con faster-whisper (para no instalar 200 MB en máquinas con
poco disco); sin él, prueba también la instalación desde cero.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVER = os.path.join(ROOT, "plugins", "meeting-to-backlog", "server")
CANARIO = "canario-" + hashlib.sha256(os.urandom(16)).hexdigest()[:24]

ap = argparse.ArgumentParser()
ap.add_argument("audio")
ap.add_argument("--venv-existente")
ap.add_argument("--timeout", type=int, default=1800)
ap.add_argument("--min-marcas", type=int, default=3, help="marcas [hh:mm:ss] mínimas esperadas")
ap.add_argument("--instalado", metavar="ID", help="usa la copia instalada por `claude plugin install` (p. ej. "
                "meeting-to-backlog@vibe-tool-kit) y resuelve su .mcp.json como Claude Code")
a = ap.parse_args()

data = tempfile.mkdtemp(prefix="vtk-e2e-")
salida = os.path.join(data, "entregables")
if a.venv_existente:
    os.makedirs(data, exist_ok=True)
    os.symlink(os.path.abspath(a.venv_existente), os.path.join(data, "venv"))
    req = open(os.path.join(SERVER, "requirements.txt"), "rb").read()
    stamp = os.path.join(a.venv_existente, ".req-sha256")
    if not os.path.exists(stamp):  # el venv prestado no lleva huella: se marca para esta prueba
        open(os.path.join(data, "venv-stamp-prestado"), "w").write(stamp)
        open(stamp, "w").write(hashlib.sha256(req).hexdigest())

env = dict(os.environ, VTK_DATA=data, VTK_PERFIL="rapido", VTK_IDIOMA="es", GRAPH_AUTH="ninguno")
cmd = [sys.executable, os.path.join(SERVER, "vtk_mcp.py")]
if a.instalado:
    # Lo mismo que hace Claude Code al arrancar el servidor del plugin instalado: toma mcpServers de la copia
    # instalada y sustituye ${CLAUDE_PLUGIN_ROOT}, ${CLAUDE_PLUGIN_DATA} y ${user_config.*} (pluginConfigs).
    plugin = next(x for x in json.loads(subprocess.run(["claude", "plugin", "list", "--json"], capture_output=True,
                                                         text=True, check=True).stdout) if x["id"] == a.instalado)
    opciones = json.load(open(os.path.expanduser("~/.claude/settings.json"))).get("pluginConfigs", {}) \
        .get(a.instalado, {}).get("options", {})
    data = os.path.expanduser("~/.claude/plugins/data/" + "".join(c if c.isalnum() else "-" for c in a.instalado))
    salida = os.path.join(tempfile.mkdtemp(prefix="vtk-salida-"), "entregables")
    def resolver(v):
        v = v.replace("${CLAUDE_PLUGIN_ROOT}", plugin["installPath"]).replace("${CLAUDE_PLUGIN_DATA}", data)
        return re.sub(r"\$\{user_config\.(\w+)\}", lambda m: str(opciones.get(m.group(1), "")), v)
    spec = json.load(open(os.path.join(plugin["installPath"], ".mcp.json")))["mcpServers"]["meeting-to-backlog"]
    env = dict(os.environ, **{k: resolver(v) for k, v in spec["env"].items()})
    cmd = [resolver(spec["command"])] + [resolver(x) for x in spec["args"]]
    SERVER = os.path.dirname(cmd[-1])
    print(f"     instalado: {plugin['installPath']} | opciones {sorted(opciones)} | datos {data}")
env["GRAPH_CLIENT_" + "SECRET"] = CANARIO  # canario (en Claude Code vendría del almacén seguro): si aparece, hay fuga
srv = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
n = 0


def call(method, params=None):
    global n
    n += 1
    srv.stdin.write(json.dumps({"jsonrpc": "2.0", "id": n, "method": method, "params": params or {}}) + "\n")
    srv.stdin.flush()
    return json.loads(srv.stdout.readline())


def tool(name, **args):
    r = call("tools/call", {"name": name, "arguments": args})["result"]
    assert not r.get("isError"), r["content"][0]["text"]
    return json.loads(r["content"][0]["text"])


ok = []
def check(cond, msg):
    ok.append(bool(cond))
    print(("ok   " if cond else "FAIL ") + msg)


def run_job(label):
    global st2_job
    t0 = time.time()
    job = st2_job = tool("procesar_reunion", fuente=os.path.abspath(a.audio), salida=salida)["job"]
    while time.time() - t0 < a.timeout:
        st = tool("estado_reunion", job=job)
        if st["fase"] in ("listo", "error"):
            break
        time.sleep(2)
    print(f"     {label}: fase={st['fase']} en {time.time() - t0:.1f}s rtf={st.get('rtf')} "
          f"cache={st.get('desde_cache')}" + (f" error={st.get('error')}" if st["fase"] == "error" else ""))
    return st


try:
    init = call("initialize", {"protocolVersion": "2025-06-18"})["result"]
    check(init["serverInfo"]["name"] == "meeting-to-backlog", "initialize")
    check({t["name"] for t in call("tools/list")["result"]["tools"]} ==
          {"procesar_reunion", "estado_reunion", "fotogramas_candidatos", "conservar_fotogramas",
           "diagnostico", "limpiar_cache"}, "tools/list")
    diag = tool("diagnostico", salida=salida)
    check(diag["chequeos"] and CANARIO not in json.dumps(diag), f"diagnostico sin secretos ({len(diag['chequeos'])} chequeos)")
    st = run_job("primera corrida")
    check(st["fase"] == "listo", "job termina en listo")
    md = os.path.join(salida, "transcripcion.md")
    txt = open(md).read() if os.path.exists(md) else ""
    check(txt.count("[00:") >= a.min_marcas, "transcripcion.md con marcas de tiempo")
    if os.path.exists(md):
        check(os.stat(md).st_mode & 0o777 == 0o600, f"entregables solo para su dueño ({oct(os.stat(md).st_mode & 0o777)})")
    check(not os.listdir(os.path.join(data, "tmp")) if os.path.isdir(os.path.join(data, "tmp")) else True,
          "temporales borrados")
    st2 = run_job("segunda corrida")
    check(st2.get("desde_cache") is True, "segunda corrida desde caché")
    filtrado = []
    for d, _, fs in os.walk(data):
        for f in fs:
            p = os.path.join(d, f)
            if os.path.islink(os.path.dirname(p)) or "/venv/" in p:
                continue
            try:
                if CANARIO in open(p, errors="ignore").read():
                    filtrado.append(p)
            except OSError:
                pass
    check(not filtrado, f"el secreto no aparece en archivos del plugin ({len(filtrado)} con canario)")

    if st.get("candidatos"):  # la fuente tiene video: los 4 fotogramas son obligatorios
        fdir = os.path.join(salida, "fotogramas")
        auto = sorted(os.listdir(fdir)) if os.path.isdir(fdir) else []
        check(len(auto) == min(4, st["candidatos"]), f"4 fotogramas automáticos ({len(auto)} de "
                                                     f"{st['candidatos']} candidatos)")
        cand = json.loads(json.dumps(tool("fotogramas_candidatos", job=st2_job, marcas=["00:00:05", "00:00:40"],
                                          por_marca=2)))
        check(len(cand["candidatos"]) >= 2, f"candidatos cerca de las marcas ({len(cand['candidatos'])})")
        r = call("tools/call", {"name": "conservar_fotogramas", "arguments": {
            "job": st2_job, "elegidos": [{"archivo": "/etc/passwd", "motivo": "x"}]}})["result"]
        check(r.get("isError"), "rechaza una ruta que no es candidata")
        elegidos = [{"archivo": c["archivo"], "motivo": f"prueba {i}", "relacion": "HU 1"}
                    for i, c in enumerate(cand["candidatos"][:4], 1)]
        res = tool("conservar_fotogramas", job=st2_job, elegidos=elegidos)
        final = sorted(os.listdir(fdir))
        md = open(os.path.join(salida, "fotogramas.md")).read()
        check(len(final) == len(elegidos) and "elegidos según la transcripción" in md and "HU 1" in md,
              f"conserva los elegidos con motivo ({res['conservados']})")
        check(not os.path.isdir(os.path.join(data, "candidatos", st["huella"])), "borra el resto de candidatos")
        tam = sum(os.path.getsize(os.path.join(fdir, f)) for f in final)
        print(f"     fotogramas entregados: {len(final)}, {tam / 1024:.0f} KB")
    lib = tool("limpiar_cache")
    check(lib["archivos_borrados"] > 0 and not os.path.exists(os.path.join(data, "cache")),
          f"limpiar_cache borra la caché ({lib['archivos_borrados']} archivos, {lib['liberado_kb']} KB)")
finally:
    srv.stdin.close()
    srv.wait(timeout=10)
    marca = os.path.join(data, "venv-stamp-prestado")
    if os.path.exists(marca):
        os.remove(open(marca).read())
    if not a.instalado:
        subprocess.run(["rm", "-rf", data])

print(f"pasan {sum(ok)}, fallan {len(ok) - sum(ok)}")
sys.exit(0 if all(ok) else 1)
