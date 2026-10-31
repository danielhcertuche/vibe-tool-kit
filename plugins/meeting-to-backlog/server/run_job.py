"""Prepara el venv del plugin si hace falta y ejecuta el worker con él. Solo stdlib.

El venv vive en VTK_DATA/venv y se reconstruye si cambia requirements.txt (huella guardada).
Usa `uv` si está instalado (más rápido); si no, venv + pip.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import seguridad  # noqa: E402

seguridad.privado()
DATA = os.environ["VTK_DATA"]
VENV = os.path.join(DATA, "venv")
REQ = os.path.join(HERE, "requirements.txt")
fuente, salida, estado = sys.argv[1:4]


def status(**kw):
    with open(estado, "w") as f:
        json.dump(kw, f, ensure_ascii=False)


py = os.path.join(VENV, "Scripts" if os.name == "nt" else "bin", "python")
want = hashlib.sha256(open(REQ, "rb").read()).hexdigest()
stamp = os.path.join(VENV, ".req-sha256")
falta_venv = not (os.path.exists(py) and os.path.exists(stamp) and open(stamp).read() == want)
hf = os.environ.get("HF_HOME") or os.path.expanduser("~/.cache/huggingface")
falta_modelo = not os.path.isdir(os.path.join(hf, "hub", "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo"))
if falta_venv or falta_modelo:  # primer uso: no empezar una descarga de ~1,8 GB que no cabe
    libre = min(seguridad.espacio_libre_gb(DATA), seguridad.espacio_libre_gb(hf))
    if libre < seguridad.DISCO_MIN_GB:
        status(fase="error", error=f"espacio insuficiente: {libre:.1f} GB libres, el primer uso necesita "
                                   f"{seguridad.DISCO_MIN_GB} GB (dependencias y modelo)")
        raise SystemExit(1)
if falta_venv:
    status(fase="instalando", progreso=0, mensaje="primera vez: instalando dependencias (~200 MB)")
    shutil.rmtree(VENV, ignore_errors=True)
    uv = shutil.which("uv")
    try:
        if uv:
            subprocess.run([uv, "venv", "-q", "-p", sys.executable, VENV], check=True)
            subprocess.run([uv, "pip", "install", "-q", "-p", py, "-r", REQ], check=True)
        else:
            subprocess.run([sys.executable, "-m", "venv", VENV], check=True)
            subprocess.run([py, "-m", "pip", "install", "-q", "-r", REQ], check=True)
    except subprocess.CalledProcessError as e:
        status(fase="error", error=f"no se pudo instalar dependencias ({e.returncode}); ver el log del job")
        raise SystemExit(1)
    open(stamp, "w").write(want)

os.execv(py, [py, os.path.join(HERE, "worker.py"), fuente, salida, estado])
