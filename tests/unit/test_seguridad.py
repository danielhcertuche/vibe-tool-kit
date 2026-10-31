"""Pruebas de seguridad.py: ocultar secretos, permisos, retención y diagnóstico sin valores secretos.

  python3 tests/unit/test_seguridad.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time

SERVER = os.path.join(os.path.dirname(__file__), "..", "..", "plugins", "meeting-to-backlog", "server")
sys.path.insert(0, SERVER)
import seguridad  # noqa: E402

ok = []


def check(c, m):
    ok.append(bool(c))
    print(("ok   " if c else "FAIL ") + m)


LLAVE = "gsk_" + "Q" * 40
SECRETO = "s3cr3t0-de-graph-" + "x" * 20
os.environ["GROQ_API_KEY"], os.environ["GRAPH_CLIENT_SECRET"] = LLAVE, SECRETO
# Los valores falsos se arman por partes para que los escáneres de secretos no los tomen por reales.
BEARER = "abcdefghij" + "klmnopqrst" + "uvwxyz0123"
JWT = "eyJ" + "hbGciOiJSUzI1NiJ9" + "." + "eyJ" + "zdWIiOiIxMjM0NTY3ODkw" + "." + "SflKxwRJSM" + "eKKF2QT4fwpM"
casos = {
    "llave de Groq": f"error al llamar con {LLAVE}",
    "secreto de Graph": f"invalid_client para {SECRETO}",
    "cabecera Bearer": "Authorization: Bearer " + BEARER,
    "JWT de Entra": "token " + JWT,
    "usuario:token en URL": "fatal: https://" + "pat:" + "tok3nFalso123456" + "@example.com/org/_git/repo",
    "firma SAS": "https://almacen.example.com/c?sv=2024&sig=AbC%2Fd3f&se=2026",
}
for nombre, texto in casos.items():
    limpio = seguridad.limpiar_secretos(texto)
    fuga = any(x in limpio for x in (LLAVE, SECRETO, BEARER, JWT.split(".")[1],
                                       "tok3nFalso123456", "AbC%2Fd3f"))
    check(not fuga and "oculto" in limpio, f"oculta {nombre}")
check(seguridad.limpiar_secretos("job sin secretos: 13 min") == "job sin secretos: 13 min", "no toca texto normal")

with tempfile.TemporaryDirectory() as d:
    # permisos: se prueba en un proceso aparte porque umask es global
    code = f"import sys; sys.path.insert(0, {SERVER!r}); import seguridad, os; seguridad.privado(); " \
           f"open({d!r} + '/a.txt', 'w').write('x'); os.makedirs({d!r} + '/sub')"
    subprocess.run([sys.executable, "-c", code], check=True)
    check(os.stat(d + "/a.txt").st_mode & 0o777 == 0o600, "archivos nuevos quedan en 600")
    check(os.stat(d + "/sub").st_mode & 0o777 == 0o700, "carpetas nuevas quedan en 700")

    base = os.path.join(d, "cache")
    os.makedirs(base)
    for nombre, edad_dias in (("viejo.json", 10), ("nuevo.json", 1)):
        p = os.path.join(base, nombre)
        open(p, "w").write("{}")
        t = time.time() - edad_dias * 86400
        os.utime(p, (t, t))
    n = seguridad.purgar(base, 7)
    check(n == 1 and os.listdir(base) == ["nuevo.json"], "retención: borra solo lo de más de 7 días")

    os.environ["GRAPH_AUTH"] = "aplicacion"
    diag = seguridad.diagnostico(d, os.path.join(d, "OneDrive - Empresa", "reuniones"))
    texto = json.dumps(diag, ensure_ascii=False)
    check(LLAVE not in texto and SECRETO not in texto, "el diagnóstico no incluye valores secretos")
    est = {x["chequeo"]: x["estado"] for x in diag}
    check(est.get("acceso a Graph") == "aviso", "avisa del alcance del modo aplicación (Sites.Selected)")
    check(est.get("carpeta de salida en carpeta sincronizada") == "aviso", "avisa si la salida cae en OneDrive")
    check(est.get("python") == "ok", "Python 3.11 o más")

print(f"pasan {sum(ok)}, fallan {len(ok) - sum(ok)}")
sys.exit(0 if all(ok) else 1)
