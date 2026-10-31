"""Modo híbrido de meeting-to-backlog contra un Groq FALSO local (sin cuenta ni red).

  python3 tests/e2e/meeting_hybrid.py <audio> [--venv-existente RUTA] [--pct 0.3]

Casos: (1) nube responde 429 a la primera y luego bien: verifica porcentaje enviado, reintento, que el
archivo sale como a.flac sin prompt, unión por tiempos y registro sin texto; (2) nube siempre falla: el
tramo vuelve a local y la transcripción sale completa. En ambos, la llave canaria no aparece en archivos.
"""
import argparse
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVER = os.path.join(ROOT, "plugins", "meeting-to-backlog", "server")
LLAVE = "llave-canaria-" + hashlib.sha256(os.urandom(8)).hexdigest()[:16]

ap = argparse.ArgumentParser()
ap.add_argument("audio")
ap.add_argument("--venv-existente")
ap.add_argument("--pct", type=float, default=0.3)
a = ap.parse_args()

vistos = []
MODO = {"v": "429-luego-ok"}


def flac_dur(data):
    i = data.find(b"fLaC")
    si = data[i + 8:i + 8 + 34]  # STREAMINFO
    rate = (si[10] << 12) | (si[11] << 4) | (si[12] >> 4)
    total = ((si[13] & 0x0F) << 32) | int.from_bytes(si[14:18], "big")
    return total / rate if rate else 1.0


class Falso(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        vistos.append({"auth_ok": self.headers.get("Authorization") == "Bearer " + LLAVE,
                       "filename_fijo": b'filename="a.flac"' in body, "prompt": b'name="prompt"' in body,
                       "bytes": len(body)})
        if MODO["v"] == "falla" or (MODO["v"] == "429-luego-ok" and len(vistos) == 1):
            code = 500 if MODO["v"] == "falla" else 429
            self.send_response(code)
            self.send_header("retry-after", "1")
            self.end_headers()
            return
        i = body.find(b"\r\n\r\n", body.find(b'filename="a.flac"')) + 4
        dur = flac_dur(body[i:])
        out = json.dumps({"segments": [{"start": 0.0, "end": dur, "text": "[desde-nube]"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Falso)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/openai/v1/audio/transcriptions"

ok = []
def check(c, m):
    ok.append(bool(c))
    print(("ok   " if c else "FAIL ") + m)


def correr(modo):
    MODO["v"] = modo
    vistos.clear()
    data = tempfile.mkdtemp(prefix="vtk-hib-")
    salida = os.path.join(data, "salida")
    if a.venv_existente:
        os.symlink(os.path.abspath(a.venv_existente), os.path.join(data, "venv"))
        req = open(os.path.join(SERVER, "requirements.txt"), "rb").read()
        open(os.path.join(a.venv_existente, ".req-sha256"), "w").write(hashlib.sha256(req).hexdigest())
    env = dict(os.environ, VTK_DATA=data, VTK_NUBE_URL=url, VTK_NUBE_PCT=str(a.pct), GRAPH_AUTH="ninguno")
    env["GROQ_" + "API_KEY"] = LLAVE
    est = os.path.join(data, "estado.json")
    t0 = time.time()
    subprocess.run([sys.executable, os.path.join(SERVER, "run_job.py"), os.path.abspath(a.audio), salida, est],
                   env=env, check=False)
    st = json.load(open(est))
    txt = open(os.path.join(salida, "transcripcion.md")).read() if os.path.exists(os.path.join(salida, "transcripcion.md")) else ""
    reg = os.path.join(data, "registro_nube.jsonl")
    filas = [json.loads(x) for x in open(reg)] if os.path.exists(reg) else []
    fuga = [os.path.join(d, f) for d, _, fs in os.walk(data) if "/venv" not in d
            for f in fs if LLAVE in open(os.path.join(d, f), errors="ignore").read()]
    if a.venv_existente:
        os.remove(os.path.join(a.venv_existente, ".req-sha256"))
    shutil.rmtree(data)
    print(f"     [{modo}] {time.time() - t0:.1f}s · híbrido={st.get('hibrido')} · peticiones={len(vistos)}")
    return st, txt, filas, fuga


st, txt, filas, fuga = correr("429-luego-ok")
h = st.get("hibrido") or {}
check(st["fase"] == "listo", "job híbrido termina en listo")
check(abs(h.get("pct_enviado", 0) - a.pct) <= 0.12, f"porcentaje enviado ≈ {a.pct} ({h.get('pct_enviado')})")
check(len(vistos) == h.get("bloques_nube", 0) + 1, "reintenta tras un 429")
check(all(v["filename_fijo"] and not v["prompt"] and v["auth_ok"] for v in vistos),
      "sale como a.flac, sin prompt, con la llave correcta")
lineas = [x for x in txt.splitlines() if x.startswith("[")]
check(lineas and "[desde-nube]" in lineas[-1] and "[desde-nube]" not in lineas[0],
      "une por tiempos: local al inicio, nube al final")
check(filas and all(set(f) == {"ts", "huella", "proveedor", "desde_s", "dur_s", "bytes", "http", "seg"}
                    for f in filas), f"registro local sin audio ni texto ({len(filas)} filas)")
check(not fuga, "la llave no aparece en archivos")

st, txt, filas, fuga = correr("falla")
h = st.get("hibrido") or {}
check(st["fase"] == "listo" and h.get("devueltos_a_local", 0) >= 1, "si la nube falla, el tramo vuelve a local")
check("[desde-nube]" not in txt and txt.count("\n[") >= 2, "la transcripción sale completa sin la nube")
check(not fuga, "la llave no aparece en archivos (caso falla)")

srv.shutdown()
print(f"pasan {sum(ok)}, fallan {len(ok) - sum(ok)}")
sys.exit(0 if all(ok) else 1)
